import discord
import os
from .embeds import info

class JobboardView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Claim", custom_id="jobboard_claim_button", style=discord.ButtonStyle.primary)
    async def button_callback(self, button, interaction):
        jobboard_post = interaction.client.database.boardposts.get_by_message(str(interaction.message.id))

        if not jobboard_post:
            await interaction.message.delete()
            return

        role_to_level = {
            int(os.getenv('StaffTrialRoleId')): 0,
            int(os.getenv('StaffProbationaryRoleId')): 1,
            int(os.getenv('StaffFullRoleId')): 2
        }

        member = interaction.user
        if interaction.client.database.members.get(str(member.id)) is None:
            return

        user_staff_level = -1 
        for role in member.roles:
            if role.id in role_to_level:
                user_staff_level = max(user_staff_level, role_to_level[role.id])
        
        if user_staff_level < jobboard_post.staff_level:
            return

        is_first_job = interaction.client.database.assignments.is_first(str(member.id))
        assignment_id = interaction.client.database.assignments.new(jobboard_post.chapter_id, jobboard_post.series_job_id, str(member.id))
        if assignment_id is None:
            return

        await interaction.message.delete()
        interaction.client.database.boardposts.delete(jobboard_post.boardpost_id)

        chapter = interaction.client.database.chapters.get_by_id(jobboard_post.chapter_id)
        series = interaction.client.database.series.get_by_id(chapter.series_id)
        series_job = interaction.client.database.jobs.get_added_by_id(jobboard_post.series_job_id)

        channel = interaction.client.get_channel(int(os.getenv("MilizeChannelId")))
        if channel:
            if chapter.is_archived:
                return await channel.send(content=f"<@{member.id}>, chapter `{chapter.chapter_name}` for series `{series.series_name}` is archived. Cannot claim.")

            additional_info = []

            if chapter.drive_link:
                additional_info.append(f"Google Folder: [Click]({chapter.drive_link})")

            if series.style_guide:
                additional_info.append(f"Style Guide: [Click]({series.style_guide})")

            additional_info_message = " — ".join(additional_info) if additional_info else ""
            await channel.send(content=f"Job board action from <@{member.id}>:", embed=info(f"Job `{series_job.job_name}` has been claimed for chapter `{chapter.chapter_name}` in `{series.series_name}`.\n{additional_info_message}"))

            if is_first_job:
                await channel.send(embed=info("Since this is your first job, please consider checking if there's any important material to read (like a style guide). Usually, it's available in the pinned messages for the channel of the series."))