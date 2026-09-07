import os
import json
import time
import requests
import yfinance as yf

# --- BOT CONFIG ---
TELEGRAM_TOKEN = "8876905313:AAHWQ8cD9jADvepC4lQE1psRH9WOxxL21qA"
CHAT_ID = "1345385952"
DATA_FILE = "trades_data.json"

# State persistence: File se load karna
def load_data():
    default_data = {"virtual_balance": 10000.00, "open_positions": {}}
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"File read error, resetting state: {e}")
            return default_data
    return default_data

def save_data(data):
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"File save error: {e}")

# Initial state load
trade_state = load_data()

WATCHLIST = [
    "IFCI.NS", "PFC.NS", "RECLTD.NS", "IREDA.NS", "SJVN.NS", "NHPC.NS", 
    "BHEL.NS", "BEL.NS", "HUDCO.NS", "NBCC.NS", "IRFC.NS", "RVNL.NS", 
    "RAILTEL.NS", "IRCON.NS", "RITES.NS", "MAZDOCK.NS", "COCHINSHIP.NS",
    "SUZLON.NS", "RPOWER.NS", "JPPOWER.NS", "IDEA.NS", "YESBANK.NS", 
    "PATANJALI.NS", "GMRINFRA.NS", "IDFCFIRSTB.NS", "PNB.NS", "UNIONBANK.NS",
    "TATASTEEL.NS", "SAIL.NS", "NMDC.NS", "NATIONALUM.NS", "HINDALCO.NS", 
    "ZOMATO.NS", "PAYTM.NS", "ASHOKLEY.NS", "CANBK.NS", "ABCAPITAL.NS"
]

def send_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print(f"Alert error: {e}")

def classify_trade_style(vol_spike_ratio):
    if vol_spike_ratio >= 4.0:
        return "⚡ SCALPING (Quick 1:1.5 Move)", 0.012, 0.020
    elif vol_spike_ratio >= 2.5:
        return "⏱️ INTRADAY (Day Trend)", 0.015, 0.035
    else:
        return "📈 SWING (Hold 1-3 Days)", 0.025, 0.060

def manage_open_positions():
    global trade_state
    closed = []
    positions = trade_state.get("open_positions", {})
    
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
            
            # --- TRAILING STOP LOSS ---
            if pos['type'] == "BUY":
                if not pos.get('trailed', False) and curr_price >= entry * 1.015:
                    pos['sl'] = entry
                    pos['trailed'] = True
                    save_data(trade_state)
                    send_alert(
                        f"🛡️ *TRAILING SL TRIGGERED*\n\n"
                        f"📌 *Stock:* {symbol}\n"
                        f"💰 Current Price: ₹{curr_price:.2f}\n"
                        f"🔒 Stop Loss moved to Entry: ₹{entry:.2f}\n"
                        f"✅ Zero-risk mode active!"
                    )

                # Target Hit
                if curr_price >= pos['target']:
                    profit = round((curr_price - entry) * qty, 2)
                    trade_state["virtual_balance"] += (curr_price * qty)
                    closed.append(symbol)
                    send_alert(
                        f"🎯 *TARGET HIT! [PROFIT BOOKED]*\n\n"
                        f"📈 *Stock:* {symbol} ({pos['style']})\n"
                        f"💰 Exit Price: ₹{curr_price:.2f}\n"
                        f"💵 Profit: +₹{profit}\n"
                        f"💼 Total Balance: ₹{trade_state['virtual_balance']:.2f}"
                    )
                # SL Hit
                elif curr_price <= pos['sl']:
                    loss = round((entry - curr_price) * qty, 2)
                    trade_state["virtual_balance"] += (curr_price * qty)
                    closed.append(symbol)
                    send_alert(
                        f"🛑 *STOP LOSS HIT!*\n\n"
                        f"📉 *Stock:* {symbol} ({pos['style']})\n"
                        f"💰 Exit Price: ₹{curr_price:.2f}\n"
                        f"⚠️ Loss: -₹{loss}\n"
                        f"💼 Total Balance: ₹{trade_state['virtual_balance']:.2f}"
                    )

            elif pos['type'] == "SELL":
                if not pos.get('trailed', False) and curr_price <= entry * 0.985:
                    pos['sl'] = entry
                    pos['trailed'] = True
                    save_data(trade_state)
                    send_alert(f"🛡️ *TRAILING SL:* {symbol} Stop Loss entry pe move ho gaya.")

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
    open_count = len(trade_state.get("open_positions", {}))
    print(f"\n[{time.strftime('%H:%M:%S')}] Active Positions: {open_count} | Balance: ₹{trade_state['virtual_balance']:.2f}")
    
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
            low_20 = float(df['Low_20'].iloc[-1])

            vol_ratio = curr_vol / avg_vol if avg_vol > 0 else 1.0

            if vol_ratio >= 2.0:
                style_name, sl_pct, tgt_pct = classify_trade_style(vol_ratio)
                
                trade_fund = min(2500.0, trade_state["virtual_balance"])
                qty = int(trade_fund // curr_close)
                if qty < 1:
                    continue

                # BUY
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
                        f"🚀 *DEMO TRADE ENTRY: BUY*\n\n"
                        f"📊 *Type:* {style_name}\n"
                        f"📈 *Stock:* {symbol}\n"
                        f"💵 *Entry:* ₹{curr_close:.2f} | *Qty:* {qty}\n"
                        f"🔥 *Volume:* {vol_ratio:.1f}x Spike\n"
                        f"🎯 *Target:* ₹{tgt}\n"
                        f"🛑 *Initial SL:* ₹{sl}\n"
                        f"💼 Balance Rem: ₹{trade_state['virtual_balance']:.2f}"
                    )

                # SELL / SHORT
                elif curr_close < low_20:
                    sl = round(curr_close * (1 + sl_pct), 2)
                    tgt = round(curr_close * (1 - tgt_pct), 2)
                    
                    trade_state["open_positions"][symbol] = {
                        'type': 'SELL', 'entry': curr_close, 'qty': qty,
                        'sl': sl, 'target': tgt, 'style': style_name, 'trailed': False
                    }
                    save_data(trade_state)

                    send_alert(
                        f"🔻 *DEMO TRADE ENTRY: SELL/SHORT*\n\n"
                        f"📊 *Type:* {style_name}\n"
                        f"📉 *Stock:* {symbol}\n"
                        f"💵 *Entry:* ₹{curr_close:.2f} | *Qty:* {qty}\n"
                        f"🔥 *Volume:* {vol_ratio:.1f}x Panic Selling\n"
                        f"🎯 *Target:* ₹{tgt}\n"
                        f"🛑 *SL:* ₹{sl}\n"
                        f"💼 Balance: ₹{trade_state['virtual_balance']:.2f}"
                    )

        except Exception as e:
            print(f"Error checking {symbol}: {e}")

# Startup Notification
open_cnt = len(trade_state.get("open_positions", {}))
send_alert(
    f"🤖 *Paper Trading Bot Live!*\n\n"
    f"💰 *Current Demo Balance:* ₹{trade_state['virtual_balance']:.2f}\n"
    f"📂 *Resumed Active Trades:* {open_cnt}\n"
    f"💾 *State Engine:* Persistent file auto-save enabled."
)

while True:
    scan_market()
    time.sleep(300)
