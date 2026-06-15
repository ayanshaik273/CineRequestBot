from config import LOG_CHANNEL, OWNER_ID
  from utils import script, get_groups, get_users, add_user, get_connected_channels_count
  from pyrogram import Client, filters
  from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton


  @Client.on_message(filters.command("start") & ~filters.channel)
  async def start(bot, message):
      await add_user(message.from_user.id, message.from_user.first_name)
      await message.reply(
          text=script.START.format(message.from_user.mention),
          disable_web_page_preview=True,
          reply_markup=InlineKeyboardMarkup([
              [InlineKeyboardButton("ʜᴇʟᴘ", callback_data="misc_help"),
               InlineKeyboardButton("ᴀʙᴏᴜᴛ", callback_data="misc_about")],
          ])
      )


  @Client.on_message(filters.command("help"))
  async def help_cmd(bot, message):
      await message.reply(text=script.HELP, disable_web_page_preview=True)


  @Client.on_message(filters.command("about"))
  async def about_cmd(bot, message):
      me = await bot.get_me()
      await message.reply(
          text=script.ABOUT.format(me.mention),
          disable_web_page_preview=True
      )


  async def _build_stats(bot):
      u_count, _ = await get_users()
      g_count, _ = await get_groups()
      ch_count = await get_connected_channels_count()
      text = script.STATS.format(u_count, g_count, ch_count)
      kb = InlineKeyboardMarkup([[
          InlineKeyboardButton("🔄 Refresh", callback_data="stats_refresh"),
      ]])
      return text, kb


  @Client.on_message(filters.command("stats") & filters.user(OWNER_ID))
  async def stats(bot, message):
      text, kb = await _build_stats(bot)
      await message.reply(text, reply_markup=kb)


  @Client.on_callback_query(filters.regex(r"^stats_refresh$") & filters.user(OWNER_ID))
  async def stats_refresh(bot, update):
      text, kb = await _build_stats(bot)
      try:
          await update.message.edit(text, reply_markup=kb)
      except Exception:
          pass
      await update.answer("✅ Refreshed!")


  @Client.on_message(filters.command("id"))
  async def id_cmd(bot, message):
      text = f"<b>➲  ᴄʜᴀᴛ ɪᴅ:-</b>  `{message.chat.id}`\n"
      if message.from_user:
          text += f"<b>➲  ʏᴏᴜʀ ɪᴅ:-</b> `{message.from_user.id}`\n"
      if message.reply_to_message:
          if message.reply_to_message.from_user:
              text += f"<b>➲  ʀᴇᴘʟɪᴇᴅ ᴜꜱᴇʀ ɪᴅ:-</b> `{message.reply_to_message.from_user.id}`\n"
          if message.reply_to_message.forward_from:
              text += f"<b>➲  ꜰᴏʀᴡᴀʀᴅ ꜰʀᴏᴍ ɪᴅ:-</b> `{message.reply_to_message.forward_from.id}`\n"
          if message.reply_to_message.forward_from_chat:
              text += f"<b>➲  ꜰᴏʀᴡᴀʀᴅ ꜰʀᴏᴍ ᴄʜᴀᴛ ɪᴅ:-</b> `{message.reply_to_message.forward_from_chat.id}`\n"
      await message.reply(text)


  @Client.on_callback_query(filters.regex(r"^misc"))
  async def misc_cb(bot, update):
      data = update.data.split("_")[-1]
      if data == "home":
          await update.message.edit(
              text=script.START.format(update.from_user.mention),
              disable_web_page_preview=True,
              reply_markup=InlineKeyboardMarkup([
                  [InlineKeyboardButton("ʜᴇʟᴘ", callback_data="misc_help"),
                   InlineKeyboardButton("ᴀʙᴏᴜᴛ", callback_data="misc_about")],
              ])
          )
      elif data == "help":
          await update.message.edit(
              text=script.HELP,
              disable_web_page_preview=True,
              reply_markup=InlineKeyboardMarkup([[
                  InlineKeyboardButton("ʙᴀᴄᴋ", callback_data="misc_home"),
              ]])
          )
      elif data == "about":
          me = await bot.get_me()
          await update.message.edit(
              text=script.ABOUT.format(me.mention),
              disable_web_page_preview=True,
              reply_markup=InlineKeyboardMarkup([[
                  InlineKeyboardButton("ʙᴀᴄᴋ", callback_data="misc_home"),
              ]])
          )
      await update.answer()


  @Client.on_message(filters.private & filters.text & filters.incoming)
  async def pm_text(bot, message):
      content = message.text
      if content.startswith("/") or content.startswith("#"):
          return
      user    = message.from_user.first_name
      user_id = message.from_user.id

      await message.reply_text(text=script.PM_REPLY)
      if LOG_CHANNEL:
          await bot.send_message(
              chat_id=LOG_CHANNEL,
              text=f"<b>#𝐌𝐒𝐆\n\nNᴀᴍᴇ : {user}\n\nID : {user_id}\n\nMᴇssᴀɢᴇ : {content}</b>"
          )
  