import logging
import re
import json
import aiohttp

logger = logging.getLogger(__name__)


async def google_spell_check(query: str) -> str:
    try:
        encoded = query.replace(" ", "+")
        url = (
            f"https://www.google.com/complete/search"
            f"?q={encoded}&client=gws-wiz&xssi=t"
        )
        headers = {"User-Agent": "Mozilla/5.0"}
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, headers=headers, timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                raw = await resp.text(encoding="utf-8")
                raw = raw.lstrip(")]}'\n")
                data = json.loads(raw)
                suggestions = data[0]
                if suggestions:
                    first = suggestions[0][0]
                    clean = re.sub(r"<[^>]+>", "", first).strip()
                    if clean.lower() != query.lower():
                        return clean
    except Exception as e:
        logger.debug(f"Spell check error: {e}")
    return ""
