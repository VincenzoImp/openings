"""
Vector store for semantic job search using ChromaDB's built-in ONNX embedder.

Embeds job text (title + description + company + location) into vectors
using ChromaDB's ``DefaultEmbeddingFunction`` (onnxruntime + all-MiniLM-L6-v2),
enabling natural language similarity search over the job database without
pulling in torch / sentence-transformers / transformers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import chromadb
from chromadb.config import Settings
from chromadb.utils.embedding_functions import (  # type: ignore[attr-defined]
    DefaultEmbeddingFunction,
)

if TYPE_CHECKING:
    import pandas as pd

logger = logging.getLogger("job_search.vector_store")


@dataclass(frozen=True)
class SemanticSearchResult:
    """Result from a semantic search query."""

    job_id: str
    distance: float
    similarity: float  # 1 - distance, clamped to [0, 1]
    metadata: dict  # title, company, location, site, relevance_score


class JobVectorStore:
    """ChromaDB-based vector store for semantic job search.

    Uses ChromaDB's built-in ONNX embedder (``DefaultEmbeddingFunction``,
    bundling ``all-MiniLM-L6-v2``) to embed job text (title + description +
    company + location) into vectors, enabling natural language similarity
    search across all stored jobs — without requiring torch or
    sentence-transformers.
    """

    COLLECTION_NAME = "jobs"
    TEXT_FIELDS = ("title", "company", "location", "description")
    METADATA_FIELDS = (
        "title",
        "company",
        "location",
        "site",
        "relevance_score",
        "first_seen",
        "job_url",
    )

    def __init__(self, persist_dir: Path) -> None:
        self._persist_dir = Path(persist_dir)
        self._persist_dir.mkdir(parents=True, exist_ok=True)

        self._embedding_fn = DefaultEmbeddingFunction()
        # Disable ChromaDB telemetry at the Settings level. The
        # ANONYMIZED_TELEMETRY env var is not honoured by every bundled
        # posthog version (it still fires noisy 'capture() takes 1 positional
        # argument but 3 were given' errors); passing Settings explicitly is
        # the contract that the ChromaDB client honours end-to-end.
        self._client = chromadb.PersistentClient(
            path=str(self._persist_dir),
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            embedding_function=self._embedding_fn,  # type: ignore[arg-type]
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            "Vector store initialized: %d jobs embedded", self._collection.count()
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_document(
        self, title: str, company: str, location: str, description: str
    ) -> str:
        """Build searchable text from job fields.

        Mirrors the pattern used by ``_get_job_text`` in the scoring module:
        concatenates the non-empty text fields separated by `` | ``.
        """
        parts: list[str] = []
        for val in (title, company, location, description):
            if val and str(val).strip() and str(val).lower() not in ("nan", "none"):
                parts.append(str(val).strip())
        return " | ".join(parts)

    def _build_metadata(self, record: dict[str, Any]) -> dict[str, Any]:
        """Extract metadata fields from a job record.

        ChromaDB metadata values must be str, int, float, or bool.
        """
        meta: dict[str, Any] = {}
        for field in self.METADATA_FIELDS:
            val = record.get(field)
            if val is not None and str(val).lower() not in ("nan", "none", ""):
                if isinstance(val, (int, float, str, bool)):
                    meta[field] = val
                else:
                    meta[field] = str(val)
        return meta

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_jobs(self, jobs: list[dict], batch_size: int = 100) -> int:
        """Upsert jobs into the vector store.

        Args:
            jobs: List of dicts, each containing at least ``job_id`` and
                one or more of the ``TEXT_FIELDS``.
            batch_size: Number of jobs to upsert per ChromaDB call.

        Returns:
            Count of jobs successfully processed.
        """
        if not jobs:
            return 0

        total = 0
        for i in range(0, len(jobs), batch_size):
            batch = jobs[i : i + batch_size]
            ids: list[str] = []
            documents: list[str] = []
            metadatas: list[dict[str, Any]] = []

            for job in batch:
                job_id = str(job.get("job_id", ""))
                if not job_id:
                    continue

                doc = self._build_document(
                    job.get("title", ""),
                    job.get("company", ""),
                    job.get("location", ""),
                    job.get("description", ""),
                )
                if not doc.strip():
                    continue

                ids.append(job_id)
                documents.append(doc)
                metadatas.append(self._build_metadata(job))

            if ids:
                self._collection.upsert(
                    ids=ids,
                    documents=documents,
                    metadatas=metadatas,  # type: ignore[arg-type]
                )
                total += len(ids)

        logger.info("Embedded %d jobs into vector store", total)
        return total

    def add_jobs_from_dataframe(self, df: pd.DataFrame) -> int:
        """Convenience wrapper to add jobs from a pandas DataFrame.

        NaN values are converted to ``None`` before processing so they
        are handled consistently by ``_build_document`` and
        ``_build_metadata``.
        """
        import pandas as pd  # noqa: F811 — runtime import for NaN handling

        records: list[dict] = df.where(pd.notna(df), None).to_dict("records")
        return self.add_jobs(records)

    def search(
        self,
        query: str,
        n_results: int = 20,
        min_score: int | None = None,
        site: str | None = None,
    ) -> list[SemanticSearchResult]:
        """Search for jobs semantically similar to *query*.

        Args:
            query: Natural-language search string.
            n_results: Maximum number of results to return.
            min_score: If set, only return jobs with ``relevance_score >= min_score``.
            site: If set, only return jobs from this job board.

        Returns:
            List of :class:`SemanticSearchResult`, ordered by similarity
            (most similar first).
        """
        if not query.strip():
            return []

        if self._collection.count() == 0:
            return []

        # Build optional ChromaDB ``where`` filter
        conditions: list[dict] = []
        if min_score is not None:
            conditions.append({"relevance_score": {"$gte": min_score}})
        if site:
            conditions.append({"site": site})

        where: dict | None = None
        if len(conditions) == 1:
            where = conditions[0]
        elif len(conditions) > 1:
            where = {"$and": conditions}

        n = min(n_results, self._collection.count())

        _include: list = ["distances", "metadatas"]  # type: ignore[type-arg]
        results = self._collection.query(
            query_texts=[query],
            n_results=n,
            where=where,
            include=_include,
        )

        search_results: list[SemanticSearchResult] = []
        distances = results.get("distances") or []
        metadatas = results.get("metadatas") or []
        ids = results.get("ids") or []
        if ids and ids[0]:
            for job_id, distance, metadata in zip(
                ids[0],
                distances[0] if distances else [],
                metadatas[0] if metadatas else [],
            ):
                similarity = max(0.0, min(1.0, 1.0 - distance))
                search_results.append(
                    SemanticSearchResult(
                        job_id=job_id,
                        distance=distance,
                        similarity=similarity,
                        metadata=dict(metadata),
                    )
                )

        return search_results

    def delete_jobs(self, job_ids: list[str]) -> None:
        """Remove jobs from the vector store.

        Silently skips IDs that are not present in the collection.
        """
        if not job_ids:
            return
        # ChromaDB raises if we delete IDs that don't exist; filter first.
        _include: list = []  # type: ignore[type-arg]
        existing = set(self._collection.get(ids=job_ids, include=_include)["ids"])
        to_delete = [jid for jid in job_ids if jid in existing]
        if to_delete:
            self._collection.delete(ids=to_delete)
            logger.info("Deleted %d jobs from vector store", len(to_delete))

    def get_embedded_ids(self) -> set[str]:
        """Return all job IDs currently in the vector store."""
        _include: list = []  # type: ignore[type-arg]
        result = self._collection.get(include=_include)
        return set(result["ids"])

    def count(self) -> int:
        """Number of jobs in the vector store."""
        return self._collection.count()

    def reset(self) -> None:
        """Delete all data and recreate the collection."""
        self._client.delete_collection(self.COLLECTION_NAME)
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            embedding_function=self._embedding_fn,  # type: ignore[arg-type]
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("Vector store reset")


# ------------------------------------------------------------------
# Singleton accessor
# ------------------------------------------------------------------

_vector_store: JobVectorStore | None = None
_vector_store_key: str | None = None


def get_vector_store(persist_dir: Path) -> JobVectorStore:
    """Get or create the singleton :class:`JobVectorStore`.

    Args:
        persist_dir: Full path where the ChromaDB collection should live.

    Returns:
        The shared ``JobVectorStore`` instance.
    """
    global _vector_store, _vector_store_key
    resolved_path = Path(persist_dir).expanduser().resolve()
    key = str(resolved_path)

    if _vector_store is None or _vector_store_key != key:
        _vector_store = JobVectorStore(persist_dir=resolved_path)
        _vector_store_key = key
    return _vector_store
