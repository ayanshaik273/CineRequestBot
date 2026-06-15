from config import LOG_CHANNEL, OWNER_ID
from utils import get_group, update_group
from database import delete_group
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton


@Client.on_message(filters.group & filters.command("verify"))
async def _verify(bot, message):
    try:
        group     = await get_group(message.chat.id)
        user_id   = group["user_id"]
        user_name = group["user_name"]
        verified  = group["verified"]
    except Exception:
        return await bot.leave_chat(message.chat.id)

    try:
        user = await bot.get_users(user_id)
    except Exception:
        return await message.reply(f"{user_name},\nꜱᴛᴀʀᴛ ᴍᴇ ɪɴ ᴘᴍ")

    if message.from_user.id != user_id:
        return await message.reply(f"Only {user.mention} can use this command 😁")
    if verified:
        return await message.reply("ᴛʜɪꜱ ɢʀᴏᴜᴘ ɪꜱ ᴀʟʀᴇᴀᴅʏ ᴠᴇʀɪꜰɪᴇᴅ!!")

    try:
        link = (await bot.get_chat(message.chat.id)).invite_link
    except Exception:
        return await message.reply("ᴍᴀᴋᴇ ᴍᴇ ᴀᴅᴍɪɴ ᴡɪᴛʜ ᴀʟʟ ᴘᴇʀᴍɪꜱꜱɪᴏɴꜱ")

    text  = "#NewRequest\n\n"
    text += f"User: {message.from_user.mention}\n"
    text += f"User ID: `{message.from_user.id}`\n"
    text += f"Group: [{message.chat.title}]({link})\n"
    text += f"Group ID: `{message.chat.id}`\n"

    markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ ᴀᴘᴘʀᴏᴠᴇ", callback_data=f"verify_approve_{message.chat.id}"),
        InlineKeyboardButton("❌ ᴅᴇᴄʟɪɴᴇ", callback_data=f"verify_decline_{message.chat.id}"),
    ]])

    sent = False
    for dest in [OWNER_ID, LOG_CHANNEL]:
        if not dest:
            continue
        try:
            await bot.send_message(
                chat_id=dest,
                text=text,
                disable_web_page_preview=True,
                reply_markup=markup if not sent else None,
            )
            sent = True
        except Exception:
            pass

    await message.reply("ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ ʀᴇǫᴜᴇꜱᴛ ꜱᴇɴᴛ ✅️\nᴄʜᴇᴄᴋ ʏᴏᴜʀ ᴘᴍ ᴡɪᴛʜ ᴍᴇ ᴛᴏ ᴀᴘᴘʀᴏᴠᴇ")


@Client.on_callback_query(filters.regex(r"^verify"))
async def verify_(bot, update):
    group_id = int(update.data.split("_")[-1])
    group    = await get_group(group_id)
    if not group:
        return await update.answer("Group not found", show_alert=True)
    name = group["name"]
    user = group["user_id"]

    if update.data.split("_")[1] == "approve":
        await update_group(group_id, {"verified": True})
        await bot.send_photo(
            chat_id=user,
            photo="https://telegra.ph/file/a706afc296de6da2a40c8.jpg",
            caption=f"<b>ʏᴏᴜʀ ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ ʀᴇǫᴜᴇꜱᴛ ꜰᴏʀ {name} ʜᴀꜱ ʙᴇᴇɴ ᴀᴘᴘʀᴏᴠᴇᴅ ✅</b>",
        )
        await update.message.edit(
            update.message.text.html.replace("#NewRequest", "#Approved")
        )
    else:
        await delete_group(group_id)
        await bot.send_message(
            chat_id=user,
            text=f"Your verification request for {name} has been declined 😐 Please Contact Admin"
        )
        await update.message.edit(
            update.message.text.html.replace("#NewRequest", "#Declined")
        )
