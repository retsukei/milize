import discord
from datetime import datetime
from discord.ext import commands
from discord.commands import SlashCommandGroup
from utils.embeds import info, error, member_info
from utils.checks import check_authority
from utils.constants import AuthorityLevel, ReminderNotification
from utils.autocompletes import get_group_list, get_series_list
from datetime import datetime, timezone

def format_time(hours):
    if hours >= 24:
        days = int(hours // 24)
        remaining_hours = int(hours % 24)
        if remaining_hours > 0:
            return f"{days} days, {remaining_hours} hours"
        else:
            return f"{days} days"
    else:
        return f"{hours:.2f} hours"

def setup(bot):
    bot.add_cog(Member(bot))

class Member(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    Member = SlashCommandGroup(name="member", description="Members related commands.")

    @Member.command(description="Adds a new member to Milize.")
    @check_authority(AuthorityLevel.Owner)
    async def add(self,
                  ctx,
                  user: discord.User,
                  authority: discord.Option(int, choices=AuthorityLevel.to_choices())):
        await ctx.defer()

        member_id = ctx.bot.database.members.add(str(user.id), authority)
        if member_id:
            return await ctx.respond(embed=info(f"<@{user.id}> has been added to members with authority level `{AuthorityLevel.to_string(authority)}`."))

        return await ctx.respond(embed=error(f"<@{user.id}> is already added to Milize."))

    @Member.command(description="Removes a member from Milize.")
    @check_authority(AuthorityLevel.Owner)
    async def remove(self,
                     ctx,
                     user: discord.User):
        await ctx.defer()

        member = ctx.bot.database.members.get(str(user.id))
        if not member:
            return await ctx.respond(embed=error(f"{user.mention} is not added to Milize."))

        rows = ctx.bot.database.members.delete(str(user.id))
        if rows is None:
            return await ctx.respond(embed=error(f"Failed to remove {user.mention} from the database."))

        await ctx.respond(embed=info(f"Removed {user.mention} from members."))

    @Member.command(description="Shows member stats.")
    @check_authority(AuthorityLevel.Member)
    async def stats(self,
                    ctx,
                    user: discord.User = None):
        await ctx.defer()

        _user = ctx.author if user is None else user
        member_id = str(_user.id)

        member = ctx.bot.database.members.get(member_id)
        if member is None:
            return await ctx.respond(embed=error(f"<@{_user.id}> is not added to members in Milize."))

        assignments = ctx.bot.database.assignments.get_completed_by_user(member_id) or []
        archived_assignments = ctx.bot.database.assignments.get_completed_by_user_archive(member_id) or []

        all_assignments = assignments + archived_assignments
        total_completed = len(all_assignments)
        total_hours = sum((a.completed_at - a.created_at).total_seconds() / 3600 for a in all_assignments if a.completed_at)
        
        if total_completed > 0:
            average_time = total_hours / total_completed
        else:
            average_time = 0

        def convert_to_utc(dt):
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)

        now = datetime.now(timezone.utc)
        completed_at_dates = [convert_to_utc(a.completed_at) for a in all_assignments if a.completed_at]
        last_job = max(completed_at_dates, default=None)
        last_job_diff = (now - last_job).days if last_job else "N/A"

        qualified_jobs = ctx.bot.database.jobs.get_by_roles([str(role.id) for role in _user.roles])
        qualified_jobs_list = ", ".join(f"`{job}`" for job in qualified_jobs) if qualified_jobs else "None"

        embed = discord.Embed(
            title=f"{_user.display_name}'s profile",
            color=discord.Color.blue()
        )

        embed.add_field(name="Credit Name", value=member.credit_name if member.credit_name else _user.display_name, inline=False)
        embed.add_field(name="Qualified for", value=qualified_jobs_list, inline=False)
        embed.add_field(name="Authority Level", value=AuthorityLevel.to_string(member.authority_level), inline=False)
        embed.add_field(name="Total Completed", value=total_completed, inline=False)
        embed.add_field(name="Total Time / Average", value=f"{format_time(total_hours)} / {format_time(average_time)}", inline=False)
        embed.add_field(name="Last Completed Job", value=f"{last_job_diff} days ago", inline=False)

        embed.set_footer(text=f"Member since {member.created_at.strftime('%Y-%m-%d')}")
        embed.set_thumbnail(url=_user.avatar.url)

        await ctx.respond(embed=embed)

    @Member.command(description="Manage your notification preferences.")
    @check_authority(AuthorityLevel.Member)
    async def notifications(self,
                            ctx,
                            reminder: discord.Option(int, description="Reminds you about your unfinished jobs.", choices=ReminderNotification.to_choices()) = None,
                            jobboard: discord.Option(bool, description="Pings whenever there's a new job posted and you're eligible.") = None,
                            stage: discord.Option(bool, description="Pings you whenever previous stage is completed.") = None):
        await ctx.defer()

        user_id = str(ctx.author.id)
        if reminder is not None or jobboard is not None or stage is not None:
            rows = self.bot.database.members.update_notifications(user_id, reminder, jobboard, stage)
            if rows is None:
                return await ctx.respond(embed=error(f"Failed to update your notification preferences."))
        
        member = self.bot.database.members.get(user_id)
        embed = discord.Embed(
            title="Notification Preferences",
            color=discord.Color.blue()
        )
        
        embed.add_field(name="Reminder Notifications", value=ReminderNotification.to_string(member.reminder_notifications))
        embed.add_field(name="Jobboard Notifications", value="Enabled" if member.jobboard_notifications else "Disabled")
        embed.add_field(name="Stage Notifications", value="Enabled" if member.stage_notifications else "Disabled")
        
        await ctx.respond(embed=embed)

    @Member.command(description="Lets you to subscribe to series' job board notifications.")
    @check_authority(AuthorityLevel.Member)
    async def series_subscribe(self,
                               ctx,
                               group_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_group_list)),
                               series_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_series_list))):
        await ctx.defer()

        member = ctx.bot.database.members.get(str(ctx.author.id))
        if not member:
            return await ctx.respond(embed=error(f"You're not added to members in Milize."))

        if member.jobboard_notifications:
            return await ctx.respond(embed=error(f"Please disable `jobboard_notifications` in `/member notifications` before subscribing to specific series."))

        series = ctx.bot.database.series.get(group_name, series_name)
        if not series:
            return await ctx.respond(embed=error(f"Failed to get series `{series_name}` from `{group_name}`."))

        if ctx.bot.database.subscriptions.is_subscribed(member.member_id, series.series_id):
            return await ctx.respond(embed=error(f"You're already subscribed to the series `{series_name}` from `{group_name}`."))

        subscription_id = ctx.bot.database.subscriptions.new(member.member_id, series.series_id)
        if subscription_id is None:
            return await ctx.respond(embed=error(f"Failed to subscribe to series `{series_name}` from `{group_name}`"))

        await ctx.respond(embed=info(f"Subscribed to `{series_name}` from `{group_name}`.\nYou'll get notified whenever a new job is posted for that series."))

    @Member.command(description="Allows you to unsubscribe from a series' job board notifications.")
    @check_authority(AuthorityLevel.Member)
    async def series_unsubscribe(self,
                                ctx,
                                group_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_group_list)),
                                series_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_series_list))):
        await ctx.defer()

        member = ctx.bot.database.members.get(str(ctx.author.id))
        if not member:
            return await ctx.respond(embed=error(f"You're not added to members in Milize."))

        series = ctx.bot.database.series.get(group_name, series_name)
        if not series:
            return await ctx.respond(embed=error(f"Series `{series_name}` from `{group_name}` not found."))

        if not ctx.bot.database.subscriptions.is_subscribed(member.member_id, series.series_id):
            return await ctx.respond(embed=error(f"You're not subscribed to the series `{series_name}` from `{group_name}`."))

        rows = ctx.bot.database.subscriptions.delete(member.member_id, series.series_id)
        if rows is None:
            return await ctx.respond(embed=error(f"Failed to unsubscribe from series `{series_name}` from `{group_name}`."))

        await ctx.respond(embed=info(f"Successfully unsubscribed from `{series_name}` from `{group_name}`.\nYou will no longer receive notifications for this series."))

    @Member.command(description="Removes all your subscriptions from series' job board notifications.")
    @check_authority(AuthorityLevel.Member)
    async def remove_subscriptions(self, ctx):
        await ctx.defer()

        member = ctx.bot.database.members.get(str(ctx.author.id))
        if not member:
            return await ctx.respond(embed=error(f"You're not added to members in Milize."))

        rows = ctx.bot.database.subscriptions.delete_all(member.member_id)
        if rows is None:
            return await ctx.respond(embed=error("Failed to remove your subscriptions."))

        await ctx.respond(embed=info("Successfully removed all your subscriptions.\nYou will no longer receive any job board notifications for subscribed series."))

    @Member.command(description="Shows all your subscriptions.")
    @check_authority(AuthorityLevel.Member)
    async def subscriptions(self, ctx):
        await ctx.defer()

        member = ctx.bot.database.members.get(str(ctx.author.id))
        if not member:
            return await ctx.respond(embed=error("You're not added to members in Milize."))

        subscriptions = ctx.bot.database.subscriptions.get_all(member.member_id)

        if not subscriptions:
            return await ctx.respond(embed=error("You're not subscribed to any series."))

        # Create an embed
        embed = discord.Embed(
            title="Your Subscriptions",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )

        for sub in subscriptions:
            series_name = sub.series_name
            subscribed_at = f"<t:{int(sub.subscribed_at.timestamp())}:f>"
            embed.add_field(name=series_name, value=f"Subscribed at: {subscribed_at}", inline=False)

        embed.set_thumbnail(url=ctx.author.avatar.url)

        await ctx.respond(embed=embed)

    @Member.command(description="Sets your credit name.")
    @check_authority(AuthorityLevel.Member)
    async def credit_name(self, ctx, credit_name: discord.Option(str, description="Type 'none' to remove.")):
        await ctx.defer()

        if credit_name.lower() == 'none':
            credit_name = None
        
        rows = ctx.bot.database.members.set_credit_name(str(ctx.author.id), credit_name)
        if rows is None:
            return await ctx.respond(embed=error("Failed to set the credit name."))

        if credit_name is None: await ctx.respond(embed=member_info("Your custom credit name has been removed. Your Discord display name will be used."))
        else: await ctx.respond(embed=member_info(f"Your credit name has been changed to `{credit_name}`."))

    @Member.command(description="Sets authority level for a member.")
    @check_authority(AuthorityLevel.Owner)
    async def set_authority(self,
                            ctx,
                            user: discord.User,
                            authority: discord.Option(int, choices=AuthorityLevel.to_choices())):
        await ctx.defer()

        member = ctx.bot.database.members.get(str(user.id))
        if member is None:
            return await ctx.respond(embed=error(f"<@{user.id}> is not added to members in Milize."))

        rows = ctx.bot.database.members.set_authority(str(user.id), authority)
        if rows and rows > 0:
            return await ctx.respond(embed=info(f"Authority level has been updated for <@{user.id}> to `{AuthorityLevel.to_string(authority)}`"))

        await ctx.respond(embed=error(f"Failed to update authority level for <@{user.id}>"))