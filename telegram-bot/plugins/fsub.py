from config import LOG_CHANNEL
from utils import get_group, update_group
from pyrogram import Client, filters, enums
from pyrogram.errors import UserNotParticipant
from pyrogram.types import ChatPermissions


@Client.on_message(filters.group & filters.command("fsub"))
async def f_sub_cmd(bot, message):
    m = await message.reply("ᴘʟᴇᴀꜱᴇ ᴡᴀɪᴛ...")
    try:
        group     = await get_group(message.chat.id)
        user_id   = group["user_id"]
        user_name = group["user_name"]
        verified  = group["verified"]
    except Exception:
        return await bot.leave_chat(message.chat.id)

    if message.from_user.id != user_id:
        return await m.edit(f"Only {user_name} can use this command 😁")
    if not verified:
        return await m.edit("ᴛʜɪꜱ ᴄʜᴀᴛ ɪꜱ ɴᴏᴛ ᴠᴇʀɪꜰɪᴇᴅ 🚫\nᴜꜱᴇ /verify")

    try:
        f_sub = int(message.command[1])
    except Exception:
        return await m.edit("ɪɴᴄᴏʀʀᴇᴄᴛ ꜰᴏʀᴍᴀᴛ 🚫\nᴜꜱᴇ `/fsub` ᴄʜᴀɴɴᴇʟ ɪᴅ")

    try:
        chat       = await bot.get_chat(f_sub)
        group_chat = await bot.get_chat(message.chat.id)
        c_link     = chat.invite_link
        g_link     = group_chat.invite_link
    except Exception as e:
        text = (
            f"🚫 ᴇʀʀᴏʀ - `{str(e)}`\n\n"
            "ᴍᴀᴋᴇ ꜱᴜʀᴇ ᴛʜᴀᴛ ɪ ᴀᴍ ᴀᴅᴍɪɴ ɪɴ ᴄʜᴀɴɴᴇʟ ᴀɴᴅ ɢʀᴏᴜᴘ ᴡɪᴛʜ ᴀʟʟ ᴘᴇʀᴍɪꜱꜱɪᴏɴꜱ"
        )
        return await m.edit(text)

    await update_group(message.chat.id, {"f_sub": f_sub})
    await m.edit(
        f"ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ᴀᴛᴛᴀᴄʜᴇᴅ ꜰᴏʀᴄᴇꜱᴜʙ ᴛᴏ [{chat.title}]({c_link})!",
        disable_web_page_preview=True
    )
    text = (
        f"#NewFsub\n\n"
        f"User: {message.from_user.mention}\n"
        f"Group: [{group_chat.title}]({g_link})\n"
        f"Channel: [{chat.title}]({c_link})"
    )
    if LOG_CHANNEL:
        await bot.send_message(chat_id=LOG_CHANNEL, text=text)


@Client.on_message(filters.group & filters.command("nofsub"))
async def nf_sub_cmd(bot, message):
    m = await message.reply("ᴅɪꜱᴀᴛᴛᴀᴄʜɪɴɢ...")
    try:
        group     = await get_group(message.chat.id)
        user_id   = group["user_id"]
        user_name = group["user_name"]
        verified  = group["verified"]
        f_sub     = group["f_sub"]
    except Exception:
        return await bot.leave_chat(message.chat.id)

    if message.from_user.id != user_id:
        return await m.edit(f"Only {user_name} can use this command 😁")
    if not verified:
        return await m.edit("ᴛʜɪꜱ ᴄʜᴀᴛ ɪꜱ ɴᴏᴛ ᴠᴇʀɪꜰɪᴇᴅ 🚫\nᴜꜱᴇ /verify")
    if not f_sub:
        return await m.edit("ᴛʜɪꜱ ᴄʜᴀᴛ ᴅᴏᴇꜱ ɴᴏᴛ ʜᴀᴠᴇ ᴀɴʏ ꜰᴏʀᴄᴇ ꜱᴜʙ\nᴜꜱᴇ /fsub")

    try:
        chat       = await bot.get_chat(f_sub)
        group_chat = await bot.get_chat(message.chat.id)
        c_link     = chat.invite_link
        g_link     = group_chat.invite_link
    except Exception as e:
        text = (
            f"🚫 ᴇʀʀᴏʀ - `{str(e)}`\n\n"
            "ᴍᴀᴋᴇ ꜱᴜʀᴇ ᴛʜᴀᴛ ɪ ᴀᴍ ᴀᴅᴍɪɴ ɪɴ ᴄʜᴀɴɴᴇʟ ᴀɴᴅ ɢʀᴏᴜᴘ ᴡɪᴛʜ ᴀʟʟ ᴘᴇʀᴍɪꜱꜱɪᴏɴꜱ"
        )
        return await m.edit(text)

    await update_group(message.chat.id, {"f_sub": False})
    await m.edit(
        f"ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ʀᴇᴍᴏᴠᴇᴅ ꜰᴏʀᴄᴇ ꜱᴜʙ ꜰʀᴏᴍ [{chat.title}]({c_link})",
        disable_web_page_preview=True
    )
    text = (
        f"#RemoveFsub\n\n"
        f"User: {message.from_user.mention}\n"
        f"Group: [{group_chat.title}]({g_link})\n"
        f"Channel: [{chat.title}]({c_link})"
    )
    if LOG_CHANNEL:
        await bot.send_message(chat_id=LOG_CHANNEL, text=text)


def _unrestrict_permissions() -> ChatPermissions:
    """Return full unrestricted ChatPermissions, compatible with both old and new Pyrogram."""
    kwargs = dict(can_send_messages=True)
    # New granular fields (Pyrogram v2 / Telegram Bot API v5.0+)
    for field in (
        "can_send_audios", "can_send_documents", "can_send_photos",
        "can_send_videos", "can_send_video_notes", "can_send_voice_notes",
        "can_send_polls", "can_send_other_messages", "can_add_web_page_previews",
        "can_change_info", "can_invite_users", "can_pin_messages",
        # legacy fields kept for older Pyrogram builds
        "can_send_media_messages",
    ):
        try:
            kwargs[field] = True
        except Exception:
            pass
    try:
        return ChatPermissions(**kwargs)
    except TypeError:
        # Fallback: only pass known-safe fields
        return ChatPermissions(can_send_messages=True)


@Client.on_callback_query(filters.regex(r"^checksub"))
async def f_sub_callback(bot, update):
    user_id = int(update.data.split("_")[-1])
    group   = await get_group(update.message.chat.id)
    if not group:
        return
    f_sub = group.get("f_sub")
    if not f_sub:
        return await update.answer("Force-sub is no longer active.", show_alert=True)

    if update.from_user.id != user_id:
        return await update.answer("ᴛʜɪꜱ  ɪꜱ  ɴᴏᴛ  ꜰᴏʀ  ʏᴏᴜ  😊", show_alert=True)

    try:
        member = await bot.get_chat_member(f_sub, user_id)
        if member.status == enums.ChatMemberStatus.BANNED:
            return await update.answer(
                "ʏᴏᴜ ᴀʀᴇ ʙᴀɴɴᴇᴅ ꜰʀᴏᴍ ᴛʜᴇ ᴄʜᴀɴɴᴇʟ.", show_alert=True
            )
    except UserNotParticipant:
        return await update.answer(
            "ꜰɪʀꜱᴛ ᴊᴏɪɴ ᴜᴘᴅᴀᴛᴇ ᴄʜᴀɴɴᴇʟ ᴛʜᴇɴ ᴄʟɪᴄᴋ ᴏɴ ᴛʜɪꜱ ʙᴜᴛᴛᴏɴ",
            show_alert=True
        )
    except Exception:
        pass

    try:
        await bot.restrict_chat_member(
            chat_id=update.message.chat.id,
            user_id=user_id,
            permissions=_unrestrict_permissions(),
        )
    except Exception:
        pass

    await update.answer("✅ ᴡᴇʟᴄᴏᴍᴇ! ʏᴏᴜ ᴄᴀɴ ɴᴏᴡ ꜱᴇɴᴅ ᴍᴇꜱꜱᴀɢᴇꜱ.", show_alert=True)
    try:
        await update.message.delete()
    except Exception:
        pass
