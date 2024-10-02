from motor.motor_asyncio import AsyncIOMotorClient
from bot import Var

class MongoDB:
    def __init__(self, uri, database_name):
        self.__client = AsyncIOMotorClient(uri)
        self.__db = self.__client[database_name]
        self.__animes = self.__db.animes[Var.BOT_TOKEN.split(':')[0]]

    async def getAnime(self, ani_id):
        # Retrieve an anime document by its ID
        return await self.__animes.find_one({'_id': ani_id}) or {}

    async def saveAnime(self, ani_id, ep, qual, post_id=None):
        # Update or insert anime episode information
        quals = (await self.getAnime(ani_id)).get(ep, {qual: False for qual in Var.QUALS})
        quals[qual] = True
        await self.__animes.update_one({'_id': ani_id}, {'$set': {ep: quals}}, upsert=True)
        if post_id:
            await self.__animes.update_one({'_id': ani_id}, {'$set': {"msg_id": post_id}}, upsert=True)

    async def getMessageId(self, ani_id):
        # Retrieve the message ID for a specific anime ID
        anime_doc = await self.getAnime(ani_id)
        return anime_doc.get("msg_id")

    async def reboot(self):
        # Drop the collection (for debugging or resetting purposes)
        await self.__animes.drop()

# Initialize MongoDB instance
db = MongoDB(Var.MONGO_URI, "FZAutoAnimes")
