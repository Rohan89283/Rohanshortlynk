import asyncio
import os
import logging
from playwright.async_api import async_playwright, Browser, BrowserContext

logger = logging.getLogger(__name__)

MAX_CONTEXTS = int(os.environ.get("MAX_CONTEXTS", "8"))

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]

_playwright = None
_browser: Browser | None = None
_pool: asyncio.Queue | None = None
_pool_lock = asyncio.Lock()
_ctx_index = 0
_recycled = 0
_replaced = 0


async def _new_context() -> BrowserContext:
    global _ctx_index
    ua = _USER_AGENTS[_ctx_index % len(_USER_AGENTS)]
    slot = _ctx_index
    _ctx_index += 1
    logger.debug(f"[POOL] Creating context slot={slot} ua={ua[:40]}...")
    ctx = await _browser.new_context(
        viewport={"width": 1920, "height": 1080},
        user_agent=ua,
        locale="en-US",
        timezone_id="America/New_York",
        extra_http_headers={
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    await ctx.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
        Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
    """)
    return ctx


async def start_pool() -> None:
    global _playwright, _browser, _pool
    logger.info(f"[POOL] Launching Chromium browser (headless)...")
    _playwright = await async_playwright().start()
    _browser = await _playwright.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-extensions",
            "--disable-background-networking",
            "--disable-default-apps",
            "--disable-sync",
            "--disable-translate",
            "--disable-hang-monitor",
            "--disable-popup-blocking",
            "--disable-notifications",
            "--disable-background-timer-throttling",
            "--disable-renderer-backgrounding",
            "--disable-backgrounding-occluded-windows",
            "--disable-ipc-flooding-protection",
            "--disable-component-update",
            "--no-first-run",
            "--disable-blink-features=AutomationControlled",
        ],
    )
    logger.info(f"[POOL] Browser launched — creating {MAX_CONTEXTS} browser contexts...")
    _pool = asyncio.Queue(maxsize=MAX_CONTEXTS)
    for i in range(MAX_CONTEXTS):
        ctx = await _new_context()
        await _pool.put(ctx)
        logger.info(f"[POOL] Context {i+1}/{MAX_CONTEXTS} created")
    logger.info(f"[POOL] Context pool ready: {MAX_CONTEXTS} contexts available")


async def stop_pool() -> None:
    logger.info("[POOL] Shutting down pool...")
    closed = 0
    if _pool:
        while not _pool.empty():
            ctx = _pool.get_nowait()
            try:
                await ctx.close()
                closed += 1
            except Exception as e:
                logger.warning(f"[POOL] Error closing context: {e}")
    logger.info(f"[POOL] Closed {closed} contexts")
    if _browser:
        await _browser.close()
        logger.info("[POOL] Browser closed")
    if _playwright:
        await _playwright.stop()
        logger.info("[POOL] Playwright stopped")


async def acquire() -> BrowserContext:
    before = _pool.qsize()
    ctx = await _pool.get()
    after = _pool.qsize()
    logger.debug(f"[POOL] Context acquired — free: {before} -> {after}/{MAX_CONTEXTS}")
    return ctx


async def release(ctx: BrowserContext, healthy: bool = True) -> None:
    global _recycled, _replaced
    if not healthy:
        logger.warning("[POOL] Unhealthy context — closing and replacing...")
        try:
            await ctx.close()
        except Exception as e:
            logger.warning(f"[POOL] Error closing unhealthy context: {e}")
        try:
            ctx = await _new_context()
            _replaced += 1
            logger.info(f"[POOL] Replacement context created (total replaced={_replaced})")
        except Exception as e:
            logger.error(f"[POOL] CRITICAL: Failed to create replacement context: {e}")
            return
    else:
        try:
            pages = ctx.pages
            for page in pages:
                await page.close()
            if pages:
                logger.debug(f"[POOL] Cleared {len(pages)} page(s) from recycled context")
            _recycled += 1
        except Exception as e:
            logger.warning(f"[POOL] Error clearing pages: {e}")

    await _pool.put(ctx)
    after = _pool.qsize()
    logger.debug(f"[POOL] Context returned — free={after}/{MAX_CONTEXTS} | recycled={_recycled} replaced={_replaced}")


def pool_size() -> int:
    return _pool.qsize() if _pool else 0


def pool_stats() -> dict:
    return {
        "total": MAX_CONTEXTS,
        "free": pool_size(),
        "busy": MAX_CONTEXTS - pool_size(),
        "recycled": _recycled,
        "replaced": _replaced,
    }
