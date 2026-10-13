import asyncio
import html
import logging
import os
import re
import sqlite3
from dataclasses import dataclass

import httpx
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

from config import COMPANIES, INTERN_KEYWORDS, ROLE_KEYWORDS

load_dotenv()
TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHECK_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", "60"))
LOCATION_FILTER = [x.strip().lower() for x in os.getenv("LOCATION_FILTER", "").split(",") if x.strip()]
FIRST_RUN_LIMIT = int(os.getenv("FIRST_RUN_LIMIT", "25"))
DB_PATH = os.getenv("DB_PATH", "jobs.db")

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
log = logging.getLogger("internship-bot")
logging.getLogger("httpx").setLevel(logging.WARNING)


def _compile(words):
    return re.compile(r"(?<![a-z])(" + "|".join(re.escape(w) for w in words) + r")(?![a-z])", re.I)


INTERN_RE = _compile(INTERN_KEYWORDS)
ROLE_RE = _compile(ROLE_KEYWORDS)


@dataclass
class Job:
    uid: str
    company: str
    title: str
    location: str
    url: str


# ---------------------------------------------------------------- database
db = sqlite3.connect(DB_PATH)
db.executescript(
    """
    CREATE TABLE IF NOT EXISTS jobs(
        uid TEXT PRIMARY KEY, company TEXT, title TEXT, location TEXT, url TEXT,
        found_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS subscribers(chat_id INTEGER PRIMARY KEY);
    """
)
db.commit()


def is_seen(uid):
    return db.execute("SELECT 1 FROM jobs WHERE uid=?", (uid,)).fetchone() is not None


def save_job(j: Job):
    db.execute(
        "INSERT OR IGNORE INTO jobs(uid,company,title,location,url) VALUES(?,?,?,?,?)",
        (j.uid, j.company, j.title, j.location, j.url),
    )
    db.commit()


def subscribers():
    return [r[0] for r in db.execute("SELECT chat_id FROM subscribers")]


# ---------------------------------------------------------------- fetchers
async def fetch_greenhouse(client, slug, name):
    r = await client.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs")
    r.raise_for_status()
    return [
        Job(f"gh:{slug}:{j['id']}", name, j["title"], (j.get("location") or {}).get("name", ""), j["absolute_url"])
        for j in r.json().get("jobs", [])
    ]


async def fetch_lever(client, slug, name):
    r = await client.get(f"https://api.lever.co/v0/postings/{slug}", params={"mode": "json"})
    r.raise_for_status()
    return [
        Job(f"lv:{slug}:{j['id']}", name, j["text"], (j.get("categories") or {}).get("location") or "", j["hostedUrl"])
        for j in r.json()
    ]


async def fetch_ashby(client, slug, name):
    r = await client.get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
    r.raise_for_status()
    return [
        Job(f"ab:{slug}:{j['id']}", name, j["title"], j.get("location") or "", j.get("jobUrl") or j.get("applyUrl", ""))
        for j in r.json().get("jobs", [])
        if j.get("isListed", True)
    ]


FETCHERS = {"greenhouse": fetch_greenhouse, "lever": fetch_lever, "ashby": fetch_ashby}


async def safe_fetch(client, sem, ats, slug, name):
    async with sem:
        try:
            return await FETCHERS[ats](client, slug, name)
        except Exception as e:
            log.warning("Skipping %s (%s/%s): %s", name, ats, slug, e)
            return []


def matches(j: Job) -> bool:
    if not j.url or not INTERN_RE.search(j.title) or not ROLE_RE.search(j.title):
        return False
    if LOCATION_FILTER:
        loc = j.location.lower()
        return any(k in loc for k in LOCATION_FILTER)
    return True


async def scan() -> list[Job]:
    sem = asyncio.Semaphore(8)
    async with httpx.AsyncClient(timeout=25, follow_redirects=True, headers={"User-Agent": "internship-alert-bot/1.0"}) as client:
        batches = await asyncio.gather(*(safe_fetch(client, sem, *c) for c in COMPANIES))
    return [j for batch in batches for j in batch if matches(j)]


# ---------------------------------------------------------------- telegram
async def send_job(bot, chat_id, j: Job, prefix="🆕"):
    text = (
        f"{prefix} <b>{html.escape(j.title)}</b>\n"
        f"🏢 {html.escape(j.company)}\n"
        f"📍 {html.escape(j.location or 'Not specified')}"
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 Apply Now", url=j.url)]])
    await bot.send_message(chat_id, text, parse_mode=ParseMode.HTML, reply_markup=kb, disable_web_page_preview=True)


async def run_check(app: Application) -> int:
    first_run = db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0
    found = await scan()
    new = [j for j in found if not is_seen(j.uid)]
    to_send = new[:FIRST_RUN_LIMIT] if first_run else new
    for j in new:
        save_job(j)
    for chat_id in subscribers():
        for j in to_send:
            try:
                await send_job(app.bot, chat_id, j)
                await asyncio.sleep(0.4)  # stay under Telegram rate limits
            except Exception as e:
                log.warning("Send failed for %s: %s", chat_id, e)
    log.info("Scan done: %d matching, %d new", len(found), len(new))
    return len(new)


async def scheduled_check(context: ContextTypes.DEFAULT_TYPE):
    await run_check(context.application)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db.execute("INSERT OR IGNORE INTO subscribers(chat_id) VALUES(?)", (update.effective_chat.id,))
    db.commit()
    await update.message.reply_text(
        "✅ Subscribed! I scan official company career boards for Data Science / AI / ML "
        f"internships every {CHECK_MINUTES} min and send new ones with an Apply button.\n\n"
        "/check – scan now\n/latest – last 10 found\n/status – bot info\n/stop – unsubscribe"
    )


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db.execute("DELETE FROM subscribers WHERE chat_id=?", (update.effective_chat.id,))
    db.commit()
    await update.message.reply_text("Unsubscribed. Send /start to resume.")


async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔎 Scanning career boards…")
    n = await run_check(context.application)
    if n == 0:
        await update.message.reply_text("No new internships since the last scan.")


async def latest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = db.execute("SELECT uid,company,title,location,url FROM jobs ORDER BY found_at DESC, rowid DESC LIMIT 10").fetchall()
    if not rows:
        await update.message.reply_text("Nothing stored yet. Try /check.")
        return
    for r in rows:
        await send_job(context.bot, update.effective_chat.id, Job(*r), prefix="📌")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total = db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    await update.message.reply_text(
        f"Companies tracked: {len(COMPANIES)}\nInterval: {CHECK_MINUTES} min\n"
        f"Location filter: {', '.join(LOCATION_FILTER) or 'none (worldwide)'}\nListings stored: {total}"
    )


def main():
    app = Application.builder().token(TOKEN).build()
    for name, fn in [("start", start), ("stop", stop), ("check", check), ("latest", latest), ("status", status)]:
        app.add_handler(CommandHandler(name, fn))
    app.job_queue.run_repeating(scheduled_check, interval=CHECK_MINUTES * 60, first=15)
    log.info("Bot running. Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
