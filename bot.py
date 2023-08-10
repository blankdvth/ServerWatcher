import requests
from json import load, dump
from os import environ, getenv, mkdir
from os.path import isdir, isfile
from time import time

import discord
from discord.ext import tasks, commands
from dotenv import load_dotenv

# Config Files
if not isdir("data"):
    mkdir("data")
if not isfile("data/config.json"):
    with open("data/config.json", "w") as f:
        dump({}, f)
with open("data/config.json") as f:
    config = load(f)

# Create Bot Instance
intents = discord.Intents.default()
intents.message_content = True
client = commands.Bot(
    command_prefix="sw?",
    intents=intents,
    allowed_mentions=discord.AllowedMentions(everyone=False, users=False, roles=False, replied_user=False)
)


def get_status(address):
    try:
        status = requests.get("https://api.mcsrvstat.us/3/" + address).json()
        if not status["online"] or status["ip"] == "127.0.0.1":
            return None
        return status
    except (Exception,):
        return None


async def update(channel_id, message_id, address):
    try:
        channel = client.get_channel(channel_id)
        message = await channel.fetch_message(message_id)
    except (Exception,):
        print(f"Deleted {message_id}, unreachable")
        del config[str(message_id)]
        with open("data/config.json", "w") as f:
            dump(config, f)
        return

    status = get_status(address)
    if status is None:
        return await message.edit(content="", embed=discord.Embed(title=f":x: {address}"))

    with open("data/config.json", "w") as f:
        dump(config, f)
    players_str = f"***{status['players']['online']}/{status['players']['max']} online***\n" + ("\n".join([f"- {player['name']}" for player in status['players']['list']]) if "list" in status['players'] else "")
    if len(players_str) > 4090:
        players_str = players_str[:4090] + "\n..."
    embed = discord.Embed(
        title=f":white_check_mark: {status['ip']}:{status['port']}" + (f" ({status['hostname']})" if "hostname" in status else ""),
        description=players_str
    )
    if "version" in status:
        embed.add_field(name="Version", value=status["version"])
    if "gamemode" in status:
        embed.add_field(name="Gamemode", value=status["gamemode"])
    if "software" in status:
        embed.add_field(name="Software", value=status["software"])
    if "motd" in status:
        embed.add_field(name="MOTD", value="\n".join(status["motd"]["clean"]), inline=False)
    if "plugins" in status:
        plugins_str = ", ".join([f"`{plugin['name']}`" for plugin in status['plugins']])
        if len(plugins_str) > 1020:
            plugins_str = plugins_str[:1020] + "..."
        embed.add_field(name=f"Plugins ({len(status['plugins'])})", value=plugins_str, inline=False)
    if "mods" in status:
        mods_str = ", ".join(f"`{mod['name']}`" for mod in status['mods'])
        if len(mods_str) > 1020:
            mods_str = mods_str[:1020] + "..."
        embed.add_field(name=f"Mods ({len(status['mods'])})", value=mods_str, inline=False)
    embed.add_field(name="Updated", value=f"<t:{int(time())}:R>", inline=False)

    await message.edit(content="", embed=embed)


class RefreshView(discord.ui.View):
    @discord.ui.button(style=discord.ButtonStyle.grey, label="Refresh")
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await update(config[str(interaction.message.id)]["channel_id"], interaction.message.id, config[str(interaction.message.id)]["address"])
        await interaction.response.defer()


@client.event
async def on_ready():
    for message_id, data in config.items():
        try:
            channel = client.get_channel(data["channel_id"])
            message = await channel.fetch_message(message_id)
            await message.edit(view=RefreshView(timeout=None))
        except (Exception,):
            continue
    await client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="MC servers (sw?watch)"))
    update_loop.start()
    print("Bot is ready")


@tasks.loop(minutes=5)
async def update_loop():
    for channel_id, message_id, address in [(v["channel_id"], k, v["address"]) for k, v in config.items()]:
        await update(channel_id, message_id, address)


@client.hybrid_command()
async def watch(ctx: commands.Context, *, address: str):
    message = await ctx.send("*Processing*")
    if not get_status(address):
        return await message.edit(content=":x: An error has occurred. Check your server address or try again later.")
    config[str(message.id)] = {"address": address, "channel_id": message.channel.id}
    with open("data/config.json", "w") as f:
        dump(config, f)
    await message.edit(view=RefreshView(timeout=None))
    await update(message.channel.id, message.id, address)


if __name__ == "__main__":
    if "BOT_TOKEN" not in environ:
        load_dotenv()
    BOT_TOKEN = getenv("BOT_TOKEN")
    if BOT_TOKEN is None:
        raise Exception("BOT_TOKEN could not be loaded from system environment variables or .env file")

    client.run(BOT_TOKEN)
