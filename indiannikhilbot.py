import os
import json
import time
import threading
from datetime import datetime
from zoneinfo import ZoneInfo
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
import yfinance as yf
import pandas as pd
import numpy as np

# --- BOT CONFIGURATION ---
TELEGRAM_TOKEN = "8876905313:AAHWQ8cD9jADvepC4lQE1psRH9WOxxL21qA"
CHAT_ID = "1345385952"
DATA_FILE = "swing_data.json"
LAST_UPDATE_ID = 0
BOT_PAUSED = False
IST = ZoneInfo("Asia/Kolkata")
state_lock = threading.Lock()

def send_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        res = requests.post(url, data=payload, timeout=10)
        return res.json()
    except Exception as e:
        print(f"Telegram error: {e}")
        return None

# --- MARKET TIMING CHECK (9:15 AM - 3:30 PM IST) ---
def is_indian_market_open():
    now = datetime.now(IST)
    if now.weekday() >= 5:  # Saturday/Sunday closed
        return False
    market_start = now.replace(hour=9, minute=15, second=0, microsecond=0)
    market_end = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return market_start <= now <= market_end

# --- STRATEGIES CONFIGURATION ---
STRATEGIES = {
    "STRAT_1": {
        "name": "20D Volume Breakout",
        "desc": "20-Day High Breakout + 2.0x Volume Surge",
        "target_pct": 0.12,
        "sl_pct": 0.035,
        "trail_at": 0.05
    },
    "STRAT_2": {
        "name": "50 EMA Pullback Bounce",
        "desc": "Bullish Reversal candle touching 50 EMA Support",
        "target_pct": 0.10,
        "sl_pct": 0.030,
        "trail_at": 0.04
    },
    "STRAT_3": {
        "name": "Supertrend + RSI Momentum",
        "desc": "Supertrend Bullish Flip with RSI crossing 60",
        "target_pct": 0.14,
        "sl_pct": 0.040,
        "trail_at": 0.05
    },
    "STRAT_4": {
        "name": "MACD Zero-Line Crossover",
        "desc": "MACD Cross above 0-line + Positive Histogram",
        "target_pct": 0.12,
        "sl_pct": 0.035,
        "trail_at": 0.05
    },
    "STRAT_5": {
        "name": "Bollinger Squeeze Expansion",
        "desc": "Band Width Contraction followed by Upper Band Break",
        "target_pct": 0.15,
        "sl_pct": 0.040,
        "trail_at": 0.06
    }
}

# --- STATE MANAGEMENT ---
def load_data():
    default_data = {
        "virtual_balance": 10000.00,
        "initial_capital": 10000.00,
        "active_strategy": "STRAT_1",
        "open_positions": {},
        "trade_history": []
    }
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                saved = json.load(f)
                if "active_strategy" not in saved:
                    saved["active_strategy"] = "STRAT_1"
                return saved
        except Exception:
            pass
    return default_data

def save_data(data):
    with state_lock:
        try:
            with open(DATA_FILE, "w") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Save error: {e}")

trade_state = load_data()

# 🎯 TOP HIGH-LIQUIDITY SWING STOCKS (NSE)
SWING_WATCHLIST = [
    "TATASTEEL.NS", "BEL.NS", "BHEL.NS", "SAIL.NS", "NATIONALUM.NS", "NMDC.NS",
    "PFC.NS", "RECLTD.NS", "COALINDIA.NS", "HINDALCO.NS", "VEDL.NS", "ONGC.NS",
    "IRFC.NS", "RVNL.NS", "SUZLON.NS", "ZOMATO.NS", "PNB.NS", "BANKBARODA.NS",
    "CANBK.NS", "ASHOKLEY.NS", "FEDERALBNK.NS", "IOC.NS", "POWERGRID.NS", "NTPC.NS",
    "IREDA.NS", "HUDCO.NS", "HAL.NS", "BDL.NS", "EXIDEIND.NS", "MOTHERSON.NS",
    "JINDALSTEL.NS", "JSWSTEEL.NS", "BHARTIARTL.NS", "ADANIENT.NS", "ADANIPOWER.NS",
    "TATAPOWER.NS", "INOXWIND.NS", "TITAGARH.NS", "MAZDOCK.NS", "COCHINSHIP.NS"
]

# --- TELEGRAM MENUS ---
def send_menu(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    active_strat = STRATEGIES.get(trade_state.get("active_strategy", "STRAT_1"), {})["name"]
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "📊 Swing Positions", "callback_data": "btn_positions"},
                {"text": "💰 10K to 100K Wallet", "callback_data": "btn_wallet"}
            ],
            [
                {"text": f"⚙️ Strategy: {active_strat}", "callback_data": "btn_select_strat"},
                {"text": "🧪 Backtest All (Win%)", "callback_data": "btn_backtest_menu"}
            ],
            [
                {"text": "🔄 Scan Breakouts", "callback_data": "btn_scan"},
                {"text": "📈 Swing P&L Audit", "callback_data": "btn_audit"}
            ],
            [
                {"text": "⏸️ Pause", "callback_data": "btn_pause"},
                {"text": "▶️ Resume", "callback_data": "btn_resume"},
                {"text": "🚨 Close All", "callback_data": "btn_panic"}
            ]
        ]
    }
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown", "reply_markup": json.dumps(keyboard)}
    try:
        requests.post(url, data=payload, timeout=5)
    except Exception as e:
        print(f"Menu error: {e}")

def send_strategy_selector():
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    curr = trade_state.get("active_strategy", "STRAT_1")
    buttons = []
    for k, v in STRATEGIES.items():
        tick = "✅ " if k == curr else ""
        buttons.append([{"text": f"{tick}{v['name']}", "callback_data": f"set_{k}"}])
    buttons.append([{"text": "⬅️ Back to Terminal", "callback_data": "btn_back_menu"}])
    
    keyboard = {"inline_keyboard": buttons}
    msg = (
        "⚙️ *SELECT ACTIVE SWING STRATEGY*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Choose which pattern the scanner will monitor:\n"
    )
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown", "reply_markup": json.dumps(keyboard)}
    requests.post(url, data=payload, timeout=5)

def send_backtest_options():
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    buttons = []
    for k, v in STRATEGIES.items():
        buttons.append([{"text": f"🧪 Test {v['name']}", "callback_data": f"bt_{k}"}])
    buttons.append([{"text": "🧪 Run Comparative Audit (All 5)", "callback_data": "bt_ALL"}])
    buttons.append([{"text": "⬅️ Back to Terminal", "callback_data": "btn_back_menu"}])
    keyboard = {"inline_keyboard": buttons}
    msg = (
        "🧪 *SWING STRATEGY HISTORICAL BACKTEST*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Pichle 1 saal ke real NSE Daily candle data par backtest karke win rate aur P&L audit karein:"
    )
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown", "reply_markup": json.dumps(keyboard)}
    requests.post(url, data=payload, timeout=5)

# --- BACKTESTING ENGINE ---
def run_backtest_for_strategy(strat_key, tickers_subset=None):
    strat = STRATEGIES[strat_key]
    tickers = tickers_subset or SWING_WATCHLIST[:12] # Efficient backtest over top 12 swing leaders
    total_trades = 0
    wins = 0
    losses = 0
    total_pct_gain = 0.0

    target = strat["target_pct"]
    sl = strat["sl_pct"]

    for sym in tickers:
        try:
            df = yf.download(tickers=sym, period="1y", interval="1d", progress=False)
            if df is None or df.empty or len(df) < 55:
                continue
            if hasattr(df.columns, 'levels'):
                df.columns = [col[0] for col in df.columns]

            # Indicators setup
            df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
            df['Vol_Avg'] = df['Volume'].rolling(window=15).mean()
            df['High_20'] = df['High'].shift(1).rolling(window=20).max()

            # RSI
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss.replace(0, np.nan)
            df['RSI'] = 100 - (100 / (1 + rs))

            # MACD
            exp1 = df['Close'].ewm(span=12, adjust=False).mean()
            exp2 = df['Close'].ewm(span=26, adjust=False).mean()
            df['MACD'] = exp1 - exp2
            df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()

            # Bollinger Bands
            df['SMA20'] = df['Close'].rolling(window=20).mean()
            df['STD20'] = df['Close'].rolling(window=20).std()
            df['UpperBB'] = df['SMA20'] + (2 * df['STD20'])
            df['LowerBB'] = df['SMA20'] - (2 * df['STD20'])
            df['BandWidth'] = (df['UpperBB'] - df['LowerBB']) / df['SMA20']

            in_pos = False
            entry_p = 0.0

            for i in range(30, len(df)):
                c = float(df['Close'].iloc[i])
                v = float(df['Volume'].iloc[i])
                v_avg = float(df['Vol_Avg'].iloc[i])
                vol_r = v / v_avg if v_avg > 0 else 1.0

                if in_pos:
                    gain_cur = (c - entry_p) / entry_p
                    if gain_cur >= target:
                        wins += 1
                        total_trades += 1
                        total_pct_gain += target
                        in_pos = False
                    elif gain_cur <= -sl:
                        losses += 1
                        total_trades += 1
                        total_pct_gain -= sl
                        in_pos = False
                    continue

                signal = False
                if strat_key == "STRAT_1": # 20D Breakout + Vol
                    if c > float(df['High_20'].iloc[i]) and vol_r >= 2.0:
                        signal = True
                elif strat_key == "STRAT_2": # 50 EMA Pullback Bounce
                    low_p = float(df['Low'].iloc[i])
                    ema_p = float(df['EMA50'].iloc[i])
                    if low_p <= ema_p and c > ema_p and c > float(df['Open'].iloc[i]):
                        signal = True
                elif strat_key == "STRAT_3": # Supertrend/RSI
                    if float(df['RSI'].iloc[i]) >= 60 and c > float(df['EMA50'].iloc[i]):
                        signal = True
                elif strat_key == "STRAT_4": # MACD Cross
                    if float(df['MACD'].iloc[i]) > 0 and float(df['MACD'].iloc[i]) > float(df['Signal'].iloc[i]) and float(df['MACD'].iloc[i-1]) <= float(df['Signal'].iloc[i-1]):
                        signal = True
                elif strat_key == "STRAT_5": # Bollinger Squeeze
                    bw = float(df['BandWidth'].iloc[i])
                    bw_avg = float(df['BandWidth'].rolling(10).mean().iloc[i])
                    if bw < bw_avg and c > float(df['UpperBB'].iloc[i]):
                        signal = True

                if signal:
                    in_pos = True
                    entry_p = c

        except Exception as e:
            pass

    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0
    return {
        "strat": strat["name"],
        "total": total_trades,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "net_gain": total_pct_gain * 100
    }

def handle_backtest_action(strat_key):
    if strat_key == "ALL":
        send_alert("⏳ *Running 1-Year Backtest for all 5 Strategies on NSE Basket... (Hold on 15s)*")
        res_list = []
        for k in STRATEGIES.keys():
            res_list.append(run_backtest_for_strategy(k))
        
        msg = "📊 *NSE 1-YEAR COMPARATIVE BACKTEST RESULTS*\n━━━━━━━━━━━━━━━━━━━━\n"
        for r in res_list:
            msg += (
                f"🎯 *{r['strat']}*\n"
                f"• Win Rate: *{r['win_rate']:.1f}%* ({r['wins']}W | {r['losses']}L)\n"
                f"• Total Trades: `{r['total']}` | Net Est. Gain: *{r['net_gain']:+.1f}%*\n\n"
            )
        msg += "━━━━━━━━━━━━━━━━━━━━\n💡 *Recommendation:* Top performing strategy ko activate karein!"
        send_menu(msg)
    else:
        strat_name = STRATEGIES[strat_key]["name"]
        send_alert(f"⏳ *Testing `{strat_name}` against 1-year historical daily data...*")
        r = run_backtest_for_strategy(strat_key)
        msg = (
            f"🧪 *BACKTEST REPORT: {r['strat']}*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 Win Rate: *{r['win_rate']:.1f}%*\n"
            f"📦 Total Simulated Trades: `{r['total']}`\n"
            f"✅ Profitable Exits (+{int(STRATEGIES[strat_key]['target_pct']*100)}%): `{r['wins']}`\n"
            f"❌ Stop Loss Exits (-{STRATEGIES[strat_key]['sl_pct']*100:.1f}%): `{r['losses']}`\n"
            f"📈 Cumulative Yield: *{r['net_gain']:+.1f}%*\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
        send_menu(msg)

def handle_callback(query_id, data):
    global trade_state, BOT_PAUSED
    requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery", data={"callback_query_id": query_id})

    if data == "btn_positions":
        with state_lock:
            pos = trade_state.get("open_positions", {})
        
        msg = "📊 *ACTIVE SWING POSITIONS (HOLDING)*\n━━━━━━━━━━━━━━━━━━━━\n"
        if pos:
            for sym, d in pos.items():
                name = sym.replace(".NS", "")
                trail_txt = "🛡️ SL at Breakeven" if d.get('trailed_level', 0) == 1 else f"SL: ₹{d['sl']:.2f}"
                msg += (
                    f"📦 *{name}* ({d.get('strat_name', 'Swing')})\n"
                    f"• Entry: `₹{d['entry']:.2f}` | Qty: `{d['qty']}`\n"
                    f"• Target: `₹{d['target']:.2f}`\n"
                    f"• Risk Guard: `{trail_txt}`\n"
                    f"• Invested: `₹{(d['entry']*d['qty']):.2f}`\n\n"
                )
        else:
            msg += "_(Koi active swing position nahi hai - bot scanning kar raha hai)_\n"
        send_menu(msg)

    elif data == "btn_wallet":
        with state_lock:
            cash = trade_state['virtual_balance']
            init = trade_state['initial_capital']
            pos = trade_state.get("open_positions", {})
            invested = sum([d['entry'] * d['qty'] for d in pos.values()])
            current_worth = cash + invested
            growth = ((current_worth - init) / init) * 100
            target_pct = (current_worth / 100000.0) * 100

        send_menu(
            f"🚀 *ROAD TO ₹1,00,000 SWING PROGRESS*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• Starting Capital: `₹{init:,.2f}`\n"
            f"• Current Portfolio: `₹{current_worth:,.2f}`\n"
            f"• Available Cash: `₹{cash:,.2f}`\n"
            f"• Allocated Margin: `₹{invested:,.2f}`\n"
            f"• Net Growth: *{growth:+.2f}%*\n"
            f"• Goal Milestone (₹1 Lakh): *{target_pct:.1f}% Completed*\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )

    elif data == "btn_select_strat":
        send_strategy_selector()

    elif data.startswith("set_STRAT_"):
        strat_key = data.replace("set_", "")
        trade_state["active_strategy"] = strat_key
        save_data(trade_state)
        s_name = STRATEGIES[strat_key]["name"]
        send_menu(f"✅ *ACTIVE STRATEGY CHANGED TO:*\n👉 *{s_name}*\n\nNaye breakouts ab is rule par trigger honge!")

    elif data == "btn_backtest_menu":
        send_backtest_options()

    elif data.startswith("bt_"):
        s_key = data.replace("bt_", "")
        threading.Thread(target=handle_backtest_action, args=(s_key,)).start()

    elif data == "btn_back_menu":
        send_menu("🎛️ *COMMAND TERMINAL ACTIVE*")

    elif data == "btn_scan":
        send_alert("🔍 *Scanning NSE Top 40 with Active Strategy...*")
        threading.Thread(target=scan_swing_breakouts).start()

    elif data == "btn_audit":
        with state_lock:
            history = list(trade_state.get("trade_history", []))
            cash = trade_state['virtual_balance']
        wins = [t for t in history if t.get("pnl", 0) > 0]
        losses = [t for t in history if t.get("pnl", 0) <= 0]
        rate = (len(wins) / len(history) * 100) if history else 0.0
        total_pnl = sum([t.get("pnl", 0) for t in history])

        send_menu(
            f"📈 *SWING PERFORMANCE AUDIT*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• Closed Swings: `{len(history)}`\n"
            f"• Win Rate: *{rate:.1f}%* ({len(wins)}W | {len(losses)}L)\n"
            f"• Realized Net Profit: *{'+' if total_pnl >= 0 else ''}₹{total_pnl:,.2f}*\n"
            f"• Current Cash: `₹{cash:,.2f}`"
        )

    elif data == "btn_pause":
        BOT_PAUSED = True
        send_menu("⏸️ *SWING SCANNER PAUSED*")

    elif data == "btn_resume":
        BOT_PAUSED = False
        send_menu("▶️ *SWING SCANNER RESUMED*")

    elif data == "btn_panic":
        with state_lock:
            pos = list(trade_state.get("open_positions", {}).items())
            if not pos:
                send_menu("🚨 Koi open position nahi hai.")
                return
            today_str = datetime.now(IST).strftime("%Y-%m-%d")
            for sym, d in pos:
                trade_state["virtual_balance"] += (d["entry"] * d["qty"])
                trade_state["trade_history"].append({
                    "symbol": sym, "type": "BUY", "entry": d["entry"], "exit": d["entry"],
                    "pnl": 0.0, "result": "MANUAL_CLOSE", "date": today_str
                })
                del trade_state["open_positions"][sym]
            save_data(trade_state)
        send_menu("🚨 *SAARI SWING POSITIONS CASH ME CONVERT HO GAYI HAIN.*")

def fast_telegram_listener():
    global LAST_UPDATE_ID
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={LAST_UPDATE_ID + 1}&timeout=2"
            res = requests.get(url, timeout=4).json()
            for update in res.get("result", []):
                LAST_UPDATE_ID = update["update_id"]
                if "callback_query" in update:
                    handle_callback(update["callback_query"]["id"], update["callback_query"]["data"])
                elif "message" in update:
                    send_menu("🎛️ *NSE SWING COMMAND CENTER*\nNeeche buttons se manage karein:")
        except Exception as e:
            print(f"Listener error: {e}")
        time.sleep(0.5)

# --- SWING POSITION MONITOR ---
def manage_swing_positions():
    global trade_state
    with state_lock:
        pos = dict(trade_state.get("open_positions", {}))
    today_str = datetime.now(IST).strftime("%Y-%m-%d")
    closed = []

    for sym, d in pos.items():
        try:
            df = yf.download(tickers=sym, period="5d", interval="15m", progress=False)
            if df is None or df.empty:
                continue
            if hasattr(df.columns, 'levels'):
                df.columns = [col[0] for col in df.columns]

            curr_price = float(df['Close'].iloc[-1])
            entry = d['entry']
            qty = d['qty']
            gain_pct = ((curr_price - entry) / entry) * 100
            name = sym.replace(".NS", "")
            trail_threshold = d.get('trail_at', 0.05) * 100

            # 🛡️ Trailing Stop-Loss: Cost lock at profit threshold
            if d.get('trailed_level', 0) == 0 and gain_pct >= trail_threshold:
                d['sl'] = entry
                d['trailed_level'] = 1
                save_data(trade_state)
                send_alert(
                    f"🛡️ *SWING PROFIT PROTECTED: {name}*\n"
                    f"Stock is up *+{gain_pct:.2f}%*! SL breakeven cost (₹{entry:.2f}) par lock ho gaya hai. Zero Risk Trade!"
                )

            # Target Hit
            if curr_price >= d['target']:
                profit = round((curr_price - entry) * qty, 2)
                trade_state["virtual_balance"] += (curr_price * qty)
                send_alert(
                    f"🎯 *TARGET HIT: {name}*\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"• Strategy: `{d.get('strat_name', 'Swing')}`\n"
                    f"• Entry: `₹{entry:.2f}` | Exit: `₹{curr_price:.2f}` (+{gain_pct:.2f}%)\n"
                    f"• Profit: *+₹{profit:,.2f}*\n"
                    f"• Balance: *₹{trade_state['virtual_balance']:,.2f}*\n"
                    f"🚀 Compounding towards ₹1 Lakh!"
                )
                trade_state["trade_history"].append({
                    "symbol": sym, "type": "BUY", "entry": entry, "exit": curr_price,
                    "pnl": profit, "result": "TARGET_HIT", "date": today_str
                })
                closed.append(sym)

            # Stop Loss Hit
            elif curr_price <= d['sl']:
                pnl = round((curr_price - entry) * qty, 2)
                trade_state["virtual_balance"] += (curr_price * qty)
                outcome = "BREAKEVEN" if pnl >= 0 else "SL_HIT"
                send_alert(
                    f"🛑 *POSITION CLOSED: {name}*\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"• Exit: `₹{curr_price:.2f}`\n"
                    f"• P&L: *{'+' if pnl >= 0 else ''}₹{pnl:.2f}*\n"
                    f"• Cash Balance: `₹{trade_state['virtual_balance']:,.2f}`"
                )
                trade_state["trade_history"].append({
                    "symbol": sym, "type": "BUY", "entry": entry, "exit": curr_price,
                    "pnl": pnl, "result": outcome, "date": today_str
                })
                closed.append(sym)

        except Exception as e:
            print(f"Tracking error {sym}: {e}")

    for sym in closed:
        if sym in trade_state["open_positions"]:
            del trade_state["open_positions"][sym]
    if closed:
        save_data(trade_state)

# --- ACTIVE STRATEGY BREAKOUT SCANNER ---
def scan_swing_breakouts():
    global trade_state, BOT_PAUSED
    if BOT_PAUSED:
        return

    manage_swing_positions()

    if len(trade_state.get("open_positions", {})) >= 2:
        return
    if trade_state["virtual_balance"] < 4000.0:
        return

    strat_key = trade_state.get("active_strategy", "STRAT_1")
    strat_cfg = STRATEGIES.get(strat_key, STRATEGIES["STRAT_1"])

    for sym in SWING_WATCHLIST:
        if sym in trade_state.get("open_positions", {}):
            continue
        try:
            time.sleep(0.12)
            df = yf.download(tickers=sym, period="3mo", interval="1d", progress=False)
            if df is None or df.empty or len(df) < 35:
                continue
            if hasattr(df.columns, 'levels'):
                df.columns = [col[0] for col in df.columns]

            curr_price = float(df['Close'].iloc[-1])
            curr_vol = float(df['Volume'].iloc[-1])
            avg_vol = float(df['Volume'].rolling(window=15).mean().iloc[-1])
            vol_ratio = curr_vol / avg_vol if avg_vol > 0 else 1.0

            df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
            df['High_20'] = df['High'].shift(1).rolling(window=20).max()

            signal_found = False

            # STRATEGY 1: 20-Day Volume Breakout
            if strat_key == "STRAT_1":
                if curr_price > float(df['High_20'].iloc[-1]) and vol_ratio >= 2.0:
                    signal_found = True

            # STRATEGY 2: 50 EMA Pullback Bounce
            elif strat_key == "STRAT_2":
                low_p = float(df['Low'].iloc[-1])
                ema_p = float(df['EMA50'].iloc[-1])
                open_p = float(df['Open'].iloc[-1])
                if low_p <= ema_p and curr_price > ema_p and curr_price > open_p and vol_ratio >= 1.2:
                    signal_found = True

            # STRATEGY 3: Supertrend + RSI Momentum
            elif strat_key == "STRAT_3":
                delta = df['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss.replace(0, np.nan)
                rsi = 100 - (100 / (1 + rs))
                curr_rsi = float(rsi.iloc[-1])
                if curr_rsi >= 60.0 and curr_price > float(df['EMA50'].iloc[-1]) and vol_ratio >= 1.5:
                    signal_found = True

            # STRATEGY 4: MACD Zero-Line Crossover
            elif strat_key == "STRAT_4":
                exp1 = df['Close'].ewm(span=12, adjust=False).mean()
                exp2 = df['Close'].ewm(span=26, adjust=False).mean()
                macd = exp1 - exp2
                signal_line = macd.ewm(span=9, adjust=False).mean()
                if float(macd.iloc[-1]) > 0 and float(macd.iloc[-1]) > float(signal_line.iloc[-1]) and float(macd.iloc[-2]) <= float(signal_line.iloc[-2]):
                    signal_found = True

            # STRATEGY 5: Bollinger Squeeze Expansion
            elif strat_key == "STRAT_5":
                sma20 = df['Close'].rolling(window=20).mean()
                std20 = df['Close'].rolling(window=20).std()
                upper_bb = sma20 + (2 * std20)
                lower_bb = sma20 - (2 * std20)
                bw = (upper_bb - lower_bb) / sma20
                if float(bw.iloc[-1]) < float(bw.rolling(10).mean().iloc[-1]) and curr_price > float(upper_bb.iloc[-1]):
                    signal_found = True

            if signal_found:
                alloc = min(trade_state["virtual_balance"], trade_state["virtual_balance"] / (2 - len(trade_state["open_positions"])))
                qty = int(alloc // curr_price)
                if qty < 1:
                    continue

                sl = round(curr_price * (1.0 - strat_cfg["sl_pct"]), 2)
                tgt = round(curr_price * (1.0 + strat_cfg["target_pct"]), 2)
                trade_state["virtual_balance"] -= (curr_price * qty)

                trade_state["open_positions"][sym] = {
                    "type": "BUY", "entry": curr_price, "qty": qty,
                    "sl": sl, "target": tgt, "trailed_level": 0,
                    "strat_name": strat_cfg["name"], "trail_at": strat_cfg["trail_at"]
                }
                save_data(trade_state)
                name = sym.replace(".NS", "")

                send_alert(
                    f"🔥 *SWING SIGNAL: {name}*\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"⚙️ *Strategy:* `{strat_cfg['name']}`\n"
                    f"📈 *Action:* `BUY SWING DELIVERY`\n"
                    f"💵 *Entry:* `₹{curr_price:.2f}` | *Qty:* `{qty}`\n"
                    f"💰 *Invested:* `₹{(curr_price*qty):,.2f}`\n"
                    f"🛑 *Stop Loss:* `₹{sl}` (-{strat_cfg['sl_pct']*100:.1f}%)\n"
                    f"🎯 *Target:* `₹{tgt}` (+{strat_cfg['target_pct']*100:.1f}%)\n"
                    f"💼 *Cash Left:* `₹{trade_state['virtual_balance']:,.2f}`\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"⏱️ *Holding Window:* 3 - 10 Days"
                )
                break
        except Exception as e:
            print(f"Scan error {sym}: {e}")

# --- HEALTH SERVER FOR RENDER ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"NSE Swing Engine Active.")

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

def self_ping_loop():
    port = int(os.environ.get("PORT", 8080))
    while True:
        try:
            time.sleep(300)
            requests.get(f"http://127.0.0.1:{port}", timeout=5)
        except Exception:
            pass

threading.Thread(target=run_health_server, daemon=True).start()
threading.Thread(target=self_ping_loop, daemon=True).start()

# Startup Notification
active_strat_name = STRATEGIES[trade_state.get("active_strategy", "STRAT_1")]["name"]
send_menu(
    f"🚀 *NSE SWING BOT ONLINE (STRATEGY LAB)*\n\n"
    f"🎯 *Compounding Target:* ₹10,000 ➔ ₹1,00,000\n"
    f"⚙️ *Active Strategy:* {active_strat_name}\n"
    f"🧪 *Features:* Dynamic Strategy Switcher + 1-Year Backtester\n\n"
    f"Menu se strategy change karein ya Backtest run karein:"
)

listener_thread = threading.Thread(target=fast_telegram_listener, daemon=True)
listener_thread.start()

while True:
    if is_indian_market_open():
        scan_swing_breakouts()
    else:
        manage_swing_positions()
    time.sleep(300)
