import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from worker import pool as ctx_pool
from worker.killers import kd, ko, zz, dd, kill

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

WORKER_KEY = os.environ.get("WORKER_KEY", "")
MAX_QUEUE_DEPTH = int(os.environ.get("MAX_QUEUE_DEPTH", "50"))

_job_queue: asyncio.Queue = asyncio.Queue(maxsize=MAX_QUEUE_DEPTH)
_stats = {"queued": 0, "running": 0, "done": 0, "failed": 0}

KILLER_MAP = {
    "kd": kd.run,
    "ko": ko.run,
    "zz": zz.run,
    "dd": dd.run,
    "kill": kill.run,
}


class JobRequest(BaseModel):
    card: str
    chat_id: int
    message_id: int
    cmd: str


async def _worker_loop():
    while True:
        job = await _job_queue.get()
        cmd_fn = job["fn"]
        ctx = await ctx_pool.acquire()
        _stats["running"] += 1
        healthy = True
        try:
            start = time.time()
            success = await asyncio.wait_for(
                cmd_fn(ctx, job["card"], job["chat_id"], job["message_id"]),
                timeout=120,
            )
            elapsed = round(time.time() - start, 2)
            if success:
                _stats["done"] += 1
                logger.info(f"[{job['cmd']}] done in {elapsed}s")
            else:
                _stats["failed"] += 1
                logger.warning(f"[{job['cmd']}] failed after {elapsed}s")
        except asyncio.TimeoutError:
            _stats["failed"] += 1
            healthy = False
            logger.error(f"[{job['cmd']}] timed out — context marked unhealthy")
        except Exception:
            _stats["failed"] += 1
            logger.exception(f"[{job['cmd']}] unexpected error")
        finally:
            _stats["running"] -= 1
            await ctx_pool.release(ctx, healthy=healthy)
            _job_queue.task_done()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ctx_pool.start_pool()
    workers = int(os.environ.get("MAX_CONTEXTS", "8"))
    for _ in range(workers):
        asyncio.create_task(_worker_loop())
    logger.info(f"Worker service ready — {workers} concurrent slots")
    yield
    await ctx_pool.stop_pool()


app = FastAPI(title="Killer Worker API", lifespan=lifespan)


def _auth(x_worker_key: str = Header(default="")):
    if WORKER_KEY and x_worker_key != WORKER_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.post("/job")
async def enqueue_job(req: JobRequest, x_worker_key: str = Header(default="")):
    _auth(x_worker_key)
    if req.cmd not in KILLER_MAP:
        raise HTTPException(status_code=400, detail=f"Unknown command: {req.cmd}")
    try:
        _job_queue.put_nowait({
            "fn": KILLER_MAP[req.cmd],
            "card": req.card,
            "chat_id": req.chat_id,
            "message_id": req.message_id,
            "cmd": req.cmd,
        })
        _stats["queued"] += 1
    except asyncio.QueueFull:
        raise HTTPException(status_code=503, detail="Worker busy — try again shortly")
    return {"status": "queued", "queue_depth": _job_queue.qsize()}


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "pool_free": ctx_pool.pool_size(),
        "queue_depth": _job_queue.qsize(),
        **_stats,
    }


@app.get("/")
async def root():
    return {"service": "killer-worker", "status": "running"}
