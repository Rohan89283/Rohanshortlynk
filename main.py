import os
import re
import gc
import io
import json
import time
import html
import uuid
import psutil
import shutil
import zipfile
import random
import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import requests
from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    InputFile,
)
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# =========================================================
# CONFIG
# =========================================================
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
BOT_ADMIN_RAW = os.getenv("BOT_ADMIN", "").strip()

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing")

if not BOT_ADMIN_RAW:
    raise RuntimeError("BOT_ADMIN is missing")

ADMIN_IDS: List[int] = []
for x in BOT_ADMIN_RAW.split(","):
    x = x.strip()
    if x.isdigit():
        ADMIN_IDS.append(int(x))

if not ADMIN_IDS:
    raise RuntimeError("BOT_ADMIN has no valid numeric admin IDs")

APP_START_TS = time.time()
BASE_DIR = Path(".").resolve()

DATA_DIR = BASE_DIR / "data"
TMP_DIR = BASE_DIR / "tmp"
LOG_DIR = BASE_DIR / "logs"

DATA_DIR.mkdir(exist_ok=True)
TMP_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

USERS_FILE = DATA_DIR / "users.json"
PROXIES_FILE = DATA_DIR / "proxies.json"
SETTINGS_FILE = DATA_DIR / "settings.json"
BOT_LOG_FILE = LOG_DIR / "bot.log"

CHK_CONCURRENCY = 15
CHK_TIMEOUT = 12
CHK_RETRIES = 3
RESULT_PREVIEW_LIMIT = 25

# callback/session memory
RESULT_SESSIONS: Dict[str, dict] = {}

# =========================================================
# LOGGING
# =========================================================
logger = logging.getLogger("ig_checker_bot")
logger.setLevel(logging.INFO)

if not logger.handlers:
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    file_handler = logging.FileHandler(BOT_LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)


# =========================================================
# JSON HELPERS
# =========================================================
def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.exception("Failed loading %s: %s", path, e)
        return default


def save_json(path: Path, data) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    tmp.replace(path)


# =========================================================
# STATE
# =========================================================
users: Dict[str, dict] = load_json(USERS_FILE, {})

proxies_data: dict = load_json(
    PROXIES_FILE,
    {
        "items": [],
        "command_proxy_enabled": {
            "chk": False
        }
    }
)

settings_data: dict = load_json(
    SETTINGS_FILE,
    {
        "auto_backup_enabled": True
    }
)


# =========================================================
# GENERAL HELPERS
# =========================================================
def now_ts() -> int:
    return int(time.time())


def esc(text) -> str:
    return html.escape(str(text))


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def fmt_uptime(seconds: float) -> str:
    s = int(seconds)
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    parts = []
    if d:
        parts.append(f"{d}d")
    if h:
        parts.append(f"{h}h")
    if m:
        parts.append(f"{m}m")
    parts.append(f"{s}s")
    return " ".join(parts)


def panel(title: str, body: str) -> str:
    return f"<b>{esc(title)}</b>\n\n{body}"


def ensure_user(user_id: int, tg_user=None) -> dict:
    uid = str(user_id)
    if uid not in users:
        users[uid] = {
            "id": user_id,
            "name": tg_user.full_name if tg_user else "",
            "username": tg_user.username if tg_user and tg_user.username else "",
            "banned": False,
            "permissions": {
                "chk": False
            },
            "created_at": now_ts(),
            "updated_at": now_ts(),
        }
    else:
        if tg_user:
            users[uid]["name"] = tg_user.full_name
            users[uid]["username"] = tg_user.username or ""
            users[uid]["updated_at"] = now_ts()

    save_json(USERS_FILE, users)
    return users[uid]


def user_status_label(user_id: int) -> str:
    if is_admin(user_id):
        return "ADMIN"
    u = ensure_user(user_id)
    if u.get("banned"):
        return "BANNED"
    if u.get("permissions", {}).get("chk"):
        return "PREMIUM"
    return "FREE"


def has_permission(user_id: int, permission: str) -> bool:
    if is_admin(user_id):
        return True
    u = ensure_user(user_id)
    if u.get("banned"):
        return False
    return bool(u.get("permissions", {}).get(permission, False))


def set_permission(user_id: str, permission: str, value: bool) -> None:
    if user_id not in users:
        users[user_id] = {
            "id": int(user_id),
            "name": "",
            "username": "",
            "banned": False,
            "permissions": {"chk": False},
            "created_at": now_ts(),
            "updated_at": now_ts(),
        }
    users[user_id].setdefault("permissions", {})
    users[user_id]["permissions"][permission] = value
    users[user_id]["updated_at"] = now_ts()
    save_json(USERS_FILE, users)


def set_ban(user_id: str, value: bool) -> None:
    if user_id not in users:
        users[user_id] = {
            "id": int(user_id),
            "name": "",
            "username": "",
            "banned": False,
            "permissions": {"chk": False},
            "created_at": now_ts(),
            "updated_at": now_ts(),
        }
    users[user_id]["banned"] = value
    users[user_id]["updated_at"] = now_ts()
    save_json(USERS_FILE, users)


def parse_user_id_arg(args: List[str]) -> Optional[str]:
    if not args:
        return None
    candidate = args[0].strip()
    if candidate.isdigit():
        return candidate
    return None


def admin_only_text() -> str:
    return "❌ <b>Admin only.</b>"


# =========================================================
# USERNAME HELPERS
# =========================================================
def clean_username_line(line: str) -> Optional[str]:
    line = line.strip()
    if not line:
        return None

    # support profile URLs
    line = line.replace("https://www.instagram.com/", "")
    line = line.replace("http://www.instagram.com/", "")
    line = line.replace("https://instagram.com/", "")
    line = line.replace("http://instagram.com/", "")

    line = line.strip("/")
    if line.startswith("@"):
        line = line[1:]

    line = line.split("?")[0].strip()
    if not line:
        return None

    if not re.fullmatch(r"[A-Za-z0-9._]+", line):
        return None

    return line


def unique_keep_order(items: List[str]) -> List[str]:
    return list(dict.fromkeys(items))


# =========================================================
# PROXY SYSTEM
# =========================================================
def save_proxies() -> None:
    save_json(PROXIES_FILE, proxies_data)


def get_all_proxies() -> List[str]:
    return proxies_data.get("items", [])


def add_proxy_line(proxy_line: str) -> Tuple[bool, str]:
    proxy_line = proxy_line.strip()
    if not proxy_line:
        return False, "Empty proxy."

    parts = proxy_line.split(":")
    if len(parts) != 4:
        return False, "Proxy must be host:port:user:pass"

    if proxy_line in proxies_data["items"]:
        return False, "Proxy already exists."

    proxies_data["items"].append(proxy_line)
    save_proxies()
    return True, "Proxy added."


def delete_proxy_value(proxy_line: str) -> Tuple[bool, str]:
    proxy_line = proxy_line.strip()
    if proxy_line not in proxies_data["items"]:
        return False, "Proxy not found."

    proxies_data["items"].remove(proxy_line)
    save_proxies()
    return True, "Proxy deleted."


def set_command_proxy_enabled(command_name: str, value: bool) -> None:
    proxies_data.setdefault("command_proxy_enabled", {})
    proxies_data["command_proxy_enabled"][command_name] = value
    save_proxies()


def is_proxy_enabled_for(command_name: str) -> bool:
    return bool(proxies_data.get("command_proxy_enabled", {}).get(command_name, False))


def build_requests_proxy(proxy_line: str) -> Optional[dict]:
    try:
        host, port, user, password = proxy_line.split(":", 3)
        proxy_url = f"http://{user}:{password}@{host}:{port}"
        return {"http": proxy_url, "https": proxy_url}
    except Exception:
        return None


# =========================================================
# INSTAGRAM CHECKER
# =========================================================
def check_username_once(username: str, use_proxy: bool) -> str:
    url = f"https://www.instagram.com/{username}/"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Connection": "keep-alive",
    }

    proxy_dict = None
    if use_proxy and proxies_data.get("items"):
        chosen = random.choice(proxies_data["items"])
        proxy_dict = build_requests_proxy(chosen)

    response = requests.get(
        url,
        headers=headers,
        proxies=proxy_dict,
        timeout=CHK_TIMEOUT,
        allow_redirects=True,
    )

    text = response.text

    # primary signal
    needle = f'rel="alternate" href="https://www.instagram.com/{username}/"'
    if needle in text:
        return "EXISTS"

    # fallback signal
    needle2 = f'"https://www.instagram.com/{username}/"'
    if needle2 in text and "page isn&#x27;t available" not in text.lower():
        return "EXISTS"

    return "NOT_EXIST"


def check_username_with_retry(username: str, use_proxy: bool) -> str:
    last_err = None
    for _ in range(CHK_RETRIES):
        try:
            return check_username_once(username, use_proxy)
        except Exception as e:
            last_err = e
    logger.warning("Check failed for %s after retries: %s", username, last_err)
    return "ERROR"


async def run_mass_check(
    usernames: List[str],
    use_proxy: bool,
) -> Tuple[List[str], List[str], List[str], List[str]]:
    semaphore = asyncio.Semaphore(CHK_CONCURRENCY)

    results_lines: List[str] = []
    exists: List[str] = []
    not_exists: List[str] = []
    errors: List[str] = []

    async def worker(username: str):
        async with semaphore:
            result = await asyncio.to_thread(check_username_with_retry, username, use_proxy)
            line = f"{username} -> {result}"
            results_lines.append(line)

            if result == "EXISTS":
                exists.append(username)
            elif result == "NOT_EXIST":
                not_exists.append(username)
            else:
                errors.append(username)

    await asyncio.gather(*(worker(u) for u in usernames))

    # keep original order in output
    order_map = {u: i for i, u in enumerate(usernames)}
    results_lines.sort(key=lambda line: order_map.get(line.split(" -> ", 1)[0], 10**9))
    exists.sort(key=lambda u: order_map.get(u, 10**9))
    not_exists.sort(key=lambda u: order_map.get(u, 10**9))
    errors.sort(key=lambda u: order_map.get(u, 10**9))

    return results_lines, exists, not_exists, errors


# =========================================================
# FILE HELPERS
# =========================================================
def write_text_file(path: Path, lines: List[str]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def create_backup_zip() -> Path:
    backup_name = f"backup_{int(time.time())}.zip"
    backup_path = TMP_DIR / backup_name

    with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in [
            USERS_FILE,
            PROXIES_FILE,
            SETTINGS_FILE,
            BOT_LOG_FILE,
            BASE_DIR / "main.py",
            BASE_DIR / "requirements.txt",
            BASE_DIR / "Dockerfile",
        ]:
            if path.exists():
                zf.write(path, arcname=path.name)

    return backup_path


async def restore_from_document(file_bytes: bytes, filename: str) -> str:
    restore_dir = TMP_DIR / f"restore_{int(time.time())}"
    restore_dir.mkdir(exist_ok=True)

    target = restore_dir / filename
    with open(target, "wb") as f:
        f.write(file_bytes)

    restored = []

    if filename.lower().endswith(".zip"):
        with zipfile.ZipFile(target, "r") as zf:
            zf.extractall(restore_dir)
        candidates = list(restore_dir.glob("*"))
    else:
        candidates = [target]

    global users, proxies_data, settings_data

    for file_path in candidates:
        name = file_path.name.lower()

        if name == "users.json":
            shutil.copy(file_path, USERS_FILE)
            users = load_json(USERS_FILE, {})
            restored.append("users.json")

        elif name == "proxies.json":
            shutil.copy(file_path, PROXIES_FILE)
            proxies_data = load_json(
                PROXIES_FILE,
                {
                    "items": [],
                    "command_proxy_enabled": {"chk": False}
                }
            )
            restored.append("proxies.json")

        elif name == "settings.json":
            shutil.copy(file_path, SETTINGS_FILE)
            settings_data = load_json(
                SETTINGS_FILE,
                {"auto_backup_enabled": True}
            )
            restored.append("settings.json")

    if not restored:
        return "No supported restore files found. Supported: users.json, proxies.json, settings.json, or backup zip."

    return "Restored: " + ", ".join(restored)


def make_result_session(owner_id: int, exists: List[str], not_exists: List[str], results: List[str]) -> str:
    session_id = uuid.uuid4().hex[:12]
    session_dir = TMP_DIR / f"chk_{session_id}"
    session_dir.mkdir(exist_ok=True)

    exists_file = session_dir / "exists.txt"
    not_exists_file = session_dir / "not_exists.txt"
    all_file = session_dir / "all_results.txt"

    write_text_file(exists_file, exists)
    write_text_file(not_exists_file, not_exists)
    write_text_file(all_file, results)

    RESULT_SESSIONS[session_id] = {
        "owner_id": owner_id,
        "exists_file": str(exists_file),
        "not_exists_file": str(not_exists_file),
        "all_file": str(all_file),
        "created_at": now_ts(),
    }
    return session_id


# =========================================================
# AUTO BACKUP JOB
# =========================================================
async def auto_send_users_backup(context: ContextTypes.DEFAULT_TYPE) -> None:
    if not settings_data.get("auto_backup_enabled", True):
        return

    if not USERS_FILE.exists():
        return

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_document(
                chat_id=admin_id,
                document=InputFile(str(USERS_FILE)),
                caption="🗂 <b>Auto users backup</b>\n\nSent every 48 hours.",
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            logger.exception("Failed sending auto users backup to %s: %s", admin_id, e)


# =========================================================
# BASIC COMMANDS
# =========================================================
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_user = update.effective_user
    ensure_user(tg_user.id, tg_user)

    body = (
        f"👋 Welcome, <b>{esc(tg_user.full_name)}</b>\n\n"
        f"Use <code>/cmds</code> to see commands.\n"
        f"Use <code>/help</code> to see usage.\n\n"
        f"Your status: <b>{esc(user_status_label(tg_user.id))}</b>"
    )
    await update.message.reply_text(panel("IG Checker Bot", body), parse_mode=ParseMode.HTML)


async def cmds_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    ensure_user(uid, update.effective_user)

    free_block = (
        "🔹 <b>Free Commands</b>\n"
        "<code>/start</code> - Welcome panel\n"
        "<code>/cmds</code> - Command list\n"
        "<code>/help</code> - Detailed usage\n"
        "<code>/id</code> - Your Telegram info and bot status\n"
        "<code>/ping</code> - Ping and uptime"
    )

    premium_block = (
        "💎 <b>Premium Commands</b>\n"
        "<code>/chk user1 user2 ...</code> - Check one or many Instagram usernames\n"
        "Also supports replying to a .txt file with one username per line"
    )

    text = free_block + "\n\n" + premium_block

    if is_admin(uid):
        admin_block = (
            "👑 <b>Admin Commands</b>\n"
            "<code>/approve &lt;id&gt; [chk|all]</code>\n"
            "<code>/revoke &lt;id&gt; [chk|all]</code>\n"
            "<code>/ban &lt;id&gt;</code>\n"
            "<code>/unban &lt;id&gt;</code>\n"
            "<code>/ram</code>\n"
            "<code>/cleanram</code>\n"
            "<code>/log</code>\n"
            "<code>/backup</code>\n"
            "<code>/restore</code> - reply to users.json / proxies.json / settings.json / backup zip\n"
            "<code>/proxy</code> - proxy control panel"
        )
        text += "\n\n" + admin_block

    await update.message.reply_text(panel("Command List", text), parse_mode=ParseMode.HTML)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    ensure_user(uid, update.effective_user)

    text = (
        "🔹 <b>How to Use</b>\n\n"
        "<b>/id</b>\n"
        "Shows your name, username, Telegram ID, and bot status.\n\n"
        "<b>/ping</b>\n"
        "Shows bot responsiveness and uptime.\n\n"
        "<b>/chk</b>\n"
        "Examples:\n"
        "<code>/chk uoigfdd</code>\n"
        "<code>/chk user1 user2 user3</code>\n"
        "You can also reply to a .txt file containing one username per line.\n"
        "The bot retries failed checks up to 3 times.\n"
        "Results include per-username status, summary, and TXT download buttons."
    )

    if is_admin(uid):
        text += (
            "\n\n👑 <b>Admin Notes</b>\n"
            "<b>/approve</b> grants command permission.\n"
            "<b>/revoke</b> removes command permission.\n"
            "<b>/ban</b> blocks a user from using the bot.\n"
            "<b>/unban</b> removes a ban.\n"
            "<b>/proxy</b> manages proxies and proxy use for /chk.\n"
            "<b>/backup</b> sends important bot files as ZIP.\n"
            "<b>/restore</b> restores supported JSON files from a replied document.\n"
            "<b>/log</b> sends the bot log file.\n"
            "<b>/ram</b> shows server memory and disk details.\n"
            "<b>/cleanram</b> cleans temp files and runs garbage collection."
        )

    await update.message.reply_text(panel("Help", text), parse_mode=ParseMode.HTML)


async def id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_user = update.effective_user
    u = ensure_user(tg_user.id, tg_user)

    text = (
        f"👤 <b>User Info</b>\n\n"
        f"Name: <b>{esc(tg_user.full_name)}</b>\n"
        f"Username: @{esc(tg_user.username or 'None')}\n"
        f"ID: <code>{tg_user.id}</code>\n"
        f"Status: <b>{esc(user_status_label(tg_user.id))}</b>\n"
        f"Banned: <b>{esc(u.get('banned', False))}</b>\n"
        f"CHK Access: <b>{esc(u.
