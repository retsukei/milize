import discord
import os
from datetime import datetime, timedelta, timezone
from discord.ext import commands
from discord.commands import SlashCommandGroup
from utils.embeds import info, error, warning
from utils.checks import check_authority
from utils.constants import AuthorityLevel, JobStatus, JobType
from utils.autocompletes import get_group_list, get_series_list, get_added_jobs, get_unadded_jobs, get_job_list, get_chapter_list

async def notify_next_stage(ctx, series_name, chapter, series_job):
    def other_stages_done(job_type):
        if job_type == JobType.Translation:
            # Check if there's no Proofreading, and Cleaning (and/or Redrawing) is completed.
            pr_series_job = ctx.bot.database.jobs.get_added_by_type(series_name, JobType.Proofreading)
            if pr_series_job:
                return False

            rd_series_job = ctx.bot.database.jobs.get_added_by_type(series_name, JobType.Redrawing)
            cl_series_job = ctx.bot.database.jobs.get_added_by_type(series_name, JobType.Cleaning)

            rd_completed = False
            cl_completed = False

            if not rd_series_job:
                rd_completed = True
            else:
                assignment = ctx.bot.database.assignments.get(chapter.chapter_id, rd_series_job[0].series_job_id)
                if assignment and assignment.status == JobStatus.Completed:
                    rd_completed = True

            if not cl_series_job:
                cl_completed = True
            else:
                assignment = ctx.bot.database.assignments.get(chapter.chapter_id, cl_series_job[0].series_job_id)
                if assignment and assignment.status == JobStatus.Completed:
                    cl_completed = True

            return rd_completed and cl_completed
        elif job_type == JobType.Proofreading:
            # Check if Cleaning (and/or Redrawing) is completed.
            rd_series_job = ctx.bot.database.jobs.get_added_by_type(series_name, JobType.Redrawing)
            cl_series_job = ctx.bot.database.jobs.get_added_by_type(series_name, JobType.Cleaning)

            rd_completed = False
            cl_completed = False

            if not rd_series_job:
                rd_completed = True
            else:
                assignment = ctx.bot.database.assignments.get(chapter.chapter_id, rd_series_job[0].series_job_id)
                if assignment and assignment.status == JobStatus.Completed:
                    rd_completed = True

            if not cl_series_job :
                cl_completed = True
            else:
                assignment = ctx.bot.database.assignments.get(chapter.chapter_id, cl_series_job[0].series_job_id)
                if assignment and assignment.status == JobStatus.Completed:
                    cl_completed = True

            return rd_completed and cl_completed
        elif job_type == JobType.Cleaning:
            # Check if there's no Redrawing or Proofreading (in that case, check translation) or they're completed.
            pr_series_job = ctx.bot.database.jobs.get_added_by_type(series_name, JobType.Proofreading)
            rd_series_job = ctx.bot.database.jobs.get_added_by_type(series_name, JobType.Redrawing)

            rd_completed = False
            pr_completed = False

            if not rd_series_job:
                rd_completed = True
            else:
                assignment = ctx.bot.database.assignments.get(chapter.chapter_id, rd_series_job[0].series_job_id)
                if assignment and assignment.status == JobStatus.Completed:
                    rd_completed = True

            if not pr_series_job:
                # Check translation.
                tl_series_job = ctx.bot.database.jobs.get_added_by_type(series_name, JobType.Translation)
                if tl_series_job:
                    assignment = ctx.bot.database.assignments.get(chapter.chapter_id, tl_series_job[0].series_job_id)
                    if assignment and assignment.status == JobStatus.Completed:
                        pr_completed = True
                else:
                    pr_completed = True
            else:
                assignment = ctx.bot.database.assignments.get(chapter.chapter_id, pr_series_job[0].series_job_id)
                if assignment and assignment.status == JobStatus.Completed:
                    pr_completed = True

            return rd_completed and pr_completed
        elif job_type == JobType.Redrawing:
            # Check if there's no Cleaning or Proofreading (in that case, check translation) or they're completed.
            pr_series_job = ctx.bot.database.jobs.get_added_by_type(series_name, JobType.Proofreading)
            cl_series_job = ctx.bot.database.jobs.get_added_by_type(series_name, JobType.Cleaning)

            cl_completed = False
            pr_completed = False

            if not cl_series_job:
                cl_completed = True
            else:
                assignment = ctx.bot.database.assignments.get(chapter.chapter_id, cl_series_job[0].series_job_id)
                if assignment and assignment.status == JobStatus.Completed:
                    cl_completed = True

            if not pr_series_job:
                # Check translation.
                tl_series_job = ctx.bot.database.jobs.get_added_by_type(series_name, JobType.Translation)
                if tl_series_job:
                    assignment = ctx.bot.database.assignments.get(chapter.chapter_id, tl_series_job[0].series_job_id)
                    if assignment and assignment.status == JobStatus.Completed:
                        pr_completed = True
                else:
                    pr_completed = True
            else:
                assignment = ctx.bot.database.assignments.get(chapter.chapter_id, pr_series_job[0].series_job_id)
                if assignment and assignment.status == JobStatus.Completed:
                    pr_completed = True

            return cl_completed and pr_completed
        elif job_type == JobType.Typesetting:
            sfx_series_job = ctx.bot.database.jobs.get_added_by_type(series_name, JobType.TypesettingSFX)

            if not sfx_series_job:
                return True
            else:
                assignment = ctx.bot.database.assignments.get(chapter.chapter_id, sfx_series_job[0].series_job_id)
                if assignment and assignment.status == JobStatus.Completed:
                    return True
                return False
        elif job_type == JobType.TypesettingSFX:
            ts_series_job = ctx.bot.database.jobs.get_added_by_type(series_name, JobType.Typesetting)

            if not ts_series_job:
                return True
            else:
                assignment = ctx.bot.database.assignments.get(chapter.chapter_id, ts_series_job[0].series_job_id)
                if assignment and assignment.status == JobStatus.Completed:
                    return True
                return False

    async def notify_member(job_type, exclude_id = None):
        notify_series_job = ctx.bot.database.jobs.get_added_by_type(series_name, job_type)
        if notify_series_job:
            for job in notify_series_job:
                assignment = ctx.bot.database.assignments.get(chapter.chapter_id, job.series_job_id)
                if assignment and assignment.status != JobStatus.Completed and assignment.assigned_to != exclude_id:
                    member = ctx.bot.database.members.get(assignment.assigned_to)
                    if member and member.stage_notifications:
                        await ctx.send(f"<@{assignment.assigned_to}>, chapter `{chapter.chapter_name}` is ready for `{JobType.to_string(job_type)}`.")
                        ctx.bot.database.assignments.update_available(assignment.assignment_id)
                        if job_type == JobType.Typesetting:
                            await notify_member(JobType.TypesettingSFX, assignment.assigned_to)

                        ctx.bot.database.assignments.update_reminder(assignment.assignment_id)
        else:
            if job_type == JobType.Typesetting:
                await notify_member(JobType.TypesettingSFX)
    
    if series_job.job_type == JobType.Translation:
        if other_stages_done(series_job.job_type):
            await notify_member(JobType.Typesetting)
        else:
            await notify_member(JobType.Proofreading)
    elif series_job.job_type == JobType.Proofreading or series_job.job_type == JobType.Cleaning or series_job.job_type == JobType.Redrawing:
        if other_stages_done(series_job.job_type):
            await notify_member(JobType.Typesetting)
    elif series_job.job_type == JobType.Typesetting or series_job.job_type == JobType.TypesettingSFX:
        if other_stages_done(series_job.job_type):
            await notify_member(JobType.Quality)
    elif series_job.job_type == JobType.Quality:
        await notify_member(JobType.Managment)


def setup(bot):
    bot.add_cog(Jobs(bot))

class Jobs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    Jobs = SlashCommandGroup(name="job", description="Jobs related commands.")

    @Jobs.command(description="Adds a new job to Milize.")
    @check_authority(AuthorityLevel.ProjectManager)
    async def new(self,
                    ctx,
                    job_name: str,
                    job_role: discord.Role,
                    job_type: discord.Option(int, choices=JobType.to_choices())):
        await ctx.defer()

        job_id = ctx.bot.database.jobs.new(job_name, job_role.id, job_type, ctx.author.id)
        if not job_id:
            await ctx.respond(embed=error(f"Job `{job_name}` is already in the database (or errored while adding).\nPlease use `/job edit` to modify already existing job."))
        else:
            await ctx.respond(embed=info(f"Job `{job_name}` has been added to the database with type `{JobType.to_string(job_type)}`."))

    @Jobs.command(description="Edits an existing job in Milize.")
    @check_authority(AuthorityLevel.ProjectManager)
    async def edit(self,
                ctx,
                job_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_job_list)),
                new_job_name: str = None,
                new_job_role: discord.Role = None,
                new_job_type: discord.Option(int, choices=JobType.to_choices()) = None):
        await ctx.defer()

        job = ctx.bot.database.jobs.get(job_name)
        if job is None:
            return await ctx.respond(embed=error(f"Job `{job_name}` does not exist in the database."))

        updated_role_id = new_job_role.id if new_job_role else job.role_id
        updated_job_type = new_job_type if new_job_type is not None else job.job_type
        updated_job_name = new_job_name if new_job_name else job.job_name

        rows = ctx.bot.database.jobs.update(job_name, updated_role_id, updated_job_type, updated_job_name)
        if rows and rows > 0:
            return await ctx.respond(embed=info(f"Job `{job_name}` has been successfully updated."))

        await ctx.respond(embed=error(f"No updates were made."))

    @Jobs.command(description="Deletes a job. Notice: will be deleted from everywhere.")
    @check_authority(AuthorityLevel.Owner)
    async def delete(self,
                     ctx,
                     job_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_job_list))):
        await ctx.defer()

        rows = ctx.bot.database.jobs.delete(job_name)

        if rows and rows > 0:
            return await ctx.respond(embed=info(f"Job `{job_name}` has been deleted from Milize."))

        return await ctx.respond(embed=error(f"Job `{job_name}` not found in the database."))

    @Jobs.command(description="Claims the job of a chapter.")
    @check_authority(AuthorityLevel.Member)
    async def claim(self,
                    ctx,
                    group_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_group_list)),
                    series_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_series_list)),
                    chapter_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_chapter_list)),
                    job_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_added_jobs))):
        await ctx.defer()

        series = ctx.bot.database.series.get(group_name, series_name)
        if series is None:
            return await ctx.respond(embed=error(f"Failed to get series `{series_name}` for group `{group_name}`."))

        chapter = ctx.bot.database.chapters.get(series_name, chapter_name)
        if chapter is None:
            return await ctx.respond(embed=error(f"Failed to get chapter `{chapter_name}` for series `{series_name}`."))

        series_job = ctx.bot.database.jobs.get_added(series_name, job_name)
        if series_job is None:
            return await ctx.respond(embed=error(f"Failed to get job `{job_name}` for series `{series_name}`."))

        assignment = ctx.bot.database.assignments.get(chapter[0], series_job[0])
        if assignment:
            user = await ctx.bot.get_or_fetch_user(assignment[3])
            return await ctx.respond(embed=error(f"Job `{job_name}` for chapter `{chapter_name}` is already claimed by <@{user.id}>"))

        is_first_job = ctx.bot.database.assignments.is_first(str(ctx.author.id))
        assignment_id = ctx.bot.database.assignments.new(chapter[0], series_job[0], ctx.author.id)
        if assignment_id is None:
            return await ctx.respond(embed=error(f"Failed to create an assignment in the database."))

        # Remove from job board if there is a post for this job.
        jobboard_post = ctx.bot.database.boardposts.get_by_chapter(chapter[0], series_job[0])
        if jobboard_post:
            job = ctx.bot.database.jobs.get(job_name)
            channel = ctx.bot.get_channel(int(job.jobboard_channel))
            if channel:
                message = await channel.fetch_message(int(jobboard_post.message_id))
                if message:
                    await message.delete()
                    ctx.bot.database.boardposts.delete(jobboard_post.boardpost_id)

        additional_info = []

        if chapter.drive_link:
            additional_info.append(f"Google Folder: [Click]({chapter.drive_link})")

        if series.style_guide:
            additional_info.append(f"Style Guide: [Click]({series.style_guide})")

        additional_info_message = " — ".join(additional_info) if additional_info else ""
        await ctx.respond(embed=info(f"Job `{job_name}` has been claimed for chapter `{chapter_name}`.\n{additional_info_message}"))

        if is_first_job:
            await ctx.send(embed=info(f"Since this is your first job, please consider checking if there's any important material to read (like a style guide). Usually, it's available in the pinned messages for the channel of the series."))

    @Jobs.command(description="Assigns a job to a member.")
    @check_authority(AuthorityLevel.ProjectManager) 
    async def assign(self,
                    ctx,
                    group_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_group_list)),
                    series_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_series_list)),
                    chapter_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_chapter_list)),
                    job_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_added_jobs)),
                    user: discord.User):
        await ctx.defer()

        chapter = ctx.bot.database.chapters.get(series_name, chapter_name)
        if chapter is None:
            return await ctx.respond(embed=error(f"Failed to get chapter `{chapter_name}` for series `{series_name}`."))

        series_job = ctx.bot.database.jobs.get_added(series_name, job_name)
        if series_job is None:
            return await ctx.respond(embed=error(f"Failed to get job `{job_name}` for series `{series_name}`."))

        assignment = ctx.bot.database.assignments.get(chapter[0], series_job[0])
        if assignment:
            assigned_user = await ctx.bot.get_or_fetch_user(assignment[3])
            return await ctx.respond(embed=error(f"Job `{job_name}` for chapter `{chapter_name}` is already assigned to <@{assigned_user.id}>.\nUse `/job reassign` to reassign."))

        user_id = str(user.id)
        member = ctx.bot.database.members.get(user_id)
        if member is None:
            return await ctx.respond(embed=error(f"<@{user.id}> is not added to members in Milize."))

        assignment_id = ctx.bot.database.assignments.new(chapter[0], series_job[0], user_id)
        if assignment_id is None:
            return await ctx.respond(embed=error(f"Failed to create an assignment in the database."))

        # Remove from job board if there is a post for this job.
        jobboard_post = ctx.bot.database.boardposts.get_by_chapter(chapter[0], series_job[0])
        if jobboard_post:
            job = ctx.bot.database.jobs.get(job_name)
            channel = ctx.bot.get_channel(int(job.jobboard_channel))
            if channel:
                message = await channel.fetch_message(int(jobboard_post.message_id))
                if message:
                    await message.delete()
                    ctx.bot.database.boardposts.delete(jobboard_post.boardpost_id)

        await ctx.respond(embed=info(f"Job `{job_name}` has been assigned to <@{user.id}> for chapter `{chapter_name}`."))

    @Jobs.command(description="Assigns a job to a member.")
    @check_authority(AuthorityLevel.ProjectManager) 
    async def reassign(self,
                    ctx,
                    group_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_group_list)),
                    series_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_series_list)),
                    chapter_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_chapter_list)),
                    job_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_added_jobs)),
                    user: discord.User):
        await ctx.defer()

        chapter = ctx.bot.database.chapters.get(series_name, chapter_name)
        if chapter is None:
            return await ctx.respond(embed=error(f"Failed to get chapter `{chapter_name}` for series `{series_name}`."))

        series_job = ctx.bot.database.jobs.get_added(series_name, job_name)
        if series_job is None:
            return await ctx.respond(embed=error(f"Failed to get job `{job_name}` for series `{series_name}`."))

        assignment = ctx.bot.database.assignments.get(chapter[0], series_job[0])
        if assignment is None:
            return await ctx.respond(embed=error(f"Job `{job_name}` for chapter `{chapter_name}` is not claimed by anyone.\nUse `/job assign` to assign."))

        user_id = str(user.id)
        member = ctx.bot.database.members.get(user_id)
        if member is None:
            return await ctx.respond(embed=error(f"<@{user.id}> is not added to members in Milize."))

        rows = ctx.bot.database.assignments.update_user(assignment.assignment_id, str(user))
        if rows and rows > 0:
            return await ctx.respond(embed=info(f"Job `{job_name}` has been assigned to <@{user.id}> for chapter `{chapter_name}`."))

        await ctx.respond(embed=error(f"No updates were made."))

    @Jobs.command(description="Unassigns the job of a chapter.")
    @check_authority(AuthorityLevel.ProjectManager)
    async def unassign(self,
                      ctx,
                      group_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_group_list)),
                      series_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_series_list)),
                      chapter_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_chapter_list)),
                      job_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_added_jobs))):
        await ctx.defer()

        chapter = ctx.bot.database.chapters.get(series_name, chapter_name)
        if chapter is None:
            return await ctx.respond(embed=error(f"Failed to get chapter `{chapter_name}` for series `{series_name}`."))

        series_job = ctx.bot.database.jobs.get_added(series_name, job_name)
        if series_job is None:
            return await ctx.respond(embed=error(f"Failed to get job `{job_name}` for series `{series_name}`."))

        assignment = ctx.bot.database.assignments.get(chapter.chapter_id, series_job.series_job_id)
        if assignment is None:
            return await ctx.respond(embed=error(f"Job `{job_name}` is not claimed by anyone."))

        rows = ctx.bot.database.assignments.delete(chapter.chapter_id, series_job.series_job_id)
        if rows and rows > 0:
            return await ctx.respond(embed=info(f"Job `{job_name}` for chapter `{chapter_name}` has been unassigned."))

        return await ctx.respond(embed=error(f"Failed to unassign job `{job_name}` for chapter `{chapter_name}`."))

    @Jobs.command(description="Unclaims the job of a chapter.")
    async def unclaim(self,
                      ctx,
                      group_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_group_list)),
                      series_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_series_list)),
                      chapter_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_chapter_list)),
                      job_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_added_jobs))):
        await ctx.defer()

        chapter = ctx.bot.database.chapters.get(series_name, chapter_name)
        if chapter is None:
            return await ctx.respond(embed=error(f"Failed to get chapter `{chapter_name}` for series `{series_name}`."))

        series_job = ctx.bot.database.jobs.get_added(series_name, job_name)
        if series_job is None:
            return await ctx.respond(embed=error(f"Failed to get job `{job_name}` for series `{series_name}`."))

        assignment = ctx.bot.database.assignments.get(chapter.chapter_id, series_job.series_job_id)
        if assignment is None:
            return await ctx.respond(embed=error(f"Job `{job_name}` is not claimed by anyone."))

        if assignment.assigned_to != str(ctx.author.id): # who the hell stores discord ids as integers?
            user = await ctx.bot.get_or_fetch_user(assignment.assigned_to)
            return await ctx.respond(embed=error(f"Job `{job_name}` is claimed by <@{user.id}>. Cannot unclaim."))

        rows = ctx.bot.database.assignments.delete(chapter.chapter_id, series_job.series_job_id)
        if rows and rows > 0:
            return await ctx.respond(embed=info(f"Job `{job_name}` for chapter `{chapter_name}` has been unclaimed."))

        return await ctx.respond(embed=error(f"Failed to unclaum job `{job_name}` for chapter `{chapter_name}`."))

    @Jobs.command(description="Shows chapter's job data.")
    async def list(self,
                    ctx,
                    group_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_group_list)),
                    series_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_series_list)),
                    chapter_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_chapter_list))):
        await ctx.defer()

        chapter = ctx.bot.database.chapters.get(series_name, chapter_name)
        if chapter is None:
            return await ctx.respond(embed=error(f"Failed to get chapter `{chapter_name}` for series `{series_name}`."))

        series_jobs = ctx.bot.database.jobs.get_added_all(series_name)
        if series_jobs is None:
            return await ctx.respond(embed=error(f"Failed to get jobs for series `{series_name}`."))

        embed = discord.Embed(title=f"Chapter {chapter[1]}", color=discord.Color.blue())
        embed.set_author(name=f"Jobs for {series_name} ({group_name})")

        for i, (series_job_id, job_id, job_name, _, _, _) in enumerate(series_jobs, start=1):
            field = ''
            assignment = ctx.bot.database.assignments.get(chapter.chapter_id, series_job_id)

            if assignment:
                user = await ctx.bot.get_or_fetch_user(assignment.assigned_to)
                member = ctx.bot.database.members.get(assignment.assigned_to)
                field = f"Assigned to: {user.display_name if member is None or member.credit_name is None else member.credit_name}\nStatus: {JobStatus.to_string(assignment.status)}"
            else:
                field = "Assigned to: None\nStatus: Backlog"

            embed.add_field(name=job_name, value=field, inline=False)

        await ctx.respond(embed=embed)

    @Jobs.command(description="Shows all jobs.")
    async def list_all(self, ctx):
        await ctx.defer()
        
        jobs = ctx.bot.database.jobs.get_all()

        output = []
        for i, (_, job_name, role_id, _, _) in enumerate(jobs, start=1):
            line = f"{i}\\. `{job_name}` — <@&{role_id}>"
            output.append(line)

        await ctx.respond(embed=info("\n".join(output), title=f"All jobs in Milize"))

    @Jobs.command(description="Updates status of a job.")
    @check_authority(AuthorityLevel.Member)
    async def update(self,
                     ctx,
                     group_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_group_list)),
                     series_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_series_list)),
                     chapter_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_chapter_list)),
                     job_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_added_jobs)),
                     status: discord.Option(int, choices=JobStatus.to_choices())):
        await ctx.defer()

        chapter = ctx.bot.database.chapters.get(series_name, chapter_name)
        if chapter is None:
            return await ctx.respond(embed=error(f"Failed to get chapter `{chapter_name}` for series `{series_name}`."))

        series_job = ctx.bot.database.jobs.get_added(series_name, job_name)
        if series_job is None:
            return await ctx.respond(embed=error(f"Failed to get job `{job_name}` for series `{series_name}`."))

        assignment = ctx.bot.database.assignments.get(chapter.chapter_id, series_job.series_job_id)
        if assignment is None:
            return await ctx.respond(embed=error(f"Job `{job_name}` is not claimed by anyone."))

        member = ctx.bot.database.members.get(str(ctx.author.id))
        if assignment.assigned_to != str(ctx.author.id) and member.authority_level < AuthorityLevel.ProjectManager:
            user = await ctx.bot.get_or_fetch_user(assignment.assigned_to)
            return await ctx.respond(embed=error(f"Job `{job_name}` is claimed by <@{user.id}>. Not allowed to update the status."))

        account = True
        if status == JobStatus.Completed and datetime.now(timezone.utc) - assignment.created_at < timedelta(minutes=5):
            account = False

        rows = ctx.bot.database.assignments.update_status(chapter.chapter_id, series_job.series_job_id, status, account)
        if rows is not None:
            line = f"Updated job `{job_name}` for chapter `{chapter_name}` to `{JobStatus.to_string(status)}`."
            if status == JobStatus.Completed and assignment.assigned_to == str(ctx.author.id):
                line += f"\nThank you for your work! {os.getenv('MilizeSaluteEmoji')}"
            await ctx.respond(embed=info(line))

            if status == JobStatus.Completed:
                # Trial / Probationary notif
                if assignment.assigned_to == str(ctx.author.id):
                    staff_trial_role_id = int(os.getenv("StaffTrialRoleId"))
                    staff_probationary_role_id = int(os.getenv("StaffProbationaryRoleId"))
                    notification_role = None

                    if staff_trial_role_id in [role.id for role in ctx.author.roles]:
                        notification_role = "Trial"
                    elif staff_probationary_role_id in [role.id for role in ctx.author.roles]:
                        notification_role = "Probationary"

                    if notification_role:
                        lead_notification_channel = ctx.bot.get_channel(int(os.getenv("LeadNotificationChannelId")))
                        if lead_notification_channel:
                            embed = discord.Embed(
                                title="Job Update Notification",
                                description=(f"{notification_role} staff <@{ctx.author.id}> has completed their job `{series_job.job_name}` on "
                                                f"chapter `{chapter_name}` for series `{series_name}`."),
                                color=discord.Color.yellow()
                            )
                        await lead_notification_channel.send(embed=embed)

                # Next stage notification
                await notify_next_stage(ctx, series_name, chapter, series_job)

                if account == False:
                    await ctx.send(embed=warning("The time between claiming and completing is too short. This job won't be counted towards your statistics."))
            return

        await ctx.respond(embed=error(f"Failed to update job."))

    @Jobs.command(description="Sets a job board channel for the specified job.")
    @check_authority(AuthorityLevel.ProjectManager)
    async def jobboard_set(self,
                           ctx,
                           job_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_job_list)), 
                           channel: discord.TextChannel):
        await ctx.defer()

        rows = ctx.bot.database.jobs.set_jobboard(job_name, channel.id)
        if rows is None:
            return await ctx.respond(embed=error(f"Failed to set the job board channel."))

        await ctx.respond(embed=info(f"The job board channel for job `{job_name}` has been set to <#{channel.id}>."))

    @Jobs.command(description="Removes job board channel for a job.")
    @check_authority(AuthorityLevel.ProjectManager)
    async def jobboard_remove(self,
                              ctx,
                              job_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_job_list))):
        await ctx.defer()

        rows  = ctx.bot.database.jobs.set_jobboard(job_name, None)
        if rows is None:
            return await ctx.respond(embed=error(f"Failed to remove the job board channel."))

        await ctx.respond(embed=info(f"The job board channel for job `{job_name}` has been removed."))