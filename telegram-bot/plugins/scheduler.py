import asyncio
import logging
import datetime
import html
from pyrogram import Client
from config import LOG_CHANNEL
from database.db import get_daily_summary, reset_failed_searches

logger = logging.getLogger(__name__)


async def _send_daily_summary(bot: Client) -> None:
    """Send top-10 failed searches to LOG_CHANNEL and reset the counter."""
    if not LOG_CHANNEL:
        return
    try:
        results = await get_daily_summary(top_n=10)
        if not results:
            await bot.send_message(
                chat_id=LOG_CHANNEL,
                text="\U0001f4ca <b>#DailySummary</b>\n\nNo failed searches in the last 24 hours! \U0001f389",
            )
            return
        lines = ["\U0001f4ca <b>#DailySummary — Top Failed Searches (24h)</b>\n"]
        for idx, doc in enumerate(results, start=1):
            query = html.escape(doc.get("query", "?"))
            count = doc.get("count", 0)
            lines.append(f"{idx}. <code>{query}</code> — <b>{count}x</b>")
        lines.append("\n<i>Add these to your channels to satisfy demand!</i>")
        await bot.send_message(
            chat_id=LOG_CHANNEL,
            text="\n".join(lines),
        )
        await reset_failed_searches()
        logger.info("Daily failed-search summary sent to LOG_CHANNEL")
    except Exception as e:
        logger.error(f"Daily summary error: {e}")


async def _daily_summary_loop(bot: Client) -> None:
    """Run forever, sending the summary once every 24 hours at midnight UTC."""
    while True:
        try:
            now = datetime.datetime.utcnow()
            # Next midnight UTC
            next_midnight = (now + datetime.timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            sleep_seconds = (next_midnight - now).total_seconds()
            logger.info(f"Daily summary scheduled in {sleep_seconds/3600:.1f}h")
            await asyncio.sleep(sleep_seconds)
            await _send_daily_summary(bot)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Daily summary loop error: {e}")
            await asyncio.sleep(60)


async def start_daily_summary_scheduler(bot: Client) -> None:
    """Start the background scheduler task (call once on bot startup)."""
    asyncio.get_event_loop().create_task(_daily_summary_loop(bot))
    logger.info("Daily summary scheduler started")