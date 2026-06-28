import asyncio
import logging
from config import MONGO_URI, OWNER_ID
from pyrogram import enums
from pymongo.errors import DuplicateKeyError
from pyrogram.errors import UserNotParticipant
from motor.motor_asyncio import AsyncIOMotorClient
from pyrogram.types import ChatPermissions, InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)

_dbclient = None


def _get_cols():
    global _dbclient
    if _dbclient is None:
        if not MONGO_URI:
            raise RuntimeError("MONGO_URI is not set. Please configure MONGODB_PASSWORD or MONGO_URI.")
        _dbclient = AsyncIOMotorClient(
            MONGO_URI,
            tlsAllowInvalidCertificates=True,
            tlsAllowInvalidHostnames=True,
            serverSelectionTimeoutMS=15000,
        )
    db = _dbclient["Channel-Filter"]
    return db["GROUPS"], db["USERS"], db["Auto-Delete"]


async def add_group(group_id, group_name, user_name, user_id, channels, f_sub, verified):
    grp_col, _, _ = _get_cols()
    data = {
        "_id":      group_id,
        "name":     group_name,
        "user_id":  user_id,
        "user_name": user_name,
        "channels": channels,
        "f_sub":    f_sub,
        "verified": verified,
    }
    try:
        await grp_col.insert_one(data)
    except DuplicateKeyError:
        pass


async def get_group(id):
    grp_col, _, _ = _get_cols()
    group = await grp_col.find_one({"_id": id})
    return dict(group) if group else None


async def update_group(id, new_data):
    grp_col, _, _ = _get_cols()
    await grp_col.update_one({"_id": id}, {"$set": new_data})


async def delete_group(id):
    grp_col, _, _ = _get_cols()
    await grp_col.delete_one({"_id": id})


async def get_groups():
    grp_col, _, _ = _get_cols()
    count  = await grp_col.count_documents({})
    cursor = grp_col.find({})
    lst    = await cursor.to_list(length=int(count) if count else 1)
    return count, lst


async def add_user(id, name):
    _, user_col, _ = _get_cols()
    data = {"_id": id, "name": name}
    try:
        await user_col.insert_one(data)
        return True   # new user
    except DuplicateKeyError:
        return False  # already existed


async def get_users():
    _, user_col, _ = _get_cols()
    count  = await user_col.count_documents({})
    cursor = user_col.find({})
    lst    = await cursor.to_list(length=int(count) if count else 1)
    return count, lst


async def delete_user(id):
    _, user_col, _ = _get_cols()
    await user_col.delete_one({"_id": id})


async def save_dlt_message(message, time):
    _, _, dlt_col = _get_cols()
    data = {
        "chat_id":    message.chat.id,
        "message_id": message.id,
        "time":       time,
    }
    await dlt_col.insert_one(data)


async def get_all_dlt_data(time):
    _, _, dlt_col = _get_cols()
    data     = {"time": {"$lte": time}}
    count    = await dlt_col.count_documents(data)
    cursor   = dlt_col.find(data)
    all_data = await cursor.to_list(length=int(count) if count else 1)
    return all_data


async def delete_all_dlt_data(time):
    _, _, dlt_col = _get_cols()
    data = {"time": {"$lte": time}}
    await dlt_col.delete_many(data)


async def force_sub(bot, message):
    grp_col, _, _ = _get_cols()
    group = await get_group(message.chat.id)
    if group is None:
        return True
    f_sub = group.get("f_sub", False)
    admin = group.get("user_id")
    if not f_sub:
        return True
    if message.from_user is None:
        return True
    try:
        # Only check membership — do NOT call get_chat() here.
        # get_chat(f_sub) was being called on every single message even for
        # already-subscribed users, wasting an API call per message.
        # The invite link is only needed when the user is NOT a participant,
        # so it's fetched lazily inside the except block below.
        member = await bot.get_chat_member(f_sub, message.from_user.id)
        if member.status == enums.ChatMemberStatus.BANNED:
            await message.reply(
                f"ꜱᴏʀʀʏ {message.from_user.mention}!\n"
                " ʏᴏᴜ ᴀʀᴇ ʙᴀɴɴᴇᴅ ɪɴ ᴏᴜʀ ᴄʜᴀɴɴᴇʟ, "
                "ʏᴏᴜ ᴡɪʟʟ ʙᴇ ʙᴀɴɴᴇᴅ ꜰʀᴏᴍ ʜᴇʀᴇ ᴡɪᴛʜɪɴ 10 ꜱᴇᴄᴏɴᴅꜱ"
            )
            await asyncio.sleep(10)
            await bot.ban_chat_member(message.chat.id, message.from_user.id)
            return False
    except UserNotParticipant:
        try:
            f_link = (await bot.get_chat(f_sub)).invite_link or ""
        except Exception:
            f_link = ""
        await bot.restrict_chat_member(
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            permissions=ChatPermissions(can_send_messages=False),
        )
        await message.reply(
            f"<b>🚫 ʜɪ ᴅᴇᴀʀ {message.from_user.mention}!\n\n"
            " ɪꜰ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ꜱᴇɴᴅ ᴍᴇꜱꜱᴀɢᴇ ɪɴ ᴛʜɪꜱ ɢʀᴏᴜᴘ.. "
            "ᴛʜᴇɴ ꜰɪʀꜱᴛ ʏᴏᴜ ʜᴀᴠᴇ ᴛᴏ ᴊᴏɪɴ ᴏᴜʀ ᴄʜᴀɴɴᴇʟ ᴛᴏ ᴍᴇꜱꜱᴀɢᴇ ʜᴇʀᴇ 💯</b>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟ ✅", url=f_link)],
                [InlineKeyboardButton("🌀 ᴛʀʏ ᴀɢᴀɪɴ 🌀",
                                      callback_data=f"checksub_{message.from_user.id}")],
            ]),
        )
        await message.delete()
        return False
    except Exception as e:
        if admin:
            try:
                await bot.send_message(chat_id=admin, text=f"❌ Error in Fsub:\n`{str(e)}`")
            except Exception:
                pass
        return False
    else:
        return True


async def get_connected_channels_count():
    grp_col, _, _ = _get_cols()
    pipeline = [
        {"$project": {"count": {"$size": {"$ifNull": ["$channels", []]}}}},
        {"$group": {"_id": None, "total": {"$sum": "$count"}}},
    ]
    result = await grp_col.aggregate(pipeline).to_list(length=1)
    return result[0]["total"] if result else 0


async def create_indexes():
    try:
        _, _, dlt_col = _get_cols()
        await dlt_col.create_index("time")
        logger.info("Database indexes OK")
    except Exception as e:
        logger.warning(f"Index warning: {e}")


async def get_setting(key: str, default=None):
    """Get a bot setting from the Settings collection."""
    global _dbclient
    if _dbclient is None:
        return default
    try:
        db = _dbclient["Channel-Filter"]
        doc = await db["Settings"].find_one({"_id": key})
        return doc["value"] if doc else default
    except Exception:
        return default


async def set_setting(key: str, value) -> None:
    """Upsert a bot setting into the Settings collection."""
    global _dbclient
    if _dbclient is None:
        raise RuntimeError("Database not connected")
    db = _dbclient["Channel-Filter"]
    await db["Settings"].update_one({"_id": key}, {"$set": {"value": value}}, upsert=True)


async def record_failed_search(query: str, chat_id: int, chat_title: str) -> None:
    """Record a failed search query for daily summary reporting."""
    global _dbclient
    if _dbclient is None:
        return
    try:
        import datetime
        db = _dbclient["Channel-Filter"]
        col = db["FailedSearches"]
        await col.update_one(
            {"query_lower": query.strip().lower()},
            {
                "$inc": {"count": 1},
                "$set": {"query": query.strip(), "last_chat_id": chat_id, "last_chat_title": chat_title},
                "$setOnInsert": {"first_seen": datetime.datetime.utcnow()},
                "$push": {"chats": {"$each": [{"chat_id": chat_id, "title": chat_title}], "$slice": -10}},
            },
            upsert=True,
        )
    except Exception:
        pass


async def get_daily_summary(top_n: int = 10) -> list:
    """Return top N failed search queries sorted by count descending."""
    global _dbclient
    if _dbclient is None:
        return []
    try:
        db = _dbclient["Channel-Filter"]
        col = db["FailedSearches"]
        cursor = col.find({}, {"query": 1, "count": 1, "last_chat_title": 1}).sort("count", -1).limit(top_n)
        return await cursor.to_list(length=top_n)
    except Exception:
        return []


async def reset_failed_searches() -> None:
    """Clear all failed search records after daily summary is sent."""
    global _dbclient
    if _dbclient is None:
        return
    try:
        db = _dbclient["Channel-Filter"]
        await db["FailedSearches"].delete_many({})
    except Exception:
        pass