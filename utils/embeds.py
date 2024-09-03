import discord

def info(message: str, title: str = None):
    return discord.Embed(title=title, description=message, color=discord.Color.green())

def member_info(message: str, title: str = None):
    return discord.Embed(title=title, description=message, color=discord.Color.blue())

def error(message: str):
    return discord.Embed(description=message, color=discord.Color.red())

def warning(message: str):
    return discord.Embed(description=message, color=discord.Color.orange())