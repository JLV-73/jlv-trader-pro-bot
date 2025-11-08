import os, math, json, asyncio, aiohttp, statistics
from dotenv import load_dotenv

import discord
from discord import app_commands
from discord.ext import tasks

# ---------- ENV ----------
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0")) or None
CHANNEL_ID_ALERTES = int(os.getenv("CHANNEL_ID_ALERTES", "0")) or None

COINGECKO = "https://api.coingecko.com/api/v3"

# ---------- HTTP ----------
async def get_json(session, url, params=None, tries=3):
    for _ in range(tries):
        try:
            async with session.get(url, params=params, timeout=15) as r:
                if r.status == 200:
                    return await r.json()
        except Exception:
            await asyncio.sleep(0.6)
    raise RuntimeError("API error")

async def get_spot(session):
    url = f"{COINGECKO}/simple/price"
    params = {"ids": "bitcoin", "vs_currencies": "usd,eur", "include_24hr_change": "true"}
    d = await get_json(session, url, params)
    b = d["bitcoin"]
    return {"usd": b["usd"], "eur": b["eur"], "chg24": b.get("usd_24h_change", 0.0)}

async def get_prices(session, days=7, interval="hourly"):
    url = f"{COINGECKO}/coins/bitcoin/market_chart"
    params = {"vs_currency": "usd", "days": str(days), "interval": interval}
    d = await get_json(session, url, params)
    return [p[1] for p in d.get("prices", [])]

# ---------- TA LÉGÈRE ----------
def sma(series, n):
    if len(series) < n: return None
    return sum(series[-n:]) / n

def ema(series, n):
    if len(series) < n: return None
    k = 2/(n+1)
    e = series[0]
    for x in series[1:]:
        e = x*k + e*(1-k)
    return e

def rsi(series, period=14):
    if len(series) < period+1: return None
    gains, losses = [], []
    for i in range(-period, 0):
        diff = series[i] - series[i-1]
        if diff >= 0: gains.append(diff)
        else: losses.append(-diff)
    avg_gain = (sum(gains)/period) if gains else 1e-7
    avg_loss = (sum(losses)/period) if losses else 1e-7
    rs = avg_gain/avg_loss
    return 100 - (100/(1+rs))

def macd(series, fast=12, slow=26, signal=9):
    if len(series) < slow+signal: return None, None, None
    def ema_full(vals, n):
        k = 2/(n+1)
        e = vals[0]; out = [e]
        for x in vals[1:]:
            e = x*k + e*(1-k); out.append(e)
        return out
    macd_line = [a-b for a,b in zip(ema_full(series, fast), ema_full(series, slow))]
    sig_line = ema_full(macd_line, signal)
    hist = [m-s for m,s in zip(macd_line, sig_line)]
    return macd_line[-1], sig_line[-1], hist[-1]

def percentile(series, q):
    s = sorted(series); idx = int((len(s)-1)*q)
    return s[idx]

def build_analysis(prices):
    price = prices[-1]
    sma20 = sma(prices, 20); sma50 = sma(prices, 50); ema21v = ema(prices, 21)
    rsi14 = rsi(prices, 14)
    macd_v, macd_sig, macd_hist = macd(prices)
    support = percentile(prices, 0.10); resistance = percentile(prices, 0.90)
    dist_sup = (price - support)/support*100 if support else 0
    dist_res = (resistance - price)/price*100 if resistance else 0

    signals = []
    if rsi14 is not None:
        if rsi14 >= 70: signals.append(("surachat_RSI", -1))
        elif rsi14 <= 30: signals.append(("survente_RSI", 1))
        else: signals.append(("RSI_neutre", 0))
    if macd_v is not None and macd_sig is not None:
        signals.append(("MACD_au-dessus" if macd_v > macd_sig else "MACD_en-dessous",
                        1 if macd_v > macd_sig else -1))
    if sma20 and sma50:
        if price > sma20 > sma50: signals.append(("tendance_haussière", 1))
        elif price < sma20 < sma50: signals.append(("tendance_baissière", -1))

    score = sum(s for _, s in signals) if signals else 0
    advice = "ATTENTE"
    if score >= 2: advice = "ACHAT PARTIEL"
    if score <= -2: advice = "PRISE DE PROFIT / VENTE PARTIELLE"
    confidence = max(5, min(95, 50 + 15*score))

    return {
        "price": price, "sma20": sma20, "sma50": sma50, "ema21": ema21v,
        "rsi14": rsi14, "macd": macd_v, "macd_sig": macd_sig, "macd_hist": macd_hist,
        "support": support, "resistance": resistance,
        "dist_sup": dist_sup, "dist_res": dist_res,
        "signals": [n for n,_ in signals], "score": score,
        "advice": advice, "confidence": confidence
    }

def simple_projection(prices, hours=24):
    if len(prices) < 26: return None
    p_now = prices[-1]; p_24h = prices[-25]
    drift_per_h = (p_now - p_24h)/24.0
    target = p_now + drift_per_h*hours
    rets = [(prices[i+1]-prices[i])/prices[i] for i in range(-25, -1)]
    vol = statistics.pstdev(rets) if rets else 0.0
    band = p_now * vol * math.sqrt(hours/24) * 1.5
    return {"target": target, "lo": target - band, "hi": target + band}

# ---------- DISCORD ----------
class Client(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.http_session = None

    async def setup_hook(self):
        self.http_session = aiohttp.ClientSession()
        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()
        watcher.start(self)

    async def close(self):
        if self.http_session: await self.http_session.close()
        await super().close()

client = Client()

@client.tree.command(name="btc", description="Prix BTC spot")
async def btc_cmd(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    spot = await get_spot(client.http_session)
    msg = (f"**BTC**  USD **${spot['usd']:,.0f}** | EUR **{spot['eur']:,.0f} €**\n"
           f"24h: {spot['chg24']:+.2f}%\n"
           f"_Analyse éducative, pas un conseil financier._")
    await interaction.followup.send(msg)

@client.tree.command(name="analyse", description="Analyse technique BTC")
async def analyse_cmd(interaction: discord.Interaction, days: app_commands.Range[int,1,30]=7):
    await interaction.response.defer(thinking=True)
    prices = await get_prices(client.http_session, days=days, interval="hourly")
    a = build_analysis(prices)
    msg = (
        f"**Analyse BTC ({days}j)**\n"
        f"Prix: **${a['price']:,.0f}** | RSI14: {a['rsi14'] and round(a['rsi14'],1)} | "
        f"MACD: {a['macd'] and round(a['macd'],2)}/{a['macd_sig'] and round(a['macd_sig'],2)}\n"
        f"SMA20: {a['sma20'] and round(a['sma20'])} | SMA50: {a['sma50'] and round(a['sma50'])} | "
        f"EMA21: {a['ema21'] and round(a['ema21'])}\n"
        f"Support≈ ${a['support'] and round(a['support'])} ({a['dist_sup']:+.2f}%) | "
        f"Résistance≈ ${a['resistance'] and round(a['resistance'])} ({a['dist_res']:+.2f}%)\n"
        f"Signaux: {', '.join(a['signals'])}\n"
        f"🧭 **Signal**: **{a['advice']}** | Confiance: **{a['confidence']}%**\n"
        f"_Ne remplace pas une stratégie perso ni la gestion du risque._"
    )
    await interaction.followup.send(msg)

@bot.tree.command(name="prediction", description="Analyse BTC")
async def prediction_cmd(interaction: discord.Interaction):
    await interaction.response.send_message("Analyse en cours…")

