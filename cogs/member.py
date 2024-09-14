import discord
import os
from datetime import datetime
from discord.ext import commands
from discord.commands import SlashCommandGroup
from utils.embeds import info, error, member_info
from utils.checks import check_authority
from utils.constants import AuthorityLevel, ReminderNotification
from utils.autocompletes import get_group_list, get_series_list
from datetime import timezone

def format_time(hours):
    if hours >= 24:
        days = int(hours // 24)
        remaining_hours = int(hours % 24)
        plural = "" if days == 1 else "s"
        if remaining_hours > 0:
            return f"{days} day{plural}, {remaining_hours} hours"
        else:
            return f"{days} day{plural}"
    else:
        return f"{hours:.2f} hours"

def format_as_days(hours):
    if hours >= 24:
        days = int(hours // 24)
        plural = "" if days == 1 else "s"
        return f"{days} day{plural}"
    else:
        return "<1 day"

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

    @Member.command(description="Shows member's profile.")
    @check_authority(AuthorityLevel.Member)
    async def profile(self,
                      ctx,
                      user: discord.User = None):
        await ctx.defer()

        if not ctx.guild:
            return await ctx.respond(embed=error("Not allowed in DMs."))

        _user = ctx.author if user is None else user
        member_id = str(_user.id)

        member = ctx.bot.database.members.get(member_id)
        if member is None:
            return await ctx.respond(embed=error(f"<@{_user.id}> is not added to members in Milize."))

        assignments = ctx.bot.database.assignments.get_completed_by_user(member_id) or []
        archived_assignments = ctx.bot.database.assignments.get_completed_by_user_archive(member_id) or []

        all_assignments = assignments + archived_assignments
        total_completed = len(all_assignments)

        def convert_to_utc(dt):
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)


        qualified_jobs = ctx.bot.database.jobs.get_by_roles([str(role.id) for role in _user.roles])
        qualified_jobs_list = ", ".join(f"`{job}`" for job in qualified_jobs) if qualified_jobs else "None"

        now = datetime.now(timezone.utc)
        completed_at_dates = [convert_to_utc(a.completed_at) for a in all_assignments if a.completed_at]
        last_job = max(completed_at_dates, default=None)
        last_job_diff = (now - last_job).days if last_job else "N/A"
        
           
        embed = discord.Embed(
            title=f"{_user.display_name}'s profile",
            color=discord.Color.blue(),
            description=f"Credit name: `{member.credit_name if member.credit_name else _user.display_name}`"
        )
        embed.add_field(name="Qualified for", value=qualified_jobs_list, inline=False)
        embed.add_field(name="Authority Level", value=AuthorityLevel.to_string(member.authority_level), inline=True)
        embed.add_field(name="Total Completed", value=total_completed, inline=True)
        embed.add_field(name="Last Completed Job", value=f"{last_job_diff} day(s) ago", inline=False)

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
                return await ctx.respond(embed=error("Failed to update your notification preferences."))
        
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
            return await ctx.respond(embed=error("You're not added to members in Milize."))

        if member.jobboard_notifications:
            return await ctx.respond(embed=error("Please disable `jobboard_notifications` in `/member notifications` before subscribing to specific series."))

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
            return await ctx.respond(embed=error("You're not added to members in Milize."))

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
            return await ctx.respond(embed=error("You're not added to members in Milize."))

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

        if credit_name is None:
            await ctx.respond(embed=member_info("Your custom credit name has been removed. Your Discord display name will be used."))
        else:
            await ctx.respond(embed=member_info(f"Your credit name has been changed to `{credit_name}`."))

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

    @Member.command(description="Restores member from retired staff.")
    async def restore(self, ctx):
        await ctx.defer()

        member = ctx.bot.database.members.get_retired(str(ctx.author.id))
        if not member:
            return await ctx.respond(embed=error(f"Could not find {ctx.author.mention} in retired staff. Cannot restore."))

        guild = ctx.bot.get_guild(int(os.getenv("StaffGuildId")))
        try:
            user = await guild.fetch_member(int(member.discord_id))
            if user:
                await user.remove_roles(*user.roles[1:], reason="Member restore. Moving to active staff.")
                
                for role_id in member.roles:
                    role = guild.get_role(int(role_id))
                    if role:
                        await user.add_roles(role, reason="Member restore. Moving to active staff.")

                ctx.bot.database.members.restore_from_retired(member.member_id)
                inactivity_channel = ctx.bot.get_channel(int(os.getenv("InactivityChannelId")))
                if inactivity_channel:
                    role_mappings = {
                        os.getenv('StaffFullRoleId'): "full",
                        os.getenv('StaffProbationaryRoleId'): "probationary",
                        os.getenv('StaffTrialRoleId'): "trial",
                    }

                    role_name = next((role_mappings[role] for role in member.roles if role in role_mappings), None)

                    embed = discord.Embed(
                        title="Inactivity Notification",
                        description=(f"✅ Moved {role_name} staff {user.mention} from retired to active (they used `/member restore` command)."),
                        color=discord.Color.yellow()
                    )
                    await inactivity_channel.send(embed=embed)

                if any(role == os.getenv("StaffProbationaryRoleId") for role in member.roles):
                    await ctx.respond(embed=info("Your roles have been restored. You'll be removed from staff in `3 days` from now unless you claim a job. Welcome back!"))
                else:
                    await ctx.respond(embed=info("Your roles have been restored. You'll be moved back to inactive in `24 hours` from now unless you claim a job. Welcome back!"))
        except (discord.NotFound, discord.Forbidden, discord.HTTPException) as e:
            print(e)
            await ctx.respond(embed=error("Could not restore due to internal error."))

    @Member.command(description="Admits user to the staff.")
    @check_authority(AuthorityLevel.Owner)
    async def admit(self, ctx, user: discord.User):
        await ctx.defer()

        member = ctx.bot.database.members.get(str(user.id))
        if member:
            return await ctx.respond(embed=error(f"{user.mention} is already added to members in Milize. Cannot admit."))

        trial_role_id = os.getenv("StaffTrialRoleId")
        probationary_role_id = os.getenv("StaffProbationaryRoleId")
        full_role_id = os.getenv("StaffFullRoleId")

        roles_mapping = {
            os.getenv("StaffTrialRoleId"): "Trial",
            os.getenv("StaffProbationaryRoleId"): "Probationary",
            os.getenv("StaffFullRoleId"): "Full"
        }

        jobs = ctx.bot.database.jobs.get_all() 

        embed = discord.Embed(
            title=f"Admit {user.display_name} to Staff",
            description="Select the appropriate role and qualifications.",
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name="Admit as:", value="Select a role from the menu below.", inline=False)
        embed.add_field(name="Added qualifications:", value="None", inline=False)
        embed.add_field(name="Available qualifications:", value=", ".join([f"`{job.job_name}`" for job in jobs]), inline=False)

        role_select = discord.ui.Select(
            placeholder="Select a role...",
            options=[
                discord.SelectOption(label="Trial Staff", value=trial_role_id, description="Admit as Trial Staff"),
                discord.SelectOption(label="Probationary Staff", value=probationary_role_id, description="Admit as Probationary Staff"),
                discord.SelectOption(label="Full Staff", value=full_role_id, description="Admit as Full Staff"),
            ]
        )

        add_button = discord.ui.Button(label="Add Qualification", style=discord.ButtonStyle.primary, custom_id="add_qualification")
        remove_button = discord.ui.Button(label="Remove Qualification", style=discord.ButtonStyle.danger, custom_id="remove_qualification")
        admit_button = discord.ui.Button(label="Admit", style=discord.ButtonStyle.success, custom_id="admit", row=2)
        cancel_button = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.secondary, custom_id="cancel", row=2)

        view = discord.ui.View()
        view.add_item(role_select)
        view.add_item(add_button)
        view.add_item(remove_button)
        view.add_item(admit_button)
        view.add_item(cancel_button)
        view.timeout = 120 # in seconds

        message = await ctx.respond(embed=embed, view=view)

        selected_role = None
        added_qualifications = []

        async def update_embed():
            embed.set_field_at(1, name="Added qualifications:", value=", ".join([f"`{q.job_name}`" for q in added_qualifications]) or "None", inline=False)
            embed.set_field_at(2, name="Available qualifications:", value=", ".join([f"`{job.job_name}`" for job in jobs]), inline=False)
            await message.edit(embed=embed)

        async def on_timeout():
            try:
                await message.delete()
            except discord.DiscordException:
                pass

        async def role_select_callback(interaction: discord.Interaction):
            if interaction.user.id != ctx.author.id:
                return

            nonlocal selected_role
            selected_role = role_select.values[0]
            embed.set_field_at(0, name="Admit as:", value=roles_mapping.get(selected_role) + " Staff", inline=False)
            await interaction.response.defer()
            await update_embed()

        async def add_qualification_callback(interaction: discord.Interaction):
            if interaction.user.id != ctx.author.id:
                return

            async def qualification_modal_callback(interaction: discord.Interaction):
                await interaction.response.defer()
                qualification = interaction.data['components'][0]['components'][0]['value']
                idx = next((i for i, job in enumerate(jobs) if job.job_name == qualification), None)
                if idx is not None:
                    added_qualifications.append(jobs[idx])
                    del jobs[idx]
                    await update_embed()

            modal = discord.ui.Modal(discord.ui.InputText(label="Qualification", placeholder="Enter qualification name..."), title="Add Qualification" )
            modal.callback = qualification_modal_callback
            await interaction.response.send_modal(modal)

        async def remove_qualification_callback(interaction: discord.Interaction):
            if interaction.user.id != ctx.author.id:
                return

            async def qualification_modal_callback(interaction: discord.Interaction):
                await interaction.response.defer()
                qualification = interaction.data['components'][0]['components'][0]['value']
                idx = next((i for i, q in enumerate(added_qualifications) if q.job_name == qualification), None)
                if idx is not None:
                    jobs.append(added_qualifications[idx])
                    del added_qualifications[idx]
                    await update_embed()

            modal = discord.ui.Modal(discord.ui.InputText(label="Qualification", placeholder="Enter qualification name..."), title="Remove Qualification" )
            modal.callback = qualification_modal_callback
            await interaction.response.send_modal(modal)

        async def admit_callback(interaction: discord.Interaction):
            if interaction.user.id != ctx.author.id:
                return

            if not selected_role:
                return

            if not added_qualifications:
                return

            await interaction.response.defer()
            roles_to_add = [discord.Object(id=int(selected_role))] + [discord.Object(id=int(q.role_id)) for q in added_qualifications]
            
            try:
                await user.add_roles(*roles_to_add)
                await interaction.message.edit(embed=info(f"Admitted {user.mention} to `{roles_mapping.get(selected_role)} Staff` with specified qualifications."), view=None)
                ctx.bot.database.members.add(str(user.id), AuthorityLevel.Member)

                channel = ctx.bot.get_channel(int(os.getenv("StaffChannelId")))
                if channel:
                    await channel.send(content=(
                        f"Everyone, please welcome {user.mention}! They're joining as {roles_mapping.get(selected_role).lower()} staff with the following qualifications: {', '.join(f'`{q.job_name}`' for q in added_qualifications)}"
                        f"\n\n{user.mention}, please read through https://discord.com/channels/1131989690715754602/1132960194079506534/1194692208868196465 and https://discord.com/channels/1131989690715754602/1133152558479851550/1172466011988045834 "
                        f"to get up on how things here work. Also, feel free to introduce yourself in <#1187150382372237342>"
                        f"\nUse `/member credit_name` command to change your credit name and check out the job board channels for available jobs!"
                    ))
            except discord.DiscordException as e:
                print(f"An error occurred while admitting '{user.display_name}': {e}")

        async def cancel_callback(interaction: discord.Interaction):
            if interaction.user.id != ctx.author.id:
                return

            await interaction.response.defer()
            try:
                await interaction.message.delete()
            except discord.DiscordException:
                pass            

        view.on_timeout = on_timeout
        role_select.callback = role_select_callback
        add_button.callback = add_qualification_callback
        remove_button.callback = remove_qualification_callback
        admit_button.callback = admit_callback
        cancel_button.callback = cancel_callback
