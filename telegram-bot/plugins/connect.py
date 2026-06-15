import html
import logging
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.db import get_group, update_group
from utils.helpers import get_chat_safe

logger = logging.getLogger(__name__)


# ── helpers ───────────────────────────────────────────────────────────────────

async def _owner_check(bot, message, group):
    if not group:
        await bot.leave_chat(message.chat.id)
        return False
    if not group.get("verified"):
        await message.reply("🚫 This chat is not verified. Use /verify first.")
        return False
    if message.from_user.id != group.get("user_id"):
        await message.reply(
            f"Only {html.escape(group.get('user_name', 'the owner'))} can use this command."
        )
        return False
    return True


def _get_user_client():
    """Return user client if available, else None. Never raises."""
    try:
        from client import User
        if User is not None and User.is_connected:
            return User
    except Exception:
        pass
    return None


async def _resolve_channel(bot, ch_id: int):
    """Try to get channel title via bot first, then user session."""
    chat = await get_chat_safe(bot, ch_id)
    if chat:
        return getattr(chat, "title", str(ch_id))
    user_client = _get_user_client()
    if user_client:
        try:
            chat = await get_chat_safe(user_client, ch_id)
            if chat:
                return getattr(chat, "title", str(ch_id))
        except Exception:
            pass
    return str(ch_id)


# ── /connect ──────────────────────────────────────────────────────────────────

@Client.on_message(filters.group & filters.command("connect"))
async def connect_cmd(bot, message):
    group = await get_group(message.chat.id)
    if not await _owner_check(bot, message, group):
        return

    args = message.command[1:]
    if not args:
        return await message.reply(
            "Usage: <code>/connect -100xxxxxxxxxx</code>"
        )

    try:
        ch_id = int(args[0])
    except ValueError:
        return await message.reply(
            "❌ Invalid channel ID. Use the numeric ID (e.g. <code>-1001234567890</code>)."
        )

    channels = group.get("channels", [])
    if ch_id in channels:
        return await message.reply("⚠️ That channel is already connected.")

    title = await _resolve_channel(bot, ch_id)
    channels.append(ch_id)
    await update_group(message.chat.id, {"channels": channels})
    await message.reply(
        f"✅ Connected: <b>{html.escape(title)}</b> (<code>{ch_id}</code>)\n"
        f"Total connected: <b>{len(channels)}</b>"
    )


# ── /disconnect ───────────────────────────────────────────────────────────────

@Client.on_message(filters.group & filters.command("disconnect"))
async def disconnect_cmd(bot, message):
    group = await get_group(message.chat.id)
    if not await _owner_check(bot, message, group):
        return

    args = message.command[1:]
    if not args:
        return await message.reply(
            "Usage: <code>/disconnect -100xxxxxxxxxx</code>\n"
            "Or use /connections to disconnect with buttons."
        )

    try:
        ch_id = int(args[0])
    except ValueError:
        return await message.reply("❌ Invalid channel ID.")

    channels = group.get("channels", [])
    if ch_id not in channels:
        return await message.reply("⚠️ That channel is not connected.")

    channels.remove(ch_id)
    await update_group(message.chat.id, {"channels": channels})
    await message.reply(
        f"✅ Disconnected <code>{ch_id}</code>.\n"
        f"Remaining: <b>{len(channels)}</b>"
    )


# ── /connections ─��────────────────────────────────────────────────────────────

@Client.on_message(filters.group & filters.command("connections"))
async def connections_cmd(bot, message):
    group = await get_group(message.chat.id)
    if not await _owner_check(bot, message, group):
        return

    channels = group.get("channels", [])
    if not channels:
        return await message.reply(
            "📭 No channels connected yet.\nUse /connect to add one."
        )

    buttons = []
    lines = ["<b>📡 Connected channels:</b>\n"]
    for i, ch_id in enumerate(channels, 1):
        title = await _resolve_channel(bot, ch_id)
        lines.append(f"{i}. <b>{html.escape(title)}</b> (<code>{ch_id}</code>)")
        buttons.append([
            InlineKeyboardButton(
                f"❌ Remove: {title[:28]}",
                callback_data=f"discon_{message.chat.id}_{ch_id}"
            )
        ])

    await message.reply(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(buttons)
    )


# ── disconnect callback ───────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^discon_"))
async def disconnect_cb(bot, update):
    parts = update.data.split("_")
    if len(parts) < 3:
        return await update.answer("Invalid data.", show_alert=True)

    group_id = int(parts[1])
    ch_id    = int(parts[2])

    group = await get_group(group_id)
    if not group:
        return await update.answer("Group not found.", show_alert=True)

    if update.from_user.id != group.get("user_id"):
        return await update.answer("Only the group owner can do this.", show_alert=True)

    channels = group.get("channels", [])
    if ch_id not in channels:
        await update.answer("Already removed.", show_alert=True)
        # Refresh the message to reflect current state
        if not channels:
            try:
                await update.message.edit("📭 No channels connected. Use /connect to add one.")
            except Exception:
                pass
        return

    channels.remove(ch_id)
    await update_group(group_id, {"channels": channels})

    if not channels:
        try:
            await update.message.edit("📭 No channels connected. Use /connect to add one.")
        except Exception:
            pass
        return await update.answer("✅ Disconnected!")

    buttons = []
    lines = ["<b>📡 Connected channels:</b>\n"]
    for i, cid in enumerate(channels, 1):
        title = await _resolve_channel(bot, cid)
        lines.append(f"{i}. <b>{html.escape(title)}</b> (<code>{cid}</code>)")
        buttons.append([
            InlineKeyboardButton(
                f"❌ Remove: {title[:28]}",
                callback_data=f"discon_{group_id}_{cid}"
            )
        ])

    try:
        await update.message.edit(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception:
        pass
    await update.answer("✅ Disconnected!")
