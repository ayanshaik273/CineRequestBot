import logging
import urllib.request
import urllib.parse
import json

logger = logging.getLogger(__name__)


async def google_spell_check(query: str) -> str:
    try:
        encoded = urllib.parse.quote(query)
        url = (
            f"https://www.google.com/complete/search"
            f"?q={encoded}&client=gws-wiz&xssi=t"
        )
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw = resp.read().decode("utf-8")
            raw = raw.lstrip(")]}'\n")
            data = json.loads(raw)
            suggestions = data[0]
            if suggestions:
                first = suggestions[0][0]
                import re
                clean = re.sub(r"<[^>]+>", "", first).strip()
                if clean.lower() != query.lower():
                    return clean
    except Exception as e:
        logger.debug(f"Spell check error: {e}")
    return ""
