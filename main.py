import asyncio
import gc
import io
import json
import logging
import os
import random
import re
import shutil
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import psutil
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# =========================
# CONFIG
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = {
    int(x.strip())
    for x in os.getenv("BOT_ADMIN", "").split(",")
    if x.strip().isdigit()
}

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
BACKUP_DIR = BASE_DIR / "backups"
TEMP_DIR = BASE_DIR / "temp"
LOG_DIR = BASE_DIR / "logs"
USER_DB_FILE = DATA_DIR / "users.json"
PROXY_DB_FILE = DATA_DIR / "proxies.json"
RUNTIME_LOG_FILE = LOG_DIR / "bot.log"
CHK_COMMAND_NAME = "chk"
MAX_RETRIES = 3
DEFAULT_THREADS = 12
CHK_FILE_SIZE_LIMIT = 1_500_000  # ~1.5 MB input guard

for p in [DATA_DIR, BACKUP_DIR, TEMP_DIR, LOG_DIR]:
    p.mkdir(parents=True, exist_ok=True)

# =========================
# LOGGING
# =========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.FileHandler(RUNTIME_LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("ig-check-bot")
START_TIME = time.time()

# =========================
# STORAGE HELPERS
# =========================
def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("Failed loading %s", path)
        return default


def save_json(path: Path, data) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


user_db: Dict[str, dict] = load_json(USER_DB_FILE, {})
proxy_db: Dict[str, object] = load_json(
    PROXY_DB_FILE,
    {
        "proxies": [],
        "command_proxy_enabled": {CHK_COMMAND_NAME: False},
        "updated_at": utc_now_iso(),
    },
)

active_chk_results: Dict[str, dict] = {}

# =========================
# DEFAULT USER MODEL
# =========================
def default_user_record(user_id: int) -> dict:
    is_admin = user_id in ADMIN_IDS
    return {
        "user_id": user_id,
        "is_banned": False,
        "status": "admin" if is_admin else "free",
        "approved_cmds": [CHK_COMMAND_NAME] if is_admin else [],
        "premium_requested": False,
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
        "last_seen_at": utc_now_iso(),
        "usage": {CHK_COMMAND_NAME: 0},
        "notes": "",
    }


def ensure_user(user) -> dict:
    key = str(user.id)
    if key not in user_db:
        user_db[key] = default_user_record(user.id)
    record = user_db[key]
    if user.id in ADMIN_IDS:
        record["status"] = "admin"
        if CHK_COMMAND_NAME not in record["approved_cmds"]:
            record["approved_cmds"].append(CHK_COMMAND_NAME)
    record["last_seen_at"] = utc_now_iso()
    record["updated_at"] = utc_now_iso()
    save_json(USER_DB_FILE, user_db)
    return record


def get_user_record(user_id: int) -> dict:
    key = str(user_id)
    if key not in user_db:
        user_db[key] = default_user_record(user_id)
        save_json(USER_DB_FILE, user_db)
    return user_db[key]


def set_user_record(user_id: int, record: dict) -> None:
    record["updated_at"] = utc_now_iso()
    user_db[str(user_id)] = record
    save_json(USER_DB_FILE, user_db)


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def is_banned(user_id: int) -> bool:
    return get_user_record(user_id).get("is_banned", False)


def can_use_cmd(user_id: int, cmd: str) -> bool:
    if is_admin(user_id):
        return True
    record = get_user_record(user_id)
    if record.get("is_banned"):
        return False
    return cmd in record.get("approved_cmds", [])


def increment_usage(user_id: int, cmd: str) -> None:
    record = get_user_record(user_id)
    usage = record.setdefault("usage", {})
    usage[cmd] = usage.get(cmd, 0) + 1
    set_user_record(user_id, record)

# =========================
# PROXY HELPERS
# =========================
def save_proxy_db() -> None:
    proxy_db["updated_at"] = utc_now_iso()
    save_json(PROXY_DB_FILE, proxy_db)


def parse_proxy_line(line: str) -> Optional[dict]:
    parts = line.strip().split(":")
    if len(parts) != 4:
        return None
    host, port, username, password = parts
    if not host or not port.isdigit() or not username or not password:
        return None
    return {
        "host": host,
        "port": int(port),
        "username": username,
        "password": password,
        "raw": line.strip(),
        "added_at": utc_now_iso(),
    }


def build_requests_proxy(proxy: dict) -> dict:
    proxy_url = f"http://{proxy['username']}:{proxy['password']}@{proxy['host']}:{proxy['port']}"
    return {"http": proxy_url, "https": proxy_url}


def chk_uses_proxy() -> bool:
    return bool(proxy_db.get("command_proxy_enabled", {}).get(CHK_COMMAND_NAME, False))

# =========================
# CHECKER CORE
# =========================
@dataclass
class CheckResult:
    username: str
    status: str  # EXISTS / NOT_EXIST / ERROR
    attempts: int
    error: str = ""


def normalize_username(s: str) -> Optional[str]:
    s = s.strip()
    if not s:
        return None
    s = s.replace("https://www.instagram.com/", "")
    s = s.replace("http://www.instagram.com/", "")
    s = s.replace("https://instagram.com/", "")
    s = s.replace("http://instagram.com/", "")
    s = s.strip("/@ ")
    s = s.split("?")[0].split("/")[0]
    if not s:
        return None
    if not re.fullmatch(r"[A-Za-z0-9._]{1,30}", s):
        return None
    return s.lower()


def parse_usernames_from_text(text: str) -> List[str]:
    usernames = []
    seen = set()
    for raw in re.split(r"[\s,]+", text or ""):
        username = normalize_username(raw)
        if username and username not in seen:
            usernames.append(username)
            seen.add(username)
    return usernames


async def fetch_text(url: str, *, proxy: Optional[dict] = None, timeout: int = 15) -> Tuple[str, str]:
    headers = {"User-Agent": "Mozilla/5.0"}

    def _do_request() -> Tuple[str, str]:
        import requests

        kwargs = {"headers": headers, "timeout": timeout}
        if proxy:
            kwargs["proxies"] = build_requests_proxy(proxy)
        r = requests.get(url, **kwargs)
        return r.text, str(r.status_code)

    return await asyncio.to_thread(_do_request)


async def check_one_username(username: str) -> CheckResult:
    proxy_list = proxy_db.get("proxies", []) if chk_uses_proxy() else []
    last_error = ""

    for attempt in range(1, MAX_RETRIES + 1):
        proxy = random.choice(proxy_list) if proxy_list else None
        try:
            html, status_code = await fetch_text(
                f"https://www.instagram.com/{username}/",
                proxy=proxy,
            )
            marker = f'rel="alternate" href="https://www.instagram.com/{username}/"'
            if marker in html:
                return CheckResult(username=username, status="EXISTS", attempts=attempt)
            return CheckResult(username=username, status="NOT_EXIST", attempts=attempt)
        except Exception as exc:
            last_error = f"attempt {attempt}: {exc}"
            logger.warning("check failed for %s | %s", username, last_error)
            await asyncio.sleep(0.4)

    return CheckResult(username=username, status="ERROR", attempts=MAX_RETRIES, error=last_error)


async def run_mass_check(usernames: List[str]) -> dict:
    started = time.time()
    semaphore = asyncio.Semaphore(DEFAULT_THREADS)

    async def _guarded(name: str) -> CheckResult:
        async with semaphore:
            return await check_one_username(name)

    results = await asyncio.gather(*[_guarded(x) for x in usernames])
    duration = round(time.time() - started, 2)
    exists = [r.username for r in results if r.status == "EXISTS"]
    not_exist = [r.username for r in results if r.status == "NOT_EXIST"]
    errors = [r for r in results if r.status == "ERROR"]

    full_lines = []
    for r in results:
        if r.status == "ERROR":
            full_lines.append(f"{r.username} -> ⚠️ ERROR | retries={r.attempts} | {r.error}")
        elif r.status == "EXISTS":
            full_lines.append(f"{r.username} -> ✅ EXISTS | tries={r.attempts}")
        else:
            full_lines.append(f"{r.username} -> ❌ NOT EXIST | tries={r.attempts}")

    return {
        "results": results,
        "exists": exists,
        "not_exist": not_exist,
        "errors": errors,
        "total": len(results),
        "duration": duration,
        "full_text": "\n".join(full_lines),
        "exists_text": "\n".join(exists) if exists else "",
        "not_exist_text": "\n".join(not_exist) if not_exist else "",
    }

# =========================
# TELEGRAM HELPERS
# =========================
def mention_user_info(user) -> str:
    fullname = " ".join(x for x in [user.first_name, user.last_name] if x).strip() or "No name"
    uname = f"@{user.username}" if user.username else "No username"
    record = get_user_record(user.id)
    return (
        f"Name: {fullname}\n"
        f"Username: {uname}\n"
        f"User ID: {user.id}\n"
        f"Status: {record.get('status', 'free')}\n"
        f"Banned: {'Yes' if record.get('is_banned') else 'No'}\n"
        f"Approved cmds: {', '.join(record.get('approved_cmds', [])) or 'None'}"
    )


def format_uptime() -> str:
    sec = int(time.time() - START_TIME)
    d, rem = divmod(sec, 86400)
    h, rem = divmod(rem, 3600)
    m, s = divmod(rem, 60)
    parts = []
    if d:
        parts.append(f"{d}d")
    if h or parts:
        parts.append(f"{h}h")
    if m or parts:
        parts.append(f"{m}m")
    parts.append(f"{s}s")
    return " ".join(parts)


def ensure_not_banned(update: Update) -> bool:
    user = update.effective_user
    if not user:
        return False
    ensure_user(user)
    if is_banned(user.id):
        return False
    return True


def require_admin(update: Update) -> bool:
    user = update.effective_user
    return bool(user and is_admin(user.id))


async def send_text_file(message, filename: str, content: str, caption: str) -> None:
    bio = io.BytesIO(content.encode("utf-8"))
    bio.name = filename
    await message.reply_document(document=bio, caption=caption)


def chk_result_keyboard(job_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Exists txt", callback_data=f"chkfile:exists:{job_id}"),
                InlineKeyboardButton("Not exist txt", callback_data=f"chkfile:not:{job_id}"),
            ],
            [
                InlineKeyboardButton("Full results txt", callback_data=f"chkfile:full:{job_id}"),
            ],
        ]
    )


def proxy_panel_keyboard() -> InlineKeyboardMarkup:
    status = "ON" if chk_uses_proxy() else "OFF"
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(f"/chk proxy: {status}", callback_data="proxy:toggle_chk")],
            [
                InlineKeyboardButton("Show proxies", callback_data="proxy:show"),
                InlineKeyboardButton("Proxy status", callback_data="proxy:status"),
            ],
            [
                InlineKeyboardButton("Add proxy", callback_data="proxy:add"),
                InlineKeyboardButton("Delete proxy", callback_data="proxy:delete"),
            ],
        ]
    )

# =========================
# BASIC COMMANDS
# =========================
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not ensure_not_banned(update):
        return
    user = update.effective_user
    text = (
        "Instagram checker bot is online.\n\n"
        "User cmds:\n"
        "/premium - request premium approval\n"
        "/chk - single or mass Instagram username check\n\n"
        "Free cmds:\n"
        "/id - your bot info\n"
        "/ping - uptime and latency\n"
    )
    if is_admin(user.id):
        text += "\nAdmin cmds enabled."
    await update.message.reply_text(text)


async def id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not ensure_not_banned(update):
        return
    await update.message.reply_text(mention_user_info(update.effective_user))


async def ping_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not ensure_not_banned(update):
        return
    start = time.perf_counter()
    msg = await update.message.reply_text("Pinging...")
    latency_ms = round((time.perf_counter() - start) * 1000, 2)
    proc = psutil.Process(os.getpid())
    mem_mb = round(proc.memory_info().rss / 1024 / 1024, 2)
    await msg.edit_text(
        f"Pong ✅\nUptime: {format_uptime()}\nLatency: {latency_ms} ms\nRAM: {mem_mb} MB"
    )


async def premium_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not ensure_not_banned(update):
        return
    user = update.effective_user
    record = get_user_record(user.id)
    if can_use_cmd(user.id, CHK_COMMAND_NAME):
        await update.message.reply_text("You already have /chk access.")
        return
    record["premium_requested"] = True
    set_user_record(user.id, record)
    await update.message.reply_text("Premium request sent to admin for approval.")

    keyboard = InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("Approve /chk", callback_data=f"premiumapprove:{user.id}:chk"),
            InlineKeyboardButton("Approve all", callback_data=f"premiumapprove:{user.id}:all"),
        ]]
    )
    text = (
        f"Premium request\n\n"
        f"User ID: {user.id}\n"
        f"Name: {user.full_name}\n"
        f"Username: @{user.username}" if user.username else f"Username: none"
    )
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(admin_id, text, reply_markup=keyboard)
        except Exception:
            logger.exception("Failed notifying admin %s", admin_id)

# =========================
# /CHK
# =========================
async def read_usernames_from_reply_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> List[str]:
    msg = update.message
    if not msg or not msg.reply_to_message or not msg.reply_to_message.document:
        return []
    doc = msg.reply_to_message.document
    if not doc.file_name.lower().endswith(".txt"):
        return []
    if doc.file_size and doc.file_size > CHK_FILE_SIZE_LIMIT:
        await msg.reply_text("TXT file too large. Keep it under about 1.5 MB.")
        return []
    tg_file = await context.bot.get_file(doc.file_id)
    content = await tg_file.download_as_bytearray()
    text = bytes(content).decode("utf-8", errors="ignore")
    return parse_usernames_from_text(text)


async def chk_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not ensure_not_banned(update):
        return
    user = update.effective_user
    if not can_use_cmd(user.id, CHK_COMMAND_NAME):
        await update.message.reply_text("You do not have permission for /chk. Use /premium first.")
        return

    typed = " ".join(context.args) if context.args else ""
    usernames = parse_usernames_from_text(typed)
    if not usernames:
        usernames = await read_usernames_from_reply_file(update, context)
    if not usernames:
        await update.message.reply_text(
            "Use /chk username or /chk user1 user2 ...\n"
            "You can also reply to a .txt file that has one username per line."
        )
        return

    increment_usage(user.id, CHK_COMMAND_NAME)
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    status_msg = await update.message.reply_text(
        f"Checking {len(usernames)} username(s)...\nProxy for /chk: {'ON' if chk_uses_proxy() else 'OFF'}"
    )
    report = await run_mass_check(usernames)

    job_id = f"{user.id}_{int(time.time())}"
    active_chk_results[job_id] = {
        "owner": user.id,
        "created_at": utc_now_iso(),
        **report,
    }

    summary = (
        f"/chk finished ✅\n\n"
        f"Total checked: {report['total']}\n"
        f"Exists: {len(report['exists'])}\n"
        f"Not exist: {len(report['not_exist'])}\n"
        f"Errors: {len(report['errors'])}\n"
        f"Time took: {report['duration']} sec"
    )
    sample_lines = report["full_text"].splitlines()[:25]
    if sample_lines:
        summary += "\n\n" + "\n".join(sample_lines)
        if report["total"] > 25:
            summary += "\n..."

    await status_msg.edit_text(summary, reply_markup=chk_result_keyboard(job_id))


async def chk_file_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    _, kind, job_id = query.data.split(":", 2)
    data = active_chk_results.get(job_id)
    if not data:
        await query.message.reply_text("That result expired.")
        return
    if query.from_user.id != data["owner"] and not is_admin(query.from_user.id):
        await query.message.reply_text("This result belongs to another user.")
        return

    if kind == "exists":
        content = data["exists_text"] or ""
        filename = "exists_usernames.txt"
        caption = f"Exists usernames: {len(data['exists'])}"
    elif kind == "not":
        content = data["not_exist_text"] or ""
        filename = "not_exist_usernames.txt"
        caption = f"Not existing usernames: {len(data['not_exist'])}"
    else:
        content = (
            f"TOTAL CHECKED: {data['total']}\n"
            f"TOTAL EXISTS: {len(data['exists'])}\n"
            f"TOTAL NOT EXIST: {len(data['not_exist'])}\n"
            f"TOTAL ERRORS: {len(data['errors'])}\n"
            f"TIME TOOK: {data['duration']} sec\n\n"
            + data["full_text"]
        )
        filename = "full_results.txt"
        caption = "Full /chk results"

    if not content.strip():
        content = "No usernames in this category."
    await send_text_file(query.message, filename, content, caption)

# =========================
# ADMIN COMMANDS
# =========================
async def admin_guard_reply(update: Update) -> bool:
    if not require_admin(update):
        if update.message:
            await update.message.reply_text("Admin only.")
        return False
    return True


def parse_target_and_scope(args: List[str]) -> Tuple[Optional[int], Optional[str]]:
    if not args:
        return None, None
    try:
        target_id = int(args[0])
    except ValueError:
        return None, None
    scope = args[1].lower() if len(args) > 1 else CHK_COMMAND_NAME
    return target_id, scope


async def ban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await admin_guard_reply(update):
        return
    target_id, _ = parse_target_and_scope(context.args)
    if not target_id:
        await update.message.reply_text("Usage: /ban user_id")
        return
    record = get_user_record(target_id)
    record["is_banned"] = True
    set_user_record(target_id, record)
    await update.message.reply_text(f"Banned {target_id}.")


async def unban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await admin_guard_reply(update):
        return
    target_id, _ = parse_target_and_scope(context.args)
    if not target_id:
        await update.message.reply_text("Usage: /unban user_id")
        return
    record = get_user_record(target_id)
    record["is_banned"] = False
    set_user_record(target_id, record)
    await update.message.reply_text(f"Unbanned {target_id}.")


async def approve_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await admin_guard_reply(update):
        return
    target_id, scope = parse_target_and_scope(context.args)
    if not target_id or not scope:
        await update.message.reply_text("Usage: /approve user_id chk|all")
        return
    record = get_user_record(target_id)
    if scope == "all":
        record["approved_cmds"] = [CHK_COMMAND_NAME]
        record["status"] = "premium"
    elif scope == CHK_COMMAND_NAME:
        if CHK_COMMAND_NAME not in record["approved_cmds"]:
            record["approved_cmds"].append(CHK_COMMAND_NAME)
        record["status"] = "premium"
    else:
        await update.message.reply_text("Only chk or all supported right now.")
        return
    record["premium_requested"] = False
    set_user_record(target_id, record)
    await update.message.reply_text(f"Approved {scope} for {target_id}.")
    try:
        await context.bot.send_message(target_id, f"You were approved for {scope}.")
    except Exception:
        logger.exception("Failed to notify approved user %s", target_id)


async def revoke_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await admin_guard_reply(update):
        return
    target_id, scope = parse_target_and_scope(context.args)
    if not target_id or not scope:
        await update.message.reply_text("Usage: /revoke user_id chk|all")
        return
    record = get_user_record(target_id)
    if scope == "all":
        record["approved_cmds"] = []
        record["status"] = "free"
    elif scope == CHK_COMMAND_NAME:
        record["approved_cmds"] = [x for x in record.get("approved_cmds", []) if x != CHK_COMMAND_NAME]
        record["status"] = "free" if not record["approved_cmds"] else record.get("status", "free")
    else:
        await update.message.reply_text("Only chk or all supported right now.")
        return
    set_user_record(target_id, record)
    await update.message.reply_text(f"Revoked {scope} from {target_id}.")


async def ram_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await admin_guard_reply(update):
        return
    vm = psutil.virtual_memory()
    du = shutil.disk_usage(BASE_DIR)
    proc = psutil.Process(os.getpid())
    text = (
        f"RAM total: {round(vm.total/1024/1024,2)} MB\n"
        f"RAM used: {round(vm.used/1024/1024,2)} MB\n"
        f"RAM available: {round(vm.available/1024/1024,2)} MB\n"
        f"Process RSS: {round(proc.memory_info().rss/1024/1024,2)} MB\n"
        f"Disk total: {round(du.total/1024/1024/1024,2)} GB\n"
        f"Disk used: {round(du.used/1024/1024/1024,2)} GB\n"
        f"Disk free: {round(du.free/1024/1024/1024,2)} GB"
    )
    await update.message.reply_text(text)


async def cleanram_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await admin_guard_reply(update):
        return
    removed = 0
    for folder in [TEMP_DIR]:
        for item in folder.glob("*"):
            try:
                if item.is_file():
                    item.unlink()
                    removed += 1
                elif item.is_dir():
                    shutil.rmtree(item)
                    removed += 1
            except Exception:
                logger.exception("Failed removing temp item %s", item)
    gc.collect()
    await update.message.reply_text(f"Temp cleaned. Removed items: {removed}. Garbage collector run complete.")


async def log_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await admin_guard_reply(update):
        return
    if not RUNTIME_LOG_FILE.exists():
        await update.message.reply_text("No log file yet.")
        return
    await update.message.reply_document(document=RUNTIME_LOG_FILE.open("rb"), caption="Runtime log")


async def create_backup_bundle() -> List[Path]:
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_folder = BACKUP_DIR / f"backup_{stamp}"
    backup_folder.mkdir(parents=True, exist_ok=True)
    files_to_copy = [
        BASE_DIR / "main.py",
        BASE_DIR / "requirements.txt",
        BASE_DIR / "Dockerfile",
        USER_DB_FILE,
        PROXY_DB_FILE,
    ]
    copied = []
    for src in files_to_copy:
        if src.exists():
            dst = backup_folder / src.name
            shutil.copy2(src, dst)
            copied.append(dst)
    zip_path = BACKUP_DIR / f"backup_{stamp}.zip"
    shutil.make_archive(str(zip_path.with_suffix("")), "zip", backup_folder)
    copied.append(zip_path)
    return copied


async def backup_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await admin_guard_reply(update):
        return
    files = await create_backup_bundle()
    zip_file = [x for x in files if x.suffix == ".zip"][-1]
    await update.message.reply_document(document=zip_file.open("rb"), caption="Backup bundle")


async def restore_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await admin_guard_reply(update):
        return
    msg = update.message
    doc = None
    if msg.reply_to_message and msg.reply_to_message.document:
        doc = msg.reply_to_message.document
    elif msg.document:
        doc = msg.document
    if not doc:
        await msg.reply_text("Reply to users.json or proxies.json with /restore, or send the file with caption /restore.")
        return
    tg_file = await context.bot.get_file(doc.file_id)
    raw = await tg_file.download_as_bytearray()
    text = bytes(raw).decode("utf-8", errors="ignore")
    data = json.loads(text)
    lower_name = (doc.file_name or "").lower()
    if "proxy" in lower_name:
        proxy_db.clear()
        proxy_db.update(data)
        save_proxy_db()
        await msg.reply_text("Proxy database restored.")
    else:
        user_db.clear()
        user_db.update(data)
        save_json(USER_DB_FILE, user_db)
        await msg.reply_text("User database restored.")


async def proxy_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await admin_guard_reply(update):
        return
    await update.message.reply_text("Proxy control panel", reply_markup=proxy_panel_keyboard())


async def proxy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.message.reply_text("Admin only.")
        return
    action = query.data.split(":", 1)[1]
    if action == "toggle_chk":
        current = chk_uses_proxy()
        proxy_db.setdefault("command_proxy_enabled", {})[CHK_COMMAND_NAME] = not current
        save_proxy_db()
        await query.message.edit_text("Proxy control panel", reply_markup=proxy_panel_keyboard())
        return
    if action == "show":
        proxies = proxy_db.get("proxies", [])
        if not proxies:
            await query.message.reply_text("No proxies saved.")
            return
        lines = [f"{i+1}. {p['raw']}" for i, p in enumerate(proxies[:100])]
        await query.message.reply_text("Saved proxies:\n\n" + "\n".join(lines))
        return
    if action == "status":
        text = (
            f"Total proxies: {len(proxy_db.get('proxies', []))}\n"
            f"/chk proxy enabled: {'Yes' if chk_uses_proxy() else 'No'}\n"
            f"Updated at: {proxy_db.get('updated_at', 'n/a')}"
        )
        await query.message.reply_text(text)
        return
    if action == "add":
        context.user_data["awaiting_proxy_add"] = True
        await query.message.reply_text("Send proxies now, one per line, in host:port:user:pass format.")
        return
    if action == "delete":
        context.user_data["awaiting_proxy_delete"] = True
        await query.message.reply_text("Send the exact proxy line(s) to delete, one per line.")
        return


async def premium_approve_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    _, user_id_str, scope = query.data.split(":")
    target_id = int(user_id_str)
    record = get_user_record(target_id)
    if scope in {"chk", "all"}:
        record["approved_cmds"] = [CHK_COMMAND_NAME]
        record["status"] = "premium"
        record["premium_requested"] = False
        set_user_record(target_id, record)
        await query.message.reply_text(f"Approved {scope} for {target_id}.")
        try:
            await context.bot.send_message(target_id, f"You were approved for {scope}.")
        except Exception:
            logger.exception("Failed sending premium approval to %s", target_id)

# =========================
# TEXT HANDLER FOR ADMIN INPUT FLOWS
# =========================
async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    if update.message.text.startswith("/"):
        return
    if is_banned(update.effective_user.id):
        return

    if context.user_data.get("awaiting_proxy_add") and is_admin(update.effective_user.id):
        added = 0
        for line in update.message.text.splitlines():
            proxy = parse_proxy_line(line)
            if proxy and all(p["raw"] != proxy["raw"] for p in proxy_db.get("proxies", [])):
                proxy_db.setdefault("proxies", []).append(proxy)
                added += 1
        save_proxy_db()
        context.user_data.pop("awaiting_proxy_add", None)
        await update.message.reply_text(f"Added {added} proxy/proxies.")
        return

    if context.user_data.get("awaiting_proxy_delete") and is_admin(update.effective_user.id):
        targets = {line.strip() for line in update.message.text.splitlines() if line.strip()}
        before = len(proxy_db.get("proxies", []))
        proxy_db["proxies"] = [p for p in proxy_db.get("proxies", []) if p["raw"] not in targets]
        removed = before - len(proxy_db.get("proxies", []))
        save_proxy_db()
        context.user_data.pop("awaiting_proxy_delete", None)
        await update.message.reply_text(f"Removed {removed} proxy/proxies.")
        return

# =========================
# SCHEDULED BACKUP PUSH
# =========================
async def auto_send_user_db(context: ContextTypes.DEFAULT_TYPE) -> None:
    if not USER_DB_FILE.exists():
        return
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_document(
                admin_id,
                document=USER_DB_FILE.open("rb"),
                caption="Automatic 48h users.json backup",
            )
        except Exception:
            logger.exception("Failed auto-sending users.json to admin %s", admin_id)

# =========================
# ERROR HANDLER
# =========================
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled exception", exc_info=context.error)

# =========================
# MAIN
# =========================
def build_app() -> Application:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is missing")
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("id", id_cmd))
    app.add_handler(CommandHandler("ping", ping_cmd))
    app.add_handler(CommandHandler("premium", premium_cmd))
    app.add_handler(CommandHandler("chk", chk_cmd))

    # admin
    app.add_handler(CommandHandler("ban", ban_cmd))
    app.add_handler(CommandHandler("unban", unban_cmd))
    app.add_handler(CommandHandler("approve", approve_cmd))
    app.add_handler(CommandHandler("revoke", revoke_cmd))
    app.add_handler(CommandHandler("ram", ram_cmd))
    app.add_handler(CommandHandler("cleanram", cleanram_cmd))
    app.add_handler(CommandHandler("log", log_cmd))
    app.add_handler(CommandHandler("backup", backup_cmd))
    app.add_handler(CommandHandler("restore", restore_cmd))
    app.add_handler(CommandHandler("proxy", proxy_cmd))

    # callbacks
    app.add_handler(CallbackQueryHandler(chk_file_callback, pattern=r"^chkfile:"))
    app.add_handler(CallbackQueryHandler(proxy_callback, pattern=r"^proxy:"))
    app.add_handler(CallbackQueryHandler(premium_approve_callback, pattern=r"^premiumapprove:"))

    # text router for admin proxy add/delete flows
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))

    app.add_error_handler(error_handler)

    if app.job_queue:
        app.job_queue.run_repeating(auto_send_user_db, interval=48 * 60 * 60, first=120)

    return app


def main() -> None:
    app = build_app()
    logger.info("Bot starting. admins=%s", sorted(ADMIN_IDS))
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
