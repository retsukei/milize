import discord
import requests
import re
import os
from discord.ext import commands
from discord.commands import SlashCommandGroup
from natsort import natsorted
from utils.embeds import info, error
from utils.checks import check_authority
from utils.constants import AuthorityLevel, StaffLevel
from utils.autocompletes import get_group_list, get_series_list, get_added_jobs, get_chapter_list
from utils.views import JobboardView

def setup(bot):
    bot.add_cog(Chapter(bot))

class Chapter(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    Chapter = SlashCommandGroup(name="chapter", description="Chapter related commands.")

    @Chapter.command(description="Adds a chapter to a series.")
    @check_authority(AuthorityLevel.ProjectManager)
    async def add(self,
                    ctx,
                    group_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_group_list)),
                    series_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_series_list)),
                    chapter_name: str):
        await ctx.defer()

        chapter_count = ctx.bot.database.series.count_chapters(series_name)
        if chapter_count and chapter_count >= 25:
            return await ctx.respond(embed=error("Reached the limit of chapters per series. Remove some before adding more."))

        chapter_drive_link = None
        series = ctx.bot.database.series.get(group_name, series_name)
        if series.series_drive_link:
            chapter_name_match = re.search(r'\d+', chapter_name)
            match = re.search(r'/folders/([a-zA-Z0-9_-]+)', series.series_drive_link)
            if match:
                response = requests.get(f"{os.getenv('KeiretsuUrl')}/api/list?id={match[1]}")
                if response.status_code == 200:
                    folders = response.json()
                    for item in folders.get('files', []):
                        if item['mimeType'] == "application/vnd.google-apps.folder":
                            # Compare by complete names or by numbers.
                            matches = False

                            if chapter_name == item['name']:
                                matches = True

                            if not matches and chapter_name_match:
                                item_match = re.search(r'\d+', item['name'])
                                if item_match:
                                    matches = int(re.search(r'\d+', chapter_name)[0]) == int(re.search(r'\d+', item['name'])[0])

                            if matches:
                                chapter_drive_link = f"https://drive.google.com/drive/folders/{item['id']}"

        chapter_id = ctx.bot.database.chapters.new(series_name, chapter_name, chapter_drive_link)
        if chapter_id is None:
            return await ctx.respond(embed=error(f"Chapter `{chapter_name}` for series `{series_name}` is already in the database (or errored while adding.)"))

        warning_message = "\n**Warning:** could not find chapter in Google Drive." if chapter_drive_link is None else ""
        await ctx.respond(embed=info(f"Chapter `{chapter_name}` for series `{series_name}` has been added." + warning_message))

    @Chapter.command(description="Deletes the chapter from a series.")
    @check_authority(AuthorityLevel.ProjectManager)
    async def delete(self,
                     ctx,
                     group_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_group_list)),
                     series_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_series_list)),
                     chapter_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_chapter_list))):
        await ctx.defer()

        rows = ctx.bot.database.chapters.delete(series_name, chapter_name)
        if rows and rows > 0:
            return await ctx.respond(embed=info(f"Chapter `{chapter_name}` for series `{series_name}` has been deleted."))

        await ctx.respond(embed=error(f"Chapter `{chapter_name}` for series `{series_name}` not found."))

    @Chapter.command(description="Edits the chapter of a series.")
    @check_authority(AuthorityLevel.ProjectManager)
    async def edit(self,
                   ctx,
                   group_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_group_list)),
                   series_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_series_list)),
                   chapter_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_chapter_list)),
                   new_name: str = None,
                   new_drive_link: str = None):
        await ctx.defer()

        if not new_name and not new_drive_link:
            return await ctx.respond(embed=error("You must provide at least one of `new_name` or `new_drive_link`."))

        rows = ctx.bot.database.chapters.update(series_name, chapter_name, new_name, new_drive_link)

        if rows and rows > 0:
            updates = []
            if new_name:
                updates.append(f"renamed to `{new_name}`")
            if new_drive_link:
                updates.append(f"changed drive link to `{new_drive_link}`")
            
            update_info = " and ".join(updates)
            return await ctx.respond(embed=info(f"Chapter `{chapter_name}` for series `{series_name}` has been updated: {update_info}."))
        
        await ctx.respond(embed=error(f"Chapter `{chapter_name}` for series `{series_name}` not found."))

    @Chapter.command(description="Lists all chapters in a series.")
    async def list(self,
                   ctx,
                   group_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_group_list)),
                   series_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_series_list))):
        await ctx.defer()

        chapters = ctx.bot.database.chapters.get_by_series_name(series_name)
        if not chapters:
            return await ctx.respond(embed=error(f"No chapters found for series `{series_name}`."))

        sorted_names = natsorted([chapter.chapter_name for chapter in chapters])

        output = []
        for i, chapter_name in enumerate(sorted_names, start=1):
            output.append(f"{i}\\. `{chapter_name}`")

        await ctx.respond(embed=info("\n".join(output), title=f"Chapters in {series_name}"))

    @Chapter.command(description="Makes a jobboard post for the job.")
    @check_authority(AuthorityLevel.ProjectManager)
    async def jobboard_post(self,
                            ctx,
                            group_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_group_list)),
                            series_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_series_list)),
                            chapter_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_chapter_list)),
                            job_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_added_jobs)),
                            min_level: discord.Option(int, description="Minimum level of staff that is allowed to claim.", choices=StaffLevel.to_choices()),
                            pref_deadline: discord.Option(int, description="Preferred deadline in days (0 for no deadline)."),
                            pages_num: discord.Option(int, description="Number of pages for this chapter.")):
        await ctx.defer()

        if not ctx.guild:
            return await ctx.respond(embed=error("Not allowed in DMs."))

        # Sanity checks
        series = ctx.bot.database.series.get(group_name, series_name)
        if not series:
            return await ctx.respond(embed=error(f"Failed to get series `{series_name}` by `{group_name}`."))

        chapter = ctx.bot.database.chapters.get(series_name, chapter_name)
        if not chapter:
            return await ctx.respond(embed=error(f"Failed to get chapter `{chapter_name}` for series `{series_name}`."))

        if chapter.is_archived:
            return await ctx.respond(embed=error(f"Chapter `{chapter_name}` is archived. Cannot post on job board."))

        series_job = ctx.bot.database.jobs.get_added(series_name, job_name)
        if not series_job:
            return await ctx.respond(embed=error(f"Failed to get job `{job_name}` for series `{series_name}`."))

        assignment = ctx.bot.database.assignments.get(chapter.chapter_id, series_job.series_job_id)
        if assignment:
            return await ctx.respond(embed=error(f"Job `{job_name}` for chapter `{chapter_name}` is already claimed. Cannot make a post."))

        job = ctx.bot.database.jobs.get(job_name)
        if not job or not job.jobboard_channel:
            return await ctx.respond(embed=error(f"Job `{job_name}` does not have a job board channel specified."))

        # Check if already posted.
        if ctx.bot.database.boardposts.get_by_chapter(chapter.chapter_id, series_job.series_job_id):
            return await ctx.respond(embed=error(f"There's already a job board post for `{job_name}` for chapter `{chapter_name}`.\nPlease remove if you want to re-post."))

        if ctx.bot.database.boardposts.get_by_series_and_job(series.series_id, series_job.job_id):
            return await ctx.respond(embed=error("You're allowed to post only 1 chapter per series for a job at a time."))

        description = f"Chapter: {chapter_name}"

        if chapter.drive_link and series.mangadex:
            description += f" — [Drive Folder]({chapter.drive_link}) • [Mangadex]({series.mangadex})"
        elif chapter.drive_link:
            description += f" — [Drive Folder]({chapter.drive_link})"
        elif series.mangadex:
            description += f" — [Mangadex]({series.mangadex})"

        embed = discord.Embed(
            title=f"{series_name} by {group_name}",
            description=description,
            color=discord.Color.blue()
        )

        deadline = f"{pref_deadline} days" if pref_deadline > 0 else "No deadline"
        embed.add_field(name="🏆 Min. Level", value=StaffLevel.to_string(min_level), inline=True)
        embed.add_field(name="⏰ Pref. Deadline", value=deadline, inline=True)
        embed.add_field(name="📄 Num. of Pages", value=f"{pages_num}", inline=True)

        if series.thumbnail:
            embed.set_thumbnail(url=series.thumbnail)

        # Prepare notification list
        role_to_level = {
            int(os.getenv('StaffTrialRoleId')): 0,
            int(os.getenv('StaffProbationaryRoleId')): 1,
            int(os.getenv('StaffFullRoleId')): 2
        }
        
        members_to_check = set()
        relevant_roles = [ctx.guild.get_role(role_id) for role_id, level in role_to_level.items() if level >= min_level]

        for role in relevant_roles:
            members_to_check.update(ctx.guild.get_role(role.id).members)

        eligible_members = []

        for member in members_to_check:
            if int(series_job.role_id) in [role.id for role in member.roles]:
                user_staff_level = -1
                for role in member.roles:
                    if role.id in role_to_level:
                        user_staff_level = max(user_staff_level, role_to_level[role.id])

                if user_staff_level >= min_level:
                    mem = ctx.bot.database.members.get(str(member.id))
                    if mem:
                        if mem.jobboard_notifications or ctx.bot.database.subscriptions.is_subscribed(mem.member_id, series.series_id):
                            eligible_members.append(member.mention)

        channel = ctx.bot.get_channel(int(job.jobboard_channel))
        message = await channel.send(content=' '.join(eligible_members), embed=embed, view=JobboardView())
        await message.edit(content=F'`@{StaffLevel.to_string(min_level).lower()}{series_name}{pref_deadline}{pages_num}`')

        boardpost_id = ctx.bot.database.boardposts.new(str(message.id), chapter.chapter_id, series_job.series_job_id, min_level)
        if boardpost_id is None:
            await message.delete()
            return await ctx.respond(embed=error("Failed to create a job board post."))

        await ctx.respond(embed=info(f"A post for `{job_name}` for chapter `{chapter_name}` has been made.\nThe post will be automatically deleted in **7 days** if not claimed.\nYou'll have to re-post it manually in that case."))

    @Chapter.command(description="Removes a jobboard post for the job.")
    @check_authority(AuthorityLevel.ProjectManager)
    async def jobboard_remove(self,
                              ctx,
                              group_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_group_list)),
                              series_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_series_list)),
                              chapter_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_chapter_list)),
                              job_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_added_jobs))):
        await ctx.defer()

        chapter = ctx.bot.database.chapters.get(series_name, chapter_name)
        if not chapter:
            return await ctx.respond(embed=error(f"Could not find chapter `{chapter_name} in series `{series_name}`"))

        series_job = ctx.bot.database.jobs.get_added(series_name, job_name)
        job = ctx.bot.database.jobs.get(job_name)

        jobboard_post = ctx.bot.database.boardposts.get_by_chapter(chapter.chapter_id, series_job.series_job_id)
        if not jobboard_post:
            return await ctx.respond(embed=error(f"Could not find post for `{job_name}` for chapter `{chapter_name}`."))

        channel = ctx.bot.get_channel(int(job.jobboard_channel))
        if channel:
            try:
                message = await channel.fetch_message(int(jobboard_post.message_id))
                if message:
                    await message.delete()
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass

        ctx.bot.database.boardposts.delete(jobboard_post.boardpost_id)
        await ctx.respond(embed=info(f"The post for `{job_name}` for chapter `{chapter_name}` has been removed."))

    @Chapter.command(description="Archives a chapter.")
    @check_authority(AuthorityLevel.ProjectManager)
    async def archive(self,
                      ctx,
                      group_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_group_list)),
                      series_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_series_list)),
                      chapter_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_chapter_list))):
        await ctx.defer()

        chapter = ctx.bot.database.chapters.get(series_name, chapter_name)
        if not chapter:
            return await ctx.respond(embed=error(f"Not found chapter `{chapter_name}` for series `{series_name}`."))

        if chapter.is_archived:
            return await ctx.respond(embed=error(f"Chapter `{chapter_name}` for series `{series_name}` is already archived."))

        rows = ctx.bot.database.chapters.archive(chapter.chapter_id)
        if rows is None:
            return await ctx.respond(embed=error(f"Failed to archive chapter `{chapter_name}` for series `{series_name}`"))

        # Move to .archive folder in GDrive
        warning = ''
        if chapter.drive_link:
            match = re.search(r'/folders/([a-zA-Z0-9_-]+)', chapter.drive_link)
            if match:
                response = requests.get(f"{os.getenv('KeiretsuUrl')}/api/archive?id={match[1]}")
                if response.status_code != 200:
                    warning = '\n**Warning:** failed to move to `.archive` folder in Google Drive.'

        # Archive assignments associated with the chapter.
        ctx.bot.database.assignments.delete_for_chapter(chapter.chapter_id) 

        await ctx.respond(embed=info(f"Chapter `{chapter_name}` for series `{series_name}` has been archived." + warning))

    @Chapter.command(description="Unarchives a chapter.")
    async def unarchive(self,
                        ctx,
                        group_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_group_list)),
                        series_name: str,
                        chapter_name: str):
        await ctx.defer()

        chapter = ctx.bot.database.chapters.get(series_name, chapter_name)
        if not chapter:
            return await ctx.respond(embed=error(f"Not found chapter `{chapter_name}` for series `{series_name}`."))

        if not chapter.is_archived:
            return await ctx.respond(embed=error(f"Chapter `{chapter_name}` for series `{series_name}` is not archived."))

        rows = ctx.bot.database.chapters.unarchive(chapter.chapter_id)
        if rows is None:
            return await ctx.respond(embed=error(f"Failed to unarchive chapter `{chapter_name}` for series `{series_name}`."))

        # Move to parent folder from archive.
        if chapter.drive_link:
            match = re.search(r'/folders/([a-zA-Z0-9_-]+)', chapter.drive_link)
            if match:
                requests.get(f"{os.getenv('KeiretsuUrl')}/api/unarchive?id={match[1]}")

        # Restore assignments
        ctx.bot.database.assignments.restore_for_chapter(chapter.chapter_id)
        await ctx.respond(embed=info(f"Chapter `{chapter_name}` for series `{series_name}` has been unarchived."))