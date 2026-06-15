from config import OWNER_ID
from pyrogram import Client, filters
from database.db import get_setting, set_setting


@Client.on_message(filters.command("setbackup") & filters.user(OWNER_ID))
async def setbackup_cmd(bot, message):
    parts = message.text.split(None, 1)
    if len(parts) < 2:
        current = await get_setting("backup_link", "not set")
        return await message.reply(
            f"<b>\U0001f517 Current backup link:</b> <code>{current}</code>\n\n"
            f"<b>Usage:</b> <code>/setbackup https://t.me/yourchannel</code>\n\n"
            f"This link appears in every result footer and the Request Here button."
        )
    link = parts[1].strip()
    if not link.startswith("https://t.me/"):
        return await message.reply(
            "\u274c Invalid link. Must start with <code>https://t.me/</code>"
        )
    await set_setting("backup_link", link)
    await message.reply(
        f"\u2705 <b>Backup channel link updated!</b>\n\n"
        f"New link: <code>{link}</code>\n\n"
        f"All future search results and request buttons will use this link."
    )
