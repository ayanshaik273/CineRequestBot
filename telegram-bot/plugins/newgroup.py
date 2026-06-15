from config import LOG_CHANNEL
from utils import script, add_user
from database.db import add_group
from asyncio import sleep
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton


@Client.on_message(filters.group & filters.new_chat_members)
async def new_group(bot, message):
    bot_id = bot.me.id if bot.me else (await bot.get_me()).id
    member = [u.id for u in (message.new_chat_members or [])]
    if bot_id not in member:
        return

    await add_group(
        group_id=message.chat.id,
        group_name=message.chat.title,
        user_name=message.from_user.first_name if message.from_user else "Unknown",
        user_id=message.from_user.id if message.from_user else 0,
        channels=[],
        f_sub=False,
        verified=False,
    )

    m = await message.reply(
        script.WELCOME.format(message.chat.title),
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("•  ʜᴇʟᴘ  •", callback_data="misc_help"),
        ]])
    )

    text = (
        f"#NewGroup\n\n"
        f"Group: {message.chat.title}\n"
        f"GroupID: `{message.chat.id}`\n"
        f"AddedBy: {message.from_user.mention if message.from_user else 'Unknown'}\n"
        f"UserID: `{message.from_user.id if message.from_user else 0}`"
    )
    if LOG_CHANNEL:
        try:
            await bot.send_message(chat_id=LOG_CHANNEL, text=text)
        except Exception:
            pass
    await sleep(120)
    await m.delete()
