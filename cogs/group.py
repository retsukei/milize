import discord
from discord.ext import commands
from discord.commands import SlashCommandGroup
from utils.embeds import info, error
from utils.checks import check_authority
from utils.constants import AuthorityLevel
from utils.autocompletes import get_group_list

def setup(bot):
    bot.add_cog(Group(bot))

class Group(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    Group = SlashCommandGroup(name="group", description="Group related commands.")

    @Group.command(description="Adds a new group to Milize.")
    @check_authority(AuthorityLevel.Owner)
    async def add(self, ctx, group_name: str, discord: str = None, website: str = None):
        await ctx.defer()

        group_id = ctx.bot.database.groups.new(group_name, discord, website, ctx.author.id)
        if not group_id:
            await ctx.respond(embed=error(f"Group `{group_name}` is already in the database (or errored while adding).\nPlease use `/group edit` to modify already existing group."))
        else:
            await ctx.respond(embed=info(f"Group `{group_name}` has been added to the database."))

    @Group.command(description="Lists all groups in Milize.")
    async def list(self, ctx):
        await ctx.defer()

        groups = ctx.bot.database.groups.get_all()

        output = []
        for i, (_, group_name, discord, website, creator_id, created_at) in enumerate(groups, start=1):
            creator = await ctx.bot.fetch_user(creator_id)
            line = f"**{i}\\. {group_name}** by {creator.display_name}"

            if discord and website:
                line += f"\n[Discord]({discord}) • [Website]({website})"
            elif discord:
                line += f"\n[Discord]({discord})"
            elif website:
                line += f"\n[Website]({website})"

            output.append(line)

        await ctx.respond(embed=info("\n\n".join(output), title="Groups in Milize"))

    @Group.command(description="Edits information of the existed group.")
    @check_authority(AuthorityLevel.Owner)
    async def edit(self,
                    ctx,
                    group_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_group_list)),
                    new_name: str = None,
                    new_discord: str = None,
                    new_website: str = None):
        await ctx.defer()

        if not new_name and not new_discord and not new_website:
            return await ctx.respond(embed=error("You must provide at least one of `new_name`, `new_discord` or `new_website`."))

        rows = ctx.bot.database.groups.update(group_name, new_name, new_discord, new_website)

        if rows and rows > 0:
            return await ctx.respond(embed=info(f"Group `{group_name}` has been updated."))

        await ctx.respond(embed=error(f"Failed to update group `{group_name}` (or no changes were made.)"))

    @Group.command(description="Deletes a group from Milize.")
    @check_authority(AuthorityLevel.Owner)
    async def delete(self,
                    ctx,
                    group_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_group_list))):
        await ctx.defer()

        rows = ctx.bot.database.groups.delete(group_name)
        if rows and rows > 0:
            return await ctx.respond(embed=info(f"Group `{group_name}` has been removed from Milize."))

        await ctx.respond(embed=error(f"Group `{group_name}` not found in the database."))