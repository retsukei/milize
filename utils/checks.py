import os
from discord.ext import commands
from functools import wraps
from .embeds import error

def check_connection(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self.cursor:
            print("No connection to the database.")
            return None
        return func(self, *args, **kwargs)
    return wrapper

def check_authority(minimum_level):
    async def predicate(ctx):
        if str(ctx.author.id) == os.getenv("DiscordOwnerId") or str(ctx.author.id) == os.getenv("DiscordDevId"):
            return True

        authority = ctx.bot.database.members.get_authority(str(ctx.author.id))
        if authority is None or authority < minimum_level:
            return False
        return True

    return commands.check(predicate)