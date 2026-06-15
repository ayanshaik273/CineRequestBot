from utils import get_group, update_group
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

ALLOWED_MINUTES = {1: 60, 2: 120, 5: 300}


def _timer_keyboard(current_secs: int) -> InlineKeyboardMarkup:
    rows = []
    for mins, secs in ALLOWED_MINUTES.items():
        label = f"{'✅ ' if secs == current_secs else ''}{mins} min"
        rows.append([InlineKeyboardButton(label, callback_data=f"adset_{secs}")])
    return InlineKeyboardMarkup(rows)


@Client.on_message(filters.group & filters.command("autodelete"))
async def autodelete_cmd(bot, message):
    group = await get_group(message.chat.id)
    if not group:
        return await message.reply("❌ This group is not verified. Use /verify first.")

    if message.from_user.id != group.get("user_id"):
        return await message.reply(f"Only {group.get('user_name')} can use this command.")

    current = group.get("auto_delete", 60)

    args = message.command[1:]
    if args:
        try:
            mins = int(args[0])
            if mins not in ALLOWED_MINUTES:
                raise ValueError
            secs = ALLOWED_MINUTES[mins]
            await update_group(message.chat.id, {"auto_delete": secs})
            return await message.reply(
                f"✅ <b>Auto-delete timer set to {mins} minute{'s' if mins > 1 else ''}.</b>\n"
                f"Search results will be deleted after <b>{mins} min</b>."
            )
        except (ValueError, IndexError):
            return await message.reply(
                "❌ Invalid value. Use:\n"
                "<code>/autodelete 1</code> — 1 minute\n"
                "<code>/autodelete 2</code> — 2 minutes\n"
                "<code>/autodelete 5</code> — 5 minutes"
            )

    mins_label = next((k for k, v in ALLOWED_MINUTES.items() if v == current), 1)
    await message.reply(
        f"⏱ <b>Auto-Delete Timer</b>\n\n"
        f"Current setting: <b>{mins_label} minute{'s' if mins_label > 1 else ''}</b>\n\n"
        f"Tap a button to change it:",
        reply_markup=_timer_keyboard(current)
    )


@Client.on_callback_query(filters.regex(r"^adset_"))
async def autodelete_cb(bot, update):
    group = await get_group(update.message.chat.id)
    if not group:
        return await update.answer("Group not found.", show_alert=True)

    if update.from_user.id != group.get("user_id"):
        return await update.answer("Only the group owner can change this.", show_alert=True)

    secs = int(update.data.split("_")[1])
    mins = secs // 60
    await update_group(update.message.chat.id, {"auto_delete": secs})
    await update.message.edit(
        f"⏱ <b>Auto-Delete Timer</b>\n\n"
        f"Current setting: <b>{mins} minute{'s' if mins > 1 else ''}</b>\n\n"
        f"Tap a button to change it:",
        reply_markup=_timer_keyboard(secs)
    )
    await update.answer(f"✅ Timer set to {mins} min", show_alert=False)
