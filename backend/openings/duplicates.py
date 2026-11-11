"""Read-only duplicate candidates. Signals only suggest a review; nothing merges here.

Each job is reduced once to compact features: normalized company and title, places,
requisition ids, apply targets and a bounded sketch of its posting text. Jobs that
share a blocking key are compared pairwise, and every pair gets a confidence in
[0, 1] with the signals that matched or conflicted. Groups are the jobs linked by
pairs at or above the requested confidence. Everything is deterministic and local.
"""

import threading
from collections import namedtuple
from itertools import pairwise

from .duplicate_signals import compare_location, compare_title, posted_apart, sketch_similarity

HIGH_CONFIDENCE = 0.85
DEFAULT_MIN_CONFIDENCE = 0.5
NEAR_IDENTICAL_TEXT = 0.75
SIMILAR_TEXT = 0.55
DIFFERENT_TEXT = 0.3
AMBIGUOUS_MATCH = 0.7
_RIVAL_MARGIN = 0.05
# A key shared by more jobs than this is a template or a careers page, not an identifier.
_IDENTIFIER_JOBS = 12
# Larger blocks are compared along a chain instead of pair by pair.
_BLOCK_PAIRS = 40
_GROUP_PAIRS = 60  # larger groups are summarised by their joining links only
_LSH_KEYS = 4  # smallest sketch hashes used to find near-identical text across companies

# Independent evidence that two records describe one vacancy, combined as 1 - Π(1 - w).
_WEIGHT = {
    "apply_target": 0.9,
    "requisition_id": 0.85,
    "requisition_id_alone": 0.3,
    "text": 0.7,
    "text_weak": 0.25,
    "similar_text": 0.4,
    "similar_text_weak": 0.15,
    "company_title": 0.4,
    "company_similar_title": 0.3,
    "title": 0.15,
    "company": 0.1,
    "location": 0.2,
}
# Evidence of different vacancies multiplies the combined score.
_PENALTY = {
    "requisition_id": 0.15,
    "apply_target": 0.15,
    "location": 0.3,
    "seniority": 0.3,
    "posting_text": 0.5,
    "posting_date": 0.75,
}
_OVERRULED = 0.97  # a conflict next to a shared identifier
_UNCLEAR_TEXT = 0.8  # some shared text, too little to call the postings similar

Evidence = namedtuple("Evidence", "score matched conflicts")
NO_EVIDENCE = Evidence(0.0, (), ())


def score_pair(a, b, generic=frozenset()):
    """Confidence in [0, 1] that two jobs are one vacancy, with the reasons.

    `generic` holds reference and target keys shared by too many jobs to identify one.
    Company, title and location stay below HIGH_CONFIDENCE without text or an identifier.
    """
    weights, matched, conflicts = [], [], []
    company = bool(a.company) and a.company == b.company
    title = compare_title(a, b)
    location = compare_location(a, b)
    similarity = (
        1.0
        if a.fingerprint and a.fingerprint == b.fingerprint
        else sketch_similarity(a.sketch, b.sketch)
    )
    target = bool((a.targets & b.targets) - generic)
    shared_reference = bool((a.references & b.references) - generic)
    reference = False

    if target:
        weights.append(_WEIGHT["apply_target"])
        matched.append("apply_target")
    if shared_reference:
        corroborated = company or title in {"same", "similar"} or (similarity or 0) >= SIMILAR_TEXT
        weights.append(_WEIGHT["requisition_id" if corroborated else "requisition_id_alone"])
        matched.append("requisition_id")
        reference = corroborated
    # An agency or a template repeats one text for many roles: shared text is weak
    # evidence under another title, and merely similar text under another employer.
    if similarity is not None and similarity >= NEAR_IDENTICAL_TEXT:
        same_role = title == "same" or (company and title)
        weights.append(_WEIGHT["text" if same_role else "text_weak"])
        matched.append("posting_text" if similarity == 1.0 else "near_identical_text")
    elif similarity is not None and similarity >= SIMILAR_TEXT:
        weights.append(_WEIGHT["similar_text" if title and company else "similar_text_weak"])
        matched.append("similar_text")
    # The second test is the grouping rule of earlier releases: every pair it joined
    # keeps some evidence, so no earlier candidate disappears at min_confidence 0.
    if (company and title == "same") or (a.legacy and a.legacy == b.legacy):
        weights.append(_WEIGHT["company_title"])
        matched.append("company_title")
    elif company and title == "similar":
        weights.append(_WEIGHT["company_similar_title"])
        matched += ["company", "similar_title"]
    elif company:
        weights.append(_WEIGHT["company"])
        matched.append("company")
    elif title == "same":
        weights.append(_WEIGHT["title"])
        matched.append("title")
    if not weights:
        return NO_EVIDENCE
    if location == "agree":
        weights.append(_WEIGHT["location"])
        matched.append("location")

    score = 1.0
    for weight in weights:
        score *= 1 - weight
    score = 1 - score
    identified = target or reference
    if not shared_reference and a.references and b.references:
        conflicts.append("requisition_id")
        score *= _OVERRULED if target else _PENALTY["requisition_id"]
    if not target:
        kinds_a = {key.split(":", 1)[0] for key in a.targets} - {"url"}
        kinds_b = {key.split(":", 1)[0] for key in b.targets} - {"url"}
        if kinds_a & kinds_b:
            conflicts.append("apply_target")
            score *= _OVERRULED if reference else _PENALTY["apply_target"]
    soft = []
    if location == "conflict":
        soft.append("location")
    if title == "seniority":
        soft.append("seniority")
    if similarity is not None and similarity < DIFFERENT_TEXT:
        soft.append("posting_text")
    elif similarity is not None and similarity < SIMILAR_TEXT and not identified:
        score *= _UNCLEAR_TEXT
    if not identified and posted_apart(a, b):
        soft.append("posting_date")
    for conflict in soft:
        score *= _OVERRULED if identified else _PENALTY[conflict]
    return Evidence(round(score, 2), tuple(matched), tuple(conflicts + soft))


def confidence_tier(score):
    if score >= HIGH_CONFIDENCE:
        return "high"
    return "medium" if score >= DEFAULT_MIN_CONFIDENCE else "low"


def _block_keys(features):
    if features.legacy:
        yield ("legacy", features.legacy)
    if features.company and features.title:
        yield ("company_title", features.company, features.title)
    if features.fingerprint:
        yield ("text", features.fingerprint)
    for value in features.sketch[:_LSH_KEYS] if features.sketch else ():
        yield ("sketch", value)
    for value in features.references:
        yield ("reference", value)
    for value in features.targets:
        yield ("target", value)


def _ambiguous(evidence):
    """Cap a link to a job that matches two vacancies which differ from each other."""
    if "apply_target" in evidence.matched or "ambiguous" in evidence.conflicts:
        return evidence
    return Evidence(
        min(evidence.score, AMBIGUOUS_MATCH), evidence.matched, (*evidence.conflicts, "ambiguous")
    )


class DuplicateIndex:
    """Jobs indexed by blocking key, to score one job or group all of them."""

    def __init__(self, features=()):
        self.jobs = {}
        self.blocks = {}
        self._evidence = {}
        self._links = None
        self._linking = threading.Lock()
        for item in features:
            self.add(item)

    def add(self, features):
        self.jobs[features.id] = features
        self._links = None
        for key in _block_keys(features):
            self.blocks.setdefault(key, []).append(features.id)

    def _generic(self, features):
        """Reference and target keys of this job shared by too many jobs."""
        return frozenset(
            value
            for kind, values in (("reference", features.references), ("target", features.targets))
            for value in values
            if len(self.blocks.get((kind, value), ())) > _IDENTIFIER_JOBS
        )

    def evidence(self, first, second):
        key = (first, second) if first < second else (second, first)
        found = self._evidence.get(key)
        if found is None:
            a, b = self.jobs[first], self.jobs[second]
            found = self._evidence[key] = score_pair(a, b, self._generic(a))
        return found

    def _rivalled(self, scores):
        """Likely matches of one job that have a rival: another match, about as likely
        or better, that is itself a different vacancy from them."""
        rivalled = set()
        jobs = list(scores)
        for index, first in enumerate(jobs):
            for second in jobs[index + 1 :]:
                between = self.evidence(first, second)
                if between.conflicts and between.score < DEFAULT_MIN_CONFIDENCE:
                    for job, rival in ((first, second), (second, first)):
                        if scores[rival] >= scores[job] - _RIVAL_MARGIN:
                            rivalled.add(job)
        return rivalled

    def matches(self, features, min_confidence=DEFAULT_MIN_CONFIDENCE, limit=5):
        """Indexed jobs most likely to be the same vacancy as one job, best first.

        The job may be new or already indexed. Only jobs sharing a blocking key are
        scored, so the cost follows the size of those blocks, not of the archive.
        """
        candidates = set()
        for key in _block_keys(features):
            members = self.blocks.get(key, ())
            if key[0] in {"legacy", "company_title", "text"} or len(members) <= _BLOCK_PAIRS:
                candidates.update(members)
        candidates.discard(features.id)
        generic = self._generic(features)
        found = {
            job_id: evidence
            for job_id in candidates
            if (evidence := score_pair(features, self.jobs[job_id], generic)).score > 0
        }
        likely = {
            job_id: item.score
            for job_id, item in found.items()
            if item.score >= DEFAULT_MIN_CONFIDENCE
        }
        for job_id in self._rivalled(likely):
            found[job_id] = _ambiguous(found[job_id])
        position = {job_id: index for index, job_id in enumerate(self.jobs)}
        ranked = sorted(found.items(), key=lambda item: (-item[1].score, position[item[0]]))
        return [item for item in ranked if item[1].score >= min_confidence][:limit]

    def _pairs(self):
        seen = set()
        for (kind, *_), members in self.blocks.items():
            if len(members) < 2:
                continue
            if len(members) <= _BLOCK_PAIRS:
                pairs = ((a, b) for index, a in enumerate(members) for b in members[index + 1 :])
            elif kind in {"legacy", "company_title", "text"}:
                ordered = sorted(members, key=lambda item: (self.jobs[item].location, item))
                pairs = pairwise(ordered)
            else:
                continue  # boilerplate or a shared page: no evidence of one vacancy
            for a, b in pairs:
                pair = (a, b) if a < b else (b, a)
                if pair not in seen:
                    seen.add(pair)
                    yield pair

    def links(self):
        """Every candidate pair with its evidence, computed once per index."""
        with self._linking:
            return self._all_links()

    def _all_links(self):
        if self._links is None:
            links = {
                pair: evidence for pair in self._pairs() if (evidence := self.evidence(*pair)).score
            }
            likely = {}
            for (a, b), evidence in links.items():
                if evidence.score >= DEFAULT_MIN_CONFIDENCE:
                    likely.setdefault(a, {})[b] = evidence.score
                    likely.setdefault(b, {})[a] = evidence.score
            ambiguous = {
                (job, other) if job < other else (other, job)
                for job, scores in likely.items()
                for other in self._rivalled(scores)
            }
            for pair in ambiguous:
                links[pair] = self._evidence[pair] = _ambiguous(links[pair])
            self._links = links
        return self._links

    def groups(self, min_confidence=DEFAULT_MIN_CONFIDENCE, match_location=False):
        """Jobs linked by pairs at or above `min_confidence`.

        Two sets of jobs are not joined while any pair across them has conflicting
        evidence and scores below the threshold, so a copy without a location cannot
        pull two cities into one group. A group's confidence is its weakest link, or
        its weakest conflicting pair when every candidate is requested.
        """
        position = {job_id: index for index, job_id in enumerate(self.jobs)}
        links = []
        for (a, b), evidence in self.links().items():
            if evidence.score < min_confidence:
                continue
            first, second = self.jobs[a], self.jobs[b]
            if (
                match_location
                and "location" not in evidence.matched
                and first.location != second.location
            ):
                continue
            links.append((-evidence.score, *sorted((position[a], position[b])), a, b, evidence))
        links.sort(key=lambda link: link[:3])
        root = {}
        members = {}
        summary = {}

        def find(item):
            root.setdefault(item, item)
            while root[item] != item:
                root[item] = root[root[item]]
                item = root[item]
            return item

        for *_, a, b, evidence in links:
            first, second = find(a), find(b)
            if first == second:
                continue
            left, right = members.get(first, [first]), members.get(second, [second])
            if min_confidence > 0 and any(
                self.evidence(x, y).conflicts and self.evidence(x, y).score < min_confidence
                for x in left
                for y in right
            ):
                continue
            root[second] = first
            members[first] = left + members.pop(second, [second])
            joined = [
                evidence,
                *filter(None, (summary.pop(first, None), summary.pop(second, None))),
            ]
            summary[first] = Evidence(
                min(item.score for item in joined),
                frozenset().union(*(item.matched for item in joined)),
                frozenset().union(*(item.conflicts for item in joined)),
            )
        groups = []
        for group, found in summary.items():
            ids = sorted(members[group], key=position.__getitem__)
            # Members that were joined through others may still contradict each other.
            doubts = [
                evidence
                for index, first in enumerate(ids if len(ids) <= _GROUP_PAIRS else ())
                for second in ids[index + 1 :]
                if (evidence := self.evidence(first, second)).conflicts
            ]
            groups.append(
                {
                    "ids": ids,
                    "confidence": min([found.score, *(item.score for item in doubts)]),
                    "matched": sorted(found.matched),
                    "conflicts": sorted(
                        found.conflicts.union(*(item.conflicts for item in doubts))
                    ),
                }
            )
        return groups
