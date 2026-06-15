import asyncio
import logging
from imdb import Cinemagoer

logger = logging.getLogger(__name__)
ia = Cinemagoer()


def _sync_search(query: str) -> list:
    results = ia.search_movie(query)
    movies = []
    for r in results[:5]:
        title = r.get("title", "")
        year  = r.get("year", "")
        label = f"{title} ({year})" if year else title
        movies.append({"id": r.movieID, "title": label})
    return movies


async def search_imdb(query: str) -> list:
    try:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _sync_search, query)
    except Exception as e:
        logger.warning(f"IMDb search error: {e}")
        return []
