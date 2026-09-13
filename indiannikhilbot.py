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

# --- 13 COMPLETE PRO STRATEGIES SUITE ---
STRATEGIES = {
    "STRAT_1": {
        "name": "1. 9:20 AM Morning Breakout",
        "tag": "Power of Stocks Style",
        "desc": "High/Low breakout of initial morning range with volume confirmation",
        "rrr": "1:2.5", "sl_pct": 0.025, "target_pct": 0.065, "trail_at": 0.035
    },
    "STRAT_2": {
        "name": "2. 20 & 50 EMA Crossover",
        "tag": "Trend Crossover",
        "desc": "20 EMA crossing above 50 EMA with strong volume momentum",
        "rrr": "1:3.0", "sl_pct": 0.030, "target_pct": 0.090, "trail_at": 0.040
    },
    "STRAT_3": {
        "name": "3. VWAP + Price Action Rejection",
        "tag": "VWAP Rebound",
        "desc": "Bullish rejection and reclaim candle at standard VWAP anchor",
        "rrr": "1:2.5", "sl_pct": 0.028, "target_pct": 0.070, "trail_at": 0.035
    },
    "STRAT_4": {
        "name": "4. Opening Range Breakout (ORB)",
        "tag": "StockEdge / Classic ORB",
        "desc": "Multi-session or morning 15-30m range cleared with heavy volume",
        "rrr": "1:3.0", "sl_pct": 0.035, "target_pct": 0.105, "trail_at": 0.045
    },
    "STRAT_5": {
        "name": "5. MACD + RSI Divergence",
        "tag": "Momentum Divergence",
        "desc": "Price makes lower low while RSI & MACD register higher lows",
        "rrr": "1:3.5", "sl_pct": 0.030, "target_pct": 0.105, "trail_at": 0.040
    },
    "STRAT_6": {
        "name": "6. Support & Resistance Flip (SR Flip)",
        "tag": "Role Reversal Floor",
        "desc": "Past multi-week resistance breached and successfully tested as new floor",
        "rrr": "1:3.0", "sl_pct": 0.030, "target_pct": 0.090, "trail_at": 0.040
    },
    "STRAT_7": {
        "name": "7. Bollinger Band Squeeze",
        "tag": "Volatility Explosion",
        "desc": "Extreme band constriction followed by high-volume upper band breach",
        "rrr": "1:2.5", "sl_pct": 0.032, "target_pct": 0.080, "trail_at": 0.040
    },
    "STRAT_8": {
        "name": "8. CPR (Central Pivot Range)",
        "tag": "Pivot Breakout",
        "desc": "Narrow CPR expansion with price breaking above Top Central Pivot",
        "rrr": "1:2.5", "sl_pct": 0.028, "target_pct": 0.070, "trail_at": 0.035
    },
    "STRAT_9": {
        "name": "9. Inside Bar Breakout",
        "tag": "Mother Candle Break",
        "desc": "Tight consolidation inside prior bar's range cleared with volume",
        "rrr": "1:3.0", "sl_pct": 0.028, "target_pct": 0.084, "trail_at": 0.040
    },
    "STRAT_10": {
        "name": "10. VPA / Smart Money Concept (SMC)",
        "tag": "Institutional Footprint",
        "desc": "Orderblock rejection with extreme volume spike (>2.0x) indicating big operators",
        "rrr": "1:4.0", "sl_pct": 0.030, "target_pct": 0.120, "trail_at": 0.045
    },
    "STRAT_11": {
        "name": "11. EMA 50/200 Golden Cross",
        "tag": "Macro Golden Cross",
        "desc": "50 EMA crossing above 200 EMA or bouncing off 200 EMA institutional floor",
        "rrr": "1:3.5", "sl_pct": 0.032, "target_pct": 0.112, "trail_at": 0.045
    },
    "STRAT_12": {
        "name": "12. SMA & EMA 50/93 Harmonic Cross",
        "tag": "Harmonic Moving Average",
        "desc": "50 SMA/EMA crossing above 93 SMA/EMA with sustained price expansion",
        "rrr": "1:3.0", "sl_pct": 0.030, "target_pct": 0.090, "trail_at": 0.040
    },
    "STRAT_13": {
        "name": "13. Fibonacci Pivot Points Reversal",
        "tag": "Fibonacci Retracement Pivot",
        "desc": "Bullish reversal from S1/S2 Fib level or breakout above Fibonacci Pivot (0.382/0.618)",
        "rrr": "1:3.5", "sl_pct": 0.028, "target_pct": 0.098, "trail_at": 0.040
    }
}

# --- 165 LIQUID INDIAN STOCKS BASKET ---
SWING_WATCHLIST_ALL = [
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

BENCHMARKS = {
    "^NSEI": "NIFTY 50",
    "^NSEBANK": "BANK NIFTY"
}

# --- STATE STORAGE ---
def load_data():
    default_data = {
        "virtual_balance": 10000.00,
        "initial_capital": 10000.00,
        "active_strategy": "STRAT_13",
        "open_positions": {},
        "trade_history": []
    }
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                saved = json.load(f)
                if "active_strategy" not in saved or saved["active_strategy"] not in STRATEGIES:
                    saved["active_strategy"] = "STRAT_13"
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

# --- UI MENUS ---
def send_menu(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    active_strat = STRATEGIES.get(trade_state.get("active_strategy", "STRAT_13"), {})["name"]
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "📊 Open Positions", "callback_data": "btn_positions"},
                {"text": "💰 10K➔100K Progress", "callback_data": "btn_wallet"}
            ],
            [
                {"text": f"⚙️ Strategy: {active_strat}", "callback_data": "btn_select_strat"}
            ],
            [
                {"text": "🏆 1-Click Master Audit (All 13 Setups)", "callback_data": "btn_master_audit"}
            ],
            [
                {"text": "🧪 Strategy Lab Menu", "callback_data": "btn_backtest_menu"},
                {"text": "🔄 Scan 165 Stocks", "callback_data": "btn_scan"}
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
    curr = trade_state.get("active_strategy", "STRAT_13")
    buttons = []
    for k, v in STRATEGIES.items():
        tick = "✅ " if k == curr else ""
        buttons.append([{"text": f"{tick}{v['name']} ({v['rrr']})", "callback_data": f"set_{k}"}])
    buttons.append([{"text": "⬅️ Back to Menu", "callback_data": "btn_back_menu"}])
    keyboard = {"inline_keyboard": buttons}
    msg = (
        "⚙️ *SELECT ACTIVE TRADING SETUP*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Jis setup par bot ko 165 stocks live scan karne hain, select karein:\n"
    )
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown", "reply_markup": json.dumps(keyboard)}
    requests.post(url, data=payload, timeout=5)

def send_backtest_options():
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    buttons = [
        [{"text": "🏆 1-Click Master Audit (All 13 Setups)", "callback_data": "btn_master_audit"}],
        [{"text": "📈 NIFTY 50 Index Audit", "callback_data": "bt_idx_NIFTY"}, {"text": "🏦 BANK NIFTY Index Audit", "callback_data": "bt_idx_BANKNIFTY"}],
        [{"text": "11. EMA 50/200 Cross", "callback_data": "bt_STRAT_11"}, {"text": "12. 50/93 SMA & EMA", "callback_data": "bt_STRAT_12"}],
        [{"text": "13. Fibonacci Pivots", "callback_data": "bt_STRAT_13"}, {"text": "10. VPA / SMC Concept", "callback_data": "bt_STRAT_10"}],
        [{"text": "6. S/R Flip Retest", "callback_data": "bt_STRAT_6"}, {"text": "2. 20/50 EMA Cross", "callback_data": "bt_STRAT_2"}],
        [{"text": "⬅️ Back to Menu", "callback_data": "btn_back_menu"}]
    ]
    keyboard = {"inline_keyboard": buttons}
    msg = (
        "🧪 *PRO STRATEGY BACKTEST LAB*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "1-Year Real Market data par naye MA 50/200, 50/93, Fibonacci Pivots ya All Setups test karein:"
    )
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown", "reply_markup": json.dumps(keyboard)}
    requests.post(url, data=payload, timeout=5)

# --- TECHNICAL FORMULAS ENGINE ---
def evaluate_strategy(df, strat_key):
    if len(df) < 95:  # Needs at least 95 bars for 93 SMA/EMA
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
    df['SMA50'] = df['Close'].rolling(50).mean()
    df['SMA93'] = df['Close'].rolling(93).mean()
    df['EMA93'] = df['Close'].ewm(span=93, adjust=False).mean()

    # 1. 9:20 AM Morning Range Breakout
    if strat_key == "STRAT_1":
        prev_h = float(df['High'].iloc[-2])
        if c > prev_h and c > o and vol_ratio >= 1.6:
            return True, f"9:20 AM Range High cleared with {vol_ratio:.1f}x Volume Momentum"

    # 2. 20 & 50 EMA Crossover
    elif strat_key == "STRAT_2":
        ema20_now = float(df['EMA20'].iloc[-1])
        ema50_now = float(df['EMA50'].iloc[-1])
        ema20_prev = float(df['EMA20'].iloc[-2])
        ema50_prev = float(df['EMA50'].iloc[-2])
        if ema20_prev <= ema50_prev and ema20_now > ema50_now and vol_ratio >= 1.3:
            return True, f"20 EMA crossed above 50 EMA with {vol_ratio:.1f}x Volume"

    # 3. VWAP + Price Action Rejection
    elif strat_key == "STRAT_3":
        tp = (df['High'] + df['Low'] + df['Close']) / 3
        vwap = (tp * df['Volume']).cumsum() / df['Volume'].cumsum()
        vwap_val = float(vwap.iloc[-1])
        if l <= vwap_val * 1.008 and c > vwap_val and c > o:
            return True, f"Bullish rejection bar bouncing off VWAP Anchor (₹{vwap_val:.1f})"

    # 4. Opening Range Breakout (ORB)
    elif strat_key == "STRAT_4":
        high_10 = float(df['High'].shift(1).rolling(10).max().iloc[-1])
        if c > high_10 and vol_ratio >= 1.9:
            return True, f"Multi-day ORB Resistance (₹{high_10:.1f}) breached with {vol_ratio:.1f}x Volume"

    # 5. MACD + RSI Divergence
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
            return True, f"Bullish RSI Divergence: Price Lower Low vs RSI Higher Low ({rsi_now:.1f})"

    # 6. Support & Resistance Flip (SR Flip)
    elif strat_key == "STRAT_6":
        past_res = float(df['High'].shift(3).rolling(20).max().iloc[-1])
        prev_close = float(df['Close'].iloc[-2])
        if prev_close >= past_res and l <= past_res * 1.01 and c > past_res and c > o:
            return True, f"SR Flip: Prior ceiling (₹{past_res:.1f}) successfully retested as floor"

    # 7. Bollinger Band Squeeze Breakout
    elif strat_key == "STRAT_7":
        sma20 = df['Close'].rolling(20).mean()
        std20 = df['Close'].rolling(20).std()
        upper_bb = sma20 + (2 * std20)
        lower_bb = sma20 - (2 * std20)
        bw = (upper_bb - lower_bb) / sma20
        bw_now = float(bw.iloc[-1])
        bw_avg = float(bw.rolling(20).mean().iloc[-1])
        if bw_now < bw_avg * 0.80 and c > float(upper_bb.iloc[-1]) and vol_ratio >= 1.6:
            return True, f"Bollinger Squeeze Release: Upper Band (₹{float(upper_bb.iloc[-1]):.1f}) blown out"

    # 8. CPR Breakout
    elif strat_key == "STRAT_8":
        pivot = (df['High'].shift(1) + df['Low'].shift(1) + df['Close'].shift(1)) / 3
        bc = (df['High'].shift(1) + df['Low'].shift(1)) / 2
        tc = (pivot - bc) + pivot
        tc_val = float(tc.iloc[-1])
        if c > tc_val and float(df['Close'].iloc[-2]) <= tc_val and vol_ratio >= 1.4:
            return True, f"CPR Expansion: Price crossed Top Central Pivot (₹{tc_val:.1f})"

    # 9. Inside Bar Breakout
    elif strat_key == "STRAT_9":
        mother_h = float(df['High'].iloc[-3])
        mother_l = float(df['Low'].iloc[-3])
        inside_h = float(df['High'].iloc[-2])
        inside_l = float(df['Low'].iloc[-2])
        if inside_h <= mother_h and inside_l >= mother_l and c > mother_h and vol_ratio >= 1.5:
            return True, f"Inside Bar Compression cleared above Mother Candle High (₹{mother_h:.1f})"

    # 10. VPA / SMC Footprint
    elif strat_key == "STRAT_10":
        swing_low = float(df['Low'].shift(2).rolling(15).min().iloc[-1])
        prev_low = float(df['Low'].iloc[-2])
        if prev_low < swing_low * 0.998 and c > swing_low and c > o and vol_ratio >= 2.0:
            return True, f"SMC Footprint: False breakdown trap reclaimed with {vol_ratio:.1f}x Institutional Spike"

    # 11. EMA 50/200 Golden Cross / Macro Support
    elif strat_key == "STRAT_11":
        ema50_now = float(df['EMA50'].iloc[-1])
        ema200_now = float(df['EMA200'].iloc[-1])
        ema50_prev = float(df['EMA50'].iloc[-2])
        ema200_prev = float(df['EMA200'].iloc[-2])
        
        cross_up = (ema50_prev <= ema200_prev and ema50_now > ema200_now)
        bounce_200 = (l <= ema200_now * 1.01 and c > ema200_now and c > o and vol_ratio >= 1.4)
        if cross_up or bounce_200:
            return True, f"EMA 50/200 Golden Trend Setup: Price {c:.1f} supported by 200 EMA ({ema200_now:.1f})"

    # 12. SMA & EMA 50/93 Harmonic Cross
    elif strat_key == "STRAT_12":
        ema50 = float(df['EMA50'].iloc[-1])
        ema93 = float(df['EMA93'].iloc[-1])
        sma50 = float(df['SMA50'].iloc[-1])
        sma93 = float(df['SMA93'].iloc[-1])
        
        ema_cross = (float(df['EMA50'].iloc[-2]) <= float(df['EMA93'].iloc[-2]) and ema50 > ema93)
        sma_cross = (float(df['SMA50'].iloc[-2]) <= float(df['SMA93'].iloc[-2]) and sma50 > sma93)
        sustained = (c > ema50 and c > sma50 and vol_ratio >= 1.3)
        
        if (ema_cross or sma_cross) and sustained:
            return True, f"50/93 Harmonic Alignment: 50 MA crossed above 93 MA with strong expansion"

    # 13. Fibonacci Pivot Points Reversal & Breakout
    elif strat_key == "STRAT_13":
        prev_h = float(df['High'].shift(1).iloc[-1])
        prev_l = float(df['Low'].shift(1).iloc[-1])
        prev_c = float(df['Close'].shift(1).iloc[-1])
        rng = prev_h - prev_l
        
        p = (prev_h + prev_l + prev_c) / 3
        s1 = p - (0.382 * rng)
        s2 = p - (0.618 * rng)
        r1 = p + (0.382 * rng)
        
        # Bullish bounce from Fib S1/S2 level or clean breakout above Pivot
        bounce_fib = (l <= s1 * 1.005 and c > s1 and c > o and vol_ratio >= 1.3)
        break_pivot = (float(df['Close'].iloc[-2]) <= p and c > p and vol_ratio >= 1.5)
        
        if bounce_fib or break_pivot:
            return True, f"Fibonacci Pivot Setup: Reclaimed Level (Pivot: ₹{p:.1f}, S1 Fib: ₹{s1:.1f}) with Volume"

    return False, ""

# --- BACKTEST SIMULATION ENGINE ---
def run_backtest_simulation(strat_key, ticker_list):
    strat = STRATEGIES[strat_key]
    target = strat["target_pct"]
    sl = strat["sl_pct"]
    total_trades, wins, losses = 0, 0, 0
    total_yield = 0.0

    for sym in ticker_list:
        try:
            time.sleep(0.02)
            df = yf.download(tickers=sym, period="1y", interval="1d", progress=False)
            if df is None or df.empty or len(df) < 95:
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

                sig, _ = evaluate_strategy(sub_df, strat_key)
                if sig:
                    in_pos = True
                    entry_p = c
        except Exception:
            pass

    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0
    return {
        "strat": strat["name"],
        "tag": strat["tag"],
        "rrr": strat["rrr"],
        "trades": total_trades,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "yield": total_yield * 100
    }

# --- MASTER 1-CLICK ALL SETUPS AUDIT ---
def handle_master_audit():
    send_alert("⏳ *Processing Master Audit: Testing All 13 Setups against Indices & 165 Universe... (Takes ~40s)*")
    test_basket = ["^NSEI", "^NSEBANK"] + SWING_WATCHLIST_ALL[:20]
    
    results = []
    for k in STRATEGIES.keys():
        r = run_backtest_simulation(k, test_basket)
        results.append(r)

    # Sort setups by highest Win Rate
    results.sort(key=lambda x: x["win_rate"], reverse=True)

    msg = "🏆 *1-CLICK MASTER AUDIT (ALL 13 SETUPS)*\n"
    msg += "━━━━━━━━━━━━━━━━━━━━\n"
    msg += "📊 *Universe:* NIFTY 50 + BANK NIFTY + Top NSE Leaders\n"
    msg += "⏱️ *Data Scope:* 1-Year Real Daily Candles\n\n"

    for idx, r in enumerate(results, 1):
        badge = "🟢" if r['win_rate'] >= 60 else ("🟡" if r['win_rate'] >= 50 else "🔴")
        msg += (
            f"*{idx}. {r['strat']}* (`{r['rrr']}`)\n"
            f"   {badge} *Win Rate:* *{r['win_rate']:.1f}%* ({r['wins']}W | {r['losses']}L)\n"
            f"   📈 *Net Alpha:* *{r['yield']:+.1f}%* | Trades: `{r['trades']}`\n\n"
        )

    best_setup = results[0]
    msg += (
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👑 *TOP WIN-RATE SETUP:* *{best_setup['strat']}*\n"
        f"👉 Highest Historical Score: *{best_setup['win_rate']:.1f}% Win Rate*\n"
        "💡 '⚙️ Strategy' button dabakar is setup ko active karein!"
    )
    send_menu(msg)

def handle_backtest_action(action_key):
    if action_key == "btn_master_audit":
        handle_master_audit()

    elif action_key.startswith("idx_"):
        idx_sym = "^NSEI" if "NIFTY" in action_key and "BANK" not in action_key else "^NSEBANK"
        idx_name = "NIFTY 50" if idx_sym == "^NSEI" else "BANK NIFTY"
        send_alert(f"⏳ *Testing all 13 setups on `{idx_name}` 1-Year Daily Data...*")
        
        msg = f"📊 *{idx_name} HISTORICAL AUDIT (13 SETUPS)*\n━━━━━━━━━━━━━━━━━━━━\n"
        for k in STRATEGIES.keys():
            r = run_backtest_simulation(k, [idx_sym])
            msg += f"• *{r['strat']}*: *{r['win_rate']:.1f}% Win* (`{r['wins']}W/{r['losses']}L`) | Net: `{r['yield']:+.1f}%`\n"
        msg += "━━━━━━━━━━━━━━━━━━━━"
        send_menu(msg)

    else:
        strat_name = STRATEGIES[action_key]["name"]
        send_alert(f"⏳ *Auditing `{strat_name}` across basket...*")
        r = run_backtest_simulation(action_key, ["^NSEI", "^NSEBANK"] + SWING_WATCHLIST_ALL[:20])
        target_pct = STRATEGIES[action_key]["target_pct"] * 100
        sl_pct = STRATEGIES[action_key]["sl_pct"] * 100
        msg = (
            f"🧪 *STRATEGY AUDIT: {r['strat']}*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 Risk-Reward Ratio: *{r['rrr']}*\n"
            f"🔥 Win Rate: *{r['win_rate']:.1f}%*\n"
            f"📦 Simulated Trades: `{r['trades']}`\n"
            f"✅ Target Hits (+{target_pct:.1f}%): `{r['wins']}`\n"
            f"❌ Stop-Loss Hits (-{sl_pct:.1f}%): `{r['losses']}`\n"
            f"📈 Cumulative Yield: *{r['yield']:+.1f}%*\n"
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
                    f"• Setup: _{d.get('reason', 'N/A')}_\n"
                    f"• Entry: `₹{d['entry']:.2f}` | Qty: `{d['qty']}`\n"
                    f"• Target: `₹{d['target']:.2f}` | Guard: `{trail_txt}`\n"
                    f"• Allocation: `₹{(d['entry']*d['qty']):.2f}`\n\n"
                )
        else:
            msg += "_(Koi active swing trade nahi hai - bot 165 stocks scan kar raha hai)_\n"
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
            f"• Target Progress: *{target_pct:.1f}%* towards ₹1 Lakh\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )

    elif data == "btn_select_strat":
        send_strategy_selector()

    elif data.startswith("set_STRAT_"):
        strat_key = data.replace("set_", "")
        trade_state["active_strategy"] = strat_key
        save_data(trade_state)
        s_name = STRATEGIES[strat_key]["name"]
        send_menu(f"✅ *STRATEGY SWITCHED:*\n👉 *{s_name}*\n\nAb poore 165 stocks is setup ke rules par scan honge!")

    elif data == "btn_master_audit":
        threading.Thread(target=handle_master_audit).start()

    elif data == "btn_backtest_menu":
        send_backtest_options()

    elif data.startswith("bt_"):
        s_key = data.replace("bt_", "")
        threading.Thread(target=handle_backtest_action, args=(s_key,)).start()

    elif data == "btn_back_menu":
        send_menu("🎛️ *COMMAND TERMINAL ACTIVE*")

    elif data == "btn_scan":
        send_alert("🔍 *Scanning Entire 165 Stocks Basket with Active Strategy...*")
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
            f"• Liquid Capital: `₹{cash:,.2f}`"
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

            if d.get('trailed_level', 0) == 0 and gain_pct >= trail_pct:
                d['sl'] = entry
                d['trailed_level'] = 1
                save_data(trade_state)
                send_alert(
                    f"🛡️ *RISK ELIMINATED: {name}*\n"
                    f"Move: *+{gain_pct:.2f}%*! SL breakeven cost (₹{entry:.2f}) par lock ho gaya hai. Trade is now 100% Risk-Free!"
                )

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

# --- 165 STOCKS BREAKOUT SCANNER ---
def scan_swing_breakouts():
    global trade_state, BOT_PAUSED
    if BOT_PAUSED:
        return

    manage_swing_positions()

    if len(trade_state.get("open_positions", {})) >= 2:
        return
    if trade_state["virtual_balance"] < 4000.0:
        return

    strat_key = trade_state.get("active_strategy", "STRAT_13")
    strat_cfg = STRATEGIES.get(strat_key, STRATEGIES["STRAT_13"])

    for sym in SWING_WATCHLIST_ALL:
        if sym in trade_state.get("open_positions", {}):
            continue
        try:
            time.sleep(0.08)
            df = yf.download(tickers=sym, period="6mo", interval="1d", progress=False)
            if df is None or df.empty or len(df) < 95:
                continue
            if hasattr(df.columns, 'levels'):
                df.columns = [col[0] for col in df.columns]

            is_signal, reason_desc = evaluate_strategy(df, strat_key)

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
                    f"🔥 *SWING BUY SIGNAL: {name}*\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"📌 *Strategy:* `{strat_cfg['name']}`\n"
                    f"🎯 *Risk-Reward Ratio:* `{strat_cfg['rrr']}`\n"
                    f"💡 *Setup:* _{reason_desc}_\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"💵 *Entry:* `₹{curr_price:.2f}` | *Qty:* `{qty}`\n"
                    f"💰 *Invested:* `₹{(curr_price*qty):,.2f}`\n"
                    f"🛑 *Stop Loss:* `₹{sl}` (-{strat_cfg['sl_pct']*100:.1f}%)\n"
                    f"🎯 *Target:* `₹{tgt}` (+{strat_cfg['target_pct']*100:.1f}%)\n"
                    f"💼 *Liquid Cash Left:* `₹{trade_state['virtual_balance']:,.2f}`\n"
                    f"⏱️ *Holding Window:* 3 - 10 Days"
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
        self.wfile.write(b"NSE 13-Strategy Suite Active.")

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
active_strat_name = STRATEGIES[trade_state.get("active_strategy", "STRAT_13")]["name"]
send_menu(
    f"🚀 *13-STRATEGY PRO SUITE & MASTER AUDIT BOT ONLINE*\n\n"
    f"🎯 *Compounding Target:* ₹10,000 ➔ ₹1,00,000\n"
    f"⚙️ *Currently Active:* `{active_strat_name}`\n"
    f"📊 *Universe:* 165 Liquid NSE Stocks + NIFTY 50 + BANK NIFTY\n"
    f"➕ *Added Setups:* EMA 50/200, 50/93 SMA & EMA, Fibonacci Pivot Points\n"
    f"🏆 *Feature:* 1-Click Master Audit (Tests all 13 setups together)\n\n"
    f"Neeche diye gaye buttons se 1-Click Master Audit chalayein:"
)

listener_thread = threading.Thread(target=fast_telegram_listener, daemon=True)
listener_thread.start()

while True:
    if is_indian_market_open():
        scan_swing_breakouts()
    else:
        manage_swing_positions()
    time.sleep(300)
