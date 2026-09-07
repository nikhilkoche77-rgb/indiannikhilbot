import os
import json
import time
import threading
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import requests
import yfinance as yf

# --- BOT CONFIGURATION ---
TELEGRAM_TOKEN = "8876905313:AAHWQ8cD9jADvepC4lQE1psRH9WOxxL21qA"
CHAT_ID = "1345385952"
DATA_FILE = "trades_data.json"
LAST_UPDATE_ID = 0
BOT_PAUSED = False

# Strict Timezone setup for Indian Market
IST = ZoneInfo("Asia/Kolkata")

def send_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        res = requests.post(url, data=payload, timeout=10)
        return res.json()
    except Exception as e:
        print(f"Telegram API error: {e}")
        return None

# --- MARKET TIMING GATES ---
def is_indian_market_open():
    now = datetime.now(IST)
    # Monday = 0, Friday = 4, Saturday = 5, Sunday = 6
    if now.weekday() >= 5:
        return False
    market_start = now.replace(hour=9, minute=15, second=0, microsecond=0)
    market_end = now.replace(hour=15, minute=25, second=0, microsecond=0)
    return market_start <= now <= market_end

def is_forex_market_open():
    now_utc = datetime.now(timezone.utc)
    weekday = now_utc.weekday()
    # Forex closes Friday 21:00 UTC and opens Sunday 21:00 UTC
    if weekday == 5: # Saturday
        return False
    if weekday == 4 and now_utc.hour >= 21: # Friday evening
        return False
    if weekday == 6 and now_utc.hour < 21: # Sunday before open
        return False
    return True

# --- DUAL-WALLET STATE LOADER ---
def load_data():
    default_data = {
        "virtual_balance_inr": 10000.00,
        "virtual_balance_usd": 100.00,
        "initial_capital_inr": 10000.00,
        "initial_capital_usd": 100.00,
        "open_positions": {},
        "trade_history": []
    }

    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                saved = json.load(f)
                saved["virtual_balance_usd"] = saved.get("virtual_balance_usd", 100.00)
                if "virtual_balance_inr" not in saved:
                    saved["virtual_balance_inr"] = saved.get("virtual_balance", 10000.00)
                return saved
        except Exception:
            pass
    return default_data

def save_data(data):
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"File save error: {e}")

trade_state = load_data()

SCALP_CRYPTO = ["BTC-USD", "ETH-USD"]
SCALP_METALS = ["GC=F"] # XAUUSD
FOREX_STANDARD = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X"]

WATCHLIST_STOCKS = [
    "TATASTEEL.NS", "BEL.NS", "BHEL.NS", "SAIL.NS", "NATIONALUM.NS", "NMDC.NS",
    "PFC.NS", "RECLTD.NS", "COALINDIA.NS", "HINDALCO.NS", "VEDL.NS", "ONGC.NS",
    "IRFC.NS", "RVNL.NS", "SUZLON.NS", "ZOMATO.NS", "PAYTM.NS", "IDEA.NS",
    "YESBANK.NS", "PNB.NS", "BANKBARODA.NS", "CANBK.NS", "UNIONBANK.NS", "IDFCFIRSTB.NS",
    "ASHOKLEY.NS", "GMRINFRA.NS", "ABCAPITAL.NS", "MANAPPURAM.NS", "FEDERALBNK.NS",
    "IOC.NS", "BPCL.NS", "POWERGRID.NS", "NTPC.NS", "RPOWER.NS", "JPPOWER.NS",
    "IFCI.NS", "IREDA.NS", "HUDCO.NS", "NBCC.NS", "RAILTEL.NS", "IRCON.NS",
    "SJVN.NS", "NHPC.NS", "MAZDOCK.NS", "COCHINSHIP.NS", "HAL.NS", "BDL.NS",
    "PATANJALI.NS", "EXIDEIND.NS", "AMARAJABAT.NS", "MOTHERSON.NS", "TATACHEM.NS",
    "JINDALSTEL.NS", "JSWSTEEL.NS", "HCLTECH.NS", "WIPRO.NS", "INFY.NS",
    "BHARTIARTL.NS", "ADANIENT.NS", "ADANIPORTS.NS", "ADANIPOWER.NS", "ADANIGREEN.NS",
    "DLF.NS", "GODREJPROP.NS", "CHOLAFIN.NS", "POONAWALLA.NS", "L&TFH.NS",
    "MUTHOOTFIN.NS", "BANDHANBNK.NS", "UCOBANK.NS", "CENTRALBK.NS", "BANKINDIA.NS",
    "IOB.NS", "OIL.NS", "GAIL.NS", "DELHIVERY.NS", "NYKAA.NS", "POLICYBZR.NS",
    "JUBLFOOD.NS", "HAVELLS.NS", "TVSMOTOR.NS", "HEROMOTOCO.NS", "PARAS.NS",
    "MTARTECH.NS", "DATA-PATTERNS.NS", "KPIGREEN.NS", "BORORENEW.NS", "GMDCLTD.NS",
    "TATAINVEST.NS", "KALYANKJIL.NS", "HBLPOWER.NS", "ENGINERSIN.NS", "WAAREEENER.NS",
    "PREMIERENE.NS", "RITES.NS", "GRSE.NS", "BEML.NS", "ASTRAL.NS", "POLYCAB.NS",
    "KEI.NS", "DIXON.NS", "KAYNES.NS", "PERSISTENT.NS", "COFORGE.NS", "MPHASIS.NS",
    "TITAN.NS", "TRENT.NS", "DMART.NS", "APOLLOTYRE.NS", "MRF.NS", "BALKRISIND.NS",
    "ESCORTS.NS", "DEEPAKNTR.NS", "TATAELXSI.NS", "CLEAN.NS", "FINEORG.NS",
    "AETHER.NS", "SUVENPHAR.NS", "NATCOPHARM.NS", "GLENMARK.NS", "LUPIN.NS",
    "AUROPHARMA.NS", "PRESTIGE.NS", "OBEROIRLTY.NS", "PHOENIXLTD.NS", "SUNTECK.NS",
    "NCC.NS", "HFCL.NS", "TEJASNET.NS", "KEC.NS", "KALPATPOWR.NS", "CESC.NS",
    "TORNTPOWER.NS", "TATAPOWER.NS", "JSWENERGY.NS", "INOXWIND.NS", "TITAGARH.NS",
    "TEXRAIL.NS", "JWL.NS", "ZENITHEXPO.NS", "ASTERDM.NS", "APLAPOLLO.NS",
    "CGPOWER.NS", "SUNDRMFAST.NS", "SCHNEIDER.NS", "TRITURBINE.NS", "THERMAX.NS",
    "PRAJIND.NS", "ELECON.NS", "KIRLOSENG.NS", "CUMMINSIND.NS", "MAHINDCIE.NS",
    "SONACOMS.NS", "UNOMINDA.NS", "SUPRAJIT.NS", "RADICO.NS", "TIINDIA.NS",
    "JBCHEPHARM.NS", "ERIS.NS", "AJANTPHARM.NS", "SYNGENE.NS", "CHAMBLFERT.NS",
    "COROMANDEL.NS", "GNFC.NS", "GSFC.NS", "FACT.NS"
]

def is_forex_or_crypto(symbol):
    return symbol.endswith("=X") or symbol.endswith("-USD") or symbol == "GC=F"

def format_clean_symbol(symbol):
    if symbol == "GC=F":
        return "XAUUSD (Gold)"
    elif symbol.endswith("=X"):
        return symbol.replace("=X", "")
    elif symbol.endswith("-USD"):
        return symbol
    return symbol.replace(".NS", "")

def send_menu(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "📊 Live Terminal", "callback_data": "btn_terminal"},
                {"text": "💰 Wallets (INR/$100)", "callback_data": "btn_wallets"}
            ],
            [
                {"text": "🔄 Refresh / Sync", "callback_data": "btn_sync"},
                {"text": "📋 Today Breakdown", "callback_data": "btn_breakdown"}
            ],
            [
                {"text": "📈 Performance", "callback_data": "btn_performance"},
                {"text": "⏸️ Pause", "callback_data": "btn_pause"},
                {"text": "▶️ Resume", "callback_data": "btn_resume"}
            ],
            [
                {"text": "🚨 Panic Exit (Close All)", "callback_data": "btn_panic"}
            ]
        ]
    }
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "reply_markup": json.dumps(keyboard)
    }
    try:
        requests.post(url, data=payload, timeout=5)
    except Exception as e:
        print(f"Telegram error: {e}")

def handle_callback(query_id, data):
    global trade_state, BOT_PAUSED
    requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery", data={"callback_query_id": query_id})

    if data == "btn_terminal":
        positions = trade_state.get("open_positions", {})
        inr_positions = {k: v for k, v in positions.items() if not is_forex_or_crypto(k)}
        fx_positions = {k: v for k, v in positions.items() if is_forex_or_crypto(k)}

        msg = "📊 *MULTI-ASSET LIVE TERMINAL*\n━━━━━━━━━━━━━━━━━━━━\n"
        msg += f"🇮🇳 *INDIAN EQUITIES [{len(inr_positions)} Active]*\n"
        if inr_positions:
            for sym, d in inr_positions.items():
                level = d.get('trailed_level', 0)
                trail_tag = "🛡️ Trailed Cost" if level == 1 else "Initial SL"
                clean = format_clean_symbol(sym)
                msg += f"• *{clean}* ({d['style']})\n  Qty: `{d['qty']}` | Entry: `₹{d['entry']:.2f}`\n  SL: `₹{d['sl']:.2f}` ({trail_tag}) | Tgt: `₹{d['target']:.2f}`\n\n"
        else:
            status = "Open" if is_indian_market_open() else "Closed"
            msg += f"_(Market {status} - No active positions)_\n\n"

        msg += "━━━━━━━━━━━━━━━━━━━━\n"
        msg += f"🌐 *FOREX / VANTAGE / XM [{len(fx_positions)} Active]*\n"
        if fx_positions:
            for sym, d in fx_positions.items():
                level = d.get('trailed_level', 0)
                trail_tag = "🛡️ Breakeven" if level == 1 else "Initial SL"
                clean = format_clean_symbol(sym)
                msg += f"• *{clean}* ({d['style']})\n  Lot: `{d['qty']}` | Entry: `${d['entry']:.4f}`\n  SL: `${d['sl']:.4f}` ({trail_tag}) | TP: `${d['target']:.4f}`\n\n"
        else:
            msg += "_(No active Forex/Crypto positions)_\n"

        send_menu(msg)

    elif data == "btn_wallets":
        inr_cash = trade_state['virtual_balance_inr']
        usd_cash = trade_state['virtual_balance_usd']
        inr_alloc = sum([d['entry'] * d['qty'] for sym, d in trade_state.get('open_positions', {}).items() if not is_forex_or_crypto(sym)])
        usd_alloc = sum([20.0 for sym in trade_state.get('open_positions', {}) if is_forex_or_crypto(sym)])

        send_menu(
            f"💰 *SEPARATED WALLET AUDIT*\n━━━━━━━━━━━━━━━━━━━━\n"
            f"🇮🇳 *INDIAN EQUITIES DEMO POOL:*\n"
            f"• Available Cash: ₹{inr_cash:.2f}\n"
            f"• Allocated Margin: ₹{inr_alloc:.2f}\n"
            f"• Total Portfolio: ₹{(inr_cash + inr_alloc):.2f}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🌐 *FOREX / VANTAGE / XM DEMO ($100):*\n"
            f"• Available Cash: ${usd_cash:.2f} USD\n"
            f"• Active Margin: ${usd_alloc:.2f} USD\n"
            f"• Total Equity: ${(usd_cash + usd_alloc):.2f} USD"
        )

    elif data == "btn_performance":
        history = trade_state.get("trade_history", [])
        inr_history = [t for t in history if t.get("currency") == "INR"]
        usd_history = [t for t in history if t.get("currency") == "USD"]

        inr_wins = [t for t in inr_history if t.get("pnl", 0) > 0]
        inr_loss = [t for t in inr_history if t.get("pnl", 0) <= 0]
        inr_rate = (len(inr_wins) / len(inr_history) * 100) if inr_history else 0.0
        inr_pnl = sum([t.get("pnl", 0) for t in inr_history])

        usd_wins = [t for t in usd_history if t.get("pnl", 0) > 0]
        usd_loss = [t for t in usd_history if t.get("pnl", 0) <= 0]
        usd_rate = (len(usd_wins) / len(usd_history) * 100) if usd_history else 0.0
        usd_pnl = sum([t.get("pnl", 0) for t in usd_history])

        send_menu(
            f"📈 *TOTAL PORTFOLIO PERFORMANCE*\n━━━━━━━━━━━━━━━━━━━━\n"
            f"🇮🇳 *INDIAN EQUITIES (₹10,000 Pool):*\n"
            f"• Total Trades: `{len(inr_history)}` (✅ {len(inr_wins)}W | ❌ {len(inr_loss)}L)\n"
            f"• Win Rate: *{inr_rate:.1f}%*\n"
            f"• Realized P&L: *{'+' if inr_pnl >= 0 else ''}₹{inr_pnl:.2f}*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🌐 *FOREX / CRYPTO (VANTAGE/XM $100 Pool):*\n"
            f"• Total Trades: `{len(usd_history)}` (✅ {len(usd_wins)}W | ❌ {len(usd_loss)}L)\n"
            f"• Win Rate: *{usd_rate:.1f}%*\n"
            f"• Realized P&L: *{'+' if usd_pnl >= 0 else ''}${usd_pnl:.2f} USD*"
        )

    elif data == "btn_sync":
        send_alert("🔄 *Syncing Markets Live...*")
        threading.Thread(target=scan_market).start()

    elif data == "btn_breakdown":
        today_str = datetime.now(IST).strftime("%Y-%m-%d")
        today_trades = [t for t in trade_state.get("trade_history", []) if t.get("date") == today_str]
        today_inr = [t for t in today_trades if t.get("currency") == "INR"]
        today_usd = [t for t in today_trades if t.get("currency") == "USD"]

        inr_pnl = sum([t.get("pnl", 0) for t in today_inr])
        inr_wins = len([t for t in today_inr if t.get("pnl", 0) > 0])
        inr_loss = len([t for t in today_inr if t.get("pnl", 0) <= 0])

        usd_pnl = sum([t.get("pnl", 0) for t in today_usd])
        usd_wins = len([t for t in today_usd if t.get("pnl", 0) > 0])
        usd_loss = len([t for t in today_usd if t.get("pnl", 0) <= 0])

        send_menu(
            f"📋 *TODAY'S BREAKDOWN ({today_str})*\n━━━━━━━━━━━━━━━━━━━━\n"
            f"🇮🇳 *INDIAN EQUITIES TODAY:*\n"
            f"• Closed Trades: `{len(today_inr)}` (✅ {inr_wins}W | ❌ {inr_loss}L)\n"
            f"• Realized P&L: *{'+' if inr_pnl >= 0 else ''}₹{inr_pnl:.2f}*\n"
            f"• Cash Balance: `₹{trade_state['virtual_balance_inr']:.2f}`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🌐 *FOREX / CRYPTO TODAY ($100 Pool):*\n"
            f"• Closed Trades: `{len(today_usd)}` (✅ {usd_wins}W | ❌ {usd_loss}L)\n"
            f"• Realized P&L: *{'+' if usd_pnl >= 0 else ''}${usd_pnl:.2f} USD*\n"
            f"• USD Balance: `${trade_state['virtual_balance_usd']:.2f} USD`"
        )

    elif data == "btn_pause":
        BOT_PAUSED = True
        send_menu("⏸️ *SCANNER PAUSED*")

    elif data == "btn_resume":
        BOT_PAUSED = False
        send_menu("▶️ *SCANNER RESUMED*")

    elif data == "btn_panic":
        positions = list(trade_state.get("open_positions", {}).items())
        if not positions:
            send_menu("🚨 *PANIC EXIT*\nKoi open position nahi mili.")
            return

        today_str = datetime.now(IST).strftime("%Y-%m-%d")
        for sym, d in positions:
            curr = d.get("currency", "INR")
            if curr == "USD":
                trade_state["virtual_balance_usd"] += 20.0
            else:
                trade_state["virtual_balance_inr"] += (d["entry"] * d["qty"])

            trade_state["trade_history"].append({
                "symbol": sym, "type": d["type"], "entry": d["entry"], "exit": d["entry"],
                "pnl": 0.0, "result": "PANIC_CLOSE", "style": d["style"], "date": today_str, "currency": curr
            })
            del trade_state["open_positions"][sym]
        save_data(trade_state)
        send_menu("🚨 *PANIC EXIT COMPLETE!*\nSaari positions square-off kar di gayi hain.")

def fast_telegram_listener():
    global LAST_UPDATE_ID
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={LAST_UPDATE_ID + 1}&timeout=1"
            res = requests.get(url, timeout=3).json()
            for update in res.get("result", []):
                LAST_UPDATE_ID = update["update_id"]
                if "callback_query" in update:
                    q_id = update["callback_query"]["id"]
                    data = update["callback_query"]["data"]
                    handle_callback(q_id, data)
                elif "message" in update:
                    send_menu("🎛️ *COMMAND TERMINAL ACTIVE*\nButtons se direct operate karein:")
        except Exception as e:
            print(f"Listener warning: {e}")
        time.sleep(0.5)

def manage_open_positions():
    global trade_state
    closed = []
    positions = trade_state.get("open_positions", {})
    today_str = datetime.now(IST).strftime("%Y-%m-%d")

    for symbol, pos in list(positions.items()):
        try:
            is_fx = is_forex_or_crypto(symbol)
            # Agar Indian market band hai toh Indian running positions ko skip karein
            if not is_fx and not is_indian_market_open():
                continue
            if symbol in FOREX_STANDARD + SCALP_METALS and not is_forex_market_open():
                continue

            interval = "5m" if symbol in (SCALP_CRYPTO + SCALP_METALS) else "15m"
            df = yf.download(tickers=symbol, period="1d", interval=interval, progress=False)
            if df is None or df.empty:
                continue
            if hasattr(df.columns, 'levels'):
                df.columns = [col[0] for col in df.columns]

            curr_price = float(df['Close'].iloc[-1])
            entry = pos['entry']
            qty = pos['qty']
            gain_pct = ((curr_price - entry) / entry) * 100
            current_level = pos.get('trailed_level', 0)
            clean_name = format_clean_symbol(symbol)
            curr = pos.get("currency", "USD" if is_fx else "INR")

            trail_point = 0.25 if symbol in (SCALP_CRYPTO + SCALP_METALS) else (0.60 if is_fx else 1.20)

            if pos['type'] == "BUY":
                if current_level < 1 and gain_pct >= trail_point:
                    pos['sl'] = round(entry, 4 if is_fx else 2)
                    pos['trailed_level'] = 1
                    save_data(trade_state)
                    tag = "⚡ *[5M SCALP TRAIL]*" if symbol in (SCALP_CRYPTO + SCALP_METALS) else "🛡️ *[TRAILING ACTIVE]*"
                    send_alert(f"{tag}: `{clean_name}`\nGain: +{gain_pct:.2f}%\nSL locked to Entry Cost!")

                if curr_price >= pos['target']:
                    profit = round((curr_price - entry) * qty, 2)
                    if curr == "USD":
                        trade_state["virtual_balance_usd"] += (20.0 + profit)
                        send_alert(f"🎯 *TARGET HIT: TAKE PROFIT*\n━━━━━━━━━━━━━━━━━━━━\n🌐 `{clean_name}` | Exit: `${curr_price:.4f}`\n💰 Profit: `+${profit:.2f} USD`\n💼 USD Balance: `${trade_state['virtual_balance_usd']:.2f} USD`")
                    else:
                        trade_state["virtual_balance_inr"] += (curr_price * qty)
                        send_alert(f"🎯 *TARGET HIT!*\n━━━━━━━━━━━━━━━━━━━━\n🇮🇳 `{clean_name}` | Exit: ₹{curr_price:.2f}\n💰 Profit: +₹{profit:.2f}\n💼 INR Balance: ₹{trade_state['virtual_balance_inr']:.2f}")
                    
                    trade_state["trade_history"].append({"symbol": symbol, "type": "BUY", "entry": entry, "exit": curr_price, "pnl": profit, "result": "WIN", "style": pos["style"], "date": today_str, "currency": curr})
                    closed.append(symbol)

                elif curr_price <= pos['sl']:
                    pnl = round((curr_price - entry) * qty, 2)
                    outcome = "WIN" if pnl >= 0 else "LOSS"
                    if curr == "USD":
                        trade_state["virtual_balance_usd"] += (20.0 + pnl)
                        title = "🛡️ *TRAILING SL HIT*" if pnl >= 0 else "🛑 *STOP LOSS HIT*"
                        send_alert(f"{title}\n━━━━━━━━━━━━━━━━━━━━\n🌐 `{clean_name}` | Exit: `${curr_price:.4f}`\n💰 P&L: `{'+' if pnl >= 0 else ''}${pnl:.2f} USD`\n💼 USD Balance: `${trade_state['virtual_balance_usd']:.2f} USD`")
                    else:
                        trade_state["virtual_balance_inr"] += (curr_price * qty)
                        title = "🛡️ *TRAILING SL HIT*" if pnl >= 0 else "🛑 *STOP LOSS HIT*"
                        send_alert(f"{title}\n━━━━━━━━━━━━━━━━━━━━\n🇮🇳 `{clean_name}` | Exit: ₹{curr_price:.2f}\n💰 P&L: {'+' if pnl >= 0 else ''}₹{pnl:.2f}\n💼 INR Balance: ₹{trade_state['virtual_balance_inr']:.2f}")

                    trade_state["trade_history"].append({"symbol": symbol, "type": "BUY", "entry": entry, "exit": curr_price, "pnl": pnl, "result": outcome, "style": pos["style"], "date": today_str, "currency": curr})
                    closed.append(symbol)

        except Exception as e:
            print(f"Tracking error {symbol}: {e}")

    for sym in closed:
        del trade_state["open_positions"][sym]
    if closed:
        save_data(trade_state)

def scan_market():
    global trade_state, BOT_PAUSED
    if BOT_PAUSED:
        return

    manage_open_positions()

    # ==============================================================
    # ⚡ ENGINE 1: CRYPTO 24/7 (BTC & ETH 5M SCALPER)
    # ==============================================================
    if trade_state["virtual_balance_usd"] >= 20.0:
        for symbol in SCALP_CRYPTO:
            if symbol in trade_state.get("open_positions", {}):
                continue
            try:
                time.sleep(0.1)
                df = yf.download(tickers=symbol, period="1d", interval="5m", progress=False)
                if df is None or df.empty or len(df) < 25:
                    continue
                if hasattr(df.columns, 'levels'):
                    df.columns = [col[0] for col in df.columns]

                # Check freshness of candle
                last_time = df.index[-1].to_pydatetime().replace(tzinfo=timezone.utc)
                if (datetime.now(timezone.utc) - last_time).total_seconds() > 900:
                    continue

                df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
                df['Vol_Avg'] = df['Volume'].rolling(window=20).mean()
                df['High_10'] = df['High'].shift(1).rolling(window=10).max()

                curr_close = float(df['Close'].iloc[-1])
                ema20 = float(df['EMA20'].iloc[-1])
                curr_vol = float(df['Volume'].iloc[-1])
                avg_vol = float(df['Vol_Avg'].iloc[-1])
                high_10 = float(df['High_10'].iloc[-1])

                vol_ratio = curr_vol / avg_vol if avg_vol > 0 else 1.0

                if curr_close > ema20 and curr_close > high_10 and vol_ratio >= 2.5:
                    sl = round(curr_close * 0.9965, 4)
                    tgt = round(curr_close * 1.0070, 4)
                    trade_state["virtual_balance_usd"] -= 20.00

                    trade_state["open_positions"][symbol] = {
                        'type': 'BUY', 'entry': curr_close, 'qty': 0.01,
                        'sl': sl, 'target': tgt, 'style': "⚡ 5M SCALP", 'trailed_level': 0, 'currency': "USD"
                    }
                    save_data(trade_state)
                    clean_sym = format_clean_symbol(symbol)

                    send_alert(
                        f"⚡ *[VANTAGE / XM ALERT]: 5M CRYPTO SCALP*\n━━━━━━━━━━━━━━━━━━━━\n"
                        f"📊 *Asset:* `{clean_sym}` | `BUY MARKET`\n"
                        f"💵 *Entry:* `${curr_close:.4f}`\n"
                        f"🛑 *SL:* `${sl:.4f}` (-0.35%) | 🎯 *TP:* `${tgt:.4f}` (+0.70%)\n"
                        f"🔥 *Volume:* `{vol_ratio:.1f}x Spike` | *Lot:* `0.01 Lot`\n"
                        f"💼 *USD Cash Left:* `${trade_state['virtual_balance_usd']:.2f} USD`"
                    )
            except Exception as e:
                print(f"Crypto error {symbol}: {e}")

    # ==============================================================
    # 🌐 ENGINE 2: FOREX & GOLD (Active Only When Forex Market Open)
    # ==============================================================
    if is_forex_market_open() and trade_state["virtual_balance_usd"] >= 20.0:
        for symbol in SCALP_METALS + FOREX_STANDARD:
            if symbol in trade_state.get("open_positions", {}):
                continue
            try:
                time.sleep(0.1)
                is_metal = symbol in SCALP_METALS
                interval = "5m" if is_metal else "15m"
                df = yf.download(tickers=symbol, period="2d", interval=interval, progress=False)
                if df is None or df.empty or len(df) < 25:
                    continue
                if hasattr(df.columns, 'levels'):
                    df.columns = [col[0] for col in df.columns]

                last_time = df.index[-1].to_pydatetime().replace(tzinfo=timezone.utc)
                if (datetime.now(timezone.utc) - last_time).total_seconds() > 1200:
                    continue

                df['Vol_Avg'] = df['Volume'].rolling(window=20).mean()
                df['High_Lookback'] = df['High'].shift(1).rolling(window=10 if is_metal else 20).max()

                curr_close = float(df['Close'].iloc[-1])
                curr_vol = float(df['Volume'].iloc[-1])
                avg_vol = float(df['Vol_Avg'].iloc[-1])
                high_val = float(df['High_Lookback'].iloc[-1])
                vol_ratio = curr_vol / avg_vol if avg_vol > 0 else 1.0

                req_ratio = 2.5 if is_metal else 2.0
                if vol_ratio >= req_ratio and curr_close > high_val:
                    sl_pct = 0.0035 if is_metal else 0.0080
                    tgt_pct = 0.0070 if is_metal else 0.0180
                    style_name = "⚡ 5M SCALP" if is_metal else "🎯 FX INTRADAY"

                    sl = round(curr_close * (1 - sl_pct), 4)
                    tgt = round(curr_close * (1 + tgt_pct), 4)
                    trade_state["virtual_balance_usd"] -= 20.00

                    trade_state["open_positions"][symbol] = {
                        'type': 'BUY', 'entry': curr_close, 'qty': 0.01,
                        'sl': sl, 'target': tgt, 'style': style_name, 'trailed_level': 0, 'currency': "USD"
                    }
                    save_data(trade_state)
                    clean_sym = format_clean_symbol(symbol)

                    send_alert(
                        f"🌐 *[VANTAGE / XM ALERT]: {style_name}*\n━━━━━━━━━━━━━━━━━━━━\n"
                        f"📊 *Asset:* `{clean_sym}` | `BUY MARKET`\n"
                        f"💵 *Entry:* `${curr_close:.4f}`\n"
                        f"🛑 *SL:* `${sl:.4f}` | 🎯 *TP:* `${tgt:.4f}`\n"
                        f"🔥 *Volume:* `{vol_ratio:.1f}x Spike` | *Lot:* `0.01 Lot`\n"
                        f"💼 *USD Cash Left:* `${trade_state['virtual_balance_usd']:.2f} USD`"
                    )
            except Exception as e:
                print(f"FX/Metal error {symbol}: {e}")

    # ==============================================================
    # 🇮🇳 ENGINE 3: INDIAN EQUITIES (Active Only Monday-Friday 9:15-15:25 IST)
    # ==============================================================
    if is_indian_market_open() and trade_state["virtual_balance_inr"] >= 1000.0:
        for symbol in WATCHLIST_STOCKS:
            if symbol in trade_state.get("open_positions", {}):
                continue
            try:
                time.sleep(0.1)
                df = yf.download(tickers=symbol, period="5d", interval="15m", progress=False)
                if df is None or df.empty or len(df) < 25:
                    continue
                if hasattr(df.columns, 'levels'):
                    df.columns = [col[0] for col in df.columns]

                # Check candle freshness (must be within last 20 minutes)
                last_time = df.index[-1].to_pydatetime()
                if last_time.tzinfo is None:
                    last_time = last_time.replace(tzinfo=IST)
                else:
                    last_time = last_time.astimezone(IST)

                if (datetime.now(IST) - last_time).total_seconds() > 1500:
                    continue

                df['Vol_Avg'] = df['Volume'].rolling(window=20).mean()
                df['High_20'] = df['High'].shift(1).rolling(window=20).max()
                curr_close = float(df['Close'].iloc[-1])
                curr_vol = float(df['Volume'].iloc[-1])
                avg_vol = float(df['Vol_Avg'].iloc[-1])
                high_20 = float(df['High_20'].iloc[-1])
                vol_ratio = curr_vol / avg_vol if avg_vol > 0 else 1.0

                if vol_ratio >= 2.0 and curr_close > high_20:
                    trade_fund = min(2500.0, trade_state["virtual_balance_inr"])
                    qty = int(trade_fund // curr_close)
                    if qty < 1:
                        continue

                    sl = round(curr_close * 0.985, 2)
                    tgt = round(curr_close * 1.035, 2)
                    trade_state["virtual_balance_inr"] -= (curr_close * qty)

                    trade_state["open_positions"][symbol] = {
                        'type': 'BUY', 'entry': curr_close, 'qty': qty,
                        'sl': sl, 'target': tgt, 'style': "🎯 INTRADAY", 'trailed_level': 0, 'currency': "INR"
                    }
                    save_data(trade_state)
                    clean_sym = format_clean_symbol(symbol)

                    send_alert(
                        f"🇮🇳 *[INDIAN EQUITIES ALERT]: 🎯 INTRADAY*\n━━━━━━━━━━━━━━━━━━━━\n"
                        f"📈 *Stock:* `{clean_sym}` | `BUY`\n"
                        f"💵 *Entry:* `₹{curr_close:.2f}` | *Qty:* `{qty}`\n"
                        f"🛑 *SL:* `₹{sl}` | 🎯 *Target:* `₹{tgt}`\n"
                        f"🔥 *Volume:* `{vol_ratio:.1f}x Spike`\n"
                        f"💼 *INR Cash Left:* `₹{trade_state['virtual_balance_inr']:.2f}`"
                    )
            except Exception as e:
                print(f"Equity error {symbol}: {e}")

# Startup Menu Broadcast
active_cnt = len(trade_state.get('open_positions', {}))
send_menu(
    f"🎛️ *REAL-TIME TIMED ENGINE ONLINE*\n\n"
    f"🇮🇳 *Indian Stock Market:* {'🟢 OPEN' if is_indian_market_open() else '🔴 CLOSED (Opens 9:15 AM)'}\n"
    f"🌐 *Forex/Gold Market:* {'🟢 OPEN' if is_forex_market_open() else '🔴 CLOSED'}\n"
    f"⚡ *Crypto (BTC/ETH):* 🟢 24/7 ACTIVE\n\n"
    f"Neeche buttons se terminal monitor karein:"
)

listener_thread = threading.Thread(target=fast_telegram_listener, daemon=True)
listener_thread.start()

while True:
    scan_market()
    time.sleep(120)
