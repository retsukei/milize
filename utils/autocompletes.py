import discord
from natsort import natsorted

async def get_group_list(ctx: discord.AutocompleteContext):
    groups = ctx.bot.database.groups.get_all()

    if groups:
        return [group.group_name for group in groups]

    return []

async def get_series_list(ctx: discord.AutocompleteContext):
    series_list = ctx.bot.database.series.get_by_group_name(ctx.options['group_name'])

    if series_list:
        return [series.series_name for series in series_list]

    return []

async def get_chapter_list(ctx: discord.AutocompleteContext):
    chapters = ctx.bot.database.chapters.get_by_series_name(ctx.options['series_name'])

    if chapters:
        return natsorted([chapter.chapter_name for chapter in chapters])

    return []

async def get_unadded_jobs(ctx: discord.AutocompleteContext):
    jobs = ctx.bot.database.jobs.get_unadded_all(ctx.options['series_name'])

    if jobs:
        return [job.job_name for job in jobs]

    return []

async def get_added_jobs(ctx: discord.AutocompleteContext):
    jobs = ctx.bot.database.jobs.get_added_all(ctx.options['series_name'])

    if jobs:
        return [job.job_name for job in jobs]

    return []

async def get_job_list(ctx: discord.AutocompleteContext):
    jobs = ctx.bot.database.jobs.get_all()

    if jobs:
        return [job.job_name for job in jobs]

    return []