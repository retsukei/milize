import discord

class AuthorityLevel:
    Member = 0
    ProjectManager = 1
    Owner = 2

    @staticmethod
    def to_string(level):
        mapping = {
            AuthorityLevel.Member: "Member",
            AuthorityLevel.ProjectManager: "Project Manager",
            AuthorityLevel.Owner: "Owner"
        }
        return mapping.get(level, "Unknown")

    @staticmethod
    def to_choices():
        return [
            discord.OptionChoice(name="Member", value=AuthorityLevel.Member),
            discord.OptionChoice(name="Project Manager", value=AuthorityLevel.ProjectManager),
            discord.OptionChoice(name="Owner", value=AuthorityLevel.Owner)
        ]

class JobStatus:
    Backlog = 0
    Progress = 1
    Completed = 2

    @staticmethod
    def to_string(status):
        mapping = {
            JobStatus.Backlog: "Backlog",
            JobStatus.Progress: "In Progress",
            JobStatus.Completed: "Completed"
        }
        return mapping.get(status, "Unknown")

    @staticmethod
    def to_choices():
        return [
            discord.OptionChoice(name="Backlog", value=JobStatus.Backlog),
            discord.OptionChoice(name="In Progress", value=JobStatus.Progress),
            discord.OptionChoice(name="Completed", value=JobStatus.Completed)
        ]

class JobType:
    Translation = 0
    Proofreading = 1
    Redrawing = 2
    Cleaning = 3
    Typesetting = 4
    TypesettingSFX = 5
    Quality = 6
    Managment = 7

    @staticmethod
    def to_string(type):
        mapping = {
            JobType.Translation: "Translation",
            JobType.Proofreading: "Proofreading",
            JobType.Redrawing: "Redrawing",
            JobType.Cleaning: "Cleaning",
            JobType.Typesetting: "Typesetting",
            JobType.TypesettingSFX: "Typesetting (SFX)",
            JobType.Quality: "Quality Checking",
            JobType.Managment: "Project Managment"
        }
        return mapping.get(type, "Unknown")

    @staticmethod
    def to_choices():
        return [
            discord.OptionChoice(name="Translation", value=JobType.Translation),
            discord.OptionChoice(name="Proofreading", value=JobType.Proofreading),
            discord.OptionChoice(name="Redrawing", value=JobType.Redrawing),
            discord.OptionChoice(name="Cleaning", value=JobType.Cleaning),
            discord.OptionChoice(name="Typesetting", value=JobType.Typesetting),
            discord.OptionChoice(name="Typesetting (SFX)", value=JobType.TypesettingSFX),
            discord.OptionChoice(name="Quality Checking", value=JobType.Quality),
            discord.OptionChoice(name="Project Managment", value=JobType.Managment),
        ]

class ReminderNotification:
    Never = 0
    ThreeDays = 1
    SevenDays = 2
    FourteenDays = 3

    @staticmethod
    def to_string(type):
        return {
            ReminderNotification.Never: "Never",
            ReminderNotification.ThreeDays: "3 days",
            ReminderNotification.SevenDays: "7 days",
            ReminderNotification.FourteenDays: "14 days"
        }.get(type, "Unknown")

    @staticmethod
    def to_choices():
        return [
            discord.OptionChoice(name="Never", value=ReminderNotification.Never),
            discord.OptionChoice(name="3 days", value=ReminderNotification.ThreeDays),
            discord.OptionChoice(name="7 days", value=ReminderNotification.SevenDays),
            discord.OptionChoice(name="14 days", value=ReminderNotification.FourteenDays),
        ]

class StaffLevel:
    Trial = 0
    Probationary = 1
    Full = 2

    @staticmethod
    def to_string(level):
        return {
            StaffLevel.Trial: "Trial",
            StaffLevel.Probationary: "Probationary",
            StaffLevel.Full: "Full"
        }.get(level, "Unknown")

    @staticmethod
    def to_choices():
        return [
            discord.OptionChoice(name="Trial", value=StaffLevel.Trial),
            discord.OptionChoice(name="Probationary", value=StaffLevel.Probationary),
            discord.OptionChoice(name="Full", value=StaffLevel.Full),
        ]