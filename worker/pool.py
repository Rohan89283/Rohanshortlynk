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


async def _new_context() -> BrowserContext:
    global _ctx_index
    ua = _USER_AGENTS[_ctx_index % len(_USER_AGENTS)]
    _ctx_index += 1
    ctx = await _browser.new_context(
        viewport={"width": 1920, "height": 1080},
        user_agent=ua,
        locale="en-US",
        timezone_id="America/New_York",
        extra_http_headers={
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    # Mask webdriver flag
    await ctx.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
        Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
    """)
    return ctx


async def start_pool() -> None:
    global _playwright, _browser, _pool
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
    _pool = asyncio.Queue(maxsize=MAX_CONTEXTS)
    for _ in range(MAX_CONTEXTS):
        ctx = await _new_context()
        await _pool.put(ctx)
    logger.info(f"Context pool ready: {MAX_CONTEXTS} contexts")


async def stop_pool() -> None:
    if _pool:
        while not _pool.empty():
            ctx = _pool.get_nowait()
            try:
                await ctx.close()
            except Exception:
                pass
    if _browser:
        await _browser.close()
    if _playwright:
        await _playwright.stop()


async def acquire() -> BrowserContext:
    return await _pool.get()


async def release(ctx: BrowserContext, healthy: bool = True) -> None:
    if not healthy:
        try:
            await ctx.close()
        except Exception:
            pass
        try:
            ctx = await _new_context()
        except Exception:
            logger.error("Failed to create replacement context")
            return
    else:
        # Clear all pages so next job starts fresh
        try:
            for page in ctx.pages:
                await page.close()
        except Exception:
            pass
    await _pool.put(ctx)


def pool_size() -> int:
    return _pool.qsize() if _pool else 0
