"""Local semantic search: a small sentence-embedding model, vectors in SQLite.

The model (all-MiniLM-L6-v2 as ONNX) is downloaded once into
``{DATA_DIR}/models`` and run through onnxruntime. Every active job gets one
384-dimensional unit vector; search is a cosine product over the matrix.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import TYPE_CHECKING, Iterable, Sequence

import numpy as np
import requests

from openings.config import EMBEDDING_MODEL
from openings.logger import get_logger
from openings.models import Job

if TYPE_CHECKING:
    from openings.config import Config
    from openings.db import JobDatabase

MODEL_REPO = "https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/resolve/main"
MODEL_FILES = {
    "model.onnx": f"{MODEL_REPO}/onnx/model.onnx",
    "tokenizer.json": f"{MODEL_REPO}/tokenizer.json",
}
MAX_TOKENS = 256
DESCRIPTION_CHARS = 2000


def job_text(job: Job) -> str:
    parts = [job.title, job.company, job.location]
    if job.description:
        parts.append(job.description[:DESCRIPTION_CHARS])
    return "\n".join(part for part in parts if part)


class EmbeddingModel:
    """Tokenizer plus ONNX session, loaded lazily."""

    def __init__(self, models_dir: Path, name: str = EMBEDDING_MODEL):
        self.name = name
        self.directory = Path(models_dir) / name
        self._lock = threading.Lock()
        self._session = None
        self._tokenizer = None
        self.logger = get_logger("embeddings")

    def ensure_downloaded(self, timeout: float = 120.0) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        for filename, url in MODEL_FILES.items():
            target = self.directory / filename
            if target.is_file() and target.stat().st_size > 0:
                continue
            self.logger.info("Downloading %s to %s", filename, self.directory)
            with requests.get(url, stream=True, timeout=timeout) as response:
                response.raise_for_status()
                partial = target.with_suffix(target.suffix + ".part")
                with partial.open("wb") as handle:
                    for chunk in response.iter_content(chunk_size=1 << 20):
                        handle.write(chunk)
                partial.replace(target)

    def _load(self) -> None:
        with self._lock:
            if self._session is not None:
                return
            import onnxruntime as ort
            from tokenizers import Tokenizer

            self.ensure_downloaded()
            tokenizer = Tokenizer.from_file(str(self.directory / "tokenizer.json"))
            tokenizer.enable_truncation(max_length=MAX_TOKENS)
            tokenizer.enable_padding(length=None)
            options = ort.SessionOptions()
            options.intra_op_num_threads = 2
            options.log_severity_level = 3
            self._tokenizer = tokenizer
            self._session = ort.InferenceSession(
                str(self.directory / "model.onnx"),
                sess_options=options,
                providers=["CPUExecutionProvider"],
            )

    def embed(self, texts: Sequence[str], batch_size: int = 32) -> np.ndarray:
        """Unit vectors, one row per text."""
        if not texts:
            return np.zeros((0, 384), dtype=np.float32)
        self._load()
        assert self._session is not None and self._tokenizer is not None
        input_names = {node.name for node in self._session.get_inputs()}
        vectors: list[np.ndarray] = []
        for start in range(0, len(texts), max(1, batch_size)):
            batch = [text or " " for text in texts[start : start + batch_size]]
            encoded = self._tokenizer.encode_batch(batch)
            ids = np.array([item.ids for item in encoded], dtype=np.int64)
            mask = np.array([item.attention_mask for item in encoded], dtype=np.int64)
            feeds = {"input_ids": ids, "attention_mask": mask}
            if "token_type_ids" in input_names:
                feeds["token_type_ids"] = np.zeros_like(ids)
            hidden = self._session.run(None, feeds)[0]
            weights = mask[..., None].astype(np.float32)
            pooled = (hidden * weights).sum(axis=1) / np.clip(weights.sum(axis=1), 1e-9, None)
            norms = np.linalg.norm(pooled, axis=1, keepdims=True)
            vectors.append((pooled / np.clip(norms, 1e-9, None)).astype(np.float32))
        return np.vstack(vectors)


class Embeddings:
    """Embed jobs on save, backfill the rest, search by cosine similarity."""

    def __init__(self, db: JobDatabase, config: Config):
        self.db = db
        self.config = config
        self.model = EmbeddingModel(config.models_dir)
        self.logger = get_logger("embeddings")
        self._cache: tuple[tuple[int, str], list[str], np.ndarray] | None = None
        self._cache_lock = threading.Lock()

    @property
    def model_name(self) -> str:
        return self.model.name

    def embed_jobs(self, jobs: Iterable[Job]) -> int:
        batch = [job for job in jobs if job.status.value != "blacklisted"]
        if not batch:
            return 0
        vectors = self.model.embed(
            [job_text(job) for job in batch], batch_size=self.config.embeddings.batch_size
        )
        return self.db.set_embeddings(
            self.model_name, [(job.job_id, vector) for job, vector in zip(batch, vectors)]
        )

    def backfill(self, limit: int | None = None) -> int:
        """Embed every active job that has no vector yet."""
        missing = self.db.jobs_without_embedding(self.model_name, limit)
        if not missing:
            return 0
        done = 0
        size = self.config.embeddings.batch_size
        for start in range(0, len(missing), size):
            jobs = self.db.get_jobs(missing[start : start + size])
            done += self.embed_jobs(jobs)
        self.logger.info("Embedded %d jobs", done)
        return done

    def count(self) -> int:
        return self.db.count_embeddings(self.model_name)

    def _matrix(self) -> tuple[list[str], np.ndarray]:
        stamp = self.db.embedding_stamp(self.model_name)
        with self._cache_lock:
            if self._cache is not None and self._cache[0] == stamp:
                return self._cache[1], self._cache[2]
            ids, matrix = self.db.embedding_matrix(self.model_name)
            self._cache = (stamp, ids, matrix)
            return ids, matrix

    def _rank(
        self, vector: np.ndarray, n: int, exclude: str | None = None
    ) -> list[tuple[str, float]]:
        ids, matrix = self._matrix()
        if not ids:
            return []
        scores = matrix @ vector
        order = np.argsort(-scores)
        results: list[tuple[str, float]] = []
        for index in order:
            job_id = ids[int(index)]
            if job_id == exclude:
                continue
            results.append((job_id, float(scores[int(index)])))
            if len(results) >= n:
                break
        return results

    def search(self, query: str, n: int = 10) -> list[tuple[str, float]]:
        """``(job_id, similarity)`` for the closest active jobs to ``query``."""
        if not query.strip():
            return []
        vector = self.model.embed([query])[0]
        return self._rank(vector, n)

    def similar(self, job_id: str, n: int = 10) -> list[tuple[str, float]]:
        """Jobs closest to an existing one; embeds it first when needed."""
        ids, matrix = self._matrix()
        if job_id in ids:
            vector = matrix[ids.index(job_id)]
        else:
            job = self.db.get_job(job_id)
            if job is None:
                return []
            vector = self.model.embed([job_text(job)])[0]
        return self._rank(vector, n, exclude=job_id)
