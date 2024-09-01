import discord
from datetime import datetime, timedelta, timezone
from discord.ext import commands, tasks
import dotenv
import os

from database import DatabaseManager
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
                                await channel.send(f"<@{member.discord_id}>, you have unfinished task for chapter `{chapter.chapter_name}` in series `{series.series_name}`.")

                        bot.database.assignments.update_reminder(assignment.assignment_id)

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
    milize_main_task.start()

@bot.command(description="Sends the bot latency.")
async def ping(ctx):
    await ctx.respond(f'Pong! {round(bot.latency * 1000)}ms')

bot.load_extension('cogs.group')
bot.load_extension('cogs.series')
bot.load_extension('cogs.chapter')
bot.load_extension('cogs.jobs')
bot.load_extension('cogs.member')
bot.database = DatabaseManager(database=os.getenv("PostgresDatabase"), host=os.getenv("PostgresHost"), password=os.getenv("PostgresPassword"), user=os.getenv("PostgresUser"))

bot.run(os.getenv("DiscordToken"))