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

# --- COMPLETE 10 SWING STRATEGIES SUITE ---
STRATEGIES = {
    "STRAT_1": {
        "name": "1. 20/50 EMA Golden Cross",
        "tag": "EMA Ribbon Cross",
        "desc": "20 EMA crossing above 50 EMA with strong volume confirmation",
        "target_pct": 0.12, "sl_pct": 0.035, "trail_at": 0.05
    },
    "STRAT_2": {
        "name": "2. Pullback to 20 EMA",
        "tag": "Trend Continuation",
        "desc": "Stock in uptrend bounces off 20 EMA with bullish rejection candle",
        "target_pct": 0.10, "sl_pct": 0.030, "trail_at": 0.04
    },
    "STRAT_3": {
        "name": "3. Volume Breakout (Darvas Box)",
        "tag": "Institutional Box Break",
        "desc": "Multi-week consolidation breakout with 2.0x institutional volume",
        "target_pct": 0.14, "sl_pct": 0.035, "trail_at": 0.05
    },
    "STRAT_4": {
        "name": "4. Support & Resistance Bounce",
        "tag": "Demand Zone Bounce",
        "desc": "Key horizontal support test with strong bullish reversal candle",
        "target_pct": 0.11, "sl_pct": 0.030, "trail_at": 0.04
    },
    "STRAT_5": {
        "name": "5. RSI Bullish Divergence",
        "tag": "Hidden Momentum Reversal",
        "desc": "Price makes lower low while RSI forms higher low",
        "target_pct": 0.13, "sl_pct": 0.035, "trail_at": 0.05
    },
    "STRAT_6": {
        "name": "6. Daily High Breakout (ORB Swing)",
        "tag": "Multi-Day Momentum",
        "desc": "Breakout above 5-day highest high with volume expansion",
        "target_pct": 0.12, "sl_pct": 0.035, "trail_at": 0.05
    },
    "STRAT_7": {
        "name": "7. MACD Histogram Reversal",
        "tag": "Momentum Shift",
        "desc": "MACD Histogram turns positive while price clears consolidation",
        "target_pct": 0.11, "sl_pct": 0.030, "trail_at": 0.04
    },
    "STRAT_8": {
        "name": "8. VCP Pattern (Minervini Style)",
        "tag": "Volatility Contraction",
        "desc": "Price volatility contracts progressively before high volume blast",
        "target_pct": 0.15, "sl_pct": 0.040, "trail_at": 0.06
    },
    "STRAT_9": {
        "name": "9. Bollinger Squeeze Breakout",
        "tag": "Volatility Explosion",
        "desc": "Tight Bollinger Bandwidth expansion breaking upper band",
        "target_pct": 0.13, "sl_pct": 0.035, "trail_at": 0.05
    },
    "STRAT_10": {
        "name": "10. Gap-Up Continuation",
        "tag": "Unfilled Gap Run",
        "desc": "Bullish gap-up held firmly without fill, breaking day 1 high",
        "target_pct": 0.12, "sl_pct": 0.035, "trail_at": 0.05
    }
}

# --- STATE MANAGEMENT ---
def load_data():
    default_data = {
        "virtual_balance": 10000.00,
        "initial_capital": 10000.00,
        "active_strategy": "STRAT_3", # Default: Volume Breakout
        "open_positions": {},
        "trade_history": []
    }
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                saved = json.load(f)
                if "active_strategy" not in saved:
                    saved["active_strategy"] = "STRAT_3"
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

# 🎯 TOP HIGH-LIQUIDITY SWING BASKET (NSE)
SWING_WATCHLIST = [
    "TATASTEEL.NS", "BEL.NS", "BHEL.NS", "SAIL.NS", "NATIONALUM.NS", "NMDC.NS",
    "PFC.NS", "RECLTD.NS", "COALINDIA.NS", "HINDALCO.NS", "VEDL.NS", "ONGC.NS",
    "IRFC.NS", "RVNL.NS", "SUZLON.NS", "ZOMATO.NS", "PNB.NS", "BANKBARODA.NS",
    "CANBK.NS", "ASHOKLEY.NS", "FEDERALBNK.NS", "IOC.NS", "POWERGRID.NS", "NTPC.NS",
    "IREDA.NS", "HUDCO.NS", "HAL.NS", "BDL.NS", "EXIDEIND.NS", "MOTHERSON.NS",
    "JINDALSTEL.NS", "JSWSTEEL.NS", "BHARTIARTL.NS", "ADANIENT.NS", "ADANIPOWER.NS",
    "TATAPOWER.NS", "INOXWIND.NS", "TITAGARH.NS", "MAZDOCK.NS", "COCHINSHIP.NS"
]

# --- UI DISPLAY MENUS ---
def send_menu(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    active_strat = STRATEGIES.get(trade_state.get("active_strategy", "STRAT_3"), {})["name"]
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "📊 Open Positions", "callback_data": "btn_positions"},
                {"text": "💰 10K➔100K Wallet", "callback_data": "btn_wallet"}
            ],
            [
                {"text": f"⚙️ Strategy: {active_strat}", "callback_data": "btn_select_strat"}
            ],
            [
                {"text": "🧪 Backtest Strategies (Win %)", "callback_data": "btn_backtest_menu"},
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
    curr = trade_state.get("active_strategy", "STRAT_3")
    buttons = []
    # Display 10 strategies neatly in buttons
    for k, v in STRATEGIES.items():
        tick = "✅ " if k == curr else ""
        buttons.append([{"text": f"{tick}{v['name']}", "callback_data": f"set_{k}"}])
    buttons.append([{"text": "⬅️ Back to Menu", "callback_data": "btn_back_menu"}])
    
    keyboard = {"inline_keyboard": buttons}
    msg = (
        "⚙️ *SELECT ACTIVE SWING STRATEGY*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Jis strategy par bot ko trade lena hai, use select karein:\n"
    )
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown", "reply_markup": json.dumps(keyboard)}
    requests.post(url, data=payload, timeout=5)

def send_backtest_options():
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    buttons = [
        [{"text": "🏆 Run Comparative Audit (All 10 Strategies)", "callback_data": "bt_ALL"}],
        [{"text": "1. 20/50 EMA Cross", "callback_data": "bt_STRAT_1"}, {"text": "2. 20 EMA Pullback", "callback_data": "bt_STRAT_2"}],
        [{"text": "3. Volume Breakout", "callback_data": "bt_STRAT_3"}, {"text": "4. S&R Bounce", "callback_data": "bt_STRAT_4"}],
        [{"text": "5. RSI Divergence", "callback_data": "bt_STRAT_5"}, {"text": "6. High Breakout", "callback_data": "bt_STRAT_6"}],
        [{"text": "7. MACD Histogram", "callback_data": "bt_STRAT_7"}, {"text": "8. VCP Pattern", "callback_data": "bt_STRAT_8"}],
        [{"text": "9. BB Squeeze", "callback_data": "bt_STRAT_9"}, {"text": "10. Gap-Up Continue", "callback_data": "bt_STRAT_10"}],
        [{"text": "⬅️ Back to Menu", "callback_data": "btn_back_menu"}]
    ]
    keyboard = {"inline_keyboard": buttons}
    msg = (
        "🧪 *SWING STRATEGY HISTORICAL BACKTEST*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Pichle 1 saal ke real NSE Daily candle data par kisi bhi strategy ka Win Rate % aur Net Gain check karein:"
    )
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown", "reply_markup": json.dumps(keyboard)}
    requests.post(url, data=payload, timeout=5)

# --- MATHEMATICAL STRATEGY EVALUATOR ---
def evaluate_strategy_signals(df, strat_key):
    """Calculates exact mathematical setup on DataFrame and returns (is_signal, reason)"""
    if len(df) < 55:
        return False, ""

    c = float(df['Close'].iloc[-1])
    o = float(df['Open'].iloc[-1])
    h = float(df['High'].iloc[-1])
    l = float(df['Low'].iloc[-1])
    v = float(df['Volume'].iloc[-1])
    v_avg15 = float(df['Volume'].rolling(15).mean().iloc[-1])
    vol_ratio = v / v_avg15 if v_avg15 > 0 else 1.0

    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()

    # 1. 20/50 EMA Golden Cross
    if strat_key == "STRAT_1":
        ema20_now = float(df['EMA20'].iloc[-1])
        ema50_now = float(df['EMA50'].iloc[-1])
        ema20_prev = float(df['EMA20'].iloc[-2])
        ema50_prev = float(df['EMA50'].iloc[-2])
        if ema20_prev <= ema50_prev and ema20_now > ema50_now and vol_ratio >= 1.5:
            return True, f"20 EMA (₹{ema20_now:.1f}) crossed above 50 EMA (₹{ema50_now:.1f}) with {vol_ratio:.1f}x Volume"

    # 2. Pullback to 20 EMA
    elif strat_key == "STRAT_2":
        ema20 = float(df['EMA20'].iloc[-1])
        ema50 = float(df['EMA50'].iloc[-1])
        if ema20 > ema50 and l <= ema20 * 1.01 and c > ema20 and c > o:
            return True, f"Bullish bounce at 20 EMA (₹{ema20:.1f}) support in uptrend"

    # 3. Volume Breakout (Darvas Box)
    elif strat_key == "STRAT_3":
        box_high = float(df['High'].shift(1).rolling(20).max().iloc[-1])
        if c > box_high and vol_ratio >= 2.0:
            return True, f"20-Day Box High (₹{box_high:.1f}) breached with {vol_ratio:.1f}x Institutional Volume"

    # 4. Support & Resistance Bounce
    elif strat_key == "STRAT_4":
        support_level = float(df['Low'].shift(1).rolling(25).min().iloc[-1])
        if l <= support_level * 1.015 and c > support_level and (c - l) > (h - c):
            return True, f"Key demand zone (₹{support_level:.1f}) respected with bullish hammer"

    # 5. RSI Bullish Divergence
    elif strat_key == "STRAT_5":
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        
        low10 = float(df['Low'].iloc[-1])
        low25 = float(df['Low'].shift(10).rolling(15).min().iloc[-1])
        rsi_now = float(rsi.iloc[-1])
        rsi_past = float(rsi.shift(10).rolling(15).min().iloc[-1])
        if low10 < low25 and rsi_now > rsi_past and rsi_now < 45:
            return True, f"RSI Divergence confirmed: Price Lower Low vs RSI Higher Low ({rsi_now:.1f})"

    # 6. Daily High Breakout (ORB Swing)
    elif strat_key == "STRAT_6":
        high_5d = float(df['High'].shift(1).rolling(5).max().iloc[-1])
        if c > high_5d and vol_ratio >= 1.8:
            return True, f"5-Day Momentum Breakout (₹{high_5d:.1f}) with {vol_ratio:.1f}x Volume"

    # 7. MACD Histogram Reversal
    elif strat_key == "STRAT_7":
        exp1 = df['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df['Close'].ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        sig = macd.ewm(span=9, adjust=False).mean()
        hist = macd - sig
        if float(hist.iloc[-2]) < 0 and float(hist.iloc[-1]) > 0 and c > float(df['EMA50'].iloc[-1]):
            return True, f"MACD Histogram flipped positive (+{float(hist.iloc[-1]):.2f}) above 50 EMA"

    # 8. VCP Pattern (Minervini Style)
    elif strat_key == "STRAT_8":
        atr_now = float((df['High'] - df['Low']).rolling(5).mean().iloc[-1])
        atr_past = float((df['High'] - df['Low']).rolling(20).mean().iloc[-1])
        high_15 = float(df['High'].shift(1).rolling(15).max().iloc[-1])
        if atr_now < (0.65 * atr_past) and c > high_15 and vol_ratio >= 1.8:
            return True, f"VCP Contraction Breakout: Volatility compressed 35% before volume expansion"

    # 9. Bollinger Squeeze Breakout
    elif strat_key == "STRAT_9":
        sma20 = df['Close'].rolling(20).mean()
        std20 = df['Close'].rolling(20).std()
        upper_bb = sma20 + (2 * std20)
        lower_bb = sma20 - (2 * std20)
        bw = (upper_bb - lower_bb) / sma20
        bw_now = float(bw.iloc[-1])
        bw_avg = float(bw.rolling(15).mean().iloc[-1])
        if bw_now < bw_avg and c > float(upper_bb.iloc[-1]) and vol_ratio >= 1.8:
            return True, f"Bollinger Squeeze broken to upside above Upper Band (₹{float(upper_bb.iloc[-1]):.1f})"

    # 10. Gap-Up Continuation
    elif strat_key == "STRAT_10":
        prev_close = float(df['Close'].iloc[-2])
        prev_high = float(df['High'].iloc[-2])
        day_open = float(df['Open'].iloc[-1])
        gap_pct = ((day_open - prev_close) / prev_close) * 100
        if gap_pct >= 1.5 and l >= prev_high and c > day_open and vol_ratio >= 2.0:
            return True, f"Aggressive +{gap_pct:.1f}% Gap-Up held firmly above yesterday's high"

    return False, ""

# --- BACKTESTING ENGINE ---
def run_backtest_for_strategy(strat_key, tickers_subset=None):
    strat = STRATEGIES[strat_key]
    tickers = tickers_subset or SWING_WATCHLIST[:12]
    total_trades = 0
    wins = 0
    losses = 0
    total_pct_gain = 0.0

    target = strat["target_pct"]
    sl = strat["sl_pct"]

    for sym in tickers:
        try:
            df = yf.download(tickers=sym, period="1y", interval="1d", progress=False)
            if df is None or df.empty or len(df) < 60:
                continue
            if hasattr(df.columns, 'levels'):
                df.columns = [col[0] for col in df.columns]

            in_pos = False
            entry_p = 0.0

            for i in range(40, len(df)):
                sub_df = df.iloc[:i+1]
                c = float(sub_df['Close'].iloc[-1])

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

                sig, _ = evaluate_strategy_signals(sub_df, strat_key)
                if sig:
                    in_pos = True
                    entry_p = c

        except Exception:
            pass

    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0
    return {
        "strat": strat["name"],
        "tag": strat["tag"],
        "total": total_trades,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "net_gain": total_pct_gain * 100
    }

def handle_backtest_action(strat_key):
    if strat_key == "ALL":
        send_alert("⏳ *Auditing All 10 Swing Strategies on 1-Year NSE Data... (Takes ~20s)*")
        res_list = []
        for k in STRATEGIES.keys():
            res_list.append(run_backtest_for_strategy(k))
        
        msg = "🏆 *10 SWING STRATEGIES HISTORICAL AUDIT*\n━━━━━━━━━━━━━━━━━━━━\n"
        for r in res_list:
            msg += (
                f"📌 *{r['strat']}*\n"
                f"• Win Rate: *{r['win_rate']:.1f}%* ({r['wins']}W | {r['losses']}L)\n"
                f"• Trades: `{r['total']}` | Net Gain: *{r['net_gain']:+.1f}%*\n\n"
            )
        msg += "━━━━━━━━━━━━━━━━━━━━\n💡 Tap '⚙️ Strategy' menu to activate the best performer!"
        send_menu(msg)
    else:
        strat_name = STRATEGIES[strat_key]["name"]
        send_alert(f"⏳ *Testing `{strat_name}` on 1-Year historical data...*")
        r = run_backtest_for_strategy(strat_key)
        msg = (
            f"🧪 *BACKTEST REPORT: {r['strat']}*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 Win Rate: *{r['win_rate']:.1f}%*\n"
            f"📦 Total Simulated Trades: `{r['total']}`\n"
            f"✅ Target Exits (+{int(STRATEGIES[strat_key]['target_pct']*100)}%): `{r['wins']}`\n"
            f"❌ Stop Loss Exits (-{STRATEGIES[strat_key]['sl_pct']*100:.1f}%): `{r['losses']}`\n"
            f"📈 Cumulative Yield: *{r['net_gain']:+.1f}%*\n"
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
        
        msg = "📊 *ACTIVE SWING HOLDINGS*\n━━━━━━━━━━━━━━━━━━━━\n"
        if pos:
            for sym, d in pos.items():
                name = sym.replace(".NS", "")
                trail_txt = "🛡️ Breakeven (0 Risk)" if d.get('trailed_level', 0) == 1 else f"SL: ₹{d['sl']:.2f}"
                msg += (
                    f"📦 *{name}*\n"
                    f"• Strategy: *{d.get('strat_name', 'Swing')}*\n"
                    f"• Setup: _{d.get('reason', 'N/A')}_\n"
                    f"• Entry: `₹{d['entry']:.2f}` | Qty: `{d['qty']}`\n"
                    f"• Target: `₹{d['target']:.2f}` | Guard: `{trail_txt}`\n"
                    f"• Invested: `₹{(d['entry']*d['qty']):.2f}`\n\n"
                )
        else:
            msg += "_(Koi active swing trade nahi hai - bot market scan kar raha hai)_\n"
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
            f"🚀 *ROAD TO ₹1,00,000 MILESTONE*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• Initial Pool: `₹{init:,.2f}`\n"
            f"• Portfolio Net Worth: `₹{current_worth:,.2f}`\n"
            f"• Liquid Cash: `₹{cash:,.2f}`\n"
            f"• In-Trade Holdings: `₹{invested:,.2f}`\n"
            f"• Net Growth: *{growth:+.2f}%*\n"
            f"• Journey Progress: *{target_pct:.1f}% Completed*\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )

    elif data == "btn_select_strat":
        send_strategy_selector()

    elif data.startswith("set_STRAT_"):
        strat_key = data.replace("set_", "")
        trade_state["active_strategy"] = strat_key
        save_data(trade_state)
        s_name = STRATEGIES[strat_key]["name"]
        send_menu(f"✅ *ACTIVE STRATEGY SWITCHED TO:*\n👉 *{s_name}*\n\nAb agle swing trades is strategy par lagaye jayenge!")

    elif data == "btn_backtest_menu":
        send_backtest_options()

    elif data.startswith("bt_"):
        s_key = data.replace("bt_", "")
        threading.Thread(target=handle_backtest_action, args=(s_key,)).start()

    elif data == "btn_back_menu":
        send_menu("🎛️ *COMMAND TERMINAL ACTIVE*")

    elif data == "btn_scan":
        send_alert("🔍 *Scanning NSE Basket with Active Strategy...*")
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
            f"• Liquid Capital: `₹{cash:,.2f}`"
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
                    "pnl": 0.0, "result": "MANUAL_EXIT", "date": today_str,
                    "strat_name": d.get("strat_name", "Swing")
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
                    send_menu("🎛️ *NSE SWING COMMAND CENTER*\nButtons se bot operate karein:")
        except Exception as e:
            print(f"Listener error: {e}")
        time.sleep(0.5)

# --- POSITION MONITORING ENGINE ---
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

            # 🛡️ Dynamic Breakeven Lock (Zero-Risk Trade)
            if d.get('trailed_level', 0) == 0 and gain_pct >= trail_threshold:
                d['sl'] = entry
                d['trailed_level'] = 1
                save_data(trade_state)
                send_alert(
                    f"🛡️ *PROFIT SECURED: {name}*\n"
                    f"Strategy: *{d.get('strat_name', 'Swing')}*\n"
                    f"Move: *+{gain_pct:.2f}%*! SL breakeven cost (₹{entry:.2f}) par lock kar diya gaya hai. Trade is now 100% Risk Free!"
                )

            # Target Hit (+10% to +15%)
            if curr_price >= d['target']:
                profit = round((curr_price - entry) * qty, 2)
                trade_state["virtual_balance"] += (curr_price * qty)
                send_alert(
                    f"🎯 *TARGET HIT: {name}*\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"📌 *Strategy Used:* `{d.get('strat_name', 'Swing')}`\n"
                    f"💵 *Entry:* `₹{entry:.2f}` | *Exit:* `₹{curr_price:.2f}` (+{gain_pct:.2f}%)\n"
                    f"💰 *Net Profit:* *+₹{profit:,.2f}*\n"
                    f"💼 *Compounded Balance:* *₹{trade_state['virtual_balance']:,.2f}*\n"
                    f"🚀 Step closer to ₹1,00,000 Milestone!"
                )
                trade_state["trade_history"].append({
                    "symbol": sym, "type": "BUY", "entry": entry, "exit": curr_price,
                    "pnl": profit, "result": "WIN", "date": today_str,
                    "strat_name": d.get("strat_name", "Swing")
                })
                closed.append(sym)

            # Stop Loss Hit
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
                    "pnl": pnl, "result": outcome, "date": today_str,
                    "strat_name": d.get("strat_name", "Swing")
                })
                closed.append(sym)

        except Exception as e:
            print(f"Tracking error {sym}: {e}")

    for sym in closed:
        if sym in trade_state["open_positions"]:
            del trade_state["open_positions"][sym]
    if closed:
        save_data(trade_state)

# --- SCANNER RUNNING ACTIVE STRATEGY ---
def scan_swing_breakouts():
    global trade_state, BOT_PAUSED
    if BOT_PAUSED:
        return

    manage_swing_positions()

    # Rule: Max 2 strong concurrent swings to power compounding
    if len(trade_state.get("open_positions", {})) >= 2:
        return
    if trade_state["virtual_balance"] < 4000.0:
        return

    strat_key = trade_state.get("active_strategy", "STRAT_3")
    strat_cfg = STRATEGIES.get(strat_key, STRATEGIES["STRAT_3"])

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

            is_signal, reason_desc = evaluate_strategy_signals(df, strat_key)

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
                    "trail_at": strat_cfg["trail_at"]
                }
                save_data(trade_state)
                name = sym.replace(".NS", "")

                send_alert(
                    f"🔥 *SWING BUY SIGNAL TRIGGERED: {name}*\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"📌 *Strategy:* `{strat_cfg['name']}`\n"
                    f"💡 *Technical Reason:* _{reason_desc}_\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"💵 *Entry Price:* `₹{curr_price:.2f}`\n"
                    f"📦 *Position Size:* `{qty}` Shares\n"
                    f"💰 *Capital Invested:* `₹{(curr_price*qty):,.2f}`\n"
                    f"🛑 *Stop Loss:* `₹{sl}` (-{strat_cfg['sl_pct']*100:.1f}%)\n"
                    f"🎯 *Target:* `₹{tgt}` (+{strat_cfg['target_pct']*100:.1f}%)\n"
                    f"💼 *Cash Remaining:* `₹{trade_state['virtual_balance']:,.2f}`\n"
                    f"⏱️ *Expected Holding:* 3 - 10 Days"
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
        self.wfile.write(b"NSE Swing Bot Suite Online.")

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

# --- STARTUP BROADCAST ---
active_strat_name = STRATEGIES[trade_state.get("active_strategy", "STRAT_3")]["name"]
send_menu(
    f"🚀 *10-IN-1 INSTITUTIONAL SWING BOT ACTIVE*\n\n"
    f"🎯 *Mission:* ₹10,000 ➔ ₹1,00,000 Compounding\n"
    f"⚙️ *Currently Active:* `{active_strat_name}`\n"
    f"📊 *Features:* 10 Swing Setups + Backtester + Signal Reason Card\n\n"
    f"Neeche diye gaye buttons se strategy badlein ya historical Win Rate audit karein:"
)

listener_thread = threading.Thread(target=fast_telegram_listener, daemon=True)
listener_thread.start()

while True:
    if is_indian_market_open():
        scan_swing_breakouts()
    else:
        manage_swing_positions()
    time.sleep(300)
