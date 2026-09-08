"""Retention: only jobs in status ``new`` are ever removed automatically."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING

from openings.db.base import Store
from openings.models import PROTECTED_STATUSES, JobStatus

if TYPE_CHECKING:
    from openings.config import Config

PROTECTED_SQL = "status IN ({})".format(
    ",".join(f"'{status.value}'" for status in sorted(PROTECTED_STATUSES))
)
UNPROTECTED_SQL = f"status = '{JobStatus.NEW.value}'"


@dataclass
class ReconciliationReport:
    """Outcome of :meth:`JobDatabase.reconcile`."""

    deleted_below_score: int = 0
    deleted_stale: int = 0
    protected: int = 0

    @property
    def total_deleted(self) -> int:
        return self.deleted_below_score + self.deleted_stale

    def to_dict(self) -> dict[str, int]:
        return {
            "deleted_below_score": self.deleted_below_score,
            "deleted_stale": self.deleted_stale,
            "protected": self.protected,
            "total_deleted": self.total_deleted,
        }


class RetentionMixin(Store):
    def count_below_score(self, score: int) -> int:
        with self._connection() as conn:
            return int(
                conn.execute(
                    f"SELECT COUNT(*) FROM jobs WHERE relevance_score < ? AND {UNPROTECTED_SQL}",
                    (score,),
                ).fetchone()[0]
            )

    def delete_below_score(self, score: int) -> int:
        with self._connection() as conn:
            cursor = conn.execute(
                f"DELETE FROM jobs WHERE relevance_score < ? AND {UNPROTECTED_SQL}", (score,)
            )
            conn.commit()
        return cursor.rowcount

    def count_stale(self, days: int) -> int:
        cutoff = date.today() - timedelta(days=days)
        with self._connection() as conn:
            return int(
                conn.execute(
                    f"SELECT COUNT(*) FROM jobs WHERE last_seen < ? AND {UNPROTECTED_SQL}",
                    (cutoff,),
                ).fetchone()[0]
            )

    def delete_stale(self, days: int) -> int:
        cutoff = date.today() - timedelta(days=days)
        with self._connection() as conn:
            cursor = conn.execute(
                f"DELETE FROM jobs WHERE last_seen < ? AND {UNPROTECTED_SQL}", (cutoff,)
            )
            conn.commit()
        return cursor.rowcount

    def count_protected(self) -> int:
        with self._connection() as conn:
            return int(
                conn.execute(f"SELECT COUNT(*) FROM jobs WHERE {PROTECTED_SQL}").fetchone()[0]
            )

    def preview_reconcile(self, config: Config) -> ReconciliationReport:
        return ReconciliationReport(
            deleted_below_score=self.count_below_score(config.scoring.save_threshold),
            deleted_stale=self.count_stale(config.retention.max_age_days),
            protected=self.count_protected(),
        )

    def reconcile(self, config: Config) -> ReconciliationReport:
        """Apply the configured save threshold and retention. Idempotent."""
        report = ReconciliationReport(protected=self.count_protected())
        report.deleted_below_score = self.delete_below_score(config.scoring.save_threshold)
        report.deleted_stale = self.delete_stale(config.retention.max_age_days)
        return report
