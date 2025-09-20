import discord
import random
from discord.ext import commands
import requests
from flask import Flask
from threading import Thread
import os
app=Flask('') 
@app.route('/')
def home():
    return "I am alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# 🔒 SECURITY: Store your bot token in env or config.json
TOKEN = os.getenv('DISCORD_BOT_TOKEN')
if not TOKEN:
    print("❌ ERROR: DISCORD_BOT_TOKEN environment variable not set!")
    print("Please set your Discord bot token in the Secrets tab.")
    exit(1)


BASE = "https://vizualabstract.github.io/StarRailStaticAPI/db/en/characters.json"
API_URL = "https://hsr-api.vercel.app/api/v1/characters"
ICON = "https://raw.githubusercontent.com/VizualAbstract/StarRailStaticAPI/main/assets"

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

RELIC = "https://vizualabstract.github.io/StarRailStaticAPI/db/en/relic_sub_affixes.json"
response = requests.get(RELIC).json()

dict1 = {
    "HPDelta": "HP",
    "AttackDelta": "ATK",
    "DefenceDelta": "DEF",
    "HPAddedRatio": "HP%",
    "AttackAddedRatio": "ATK%",
    "DefenceAddedRatio": "DEF%",
    "SpeedDelta": "SPD",
    "CriticalChanceBase": "CRIT Rate%",
    "CriticalDamageBase": "CRIT DMG%",
    "StatusProbabilityBase": "Effect Hit Rate%",
    "StatusResistanceBase": "Effect RES%",
    "BreakDamageAddedRatioBase": "Break Effect%",
}

weights = [10, 10, 10, 8, 8, 8, 3, 4, 4, 6, 6, 6]

# ------------------------
# Relic Rolling System
# ------------------------
def roll_relic():
    visited = set()
    substats = []

    x = random.choices([4, 5], weights=[0.9, 0.1], k=1)[0]  # number of substats
    values = {}

    for _ in range(x):
        y = random.choices(list(dict1), weights=weights, k=1)[0]
        while y in visited:
            y = random.choices(list(dict1), weights=weights, k=1)[0]
        visited.add(y)

        z = random.choices([2, 3, 4, 5], weights=[0.6, 0.2, 0.2, 0.1], k=1)[0]  # rarity
        affixes = response[str(z)]["affixes"]

        for i in affixes.values():
            if i["property"] == y:
                if dict1[y][-1] == "%":
                    value = (i["base"] + i["step"] * 2) * 100
                else:
                    value = i["base"] + i["step"]
                values[y] = [value, z, i] 
                substats.append(y)# value + rarity + affix data
                break

    return substats, values

current_values = {}

def init_values(substats, values):
    """Initialize global current_values with base values"""
    global current_values
    current_values = {sub: values[sub][0] for sub in substats}

def build_embed(substats, values, enhancement_level):
    global current_values

    # only upgrade one random substat
    if enhancement_level>0:
        chosen = random.choice(substats)
        base, _, data = values[chosen]
        step = data["step"]
    
        prev = current_values[chosen]
        new = prev + step+base
        current_values[chosen] = new

    embed = discord.Embed(
        title=f"Relic Stats (+{enhancement_level})",
        color=discord.Color.blurple(),
    )

    # add fields
    for sub in substats:
        val = current_values[sub]
        if "%" in dict1[sub]:
            embed.add_field(
                name=dict1[sub],
                value=f"{val:.1f}%",
                inline=False,
            )
        else:
            embed.add_field(
                name=dict1[sub],
                value=f"{val:.0f}",
                inline=False,
            )

    # show which one got upgraded
    if enhancement_level>0:
        embed.set_footer(text=f"Upgraded: {dict1[chosen]}")
    return embed


class RelicView(discord.ui.View):
    def __init__(self, substats, values):
        super().__init__(timeout=60)
        self.substats = substats
        self.values = values
        self.levels = [0, 3, 6, 9, 12, 15]
        self.index = 0  # start at +0

    @discord.ui.button(label="Next", style=discord.ButtonStyle.green)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # move forward
        self.index += 1

        # stop if past last index
        if self.index >= len(self.levels):
            await interaction.response.send_message("No more upgrades!", ephemeral=True)
            self.stop()
            return

        # build new embed for the next level
        embed = build_embed(self.substats, self.values, self.levels[self.index])
        await interaction.response.edit_message(embed=embed, view=self)

@bot.command()
async def relic(ctx):
    substats, values = roll_relic()
 
    init_values(substats, values)  
    embed = build_embed(substats, values, 0)
    
    await ctx.send(embed=embed, view=RelicView(substats, values))

# ------------------------
# Character Fetch System
# ------------------------
def fetch_char(name: str) -> discord.Embed | None:
    name = name.lower()
    response = requests.get(BASE)
    response1 = requests.get(f"{API_URL}/{name}").json()

    if response.status_code == 200:
        response2 = response.json()
    else:
        return None

    if response1 and len(response1) >= 1:
        intro = response1[0].get("introduction", "No introduction found.")

        for i in response2.values():
            if i.get("name", "").lower() == name or i.get("tag", "").lower() == name:
                embed = discord.Embed(
                    title=i.get("name"),
                    description=(
                        f"**Rarity:** {i.get('rarity')}\n"
                        f"**Path:** {i.get('path')}\n"
                        f"**Element:** {i.get('element')}\n"
                        f"**Introduction:** {intro}\n"
                    ),
                    color=discord.Color.red(),
                )
                embed.set_image(url=f"{ICON}/{i.get('icon')}")
                embed.set_thumbnail(url=f"{ICON}/{i.get('preview')}")
                return embed

    return None


# ------------------------
# Commands
# ------------------------
@bot.command()
async def ping(ctx):
    await ctx.send("pong")


@bot.command()
async def character(ctx, name: str):
    embed = fetch_char(name)
    if embed:
        await ctx.send(embed=embed)
    else:
        await ctx.send("Character not found")


@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

keep_alive()  
bot.run(TOKEN)
