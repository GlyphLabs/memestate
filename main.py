from typing import Union, Deque, List

from cachetools import TTLCache, cached
from fastapi import FastAPI
from collections import deque
from fastapi_utils.tasks import repeat_every
from random import choice
from aiohttp import ClientSession
from ormsgpack import packb, unpackb

app = FastAPI()


class Memes:
    def __init__(self):
        self.subreddits = (
            "memes",
            "dankmemes",
            "me_irl",
            "funny",
            "wholesomememes",
            "antimeme",
        )
        self.memecache: TTLCache[str, Deque[bytes]] = TTLCache(100, 3600)

    @property
    @cached(cache=TTLCache(1, 3600))
    def allmemes(self) -> List:
        meme_list = []
        for meme_subreddit in self.memecache.keys():
            for meme in self.memecache[meme_subreddit]:
                meme_list.append(meme)
        return meme_list

    async def get_random(self, subreddit: str = None, amount: int = 0):
        if subreddit and not self.memecache.get(subreddit):
            await self.get_memes_from_sub(subreddit)
        if not amount:
            if not subreddit:
                return unpackb(choice(self.allmemes))
            return unpackb(choice(self.memecache.get(subreddit)))
        return [unpackb(choice(self.allmemes)) for _ in range(amount)]

    async def get_memes_from_sub(self, sub: str):
        async with ClientSession() as session:
            d = await session.get(f"https://www.reddit.com/r/{sub}/hot.json?limit=100")
            data = await d.json()
            memes = (
                i["data"] for i in data["data"]["children"] if not i.get("over_18")
            )
            if sub not in self.memecache:
                self.memecache[sub] = deque(maxlen=1024)
            for meme in memes:
                m = packb(
                    {
                        "title": meme["title"],
                        "author": meme["author"],
                        "subreddit": sub,
                        "postLink": f"https://reddit.com{meme['permalink']}",
                        "ups": meme["ups"],
                        "imageUrl": None
                        if (not meme.get("url", None))
                        or meme["permalink"] in meme["url"]
                        else meme["url"],
                    }
                )
                self.memecache[sub].appendleft(m)


meme = Memes()


@app.on_event("startup")
@repeat_every(seconds=3600)
async def refresh_cache() -> dict:
    print("fetching memes!")
    for subreddit in meme.subreddits:
        print(f"getting memes from r/{subreddit}!")
        await meme.get_memes_from_sub(subreddit)
    print(f"done! got {len(meme.allmemes)} memes :>")


@app.get("/")
async def random_meme(amount: Union[int, None] = None):
    return await meme.get_random(amount=amount)


@app.get("/{subreddit}")
async def random_meme_from_subreddit(subreddit: str, amount: Union[int, None] = None):
    return await meme.get_random(subreddit, amount)