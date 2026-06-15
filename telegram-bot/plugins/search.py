import asyncio
import html
import logging
import uuid
from time import time

from pyrogram import Client, filters
from pyrogram.errors import FloodWait, ChannelInvalid, ChannelPrivate, PeerIdInvalid

from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import RESULTS_CHANNEL, SEARCH_REPLY_TTL, SESSION
from database.db import get_group, force_sub, save_dlt_message
from utils.spell import google_spell_check
from utils.imdb import search_imdb

logger = logging.getLogger(__name__)

_TG_LIMIT = 4096
_RESULTS_PER_PAGE = 4   # results per page / per RESULTS_CHANNEL message
_SESSION_TTL = 3600     # page sessions expire after 1 hour

# In-memory page sessions: session_id → session dict
_page_sessions: dict = {}

# Lock: prevents concurrent User.start() calls that cause AUTH_KEY_DUPLICATED
_user_start_lock = asyncio.Lock()


def _prune_sessions():
    now = time()
    expired = [k for k, v in _page_sessions.items() if now > v.get("ttl", 0)]
    for k in expired:
        _page_sessions.pop(k, None)


# ── helpers ────────────────────────────────────────────────────────────────────

async def _results_link(bot, channel_id: int, message_id: int) -> str:
    """Build a shareable t.me link to a message in the results channel."""
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

    We trust Telegram's search_messages() to filter by relevance — a secondary
    substring check was previously discarding valid fuzzy/partial matches.
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


def _build_page_message(query: str, page_results: list, total: int,
                         page: int, total_pages: int,
                         offset: int, ttl_secs: int) -> str:
    """Build the RESULTS_CHANNEL message for one page of results."""
    mins = max(1, ttl_secs // 60)
    header = (
        f"🔍 <b>Search:</b> {html.escape(query)}\n"
        f"📄 <b>Page {page}/{total_pages}</b>  ·  "
        f"<b>{total} result{'s' if total != 1 else ''} total</b>\n\n"
    )
    footer = (
        "\n" + "─" * 32 + "\n"
        f"⏳ <i>Auto-deletes in {mins} min{'s' if mins != 1 else ''}</i>"
    )
    budget = _TG_LIMIT - len(header) - len(footer) - 20
    body_lines = []
    used = 0
    for i, text in enumerate(page_results, offset + 1):
        snippet = html.escape(text[:300])
        if len(text) > 300:
            snippet += "…"
        entry = f"<b>{i}.</b> {snippet}\n\n"
        if used + len(entry) > budget:
            break
        body_lines.append(entry)
        used += len(entry)
    return header + "".join(body_lines) + footer


def _page_keyboard(session_id: str, page: int, total_pages: int,
                   current_url: str) -> InlineKeyboardMarkup:
    """Build the pagination keyboard matching the screenshot layout.

    Row 1: page number buttons (up to 4 per row, sliding window)
    Row 2: ⬅️ Prev / Next ➡️  (only when applicable)
    Row 3: 🎬 Click here to Get movie/Series  (always)
    """
    rows = []

    if total_pages > 1:
        # Page buttons — show at most 4 per row, sliding window centred on `page`
        half = 2
        start = max(1, min(page - half, total_pages - 3))
        end = min(total_pages, start + 3)
        start = max(1, end - 3)  # re-anchor in case end hit the wall

        pg_row = []
        for p in range(start, end + 1):
            label = f"• Pg {p} •" if p == page else f"Pg {p}"
            pg_row.append(
                InlineKeyboardButton(label, callback_data=f"pg_{session_id}_{p}")
            )
        rows.append(pg_row)

        # Prev / Next navigation row
        nav = []
        if page > 1:
            nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"pg_{session_id}_{page - 1}"))
        if page < total_pages:
            nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"pg_{session_id}_{page + 1}"))
        if nav:
            rows.append(nav)

    # Always-present link button
    rows.append([
        InlineKeyboardButton("🎬 Click here to Get movie/Series", url=current_url)
    ])
    return InlineKeyboardMarkup(rows)


async def _send_to_results_channel(bot, text: str):
    """Send a message to RESULTS_CHANNEL.

    On PeerIdInvalid (in-memory session lost access_hash after restart/reconnect),
    force-resolve the peer by scanning all dialogs, then retry once.
    This is more reliable than a pre-resolve warmup that may not survive reconnections.
    """
    try:
        return await bot.send_message(
            chat_id=RESULTS_CHANNEL,
            text=text,
            disable_web_page_preview=True,
        )
    except (PeerIdInvalid, ValueError):
        logger.warning("PeerIdInvalid for RESULTS_CHANNEL — rescanning dialogs to re-resolve peer")
        try:
            async for dialog in bot.get_dialogs():
                if dialog.chat.id == RESULTS_CHANNEL:
                    logger.info("RESULTS_CHANNEL peer re-resolved via dialogs scan")
                    break
        except Exception as scan_err:
            logger.warning("Dialog scan failed during peer re-resolution: %s", scan_err)
        # Retry — if the scan found the peer it's now cached; otherwise this will
        # raise a descriptive exception that the caller can surface to the user.
        return await bot.send_message(
            chat_id=RESULTS_CHANNEL,
            text=text,
            disable_web_page_preview=True,
        )


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

    # ── Load group config ──────────────────────────────────────────────────
    group = await get_group(message.chat.id)
    if not group or not group.get("verified"):
        return

    # ── Force subscribe check ──────────────────────────────────────────────
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

    # ── Connect user session ───────────────────────────────────────────────
    # Use a lock so concurrent searches don't all call User.start() at the
    # same time — that causes [406 AUTH_KEY_DUPLICATED] from Telegram.
    try:
        from client import User
        if User is None:
            raise RuntimeError("User session is not configured (SESSION env var missing)")
        if not User.is_connected:
            async with _user_start_lock:
                # Double-check inside the lock — another coroutine may have
                # already started the session while we were waiting.
                if not User.is_connected:
                    await User.start()
    except Exception as e:
        logger.warning("User session unavailable: %s", e)
        m = await message.reply(
            "⚠️ <b>Search is temporarily unavailable.</b> Try again in a moment."
        )
        await _schedule_delete(bot, m, 30)
        return

    wait_msg = await message.reply("🔍 <i>Searching...</i>")

    results = await _search_channels(User, channels, query)
    ttl = group.get("auto_delete", SEARCH_REPLY_TTL)

    # ── Spell-correct fallback ─────────────────────────────────────────────
    if not results:
        corrected = await google_spell_check(query)
        if corrected and corrected.lower() != query.lower():
            results = await _search_channels(User, channels, corrected)
            if results:
                query = corrected

    # ── No results at all ─────────────────────────────────────────────────
    if not results:
        imdb_hits = await search_imdb(query)
        imdb_text = ""
        if imdb_hits:
            imdb_text = "\n\n<b>Did you mean:</b>\n"
            imdb_text += "\n".join(f"• {html.escape(h['title'])}" for h in imdb_hits[:5])
        await wait_msg.edit(
            f"❌ <b>No results found for:</b> <i>{html.escape(query)}</i>"
            f"{imdb_text}\n\n<b>Please request the group admin 👇</b>"
        )
        await _schedule_delete(bot, wait_msg, ttl)
        return

    # ── Split into pages ───────────────────────────────────────────────────
    total = len(results)
    pages_data = [results[i:i + _RESULTS_PER_PAGE] for i in range(0, total, _RESULTS_PER_PAGE)]
    total_pages = len(pages_data)

    # ── Post each page to RESULTS_CHANNEL ─────────────────────────────────
    # _send_to_results_channel handles PeerIdInvalid by re-resolving the peer
    # via a full dialog scan and retrying — no separate pre-resolve step needed.
    page_urls: list[str] = []
    for pg_num, pg_results in enumerate(pages_data, 1):
        offset = (pg_num - 1) * _RESULTS_PER_PAGE
        text = _build_page_message(query, pg_results, total, pg_num, total_pages, offset, ttl)
        try:
            sent = await _send_to_results_channel(bot, text)
            url = await _results_link(bot, RESULTS_CHANNEL, sent.id)
            page_urls.append(url)
            await _schedule_delete(bot, sent, ttl)
        except Exception as e:
            logger.error("Failed to send page %d to RESULTS_CHANNEL: %s", pg_num, e)
            if pg_num == 1:
                await wait_msg.edit(
                    f"❌ <b>Failed to post results.</b>\n"
                    f"<code>{type(e).__name__}: {html.escape(str(e))}</code>\n\n"
                    f"ℹ️ Make sure the bot is admin in the results channel with "
                    f"<b>Post Messages</b> permission."
                )
                return
            break  # partial send — use the pages we managed to post

    if not page_urls:
        await wait_msg.edit("❌ <b>Failed to post results.</b> Please try again.")
        return

    actual_pages = len(page_urls)

    # ── Store session for callback navigation ──────────────────────────────
    _prune_sessions()
    session_id = uuid.uuid4().hex[:8]
    _page_sessions[session_id] = {
        "urls": page_urls,
        "query": query,
        "total": total,
        "total_pages": actual_pages,
        "ttl": int(time()) + _SESSION_TTL,
        "reply_ttl": ttl,
    }

    # ── Edit wait_msg → page 1 reply ───────────────────────────────────────
    mins_label = max(1, ttl // 60)
    group_text = (
        f"✅ <b>Found {total} result{'s' if total != 1 else ''} in "
        f"<a href=\"{page_urls[0]}\">Channel</a>.</b>\n"
        f"Page 1/{actual_pages}\n"
        f"<i>(Results auto-delete in {mins_label} min{'s' if mins_label != 1 else ''})</i>"
    )
    kb = _page_keyboard(session_id, 1, actual_pages, page_urls[0])
    await wait_msg.edit(group_text, reply_markup=kb)
    await _schedule_delete(bot, wait_msg, ttl)


# ── Pagination callback handler ────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^pg_[0-9a-f]{8}_\d+$"))
async def page_cb(bot, cb):
    parts = cb.data.split("_")
    session_id = parts[1]
    page = int(parts[2])

    session = _page_sessions.get(session_id)
    if not session:
        return await cb.answer(
            "⏰ Session expired — please search again.", show_alert=True
        )

    urls = session["urls"]
    total = session["total"]
    total_pages = session["total_pages"]
    query = session["query"]
    ttl = session.get("reply_ttl", SEARCH_REPLY_TTL)

    if page < 1 or page > total_pages:
        return await cb.answer("Invalid page.", show_alert=True)

    url = urls[page - 1]
    mins_label = max(1, ttl // 60)

    text = (
        f"✅ <b>Found {total} result{'s' if total != 1 else ''} in "
        f"<a href=\"{url}\">Channel</a>.</b>\n"
        f"Page {page}/{total_pages}\n"
        f"<i>(Results auto-delete in {mins_label} min{'s' if mins_label != 1 else ''})</i>"
    )
    kb = _page_keyboard(session_id, page, total_pages, url)

    try:
        await cb.message.edit(text, reply_markup=kb)
    except Exception:
        pass
    await cb.answer()
