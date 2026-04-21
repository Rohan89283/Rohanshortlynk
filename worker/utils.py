import os
import random
import string
import httpx

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
BOT_ADMIN_ID = int(os.environ.get("BOT_ADMIN_ID", "935200729"))

_FAKE_FIRST_NAMES = ["James", "John", "Robert", "Michael", "David", "William", "Richard", "Joseph", "Thomas", "Charles"]
_FAKE_LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]
_FAKE_ADDRESSES = [
    ("123 Elm Street", "New York", "NY", "10001"),
    ("456 Oak Avenue", "Los Angeles", "CA", "90001"),
    ("789 Pine Road", "Chicago", "IL", "60601"),
    ("321 Maple Drive", "Houston", "TX", "77001"),
    ("654 Cedar Lane", "Phoenix", "AZ", "85001"),
]

_bin_cache: dict = {}


def get_fake_identity() -> dict:
    first = random.choice(_FAKE_FIRST_NAMES)
    last = random.choice(_FAKE_LAST_NAMES)
    addr = random.choice(_FAKE_ADDRESSES)
    phone = (
        random.choice(["201", "202", "203", "205", "206", "207", "208", "209"])
        + random.choice(["201", "202", "303", "404", "505", "606"])
        + "".join(random.choices(string.digits, k=4))
    )
    email = "".join(random.choices(string.ascii_lowercase + string.digits, k=10)) + "@gmail.com"
    return {
        "first_name": first,
        "last_name": last,
        "address": addr[0],
        "city": addr[1],
        "state": addr[2],
        "zip": addr[3],
        "phone": phone,
        "email": email,
    }


def get_wrong_cvv(exclude: str) -> str:
    while True:
        fake = "".join(random.choices(string.digits, k=len(exclude)))
        if fake != exclude:
            return fake


def split_card(card_input: str) -> tuple:
    parts = card_input.replace(" ", "|").replace("/", "|").replace("\\", "|").strip().split("|")
    if len(parts) != 4:
        raise ValueError("Invalid card format")
    return parts[0], parts[1].zfill(2), parts[2][-2:], parts[3]


async def get_bin_info(bin_number: str) -> tuple:
    if bin_number in _bin_cache:
        return _bin_cache[bin_number]
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            res = await client.get(f"https://bins.antipublic.cc/bins/{bin_number}")
            if res.status_code == 200:
                data = res.json()
                brand = data.get("brand", "Unknown").upper()
                type_ = data.get("type", "Unknown").upper()
                country = data.get("country_name", "Unknown")
                country_code = data.get("country", "") or data.get("country_code", "")
                flag = ""
                if country_code and len(country_code) == 2:
                    try:
                        flag = "".join(chr(ord(c) + 127397) for c in country_code.upper())
                    except Exception:
                        flag = data.get("country_flag", "")
                else:
                    flag = data.get("country_flag", "")
                bank = data.get("bank", "Unknown")
                level = data.get("level", "")
                parts = [brand]
                if type_ and type_ != "UNKNOWN":
                    parts.append(type_)
                if country and country != "Unknown":
                    parts.append(country)
                if level:
                    parts.append(level)
                if bank and bank != "Unknown":
                    parts.append(bank)
                result = (" • ".join(parts), flag)
                if len(_bin_cache) < 1000:
                    _bin_cache[bin_number] = result
                return result
    except Exception:
        pass
    return ("Unavailable", "")


async def tg_edit(chat_id: int, message_id: int, text: str) -> None:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText",
                data={"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "Markdown"},
            )
    except Exception:
        pass


async def tg_admin_screenshot(cmd: str, trace: str, screenshot_bytes: bytes | None) -> None:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            if screenshot_bytes:
                await client.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                    data={
                        "chat_id": BOT_ADMIN_ID,
                        "caption": f"{cmd.upper()} Error:\n```\n{trace[:800]}\n```",
                        "parse_mode": "Markdown",
                    },
                    files={"photo": ("fail.png", screenshot_bytes, "image/png")},
                )
            else:
                await client.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    data={
                        "chat_id": BOT_ADMIN_ID,
                        "text": f"{cmd.upper()} Error:\n```\n{trace[:900]}\n```",
                        "parse_mode": "Markdown",
                    },
                )
    except Exception:
        pass
