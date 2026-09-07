import os
import json
import time
import threading
from datetime import datetime
import requests
import yfinance as yf

# --- BOT CONFIGURATION ---
TELEGRAM_TOKEN = "8876905313:AAHWQ8cD9jADvepC4lQE1psRH9WOxxL21qA"
CHAT_ID = "1345385952"
DATA_FILE = "trades_data.json"
LAST_UPDATE_ID = 0
BOT_PAUSED = False

def send_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        res = requests.post(url, data=payload, timeout=10)
        return res.json()
    except Exception as e:
        print(f"Telegram API error: {e}")
        return None

# --- DUAL-WALLET LOADER (INR + USD SEPARATED) ---
def load_data():
    default_data = {
        "virtual_balance_inr": 175.89,
        "virtual_balance_usd": 100.00,
        "initial_capital_inr": 10000.00,
        "initial_capital_usd": 100.00,
        "open_positions": {
            "GAIL.NS": {"type": "BUY", "entry": 177.20, "qty": 14, "sl": 174.54, "target": 183.40, "style": "🎯 INTRADAY", "trailed_level": 0, "currency": "INR"},
            "INOXWIND.NS": {"type": "BUY", "entry": 75.71, "qty": 33, "sl": 74.57, "target": 78.36, "style": "🎯 INTRADAY", "trailed_level": 0, "currency": "INR"},
            "NYKAA.NS": {"type": "BUY", "entry": 336.60, "qty": 7, "sl": 331.55, "target": 348.38, "style": "🎯 INTRADAY", "trailed_level": 0, "currency": "INR"},
            "JPPOWER.NS": {"type": "BUY", "entry": 17.04, "qty": 146, "sl": 16.78, "target": 17.64, "style": "🎯 INTRADAY", "trailed_level": 0, "currency": "INR"}
        },
        "trade_history": []
    }

    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                saved = json.load(f)
                saved["virtual_balance_usd"] = saved.get("virtual_balance_usd", 100.00)
                if "virtual_balance_inr" not in saved:
                    saved["virtual_balance_inr"] = saved.get("virtual_balance", 175.89)
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

# ⚡ DEDICATED SCALPING ASSETS (5-Minute Fast Execution Engine)
SCALP_ASSETS = ["GC=F", "BTC-USD", "ETH-USD"]

# 🌐 FOREX STANDARD ASSETS (15-Minute Intraday Engine)
FOREX_STANDARD = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X"]

# 🇮🇳 INDIAN EQUITIES WATCHLIST (15-Minute Institutional Engine)
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
        if not positions:
            send_menu("📊 *LIVE TERMINAL*\n\nKoi active trade open nahi hai.")
        else:
            msg_inr = "🇮🇳 *INDIAN POSITIONS*\n"
            msg_fx = "\n🌐 *VANTAGE/XM POSITIONS*\n"
            has_inr = False
            has_fx = False

            for sym, d in positions.items():
                level = d.get('trailed_level', 0)
                trail_info = "Cost Locked" if level == 1 else "Initial SL"
                clean_name = format_clean_symbol(sym)

                if is_forex_or_crypto(sym):
                    has_fx = True
                    msg_fx += f"• *{clean_name}* ({d['style']})\n  Lot: {d['qty']} | Entry: {d['entry']:.4f}\n  SL: {d['sl']:.4f} ({trail_info}) | Tgt: {d['target']:.4f}\n\n"
                else:
                    has_inr = True
                    msg_inr += f"• *{clean_name}* ({d['style']})\n  Qty: {d['qty']} | Entry: ₹{d['entry']:.2f}\n  SL: ₹{d['sl']:.2f} ({trail_info}) | Tgt: ₹{d['target']:.2f}\n\n"

            final_msg = ""
            if has_inr: final_msg += msg_inr
            if has_fx: final_msg += msg_fx
            send_menu(final_msg)

    elif data == "btn_wallets":
        inr_cash = trade_state['virtual_balance_inr']
        usd_cash = trade_state['virtual_balance_usd']
        inr_alloc = sum([d['entry'] * d['qty'] for sym, d in trade_state.get('open_positions', {}).items() if not is_forex_or_crypto(sym)])
        usd_alloc = sum([20.0 for sym in trade_state.get('open_positions', {}) if is_forex_or_crypto(sym)])

        send_menu(
            f"💰 *SEPARATED WALLET AUDIT*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
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
        total = len(history)
        if total == 0:
            send_menu("📈 *PERFORMANCE*\n\nAbhi tak koi trade close nahi hua hai.")
        else:
            wins = [t for t in history if t.get("pnl", 0) > 0]
            losses = [t for t in history if t.get("pnl", 0) <= 0]
            win_rate = (len(wins) / total) * 100
            pnl_inr = sum([t.get("pnl", 0) for t in history if t.get("currency") == "INR"])
            pnl_usd = sum([t.get("pnl", 0) for t in history if t.get("currency") == "USD"])

            send_menu(
                f"📈 *TOTAL PERFORMANCE AUDIT*\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🎯 Win Rate: *{win_rate:.1f}%* ({len(wins)}W | {len(losses)}L)\n"
                f"🇮🇳 Indian Equities P&L: *{'+' if pnl_inr >= 0 else ''}₹{pnl_inr:.2f}*\n"
                f"🌐 Forex/Crypto P&L: *{'+' if pnl_usd >= 0 else ''}${pnl_usd:.2f} USD*"
            )

    elif data == "btn_sync":
        send_alert("🔄 *Scanning Markets (5m Scalp + 15m Equities)...*")
        threading.Thread(target=scan_market).start()

    elif data == "btn_breakdown":
        today_str = datetime.now().strftime("%Y-%m-%d")
        today_trades = [t for t in trade_state.get("trade_history", []) if t.get("date") == today_str]
        pnl_inr = sum([t.get("pnl", 0) for t in today_trades if t.get("currency") == "INR"])
        pnl_usd = sum([t.get("pnl", 0) for t in today_trades if t.get("currency") == "USD"])
        send_menu(
            f"📋 *TODAY'S BREAKDOWN ({today_str})*\n\n"
            f"Total Trades: {len(today_trades)}\n"
            f"🇮🇳 INR Day P&L: {'+' if pnl_inr >= 0 else ''}₹{pnl_inr:.2f}\n"
            f"🌐 USD Day P&L: {'+' if pnl_usd >= 0 else ''}${pnl_usd:.2f} USD"
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

        today_str = datetime.now().strftime("%Y-%m-%d")
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
        send_menu("🚨 *PANIC EXIT COMPLETE!*\nSaare trades close kar diye gaye hain.")

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
    today_str = datetime.now().strftime("%Y-%m-%d")

    for symbol, pos in list(positions.items()):
        try:
            interval = "5m" if symbol in SCALP_ASSETS else "15m"
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
            is_fx = is_forex_or_crypto(symbol)
            clean_name = format_clean_symbol(symbol)
            curr = pos.get("currency", "USD" if is_fx else "INR")

            # Trailing Trigger: Scalp = +0.25%, Standard = +1.2%
            trail_point = 0.25 if symbol in SCALP_ASSETS else (0.60 if is_fx else 1.20)

            if pos['type'] == "BUY":
                if current_level < 1 and gain_pct >= trail_point:
                    pos['sl'] = round(entry, 4 if is_fx else 2)
                    pos['trailed_level'] = 1
                    save_data(trade_state)
                    tag = "⚡ *[5M SCALP TRAIL]*" if symbol in SCALP_ASSETS else "🛡️ *[TRAILING ACTIVE]*"
                    send_alert(f"{tag}: `{clean_name}`\nGain: +{gain_pct:.2f}%\nStop Loss locked at Entry bhav (Cost Locked!)")

                # Target Hit
                if curr_price >= pos['target']:
                    profit = round((curr_price - entry) * qty, 2)
                    if curr == "USD":
                        trade_state["virtual_balance_usd"] += (20.0 + profit)
                        send_alert(
                            f"🎯 *TARGET HIT: TAKE PROFIT REACHED*\n"
                            f"━━━━━━━━━━━━━━━━━━━━\n"
                            f"🌐 *Broker:* Vantage / XM\n"
                            f"📊 *Asset:* `{clean_name}` ({pos['style']})\n"
                            f"💵 *Exit:* `${curr_price:.4f}`\n"
                            f"💰 *Profit:* `+${profit:.2f} USD`\n"
                            f"💼 *USD Balance:* `${trade_state['virtual_balance_usd']:.2f} USD`"
                        )
                    else:
                        trade_state["virtual_balance_inr"] += (curr_price * qty)
                        send_alert(
                            f"🎯 *TARGET HIT!*\n"
                            f"━━━━━━━━━━━━━━━━━━━━\n"
                            f"🇮🇳 *Stock:* `{clean_name}` ({pos['style']})\n"
                            f"💵 *Exit:* ₹{curr_price:.2f}\n"
                            f"💰 *Profit:* +₹{profit:.2f}\n"
                            f"💼 *INR Balance:* ₹{trade_state['virtual_balance_inr']:.2f}"
                        )
                    trade_state["trade_history"].append({
                        "symbol": symbol, "type": "BUY", "entry": entry, "exit": curr_price,
                        "pnl": profit, "result": "WIN", "style": pos["style"], "date": today_str, "currency": curr
                    })
                    closed.append(symbol)

                # SL Hit
                elif curr_price <= pos['sl']:
                    pnl = round((curr_price - entry) * qty, 2)
                    outcome = "WIN" if pnl >= 0 else "LOSS"
                    if curr == "USD":
                        trade_state["virtual_balance_usd"] += (20.0 + pnl)
                        title = "🛡️ *TRAILING SL HIT (PROFIT SECURED)*" if pnl >= 0 else "🛑 *STOP LOSS HIT*"
                        send_alert(
                            f"{title}\n"
                            f"━━━━━━━━━━━━━━━━━━━━\n"
                            f"🌐 *Broker:* Vantage / XM\n"
                            f"📊 *Asset:* `{clean_name}`\n"
                            f"💵 *Exit:* `${curr_price:.4f}`\n"
                            f"💰 *P&L:* `{'+' if pnl >= 0 else ''}${pnl:.2f} USD`\n"
                            f"💼 *USD Balance:* `${trade_state['virtual_balance_usd']:.2f} USD`"
                        )
                    else:
                        trade_state["virtual_balance_inr"] += (curr_price * qty)
                        title = "🛡️ *TRAILING SL HIT (PROFIT SECURED)*" if pnl >= 0 else "🛑 *STOP LOSS HIT*"
                        send_alert(
                            f"{title}\n"
                            f"━━━━━━━━━━━━━━━━━━━━\n"
                            f"🇮🇳 *Stock:* `{clean_name}`\n"
                            f"💵 *Exit:* ₹{curr_price:.2f}\n"
                            f"💰 *P&L:* {'+' if pnl >= 0 else ''}₹{pnl:.2f}\n"
                            f"💼 *INR Balance:* ₹{trade_state['virtual_balance_inr']:.2f}"
                        )
                    trade_state["trade_history"].append({
                        "symbol": symbol, "type": "BUY", "entry": entry, "exit": curr_price,
                        "pnl": pnl, "result": outcome, "style": pos["style"], "date": today_str, "currency": curr
                    })
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
    # ⚡ ENGINE 1: BTC, ETH & GOLD 5-MINUTE HIGH-SPEED SCALPER
    # ==============================================================
    if trade_state["virtual_balance_usd"] >= 20.0:
        for symbol in SCALP_ASSETS:
            if symbol in trade_state.get("open_positions", {}):
                continue
            try:
                time.sleep(0.1)
                df = yf.download(tickers=symbol, period="1d", interval="5m", progress=False)
                if df is None or df.empty or len(df) < 25:
                    continue
                if hasattr(df.columns, 'levels'):
                    df.columns = [col[0] for col in df.columns]

                df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
                df['Vol_Avg'] = df['Volume'].rolling(window=20).mean()
                df['High_10'] = df['High'].shift(1).rolling(window=10).max()

                curr_close = float(df['Close'].iloc[-1])
                ema20 = float(df['EMA20'].iloc[-1])
                curr_vol = float(df['Volume'].iloc[-1])
                avg_vol = float(df['Vol_Avg'].iloc[-1])
                high_10 = float(df['High_10'].iloc[-1])

                vol_ratio = curr_vol / avg_vol if avg_vol > 0 else 1.0

                # 5m Scalper Condition: Price > EMA20, Volume > 2.5x, Breakout 10-bar High
                if curr_close > ema20 and curr_close > high_10 and vol_ratio >= 2.5:
                    sl = round(curr_close * (1 - 0.0035), 4)    # 0.35% Tight SL
                    tgt = round(curr_close * (1 + 0.0070), 4)   # 0.70% Scalp Target (1:2 RR)
                    trade_state["virtual_balance_usd"] -= 20.00

                    trade_state["open_positions"][symbol] = {
                        'type': 'BUY', 'entry': curr_close, 'qty': 0.01,
                        'sl': sl, 'target': tgt, 'style': "⚡ 5M SCALP", 'trailed_level': 0, 'currency': "USD"
                    }
                    save_data(trade_state)
                    clean_sym = format_clean_symbol(symbol)

                    send_alert(
                        f"⚡ *[VANTAGE / XM ALERT]: 5M HIGH-SPEED SCALP*\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"📊 *Asset:* `{clean_sym}`\n"
                        f"⚡ *Signal:* `BUY MARKET`\n"
                        f"💵 *Entry:* `{curr_close:.4f}`\n"
                        f"🛑 *Stop Loss:* `{sl:.4f}` (-0.35%)\n"
                        f"🎯 *Take Profit:* `{tgt:.4f}` (+0.70%)\n"
                        f"📈 *Trend Filter:* `Above 5M EMA20`\n"
                        f"🔥 *Volume Surge:* `{vol_ratio:.1f}x Spike`\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"📌 *Order Setup (MT4/MT5):*\n"
                        f"• Account Base: `$100 USD Micro`\n"
                        f"• Lot Sizing: `0.01 Lot`\n"
                        f"• Breakeven Lock: `At +0.25% Move`\n"
                        f"💼 *Remaining USD Cash:* `${trade_state['virtual_balance_usd']:.2f} USD`"
                    )
            except Exception as e:
                print(f"Scalp error {symbol}: {e}")

    # ==============================================================
    # 🌐 ENGINE 2: FOREX STANDARD (15-Minute Intraday Engine)
    # ==============================================================
    if trade_state["virtual_balance_usd"] >= 20.0:
        for symbol in FOREX_STANDARD:
            if symbol in trade_state.get("open_positions", {}):
                continue
            try:
                time.sleep(0.1)
                df = yf.download(tickers=symbol, period="5d", interval="15m", progress=False)
                if df is None or df.empty or len(df) < 25:
                    continue
                if hasattr(df.columns, 'levels'):
                    df.columns = [col[0] for col in df.columns]

                df['Vol_Avg'] = df['Volume'].rolling(window=20).mean()
                df['High_20'] = df['High'].shift(1).rolling(window=20).max()
                curr_close = float(df['Close'].iloc[-1])
                curr_vol = float(df['Volume'].iloc[-1])
                avg_vol = float(df['Vol_Avg'].iloc[-1])
                high_20 = float(df['High_20'].iloc[-1])
                vol_ratio = curr_vol / avg_vol if avg_vol > 0 else 1.0

                if vol_ratio >= 2.0 and curr_close > high_20:
                    sl = round(curr_close * (1 - 0.0080), 4)
                    tgt = round(curr_close * (1 + 0.0180), 4)
                    trade_state["virtual_balance_usd"] -= 20.00

                    trade_state["open_positions"][symbol] = {
                        'type': 'BUY', 'entry': curr_close, 'qty': 0.01,
                        'sl': sl, 'target': tgt, 'style': "🎯 FX INTRADAY", 'trailed_level': 0, 'currency': "USD"
                    }
                    save_data(trade_state)
                    clean_sym = format_clean_symbol(symbol)

                    send_alert(
                        f"🌐 *[VANTAGE / XM ALERT]: 15M FX INTRADAY*\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"📊 *Pair:* `{clean_sym}`\n"
                        f"⚡ *Action:* `BUY MARKET`\n"
                        f"💵 *Entry:* `{curr_close:.4f}`\n"
                        f"🛑 *Stop Loss:* `{sl:.4f}`\n"
                        f"🎯 *Take Profit:* `{tgt:.4f}`\n"
                        f"🔥 *Volume:* `{vol_ratio:.1f}x Spike`\n"
                        f"💼 *Remaining USD Cash:* `${trade_state['virtual_balance_usd']:.2f} USD`"
                    )
            except Exception as e:
                print(f"FX error {symbol}: {e}")

    # ==============================================================
    # 🇮🇳 ENGINE 3: INDIAN EQUITIES (15-Minute Breakout Engine)
    # ==============================================================
    if trade_state["virtual_balance_inr"] >= 1000.0:
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
                        f"🇮🇳 *[INDIAN EQUITIES ALERT]: 🎯 INTRADAY*\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"📈 *Stock:* `{clean_sym}`\n"
                        f"💵 *Entry:* `₹{curr_close:.2f}` | *Qty:* `{qty}`\n"
                        f"🛑 *SL:* `₹{sl}`\n"
                        f"🎯 *Target:* `₹{tgt}`\n"
                        f"🔥 *Volume:* `{vol_ratio:.1f}x Spike`\n"
                        f"💼 *INR Balance:* `₹{trade_state['virtual_balance_inr']:.2f}`"
                    )
            except Exception as e:
                print(f"Equity error {symbol}: {e}")

# Startup Notification
active_cnt = len(trade_state.get('open_positions', {}))
send_menu(
    f"🎛️ *MULTI-SPEED HYBRID ENGINE ONLINE*\n\n"
    f"⚡ *BTC, ETH & Gold:* 5-Minute Fast Scalper\n"
    f"🌐 *Forex Pairs:* 15-Minute Intraday ($100 Pool)\n"
    f"🇮🇳 *Indian Equities:* 15-Minute Breakouts (₹10,000 Pool)\n"
    f"📂 *Active Restored Trades:* {active_cnt}\n\n"
    f"Neeche buttons se terminal monitor karein:"
)

listener_thread = threading.Thread(target=fast_telegram_listener, daemon=True)
listener_thread.start()

while True:
    scan_market()
    time.sleep(120)
