import asyncio
import logging
import sys
import os
from time import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_all_dlt_data, delete_all_dlt_data
from config import API_ID, API_HASH, BOT_TOKEN
from pyrogram import Client
from pyrogram.errors import FloodWait

logger = logging.getLogger(__name__)


async def run_check_up():
    while True:
        bot = None
        try:
            bot = Client(
                name="auto-delete",
                api_id=API_ID,
                api_hash=API_HASH,
                bot_token=BOT_TOKEN,
                in_memory=True,
            )
            await bot.start()
            logger.info("Auto-delete worker connected")

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
                            logger.debug(f"Delete error: {data} ��� {e}")
                    await delete_all_dlt_data(_time)
                except Exception as e:
                    logger.warning(f"Auto-delete loop error: {e}")
                await asyncio.sleep(5)

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Auto-delete worker crashed: {e} — restarting in 10s")
        finally:
            if bot:
                try:
                    await bot.stop()
                except Exception:
                    pass
        await asyncio.sleep(10)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_check_up())
