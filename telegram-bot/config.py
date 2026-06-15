import os
import base64
import struct
import logging

logger = logging.getLogger(__name__)

API_ID    = int(os.environ.get("API_ID", 0))
API_HASH  = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
OWNER_ID  = int(os.environ.get("OWNER_ID", 0))
LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL", 0))

MONGODB_PASSWORD = os.environ.get("MONGODB_PASSWORD", "")
_raw_uri = os.environ.get("MONGO_URI", "")
if MONGODB_PASSWORD:
    MONGO_URI = (
        f"mongodb+srv://abdulazizshaik521:{MONGODB_PASSWORD}"
        f"@azizthekiller.h74ev.mongodb.net/?appName=Azizthekiller"
    )
elif _raw_uri:
    MONGO_URI = _raw_uri
else:
    MONGO_URI = ""

CHANNEL        = os.environ.get("UPDATES_CHANNEL", "")
BACKUP_CHANNEL = os.environ.get("BACKUP_CHANNEL", "")
RESULTS_CHANNEL = int(os.environ.get("RESULTS_CHANNEL", 0))

SEARCH_REPLY_TTL = int(os.environ.get("SEARCH_REPLY_TTL", 600))  # 10 mins default
WELCOME_TTL      = 120
HEALTH_PORT = int(os.environ.get("HEALTH_PORT", os.environ.get("PORT", 5000)))
PORT        = HEALTH_PORT

_PYRO_FORMAT = ">BI?256sQ?"
_PYRO_SIZE   = struct.calcsize(_PYRO_FORMAT)

def _convert_custom_session(raw_b64: str) -> str:
    try:
        data = base64.urlsafe_b64decode(raw_b64 + "=" * (-len(raw_b64) % 4))
        if len(data) == _PYRO_SIZE:
            return raw_b64
        dc_id  = data[0]
        ip_len = struct.unpack(">H", data[1:3])[0]
        offset = 3 + ip_len + 2
        auth_key = data[offset:offset + 256]
        if len(auth_key) != 256:
            return raw_b64
        packed = struct.pack(
            _PYRO_FORMAT,
            dc_id,
            API_ID,
            False,
            auth_key,
            OWNER_ID,
            False,
        )
        converted = base64.urlsafe_b64encode(packed).decode().rstrip("=")
        logger.info("Session converted from custom format → Pyrogram format (dc_id=%d)", dc_id)
        return converted
    except Exception as e:
        logger.warning("Session conversion failed (%s) — using raw value", e)
        return raw_b64


def _normalise_session(s: str) -> str:
    if not s:
        return s
    raw = s[1:] if (s.startswith("1") and len(s) > 1) else s
    return _convert_custom_session(raw)


_raw_session = os.environ.get("SESSION") or os.environ.get("SESSION_SECRET", "")
SESSION = _normalise_session(_raw_session)
