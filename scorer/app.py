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

        torch.set_num_threads(THREADS)
        torch.set_num_interop_threads(1)
        agent = Agent(MODEL, revision=REVISION, device="cpu", backend="eager")
        while True:
            value = connection.recv()
            try:
                result = agent.predict(value["state"], value["questions"], max_len=value["max_len"])
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
            raise RuntimeError(response.get("error", "Model inference failed"))
        READY = True
        LAST_ERROR = None
        return response["result"]
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


app = FastAPI(title="Openings optional CPU scorer", version="0.6.2", lifespan=lifespan)


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
        usage = result.get("usage") or {}
        if (
            usage.get("truncated")
            or usage.get("state_tokens_dropped")
            or usage.get("truncated_questions")
        ):
            raise HTTPException(
                422,
                "Context was truncated; no fit score is returned. Use a shorter scoring profile or a larger compatible service.",
            )
        return {**result, "model": MODEL, "model_revision": REVISION}
    finally:
        LAST_USED = time.monotonic()
        if UNLOAD_PENDING:
            unload()
        LOCK.release()
