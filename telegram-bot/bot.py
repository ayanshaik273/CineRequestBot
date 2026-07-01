import asyncio
import logging
import os
import signal
import sys

from pyrogram import Client
from pyrogram.errors import FloodWait
from config import API_ID, API_HASH, BOT_TOKEN, SESSION, LOG_CHANNEL, RESULTS_CHANNEL
from database import create_indexes
from plugins.scheduler import start_daily_summary_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def _is_auth_key_duplicated(exc: Exception) -> bool:
    """Check if an exception is AUTH_KEY_DUPLICATED without relying on a specific
    Pyrogram exception class — the class name varies across Pyrogram versions."""
    return "AUTH_KEY_DUPLICATED" in str(exc)


def _session_name():
    """Use in-memory session on Railway (ephemeral filesystem)."""
    sessions_dir = os.environ.get("SESSIONS_DIR", "sessions")
    try:
        os.makedirs(sessions_dir, exist_ok=True)
        test = os.path.join(sessions_dir, ".write_test")
        open(test, "w").close()
        os.remove(test)
        return os.path.join(sessions_dir, "bot")
    except Exception:
        return ":memory:"


class Bot(Client):
    def __init__(self):
        name = _session_name()
        kwargs = dict(
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            plugins={"root": "plugins"},
            sleep_threshold=60,
        )
        if name == ":memory:":
            kwargs["in_memory"] = True
            name = "bot"
        super().__init__(name=name, **kwargs)

    async def start(self):
        await super().start()
        await create_indexes()

        if SESSION:
            await _start_user_session()
        else:
            logger.warning("⚠️  SESSION not set — search will not work. Add SESSION env var.")

        if not RESULTS_CHANNEL:
            logger.warning("⚠️  RESULTS_CHANNEL not set — add it to env vars.")
        else:
            await _warmup_results_channel(self)

        _start_autodelete_worker(self)
        await start_daily_summary_scheduler(self)

        from pyrogram.types import BotCommand

        await self.set_bot_commands([
            BotCommand("start",       "Check if I'm alive"),
            BotCommand("id",          "Get channel/group ID"),
            BotCommand("verify",      "Request group verification"),
            BotCommand("connect",     "Connect a channel for searching"),
            BotCommand("disconnect",  "Disconnect a channel"),
            BotCommand("connections", "List connected channels"),
            BotCommand("fsub",        "Set force-subscribe channel"),
            BotCommand("nofsub",      "Remove force-subscribe"),
            BotCommand("autodelete",  "Set result auto-delete timer"),
            BotCommand("addsource",   "Add/remove/list source channels"),
            BotCommand("ping",        "Check bot speed"),
            BotCommand("stats",       "Bot statistics (owner only)"),
            BotCommand("setbackup",   "Update backup channel link (owner only)"),
            BotCommand("help",        "Show all commands"),
        ])

        me = await self.get_me()
        logger.info("✅ CineRequestBot started as @%s (%d)", me.username, me.id)

        if LOG_CHANNEL:
            try:
                await self.send_message(
                    LOG_CHANNEL,
                    f"✅ <b>CineRequestBot Started</b>\n\n"
                    f"🤖 @{me.username} (<code>{me.id}</code>)\n"
                    f"📺 Results channel: <code>{RESULTS_CHANNEL or 'NOT SET'}</code>\n"
                    f"🔑 Session: {'✅ configured' if SESSION else '❌ missing'}",
                )
            except Exception:
                pass

    async def stop(self, *args):
        try:
            from client import User
            if User is not None and User.is_connected:
                await User.stop()
        except Exception:
            pass
        await super().stop()
        logger.info("Bot stopped")


async def _warmup_results_channel(bot):
    """Resolve RESULTS_CHANNEL peer on cold start.

    If RESULTS_CHANNEL is a @username string, get_chat() resolves it instantly.
    If it is a numeric ID (int), try raw MTProto GetFullChannel(access_hash=0)
    which Telegram accepts when the bot is admin, then fall back to get_chat().
    """
    try:
        if isinstance(RESULTS_CHANNEL, str):
            # Public channel username — always resolvable without access_hash
            chat = await bot.get_chat(RESULTS_CHANNEL)
            logger.info("✅ Results channel resolved: %s", chat.title)
        else:
            from pyrogram.raw.functions.channels import GetFullChannel
            from pyrogram.raw.types import InputChannel
            bare_id = abs(RESULTS_CHANNEL) - 1_000_000_000_000
            try:
                result = await bot.invoke(
                    GetFullChannel(channel=InputChannel(channel_id=bare_id, access_hash=0))
                )
                title = result.chats[0].title if result.chats else str(RESULTS_CHANNEL)
                logger.info("✅ Results channel resolved via raw API: %s", title)
            except Exception:
                chat = await bot.get_chat(RESULTS_CHANNEL)
                logger.info("✅ Results channel resolved via get_chat: %s", chat.title)
    except Exception as e:
        logger.warning(
            "⚠️  Could not resolve RESULTS_CHANNEL %s: %s — "
            "set RESULTS_CHANNEL to the channel @username or ensure bot is admin.",
            RESULTS_CHANNEL, e,
        )


async def _start_user_session():
    """Start the user session, retrying through FloodWait or AUTH_KEY_DUPLICATED.

    AUTH_KEY_DUPLICATED happens on Railway when a new deployment starts before the
    previous instance has fully disconnected. Waiting 35 s gives the old process time
    to exit and Telegram to release the auth key.
    """
    try:
        from client import User
        if User is None:
            logger.error("User is None — SESSION env var is set but client failed to init")
            return
        if not User.is_connected:
            while True:
                try:
                    await User.start()
                    break
                except Exception as e:
                    if _is_auth_key_duplicated(e):
                        wait = 35
                        logger.warning(
                            "⚠️  AUTH_KEY_DUPLICATED on user session — "
                            "old Railway instance still connected. "
                            "Waiting %ds for it to disconnect...",
                            wait,
                        )
                        try:
                            await User.stop()
                        except Exception:
                            pass
                        await asyncio.sleep(wait)
                    elif isinstance(e, FloodWait):
                        wait = e.value + 5
                        logger.warning(
                            "⚠️  FloodWait on user session start — waiting %ds (~%.0f min)...",
                            wait, wait / 60,
                        )
                        await asyncio.sleep(wait)
                    else:
                        raise
        me = await User.get_me()
        logger.info("✅ User session active: @%s (id=%d)", me.username or me.first_name, me.id)
        count = 0
        async for _ in User.get_dialogs():
            count += 1
            if count >= 200:
                break
        logger.info("✅ Peer cache warmed (%d dialogs loaded)", count)
    except Exception as e:
        logger.warning("⚠️  User session failed to start: %s", e)


async def _session_watchdog():
    while True:
        await asyncio.sleep(300)
        if not SESSION:
            continue
        try:
            from client import User
            if User is None:
                continue
            if not User.is_connected:
                logger.warning("Watchdog: User session disconnected — reconnecting")
                await _start_user_session()
            else:
                await User.get_me()
        except FloodWait as e:
            wait = e.value + 5
            logger.warning("Watchdog FloodWait — sleeping %ds before retry", wait)
            await asyncio.sleep(wait)
        except Exception as e:
            if _is_auth_key_duplicated(e):
                logger.warning("Watchdog: AUTH_KEY_DUPLICATED — waiting 35s before reconnect")
                await asyncio.sleep(35)
            else:
                logger.warning("Watchdog error: %s — attempting reconnect", e)
            try:
                await _start_user_session()
            except Exception:
                pass


def _start_autodelete_worker(bot):
    from utils.delete import run_autodelete_loop
    asyncio.create_task(run_autodelete_loop(bot))
    logger.info("✅ Auto-delete loop started (in-process)")


async def _start_bot_with_flood_retry() -> "Bot":
    """Start the bot, sleeping through any FloodWait on auth instead of crashing."""
    while True:
        bot = Bot()
        try:
            await bot.start()
            return bot
        except FloodWait as e:
            wait = e.value + 10
            logger.warning(
                "⚠️  Telegram FloodWait on bot authorization — waiting %d seconds (~%.0f min) before retry...",
                wait, wait / 60,
            )
            try:
                await bot.stop()
            except Exception:
                pass
            await asyncio.sleep(wait)
        except Exception:
            try:
                await bot.stop()
            except Exception:
                pass
            raise


async def main():
    from health import start_health_server
    start_health_server()

    bot = await _start_bot_with_flood_retry()

    watchdog = asyncio.create_task(_session_watchdog())
    stop_event = asyncio.Event()

    def _handle_signal():
        logger.info("Shutdown signal received")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _handle_signal)
        except NotImplementedError:
            pass

    logger.info("Bot is running. SIGTERM/Ctrl+C to stop.")
    await stop_event.wait()

    watchdog.cancel()
    try:
        await watchdog
    except asyncio.CancelledError:
        pass
    await bot.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Stopped by user")
