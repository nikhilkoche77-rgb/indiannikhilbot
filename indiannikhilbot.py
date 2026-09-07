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

# Persistent State Manager
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
        except Exception as e:
            print(f"State load warning: {e}")
            return default_data
    return default_data

def save_data(data):
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"State save error: {e}")

trade_state = load_data()

# 120+ High-Momentum & Liquid Stocks Watchlist
WATCHLIST = [
    # ⚡ 1. Scalping (High Liquidity & Fast Turnover)
    "TATASTEEL.NS", "BEL.NS", "BHEL.NS", "SAIL.NS", "NATIONALUM.NS", "NMDC.NS",
    "PFC.NS", "RECLTD.NS", "COALINDIA.NS", "HINDALCO.NS", "VEDL.NS", "ONGC.NS",
    "IRFC.NS", "RVNL.NS", "SUZLON.NS", "ZOMATO.NS", "PAYTM.NS", "IDEA.NS",
    "YESBANK.NS", "PNB.NS", "BANKBARODA.NS", "CANBK.NS", "UNIONBANK.NS", "IDFCFIRSTB.NS",
    "ASHOKLEY.NS", "GMRINFRA.NS", "ABCAPITAL.NS", "MANAPPURAM.NS", "FEDERALBNK.NS",
    "IOC.NS", "BPCL.NS", "POWERGRID.NS", "NTPC.NS", "RPOWER.NS", "JPPOWER.NS",

    # ⏱️ 2. Intraday Momentum & Directional Breakouts
    "IFCI.NS", "IREDA.NS", "HUDCO.NS", "NBCC.NS", "RAILTEL.NS", "IRCON.NS",
    "SJVN.NS", "NHPC.NS", "MAZDOCK.NS", "COCHINSHIP.NS", "HAL.NS", "BDL.NS",
    "PATANJALI.NS", "EXIDEIND.NS", "AMARAJABAT.NS", "MOTHERSON.NS", "TATACHEM.NS",
    "JINDALSTEL.NS", "JSWSTEEL.NS", "HCLTECH.NS", "WIPRO.NS", "INFY.NS",
    "BHARTIARTL.NS", "ADANIENT.NS", "ADANIPORTS.NS", "ADANIPOWER.NS", "ADANIGREEN.NS",
    "DLF.NS", "GODREJPROP.NS", "CHOLAFIN.NS", "POONAWALLA.NS", "L&TFH.NS",
    "MUTHOOTFIN.NS", "BANDHANBNK.NS", "UCOBANK.NS", "CENTRALBK.NS", "BANKINDIA.NS",
    "IOB.NS", "OIL.NS", "GAIL.NS", "DELHIVERY.NS", "NYKAA.NS", "POLICYBZR.NS",
    "JUBLFOOD.NS", "HAVELLS.NS",

    # 📈 3. Swing Setups (Consolidation to Expansion)
    "PARAS.NS", "MTARTECH.NS", "DATA-PATTERNS.NS", "KPIGREEN.NS", "BORORENEW.NS",
    "GMDCLTD.NS", "TATAINVEST.NS", "KALYANKJIL.NS", "HBLPOWER.NS", "ENGINERSIN.NS",
    "WAAREEENER.NS", "PREMIERENE.NS", "RITES.NS", "GRSE.NS", "BEML.NS",
    "ASTRAL.NS", "POLYCAB.NS", "KEI.NS", "DIXON.NS", "KAYNES.NS",
    "PERSISTENT.NS", "COFORGE.NS", "MPHASIS.NS", "TITAN.NS", "TRENT.NS",
    "DMART.NS", "APOLLOTYRE.NS", "MRF.NS", "BALKRISIND.NS", "ESCORTS.NS",
    "DEEPAKNTR.NS", "TATAELXSI.NS", "CLEAN.NS", "FINEORG.NS", "AETHER.NS",
    "SUVENPHAR.NS", "NATCOPHARM.NS", "GLENMARK.NS", "LUPIN.NS", "AUROPHARMA.NS"
]

def send_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print(f"Telegram API error: {e}")

def generate_performance_report():
    history = trade_state.get("trade_history", [])
    total_trades = len(history)
    
    if total_trades == 0:
        return (
            f"📊 *PERFORMANCE REPORT*\n\n"
            f"💰 *Current Balance:* ₹{trade_state['virtual_balance']:.2f}\n"
            f"📂 *Open Trades:* {len(trade_state.get('open_positions', {}))}\n"
            f"ℹ️ Abhi tak koi trade close nahi hua hai."
        )

    wins = [t for t in history if t.get("pnl", 0) > 0]
    losses = [t for t in history if t.get("pnl", 0) <= 0]
    win_rate = (len(wins) / total_trades) * 100
    total_pnl = sum([t.get("pnl", 0) for t in history])

    return (
        f"🏛️ *PERFORMANCE DASHBOARD*\n\n"
        f"💰 *Balance:* ₹{trade_state['virtual_balance']:.2f}\n"
        f"📈 *Net P&L:* {'+' if total_pnl >= 0 else ''}₹{total_pnl:.2f}\n"
        f"🎯 *Win Rate:* {win_rate:.1f}%\n"
        f"🔢 *Total Trades:* {total_trades} (✅ {len(wins)} Win | ❌ {len(losses)} Loss)\n"
        f"📂 *Active Open Positions:* {len(trade_state.get('open_positions', {}))}\n\n"
        f"👉 Commands: `/status` (open positions) | `/eod` (daily summary)"
    )

def check_telegram_commands():
    global LAST_UPDATE_ID, trade_state
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={LAST_UPDATE_ID + 1}&timeout=1"
    try:
        res = requests.get(url, timeout=3).json()
        for update in res.get("result", []):
            LAST_UPDATE_ID = update["update_id"]
            text = update.get("message", {}).get("text", "").strip().lower()

            if text in ["/report", "report", "/pnl", "pnl"]:
                send_alert(generate_performance_report())
            
            elif text in ["/status", "status"]:
                positions = trade_state.get("open_positions", {})
                if not positions:
                    send_alert("ℹ️ *Status:* Koi bhi open position active nahi hai.")
                else:
                    msg = "📋 *ACTIVE OPEN POSITIONS:*\n\n"
                    for sym, data in positions.items():
                        msg += (
                            f"• *{sym}* ({data['style']})\n"
                            f"  Entry: ₹{data['entry']:.2f} | Qty: {data['qty']}\n"
                            f"  SL: ₹{data['sl']:.2f} | Target: ₹{data['target']:.2f}\n\n"
                        )
                    send_alert(msg)

            elif text in ["/eod", "eod"]:
                today_str = datetime.now().strftime("%Y-%m-%d")
                today_trades = [t for t in trade_state.get("trade_history", []) if t.get("date") == today_str]
                pnl_today = sum([t.get("pnl", 0) for t in today_trades])
                send_alert(
                    f"🏁 *EOD SUMMARY ({today_str})*\n\n"
                    f"🔢 Today Trades: {len(today_trades)}\n"
                    f"💵 Today P&L: {'+' if pnl_today >= 0 else ''}₹{pnl_today:.2f}\n"
                    f"💼 Balance: ₹{trade_state['virtual_balance']:.2f}"
                )
    except Exception as e:
        print(f"Command listener warning: {e}")

def classify_trade_style(vol_spike_ratio):
    if vol_spike_ratio >= 4.0:
        return "⚡ SCALPING", 0.012, 0.025
    elif vol_spike_ratio >= 2.5:
        return "⏱️ INTRADAY", 0.015, 0.035
    else:
        return "📈 SWING", 0.025, 0.060

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
            
            # --- Trailing Stop Loss Rule ---
            if pos['type'] == "BUY":
                if not pos.get('trailed', False) and curr_price >= entry * 1.015:
                    pos['sl'] = entry
                    pos['trailed'] = True
                    save_data(trade_state)
                    send_alert(f"🛡️ *TRAILING SL ACTIVE:* {symbol} SL moved to entry ₹{entry:.2f}. Trade risk-free!")

                # Target Hit
                if curr_price >= pos['target']:
                    profit = round((curr_price - entry) * qty, 2)
                    trade_state["virtual_balance"] += (curr_price * qty)
                    trade_state["trade_history"].append({
                        "symbol": symbol, "type": "BUY", "entry": entry, "exit": curr_price,
                        "pnl": profit, "result": "WIN", "style": pos["style"], "date": today_str
                    })
                    closed.append(symbol)
                    send_alert(
                        f"🎯 *TARGET HIT!*\n\n"
                        f"📈 *{symbol}* ({pos['style']})\n"
                        f"💰 Exit: ₹{curr_price:.2f}\n"
                        f"💵 P&L: +₹{profit}\n"
                        f"💼 Demo Balance: ₹{trade_state['virtual_balance']:.2f}"
                    )

                # Stop Loss Hit
                elif curr_price <= pos['sl']:
                    loss = round((entry - curr_price) * qty, 2)
                    trade_state["virtual_balance"] += (curr_price * qty)
                    trade_state["trade_history"].append({
                        "symbol": symbol, "type": "BUY", "entry": entry, "exit": curr_price,
                        "pnl": -loss, "result": "LOSS", "style": pos["style"], "date": today_str
                    })
                    closed.append(symbol)
                    send_alert(
                        f"🛑 *STOP LOSS HIT!*\n\n"
                        f"📉 *{symbol}*\n"
                        f"💰 Exit: ₹{curr_price:.2f}\n"
                        f"⚠️ P&L: -₹{loss}\n"
                        f"💼 Demo Balance: ₹{trade_state['virtual_balance']:.2f}"
                    )

            elif pos['type'] == "SELL":
                if not pos.get('trailed', False) and curr_price <= entry * 0.985:
                    pos['sl'] = entry
                    pos['trailed'] = True
                    save_data(trade_state)
                    send_alert(f"🛡️ *TRAILING SL:* {symbol} Stop Loss entry pe shift ho gaya.")

                if curr_price <= pos['target']:
                    profit = round((entry - curr_price) * qty, 2)
                    trade_state["virtual_balance"] += ((entry - curr_price) * qty) + (entry * qty)
                    closed.append(symbol)
                    send_alert(f"🎯 *TARGET HIT (SHORT):* {symbol} | Profit: +₹{profit} | Balance: ₹{trade_state['virtual_balance']:.2f}")
                elif curr_price >= pos['sl']:
                    loss = round((curr_price - entry) * qty, 2)
                    trade_state["virtual_balance"] -= loss
                    closed.append(symbol)
                    send_alert(f"🛑 *SL HIT (SHORT):* {symbol} | Loss: -₹{loss} | Balance: ₹{trade_state['virtual_balance']:.2f}")

        except Exception as e:
            print(f"Tracking error {symbol}: {e}")

    for sym in closed:
        del trade_state["open_positions"][sym]
    if closed:
        save_data(trade_state)

def scan_market():
    global trade_state
    manage_open_positions()

    for symbol in WATCHLIST:
        if symbol in trade_state.get("open_positions", {}):
            continue

        try:
            time.sleep(0.2)  # Server safe delay
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
            low_20 = float(df['Low_20'].iloc[-1])

            vol_ratio = curr_vol / avg_vol if avg_vol > 0 else 1.0

            # 2x Volume Burst Filter
            if vol_ratio >= 2.0:
                style_name, sl_pct, tgt_pct = classify_trade_style(vol_ratio)
                
                # Max 25% demo capital per position (Risk management)
                trade_fund = min(2500.0, trade_state["virtual_balance"])
                qty = int(trade_fund // curr_close)
                if qty < 1:
                    continue

                if curr_close > high_20:
                    sl = round(curr_close * (1 - sl_pct), 2)
                    tgt = round(curr_close * (1 + tgt_pct), 2)
                    trade_state["virtual_balance"] -= (curr_close * qty)
                    
                    trade_state["open_positions"][symbol] = {
                        'type': 'BUY', 'entry': curr_close, 'qty': qty,
                        'sl': sl, 'target': tgt, 'style': style_name, 'trailed': False
                    }
                    save_data(trade_state)

                    send_alert(
                        f"🚀 *INSTITUTIONAL BREAKOUT ENTRY*\n\n"
                        f"📊 *Type:* {style_name}\n"
                        f"📈 *Stock:* {symbol}\n"
                        f"💵 *Entry:* ₹{curr_close:.2f} | *Qty:* {qty}\n"
                        f"🔥 *Relative Volume (RVOL):* {vol_ratio:.1f}x Surge\n"
                        f"🎯 *Target:* ₹{tgt}\n"
                        f"🛑 *SL:* ₹{sl}\n"
                        f"💼 Rem. Balance: ₹{trade_state['virtual_balance']:.2f}\n\n"
                        f"👉 Reply `/status` for active trades or `/report` for P&L."
                    )

        except Exception as e:
            print(f"Scan error {symbol}: {e}")

# Startup Notification
open_cnt = len(trade_state.get("open_positions", {}))
send_alert(
    f"🤖 *Paper Trading Bot Live!*\n\n"
    f"💰 *Current Demo Balance:* ₹{trade_state['virtual_balance']:.2f}\n"
    f"📂 *Active Open Trades:* {open_cnt}\n"
    f"📱 *Commands Active:* `/status`, `/report`, `/eod`\n"
    f"📡 120 Stocks scanning in background..."
)

# Main Loop (Every 5 minutes + periodic command listener)
while True:
    scan_market()
    for _ in range(30):
        check_telegram_commands()
        time.sleep(10)
