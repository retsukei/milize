import discord
from datetime import datetime, timedelta, timezone
from discord.ext import tasks
import dotenv
import os
import textwrap
import shutil

from database import DatabaseManager
from mangadex import MangaDexAPI
import utils

bot = discord.Bot(intents=discord.Intents.all())
dotenv.load_dotenv()

def should_notify(series_name, chapter, series_job):
    if series_job.job_type == utils.constants.JobType.Typesetting or series_job.job_type == utils.constants.JobType.TypesettingSFX:
        # Check if pr, clrd done.
        rd_type = bot.database.jobs.get_added_by_type(series_name, utils.constants.JobType.Redrawing)
        cl_type = bot.database.jobs.get_added_by_type(series_name, utils.constants.JobType.Cleaning)
        pr_type = bot.database.jobs.get_added_by_type(series_name, utils.constants.JobType.Proofreading)

        notify = True

        if rd_type:
            assignment = bot.database.assignments.get(chapter.chapter_id, rd_type[0].series_job_id)
            if not assignment or assignment.status != utils.constants.JobStatus.Completed:
                notify = False

        if cl_type:
            assignment = bot.database.assignments.get(chapter.chapter_id, cl_type[0].series_job_id)
            if not assignment or assignment.status != utils.constants.JobStatus.Completed:
                notify = False

        if pr_type:
            assignment = bot.database.assignments.get(chapter.chapter_id, pr_type[0].series_job_id)
            if not assignment or assignment.status != utils.constants.JobStatus.Completed:
                notify = False

        return notify
    elif series_job.job_type == utils.constants.JobType.Quality:
        # Check if ts/sfx done.
        ts_type = bot.database.jobs.get_added_by_type(series_name, utils.constants.JobType.Typesetting)
        sfx_type = bot.database.jobs.get_added_by_type(series_name, utils.constants.JobType.TypesettingSFX)

        notify = True

        if ts_type:
            assignment = bot.database.assignments.get(chapter.chapter_id, ts_type[0].series_job_id)
            if not assignment or assignment.status != utils.constants.JobStatus.Completed:
                notify = False

        if sfx_type:
            assignment = bot.database.assignments.get(chapter.chapter_id, sfx_type[0].series_job_id)
            if not assignment or assignment.status != utils.constants.JobStatus.Completed:
                notify = False

        return notify
    elif series_job.job_type == utils.constants.JobType.Proofreading:
        # Check if tl done.
        tl_type = bot.database.jobs.get_added_by_type(series_name, utils.constants.JobType.Translation)

        if tl_type:
            assignment = bot.database.assignments.get(chapter.chapter_id, tl_type[0].series_job_id)
            if not assignment or assignment.status != utils.constants.JobStatus.Completed:
                return False

    return True

def convert_to_utc(dt):
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def reminder_timedelta(reminder):
    if reminder == 1:
        return timedelta(days=3)
    elif reminder == 2:
        return timedelta(days=7)
    else:
        return timedelta(days=14)

@tasks.loop(hours=1)
async def milize_main_task():
    """
    now = datetime.now(timezone.utc)
    members = bot.database.members.get_with_reminder_notif()
    if members:
        for member in members:
            assignments = bot.database.assignments.get_by_user_uncompleted(member.discord_id)
            if assignments:
                for assignment in assignments:
                    last_reminder = assignment.created_at if assignment.reminded_at is None else assignment.reminded_at
                    next_reminder = last_reminder + reminder_timedelta(member.reminder_notifications)

                    if now >= convert_to_utc(next_reminder):
                        channel = bot.get_channel(int(os.getenv("MilizeChannelId")))
                        if channel:
                            chapter = bot.database.chapters.get_by_id(assignment.chapter_id)
                            series = bot.database.series.get_by_id(chapter.series_id)
                            series_job = bot.database.jobs.get_added_by_id(assignment.series_job_id)
                            if should_notify(series.series_name, chapter, series_job):
                                await channel.send(f"<@{member.discord_id}>, you have unfinished task(s) for chapter `{chapter.chapter_name}` in series `{series.series_name}`.")

                        bot.database.assignments.update_reminder(assignment.assignment_id)
    """

    jobboard_posts = bot.database.boardposts.get_for_removal()
    if jobboard_posts:
        for post in jobboard_posts:
            channel_id = post.jobboard_channel
            message_id = post.message_id

            try:
                channel = bot.get_channel(int(channel_id))
                if channel is None:
                    channel = await bot.fetch_channel(int(channel_id))

                message = await channel.fetch_message(int(message_id))
                await message.delete()
                bot.database.boardposts.delete(post.boardpost_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass

@tasks.loop(hours=1)
async def inactivity_task():
    now = datetime.now(timezone.utc)

    group_lead_id = int(os.getenv("StaffGroupLeadRoleId"))
    dep_lead_id = int(os.getenv("StaffDepLeadRoleId"))

    full_staff_id = int(os.getenv("StaffFullRoleId"))
    probationary_staff_id = int(os.getenv("StaffProbationaryRoleId"))
    trial_staff_id = int(os.getenv("StaffTrialRoleId"))

    members = bot.database.members.get_all()

    for member in members:
        assignments = bot.database.assignments.get_by_user(member.discord_id)
        archived_assignments = bot.database.assignments.get_by_user_archive(member.discord_id)

        all_assignments = assignments + archived_assignments

        active_assignments = [a for a in assignments if a.status < 2]
        if active_assignments:
            continue

        last_completed_at = max(
            (a.completed_at for a in all_assignments if a.completed_at), default=None
        )

        if not last_completed_at:
            last_completed_at = member.created_at

        time_inactive = (now - last_completed_at).days
        if time_inactive < 30 or member.reminded_at and (now - member.reminded_at).days < 1:
            continue

        guild = bot.get_guild(int(os.getenv("StaffGuildId")))
        try:
            user = await guild.fetch_member(int(member.discord_id))
            if user:
                user_roles = [role.id for role in user.roles]
                if group_lead_id in user_roles or dep_lead_id in user_roles:
                    continue

                if full_staff_id in user_roles and time_inactive >= 90:
                    if member.reminded_at and (now - member.reminded_at).days < 7:
                        continue

                    bot.database.members.move_to_retired(member.member_id, [str(role.id) for role in user.roles if role.id != guild.id])
                    await user.remove_roles(*user.roles[1:], reason="Inactivity. Moved to retired staff.")
                    
                    role = guild.get_role(int(os.getenv("StaffRetiredRoleId")))
                    if role:
                        await user.add_roles(role, reason="Inactivity. Moved to retired staff.")

                    inactivity_channel = bot.get_channel(int(os.getenv("InactivityChannelId")))
                    if inactivity_channel:
                        embed = discord.Embed(
                            title="Inactivity Notification",
                            description=(f"❌ Moved full staff {user.mention} to retired due to inactivity."),
                            color=discord.Color.yellow()
                        )
                        await inactivity_channel.send(embed=embed)

                    message = """
                    Hello! In case you've forgotten, I am the bot that manages `Keiretsu`.

                    Due to your inactivity over the past 3 months, you have been moved from the `full staff` category to `retired`. All your roles were automatically removed. This is a necessary step to accurately track our active staff members.

                    If you'd like to start working again or believe this was done in error, feel free to use the `/member restore` command. Your roles will be reinstated, but they will be removed again in `7 days` unless you claim a job.
                    """
                    await user.send(textwrap.dedent(message))
                elif probationary_staff_id in user_roles and time_inactive >= 30:
                    if member.reminded_at and (now - member.reminded_at).days >= 7:
                        # Remove all roles. Delete from members.
                        await user.remove_roles(*user.roles[1:], reason="Inactivity. Removed from probationary.")
                        bot.database.members.delete(member.discord_id)

                        inactivity_channel = bot.get_channel(int(os.getenv("InactivityChannelId")))
                        if inactivity_channel:
                            embed = discord.Embed(
                                title="Inactivity Notification",
                                description=(f"👞💨 Removed (laid off) probationary staff {user.mention} from staff due to inactivity."),
                                color=discord.Color.yellow()
                            )
                            await inactivity_channel.send(embed=embed)
                        continue
                    
                    if member.reminded_at:
                        continue

                    bot.database.members.move_to_retired(member.member_id, [str(role.id) for role in user.roles if role.id != guild.id])
                    await user.remove_roles(*user.roles[1:], reason="Inactivity. Moved to retired staff.")
                    
                    role = guild.get_role(int(os.getenv("StaffRetiredRoleId")))
                    if role:
                        await user.add_roles(role, reason="Inactivity. Moved to retired staff.")

                    inactivity_channel = bot.get_channel(int(os.getenv("InactivityChannelId")))
                    if inactivity_channel:
                        embed = discord.Embed(
                            title="Inactivity Notification",
                            description=(f"❌ Moved probationary staff {user.mention} to retired due to inactivity."),
                            color=discord.Color.yellow()
                        )
                        await inactivity_channel.send(embed=embed)

                    message = """
                    Hello! In case you've forgotten, I am the bot that manages `Keiretsu`.

                    Due to your inactivity over the past month, you have been moved from the `probationary staff` category to `retired`. All your roles were automatically removed. This is a necessary step to accurately track our active staff members.

                    If you'd like to start working again or believe this was done in error, feel free to use the `/member restore` command. Your roles will be reinstated, but you will be removed from staff completely in `7 days` unless you claim a job within that period.
                    """
                    await user.send(textwrap.dedent(message))
                elif trial_staff_id in user_roles and time_inactive >= 30:
                    # Lay off silently.
                    await user.remove_roles(*user.roles[1:], reason="Inactivity. Removed from trial.")
                    bot.database.members.delete(member.discord_id)

                    inactivity_channel = bot.get_channel(int(os.getenv("InactivityChannelId")))
                    if inactivity_channel:
                        embed = discord.Embed(
                            title="Inactivity Notification",
                            description=(f"👞💨 Removed (laid off) trial staff {user.mention} from staff due to inactivity."),
                            color=discord.Color.yellow()
                        )
                        await inactivity_channel.send(embed=embed)

        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass

@tasks.loop(minutes=1)
async def scheduled_upload_task():
    scheduled_upload = bot.database.chapters.get_active_scheduled_upload()
    if scheduled_upload:
        # Remove from the database immediately.
        bot.database.chapters.delete_upload_schedule(scheduled_upload.upload_id)

        channel = bot.get_channel(int(os.getenv("MilizeChannelId")))
        if channel:
            embed = discord.Embed(
                title=":yellow_square: Upload Scheduler",
                description=f"Uploading chapter `{scheduled_upload.chapter_number}` in `{scheduled_upload.series_name}` by `{scheduled_upload.group_name}`\nStatus: `Preparing...`",
                color=discord.Color.blue()
            )
            message = await channel.send(embed=embed)

            session_id = bot.mangadex.check_for_session()
            if session_id:
                bot.mangadex.abandon_session(session_id)

            session_id = bot.mangadex.create_session(scheduled_upload.group_ids, scheduled_upload.series_id)
            if not session_id:
                embed = discord.Embed(
                    title=":red_square: Upload Scheduler",
                    description=f"Uploading chapter `{scheduled_upload.chapter_number}` in `{scheduled_upload.series_name}` by `{scheduled_upload.group_name}`\nStatus: `Failed to create session.`",
                    color=discord.Color.blue()
                )
                await message.edit(embed=embed)
                return

            embed.description = f"Uploading chapter `{scheduled_upload.chapter_number}` in `{scheduled_upload.series_name}` by `{scheduled_upload.group_name}`\nStatus: `Uploading...`"
            await message.edit(embed=embed)
            
            chapter_id = bot.mangadex.upload_chapter(session_id, scheduled_upload.volume_number, scheduled_upload.chapter_number, scheduled_upload.chapter_name, scheduled_upload.language, scheduled_upload.folder_name, 1)

            if not chapter_id:
                embed = discord.Embed(
                    title=":red_square: Upload Scheduler",
                    description=f"Uploading chapter `{scheduled_upload.chapter_number}` in `{scheduled_upload.series_name}` by `{scheduled_upload.group_name}`\nStatus: `Failed to upload the chapter.`",
                    color=discord.Color.blue()
                )
                await message.edit(embed=embed)
                return

            embed = discord.Embed(
                title=":green_square: Upload Scheduler",
                description=f"Uploading chapter `{scheduled_upload.chapter_number}` in `{scheduled_upload.series_name}` by `{scheduled_upload.group_name}`\nStatus: `Uploaded.`",
                color=discord.Color.blue()
            )
            await message.edit(embed=embed)
            await channel.send(content=f"<@{scheduled_upload.discord_id}> chapter is uploaded: https://mangadex.org/chapter/{chapter_id}")

            if os.path.exists(scheduled_upload.folder_name):
                shutil.rmtree(scheduled_upload.folder_name)

@bot.event
async def on_application_command_error(ctx, error):
    if isinstance(error, discord.errors.CheckFailure):
        await ctx.respond(embed=utils.embeds.error("You do not have authority to perform this action."))
    else:
        raise error

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    bot.add_view(utils.views.JobboardView())

    # Tasks
    milize_main_task.start()
    inactivity_task.start()
    scheduled_upload_task.start()

@bot.command(description="Sends the bot latency.")
async def ping(ctx):
    await ctx.respond(f'Pong! {round(bot.latency * 1000)}ms')

bot.load_extension('cogs.group')
bot.load_extension('cogs.series')
bot.load_extension('cogs.chapter')
bot.load_extension('cogs.jobs')
bot.load_extension('cogs.member')
bot.database = DatabaseManager(database=os.getenv("PostgresDatabase"), host=os.getenv("PostgresHost"), password=os.getenv("PostgresPassword"), user=os.getenv("PostgresUser"))

bot.mangadex = MangaDexAPI()
bot.mangadex.login(client_id=os.getenv("MangaDexId"), client_secret=os.getenv("MangaDexSecret"), username=os.getenv("MangaDexLogin"), password=os.getenv("MangaDexPassword"))

bot.run(os.getenv("DiscordToken"))