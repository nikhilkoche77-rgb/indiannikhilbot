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
        print(f"Telegram alert error: {e}")
        return None

def is_indian_market_open():
    now = datetime.now(IST)
    if now.weekday() >= 5:
        return False
    market_start = now.replace(hour=9, minute=15, second=0, microsecond=0)
    market_end = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return market_start <= now <= market_end

# --- 7 HIGH WIN-RATE SWING STRATEGIES WITH EXPANDED RRR ---
STRATEGIES = {
    "STRAT_1": {
        "name": "1. 20 EMA Pullback Bounce",
        "tag": "Trend Continuation",
        "desc": "Bullish rejection candle at 20 EMA while trading above 50 & 200 EMA",
        "rrr": "1:2.5", "sl_pct": 0.030, "target_pct": 0.075, "trail_at": 0.040
    },
    "STRAT_2": {
        "name": "2. Positional ORB with Volume",
        "tag": "Institutional Surge",
        "desc": "5-10 Day Range Breakout backed by heavy institutional volume (>2x)",
        "rrr": "1:3.0", "sl_pct": 0.035, "target_pct": 0.105, "trail_at": 0.045
    },
    "STRAT_3": {
        "name": "3. Support / Resistance Flip",
        "tag": "Role Reversal Retest",
        "desc": "Past multi-week resistance breached and successfully tested as new floor",
        "rrr": "1:3.0", "sl_pct": 0.030, "target_pct": 0.090, "trail_at": 0.040
    },
    "STRAT_4": {
        "name": "4. VCP (Minervini Style)",
        "tag": "Volatility Contraction",
        "desc": "Successive contracting waves followed by explosive volume expansion",
        "rrr": "1:4.0", "sl_pct": 0.035, "target_pct": 0.140, "trail_at": 0.050
    },
    "STRAT_5": {
        "name": "5. Bollinger Band Squeeze",
        "tag": "Volatility Explosion",
        "desc": "Extreme band constriction followed by high volume upper band breach",
        "rrr": "1:2.5", "sl_pct": 0.032, "target_pct": 0.080, "trail_at": 0.040
    },
    "STRAT_6": {
        "name": "6. MACD Zero-Line Momentum",
        "tag": "Momentum Shift",
        "desc": "Histogram positive shift while price breaks horizontal resistance",
        "rrr": "1:2.0", "sl_pct": 0.030, "target_pct": 0.060, "trail_at": 0.035
    },
    "STRAT_7": {
        "name": "7. ORB with Relative Strength",
        "tag": "Alpha Outperformer",
        "desc": "Multi-day high breakout in stocks strongly outperforming Nifty 50",
        "rrr": "1:3.5", "sl_pct": 0.035, "target_pct": 0.122, "trail_at": 0.050
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
                if "active_strategy" not in saved or saved["active_strategy"] not in STRATEGIES:
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

# 🎯 TOP SWING BASKET + BENCHMARK INDICES
SWING_WATCHLIST = [
    "TATASTEEL.NS", "BEL.NS", "BHEL.NS", "SAIL.NS", "NATIONALUM.NS", "NMDC.NS",
    "PFC.NS", "RECLTD.NS", "COALINDIA.NS", "HINDALCO.NS", "VEDL.NS", "ONGC.NS",
    "IRFC.NS", "RVNL.NS", "SUZLON.NS", "ZOMATO.NS", "PNB.NS", "BANKBARODA.NS",
    "CANBK.NS", "ASHOKLEY.NS", "FEDERALBNK.NS", "IOC.NS", "POWERGRID.NS", "NTPC.NS",
    "IREDA.NS", "HUDCO.NS", "HAL.NS", "BDL.NS", "EXIDEIND.NS", "MOTHERSON.NS",
    "JINDALSTEL.NS", "JSWSTEEL.NS", "BHARTIARTL.NS", "ADANIENT.NS", "ADANIPOWER.NS",
    "TATAPOWER.NS", "INOXWIND.NS", "TITAGARH.NS", "MAZDOCK.NS", "COCHINSHIP.NS"
]

BENCHMARK_INDICES = {
    "^NSEI": "NIFTY 50",
    "^NSEBANK": "BANK NIFTY"
}

# --- UI MENUS ---
def send_menu(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    active_strat = STRATEGIES.get(trade_state.get("active_strategy", "STRAT_1"), {})["name"]
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "📊 Open Positions", "callback_data": "btn_positions"},
                {"text": "💰 10K➔100K Journey", "callback_data": "btn_wallet"}
            ],
            [
                {"text": f"⚙️ Strategy: {active_strat}", "callback_data": "btn_select_strat"}
            ],
            [
                {"text": "🧪 Backtest (Stocks & Indices)", "callback_data": "btn_backtest_menu"},
                {"text": "🔄 Scan Now", "callback_data": "btn_scan"}
            ],
            [
                {"text": "📈 Performance Audit", "callback_data": "btn_audit"},
                {"text": "🚨 Close All", "callback_data": "btn_panic"}
            ],
            [
                {"text": "⏸️ Pause", "callback_data": "btn_pause"},
                {"text": "▶️ Resume", "callback_data": "btn_resume"}
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
        buttons.append([{"text": f"{tick}{v['name']} ({v['rrr']})", "callback_data": f"set_{k}"}])
    buttons.append([{"text": "⬅️ Back to Menu", "callback_data": "btn_back_menu"}])
    keyboard = {"inline_keyboard": buttons}
    msg = (
        "⚙️ *SELECT ACTIVE SWING STRATEGY*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Aap jis strategy par bot ko trades lene dena chahte hain, select karein:\n"
    )
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown", "reply_markup": json.dumps(keyboard)}
    requests.post(url, data=payload, timeout=5)

def send_backtest_options():
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    buttons = [
        [{"text": "🏆 Comprehensive Audit (All 7 on Top Stocks)", "callback_data": "bt_ALL"}],
        [{"text": "📈 Test NIFTY 50 Index", "callback_data": "bt_idx_NIFTY"}, {"text": "🏦 Test BANK NIFTY Index", "callback_data": "bt_idx_BANKNIFTY"}],
        [{"text": "1. 20 EMA Pullback", "callback_data": "bt_STRAT_1"}, {"text": "2. Positional ORB", "callback_data": "bt_STRAT_2"}],
        [{"text": "3. S/R Flip Retest", "callback_data": "bt_STRAT_3"}, {"text": "4. VCP Pattern", "callback_data": "bt_STRAT_4"}],
        [{"text": "5. BB Squeeze Break", "callback_data": "bt_STRAT_5"}, {"text": "6. MACD Shift", "callback_data": "bt_STRAT_6"}],
        [{"text": "7. Relative Strength ORB", "callback_data": "bt_STRAT_7"}],
        [{"text": "⬅️ Back to Menu", "callback_data": "btn_back_menu"}]
    ]
    keyboard = {"inline_keyboard": buttons}
    msg = (
        "🧪 *MULTI-ASSET HISTORICAL BACKTEST ENGINE*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "1-Year Real Daily Candle Data par Win Rate %, Max Drawdown, aur Net Profit audit karein:"
    )
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown", "reply_markup": json.dumps(keyboard)}
    requests.post(url, data=payload, timeout=5)

# --- TECHNICAL STRATEGY EVALUATION ---
def evaluate_strategy(df, strat_key, nifty_df=None):
    if len(df) < 65:
        return False, ""

    c = float(df['Close'].iloc[-1])
    o = float(df['Open'].iloc[-1])
    h = float(df['High'].iloc[-1])
    l = float(df['Low'].iloc[-1])
    v = float(df['Volume'].iloc[-1])
    v_avg10 = float(df['Volume'].rolling(10).mean().iloc[-1])
    vol_ratio = v / v_avg10 if v_avg10 > 0 else 1.0

    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['EMA200'] = df['Close'].ewm(span=200, adjust=False).mean()

    # 1. The 20 EMA Pullback Strategy (Uptrend wave)
    if strat_key == "STRAT_1":
        ema20 = float(df['EMA20'].iloc[-1])
        ema50 = float(df['EMA50'].iloc[-1])
        ema200 = float(df['EMA200'].iloc[-1])
        if ema20 > ema50 > ema200 and l <= ema20 * 1.012 and c > ema20 and c > o:
            return True, f"Uptrend bounce: Green rejection bar at 20 EMA (₹{ema20:.1f}) above 50/200 EMA"

    # 2. Opening Range Breakout (ORB) with Volume (5-10 Days)
    elif strat_key == "STRAT_2":
        high_10 = float(df['High'].shift(1).rolling(10).max().iloc[-1])
        if c > high_10 and vol_ratio >= 2.0:
            return True, f"10-Day Resistance (₹{high_10:.1f}) breached with {vol_ratio:.1f}x Institutional Volume"

    # 3. Support / Resistance Flip (SR Flip / Role Reversal)
    elif strat_key == "STRAT_3":
        past_res = float(df['High'].shift(3).rolling(20).max().iloc[-1])
        prev_close = float(df['Close'].iloc[-2])
        if prev_close >= past_res and l <= past_res * 1.01 and c > past_res and c > o:
            return True, f"S/R Flip Retest: Prior resistance (₹{past_res:.1f}) tested successfully as fresh support"

    # 4. The VCP (Volatility Contraction Pattern - Minervini)
    elif strat_key == "STRAT_4":
        range_now = float((df['High'] - df['Low']).rolling(4).mean().iloc[-1])
        range_past = float((df['High'] - df['Low']).rolling(20).mean().iloc[-1])
        high_15 = float(df['High'].shift(1).rolling(15).max().iloc[-1])
        if range_now < (0.60 * range_past) and c > high_15 and vol_ratio >= 1.7:
            return True, f"VCP Breakout: Volatility compressed 40%+ into tight contraction with volume surge"

    # 5. Bollinger Band Squeeze Breakout
    elif strat_key == "STRAT_5":
        sma20 = df['Close'].rolling(20).mean()
        std20 = df['Close'].rolling(20).std()
        upper_bb = sma20 + (2 * std20)
        lower_bb = sma20 - (2 * std20)
        bw = (upper_bb - lower_bb) / sma20
        bw_now = float(bw.iloc[-1])
        bw_avg = float(bw.rolling(20).mean().iloc[-1])
        if bw_now < bw_avg * 0.80 and c > float(upper_bb.iloc[-1]) and vol_ratio >= 1.6:
            return True, f"Bollinger Squeeze Release: Upper band (₹{float(upper_bb.iloc[-1]):.1f}) blown out with expansion"

    # 6. MACD Zero-Line / Histogram Momentum Shift
    elif strat_key == "STRAT_6":
        exp1 = df['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df['Close'].ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        sig = macd.ewm(span=9, adjust=False).mean()
        hist = macd - sig
        high_5 = float(df['High'].shift(1).rolling(5).max().iloc[-1])
        if float(hist.iloc[-2]) < 0 and float(hist.iloc[-1]) > 0 and c > high_5:
            return True, f"MACD Histogram flipped positive (+{float(hist.iloc[-1]):.2f}) confirming fresh wave"

    # 7. ORB with Relative Strength (vs NIFTY 50)
    elif strat_key == "STRAT_7":
        high_5 = float(df['High'].shift(1).rolling(5).max().iloc[-1])
        if nifty_df is not None and len(nifty_df) >= 5:
            stock_5d_ret = ((c - float(df['Close'].iloc[-5])) / float(df['Close'].iloc[-5])) * 100
            nifty_5d_ret = ((float(nifty_df['Close'].iloc[-1]) - float(nifty_df['Close'].iloc[-5])) / float(nifty_df['Close'].iloc[-5])) * 100
            is_outperforming = stock_5d_ret > (nifty_5d_ret + 2.0)
        else:
            is_outperforming = True
        
        if c > high_5 and is_outperforming and vol_ratio >= 1.5:
            return True, f"Alpha Breakout: Stock at 5-Day High while significantly outperforming Nifty 50"

    return False, ""

# --- HISTORICAL BACKTEST ENGINE ---
def run_backtest_simulation(strat_key, ticker_list):
    strat = STRATEGIES[strat_key]
    target = strat["target_pct"]
    sl = strat["sl_pct"]
    total_trades, wins, losses = 0, 0, 0
    total_yield = 0.0

    # Fetch Nifty data for relative strength reference
    nifty_df = None
    if strat_key == "STRAT_7":
        try:
            nifty_df = yf.download(tickers="^NSEI", period="1y", interval="1d", progress=False)
            if hasattr(nifty_df.columns, 'levels'):
                nifty_df.columns = [col[0] for col in nifty_df.columns]
        except Exception:
            pass

    for sym in ticker_list:
        try:
            df = yf.download(tickers=sym, period="1y", interval="1d", progress=False)
            if df is None or df.empty or len(df) < 70:
                continue
            if hasattr(df.columns, 'levels'):
                df.columns = [col[0] for col in df.columns]

            in_pos = False
            entry_p = 0.0

            for i in range(50, len(df)):
                sub_df = df.iloc[:i+1]
                c = float(sub_df['Close'].iloc[-1])

                if in_pos:
                    pnl_pct = (c - entry_p) / entry_p
                    if pnl_pct >= target:
                        wins += 1
                        total_trades += 1
                        total_yield += target
                        in_pos = False
                    elif pnl_pct <= -sl:
                        losses += 1
                        total_trades += 1
                        total_yield -= sl
                        in_pos = False
                    continue

                nifty_sub = nifty_df.iloc[:i+1] if nifty_df is not None and len(nifty_df) >= i+1 else None
                sig, _ = evaluate_strategy(sub_df, strat_key, nifty_sub)
                if sig:
                    in_pos = True
                    entry_p = c
        except Exception:
            pass

    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0
    return {
        "strat": strat["name"],
        "rrr": strat["rrr"],
        "trades": total_trades,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "yield": total_yield * 100
    }

def handle_backtest_action(action_key):
    if action_key == "ALL":
        send_alert("⏳ *Running 1-Year Backtest for All 7 Strategies across Top 12 NSE Leaders...*")
        sample_basket = SWING_WATCHLIST[:12]
        results = [run_backtest_simulation(k, sample_basket) for k in STRATEGIES.keys()]

        msg = "🏆 *1-YEAR HISTORICAL SWING AUDIT REPORT*\n━━━━━━━━━━━━━━━━━━━━\n"
        for r in results:
            msg += (
                f"📌 *{r['strat']}* (RRR `{r['rrr']}`)\n"
                f"• Win Rate: *{r['win_rate']:.1f}%* ({r['wins']}W | {r['losses']}L)\n"
                f"• Total Trades: `{r['trades']}` | Net Alpha: *{r['yield']:+.1f}%*\n\n"
            )
        msg += "━━━━━━━━━━━━━━━━━━━━\n💡 Switch strategy via '⚙️ Strategy' menu anytime!"
        send_menu(msg)

    elif action_key.startswith("idx_"):
        idx_sym = "^NSEI" if "NIFTY" in action_key and "BANK" not in action_key else "^NSEBANK"
        idx_name = "NIFTY 50" if idx_sym == "^NSEI" else "BANK NIFTY"
        send_alert(f"⏳ *Testing all strategies on `{idx_name}` 1-Year Daily Data...*")
        
        msg = f"📊 *{idx_name} HISTORICAL AUDIT REPORT*\n━━━━━━━━━━━━━━━━━━━━\n"
        for k in STRATEGIES.keys():
            r = run_backtest_simulation(k, [idx_sym])
            msg += (
                f"• *{r['strat']}*: *{r['win_rate']:.1f}% Win* "
                f"({r['wins']}W/{r['losses']}L) | Net: `{r['yield']:+.1f}%`\n"
            )
        msg += "━━━━━━━━━━━━━━━━━━━━"
        send_menu(msg)

    else:
        strat_name = STRATEGIES[action_key]["name"]
        send_alert(f"⏳ *Auditing `{strat_name}` against 1-Year Daily historical records...*")
        r = run_backtest_simulation(action_key, SWING_WATCHLIST[:12])
        target_pct = STRATEGIES[action_key]["target_pct"] * 100
        sl_pct = STRATEGIES[action_key]["sl_pct"] * 100
        msg = (
            f"🧪 *STRATEGY AUDIT: {r['strat']}*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 Risk-Reward Ratio: *{r['rrr']}*\n"
            f"🔥 Historical Win Rate: *{r['win_rate']:.1f}%*\n"
            f"📦 Simulated Trades: `{r['trades']}`\n"
            f"✅ Target Hits (+{target_pct:.1f}%): `{r['wins']}`\n"
            f"❌ Stop-Loss Hits (-{sl_pct:.1f}%): `{r['losses']}`\n"
            f"📈 Cumulative Compounded Return: *{r['yield']:+.1f}%*\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
        send_menu(msg)

# --- TELEGRAM CALLBACK HANDLER ---
def handle_callback(query_id, data):
    global trade_state, BOT_PAUSED
    requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery", data={"callback_query_id": query_id})

    if data == "btn_positions":
        with state_lock:
            pos = trade_state.get("open_positions", {})
        msg = "📊 *ACTIVE SWING POSITIONS*\n━━━━━━━━━━━━━━━━━━━━\n"
        if pos:
            for sym, d in pos.items():
                name = sym.replace(".NS", "")
                trail_txt = "🛡️ Breakeven (0 Risk)" if d.get('trailed_level', 0) == 1 else f"SL: ₹{d['sl']:.2f}"
                msg += (
                    f"📦 *{name}*\n"
                    f"• Strategy: *{d.get('strat_name', 'Swing')}* ({d.get('rrr', '1:3')})\n"
                    f"• Rationale: _{d.get('reason', 'N/A')}_\n"
                    f"• Entry: `₹{d['entry']:.2f}` | Qty: `{d['qty']}`\n"
                    f"• Target: `₹{d['target']:.2f}` | Guard: `{trail_txt}`\n"
                    f"• Allocation: `₹{(d['entry']*d['qty']):.2f}`\n\n"
                )
        else:
            msg += "_(Koi active swing trade nahi hai - bot scanning kar raha hai)_\n"
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
            f"🚀 *₹10,000 ➔ ₹1,00,000 COMPOUNDING AUDIT*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• Initial Pool: `₹{init:,.2f}`\n"
            f"• Net Portfolio Worth: `₹{current_worth:,.2f}`\n"
            f"• Liquid Cash: `₹{cash:,.2f}`\n"
            f"• In-Trade Margin: `₹{invested:,.2f}`\n"
            f"• Total ROI: *{growth:+.2f}%*\n"
            f"• Journey Completed: *{target_pct:.1f}%* towards ₹1 Lakh\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )

    elif data == "btn_select_strat":
        send_strategy_selector()

    elif data.startswith("set_STRAT_"):
        strat_key = data.replace("set_", "")
        trade_state["active_strategy"] = strat_key
        save_data(trade_state)
        s_name = STRATEGIES[strat_key]["name"]
        send_menu(f"✅ *ACTIVE STRATEGY ACTIVATED:*\n👉 *{s_name}*\n\nAb agle trades is setup ke strict parameters par liye jayenge!")

    elif data == "btn_backtest_menu":
        send_backtest_options()

    elif data.startswith("bt_"):
        s_key = data.replace("bt_", "")
        threading.Thread(target=handle_backtest_action, args=(s_key,)).start()

    elif data == "btn_back_menu":
        send_menu("🎛️ *COMMAND TERMINAL ACTIVE*")

    elif data == "btn_scan":
        send_alert("🔍 *Running Manual Scan Across 40 NSE Leaders...*")
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
            f"📈 *CLOSED SWING PERFORMANCE*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• Total Closed: `{len(history)}`\n"
            f"• Win Rate: *{rate:.1f}%* ({len(wins)}W | {len(losses)}L)\n"
            f"• Realized Net Profit: *{'+' if total_pnl >= 0 else ''}₹{total_pnl:,.2f}*\n"
            f"• Available Liquid Capital: `₹{cash:,.2f}`"
        )

    elif data == "btn_pause":
        BOT_PAUSED = True
        send_menu("⏸️ *SCANNER PAUSED*")

    elif data == "btn_resume":
        BOT_PAUSED = False
        send_menu("▶️ *SCANNER RESUMED*")

    elif data == "btn_panic":
        with state_lock:
            pos = list(trade_state.get("open_positions", {}).items())
            if not pos:
                send_menu("🚨 Koi open position nahi mili.")
                return
            today_str = datetime.now(IST).strftime("%Y-%m-%d")
            for sym, d in pos:
                trade_state["virtual_balance"] += (d["entry"] * d["qty"])
                trade_state["trade_history"].append({
                    "symbol": sym, "type": "BUY", "entry": d["entry"], "exit": d["entry"],
                    "pnl": 0.0, "result": "MANUAL_EXIT", "date": today_str, "strat_name": d.get("strat_name", "Swing")
                })
                del trade_state["open_positions"][sym]
            save_data(trade_state)
        send_menu("🚨 *ALL SWING POSITIONS EXITED TO CASH.*")

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
                    send_menu("🎛️ *COMMAND TERMINAL ACTIVE*\nButtons se bot operate karein:")
        except Exception as e:
            print(f"Listener error: {e}")
        time.sleep(0.5)

# --- POSITION MONITORING WITH MULTI-STAGE TRAILING ---
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
            trail_pct = d.get('trail_at', 0.04) * 100

            # 🛡️ Step 1: Trailing to Breakeven (Zero Risk)
            if d.get('trailed_level', 0) == 0 and gain_pct >= trail_pct:
                d['sl'] = entry
                d['trailed_level'] = 1
                save_data(trade_state)
                send_alert(
                    f"🛡️ *RISK ELIMINATED: {name}*\n"
                    f"Move: *+{gain_pct:.2f}%*! SL breakeven cost (₹{entry:.2f}) par lock ho gaya hai. Trade is now 100% Risk-Free!"
                )

            # 🎯 Target Hit (Full RRR Achieved)
            if curr_price >= d['target']:
                profit = round((curr_price - entry) * qty, 2)
                trade_state["virtual_balance"] += (curr_price * qty)
                send_alert(
                    f"🎯 *TARGET HIT: {name}*\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"📌 *Strategy:* `{d.get('strat_name', 'Swing')}` ({d.get('rrr', '1:3')})\n"
                    f"💵 *Entry:* `₹{entry:.2f}` | *Exit:* `₹{curr_price:.2f}` (+{gain_pct:.2f}%)\n"
                    f"💰 *Net Profit Booked:* *+₹{profit:,.2f}*\n"
                    f"💼 *Compounded Balance:* *₹{trade_state['virtual_balance']:,.2f}*\n"
                    f"🚀 Step closer to ₹1,00,000 Milestone!"
                )
                trade_state["trade_history"].append({
                    "symbol": sym, "type": "BUY", "entry": entry, "exit": curr_price,
                    "pnl": profit, "result": "WIN", "date": today_str, "strat_name": d.get("strat_name", "Swing")
                })
                closed.append(sym)

            # 🛑 Stop Loss Hit
            elif curr_price <= d['sl']:
                pnl = round((curr_price - entry) * qty, 2)
                trade_state["virtual_balance"] += (curr_price * qty)
                outcome = "BREAKEVEN" if pnl >= 0 else "LOSS"
                send_alert(
                    f"🛑 *POSITION CLOSED: {name}*\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"📌 *Strategy:* `{d.get('strat_name', 'Swing')}`\n"
                    f"💵 *Exit:* `₹{curr_price:.2f}`\n"
                    f"💰 *P&L:* *{'+' if pnl >= 0 else ''}₹{pnl:.2f}*\n"
                    f"💼 *Liquid Balance:* `₹{trade_state['virtual_balance']:,.2f}`"
                )
                trade_state["trade_history"].append({
                    "symbol": sym, "type": "BUY", "entry": entry, "exit": curr_price,
                    "pnl": pnl, "result": outcome, "date": today_str, "strat_name": d.get("strat_name", "Swing")
                })
                closed.append(sym)

        except Exception as e:
            print(f"Tracking error {sym}: {e}")

    for sym in closed:
        if sym in trade_state["open_positions"]:
            del trade_state["open_positions"][sym]
    if closed:
        save_data(trade_state)

# --- BREAKOUT SCANNER ---
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

    nifty_df = None
    if strat_key == "STRAT_7":
        try:
            nifty_df = yf.download(tickers="^NSEI", period="1mo", interval="1d", progress=False)
            if hasattr(nifty_df.columns, 'levels'):
                nifty_df.columns = [col[0] for col in nifty_df.columns]
        except Exception:
            pass

    for sym in SWING_WATCHLIST:
        if sym in trade_state.get("open_positions", {}):
            continue
        try:
            time.sleep(0.12)
            df = yf.download(tickers=sym, period="3mo", interval="1d", progress=False)
            if df is None or df.empty or len(df) < 55:
                continue
            if hasattr(df.columns, 'levels'):
                df.columns = [col[0] for col in df.columns]

            is_signal, reason_desc = evaluate_strategy(df, strat_key, nifty_df)

            if is_signal:
                curr_price = float(df['Close'].iloc[-1])
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
                    "strat_name": strat_cfg["name"],
                    "reason": reason_desc,
                    "rrr": strat_cfg["rrr"],
                    "trail_at": strat_cfg["trail_at"]
                }
                save_data(trade_state)
                name = sym.replace(".NS", "")

                send_alert(
                    f"🔥 *SWING BUY SIGNAL TRIGGERED: {name}*\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"📌 *Strategy:* `{strat_cfg['name']}`\n"
                    f"🎯 *Risk-Reward Ratio:* `{strat_cfg['rrr']}`\n"
                    f"💡 *Technical Reason:* _{reason_desc}_\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"💵 *Entry Price:* `₹{curr_price:.2f}`\n"
                    f"📦 *Position Size:* `{qty}` Shares\n"
                    f"💰 *Capital Invested:* `₹{(curr_price*qty):,.2f}`\n"
                    f"🛑 *Stop Loss:* `₹{sl}` (-{strat_cfg['sl_pct']*100:.1f}%)\n"
                    f"🎯 *Target:* `₹{tgt}` (+{strat_cfg['target_pct']*100:.1f}%)\n"
                    f"💼 *Cash Remaining:* `₹{trade_state['virtual_balance']:,.2f}`\n"
                    f"⏱️ *Holding Expectation:* 3 - 10 Days"
                )
                break
        except Exception as e:
            print(f"Scan error {sym}: {e}")

# --- HEALTH SERVER FOR RENDER KEEP-ALIVE ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"NSE Multi-Strategy Engine Active.")

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

# --- STARTUP NOTIFICATION ---
active_strat_name = STRATEGIES[trade_state.get("active_strategy", "STRAT_1")]["name"]
send_menu(
    f"🚀 *NSE TOP 7 SWING BOT ONLINE*\n\n"
    f"🎯 *Mission:* ₹10,000 ➔ ₹1,00,000 Compounding\n"
    f"⚙️ *Currently Active:* `{active_strat_name}`\n"
    f"📊 *RRR Setup:* Dynamic 1:2.0 to 1:4.0 Risk-to-Reward\n"
    f"🧪 *Coverage:* 40 NSE Momentum Stocks + NIFTY 50 + BANK NIFTY\n\n"
    f"Menu se strategy badlein ya Historical Backtest audit run karein:"
)

listener_thread = threading.Thread(target=fast_telegram_listener, daemon=True)
listener_thread.start()

while True:
    if is_indian_market_open():
        scan_swing_breakouts()
    else:
        manage_swing_positions()
    time.sleep(300)
