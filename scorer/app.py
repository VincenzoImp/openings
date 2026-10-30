"""Optional single-checkpoint CPU scorer. The core application has no ML dependency."""

import multiprocessing
import os
import threading
import time
from contextlib import asynccontextmanager
from typing import Any, Literal

os.environ.setdefault("USE_TF", "0")

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from preparation import prepare_state

MODEL = os.environ.get("SCORER_MODEL", "convaiinnovations/laya")
REVISION = os.environ.get("SCORER_REVISION", "55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851")
MAX_CONTEXT = int(os.environ.get("SCORER_MAX_CONTEXT", "2048"))
THREADS = min(max(int(os.environ.get("SCORER_THREADS", "2")), 1), 2)
KEY = os.environ.get("SCORER_API_KEY", "")
IDLE_SECONDS = max(int(os.environ.get("SCORER_IDLE_UNLOAD", "120")), 15)
REQUEST_TIMEOUT = min(max(int(os.environ.get("SCORER_REQUEST_TIMEOUT", "600")), 5), 600)
LOCK = threading.Lock()
MODEL_PROCESS = None
MODEL_PIPE = None
READY = False
LAST_USED = 0.0
UNLOAD_PENDING = False
LAST_ERROR = None


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Question(Input):
    type: Literal["score"] = "score"
    instructions: str | dict | list = Field(default="")
    criteria: list[str] = Field(min_length=2, max_length=10)


class ScoreRequest(Input):
    model: str = Field(min_length=1, max_length=300)
    state: str | dict[str, Any] | list
    questions: dict[str, Question] = Field(min_length=1, max_length=1)
    max_len: int = Field(default=2048, ge=256, le=8192)


def model_loop(connection):
    """Keep native runtimes in a disposable process so unloading returns all RAM."""
    try:
        import torch
        from laya import Agent
        from laya.common import build_head, encode_text, render_options

        torch.set_num_threads(THREADS)
        torch.set_num_interop_threads(1)
        agent = Agent(MODEL, revision=REVISION, device="cpu", backend="eager")
        while True:
            value = connection.recv()
            try:
                question = agent._to_internal(next(iter(value["questions"].values())))
                head, _, _ = build_head(agent.tok, question, agent.cfg.get("head_max_len", 192))
                instruction = f"{question['t']} question: {question['ins']}".replace(
                    agent.tok.mask_token, " "
                )
                full_head = [agent.tok.cls_token_id]
                full_head += encode_text(agent.tok, instruction, add_special_tokens=False)[
                    "input_ids"
                ]
                full_head += [agent.tok.sep_token_id]
                for option in render_options(question):
                    full_head += [agent.tok.mask_token_id]
                    full_head += encode_text(
                        agent.tok,
                        " " + option.replace(agent.tok.mask_token, " "),
                        add_special_tokens=False,
                    )["input_ids"]
                full_head += [agent.tok.sep_token_id]
                # Laya can shorten instructions/options without a usage flag.
                # Require its assembled head to contain the complete rendered question.
                if head != full_head:
                    connection.send({"ok": False, "error": "question_too_long"})
                    continue
                state, preparation = prepare_state(
                    agent.tok, value["state"], max(0, value["max_len"] - len(head) - 1)
                )
                result = agent.predict(state, value["questions"], max_len=value["max_len"])
                if preparation is not None:
                    usage = result["usage"]
                    preparation.update(
                        state_tokens_used=(
                            preparation["state_tokens_used"] - usage["state_tokens_dropped"]
                        ),
                        state_tokens_dropped=(
                            preparation["state_tokens_dropped"] + usage["state_tokens_dropped"]
                        ),
                        shortened=preparation["shortened"] or usage["truncated"],
                    )
                    result["input_preparation"] = preparation
                connection.send({"ok": True, "result": result})
            except Exception as error:
                connection.send({"ok": False, "error": type(error).__name__})
    except (EOFError, BrokenPipeError):
        pass
    except Exception as error:
        try:
            connection.send({"ok": False, "error": type(error).__name__})
        except (EOFError, BrokenPipeError, OSError):
            pass
    finally:
        connection.close()


def unload():
    global MODEL_PROCESS, MODEL_PIPE, READY, UNLOAD_PENDING
    if MODEL_PROCESS is not None:
        MODEL_PROCESS.terminate()
        MODEL_PROCESS.join(timeout=2)
        if MODEL_PROCESS.is_alive():
            MODEL_PROCESS.kill()
            MODEL_PROCESS.join(timeout=1)
        MODEL_PROCESS.close()
        MODEL_PROCESS = None
    if MODEL_PIPE is not None:
        MODEL_PIPE.close()
        MODEL_PIPE = None
    READY = False
    UNLOAD_PENDING = False


def predict(value):
    global MODEL_PROCESS, MODEL_PIPE, READY, LAST_ERROR
    try:
        if MODEL_PROCESS is None or not MODEL_PROCESS.is_alive():
            unload()
            context = multiprocessing.get_context("spawn")
            MODEL_PIPE, child = context.Pipe()
            MODEL_PROCESS = context.Process(
                target=model_loop, args=(child,), name="openings-model", daemon=True
            )
            MODEL_PROCESS.start()
            child.close()
        MODEL_PIPE.send(value)
        if not MODEL_PIPE.poll(REQUEST_TIMEOUT):
            raise TimeoutError("Model response deadline exceeded")
        response = MODEL_PIPE.recv()
        if not response.get("ok"):
            if response.get("error") == "question_too_long":
                raise HTTPException(
                    422,
                    {
                        "code": "question_too_long",
                        "message": "Shorten the score rubric or criteria; their complete text must fit the question token budget.",
                    },
                )
            raise RuntimeError(response.get("error", "Model inference failed"))
        READY = True
        LAST_ERROR = None
        return response["result"]
    except HTTPException:
        raise
    except Exception as error:
        LAST_ERROR = type(error).__name__
        unload()
        raise HTTPException(
            503, "The local model could not score. Check its cache, available memory and logs."
        ) from error


@asynccontextmanager
async def lifespan(app):
    stopping = threading.Event()

    def idle_unload():
        while not stopping.wait(10):
            if (
                MODEL_PROCESS is not None
                and time.monotonic() - LAST_USED >= IDLE_SECONDS
                and LOCK.acquire(blocking=False)
            ):
                try:
                    unload()
                finally:
                    LOCK.release()

    monitor = threading.Thread(target=idle_unload, name="scorer-idle", daemon=True)
    monitor.start()
    try:
        yield
    finally:
        stopping.set()
        monitor.join(timeout=1)
        # Uvicorn finishes active requests before its lifespan shutdown.
        with LOCK:
            unload()


app = FastAPI(title="Openings optional CPU scorer", version="0.8.0", lifespan=lifespan)


@app.middleware("http")
async def authenticate(request: Request, call_next):
    if (
        KEY
        and request.url.path != "/health"
        and request.headers.get("authorization") != "Bearer " + KEY
    ):
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    size = request.headers.get("content-length")
    try:
        if size and int(size) > 2 * 1024 * 1024:
            return JSONResponse({"detail": "Request too large"}, status_code=413)
    except ValueError:
        return JSONResponse({"detail": "Invalid Content-Length"}, status_code=400)
    return await call_next(request)


@app.get("/health")
def health():
    return {
        "status": "ready" if READY and MODEL_PROCESS and MODEL_PROCESS.is_alive() else "idle",
        "device": "cpu",
        "threads": THREADS,
        "max_len": MAX_CONTEXT,
        "model": MODEL,
        "revision": REVISION,
        "last_error": LAST_ERROR,
    }


@app.post("/v1/unload")
def request_unload():
    global UNLOAD_PENDING
    UNLOAD_PENDING = True
    if not LOCK.acquire(blocking=False):
        return {"status": "unload_pending"}
    try:
        unload()
        return {"status": "idle"}
    finally:
        LOCK.release()


@app.post("/v1/systemone")
def system_one(value: ScoreRequest):
    global LAST_USED
    if value.model not in ("english", "laya-english", MODEL):
        raise HTTPException(
            422, "This service loads one configured checkpoint; the requested model is not served."
        )
    if value.max_len > MAX_CONTEXT:
        raise HTTPException(
            422, "The requested context exceeds this service's configured resource limit."
        )
    if not LOCK.acquire(blocking=False):
        raise HTTPException(503, "The scorer is busy. Retry after the current request finishes.")
    try:
        result = predict(
            {
                "state": value.state,
                "questions": {
                    name: question.model_dump() for name, question in value.questions.items()
                },
                "max_len": value.max_len,
            }
        )
        return {**result, "model": MODEL, "model_revision": REVISION}
    finally:
        LAST_USED = time.monotonic()
        if UNLOAD_PENDING:
            unload()
        LOCK.release()
