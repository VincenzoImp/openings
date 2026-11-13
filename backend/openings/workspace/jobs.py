"""Job records: full and compact reads, filters, search and triage counts."""

import json
import re

from ..db import decode_record
from ..errors import DomainError, missing
from ..job_signals import (
    DISMISSAL_COLUMNS,
    DISMISSED_BY,
    SIGNAL_FILTERS,
    SIGNALS_SQL,
    UNLISTED_SQL,
    dismissal_record,
    normalize_languages,
    signal_record,
)
from ..posting import posting_complete, posting_complete_sql


class JobReads:
    """Reading and searching jobs."""

    @staticmethod
    def _job_columns():
        columns = [
            f"j.{key} AS j_{key}"
            for key in (
                "id",
                "title",
                "company",
                "location",
                "url",
                "triage",
                "metadata",
                "content_version",
                "version",
                "created_at",
                "updated_at",
            )
        ]
        columns += [f"j.{name} AS j_{name}" for name in DISMISSAL_COLUMNS]
        columns += [
            "substr(j.posting,1,240) AS j_posting_preview",
            posting_complete_sql() + " AS j_complete",
            "(SELECT json_object('id',id,'status',status,'outcome',outcome,'version',version) FROM applications WHERE job_id=j.id ORDER BY (status='closed'),created_at DESC,id DESC LIMIT 1) AS j_application",
            "(SELECT count(*) FROM applications WHERE job_id=j.id) AS j_application_count",
            SIGNALS_SQL.format(alias="j") + " AS j_signals",
            UNLISTED_SQL.format(alias="j") + " AS j_unlisted_at",
        ]
        return ",".join(columns)

    @staticmethod
    def _compact_job(row):
        result = {key[2:]: value for key, value in dict(row).items() if key.startswith("j_")}
        result["metadata"] = json.loads(result["metadata"])
        result["complete"] = bool(result["complete"])
        result["application"] = json.loads(result["application"]) if result["application"] else None
        result["source"] = (
            result["metadata"].get("source") or result["metadata"].get("ats") or "manual"
        )
        for field in ("is_remote", "job_type", "salary", "date_posted", "workplace_type"):
            if field in result["metadata"]:
                result[field] = result["metadata"][field]
        result["signals"] = signal_record(result["signals"], result.pop("unlisted_at"))
        result["dismissal"] = dismissal_record(result)
        return result

    def _job(self, row):
        if not row:
            missing("Job")
        row = decode_record(row, ("metadata", "overrides"))
        with self.db.connect() as connection:
            row["postings"] = []
            for posting in connection.execute(
                "SELECT p.id,p.source_id,s.name AS source_name,s.kind AS source_kind,p.identity,"
                "p.url,p.first_seen_at,p.last_seen_at,p.unlisted_at FROM postings p "
                "LEFT JOIN sources s ON s.id=p.source_id WHERE p.job_id=? ORDER BY p.first_seen_at",
                (row["id"],),
            ):
                row["postings"].append(dict(posting))
            application = connection.execute(
                "SELECT id,status,outcome,version,(SELECT count(*) FROM applications WHERE job_id=?) AS application_count FROM applications WHERE job_id=? ORDER BY (status='closed'),created_at DESC,id DESC LIMIT 1",
                (row["id"], row["id"]),
            ).fetchone()
            row["application"] = dict(application) if application else None
            row["application_count"] = (
                row["application"].pop("application_count") if application else 0
            )
            signals = connection.execute(
                "SELECT "
                + SIGNALS_SQL.format(alias="j")
                + ","
                + UNLISTED_SQL.format(alias="j")
                + " FROM jobs j WHERE j.id=?",
                (row["id"],),
            ).fetchone()
        row["complete"] = posting_complete(row["posting"], row["metadata"], row["overrides"])
        row["signals"] = signal_record(signals[0], signals[1])
        row["dismissal"] = dismissal_record(row)
        return row

    def get_job(self, job_id):
        return self._job(self.db.one("SELECT * FROM jobs WHERE id=?", (job_id,)))

    def job_summary(self, job_id):
        """Return the compact list-item shape of one job: no full posting or observations."""
        row = self.db.one("SELECT " + self._job_columns() + " FROM jobs j WHERE j.id=?", (job_id,))
        if not row:
            missing("Job")
        return self._compact_job(row)

    @staticmethod
    def _job_filters(
        q="",
        triage=None,
        company=None,
        location=None,
        source=None,
        remote=None,
        job_type=None,
        created_since=None,
        created_until=None,
        complete=None,
        signal=None,
        posting_language=None,
        posting_language_not=None,
        requires=None,
        dismissed_by=None,
        rule_id=None,
    ):
        conditions, args = [], []
        if signal:
            if signal not in SIGNAL_FILTERS:
                raise DomainError(
                    422, "signal", "Choose " + ", ".join(sorted(SIGNAL_FILTERS)) + "."
                )
            conditions.append(SIGNAL_FILTERS[signal])
        for value, operator in ((posting_language, "="), (posting_language_not, "<>")):
            if value:
                conditions.append(
                    "EXISTS(SELECT 1 FROM job_signals s WHERE s.job_id=j.id "
                    f"AND s.language IS NOT NULL AND s.language{operator}?)"
                )
                args.append(normalize_languages([value])[0])
        if requires:
            conditions.append(
                "EXISTS(SELECT 1 FROM job_signals s, json_each(s.required) g, json_each(g.value) c "
                "WHERE s.job_id=j.id AND c.value=?)"
            )
            args.append(normalize_languages([requires])[0])
        if dismissed_by:
            if dismissed_by not in DISMISSED_BY:
                raise DomainError(422, "dismissed_by", "Choose rule, agent, owner or other.")
            conditions.append("j.triage='dismissed' AND " + DISMISSED_BY[dismissed_by])
        if rule_id:
            conditions.append("j.dismissed_rule_id=?")
            args.append(rule_id)
        if triage == "active":
            conditions.append("j.triage!='dismissed'")
        elif triage:
            if triage not in ("new", "shortlisted", "dismissed"):
                raise DomainError(422, "triage", "Choose new, shortlisted or dismissed.")
            conditions.append("j.triage=?")
            args.append(triage)
        if company:
            conditions.append("j.company=?")
            args.append(company)
        if location:
            conditions.append("j.location LIKE ?")
            args.append("%" + location + "%")
        source_sql = "coalesce(json_extract(j.metadata,'$.source'),json_extract(j.metadata,'$.ats'),'manual')"
        if source:
            conditions.append(source_sql + "=?")
            args.append(source)
        if remote is not None:
            conditions.append("json_extract(j.metadata,'$.is_remote')=?")
            args.append(int(remote))
        if complete is not None:
            conditions.append(posting_complete_sql() + "=?")
            args.append(int(complete))
        if job_type:
            conditions.append("json_extract(j.metadata,'$.job_type')=?")
            args.append(job_type)
        for value, operator in ((created_since, ">="), (created_until, "<=")):
            if value:
                conditions.append("j.created_at" + operator + "?")
                args.append(value)
        terms = re.findall(r"\w+", q)
        if terms:
            conditions.append("j.rowid IN (SELECT rowid FROM jobs_fts WHERE jobs_fts MATCH ?)")
            args.append(" AND ".join('"' + term + '"*' for term in terms[:15]))
        return (" WHERE " + " AND ".join(conditions)) if conditions else "", args

    def list_jobs(
        self,
        q="",
        triage=None,
        company=None,
        limit=50,
        offset=0,
        sort="newest",
        location=None,
        source=None,
        remote=None,
        job_type=None,
        created_since=None,
        created_until=None,
        complete=None,
        include_facets=False,
        signal=None,
        posting_language=None,
        posting_language_not=None,
        requires=None,
        dismissed_by=None,
        rule_id=None,
        include_counts=False,
    ):
        limit, offset = min(max(int(limit), 1), 200), max(int(offset), 0)
        signal_filters = {
            "signal": signal,
            "posting_language": posting_language,
            "posting_language_not": posting_language_not,
            "requires": requires,
        }
        with self.db.connect() as connection:
            where, args = self._job_filters(
                q,
                triage,
                company,
                location,
                source,
                remote,
                job_type,
                created_since,
                created_until,
                complete,
                dismissed_by=dismissed_by,
                rule_id=rule_id,
                **signal_filters,
            )
            base = " FROM jobs j"
            order = {
                "oldest": "j.created_at ASC",
                "company": "j.company,j.title",
                "title": "j.title",
                "dismissed": "j.dismissed_at IS NULL,j.dismissed_at DESC,j.created_at DESC",
            }.get(sort, "j.created_at DESC")
            rows = connection.execute(
                "SELECT "
                + self._job_columns()
                + base
                + where
                + " ORDER BY "
                + order
                + ",j.id LIMIT ? OFFSET ?",
                (*args, limit, offset),
            ).fetchall()
            total = connection.execute("SELECT count(*)" + base + where, args).fetchone()[0]
            result = {
                "items": [self._compact_job(row) for row in rows],
                "total": total,
                "limit": limit,
                "offset": offset,
            }
            if include_counts:
                result["counts"] = self._job_counts(
                    connection,
                    q,
                    company=company,
                    location=location,
                    source=source,
                    remote=remote,
                    job_type=job_type,
                    created_since=created_since,
                    created_until=created_until,
                    complete=complete,
                    **signal_filters,
                )
            if not include_facets:
                return result
            facets = {}
            for name, expression in (
                ("companies", "j.company"),
                ("locations", "j.location"),
                (
                    "sources",
                    "coalesce(json_extract(j.metadata,'$.source'),json_extract(j.metadata,'$.ats'),'manual')",
                ),
                ("job_types", "json_extract(j.metadata,'$.job_type')"),
            ):
                facet_rows = connection.execute(
                    "SELECT DISTINCT "
                    + expression
                    + " value"
                    + base
                    + where
                    + " ORDER BY value LIMIT 200",
                    args,
                )
                facets[name] = [r[0] for r in facet_rows if r[0] not in (None, "")]
        return {**result, "facets": facets}

    def _job_counts(self, connection, q="", **filters):
        """Jobs of each triage and dismissed jobs by who dismissed them, for the same filters."""
        where, args = self._job_filters(q, **filters)
        row = connection.execute(
            "SELECT count(*),"
            "coalesce(sum(j.triage='new'),0),"
            "coalesce(sum(j.triage='shortlisted'),0),"
            "coalesce(sum(j.triage='dismissed'),0),"
            + ",".join(
                f"coalesce(sum(j.triage='dismissed' AND {sql}),0)" for sql in DISMISSED_BY.values()
            )
            + " FROM jobs j"
            + where,
            args,
        ).fetchone()
        return {
            "all": row[0],
            "new": row[1],
            "shortlisted": row[2],
            "dismissed": row[3],
            "dismissed_by": dict(zip(DISMISSED_BY, row[4:], strict=True)),
        }
