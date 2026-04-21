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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

WORKER_KEY = os.environ.get("WORKER_KEY", "")
MAX_QUEUE_DEPTH = int(os.environ.get("MAX_QUEUE_DEPTH", "50"))
MAX_WORKERS = int(os.environ.get("MAX_CONTEXTS", "8"))

_job_queue: asyncio.Queue = asyncio.Queue(maxsize=MAX_QUEUE_DEPTH)
_stats = {"queued": 0, "running": 0, "done": 0, "failed": 0}
_worker_states: dict[int, dict] = {}  # worker_id -> {status, cmd, card, started}

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


def _log_status():
    free = ctx_pool.pool_size()
    busy = MAX_WORKERS - free
    queued = _job_queue.qsize()
    logger.info(
        f"[STATUS] workers={MAX_WORKERS} | busy={busy} | free={free} | "
        f"queue={queued}/{MAX_QUEUE_DEPTH} | done={_stats['done']} | failed={_stats['failed']}"
    )
    for wid, state in _worker_states.items():
        if state["status"] == "running":
            elapsed = round(time.time() - state["started"], 1)
            logger.info(
                f"  [W{wid}] running cmd={state['cmd']} card={state['card'][:16]}... "
                f"chat={state['chat_id']} elapsed={elapsed}s"
            )


async def _status_printer():
    """Print periodic status summary every 30 seconds."""
    while True:
        await asyncio.sleep(30)
        _log_status()


async def _worker_loop(worker_id: int):
    logger.info(f"[W{worker_id}] Worker started and waiting for jobs")
    _worker_states[worker_id] = {"status": "idle", "cmd": None, "card": None, "chat_id": None, "started": None}

    while True:
        job = await _job_queue.get()
        cmd_fn = job["fn"]

        logger.info(
            f"[W{worker_id}] Acquired job: cmd={job['cmd']} card={job['card'][:16]}... "
            f"chat={job['chat_id']} msg={job['message_id']}"
        )

        ctx = await ctx_pool.acquire()
        free_after_acquire = ctx_pool.pool_size()
        logger.info(
            f"[W{worker_id}] Context acquired — pool free={free_after_acquire}/{MAX_WORKERS}"
        )

        _stats["running"] += 1
        _worker_states[worker_id] = {
            "status": "running",
            "cmd": job["cmd"],
            "card": job["card"],
            "chat_id": job["chat_id"],
            "started": time.time(),
        }
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
                logger.info(
                    f"[W{worker_id}] SUCCESS cmd={job['cmd']} elapsed={elapsed}s "
                    f"card={job['card'][:16]}... | total done={_stats['done']}"
                )
            else:
                _stats["failed"] += 1
                logger.warning(
                    f"[W{worker_id}] FAILED cmd={job['cmd']} elapsed={elapsed}s "
                    f"card={job['card'][:16]}... | total failed={_stats['failed']}"
                )

        except asyncio.TimeoutError:
            _stats["failed"] += 1
            healthy = False
            elapsed = round(time.time() - start, 2)
            logger.error(
                f"[W{worker_id}] TIMEOUT cmd={job['cmd']} after {elapsed}s "
                f"card={job['card'][:16]}... — context marked unhealthy"
            )

        except Exception as exc:
            _stats["failed"] += 1
            logger.exception(
                f"[W{worker_id}] EXCEPTION cmd={job['cmd']} card={job['card'][:16]}...: {exc}"
            )

        finally:
            _stats["running"] -= 1
            _worker_states[worker_id] = {"status": "idle", "cmd": None, "card": None, "chat_id": None, "started": None}
            await ctx_pool.release(ctx, healthy=healthy)
            free_after_release = ctx_pool.pool_size()
            logger.info(
                f"[W{worker_id}] Context released healthy={healthy} — pool free={free_after_release}/{MAX_WORKERS} | "
                f"queue remaining={_job_queue.qsize()}"
            )
            _job_queue.task_done()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info(f"[STARTUP] Killer Worker API starting up")
    logger.info(f"[STARTUP] MAX_CONTEXTS={MAX_WORKERS} | MAX_QUEUE={MAX_QUEUE_DEPTH}")
    logger.info(f"[STARTUP] WORKER_KEY={'SET' if WORKER_KEY else 'NOT SET'}")
    logger.info("=" * 60)

    await ctx_pool.start_pool()

    for i in range(MAX_WORKERS):
        asyncio.create_task(_worker_loop(i))

    asyncio.create_task(_status_printer())

    logger.info(f"[STARTUP] All {MAX_WORKERS} workers started — service ready")
    _log_status()

    yield

    logger.info("[SHUTDOWN] Stopping pool...")
    await ctx_pool.stop_pool()
    logger.info("[SHUTDOWN] Done")


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
        depth = _job_queue.qsize()
        free = ctx_pool.pool_size()
        logger.info(
            f"[ENQUEUE] cmd={req.cmd} card={req.card[:16]}... chat={req.chat_id} "
            f"| queue={depth}/{MAX_QUEUE_DEPTH} pool_free={free}/{MAX_WORKERS}"
        )
    except asyncio.QueueFull:
        logger.warning(
            f"[QUEUE FULL] Rejected cmd={req.cmd} card={req.card[:16]}... "
            f"queue={_job_queue.qsize()}/{MAX_QUEUE_DEPTH}"
        )
        raise HTTPException(status_code=503, detail="Worker busy — try again shortly")
    return {"status": "queued", "queue_depth": _job_queue.qsize()}


@app.get("/health")
async def health():
    pool = ctx_pool.pool_stats()
    busy_workers = [
        {"worker": wid, "cmd": s["cmd"], "card": s["card"][:16] + "..." if s["card"] else None,
         "elapsed": round(time.time() - s["started"], 1) if s["started"] else None}
        for wid, s in _worker_states.items() if s["status"] == "running"
    ]
    return {
        "status": "ok",
        "pool": pool,
        "queue_depth": _job_queue.qsize(),
        "queue_max": MAX_QUEUE_DEPTH,
        "busy_workers": busy_workers,
        **_stats,
    }


@app.get("/")
async def root():
    return {"service": "killer-worker", "status": "running"}
