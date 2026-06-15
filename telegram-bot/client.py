from config import API_ID, API_HASH, BOT_TOKEN, SESSION
from pyrogram import Client

# Only create User client if SESSION is configured.
# If SESSION is empty/missing, User is None and search will be disabled.
if SESSION:
    User = Client(
        name="user",
        session_string=SESSION,
        api_id=API_ID,
        api_hash=API_HASH,
        in_memory=True,
    )
else:
    User = None

DlBot = Client(
    name="auto-delete",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True,
)
