"""Embedding vectors stored next to the jobs they describe."""

from __future__ import annotations

from typing import Sequence

import numpy as np

from openings.db.base import Store, chunks, placeholders, unique
from openings.models import JobStatus, utcnow


class EmbeddingsMixin(Store):
    def set_embeddings(self, model: str, rows: Sequence[tuple[str, np.ndarray]]) -> int:
        if not rows:
            return 0
        now = utcnow()
        with self._connection() as conn:
            conn.executemany(
                "INSERT INTO embeddings (job_id, model, vector, updated_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(job_id) DO UPDATE SET model = excluded.model, "
                "vector = excluded.vector, updated_at = excluded.updated_at",
                [
                    (job_id, model, np.asarray(vector, dtype=np.float32).tobytes(), now)
                    for job_id, vector in rows
                ],
            )
            conn.commit()
        return len(rows)

    def jobs_without_embedding(self, model: str, limit: int | None = None) -> list[str]:
        """Active jobs that have no vector for ``model`` yet."""
        sql = (
            "SELECT jobs.job_id FROM jobs LEFT JOIN embeddings "
            "ON embeddings.job_id = jobs.job_id AND embeddings.model = ? "
            "WHERE embeddings.job_id IS NULL AND jobs.status != ? ORDER BY jobs.last_seen DESC"
        )
        params: list[object] = [model, JobStatus.BLACKLISTED.value]
        if limit:
            sql += " LIMIT ?"
            params.append(int(limit))
        with self._connection() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [row["job_id"] for row in rows]

    def delete_embeddings(self, job_ids: Sequence[str]) -> int:
        ids = unique(job_ids)
        if not ids:
            return 0
        deleted = 0
        with self._connection() as conn:
            for chunk in chunks(ids):
                cursor = conn.execute(
                    f"DELETE FROM embeddings WHERE job_id IN ({placeholders(len(chunk))})",
                    list(chunk),
                )
                deleted += cursor.rowcount
            conn.commit()
        return deleted

    def embedding_matrix(self, model: str) -> tuple[list[str], np.ndarray]:
        """Every active job's vector as one matrix, rows aligned with the ids."""
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT embeddings.job_id, embeddings.vector FROM embeddings "
                "JOIN jobs ON jobs.job_id = embeddings.job_id "
                "WHERE embeddings.model = ? AND jobs.status != ?",
                (model, JobStatus.BLACKLISTED.value),
            ).fetchall()
        if not rows:
            return [], np.zeros((0, 0), dtype=np.float32)
        ids = [row["job_id"] for row in rows]
        matrix = np.vstack([np.frombuffer(row["vector"], dtype=np.float32) for row in rows])
        return ids, matrix

    def embedding_stamp(self, model: str) -> tuple[int, str]:
        """Cheap change detector for the in-process matrix cache."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*), COALESCE(MAX(updated_at), '') FROM embeddings WHERE model = ?",
                (model,),
            ).fetchone()
        return int(row[0]), str(row[1])

    def count_embeddings(self, model: str) -> int:
        with self._connection() as conn:
            return int(
                conn.execute(
                    "SELECT COUNT(*) FROM embeddings WHERE model = ?", (model,)
                ).fetchone()[0]
            )
