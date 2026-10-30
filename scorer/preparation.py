"""Deterministic input preparation; the model alone determines the fit score."""

import json

PREPARATION_VERSION = 1


def _tokens(tokenizer, value, **kwargs):
    return tokenizer(value, add_special_tokens=False, **kwargs)


def _prefix(tokenizer, value, limit):
    """Keep an original-text prefix, including at a multi-token Unicode character."""
    encoded = _tokens(tokenizer, value, return_offsets_mapping=True)
    total = len(encoded["input_ids"])
    if total <= limit:
        return value, total, total
    end = encoded["offset_mapping"][limit - 1][1] if limit else 0
    while end:
        shortened = value[:end]
        used = len(_tokens(tokenizer, shortened)["input_ids"])
        if used <= limit:
            return shortened, total, used
        end -= 1
    return "", total, 0


def _value(value):
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def prepare_state(tokenizer, state, state_budget):
    """Bound Openings sections and retain one posting prefix within the real budget.

    Other System One states keep their existing serialization and behavior. No
    tokenizer or model dependency is needed in the core application.
    """
    if not (
        isinstance(state, dict)
        and isinstance(state.get("candidate"), dict)
        and isinstance(state.get("job"), dict)
    ):
        return state, None
    candidate, job = state["candidate"], state["job"]
    profile = candidate.get("profile", candidate)
    knowledge, metadata = candidate.get("knowledge", []), job.get("metadata") or {}
    if (
        not isinstance(profile, dict)
        or not isinstance(knowledge, list)
        or any(not isinstance(record, dict) for record in knowledge)
        or not isinstance(metadata, dict)
    ):
        return state, None
    candidate_lines = ["Candidate:"]
    for key in ("roles", "preferences", "summary", "headline", "location"):
        if profile.get(key):
            candidate_lines.append(f"{key}: {_value(profile[key])}")
    for record in knowledge:
        for key in ("kind", "title", "metadata", "narrative"):
            if record.get(key):
                candidate_lines.append(f"{key}: {_value(record[key])}")
    essentials_lines = ["Job:"]
    for key in ("title", "company", "location"):
        if job.get(key):
            essentials_lines.append(f"{key}: {_value(job[key])}")
    for key in ("is_remote", "job_type", "job_types", "salary"):
        value = metadata.get(key)
        if value is not None:
            essentials_lines.append(f"{key}: {_value(value)}")
    # Match Laya's mask sanitization before measuring the exact model input.
    candidate_text = "\n".join(candidate_lines).replace(tokenizer.mask_token, " ")
    essentials_text = "\n".join(essentials_lines).replace(tokenizer.mask_token, " ")
    candidate_limit = essentials_limit = state_budget // 4
    candidate_text, candidate_total, candidate_used = _prefix(
        tokenizer, candidate_text, candidate_limit
    )
    essentials, essentials_total, essentials_used = _prefix(
        tokenizer, essentials_text, essentials_limit
    )
    # Measure the combined prefix too: token boundaries need not be additive.
    # At least half the state budget remains for the posting, even for huge profiles.
    while True:
        prefix = candidate_text + "\n\n" + essentials + "\n\nPosting:\n"
        prefix_tokens = len(_tokens(tokenizer, prefix)["input_ids"])
        if prefix_tokens <= state_budget // 2:
            break
        if not essentials_limit:
            raise ValueError("The scoring context leaves no room for the posting.")
        essentials_limit = max(0, essentials_limit - (prefix_tokens - state_budget // 2))
        essentials, _, essentials_used = _prefix(tokenizer, essentials_text, essentials_limit)
    prepared = prefix + str(job.get("posting") or "").replace(tokenizer.mask_token, " ")
    prepared, state_total, state_used = _prefix(tokenizer, prepared, state_budget)
    return prepared, {
        "version": PREPARATION_VERSION,
        "state": prepared,
        "candidate_tokens": candidate_total,
        "candidate_tokens_used": candidate_used,
        "essentials_tokens": essentials_total,
        "essentials_tokens_used": essentials_used,
        "prefix_tokens": prefix_tokens,
        "state_tokens": state_total,
        "state_tokens_used": state_used,
        "state_tokens_dropped": state_total - state_used,
        "shortened": (
            candidate_used < candidate_total
            or essentials_used < essentials_total
            or state_used < state_total
        ),
    }
