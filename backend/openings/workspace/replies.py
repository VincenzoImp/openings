"""Employer replies, written through the application update: record, correct, remove.

Recording a reply moves the stage when its kind implies it (``stage_after_reply``)
in the update's transaction, and the change leaves one event: the reply's, with the
stage it moved from and to. A correction or a removal never moves the stage.
"""

from .. import events
from ..actors import current_actor
from ..common import now
from ..errors import DomainError, missing
from ..outcomes import (
    duplicate_reply,
    insert_reply,
    not_sent,
    reply_record,
    stage_after_reply,
    today,
)

# The application fields a reply that moves the stage sets.
STAGE_FIELDS = frozenset({"status", "outcome", "concluded_on", "applied_at"})


class ReplyChanges:
    """The reply part of ``update_application``."""

    @staticmethod
    def reply_stage(conn, row, reply, changes):
        """Check a reply change and put the stage a new reply moves to into ``changes``.

        Returns the fields the reply sets, or an empty set when it moves nothing.
        """
        if reply is None or reply.id is not None:
            return frozenset()
        sent = row["applied_at"] is not None or row["status"] in {"applied", "interview", "offer"}
        if not sent:
            raise not_sent()
        if changes.keys() & {"status", "outcome", "concluded_on"}:
            raise DomainError(
                422,
                "reply_stage",
                "Recording a reply sets the stage itself: omit status, outcome and concluded_on.",
            )
        target = stage_after_reply(row["status"], row["outcome"], reply.kind)
        if target is None:
            return frozenset()
        changes["status"], changes["outcome"] = target
        return STAGE_FIELDS

    def write_reply(self, conn, row, reply, moved):
        """Insert, correct or remove the reply in the update's transaction, with its event."""
        if reply.id is None:
            day = reply.date or today()
            duplicate_reply(conn, row["id"], reply.kind, day)
            reply_id = insert_reply(conn, row["id"], reply.kind, day, reply.note or "")
            payload = {"kind": reply.kind, "date": day, **(moved or {})}
            events.record(
                conn,
                "reply_added",
                subject=("reply", reply_id),
                payload=payload,
                job_id=row["job_id"],
                application_id=row["id"],
            )
            return
        current = conn.execute(
            "SELECT * FROM replies WHERE id=? AND application_id=?", (reply.id, row["id"])
        ).fetchone()
        if current is None:
            missing("Reply")
        if reply.remove:
            conn.execute("DELETE FROM replies WHERE id=?", (reply.id,))
            events.record(
                conn,
                "reply_removed",
                subject=("reply", reply.id),
                payload={"kind": current["kind"], "date": current["date"]},
                job_id=row["job_id"],
                application_id=row["id"],
            )
            return
        given = reply.model_dump(include={"kind", "date", "note"}, exclude_unset=True)
        actual = {key: value for key, value in given.items() if current[key] != value}
        if not actual:
            return
        duplicate_reply(
            conn,
            row["id"],
            actual.get("kind", current["kind"]),
            actual.get("date", current["date"]),
            excluding=reply.id,
        )
        conn.execute(
            "UPDATE replies SET "
            + "".join(key + "=?," for key in actual)
            + "updated_by=?,version=version+1,updated_at=? WHERE id=?",
            (*actual.values(), current_actor().label, now(), reply.id),
        )
        events.record(
            conn,
            "reply_edited",
            subject=("reply", reply.id),
            payload={"fields": sorted(actual), "version": current["version"] + 1},
            job_id=row["job_id"],
            application_id=row["id"],
        )

    def get_reply(self, reply_id):
        """One reply as reads return it."""
        row = self.db.one(
            "SELECT r.*,a.job_id FROM replies r JOIN applications a ON a.id=r.application_id "
            "WHERE r.id=?",
            (reply_id,),
        )
        if row is None:
            missing("Reply")
        return reply_record(row)
