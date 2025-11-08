import os
import discord
from discord.ext import commands
from discord import app_commands
import requests

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0"))
CHANNEL_ID_ALERTES = int(os.getenv("CHANNEL_ID_ALERTES", "0"))

intents = discord.Intents.default()
client = commands.Bot(command_prefix="!", intents=intents)

# ----------------------------
#   FONCTION : prix du BTC
# ----------------------------
def get_btc_price():
    try:
        data = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd").json()
        return data["bitcoin"]["usd"]
    except:
        return None

# ----------------------------
# EVENT : Bot prêt
# ----------------------------
@client.event
async def on_ready():
    guild = discord.Object(id=GUILD_ID)
    try:
        client.tree.copy_global_to(guild=guild)
        await client.tree.sync(guild=guild)
        print(f"✅ Commandes synchronisées sur le serveur {GUILD_ID}")
    except Exception as e:
        print(f"Erreur sync: {e}")

    print(f"✅ Bot connecté comme : {client.user}")

# ----------------------------
# SLASH COMMAND : /btc
# ----------------------------
@client.tree.command(name="btc", description="Affiche le prix actuel du Bitcoin")
async def btc_cmd(interaction: discord.Interaction):
    price = get_btc_price()
    if price is None:
        await interaction.response.send_message("Impossible de récupérer le prix du BTC.")
    else:
        await interaction.response.send_message(f"💰 **Bitcoin : {price} USD**")

# ----------------------------
# SLASH COMMAND : /analyse
# ----------------------------
@client.tree.command(name="analyse", description="Donne une analyse basique du BTC")
async def analyse_cmd(interaction: discord.Interaction):
    price = get_btc_price()
    if price is None:
        await interaction.response.send_message("Erreur : prix indisponible.")
        return

    tendance = "📈 Hausse probable" if price > 60000 else "📉 Consolidation"
    await interaction.response.send_message(f"Analyse BTC :\n\nPrix : {price}$\nTendance : {tendance}")

# ----------------------------
# SLASH COMMAND : /prediction
# ----------------------------
@client.tree.command(name="prediction", description="Donne une prédiction fictive")
async def prediction_cmd(interaction: discord.Interaction):
    price = get_btc_price()
    if price:
        pred = round(price * 1.05)
        await interaction.response.send_message(f"🔮 Prédiction : **{pred}$** dans quelques jours… (fictif)")
    else:
        await interaction.response.send_message("Erreur de récupération du prix.")

# ----------------------------
# SLASH COMMAND : /signal
# ----------------------------
@client.tree.command(name="signal", description="Signal d'achat/vente simple")
async def signal_cmd(interaction: discord.Interaction):
    price = get_btc_price()
    if price is None:
        await interaction.response.send_message("Erreur de récupération du prix.")
        return

    signal = "✅ Achat" if price < 60000 else "⚠️ Attendre / Vente"
    await interaction.response.send_message(f"Signal : **{signal}**\nPrix actuel : {price}$")

# ----------------------------
# LANCEMENT
# ----------------------------
client.run(DISCORD_TOKEN)
