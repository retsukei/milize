import discord
import requests
import re
import os
import langcodes
import zipfile
import warnings
import psd_tools
from PIL import Image
from datetime import datetime, timedelta, timezone
from discord.ext import commands
from discord.commands import SlashCommandGroup
from natsort import natsorted
from urllib.parse import urlparse
from utils.embeds import info, error
from utils.checks import check_authority
from utils.constants import AuthorityLevel, StaffLevel, JobStatus, JobType
from utils.autocompletes import get_group_list, get_series_list, get_added_jobs, get_chapter_list
from utils.views import JobboardView
from utils.titlecase import to_title_case

warnings.filterwarnings("ignore", module="psd_tools")

def normalize_language(name: str) -> str | None:
    try:
        return langcodes.find(name).language
    except LookupError:
        return None

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
            return await ctx.respond(embed=error("Reached the limit of chapters per series. Remove (or archive) some before adding more."))

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
                                item_match = re.search(r'\d+(\.\d+)?', item['name'])
                                if item_match:
                                    matches = float(re.search(r'\d+(\.\d+)?', chapter_name)[0]) == float(re.search(r'\d+(\.\d+)?', item['name'])[0])

                            if matches:
                                chapter_drive_link = f"https://drive.google.com/drive/folders/{item['id']}"

        chapter_id = ctx.bot.database.chapters.new(series_name, chapter_name, chapter_drive_link)
        if chapter_id is None:
            return await ctx.respond(embed=error(f"Chapter `{chapter_name}` for series `{series_name}` is already in the database (or errored while adding.)"))

        # Add series-based assignments.
        series_assignments = ctx.bot.database.series.get_assignments(series.series_id)
        if series_assignments:
            for assignment in series_assignments:
                assignment_id = ctx.bot.database.assignments.new(chapter_id, assignment.series_job_id, assignment.assigned_to)
                if assignment_id is None:
                    return await ctx.respond(embed=error("Failed to add series-based assignments for this chapter."))

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

        if str(ctx.author.id) != os.getenv("DiscordDevId"):
            return await ctx.respond(embed=error(f"Use the `/chapter archive` command to archive a completed chapter.\nIf you need to delete a chapter, ping <@{os.getenv('DiscordDevId')}>"))

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

    @Chapter.command(description="Cancels a scheduled upload.")
    @check_authority(AuthorityLevel.Owner)
    async def schedule_cancel(self,
                              ctx,
                              upload_id: discord.Option(int, description="Upload ID.")):
        await ctx.defer()

        scheduled_upload = ctx.bot.database.chapters.get_scheduled_upload(upload_id)
        if not scheduled_upload:
            return await ctx.respond(embed=error(f"No scheduled upload with ID `{upload_id}` was found."))
        
        ctx.bot.database.chapters.delete_upload_schedule(upload_id)
        await ctx.respond(embed=info(f"Scheduled upload with ID `{upload_id}` has been canceled."))

    @Chapter.command(description="Schedules a chapter for upload on mangadex.")
    @check_authority(AuthorityLevel.Owner)
    async def schedule(self,
                       ctx,
                       group_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_group_list)),
                       series_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_series_list)),
                       chapter_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_chapter_list)),
                       recruitment_page: discord.Option(discord.Attachment, description="Attach recruitment page png.") = None,
                       credit_page: discord.Option(discord.Attachment, description="Attach credit page png.") = None,
                       additional_page1: discord.Option(discord.Attachment, description="Additional page 1") = None,
                       additional_page2: discord.Option(discord.Attachment, description="Additional page 2") = None,
                       additional_page3: discord.Option(discord.Attachment, description="Additional page 3") = None,
                       grayscale: discord.Option(bool, description="If the pages should be grayscale'd (applied by defailt)") = True):
        await ctx.defer()

        if not ctx.guild:
            return await ctx.respond(embed=error("Not allowed in DMs."))
        
        if not ctx.bot.mangadex.access_token:
            return await ctx.respond(embed=error("MangaDex.API is not initialized. Scheduling is not possible."))
        
        group_names = [group_name]

        # Sanity checks
        groups = []
        for name in group_names:
            group = ctx.bot.database.groups.get_by_name(name)
            if not group:
                return await ctx.respond(embed=error(f"Failed to get group `{name}`."))
            
            if not group.website or "mangadex.org/group/" not in group.website:
                return await ctx.respond(embed=error(f"Group `{name}` does not have mangadex link attached or it's incorrect. Cannot upload."))

            groups.append(group)

        series = ctx.bot.database.series.get(group_name, series_name)
        if not series:
            return await ctx.respond(embed=error(f"Failed to get series `{series_name}` by `{group_name}`."))

        chapter = ctx.bot.database.chapters.get(series_name, chapter_name)
        if not chapter:
            return await ctx.respond(embed=error(f"Failed to get chapter `{chapter_name}` for series `{series_name}`."))
        
        # Check if chapter is already scheduled for upload.
        scheduled_upload = ctx.bot.database.chapters.get_scheduled_upload_by_chapter(chapter.chapter_id)
        if scheduled_upload:
            return await ctx.respond(embed=error(f"Chapter `{chapter_name}` is already scheduled for upload."))

        if chapter.is_archived:
            return await ctx.respond(embed=error(f"Chapter `{chapter_name}` is archived. Cannot upload."))
        
        if not chapter.drive_link:
            return await ctx.respond(embed=error(f"Chapter `{chapter_name}` does not have GDrive link attached. Cannot upload."))
        
        if not series.mangadex or "mangadex.org/title/" not in series.mangadex:
            return await ctx.respond(embed=error(f"Series `{series_name}` does not have MangaDex link attached or it's incorrect. Cannot upload."))
        
        response = requests.get(f"{os.getenv('KeiretsuUrl')}/api/list?id={re.search(r'/folders/([a-zA-Z0-9_-]+)', chapter.drive_link)[1]}")
        if response.status_code != 200:
            return await ctx.respond(embed=error("Failed to list drive files for the chapter or no 'tspr' folder is present."))
        
        typesetting_folder = next(
            (item for item in response.json().get("files", []) if "tspr" in item["name"]),
            None
        )

        response = requests.get(f"{os.getenv('KeiretsuUrl')}/api/list?id={typesetting_folder['id']}")
        if response.status_code != 200:
            return await ctx.respond(embed=error("Failed to count the amount of pages. Cannot upload."))
        
        files = response.json().get("files", [])
        filtered_files = [file for file in files if file.get("mimeType") != 'application/vnd.google-apps.folder']
        page_count = len(filtered_files)

        if page_count < 1:
            return await ctx.respond(embed=error("No .PSD files found in the chapter."))
        
        additional_pages = [recruitment_page, credit_page, additional_page1, additional_page2, additional_page3]
        additional_pages_count = sum(1 for page in additional_pages if page is not None)

        embed = discord.Embed(
            title="Scheduling for upload",
            color=discord.Color.blue()
        )
        embed.add_field(name="Volume Number", value="None", inline=True)
        embed.add_field(name="Chapter Number", value="None", inline=True)
        embed.add_field(name="Scanlation Language", value="English", inline=True)
        embed.add_field(name="Chapter Name", value="None", inline=True)
        embed.add_field(name="Grayscale", value=grayscale, inline=True)
        embed.add_field(name="Groups", value=", ".join(group_names) + ", Keiretsu", inline=False)
        embed.add_field(name="Number of pages", value=f"{page_count}" if additional_pages_count < 1 else f"{page_count} + {additional_pages_count} additional", inline=False)
        embed.add_field(name="To be uploaded at", value="None", inline=False)

        if series.thumbnail:
            embed.set_thumbnail(url=series.thumbnail)

        metadata_button = discord.ui.Button(label="Metadata", style=discord.ButtonStyle.primary, custom_id="schedule_metadata")
        time_button = discord.ui.Button(label="Time", style=discord.ButtonStyle.primary, custom_id="schedule_time")
        add_group_button = discord.ui.Button(label="Add Group", style=discord.ButtonStyle.primary, custom_id="schedule_add_group")
        remove_group_button = discord.ui.Button(label="Remove Group", style=discord.ButtonStyle.primary, custom_id="schedule_remove_group")
        schedule_button = discord.ui.Button(label="Schedule", style=discord.ButtonStyle.success, custom_id="schedule_schedule", row=2)
        cancel_button = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.danger, custom_id="schedule_cancel", row=2)

        view = discord.ui.View()
        view.add_item(metadata_button)
        view.add_item(time_button)
        view.add_item(add_group_button)
        view.add_item(remove_group_button)
        view.add_item(schedule_button)
        view.add_item(cancel_button)
        view.timeout = 120 # in seconds

        message = await ctx.respond(embed=embed, view=view)

        volume_number = None
        chapter_number = None
        scan_language = "English"
        chapter_name_local = None
        upload_time = None
        proceed_called = False

        async def update_embed():
            embed.set_field_at(0, name="Volume Number", value=volume_number or "None", inline=True)
            embed.set_field_at(1, name="Chapter Number", value=chapter_number or "None", inline=True)
            embed.set_field_at(2, name="Scanlation Language", value=scan_language or "None", inline=True)
            embed.set_field_at(3, name="Chapter Name", value=chapter_name_local or "None", inline=True)
            embed.set_field_at(5, name="Groups", value=", ".join(group.group_name for group in groups) + ", Keiretsu", inline=False)
            embed.set_field_at(7, name="To be uploaded at", value=f"{upload_time} UTC" or "None", inline=False)
            await message.edit(embed=embed)

        async def on_timeout():
            try:
                if proceed_called:
                    return
                
                await message.delete()
            except discord.DiscordException:
                pass

        async def on_proceed_timeout():
            try:
                await message.edit(view=None)
            except discord.DiscordException:
                pass

        async def metadata_callback(interaction: discord.Interaction):
            if interaction.user.id != ctx.author.id:
                return

            async def metadata_modal_callback(interaction: discord.Interaction):
                await interaction.response.defer()
                nonlocal volume_number
                nonlocal chapter_number
                nonlocal scan_language
                nonlocal chapter_name_local

                volume_number = interaction.data['components'][0]['components'][0]['value'] or volume_number
                chapter_number = interaction.data['components'][1]['components'][0]['value'] or chapter_number
                chapter_name_local = interaction.data['components'][2]['components'][0]['value'] or chapter_name_local
                scan_language = interaction.data['components'][3]['components'][0]['value'] or scan_language

                await update_embed()

            modal = discord.ui.Modal(
                discord.ui.InputText(label="Volume Number", placeholder="Enter volume number...", required=False),
                discord.ui.InputText(label="Chapter Number", placeholder="Enter chapter number...", required=False),
                discord.ui.InputText(label="Chapter Name", placeholder="Enter chapter name...", required=False),
                discord.ui.InputText(label="Scanlation Language", placeholder="Enter scanlation language...", required=False),
                title="Chapter Metadata" )
            modal.callback = metadata_modal_callback
            await interaction.response.send_modal(modal)

        async def time_callback(interaction: discord.Interaction):
            if interaction.user.id != ctx.author.id:
                return
            
            async def time_modal_callback(interaction: discord.Interaction):
                await interaction.response.defer()

                nonlocal upload_time
                upload_time_str = interaction.data['components'][0]['components'][0]['value']
                try:
                    upload_time = datetime.strptime(upload_time_str, "%Y-%m-%d %H:%M")
                except ValueError:
                    upload_time = "Invalid format."

                await update_embed()
            
            modal = discord.ui.Modal(
                discord.ui.InputText(label="Upload Time (in UTC)", placeholder="YYYY-MM-DD HH:MM"),
                title="Upload Time"
            )
            modal.callback = time_modal_callback
            await interaction.response.send_modal(modal)

        async def add_group_callback(interaction: discord.Interaction):
            if interaction.user.id != ctx.author.id:
                return
            
            async def add_group_modal_callback(interaction: discord.Interaction):
                await interaction.response.defer()

                nonlocal groups
                nonlocal ctx

                group_name_str = interaction.data['components'][0]['components'][0]['value']
                group = ctx.bot.database.groups.get_by_name(group_name_str)
                if group and "mangadex.org/group/" in group.website:
                    groups.append(group)

                await update_embed()

            modal = discord.ui.Modal(
                discord.ui.InputText(label="Group Name", placeholder="Enter group name..."),
                title="Add Group"
            )
            modal.callback = add_group_modal_callback
            await interaction.response.send_modal(modal)

        async def remove_group_callback(interaction: discord.Interaction):
            if interaction.user.id != ctx.author.id:
                return

            async def remove_group_modal_callback(interaction: discord.Interaction):
                await interaction.response.defer()

                nonlocal groups
                nonlocal ctx

                group_name_str = interaction.data['components'][0]['components'][0]['value']
                group = ctx.bot.database.groups.get_by_name(group_name_str)
                if group and group in groups:
                    groups.remove(group)

                await update_embed()

            modal = discord.ui.Modal(
                discord.ui.InputText(label="Group Name", placeholder="Enter group name to remove..."),
                title="Remove Group"
            )
            modal.callback = remove_group_modal_callback
            await interaction.response.send_modal(modal)

        async def cancel_callback(interaction: discord.Interaction):
            if interaction.user.id != ctx.author.id:
                return

            await interaction.response.defer()
            try:
                await interaction.message.delete()
            except discord.DiscordException:
                pass

        async def proceed_callback(interaction: discord.Interaction):
            if interaction.user.id != ctx.author.id:
                return
            
            nonlocal chapter
            nonlocal upload_time
            nonlocal proceed_called
            nonlocal series
            nonlocal volume_number
            nonlocal chapter_number
            nonlocal chapter_name_local
            nonlocal scan_language

            proceed_called = True
            
            await interaction.response.defer()
            await interaction.message.edit(embed=info(":hourglass: Searching for 'tspr' folder..."), view=None)

            match = re.search(r'/folders/([a-zA-Z0-9_-]+)', chapter.drive_link)
            if not match:
                return await interaction.message.edit(embed=error("Could not extract ID from the gdrive link."))
            
            list_url = f"{os.getenv('KeiretsuUrl')}/api/list?id={match[1]}"
            try:
                list_response = requests.get(list_url)
                list_response.raise_for_status()
            except requests.exceptions.RequestException as e:
                print(e)
                return await interaction.message.edit(embed=error("An error occurred while fetching the folder list."))

            files = list_response.json()['files']
            tspr_folder_id = None
            for file in files:
                if 'tspr' in file['name']:
                    tspr_folder_id = file['id']
                    break

            if not tspr_folder_id:
                return await interaction.message.edit(embed=error("Could not find the typesetting folder."))

            download_url = f"{os.getenv('KeiretsuUrl')}/api/download_zip?id={tspr_folder_id}"

            await interaction.message.edit(embed=info(":hourglass: Downloading PSDs from Google Drive..."))
            try:
                response = requests.get(download_url)
                response.raise_for_status()
            except requests.exceptions.RequestException as e:
                print(e)
                return await interaction.message.edit(embed=error("An error occurred while downloading the PSDs. The `tspr` folder might be empty."))

            content_disposition = response.headers.get('Content-Disposition', '')
            if 'filename=' in content_disposition:
                filename = content_disposition.split('filename=')[1].strip('\"')
            else:
                filename = os.path.basename(urlparse(download_url).path)

            zip_file_path = os.path.join('./data', filename)
            extracted_folder_path = os.path.join('./data', os.path.splitext(filename)[0])

            with open(zip_file_path, 'wb') as f:
                f.write(response.content)

            try:
                with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
                    zip_ref.extractall(extracted_folder_path)
            except zipfile.BadZipFile:
                return await interaction.message.edit(embed=error("The downloaded file is not a valid zip file."))
            
            try:
                os.remove(zip_file_path)
            except OSError as e:
                print(f"Error deleting file {zip_file_path}: {e}")
                return await interaction.message.edit(embed=error("An error occurred while cleaning up the .zip file."))

            await interaction.message.edit(embed=info(":hourglass: Converting .PSDs to .PNGs..."), view=None)

            try:
                psd_files = [f for f in os.listdir(extracted_folder_path) if f.lower().endswith('.psd')]
                if not psd_files:
                     return await interaction.message.edit(embed=error("No PSD files found to convert."))
                
                for psd_file in psd_files:
                    psd_file_path = os.path.join(extracted_folder_path, psd_file)

                    psd = psd_tools.PSDImage.open(psd_file_path)
                    image = psd.composite()

                    if grayscale:
                        image = image.convert('L')
                        image = image.convert('P', palette=Image.ADAPTIVE, colors=256)

                    png_file_path = os.path.join(extracted_folder_path, os.path.splitext(psd_file)[0] + '.png')
                    image.save(png_file_path, format='PNG', optimize=True)

                    os.remove(psd_file_path)

                png_files = [f for f in os.listdir(extracted_folder_path) if f.lower().endswith('.png')]
                get_num = lambda f: int(''.join(filter(str.isdigit, os.path.splitext(f)[0])) or 0)
                max_page = max((get_num(f) for f in png_files), default=0) + 1

                attachments_to_save = [additional_page1, additional_page2, additional_page3, recruitment_page, credit_page]
                for attachment in attachments_to_save:
                    if attachment:
                        response = requests.get(attachment.url)
                        if response.status_code == 200:
                            local_filename = os.path.join(extracted_folder_path, f"{max_page:03}.png")
                            with open(local_filename, 'wb') as f:
                                f.write(response.content)

                            max_page += 1
                        else:
                            await interaction.message.edit(embed=error("Failed to save additional pages."))
                            return

                group_ids = [
                    match.group(1)
                    for group in groups
                    if (website := group.website) and (match := re.search(r"mangadex\.org/group/([\w-]+)", website))
                ]
                group_ids.append(os.getenv("MangaDexKeiretsuId"))

                series_id = re.search(r"mangadex\.org/title/([\w-]+)", series.mangadex)[1]

                upload_id = ctx.bot.database.chapters.new_upload_schedule(
                    volume_number,
                    chapter_number,
                    normalize_language(scan_language),
                    chapter_name_local,
                    group_ids,
                    series_id,
                    extracted_folder_path,
                    upload_time,
                    ctx.author.id,
                    series.series_name,
                    group.group_name,
                    chapter.chapter_id
                )

                if not upload_id:
                    await interaction.message.edit(embed=error("Failed to create record for scheduled upload."))
                    return

                await interaction.message.edit(embed=info(f"Scheduled upload confirmed. It will be uploaded <t:{int(upload_time.timestamp())}:R>\nThe upload ID is `{upload_id}`. Use it as input if you need to cancel using `/chapter schedule_cancel`"), view=None)

            except Exception as e:
                print(f"Error converting PSDs to PNG: {e}")
                await interaction.message.edit(embed=error("An error occurred while converting PSD files to PNG."), view=None)

        async def schedule_callback(interaction: discord.Interaction):
            if interaction.user.id != ctx.author.id:
                return
            
            await interaction.response.defer()

            nonlocal chapter_name_local
            nonlocal chapter_number
            nonlocal volume_number
            nonlocal scan_language
            nonlocal upload_time
            nonlocal groups

            if upload_time:
                upload_time = upload_time.replace(tzinfo=timezone.utc)

            def is_number(s: str) -> bool:
                try:
                    float(s)
                    return True
                except ValueError:
                    return False
            
            # Check everything and raise all issues before uploading.
            schedule_attempt_issues = []

            # Check metadata
            if not chapter_number or not is_number(chapter_number):
                schedule_attempt_issues.append({ "message": "Chapter number must be specified as a number.", "critical": True })

            if not volume_number:
                schedule_attempt_issues.append({ "message": "Volume number is not specified.", "critical": False })
            elif not is_number(volume_number):
                schedule_attempt_issues.append({ "message": "Volume number must be specified as a number.", "critical": True })

            if not upload_time or not isinstance(upload_time, datetime):
                schedule_attempt_issues.append({
                    "message": "Upload time is not set or invalid.",
                    "critical": True
                })
            elif upload_time <= datetime.now(timezone.utc):
                schedule_attempt_issues.append({
                    "message": "Upload time must be in the future.",
                    "critical": True
                })

            if not chapter_name_local:
                schedule_attempt_issues.append({ "message": "Chapter title must be specified.", "critical": True })
            elif to_title_case(chapter_name_local) != chapter_name_local:
                schedule_attempt_issues.append({ "message": f"Chapter name does not match with Chicago Title Case Style (`{to_title_case(chapter_name_local)}`)", "critical": False })

            # Check if an actual language
            if not normalize_language(scan_language):
                schedule_attempt_issues.append({ "message": f"Language `{scan_language}` could not be found or normalized.", "critical": True })

            # Check if uploader added as a member to all groups
            if not groups or not isinstance(groups, list) or not all(groups):
                schedule_attempt_issues.append({
                    "message": "At least one scanlation group must be selected.",
                    "critical": True
                })
            elif groups:
                for group in groups:
                    match = re.search(r"https?://mangadex\.org/group/([a-fA-F0-9-]{36})", group.website)
                    if not match:
                        schedule_attempt_issues.append({ "message": "One of the groups' website did not match mangadex group URL regex.", "critical": True })
                        break

                    group_data = ctx.bot.mangadex.group_by_id(match[1])
                    relationships = group_data["relationships"]
                    if not any(entry["id"] == ctx.bot.mangadex.uploader_uuid for entry in relationships):
                        schedule_attempt_issues.append({ "message": f"`{group.group_name}` does not have `{os.getenv('MangaDexLogin')}` added to its members on mangadex.", "critical": True })
                        break

            description = ""
            critical = any(entry["critical"] for entry in schedule_attempt_issues)

            if len(schedule_attempt_issues) > 0:
                description = "__**Upload Schedule Validator raised the following issues:**__"
                for issue in schedule_attempt_issues:
                    description += f"\n{':x:' if issue['critical'] else ':warning:'} {issue['message']}"

                if critical:
                    description += "\n\nAt least one was raised as `critical`. You can not proceed with the upload."
                else:
                    description += "\n\nNone were raised as `critical`, so you can proceed with the upload."
            else:
                description = ":white_check_mark: Upload Schedule Validator did not find any issues. You can proceed with the upload"

            embed = discord.Embed(
                description=description,
                color=discord.Color.blue()
            )

            proceed_button = discord.ui.Button(label="Proceed", style=discord.ButtonStyle.green)
            proceed_button.callback = proceed_callback

            cancel_button = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.red)
            cancel_button.callback = cancel_callback

            view = None

            if not critical:
                view = discord.ui.View()
                view.add_item(proceed_button)
                view.add_item(cancel_button)

                view.timeout = 120
                view.on_timeout = on_proceed_timeout

            await interaction.message.edit(embed=embed, view=view)

        view.on_timeout = on_timeout
        metadata_button.callback = metadata_callback
        time_button.callback = time_callback

        add_group_button.callback = add_group_callback
        remove_group_button.callback = remove_group_callback

        cancel_button.callback = cancel_callback
        schedule_button.callback = schedule_callback


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

        await ctx.respond(embed=info(f"A post for `{job_name}` for chapter `{chapter_name}` has been made.\nThe post will be automatically deleted in **30 days** if not claimed.\nYou'll have to re-post it manually in that case."))

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
    @check_authority(AuthorityLevel.ProjectManager)
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

    @Chapter.command(description="Shows the progress of a chapter.")
    async def progress(self,
                       ctx,
                       group_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_group_list)),
                       series_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_series_list)),
                       chapter_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_chapter_list))):
        await ctx.defer()

        chapter = ctx.bot.database.chapters.get(series_name, chapter_name)
        if not chapter:
            return await ctx.respond(embed=error(f"Not found chapter `{chapter_name}` for series `{series_name}`."))

        series_jobs = ctx.bot.database.jobs.get_added_all(series_name)
        if series_jobs is None:
            return await ctx.respond(embed=error(f"Failed to get jobs for series `{series_name}`."))

        embed = discord.Embed(
            color=discord.Color.blue(),
            description=f"**Chapter {chapter.chapter_name}:** All jobs are completed!"
        )
        embed.set_author(name=f"{series_name} ({group_name})")

        for job in series_jobs:
            assignment = ctx.bot.database.assignments.get(chapter.chapter_id, job.series_job_id)
            if not assignment or assignment.status != JobStatus.Completed:
                embed.description = f"**Chapter {chapter.chapter_name}:** Currently waiting for `{JobType.to_string(job.job_type)}` to be completed.\nWe apologize for any delays {os.getenv('MilizeDownEmoji')}"
                return await ctx.respond(embed=embed)

        await ctx.respond(embed=embed)

    @Chapter.command(description="Marks all assignments in a chapter as completed.")
    @check_authority(AuthorityLevel.ProjectManager)
    async def complete(self,
                        ctx,
                        group_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_group_list)),
                        series_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_series_list)),
                        chapter_name: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_chapter_list))):
        await ctx.defer()

        chapter = ctx.bot.database.chapters.get(series_name, chapter_name)
        if chapter is None:
            return await ctx.respond(embed=error(f"Failed to get chapter `{chapter_name}` for series `{series_name}`."))

        assignments = ctx.bot.database.assignments.get_for_chapter(chapter.chapter_id)
        if not assignments:
            return await ctx.respond(embed=error(f"No assignments found for chapter `{chapter_name}`."))

        for assignment in assignments:
            account = True
            if datetime.now(timezone.utc) - assignment.created_at < timedelta(minutes=5):
                account = False

            ctx.bot.database.assignments.update_status(chapter.chapter_id, assignment.series_job_id, JobStatus.Completed, account)

        line = f"All assignments in chapter `{chapter_name}` for series `{series_name}` have been marked as `Completed`."
        await ctx.respond(embed=info(line))