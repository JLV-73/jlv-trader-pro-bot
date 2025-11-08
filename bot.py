import os
import logging
import discord
from discord.ext import commands
from discord import app_commands
import requests

# ---------- LOGS ----------
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("jlv-bot")

# ---------- ENV ----------
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID_ENV = os.getenv("GUILD_ID", "0").strip()
GUILD_ID = int(GUILD_ID_ENV) if GUILD_ID_ENV.isdigit() else 0

# ---------- DISCORD ----------
intents = discord.Intents.default()
client = commands.Bot(command_prefix="!", intents=intents)

# ---------- DATA ----------
def get_btc_price():
    try:
        resp = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "bitcoin", "vs_currencies": "usd"},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()["bitcoin"]["usd"]
    except Exception as e:
        log.error(f"Erreur prix BTC: {e}")
        return None

# --------- COMMANDES ----------
@client.tree.command(name="ping", description="Test simple de disponibilité")
async def ping_cmd(interaction: discord.Interaction):
    await interaction.response.send_message("Pong ✅ (bot en ligne)")

@client.tree.command(name="btc", description="Prix actuel du Bitcoin (USD)")
async def btc_cmd(interaction: discord.Interaction):
    price = get_btc_price()
    if price is None:
        await interaction.response.send_message("Impossible de récupérer le prix du BTC pour le moment.")
    else:
        await interaction.response.send_message(f"💰 **BTC : {price:,} USD**".replace(",", " "))

@client.tree.command(name="analyse", description="Analyse BTC très simple")
async def analyse_cmd(interaction: discord.Interaction):
    price = get_btc_price()
    if price is None:
        await interaction.response.send_message("Erreur : prix indisponible.")
        return
    tendance = "📈 Plutôt haussier" if price > 60000 else "📉 Plutôt neutre/baisse"
    await interaction.response.send_message(f"Analyse BTC\n• Prix : {price}$\n• Tendance : {tendance}")

@client.tree.command(name="prediction", description="Projection fictive courte")
async def prediction_cmd(interaction: discord.Interaction):
    price = get_btc_price()
    if price is None:
        await interaction.response.send_message("Erreur : prix indisponible.")
        return
    pred = round(price * 1.05)
    await interaction.response.send_message(f"🔮 Projection (fictive) : **{pred}$**")

@client.tree.command(name="signal", description="Signal pédagogique (achat/attente)")
async def signal_cmd(interaction: discord.Interaction):
    price = get_btc_price()
    if price is None:
        await interaction.response.send_message("Erreur : prix indisponible.")
        return
    signal = "✅ Achat DCA" if price < 60000 else "⏸️ Attente / prise partielle"
    await interaction.response.send_message(f"Signal : **{signal}** | Prix : {price}$\n*Pédagogique, pas un conseil financier.*")

# --------- SYNC ----------
@client.event
async def on_ready():
    log.info(f"Connecté comme {client.user} (id={client.user.id})")
    try:
        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)
            client.tree.copy_global_to(guild=guild)
            cmds = await client.tree.sync(guild=guild)
            log.info(f"Slash commands synchronisées sur le serveur {GUILD_ID} ({len(cmds)} cmd).")
        else:
            cmds = await client.tree.sync()
            log.info(f"Slash commands synchronisées en GLOBAL ({len(cmds)} cmd).")
    except Exception as e:
        log.error(f"Sync guild échouée ({GUILD_ID}). Fallback global. Raison: {e}")
        cmds = await client.tree.sync()
        log.info(f"Slash commands synchronisées en GLOBAL ({len(cmds)} cmd).")

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        raise SystemExit("DISCORD_TOKEN manquant.")
    client.run(DISCORD_TOKEN)
