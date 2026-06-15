import asyncio
import time
import uuid
from config import OWNER_ID
from database import get_users, get_groups, delete_user, delete_group
from pyrogram import Client, filters
from pyrogram.errors import FloodWait, InputUserDeactivated, UserIsBlocked, PeerIdInvalid
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

_pending: dict = {}
_PENDING_TTL = 300


def _prune_pending():
    now = time.time()
    expired = [k for k, v in _pending.items() if now - v.get("ts", now) > _PENDING_TTL]
    for k in expired:
        _pending.pop(k, None)


async def _send_to_user(bot, from_chat_id: int, message_id: int, chat_id: int) -> bool:
    """Send via the bot token client — loop on FloodWait instead of recursing."""
    while True:
        try:
            await bot.copy_message(
                chat_id=chat_id,
                from_chat_id=from_chat_id,
                message_id=message_id,
            )
            return True
        except FloodWait as e:
            await asyncio.sleep(e.value + 1)
        except (InputUserDeactivated, UserIsBlocked, PeerIdInvalid):
            return False
        except Exception:
            return False


async def _send_to_group(bot, from_chat_id: int, message_id: int, chat_id: int) -> bool:
    """Send to group via the bot token client, then try to pin — loop on FloodWait."""
    while True:
        try:
            sent = await bot.copy_message(
                chat_id=chat_id,
                from_chat_id=from_chat_id,
                message_id=message_id,
            )
            try:
                await bot.pin_chat_message(chat_id, sent.id, disable_notification=True)
            except Exception:
                pass
            return True
        except FloodWait as e:
            await asyncio.sleep(e.value + 1)
        except Exception:
            return False


def _estimate(count: int) -> str:
    secs = max(1, count // 20)
    if secs < 60:
        return f"~{secs}s"
    return f"~{secs // 60}m {secs % 60}s"


def _preview_text(br_msg, count: int, target: str) -> str:
    snippet = ""
    if br_msg.text:
        snippet = br_msg.text.html[:200]
    elif br_msg.caption:
        snippet = br_msg.caption.html[:200]
    else:
        snippet = f"[{br_msg.media.value if br_msg.media else 'media'}]"

    label = "users" if target == "users" else "groups"
    return (
        f"📣 <b>Broadcast preview</b>\n\n"
        f"Recipients: <b>{count} {label}</b>\n"
        f"Sending as: <b>@{'{'}bot_username{'}'}</b>\n"
        f"Message:\n\n{snippet}\n\n"
        f"Confirm to start sending. Estimated time: <b>{_estimate(count)}</b>."
    )


def _confirm_kb(broadcast_id: str, count: int, target: str) -> InlineKeyboardMarkup:
    label = "users" if target == "users" else "groups"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"✅ Send to {count} {label}", callback_data=f"bc_go_{broadcast_id}")],
        [InlineKeyboardButton("❌ Cancel", callback_data=f"bc_cancel_{broadcast_id}")],
    ])


@Client.on_message(filters.command("broadcast") & filters.user(OWNER_ID))
async def broadcast_cmd(bot, message):
    if not message.reply_to_message:
        return await message.reply(
            "Reply to a message with /broadcast to send it to all users.\n"
            "Use /broadcast_groups to send to all groups instead."
        )

    _prune_pending()
    count, _ = await get_users()
    if count == 0:
        return await message.reply("No users in the database yet.")

    broadcast_id = str(uuid.uuid4())[:8]
    br_msg = message.reply_to_message
    _pending[broadcast_id] = {
        "from_chat_id": br_msg.chat.id,
        "message_id": br_msg.id,
        "target": "users",
        "ts": time.time(),
    }

    me = await bot.get_me()
    preview = _preview_text(br_msg, count, "users").replace(
        "{bot_username}", me.username or me.first_name
    )
    await message.reply(preview, reply_markup=_confirm_kb(broadcast_id, count, "users"))


@Client.on_message(filters.command("broadcast_groups") & filters.user(OWNER_ID))
async def broadcast_groups_cmd(bot, message):
    if not message.reply_to_message:
        return await message.reply(
            "Reply to a message with /broadcast_groups to send it to all groups."
        )

    _prune_pending()
    count, _ = await get_groups()
    if count == 0:
        return await message.reply("No groups in the database yet.")

    broadcast_id = str(uuid.uuid4())[:8]
    br_msg = message.reply_to_message
    _pending[broadcast_id] = {
        "from_chat_id": br_msg.chat.id,
        "message_id": br_msg.id,
        "target": "groups",
        "ts": time.time(),
    }

    me = await bot.get_me()
    preview = _preview_text(br_msg, count, "groups").replace(
        "{bot_username}", me.username or me.first_name
    )
    await message.reply(preview, reply_markup=_confirm_kb(broadcast_id, count, "groups"))


@Client.on_callback_query(filters.regex(r"^bc_"))
async def broadcast_cb(bot, update):
    if update.from_user.id != OWNER_ID:
        return await update.answer("Not authorised.", show_alert=True)

    parts = update.data.split("_")
    action = parts[1]
    broadcast_id = parts[2]

    if action == "cancel":
        _pending.pop(broadcast_id, None)
        return await update.message.edit("❌ Broadcast cancelled.")

    pending = _pending.pop(broadcast_id, None)
    if not pending:
        return await update.message.edit("❌ Broadcast expired or already sent.")

    from_chat_id = pending["from_chat_id"]
    message_id   = pending["message_id"]
    target       = pending["target"]

    if target == "users":
        count, recipients = await get_users()
        ids = [r["_id"] for r in recipients]
        send_fn = _send_to_user
        del_fn  = delete_user
    else:
        count, recipients = await get_groups()
        ids = [r["_id"] for r in recipients]
        send_fn = _send_to_group
        del_fn  = delete_group

    status_msg = await update.message.edit(
        f"📤 Broadcasting to {count} {target}... 0 done."
    )

    success = failed = 0
    for i, chat_id in enumerate(ids):
        ok = await send_fn(bot, from_chat_id, message_id, chat_id)
        if ok:
            success += 1
        else:
            failed += 1
            try:
                await del_fn(chat_id)
            except Exception:
                pass
        await asyncio.sleep(0.05)  # ~20 msgs/sec — stay under Telegram's 30/sec hard limit
        if (i + 1) % 20 == 0:
            try:
                await status_msg.edit(
                    f"📤 Broadcasting... {i + 1}/{count} done. ✅ {success} ❌ {failed}"
                )
            except Exception:
                pass

    await status_msg.edit(
        f"✅ <b>Broadcast complete!</b>\n\n"
        f"Total: {count}\n"
        f"✅ Success: {success}\n"
        f"❌ Failed: {failed}"
    )
