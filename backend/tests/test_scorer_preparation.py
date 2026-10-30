"""Preparation invariants need no model runtime in the core test environment."""

import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace


SPEC = importlib.util.spec_from_file_location(
    "scorer_preparation", Path(__file__).parents[2] / "scorer" / "preparation.py"
)
preparation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preparation)


class CharacterTokenizer:
    """A Unicode character may occupy several tokens with the same text offset."""

    mask_token = "[MASK]"
    cls_token_id, sep_token_id, mask_token_id = 1, 2, 3

    def __call__(self, text, **kwargs):
        ids, offsets = [], []
        for index, character in enumerate(text):
            count = 2 if ord(character) > 127 else 1
            ids.extend([ord(character)] * count)
            offsets.extend([(index, index + 1)] * count)
        return {"input_ids": ids, "offset_mapping": offsets}


def test_huge_candidate_and_essentials_leave_at_least_half_for_posting():
    tokenizer = CharacterTokenizer()
    source = {
        "candidate": {"profile": {"summary": "Experience. " * 1000}, "knowledge": []},
        "job": {"title": "Python engineer " * 1000, "posting": "REQUIRED: Python. " * 1000},
    }
    state, metadata = preparation.prepare_state(tokenizer, source, 256)
    assert isinstance(state, str)
    assert metadata["candidate_tokens_used"] <= 64
    assert metadata["essentials_tokens_used"] <= 64
    assert metadata["prefix_tokens"] <= 128
    assert "Posting:\nREQUIRED: Python." in state[:256]
    assert len(tokenizer(state)["input_ids"]) <= 256
    assert len(state) < 300
    assert metadata["state_tokens_dropped"] > 0
    assert metadata["shortened"]
    assert metadata["state"] == state
    assert source["candidate"]["profile"]["summary"] == "Experience. " * 1000


def test_short_content_survives_and_json_storage_order_does_not_change_projection():
    tokenizer = CharacterTokenizer()
    source = {
        "candidate": {"profile": {"summary": "APIs", "roles": "Engineer"}},
        "job": {"posting": "Python and C++.", "title": "API engineer", "company": "Example"},
    }
    state, metadata = preparation.prepare_state(tokenizer, source, 1024)
    assert state.index("roles: Engineer") < state.index("summary: APIs")
    assert state.index("title: API engineer") < state.index("company: Example")
    assert state.endswith("Posting:\nPython and C++.")
    assert not metadata["shortened"]
    restored = json.loads(json.dumps(source, sort_keys=True))
    assert preparation.prepare_state(tokenizer, restored, 1024)[0] == state


def test_unicode_prefix_retains_valid_original_characters_within_actual_token_budget():
    tokenizer = CharacterTokenizer()
    assert preparation._prefix(tokenizer, "évidence", 1) == ("", 9, 0)
    assert preparation._prefix(tokenizer, "évidence", 2) == ("é", 9, 2)
    assert preparation.prepare_state(tokenizer, "Existing generic state", 256) == (
        "Existing generic state",
        None,
    )
    generic = {"candidate": {"profile": None}, "job": {"metadata": ["Arbitrary JSON"]}}
    assert preparation.prepare_state(tokenizer, generic, 256) == (generic, None)


def test_scorer_uses_frozen_preparation_and_rejects_question_loss_before_inference(monkeypatch):
    options = ["level 0: Low", "level 1: High"]

    def build_head(tokenizer, question, limit):
        if len(question["ins"]) > 100:
            return [1, 2], [], {}  # Simulate the library shortening the question head.
        head = [1] + list(map(ord, "score question: " + question["ins"])) + [2]
        for option in options:
            head += [3] + list(map(ord, " " + option))
        return head + [2], [], {}

    model_inputs = []

    class Agent:
        tok = CharacterTokenizer()
        cfg = {"head_max_len": 192}

        def __init__(self, *args, **kwargs):
            pass

        @staticmethod
        def _to_internal(question):
            return {"t": "score", "ins": question["instructions"], "crit": question["criteria"]}

        def predict(self, state, questions, max_len):
            model_inputs.append(state)
            return {
                "usage": {
                    "state_tokens": len(self.tok(state)["input_ids"]),
                    "state_tokens_dropped": 0,
                    "truncated": False,
                }
            }

    monkeypatch.setitem(
        sys.modules,
        "torch",
        SimpleNamespace(
            set_num_threads=lambda value: None, set_num_interop_threads=lambda value: None
        ),
    )
    monkeypatch.setitem(sys.modules, "laya", SimpleNamespace(Agent=Agent))
    monkeypatch.setitem(
        sys.modules,
        "laya.common",
        SimpleNamespace(
            build_head=build_head,
            encode_text=lambda tokenizer, text, **kwargs: tokenizer(text, **kwargs),
            render_options=lambda question: options,
        ),
    )
    monkeypatch.setitem(sys.modules, "preparation", preparation)
    spec = importlib.util.spec_from_file_location(
        "bundled_scorer", Path(__file__).parents[2] / "scorer" / "app.py"
    )
    scorer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scorer)
    state = {"candidate": {"summary": "Python"}, "job": {"posting": "Python APIs. " * 1000}}
    requests = iter(
        [
            {
                "state": state,
                "max_len": 256,
                "questions": {"fit": {"instructions": instruction, "criteria": ["Low", "High"]}},
            }
            for instruction in ("Assess.", "Oversized question. " * 100)
        ]
    )

    class Connection:
        sent = []
        closed = False

        def recv(self):
            try:
                return next(requests)
            except StopIteration:
                raise EOFError from None

        def send(self, value):
            self.sent.append(value)

        def close(self):
            self.closed = True

    connection = Connection()
    scorer.model_loop(connection)
    assert connection.closed
    assert len(model_inputs) == 1
    result = connection.sent[0]["result"]
    assert result["input_preparation"]["state"] == model_inputs[0]
    assert result["input_preparation"]["state_tokens_dropped"] > 0
    assert result["input_preparation"]["shortened"]
    assert not result["usage"]["truncated"]
    assert connection.sent[1] == {"ok": False, "error": "question_too_long"}
