"""Auto-delete worker — runs as an asyncio task inside the main bot process.

Previously this was a subprocess with its own Pyrogram client (same bot token),
which caused AUTH_KEY_DUPLICATED and FloodWait on every restart.
Now it reuses the already-connected bot client passed from bot.py.
"""
import asyncio
import logging
from time import time

from pyrogram.errors import FloodWait

logger = logging.getLogger(__name__)


async def run_autodelete_loop(bot) -> None:
    """Continuously delete expired messages using the main bot client.

    Call this as an asyncio.create_task() from bot.py — no subprocess needed.
    """
    from database import get_all_dlt_data, delete_all_dlt_data

    logger.info("✅ Auto-delete loop started (in-process)")
    while True:
        try:
            _time = int(time())
            all_data = await get_all_dlt_data(_time)
            for data in all_data:
                try:
                    await bot.delete_messages(
                        chat_id=data["chat_id"],
                        message_ids=data["message_id"],
                    )
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                except Exception as e:
                    logger.debug("Delete error: %s — %s", data, e)
            if all_data:
                await delete_all_dlt_data(_time)
        except asyncio.CancelledError:
            logger.info("Auto-delete loop cancelled")
            return
        except Exception as e:
            logger.warning("Auto-delete loop error: %s", e)
        await asyncio.sleep(5)
