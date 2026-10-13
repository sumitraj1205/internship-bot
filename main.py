"""
Internship Alert Bot (runs once per GitHub Actions schedule).

Scans official career boards (Greenhouse / Lever / Ashby) of real companies for
Data Science / AI / ML internships and sends new ones to your Telegram with an
"Apply Now" button.
"""
import html
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

# ======================= SETTINGS YOU CAN EDIT =======================

# (platform, company slug, display name)
# Slug = last part of the company's careers link, e.g. jobs.lever.co/palantir -> "palantir"
# A wrong slug is simply skipped (shown as "Skipping" in the run log).
COMPANIES = [
    # Greenhouse  (boards.greenhouse.io/<slug>)
    ("greenhouse", "anthropic", "Anthropic"),
    ("greenhouse", "databricks", "Databricks"),
    ("greenhouse", "scaleai", "Scale AI"),
    ("greenhouse", "stripe", "Stripe"),
    ("greenhouse", "airbnb", "Airbnb"),
    ("greenhouse", "cloudflare", "Cloudflare"),
    ("greenhouse", "datadog", "Datadog"),
    ("greenhouse", "mongodb", "MongoDB"),
    ("greenhouse", "gitlab", "GitLab"),
    ("greenhouse", "figma", "Figma"),
    ("greenhouse", "coinbase", "Coinbase"),
    ("greenhouse", "pinterest", "Pinterest"),
    ("greenhouse", "twilio", "Twilio"),
    ("greenhouse", "razorpaysoftwareprivatelimited", "Razorpay"),
    ("greenhouse", "groww", "Groww"),
    # Lever  (jobs.lever.co/<slug>)
    ("lever", "palantir", "Palantir"),
    ("lever", "spotify", "Spotify"),
    ("lever", "meesho", "Meesho"),
    ("lever", "cred", "CRED"),
    # Ashby  (jobs.ashbyhq.com/<slug>)
    ("ashby", "openai", "OpenAI"),
    ("ashby", "cohere", "Cohere"),
    ("ashby", "notion", "Notion"),
    ("ashby", "ramp", "Ramp"),
    ("ashby", "snowflake", "Snowflake"),
]

# The job title must contain one INTERN word AND one ROLE word.
INTERN_KEYWORDS = ["intern", "interns", "internship", "trainee", "apprentice", "co-op", "coop"]
ROLE_KEYWORDS = [
    "data science", "data scientist", "machine learning", "ml", "ai",
    "artificial intelligence", "llm", "nlp", "computer vision", "deep learning",
    "generative", "genai", "applied scientist", "research engineer",
    "research scientist", "data analyst", "data engineer",
]

# Only jobs whose location contains one of these words are sent.
# Make it an empty list [] to receive jobs from ALL locations worldwide.
LOCATION_FILTER = [
    "india", "remote", "anywhere", "bengaluru", "bangalore", "hyderabad", "pune",
    "mumbai", "delhi", "gurgaon", "gurugram", "noida", "chennai", "kolkata",
]

# On the very first run, send at most this many existing openings (rest saved silently).
FIRST_RUN_LIMIT = 25

# =====================================================================

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
STATE_FILE = Path("seen.json")  # remembers which jobs were already sent


def _compile(words):
    return re.compile(r"(?<![a-z])(" + "|".join(re.escape(w) for w in words) + r")(?![a-z])", re.I)


INTERN_RE = _compile(INTERN_KEYWORDS)
ROLE_RE = _compile(ROLE_KEYWORDS)


# ------------------------------ fetchers ------------------------------
def fetch_greenhouse(client, slug, name):
    r = client.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs")
    r.raise_for_status()
    return [
        {"uid": f"gh:{slug}:{j['id']}", "company": name, "title": j["title"],
         "location": (j.get("location") or {}).get("name", ""), "url": j["absolute_url"]}
        for j in r.json().get("jobs", [])
    ]


def fetch_lever(client, slug, name):
    r = client.get(f"https://api.lever.co/v0/postings/{slug}", params={"mode": "json"})
    r.raise_for_status()
    return [
        {"uid": f"lv:{slug}:{j['id']}", "company": name, "title": j["text"],
         "location": (j.get("categories") or {}).get("location") or "", "url": j["hostedUrl"]}
        for j in r.json()
    ]


def fetch_ashby(client, slug, name):
    r = client.get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
    r.raise_for_status()
    return [
        {"uid": f"ab:{slug}:{j['id']}", "company": name, "title": j["title"],
         "location": j.get("location") or "", "url": j.get("jobUrl") or j.get("applyUrl") or ""}
        for j in r.json().get("jobs", [])
        if j.get("isListed", True)
    ]


FETCHERS = {"greenhouse": fetch_greenhouse, "lever": fetch_lever, "ashby": fetch_ashby}


def safe_fetch(client, company):
    ats, slug, name = company
    try:
        return FETCHERS[ats](client, slug, name)
    except Exception as e:
        print(f"Skipping {name} ({ats}/{slug}): {e}")
        return []


def matches(job):
    if not job["url"].startswith("http"):
        return False
    if not INTERN_RE.search(job["title"]) or not ROLE_RE.search(job["title"]):
        return False
    if LOCATION_FILTER:
        loc = job["location"].lower()
        return any(k in loc for k in LOCATION_FILTER)
    return True


# ------------------------------ telegram ------------------------------
def send(client, text, apply_url=None):
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if apply_url:
        payload["reply_markup"] = {"inline_keyboard": [[{"text": "🚀 Apply Now", "url": apply_url}]]}
    for _ in range(3):
        r = client.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json=payload)
        if r.status_code == 429:  # Telegram says "slow down"
            time.sleep(r.json().get("parameters", {}).get("retry_after", 5) + 1)
            continue
        if r.status_code != 200:
            raise RuntimeError(f"Telegram error {r.status_code}: {r.text}")
        return
    raise RuntimeError("Telegram rate limit, will retry on next run")


def job_message(job):
    return (
        f"🆕 <b>{html.escape(job['title'])}</b>\n"
        f"🏢 {html.escape(job['company'])}\n"
        f"📍 {html.escape(job['location'] or 'Not specified')}"
    )


# -------------------------------- main --------------------------------
def main():
    if not BOT_TOKEN or not CHAT_ID:
        sys.exit("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID. Add them in GitHub -> Settings -> Secrets.")

    first_run = not STATE_FILE.exists()
    seen = set() if first_run else set(json.loads(STATE_FILE.read_text()))
    manual = os.getenv("GITHUB_EVENT_NAME") == "workflow_dispatch"

    with httpx.Client(timeout=25, follow_redirects=True, headers={"User-Agent": "internship-alert-bot/1.0"}) as client:
        with ThreadPoolExecutor(8) as pool:
            batches = list(pool.map(lambda c: safe_fetch(client, c), COMPANIES))
        found = [j for b in batches for j in b if matches(j)]
        new = [j for j in found if j["uid"] not in seen]
        to_send = new[:FIRST_RUN_LIMIT] if first_run else new
        silent = new[len(to_send):]
        print(f"matching={len(found)} new={len(new)} sending={len(to_send)}")

        if first_run:
            send(client, "✅ <b>Setup complete!</b> I check official company career pages every hour "
                         "and will message you new Data Science / AI internships here.")
        try:
            for j in to_send:
                send(client, job_message(j), j["url"])
                seen.add(j["uid"])
                time.sleep(0.5)
            for j in silent:
                seen.add(j["uid"])
            if manual or first_run:
                send(client, f"ℹ️ Scan finished: {len(found)} matching openings right now, {len(new)} new.")
        finally:
            STATE_FILE.write_text(json.dumps(sorted(seen), indent=0))


if __name__ == "__main__":
    main()
