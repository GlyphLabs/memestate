from typing import Union, Deque, List

from cachetools import TTLCache
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
        self._http = ClientSession()
        self.memecache: TTLCache[str, Deque[bytes]] = TTLCache(100, 3600)
        # self.allmemes: Deque[bytes] = deque()

    @property
    def allmemes(self) -> List:
        return [unpackb(meme) for meme in [self.memecache[subreddit] for subreddit in self.memecache.keys()]]

    async def get_random(self, subreddit: str = None):
        if not subreddit:
            return {"res":choice(self.allmemes)}
        if not (memes := self.memecache.get(subreddit)):
            await self.__get_memes_from_sub(subreddit)
        return {"res":unpackb(choice(memes))}

    async def get_memes_from_sub(self, sub: str):
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
                        "url": meme["url"],
                    }
                )
                self.memecache[sub].appendleft(m)
                if sub.lower() != "showerthoughts":
                    self.allmemes.appendleft(m)
            print("done")
meme = Memes()

@app.on_event('startup')
@repeat_every(seconds=3600)
async def refresh_cache() -> dict:
    print("i'm getting the memes rn!")
    for subreddit in meme.subreddits:
        print(f"getting memes from r/{subreddit}") 
        await meme.get_memes_from_sub(subreddit)
    print(f"done! got {len(meme.allmemes)} memes :>")

@app.get("/")
async def read_root():
    return await meme.get_random()


@app.get("/items/{item_id}")
def read_item(item_id: int, q: Union[str, None] = None):
    return {"item_id": item_id, "q": q}
