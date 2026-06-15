import time
from pyrogram import Client, filters


@Client.on_message(filters.command("ping"))
async def ping(bot, message):
    start = time.time()
    m = await message.reply("<b>🏓 Pong!</b>")
    elapsed = (time.time() - start) * 1000
    await m.edit(f"<b>🏓 Pong!</b>\n<b>⚡ Speed: {elapsed:.2f} ms</b>")
