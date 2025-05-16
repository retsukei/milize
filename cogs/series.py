import discord
import re
import os
import requests
import base64
import json
from discord.ext import commands
from discord.commands import SlashCommandGroup
from utils.embeds import info, error
from utils.checks import check_authority
from utils.constants import AuthorityLevel
from utils.autocompletes import get_group_list, get_series_list, get_added_jobs, get_unadded_jobs

def normalize_series_name(name: str) -> str:
    return re.sub(r"[^\w\-]", "_", name.strip().lower())

async def get_series_list_by_source(ctx: discord.AutocompleteContext):
    series_list = ctx.bot.database.series.get_by_group_name(ctx.options['source_group_name'])

    if series_list:
        return [series.series_name for series in series_list]

    return []

async def get_series_list_by_target(ctx: discord.AutocompleteContext):
    series_list = ctx.bot.database.series.get_by_group_name(ctx.options['target_group_name'])

    if series_list:
        return [series.series_name for series in series_list]

    return []

def setup(bot):
    bot.add_cog(Series(bot))

class Series(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    Series = SlashCommandGroup(name="series", description="Series related commands.")

    @Series.command(description="Adds a new series to a group.")
    @check_authority(AuthorityLevel.ProjectManager)
    async def add(self,
                    ctx,
                    group_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_group_list)),
                    series_name: str,
                    drive_link: str,
                    style_guide: str = None,
                    mangadex: str = None,
                    github_link: str = None,
                    thumbnail: str = None):
        await ctx.defer()

        group = ctx.bot.database.groups.get_by_name(group_name)
        if group is None:
            return await ctx.respond(embed=error(f"Group `{group_name}` does not exist or failed to fetch it."))

        match = re.search(r'/folders/([a-zA-Z0-9_-]+)', drive_link)
        if match is None:
            return await ctx.respond(embed=error("Incorrect Google Drive folder URL."))

        series_id = ctx.bot.database.series.new(group[0], series_name, drive_link, style_guide, mangadex, github_link, thumbnail)
        if not series_id:
            return await ctx.respond(embed=error(f"Failed to add new series `{series_name}` for group `{group_name}`."))

        await ctx.respond(embed=info(f"New series `{series_name}` has been successfully added for group `{group_name}`."))

    @Series.command(description="Deletes series from Milize.")
    @check_authority(AuthorityLevel.ProjectManager)
    async def delete(self,
                    ctx,
                    group_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_group_list)),
                    series_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_series_list))):
        await ctx.defer()

        rows = ctx.bot.database.series.delete(group_name, series_name)
        if rows and rows > 0:
            return await ctx.respond(embed=info(f"Series `{series_name}` has been removed from Milize."))

        await ctx.respond(embed=error(f"Series `{series_name}` not found in the database."))

    @Series.command(description="Lists all series of a group.")
    async def list(self,
                    ctx,
                    group_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_group_list))):
        await ctx.defer()

        series = ctx.bot.database.series.get_by_group_name(group_name)
        
        output = []
        for i, (_, series_name, series_drive_link, style_guide, _, _) in enumerate(series, start=1):
            line = f"**{i}\\. {series_name}**"

            if series_drive_link and style_guide:
                line += f" — [Drive Link]({series_drive_link}) • [Style Guide]({style_guide})"
            elif series_drive_link:
                line += f" — [Drive Link]({series_drive_link})"
            elif style_guide:
                line += f" — [Style Guide]({style_guide})"

            output.append(line)

        await ctx.respond(embed=info("\n".join(output), title=f"Series of {group_name}"))

    @Series.command(description="Edits the series of a group.")
    @check_authority(AuthorityLevel.ProjectManager)
    async def edit(self,
                    ctx,
                    group_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_group_list)),
                    series_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_series_list)),
                    new_name: str = None,
                    new_drive_link: str = None,
                    new_style_guide: str = None,
                    new_mangadex: str = None,
                    new_github_link: str = None,
                    new_thumbnail: str = None):
        await ctx.defer()

        if not new_name and not new_drive_link and not new_style_guide and not new_mangadex and not new_thumbnail and not new_github_link:
            return await ctx.respond(embed=error("You must provide at least one of `new_name`, `new_drive_link`, `new_style_guide`, `new_mangadex`, `new_github_link` or `new_thumbnail`."))

        rows = ctx.bot.database.series.update(series_name, new_name, new_drive_link, new_style_guide, new_mangadex, new_github_link, new_thumbnail)

        if rows and rows > 0:
            return await ctx.respond(embed=info(f"Series `{series_name}` has been updated."))

        await ctx.respond(embed=error(f"Failed to update series `{series_name}` (or no changes were made.)"))

    @Series.command(description="Moves series from one group to another.")
    @check_authority(AuthorityLevel.ProjectManager)
    async def move(self,
                    ctx,
                    group_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_group_list)),
                    series_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_series_list)),
                    new_group: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_group_list))):
        await ctx.defer()

        group_from = ctx.bot.database.groups.get_by_name(group_name)
        group_to = ctx.bot.database.groups.get_by_name(new_group)

        if group_from.group_id == group_to.group_id:
            return await ctx.respond(embed=error(f"The series is already in `{group_from.group_name}`."))

        rows = ctx.bot.database.series.move(group_from.group_id, group_to.group_id)
        if rows and rows > 0:
            return await ctx.respond(embed=info(f"Series `{series_name}` has been moved to `{group_to.group_name}`."))

        await ctx.respond(embed=info("Failed to update."))

    @Series.command(description="Creates a github .json file to upload on cubari")
    @check_authority(AuthorityLevel.ProjectManager)
    async def add_github(self,
                         ctx,
                         group_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_group_list)),
                         series_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_series_list)),
                         title: str,
                         description: str,
                         artist: str,
                         author: str,
                         cover: str):
        await ctx.defer()

        series = ctx.bot.database.series.get(group_name, series_name)
        if not series:
            return await ctx.respond(embed=error("Failed to get series."))
        
        if series.github_link:
            return await ctx.respond(embed=error(f"GitHub link is already set for series `{series_name}`"))
        
        file_name = normalize_series_name(series_name) + ".json"
        owner = os.getenv("GitHubUsername")
        repo = os.getenv("GitHubRepo")
        branch = "main"
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{file_name}"
        headers = {
            "Authorization": f"token {os.getenv('GitHubToken')}",
            "Accept": "application/vnd.github.v3+json"
        }
        try:
            response = requests.get(url, headers=headers, params={"ref": branch})
            response.raise_for_status()
            data = response.json()
            content = base64.b64decode(data["content"]).decode("utf-8")
            json_data = json.loads(content)
            sha = data["sha"]
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                json_data = {
                    "title": title,
                    "description": description,
                    "artist": artist,
                    "author": author,
                    "cover": cover,
                    "chapters": {}
                }
                sha = None
            else:
                raise

        updated_content = json.dumps(json_data, indent=2)
        encoded_content = base64.b64encode(updated_content.encode("utf-8")).decode("utf-8")

        commit_message = f"[{series_name}] Initialize metadata"
        update_data = {
            "message": commit_message,
            "content": encoded_content,
            "branch": branch,
        }
        if sha:
            update_data["sha"] = sha

        update_response = requests.put(url, headers=headers, json=update_data)
        update_response.raise_for_status()

        rows = ctx.bot.database.series.update(series_name=series_name, new_github_link=f"https://github.com/{owner}/{repo}/blob/{branch}/{file_name}")
        if rows is None:
            return await ctx.respond(embed=error("Failed to update database with the github link."))

        await ctx.respond(embed=info(f"Github file `{file_name}` for series **{series_name}** has been successfully added."))

    @Series.command(description="Attaches job to a series.")
    @check_authority(AuthorityLevel.ProjectManager)
    async def add_job(self,
                         ctx,
                         group_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_group_list)),
                         series_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_series_list)),
                         job_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_unadded_jobs))):
        await ctx.defer()

        series = ctx.bot.database.series.get(group_name, series_name)
        if series is None:
            return await ctx.respond(embed=error(f"Failed to get series `{series_name}`."))

        series_job_id = ctx.bot.database.jobs.add_to_series(series.series_id, job_name)
        if series_job_id is None:
            return await ctx.respond(embed=error(f"Job `{job_name}` is already added to series `{series_name}` (or errored while adding.)"))

        await ctx.respond(embed=info(f"Job `{job_name}` has been added to series `{series_name}`."))

    @Series.command(description="Removes job from series.")
    @check_authority(AuthorityLevel.ProjectManager)
    async def remove_job(self,
                         ctx,
                         group_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_group_list)),
                         series_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_series_list)),
                         job_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_added_jobs))):
        await ctx.defer()

        series = ctx.bot.database.series.get(group_name, series_name)
        if series is None:
            return await ctx.respond(embed=error(f"Failed to get series `{series_name}`."))

        rows = ctx.bot.database.jobs.remove_from_series(series.series_id, job_name)
        if rows and rows > 0:
            return await ctx.respond(embed=info(f"Job `{job_name}` has been removed from series `{series_name}`."))

        await ctx.respond(embed=error(f"Job`{job_name}` not found in `{series_name}`."))

    @Series.command(description="Lists job attached to a series.")
    async def list_jobs(self,
                         ctx,
                         group_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_group_list)),
                         series_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_series_list))):
        await ctx.defer()

        series_jobs = ctx.bot.database.jobs.get_added_all(series_name)

        output = []
        for i, (_, _, job_name, role_id, _, _) in enumerate(series_jobs, start=1):
            line = f"{i}\\. `{job_name}` — <@&{role_id}>"
            output.append(line)

        await ctx.respond(embed=info("\n".join(output), title=f"Added jobs for {series_name}"))

    @Series.command(description="Copies jobs from another series.")
    @check_authority(AuthorityLevel.ProjectManager)
    async def copy_jobs(self,
                    ctx,
                    source_group_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_group_list)),
                    source_series_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_series_list_by_source)),
                    target_group_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_group_list)),
                    target_series_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_series_list_by_target))):
        await ctx.defer()

        source_series = ctx.bot.database.series.get(source_group_name, source_series_name)
        target_series = ctx.bot.database.series.get(target_group_name, target_series_name)

        if not source_series:
            return await ctx.respond(embed=error(f"Source series `{source_series_name}` not found in group `{source_group_name}`."))

        if not target_series:
            return await ctx.respond(embed=error(f"Target series `{target_series_name}` not found in group `{target_group_name}`."))

        jobs = ctx.bot.database.jobs.get_added_all(source_series_name)

        if not jobs:
            return await ctx.respond(embed=error(f"No jobs found for source series `{source_series_name}`."))

        copied_jobs = 0
        for job in jobs:
            try:
                new_job_id = ctx.bot.database.jobs.add_to_series(target_series.series_id, job.job_name)
                if new_job_id:
                    copied_jobs += 1
            except Exception as e:
                print(f"Failed to copy job '{job.job_name}': {e}")

        if copied_jobs == 0:
            await ctx.respond(embed=error(f"Failed to copy any jobs from `{source_series_name}` to `{target_series_name}`."))
        else:
            await ctx.respond(embed=info(f"Successfully copied `{copied_jobs}` job(s) from `{source_series_name}` in group `{source_group_name}` to `{target_series_name}` in group `{target_group_name}`."))
        
    @Series.command(description="Archives a series.")
    @check_authority(AuthorityLevel.Owner)
    async def archive(self,
                      ctx,
                      group_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_group_list)),
                      series_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_series_list))):
        await ctx.defer()

        series = ctx.bot.database.series.get(group_name, series_name)
        if not series:
            return await ctx.respond(embed=error(f"Failed to get series `{series_name}` from `{group_name}`."))

        if series.is_archived:
            return await ctx.respond(embed=error(f"Series `{series_name}` is already archived."))

        rows = ctx.bot.database.series.archive(series.series_id)
        if rows is None:
            return await ctx.respond(embed=error(f"Failed to archive series `{series_name}`."))

        rows = ctx.bot.database.chapters.archive_all(series.series_id)
        if rows is None:
            return await ctx.respond(embed=error(f"Failed to archive all chapters for series `{series_name}`."))

        # Move to .archive folder in GDrive
        warning = ''
        if series.series_drive_link:
            match = re.search(r'/folders/([a-zA-Z0-9_-]+)', series.series_drive_link)
            if match:
                response = requests.get(f"{os.getenv('KeiretsuUrl')}/api/archive?id={match[1]}")
                if response.status_code != 200:
                    warning = '\n**Warning:** failed to move to `.archive(d)` folder in Google Drive.'

        await ctx.respond(embed=info(f"Series `{series_name}` from `{group_name}` has been archived." + warning))

    @Series.command(description="Archives a series.")
    @check_authority(AuthorityLevel.Owner)
    async def unarchive(self,
                      ctx,
                      group_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_group_list)),
                      series_name: str):
        await ctx.defer()

        series = ctx.bot.database.series.get(group_name, series_name)
        if not series:
            return await ctx.respond(embed=error(f"Failed to get series `{series_name}` from `{group_name}`."))

        if not series.is_archived:
            return await ctx.respond(embed=error(f"Series `{series_name}` is not archived."))

        rows = ctx.bot.database.series.unarchive(series.series_id)
        if rows is None:
            return await ctx.respond(embed=error(f"Failed to unarchive series `{series_name}`."))

        # Move to parent folder from archive.
        if series.series_drive_link:
            match = re.search(r'/folders/([a-zA-Z0-9_-]+)', series.series_drive_link)
            if match:
                requests.get(f"{os.getenv('KeiretsuUrl')}/api/unarchive?id={match[1]}")

        await ctx.respond(embed=info(f"Series `{series_name}` from `{group_name}` has been unarchived."))

    @Series.command(description="Assigns staff at the series level.")
    @check_authority(AuthorityLevel.Owner)
    async def assign(self,
                     ctx,
                     group_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_group_list)),
                     series_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_series_list)),
                     job_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_added_jobs)),
                     user: discord.User):
        await ctx.defer()

        user_id = str(user.id)
        member = ctx.bot.database.members.get(user_id)
        if not member:
            return await ctx.respond(embed=error(f"{user.mention} is not added to members in Milize."))

        series = ctx.bot.database.series.get(group_name, series_name)
        if not series:
            return await ctx.respond(embed=error(f"Failed to get series `{series_name}` for `{group_name}`."))

        series_job = ctx.bot.database.jobs.get_added(series_name, job_name)
        if not series_job:
            return await ctx.respond(embed=error(f"Failed to get job `{job_name}` for series `{series_name}`."))

        assignment = ctx.bot.database.series.get_assignment(series.series_id, series_job.series_job_id)
        if assignment:
            return await ctx.respond(embed=error(f"Job is already assigned to <@{assignment.assigned_to}>. Cannot assign."))

        assignment_id = ctx.bot.database.series.add_assignment(series.series_id, series_job.series_job_id, user_id)
        if assignment_id is None:
            return await ctx.respond(embed=error(f"Failed to assign {user.mention} to job `{job_name}` for series `{series_name}`."))

        await ctx.respond(embed=info(f"{user.mention} has been assigned to `{job_name}` for series `{series_name}` as consistent staff.\nNewly created chapters will have them automatically added."))

    @Series.command(description="Unassigns staff at the series level.")
    @check_authority(AuthorityLevel.Owner)
    async def unassign(self,
                     ctx,
                     group_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_group_list)),
                     series_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_series_list)),
                     job_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_added_jobs))):
        await ctx.defer()

        series = ctx.bot.database.series.get(group_name, series_name)
        if not series:
            return await ctx.respond(embed=error(f"Failed to get series `{series_name}` for `{group_name}`."))

        series_job = ctx.bot.database.jobs.get_added(series_name, job_name)
        if not series_job:
            return await ctx.respond(embed=error(f"Failed to get job `{job_name}` for series `{series_name}`."))

        assignment = ctx.bot.database.series.get_assignment(series.series_id, series_job.series_job_id)
        if not assignment:
            return await ctx.respond(embed=error(f"Job `{job_name}` for series `{series_name}` is not assigned to anyone."))

        assignment_id = ctx.bot.database.series.remove_assignment(series.series_id, series_job.series_job_id)
        if assignment_id is None:
            return await ctx.respond(embed=error(f"Failed to remove assignment for job `{job_name}` for series `{series_name}`."))

        await ctx.respond(embed=info(f"Assignment for job `{job_name}` for series `{series_name}` has been removed."))

    @Series.command(description="Blocks series from being uploaded to specified website.")
    @check_authority(AuthorityLevel.Owner)
    async def block_website(
        self,
        ctx,
        group_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_group_list)),
        series_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_series_list)),
        website: discord.Option(str, description="Website to block.")
    ):
        await ctx.defer()

        if str(ctx.author.id) != os.getenv("DiscordDevId") and str(ctx.author.id) != os.getenv("DiscordOwnerId"):
            return await ctx.respond(embed=error("Not allowed. Ping owner or developer."))

        series = ctx.bot.database.series.get(group_name, series_name)
        if not series:
            return await ctx.respond(embed=error(f"Failed to get series `{series_name}` for `{group_name}`."))

        blocked_websites = series.blocked_websites or []

        if website in blocked_websites:
            return await ctx.respond(embed=error("Specified website is already blocked for this series."))

        blocked_websites.append(website)

        updated = ctx.bot.database.series.update_blocked_websites(series_name, blocked_websites)
        if not updated:
            return await ctx.respond(embed=error("Failed to update blocked websites."))

        return await ctx.respond(embed=info(f"Website `{website}` is now blocked for series `{series_name}`."))
    
    @Series.command(description="Unblocks a website for a specific series.")
    @check_authority(AuthorityLevel.Owner)
    async def unblock_website(
        self,
        ctx,
        group_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_group_list)),
        series_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_series_list)),
        website: discord.Option(str, description="Website to unblock.")
    ):
        await ctx.defer()

        if str(ctx.author.id) != os.getenv("DiscordDevId") and str(ctx.author.id) != os.getenv("DiscordOwnerId"):
            return await ctx.respond(embed=error("Not allowed. Ping owner or developer."))

        series = ctx.bot.database.series.get(group_name, series_name)
        if not series:
            return await ctx.respond(embed=error(f"Failed to get series `{series_name}` for `{group_name}`."))

        blocked_websites = series.blocked_websites or []

        if website not in blocked_websites:
            return await ctx.respond(embed=error(f"Website `{website}` is not currently blocked for this series."))

        blocked_websites.remove(website)

        updated = ctx.bot.database.series.update_blocked_websites(series_name, blocked_websites)
        if not updated:
            return await ctx.respond(embed=error("Failed to update blocked websites."))

        return await ctx.respond(embed=info(f"Website `{website}` is now unblocked for series `{series_name}`."))

    @Series.command(description="Lists all roles at the series level.")
    @check_authority(AuthorityLevel.Member)
    async def assignments(self,
                          ctx,
                          group_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_group_list)),
                          series_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_series_list))):
        await ctx.defer()

        if not ctx.guild or ctx.guild.id != int(os.getenv("StaffGuildId")):
            return await ctx.respond(embed=error("This command is now deprecated. Please use `/chapter progress` to check the progress of a chapter."))

        series = ctx.bot.database.series.get(group_name, series_name)
        if series is None:
            return await ctx.respond(embed=error(f"Failed to get series `{series_name}` for group `{group_name}`."))

        series_jobs = ctx.bot.database.jobs.get_added_all(series_name)
        if series_jobs is None:
            return await ctx.respond(embed=error(f"Failed to get jobs for series `{series_name}`."))

        embed = discord.Embed(title="Consistent staff", url=series.series_drive_link, color=discord.Color.blue())
        embed.set_author(name=f"Jobs for {series_name} ({group_name})")

        for i, (series_job_id, job_id, job_name, _, _, _) in enumerate(series_jobs, start=1):
            field = ''
            assignment = ctx.bot.database.series.get_assignment(series.series_id, series_job_id)

            if assignment:
                user = await ctx.bot.get_or_fetch_user(int(assignment.assigned_to))
                member = ctx.bot.database.members.get(assignment.assigned_to)
                display_name = "<unknown>" if not user else user.display_name
                field = f"Assigned to: {display_name if member is None or member.credit_name is None else member.credit_name}"
            else:
                field = "Assigned to: None"

            embed.add_field(name=job_name, value=field, inline=False)

        await ctx.respond(embed=embed)