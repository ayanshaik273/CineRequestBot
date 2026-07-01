class script:
    START = """👋 Hey {},

✅ <b>CineRequestBot is alive and running!</b>

🎬 Add me to your group and link your content channels.
Members can then type any movie or series name — results are delivered privately via button.

<b>Send /help for all commands</b>"""

    HELP = """<b>‼️  Commands  ‼️</b>

/start - Check if I'm alive
/id - Get channel/group ID
/verify - Request group verification
/connect - Link a content channel to search from
/disconnect - Disconnect a channel
/connections - View & manage connected channels
/fsub - Set force-subscribe channel
/nofsub - Remove force-subscribe
/autodelete - Set result auto-delete timer (1, 2 or 5 mins)
/ping - Check bot speed
/report - Report an issue or content concern

<b>How it works:</b>
❶ Add me as admin in your group and content channel.
❷ Type /verify in the group — wait for approval.
❸ Use <code>/connect -100xxxxxxxxxx</code> to link your channel.
❹ Members type a movie name → results appear in a private results channel via button.

<i>ℹ️ This bot is a search tool only. It does not host or distribute any files. All results are links to existing public Telegram channels.</i>"""

    ABOUT = """<b>➣ Bot Name ⋟  {}</b>
<b>➢ Language ⋟  <a href="https://www.python.org">Python 3</a></b>
<b>➣ Database ⋟  <a href="https://www.mongodb.com">MongoDB</a></b>
<b>➢ Framework ⋟  <a href="https://docs.pyrogram.org">Pyrogram</a></b>

<i>ℹ️ This bot is a search tool only. It does not host, store, or distribute any media files. All results are links to existing public Telegram channels. To report a concern: /report</i>"""

    STATS = """<b>📊 Bot Statistics</b>

👤 <b>Total Users:</b> {}
♻️ <b>Total Groups:</b> {}
📡 <b>Connected Channels:</b> {}"""

    BROADCAST = """<u>{}</u>

Total: {}
Remaining: {}
Success: {}
Failed: {}"""

    NO_RESULTS_FINAL = "<b>⚠️ No Results Found!\nPlease request the group admin 👇</b>"

    FSUB_MSG = "<b>🚫 Hi {}!\n\nJoin our channel first to use this group 💯</b>"

    WELCOME = """<b>☤ Thank you for adding me to {}

• Make me an admin with full permissions
• Get verified using the /verify command
• Questions? Use the buttons below</b>"""

    PM_REPLY = """<b>Hi! 👋

To search for movies or series, add me to your group and use /verify.</b>"""

    REPORT = """<b>📋 Report a Content Concern</b>

This bot is a <b>search tool only</b> — it does not host or distribute any files.
All results are links to existing public Telegram channels.

If you have a content concern or copyright issue:

📧 <b>Email:</b> <code>ssthekiller@proton.me</code>
📝 <b>Include:</b> the content name, the source channel, and your reason.

We review all reports and will disconnect any flagged source channel promptly.

<i>Group admins can also use /disconnect to remove a source channel immediately.</i>"""
