import os
import json
import time
from datetime import datetime
import requests
import yfinance as yf

# --- BOT CONFIGURATION ---
TELEGRAM_TOKEN = "8876905313:AAHWQ8cD9jADvepC4lQE1psRH9WOxxL21qA"
CHAT_ID = "1345385952"
DATA_FILE = "trades_data.json"
LAST_UPDATE_ID = 0
BOT_PAUSED = False

# Persistent Storage
def load_data():
    default_data = {
        "virtual_balance": 10000.00,
        "initial_capital": 10000.00,
        "open_positions": {},
        "trade_history": []
    }
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return default_data
    return default_data

def save_data(data):
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Save error: {e}")

trade_state = load_data()

# 120+ High-Momentum Watchlist
WATCHLIST = [
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
    "MUTHOOTFIN.NS", "BANDHANBNK.NS", "UCOBANK.NS", "CENTRALBK.NS", "BANKINDIA.NS"
]

# Send message with interactive keyboard dashboard
def send_menu(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "📊 Live Terminal", "callback_data": "btn_terminal"},
                {"text": "💰 Wallets", "callback_data": "btn_wallets"}
            ],
            [
                {"text": "⚡ Scalp (1:2.0)", "callback_data": "btn_scalp"},
                {"text": "🎯 Intraday (1:3.0)", "callback_data": "btn_intraday"}
            ],
            [
                {"text": "⚖️ Sizing (25%)", "callback_data": "btn_sizing"},
                {"text": "🏔️ Swing Max (1:6.0)", "callback_data": "btn_swing"}
            ],
            [
                {"text": "🔄 Refresh / Sync", "callback_data": "btn_sync"},
                {"text": "📋 Breakdown", "callback_data": "btn_breakdown"}
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
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

def send_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print(f"Alert error: {e}")

# Button Click Handlers
def handle_callback(query_id, data):
    global trade_state, BOT_PAUSED

    # Acknowledge callback query
    requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery", data={"callback_query_id": query_id})

    if data == "btn_terminal":
        positions = trade_state.get("open_positions", {})
        if not positions:
            send_menu("📊 *LIVE TERMINAL*\n\nKoi bhi active position nahi chal rahi hai.\nCapital Safe & Idle.")
        else:
            msg = "📊 *LIVE TERMINAL: ACTIVE POSITIONS*\n\n"
            for sym, d in positions.items():
                msg += f"• *{sym}* ({d['style']})\n  Qty: {d['qty']} | Entry: ₹{d['entry']:.2f}\n  SL: ₹{d['sl']:.2f} | Tgt: ₹{d['target']:.2f}\n\n"
            send_menu(msg)

    elif data == "btn_wallets":
        bal = trade_state['virtual_balance']
        allocated = sum([d['entry'] * d['qty'] for d in trade_state.get('open_positions', {}).values()])
        send_menu(
            f"💰 *WALLET & MARGIN AUDIT*\n\n"
            f"💵 Available Cash: ₹{bal:.2f}\n"
            f"📊 In-Trade Capital: ₹{allocated:.2f}\n"
            f"💼 Total Net Worth: ₹{(bal + allocated):.2f}"
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
            total_pnl = sum([t.get("pnl", 0) for t in history])
            send_menu(
                f"📈 *INSTITUTIONAL PERFORMANCE*\n\n"
                f"🎯 Win Rate: *{win_rate:.1f}%*\n"
                f"🔢 Total Closed Trades: {total}\n"
                f"✅ Wins: {len(wins)} | ❌ Losses: {len(losses)}\n"
                f"💵 Realized P&L: *{'+' if total_pnl >= 0 else ''}₹{total_pnl:.2f}*"
            )

    elif data == "btn_scalp":
        send_menu("⚡ *SCALP ENGINE*\n\nTrigger: > 4.0x RVOL Spikes\nTarget: +2.0% to 2.5%\nSL: 1.2%\nRisk-to-Reward: 1:2.0")

    elif data == "btn_intraday":
        send_menu("🎯 *INTRADAY ENGINE*\n\nTrigger: 20-Candle Breakout + >2.5x Volume\nTarget: +3.5%\nSL: 1.5%\nRisk-to-Reward: 1:3.0")

    elif data == "btn_swing":
        send_menu("🏔️ *SWING MAX ENGINE*\n\nTrigger: 20-Day Range Breakouts\nTarget: +6.0% to +12.0%\nSL: 2.5%\nRisk-to-Reward: 1:6.0")

    elif data == "btn_sizing":
        send_menu("⚖️ *POSITION SIZING*\n\nMax Allocation: 25% Capital Per Position\nMax Active Risk: 2% of Total Portfolio\nAuto-Sizing: Enabled")

    elif data == "btn_sync":
        send_alert("🔄 *Syncing Market Data...* Scanning watchlist now.")
        scan_market()

    elif data == "btn_breakdown":
        today_str = datetime.now().strftime("%Y-%m-%d")
        today_trades = [t for t in trade_state.get("trade_history", []) if t.get("date") == today_str]
        pnl = sum([t.get("pnl", 0) for t in today_trades])
        send_menu(
            f"📋 *TODAY'S BREAKDOWN ({today_str})*\n\n"
            f"Trades: {len(today_trades)}\n"
            f"Net Daily P&L: {'+' if pnl >= 0 else ''}₹{pnl:.2f}\n"
            f"Capital Buffer: ₹{trade_state['virtual_balance']:.2f}"
        )

    elif data == "btn_pause":
        BOT_PAUSED = True
        send_menu("⏸️ *SCANNER PAUSED*\nNaye breakout alerts block kar diye gaye hain. Open trades continue track honge.")

    elif data == "btn_resume":
        BOT_PAUSED = False
        send_menu("▶️ *SCANNER RESUMED*\nWatchlist scanning live shuru ho chuki hai.")

    elif data == "btn_panic":
        # Panic exit: Market orders par sabhi open trades square-off
        positions = list(trade_state.get("open_positions", {}).items())
        if not positions:
            send_menu("🚨 *PANIC EXIT*\nKoi bhi open position nahi hai.")
            return

        today_str = datetime.now().strftime("%Y-%m-%d")
        for sym, d in positions:
            trade_state["virtual_balance"] += (d["entry"] * d["qty"])
            trade_state["trade_history"].append({
                "symbol": sym, "type": d["type"], "entry": d["entry"], "exit": d["entry"],
                "pnl": 0.0, "result": "PANIC_CLOSE", "style": d["style"], "date": today_str
            })
            del trade_state["open_positions"][sym]
        save_data(trade_state)
        send_menu("🚨 *PANIC EXIT COMPLETE!*\nSaari positions ko entry level par close kar diya gaya hai. Balance restored.")

# Listener for Button Clicks
def check_telegram_updates():
    global LAST_UPDATE_ID
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={LAST_UPDATE_ID + 1}&timeout=1"
    try:
        res = requests.get(url, timeout=3).json()
        for update in res.get("result", []):
            LAST_UPDATE_ID = update["update_id"]
            if "callback_query" in update:
                q_id = update["callback_query"]["id"]
                data = update["callback_query"]["data"]
                handle_callback(q_id, data)
            elif "message" in update:
                # Jab user koi text bheje, Dashboard bhej do
                send_menu("🎛️ *COMMAND TERMINAL ACTIVE*\nNeeche diye gaye buttons ko tap karein:")
    except Exception as e:
        print(f"Listener error: {e}")

def classify_trade_style(vol_spike_ratio):
    if vol_spike_ratio >= 4.0:
        return "⚡ SCALP", 0.012, 0.025
    elif vol_spike_ratio >= 2.5:
        return "🎯 INTRADAY", 0.015, 0.035
    else:
        return "🏔️ SWING", 0.025, 0.060

def manage_open_positions():
    global trade_state
    closed = []
    positions = trade_state.get("open_positions", {})
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    for symbol, pos in list(positions.items()):
        try:
            df = yf.download(tickers=symbol, period="1d", interval="5m", progress=False)
            if df is None or df.empty:
                continue
            if hasattr(df.columns, 'levels'):
                df.columns = [col[0] for col in df.columns]
                
            curr_price = float(df['Close'].iloc[-1])
            entry = pos['entry']
            qty = pos['qty']
            
            # Trailing SL Trigger (+1.5% profit)
            if pos['type'] == "BUY":
                if not pos.get('trailed', False) and curr_price >= entry * 1.015:
                    pos['sl'] = entry
                    pos['trailed'] = True
                    save_data(trade_state)
                    send_alert(f"🛡️ *TRAILING SL ACTIVE:* {symbol} SL moved to cost ₹{entry:.2f}. Zero risk locked!")

                if curr_price >= pos['target']:
                    profit = round((curr_price - entry) * qty, 2)
                    trade_state["virtual_balance"] += (curr_price * qty)
                    trade_state["trade_history"].append({
                        "symbol": symbol, "type": "BUY", "entry": entry, "exit": curr_price,
                        "pnl": profit, "result": "WIN", "style": pos["style"], "date": today_str
                    })
                    closed.append(symbol)
                    send_alert(f"🎯 *TARGET HIT!*\n\n📈 *{symbol}* ({pos['style']})\nExit: ₹{curr_price:.2f} | Profit: +₹{profit}\nBalance: ₹{trade_state['virtual_balance']:.2f}")

                elif curr_price <= pos['sl']:
                    loss = round((entry - curr_price) * qty, 2)
                    trade_state["virtual_balance"] += (curr_price * qty)
                    trade_state["trade_history"].append({
                        "symbol": symbol, "type": "BUY", "entry": entry, "exit": curr_price,
                        "pnl": -loss, "result": "LOSS", "style": pos["style"], "date": today_str
                    })
                    closed.append(symbol)
                    send_alert(f"🛑 *STOP LOSS HIT!*\n\n📉 *{symbol}*\nExit: ₹{curr_price:.2f} | Loss: -₹{loss}\nBalance: ₹{trade_state['virtual_balance']:.2f}")

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

    for symbol in WATCHLIST:
        if symbol in trade_state.get("open_positions", {}):
            continue

        try:
            time.sleep(0.2)
            df = yf.download(tickers=symbol, period="5d", interval="15m", progress=False)
            if df is None or df.empty or len(df) < 25:
                continue

            if hasattr(df.columns, 'levels'):
                df.columns = [col[0] for col in df.columns]

            df['Vol_Avg'] = df['Volume'].rolling(window=20).mean()
            df['High_20'] = df['High'].shift(1).rolling(window=20).max()
            df['Low_20'] = df['Low'].shift(1).rolling(window=20).min()

            curr_close = float(df['Close'].iloc[-1])
            curr_vol = float(df['Volume'].iloc[-1])
            avg_vol = float(df['Vol_Avg'].iloc[-1])
            high_20 = float(df['High_20'].iloc[-1])

            vol_ratio = curr_vol / avg_vol if avg_vol > 0 else 1.0

            # Breakout logic with 2x Volume Surge
            if vol_ratio >= 2.0 and curr_close > high_20:
                style_name, sl_pct, tgt_pct = classify_trade_style(vol_ratio)
                
                trade_fund = min(2500.0, trade_state["virtual_balance"])
                qty = int(trade_fund // curr_close)
                if qty < 1:
                    continue

                sl = round(curr_close * (1 - sl_pct), 2)
                tgt = round(curr_close * (1 + tgt_pct), 2)
                trade_state["virtual_balance"] -= (curr_close * qty)
                
                trade_state["open_positions"][symbol] = {
                    'type': 'BUY', 'entry': curr_close, 'qty': qty,
                    'sl': sl, 'target': tgt, 'style': style_name, 'trailed': False
                }
                save_data(trade_state)

                send_alert(
                    f"🚀 *DEMO TRADE ENTRY: BUY*\n\n"
                    f"📊 *Type:* {style_name}\n"
                    f"📈 *Stock:* {symbol}\n"
                    f"💵 *Entry:* ₹{curr_close:.2f} | *Qty:* {qty}\n"
                    f"🔥 *Volume:* {vol_ratio:.1f}x Spike\n"
                    f"🎯 *Target:* ₹{tgt}\n"
                    f"🛑 *SL:* ₹{sl}\n"
                    f"💼 Rem. Balance: ₹{trade_state['virtual_balance']:.2f}"
                )

        except Exception as e:
            print(f"Scan error {symbol}: {e}")

# Startup Menu Broadcast
send_menu("🎛️ *INSTITUTIONAL TRADING TERMINAL LIVE*\nNeeche buttons diye gaye hain, kisi bhi feature par tap karein:")

# Loop with Instant Button Listener
while True:
    scan_market()
    for _ in range(30):
        check_telegram_updates()
        time.sleep(10)
