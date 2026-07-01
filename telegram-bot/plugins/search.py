import asyncio
import html
import logging
import uuid
from time import time

from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait, ChannelInvalid, ChannelPrivate, PeerIdInvalid
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import RESULTS_CHANNEL, SEARCH_REPLY_TTL, SESSION, BACKUP_CHANNEL, LOG_CHANNEL, OWNER_ID
from database.db import get_group, force_sub, save_dlt_message, get_setting, record_failed_search
from utils.spell import google_spell_check
from utils.imdb import search_imdb

logger = logging.getLogger(__name__)

_TG_LIMIT = 4096
_RESULTS_PER_PAGE = 4
_SESSION_TTL = 3600

_page_sessions: dict = {}
_user_start_lock = asyncio.Lock()

_rate_limit: dict = {}
_RATE_LIMIT_COUNT = 3
_RATE_LIMIT_WINDOW = 30

# Per-user cooldown for Request Here (60 s)
_req_cooldown: dict = {}

_OLD_LINKS = [
    "https://t.me/BackupchannelJoinn",
    "https://t.me/%2BiGDgei3ADkZiMjNl",
    "https://t.me/+iGDgei3ADkZiMjNl",
    "https://t.me/backupchannek",
]


def _is_rate_limited(user_id: int) -> bool:
    now = time()
    hits = [t for t in _rate_limit.get(user_id, []) if now - t < _RATE_LIMIT_WINDOW]
    if len(hits) >= _RATE_LIMIT_COUNT:
        _rate_limit[user_id] = hits
        return True
    hits.append(now)
    _rate_limit[user_id] = hits
    return False


def _prune_sessions():
    now = time()
    expired = [k for k, v in _page_sessions.items() if now > v.get("ttl", 0)]
    for k in expired:
        _page_sessions.pop(k, None)
    expired_rl = [k for k, v in _rate_limit.items() if not any(now - t < _RATE_LIMIT_WINDOW for t in v)]
    for k in expired_rl:
        _rate_limit.pop(k, None)


async def _get_backup_link() -> str:
    try:
        link = await get_setting("backup_link")
        if link:
            return link
    except Exception:
        pass
    return BACKUP_CHANNEL or ""


async def _results_link(bot, channel_id: int, message_id: int) -> str:
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


async def _search_channels(user_client, channels: list, query: str, backup_link: str = "") -> list:
    results = []
    for ch_id in channels:
        try:
            async for msg in user_client.search_messages(ch_id, query=query, limit=50):
                text = (msg.text or msg.caption or "").strip()
                if backup_link:
                    for old in _OLD_LINKS:
                        text = text.replace(old, backup_link)
                if text:
                    results.append(text)
                    if len(results) >= 30:
                        return results
        except (ChannelInvalid, ChannelPrivate):
            logger.debug("Channel %s invalid/private -- skipping", ch_id)
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except Exception as e:
            logger.debug("Search error ch=%s: %s", ch_id, e)
    return results


def _build_page_message(query: str, page_results: list, total: int,
                         page: int, total_pages: int,
                         offset: int, ttl_secs: int,
                         backup_link: str = "") -> str:
    mins = max(1, ttl_secs // 60)
    header = (
        "\U0001f50d <b>Search:</b> " + html.escape(query) + "\n"
        + "\U0001f4c4 <b>Page " + str(page) + "/" + str(total_pages) + "</b>  \u00b7  "
        + "<b>" + str(total) + " result" + ("s" if total != 1 else "") + " total</b>\n\n"
    )
    join_line = "\U0001f4e2 Join: " + backup_link + "\n" if backup_link else ""
    footer = (
        "\n" + "\u2500" * 32 + "\n"
        + join_line
        + "\u23f3 <i>Auto-deletes in " + str(mins) + " min" + ("s" if mins != 1 else "") + "</i>"
    )
    budget = _TG_LIMIT - len(header) - len(footer) - 20
    body_lines = []
    used = 0
    for i, text in enumerate(page_results, offset + 1):
        full = html.escape(text)
        remaining = budget - used
        if remaining <= 10 and used > 0:
            break
        if len(full) <= remaining - 10:
            snippet = full
        else:
            snippet = full[:max(remaining - 1, 50)] + "\u2026"
        entry = "<b>" + str(i) + ".</b> " + snippet + "\n\n"
        body_lines.append(entry)
        used += len(entry)
        if used >= budget:
            break
    return header + "".join(body_lines) + footer


def _page_keyboard(session_id: str, page: int, total_pages: int,
                   current_url: str) -> InlineKeyboardMarkup:
    rows = []
    if total_pages > 1:
        half = 2
        start = max(1, min(page - half, total_pages - 3))
        end = min(total_pages, start + 3)
        start = max(1, end - 3)
        pg_row = []
        for p in range(start, end + 1):
            label = "\u2022 Pg " + str(p) + " \u2022" if p == page else "Pg " + str(p)
            pg_row.append(InlineKeyboardButton(label, callback_data="pg_" + session_id + "_" + str(p)))
        rows.append(pg_row)
        nav = []
        if page > 1:
            nav.append(InlineKeyboardButton("\u2b05\ufe0f Prev", callback_data="pg_" + session_id + "_" + str(page - 1)))
        if page < total_pages:
            nav.append(InlineKeyboardButton("Next \u27a1\ufe0f", callback_data="pg_" + session_id + "_" + str(page + 1)))
        if nav:
            rows.append(nav)
    rows.append([InlineKeyboardButton("\U0001f3ac Click here to Get movie/Series", url=current_url)])
    return InlineKeyboardMarkup(rows)


async def _send_to_results_channel(bot, text: str):
    try:
        return await bot.send_message(chat_id=RESULTS_CHANNEL, text=text, disable_web_page_preview=True)
    except (PeerIdInvalid, ValueError):
        logger.warning("Peer id invalid for RESULTS_CHANNEL -- re-resolving")
        try:
            if isinstance(RESULTS_CHANNEL, str):
                await bot.get_chat(RESULTS_CHANNEL)
            else:
                from pyrogram.raw.functions.channels import GetFullChannel
                from pyrogram.raw.types import InputChannel
                bare_id = abs(RESULTS_CHANNEL) - 1_000_000_000_000
                try:
                    await bot.invoke(GetFullChannel(channel=InputChannel(channel_id=bare_id, access_hash=0)))
                except Exception:
                    await bot.get_chat(RESULTS_CHANNEL)
        except Exception as resolve_err:
            logger.warning("Peer re-resolution failed: %s", resolve_err)
        return await bot.send_message(chat_id=RESULTS_CHANNEL, text=text, disable_web_page_preview=True)


@Client.on_message(
    filters.text & filters.group & filters.incoming
    & ~filters.via_bot & ~filters.bot
    & ~filters.command([
        "start", "help", "about", "id", "verify", "connect", "disconnect",
        "connections", "fsub", "nofsub", "autodelete", "broadcast",
        "broadcast_groups", "ping", "stats", "setbackup",
        "addsource", "summary", "clearfailed",
    ])
)
async def search(bot, message):
    if not message.text or not message.text.strip():
        return
    query = message.text.strip()
    if len(query) < 2 or len(query) > 100:
        return

    group = await get_group(message.chat.id)
    if not group or not group.get("verified"):
        return

    if not await force_sub(bot, message):
        return

    if message.from_user and _is_rate_limited(message.from_user.id):
        m = await message.reply(
            "⚠️ <b>Too many searches.</b> Please wait 30 seconds and try again."
        )
        await _schedule_delete(bot, m, 30)
        return

    channels = group.get("channels", [])
    if not channels:
        m = await message.reply(
            "\u26a0\ufe0f <b>No channels connected yet.</b>\n"
            "Ask the group admin to use /connect to link channels first."
        )
        await _schedule_delete(bot, m, 60)
        return

    if not RESULTS_CHANNEL:
        m = await message.reply("\u26a0\ufe0f <b>Results channel not configured.</b> Contact the bot owner.")
        await _schedule_delete(bot, m, 60)
        return

    if not SESSION:
        m = await message.reply("\u26a0\ufe0f <b>Search session not configured.</b> Contact the bot owner.")
        await _schedule_delete(bot, m, 60)
        return

    try:
        from client import User
        if User is None:
            raise RuntimeError("User session is not configured (SESSION env var missing)")
        if not User.is_connected:
            async with _user_start_lock:
                if not User.is_connected:
                    await User.start()
    except Exception as e:
        logger.warning("User session unavailable: %s", e)
        m = await message.reply("\u26a0\ufe0f <b>Search is temporarily unavailable.</b> Try again in a moment.")
        await _schedule_delete(bot, m, 30)
        return

    backup_link = await _get_backup_link()
    wait_msg = await message.reply("\U0001f50d <i>Searching...</i>")

    results = await _search_channels(User, channels, query, backup_link)
    ttl = group.get("auto_delete", SEARCH_REPLY_TTL)

    if not results:
        corrected = await google_spell_check(query)
        if corrected and corrected.lower() != query.lower():
            results = await _search_channels(User, channels, corrected, backup_link)
            if results:
                query = corrected

    if not results:
        imdb_hits = await search_imdb(query)
        imdb_text = ""
        if imdb_hits:
            imdb_text = "\n\n<b>Did you mean:</b>\n"
            imdb_text += "\n".join("\u2022 " + html.escape(h["title"]) for h in imdb_hits[:5])

        # Embed query directly in callback_data (first 50 chars) — no session needed
        safe_query = query[:50]
        _no_res_kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("\U0001f4e9 Request Here", callback_data=f"req_admin#{safe_query}")
        ]])

        await wait_msg.edit(
            "\u274c <b>No results found for:</b> <i>" + html.escape(query) + "</i>"
            + imdb_text + "\n\n<b>Please request the group admin \U0001f447</b>",
            reply_markup=_no_res_kb,
        )
        await _schedule_delete(bot, wait_msg, ttl)
        try:
            await record_failed_search(query, message.chat.id, message.chat.title or '')
        except Exception:
            pass
        if LOG_CHANNEL:
            try:
                user = message.from_user
                user_info = (
                    f"[{html.escape(user.first_name)}](tg://user?id={user.id})"
                    if user else "Unknown"
                )
                await bot.send_message(
                    chat_id=LOG_CHANNEL,
                    text=(
                        "#FailedSearch\n\n"
                        f"\U0001f50d Query: <code>{html.escape(query)}</code>\n"
                        f"\U0001f465 User: {user_info} (<code>{user.id if user else 'N/A'}</code>)\n"
                        f"\U0001f4ac Group: <b>{html.escape(message.chat.title or '')}</b> "
                        f"(<code>{message.chat.id}</code>)"
                    ),
                    disable_web_page_preview=True,
                )
            except Exception:
                pass
        return

    total = len(results)
    pages_data = [results[i:i + _RESULTS_PER_PAGE] for i in range(0, total, _RESULTS_PER_PAGE)]
    total_pages = len(pages_data)

    page_urls: list = []
    for pg_num, pg_results in enumerate(pages_data, 1):
        offset = (pg_num - 1) * _RESULTS_PER_PAGE
        text = _build_page_message(query, pg_results, total, pg_num, total_pages, offset, ttl, backup_link)
        try:
            sent = await _send_to_results_channel(bot, text)
            url = await _results_link(bot, RESULTS_CHANNEL, sent.id)
            page_urls.append(url)
            await _schedule_delete(bot, sent, ttl)
        except Exception as e:
            logger.error("Failed to send page %d to RESULTS_CHANNEL: %s", pg_num, e)
            if pg_num == 1:
                await wait_msg.edit(
                    "\u274c <b>Failed to post results.</b>\n"
                    "<code>" + type(e).__name__ + ": " + html.escape(str(e)) + "</code>\n\n"
                    "\u2139\ufe0f Make sure the bot is admin in the results channel with "
                    "<b>Post Messages</b> permission."
                )
                return
            break

    if not page_urls:
        await wait_msg.edit("\u274c <b>Failed to post results.</b> Please try again.")
        return

    actual_pages = len(page_urls)
    _prune_sessions()
    session_id = uuid.uuid4().hex[:8]
    _page_sessions[session_id] = {
        "urls": page_urls, "query": query, "total": total,
        "total_pages": actual_pages, "ttl": int(time()) + _SESSION_TTL, "reply_ttl": ttl,
    }

    mins_label = max(1, ttl // 60)
    group_text = (
        "\u2705 <b>Found " + str(total) + " result" + ("s" if total != 1 else "") + " in "
        + '<a href="' + page_urls[0] + '">Channel</a>.</b>\n'
        + "Page 1/" + str(actual_pages) + "\n"
        + "<i>(Results auto-delete in " + str(mins_label) + " min" + ("s" if mins_label != 1 else "") + ")</i>"
    )
    kb = _page_keyboard(session_id, 1, actual_pages, page_urls[0])
    await wait_msg.edit(group_text, reply_markup=kb, disable_web_page_preview=True)
    await _schedule_delete(bot, wait_msg, ttl)


@Client.on_callback_query(filters.regex(r"^pg_[0-9a-f]{8}_\d+$"))
async def page_cb(bot, cb):
    parts = cb.data.split("_")
    session_id = parts[1]
    page = int(parts[2])

    session = _page_sessions.get(session_id)
    if not session:
        return await cb.answer("\u23f0 Session expired -- please search again.", show_alert=True)

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
        "\u2705 <b>Found " + str(total) + " result" + ("s" if total != 1 else "") + " in "
        + '<a href="' + url + '">Channel</a>.</b>\n'
        + "Page " + str(page) + "/" + str(total_pages) + "\n"
        + "<i>(Results auto-delete in " + str(mins_label) + " min" + ("s" if mins_label != 1 else "") + ")</i>"
    )
    kb = _page_keyboard(session_id, page, total_pages, url)
    try:
        await cb.message.edit(text, reply_markup=kb)
    except Exception:
        pass
    await cb.answer()


@Client.on_callback_query(filters.regex(r"^req_admin#"), group=-1)
async def request_to_admin(bot, cb):
    """Handle 'Request Here' tap — rate-limit, notify owner/log channel."""
    now = time()
    last = _req_cooldown.get(cb.from_user.id, 0)
    if now - last < 60:
        return await cb.answer(
            "\u23f3 Please wait 1 minute before sending another request.",
            show_alert=True,
        )
    _req_cooldown[cb.from_user.id] = now

    await cb.answer("\u2705 Your request has been sent to the admin!", show_alert=True)

    movie_name = cb.data.split("#", 1)[1] if "#" in cb.data else "Unknown"
    user = cb.from_user
    requester = f"@{user.username}" if user.username else (user.first_name or str(user.id))
    text = f"#RequestFromYourGroup\n{movie_name}\n\U0001f464 {requester}"

    logger.info("REQUEST: movie=%r requester=%s OWNER_ID=%s LOG_CHANNEL=%s",
                movie_name, requester, OWNER_ID, LOG_CHANNEL)

    sent = False

    # Try owner PM first
    if OWNER_ID:
        try:
            await bot.send_message(chat_id=OWNER_ID, text=text)
            sent = True
            logger.info("REQUEST delivered to OWNER_ID=%s", OWNER_ID)
        except Exception as e:
            logger.exception("REQUEST: failed to send to OWNER_ID=%s — %s", OWNER_ID, e)

    # Also send to log channel
    if LOG_CHANNEL:
        try:
            await bot.send_message(chat_id=LOG_CHANNEL, text=text)
            sent = True
            logger.info("REQUEST delivered to LOG_CHANNEL=%s", LOG_CHANNEL)
        except Exception as e:
            logger.exception("REQUEST: failed to send to LOG_CHANNEL=%s — %s", LOG_CHANNEL, e)

    # Fallback: reply in the group so admin never misses it
    if not sent:
        logger.warning("REQUEST: PM and LOG_CHANNEL both failed — posting in group as fallback")
        try:
            await cb.message.reply_text(
                f"\U0001f4e9 <b>New Request</b>\n\n"
                f"\U0001f3ac {movie_name}\n"
                f"\U0001f464 {requester}\n\n"
                f"<i>(Admin PM not configured — set OWNER_ID env var on Railway)</i>",
                parse_mode=enums.ParseMode.HTML,
            )
        except Exception as e2:
            logger.exception("REQUEST: group fallback also failed: %s", e2)
