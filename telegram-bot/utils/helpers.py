from pyrogram.errors import FloodWait
import asyncio
import logging

logger = logging.getLogger(__name__)


def make_message_link(chat_id: int, message_id: int) -> str:
    cid = str(chat_id)
    if cid.startswith("-100"):
        cid = cid[4:]
    return f"https://t.me/c/{cid}/{message_id}"


async def get_chat_safe(client, chat_id):
    try:
        return await client.get_chat(chat_id)
    except Exception:
        pass
    try:
        async for dialog in client.get_dialogs():
            if dialog.chat.id == chat_id or str(dialog.chat.id) == str(chat_id):
                return dialog.chat
    except Exception:
        pass
    return None


async def copy_msgs(br_msg, chat_id: int) -> bool:
    """Copy a message to chat_id — loop on FloodWait instead of recursing."""
    while True:
        try:
            await br_msg.copy(chat_id)
            return True
        except FloodWait as e:
            await asyncio.sleep(e.value + 1)
        except Exception:
            return False


async def grp_copy_msgs(br_msg, chat_id: int) -> bool:
    """Copy a message to a group and try to pin it — loop on FloodWait."""
    while True:
        try:
            h = await br_msg.copy(chat_id)
            try:
                await h.pin()
            except Exception:
                pass
            return True
        except FloodWait as e:
            await asyncio.sleep(e.value + 1)
        except Exception:
            return False
