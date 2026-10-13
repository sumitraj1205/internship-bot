"""Runs ONE scan and exits. Used by GitHub Actions (free scheduler)."""
import asyncio
import os

from telegram import Bot

import bot as core


async def main():
    chat_id = int(os.environ["TELEGRAM_CHAT_ID"])
    first_run = core.db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0
    found = await core.scan()
    new = [j for j in found if not core.is_seen(j.uid)]
    to_send = new[: core.FIRST_RUN_LIMIT] if first_run else new
    for j in new:
        core.save_job(j)
    async with Bot(core.TOKEN) as tg:
        for j in to_send:
            await core.send_job(tg, chat_id, j)
            await asyncio.sleep(0.4)
    print(f"matching={len(found)} new={len(new)} sent={len(to_send)}")


asyncio.run(main())
