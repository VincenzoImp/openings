"""
Vector store for semantic job search using ChromaDB and sentence-transformers.

Embeds job text (title + description + company + location) into vectors
using sentence-transformers, enabling natural language similarity search
over the job database.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

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

    Uses sentence-transformers to embed job text (title + description +
    company + location) into vectors, enabling natural language similarity
    search across all stored jobs.
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

    def __init__(self, persist_dir: Path, model_name: str = "all-MiniLM-L6-v2") -> None:
        self._persist_dir = Path(persist_dir)
        self._persist_dir.mkdir(parents=True, exist_ok=True)

        self._embedding_fn = SentenceTransformerEmbeddingFunction(model_name=model_name)
        self._client = chromadb.PersistentClient(path=str(self._persist_dir))
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            embedding_function=self._embedding_fn,
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

    def _build_metadata(self, record: dict) -> dict:
        """Extract metadata fields from a job record.

        ChromaDB metadata values must be str, int, float, or bool.
        """
        meta: dict = {}
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
            metadatas: list[dict] = []

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
                    ids=ids, documents=documents, metadatas=metadatas
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

        results = self._collection.query(
            query_texts=[query],
            n_results=n,
            where=where,
            include=["distances", "metadatas"],
        )

        search_results: list[SemanticSearchResult] = []
        if results and results["ids"] and results["ids"][0]:
            for job_id, distance, metadata in zip(
                results["ids"][0],
                results["distances"][0],
                results["metadatas"][0],
            ):
                similarity = max(0.0, min(1.0, 1.0 - distance))
                search_results.append(
                    SemanticSearchResult(
                        job_id=job_id,
                        distance=distance,
                        similarity=similarity,
                        metadata=metadata,
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
        existing = set(self._collection.get(ids=job_ids, include=[])["ids"])
        to_delete = [jid for jid in job_ids if jid in existing]
        if to_delete:
            self._collection.delete(ids=to_delete)
            logger.info("Deleted %d jobs from vector store", len(to_delete))

    def get_embedded_ids(self) -> set[str]:
        """Return all job IDs currently in the vector store."""
        result = self._collection.get(include=[])
        return set(result["ids"])

    def count(self) -> int:
        """Number of jobs in the vector store."""
        return self._collection.count()

    def reset(self) -> None:
        """Delete all data and recreate the collection."""
        self._client.delete_collection(self.COLLECTION_NAME)
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            embedding_function=self._embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("Vector store reset")


# ------------------------------------------------------------------
# Singleton accessor
# ------------------------------------------------------------------

_vector_store: JobVectorStore | None = None


def get_vector_store(
    data_dir: Path,
    model_name: str = "all-MiniLM-L6-v2",
) -> JobVectorStore:
    """Get or create the singleton :class:`JobVectorStore`.

    Args:
        data_dir: Base data directory (e.g. ``config.data_path``).
            The ChromaDB files are stored under ``<data_dir>/chroma/``.
        model_name: Sentence-transformer model to use for embeddings.

    Returns:
        The shared ``JobVectorStore`` instance.
    """
    global _vector_store
    if _vector_store is None:
        chroma_path = Path(data_dir) / "chroma"
        _vector_store = JobVectorStore(
            persist_dir=chroma_path,
            model_name=model_name,
        )
    return _vector_store
