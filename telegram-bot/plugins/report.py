from pyrogram import Client, filters
from utils import script


@Client.on_message(filters.command("report"))
async def report_cmd(bot, message):
    await message.reply(
        text=script.REPORT,
        disable_web_page_preview=True,
    )
