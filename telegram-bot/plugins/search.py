import asyncio
import html
import logging
from time import time

from pyrogram import Client, filters
from pyrogram.errors import FloodWait, ChannelInvalid, ChannelPrivate
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import RESULTS_CHANNEL, SEARCH_REPLY_TTL, SESSION
from database.db import get_group, force_sub, save_dlt_message
from utils.spell import google_spell_check
from utils.imdb import search_imdb

logger = logging.getLogger(__name__)

# Telegram hard limit for text messages
_TG_LIMIT = 4096


# ── helpers ───────────────────────────────────────────────────────────────────

async def _results_link(bot, channel_id: int, message_id: int) -> str:
    """Build a shareable link to a message in the results channel.
    Uses the public username link (t.me/username/id) for public channels,
    and the private link (t.me/c/id/msg) for private channels."""
    try:
        chat = await bot.get_chat(channel_id)
        if getattr(chat, "username", None):
            return f"https://t.me/{chat.username}/{message_id}"
    except Exception:
        pass
    cid = str(channel_id)
    if cid.startswith("-100"):
        cid = cid[4:]
    return f"https://t.me/c/{cid}/{message_id}"


async def _schedule_delete(bot, message, ttl: int):
    try:
        await save_dlt_message(message, int(time()) + ttl)
    except Exception as e:
        logger.debug("save_dlt_message: %s", e)


async def _search_channels(user_client, channels: list, query: str) -> list:
    """Search connected channels via user session. Returns list of message texts.

    We trust Telegram's search_messages() to filter by relevance — adding a
    secondary substring check was discarding valid fuzzy/partial matches.
    """
    results = []
    for ch_id in channels:
        try:
            async for msg in user_client.search_messages(ch_id, query=query, limit=50):
                text = (msg.text or msg.caption or "").strip()
                if text:
                    results.append(text)
                    if len(results) >= 30:
                        return results
        except (ChannelInvalid, ChannelPrivate):
            logger.debug("Channel %s invalid/private — skipping", ch_id)
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except Exception as e:
            logger.debug("Search error ch=%s: %s", ch_id, e)
    return results


def _build_results_message(query: str, results: list, ttl_secs: int,
                            page: int = 1, total_pages: int = 1) -> str:
    """Build the results message, guaranteed to stay within Telegram's 4096-char limit."""
    mins = max(1, ttl_secs // 60)
    footer = (
        "\n" + "─" * 32 + "\n"
        + f"⏳ <b>Results auto-delete in {mins} min{'s' if mins != 1 else ''}</b>"
    )
    header = (
        f"🔍 <b>Search:</b> {html.escape(query)}\n"
        f"📄 <b>Page:</b> {page}/{total_pages}\n"
        f"📊 <b>Total Results:</b> {len(results)}\n\n"
    )

    # Budget: total limit minus header and footer
    budget = _TG_LIMIT - len(header) - len(footer) - 20  # 20 chars safety margin

    body_lines = []
    used = 0
    shown = 0
    for i, text in enumerate(results, 1):
        # Truncate individual result to 250 chars to keep things readable
        snippet = html.escape(text[:250])
        if len(text) > 250:
            snippet += "…"
        entry = f"<b>{i}.</b> {snippet}\n\n"
        if used + len(entry) > budget:
            # No more room — note how many were cut
            remaining = len(results) - shown
            if remaining > 0:
                body_lines.append(
                    f"<i>… and {remaining} more result{'s' if remaining != 1 else ''} "
                    f"(use a more specific query to narrow down)</i>"
                )
            break
        body_lines.append(entry)
        used += len(entry)
        shown += 1

    return header + "".join(body_lines) + footer


# ── main search handler ────────────────────────────────────────────────────────

@Client.on_message(
    filters.text
    & filters.group
    & filters.incoming
    & ~filters.via_bot
    & ~filters.bot
    & ~filters.command([
        "start", "help", "about", "id", "verify", "connect", "disconnect",
        "connections", "fsub", "nofsub", "autodelete", "broadcast",
        "broadcast_groups", "ping", "stats",
    ])
)
async def search(bot, message):
    if not message.text or not message.text.strip():
        return

    query = message.text.strip()
    if len(query) < 2 or len(query) > 100:
        return

    # ── Load group config ─────────────────────────────────────────────────
    group = await get_group(message.chat.id)
    if not group or not group.get("verified"):
        return

    # ── Force subscribe check ─────────────────────────────────────────────
    if not await force_sub(bot, message):
        return

    channels = group.get("channels", [])
    if not channels:
        m = await message.reply(
            "⚠️ <b>No channels connected yet.</b>\n"
            "Ask the group admin to use /connect to link channels first."
        )
        await _schedule_delete(bot, m, 60)
        return

    # ── Pre-flight checks ─────────────────────────────────────────────────
    if not RESULTS_CHANNEL:
        m = await message.reply(
            "⚠️ <b>Results channel not configured.</b> Contact the bot owner."
        )
        await _schedule_delete(bot, m, 60)
        return

    if not SESSION:
        m = await message.reply(
            "⚠️ <b>Search session not configured.</b> Contact the bot owner."
        )
        await _schedule_delete(bot, m, 60)
        return

    # ── Connect user session ──────────────────────────────────────────────
    try:
        from client import User
        if User is None:
            raise RuntimeError("User session is not configured (SESSION env var missing)")
        if not User.is_connected:
            await User.start()
    except Exception as e:
        logger.warning("User session unavailable: %s", e)
        m = await message.reply(
            "⚠️ <b>Search is temporarily unavailable.</b> Try again in a moment."
        )
        await _schedule_delete(bot, m, 30)
        return

    # ── Searching indicator ───────────────────────────────────────────────
    wait_msg = await message.reply("🔍 <i>Searching...</i>")

    results = await _search_channels(User, channels, query)
    ttl = group.get("auto_delete", SEARCH_REPLY_TTL)

    # ── No results — try spell correction ─────────────────────────────────
    if not results:
        corrected = await google_spell_check(query)
        if corrected and corrected.lower() != query.lower():
            results = await _search_channels(User, channels, corrected)
            if results:
                query = corrected

    # ── Still no results — show fallback ─────────────────────────────────
    if not results:
        imdb_hits = await search_imdb(query)
        imdb_text = ""
        if imdb_hits:
            imdb_text = "\n\n<b>Did you mean:</b>\n"
            imdb_text += "\n".join(
                f"• {html.escape(h['title'])}" for h in imdb_hits[:5]
            )
        await wait_msg.edit(
            f"❌ <b>No results found for:</b> <i>{html.escape(query)}</i>"
            f"{imdb_text}\n\n<b>Please request the group admin 👇</b>"
        )
        await _schedule_delete(bot, wait_msg, ttl)
        return

    # ── Send results to RESULTS_CHANNEL ──────────────────────────────────
    results_text = _build_results_message(query, results, ttl_secs=ttl)

    # Ensure the results channel peer is cached before sending.
    # get_chat(numeric_id) silently fails on in-memory sessions because the
    # access_hash is not stored — fall back to get_dialogs() which always works.
    try:
        await bot.get_chat(RESULTS_CHANNEL)
    except Exception:
        try:
            async for dialog in bot.get_dialogs():
                if dialog.chat.id == RESULTS_CHANNEL:
                    break
        except Exception as e:
            logger.warning("Could not pre-resolve RESULTS_CHANNEL peer: %s", e)

    try:
        sent = await bot.send_message(
            chat_id=RESULTS_CHANNEL,
            text=results_text,
            disable_web_page_preview=True,
        )
    except Exception as e:
        logger.error("Failed to send to RESULTS_CHANNEL %s: %s", RESULTS_CHANNEL, e)
        await wait_msg.edit(
            f"❌ <b>Failed to post results.</b>\n"
            f"<code>{type(e).__name__}: {html.escape(str(e))}</code>\n\n"
            f"ℹ️ Make sure the bot is admin in the results channel with <b>Post Messages</b> permission, "
            f"and that <code>RESULTS_CHANNEL={RESULTS_CHANNEL}</code> is the correct channel ID."
        )
        return

    await _schedule_delete(bot, sent, ttl)

    # ── Reply in group with button ────────────────────────────────────────
    result_url = await _results_link(bot, RESULTS_CHANNEL, sent.id)
    mins_label = max(1, ttl // 60)

    group_reply = (
        f"✅ <b>Found {len(results)} result{'s' if len(results) != 1 else ''} in <a href=\"{result_url}\">Channel</a>.</b>\n"
        f"Page 1/1\n"
        f"<i>(Results auto-delete in {mins_label} min{'s' if mins_label != 1 else ''})</i>"
    )
    reply_kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🎬 Click here to Get movie/Series", url=result_url),
    ]])

    await wait_msg.edit(group_reply, reply_markup=reply_kb)
    await _schedule_delete(bot, wait_msg, ttl)
