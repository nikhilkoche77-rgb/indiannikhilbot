import time
import requests
import yfinance as yf

# --- BOT CONFIG ---
TELEGRAM_TOKEN = "8876905313:AAHWQ8cD9jADvepC4lQE1psRH9WOxxL21qA"
CHAT_ID = "1345385952"

# Demo Account Balance
virtual_balance = 10000.00
open_positions = {}  # {symbol: {type, entry, qty, sl, target, style, trailed}}

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
        return "⚡ SCALPING (Quick 1:1.5 Move)", 0.012, 0.020  # SL 1.2%, Target 2.0%
    elif vol_spike_ratio >= 2.5:
        return "⏱️ INTRADAY (Day Trend)", 0.015, 0.035      # SL 1.5%, Target 3.5%
    else:
        return "📈 SWING (Hold 1-3 Days)", 0.025, 0.060      # SL 2.5%, Target 6.0%

def manage_open_positions():
    global virtual_balance, open_positions
    closed = []
    
    for symbol, pos in open_positions.items():
        try:
            df = yf.download(tickers=symbol, period="1d", interval="5m", progress=False)
            if df is None or df.empty:
                continue
            if hasattr(df.columns, 'levels'):
                df.columns = [col[0] for col in df.columns]
                
            curr_price = float(df['Close'].iloc[-1])
            entry = pos['entry']
            qty = pos['qty']
            
            # --- TRAILING STOP LOSS LOGIC ---
            # Agar BUY trade 1.5% upar nikal gaya, toh SL entry price par shift (Zero Risk)
            if pos['type'] == "BUY":
                if not pos['trailed'] and curr_price >= entry * 1.015:
                    pos['sl'] = entry
                    pos['trailed'] = True
                    send_alert(
                        f"🛡️ *TRAILING SL TRIGGERED*\n\n"
                        f"📌 *Stock:* {symbol}\n"
                        f"💰 Current Price: ₹{curr_price:.2f}\n"
                        f"🔒 Stop Loss moved to Entry: ₹{entry:.2f}\n"
                        f"✅ Ab is trade me koi loss nahi ho sakta!"
                    )

                # Target Hit
                if curr_price >= pos['target']:
                    profit = round((curr_price - entry) * qty, 2)
                    virtual_balance += (curr_price * qty)
                    closed.append(symbol)
                    send_alert(
                        f"🎯 *TARGET HIT! [PROFIT BOOKED]*\n\n"
                        f"📈 *Stock:* {symbol} ({pos['style']})\n"
                        f"💰 Exit Price: ₹{curr_price:.2f}\n"
                        f"💵 Trade Profit: +₹{profit}\n"
                        f"💼 Total Demo Balance: ₹{virtual_balance:.2f}"
                    )
                # SL Hit
                elif curr_price <= pos['sl']:
                    loss = round((entry - curr_price) * qty, 2)
                    virtual_balance += (curr_price * qty)
                    closed.append(symbol)
                    send_alert(
                        f"🛑 *STOP LOSS HIT!*\n\n"
                        f"📉 *Stock:* {symbol} ({pos['style']})\n"
                        f"💰 Exit Price: ₹{curr_price:.2f}\n"
                        f"⚠️ Loss: -₹{loss}\n"
                        f"💼 Total Demo Balance: ₹{virtual_balance:.2f}"
                    )

            # SHORT / SELL trades
            elif pos['type'] == "SELL":
                if not pos['trailed'] and curr_price <= entry * 0.985:
                    pos['sl'] = entry
                    pos['trailed'] = True
                    send_alert(f"🛡️ *TRAILING SL:* {symbol} Stop Loss entry pe move ho gaya.")

                if curr_price <= pos['target']:
                    profit = round((entry - curr_price) * qty, 2)
                    virtual_balance += ((entry - curr_price) * qty) + (entry * qty)
                    closed.append(symbol)
                    send_alert(f"🎯 *TARGET HIT (SHORT):* {symbol} | Profit: +₹{profit} | Balance: ₹{virtual_balance:.2f}")
                elif curr_price >= pos['sl']:
                    loss = round((curr_price - entry) * qty, 2)
                    virtual_balance -= loss
                    closed.append(symbol)
                    send_alert(f"🛑 *SL HIT (SHORT):* {symbol} | Loss: -₹{loss} | Balance: ₹{virtual_balance:.2f}")

        except Exception as e:
            print(f"Tracking error {symbol}: {e}")

    for sym in closed:
        del open_positions[sym]

def scan_market():
    global virtual_balance
    print(f"\n[{time.strftime('%H:%M:%S')}] Active Positions: {len(open_positions)} | Demo Balance: ₹{virtual_balance:.2f}")
    
    # Pehle purane open trades track karein
    manage_open_positions()

    for symbol in WATCHLIST:
        if symbol in open_positions:
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
                
                # Ek trade par max ₹2500 virtual allocation (Risk management)
                trade_fund = min(2500.0, virtual_balance)
                qty = int(trade_fund // curr_close)
                if qty < 1:
                    continue

                # 1. BUY BREAKOUT
                if curr_close > high_20:
                    sl = round(curr_close * (1 - sl_pct), 2)
                    tgt = round(curr_close * (1 + tgt_pct), 2)
                    virtual_balance -= (curr_close * qty)
                    
                    open_positions[symbol] = {
                        'type': 'BUY', 'entry': curr_close, 'qty': qty,
                        'sl': sl, 'target': tgt, 'style': style_name, 'trailed': False
                    }

                    msg = (
                        f"🚀 *DEMO TRADE ENTRY: BUY*\n\n"
                        f"📊 *Type:* {style_name}\n"
                        f"📈 *Stock:* {symbol}\n"
                        f"💵 *Entry:* ₹{curr_close:.2f} | *Qty:* {qty}\n"
                        f"🔥 *Volume:* {vol_ratio:.1f}x Blast\n"
                        f"🎯 *Target:* ₹{tgt}\n"
                        f"🛑 *Initial SL:* ₹{sl}\n"
                        f"💼 Rem. Demo Balance: ₹{virtual_balance:.2f}\n\n"
                        f"👉 *Action:* Trailing SL active rahega!"
                    )
                    send_alert(msg)

                # 2. SELL / SHORT BREAKDOWN
                elif curr_close < low_20:
                    sl = round(curr_close * (1 + sl_pct), 2)
                    tgt = round(curr_close * (1 - tgt_pct), 2)
                    
                    open_positions[symbol] = {
                        'type': 'SELL', 'entry': curr_close, 'qty': qty,
                        'sl': sl, 'target': tgt, 'style': style_name, 'trailed': False
                    }

                    msg = (
                        f"🔻 *DEMO TRADE ENTRY: SELL/SHORT*\n\n"
                        f"📊 *Type:* {style_name}\n"
                        f"📉 *Stock:* {symbol}\n"
                        f"💵 *Entry:* ₹{curr_close:.2f} | *Qty:* {qty}\n"
                        f"🔥 *Volume:* {vol_ratio:.1f}x Panic Selling\n"
                        f"🎯 *Target:* ₹{tgt}\n"
                        f"🛑 *SL:* ₹{sl}\n"
                        f"💼 Demo Balance: ₹{virtual_balance:.2f}"
                    )
                    send_alert(msg)

        except Exception as e:
            print(f"Error checking {symbol}: {e}")

# Startup Notification
send_alert(
    f"🤖 *Paper Trading & Breakout Bot Live!*\n\n"
    f"💰 *Demo Balance:* ₹{virtual_balance:.2f}\n"
    f"🏷️ *Modes Active:* Scalping, Intraday, Swing\n"
    f"🛡️ *Trailing SL:* Auto-shift on +1.5% profit\n"
    f"📡 Monitoring live market..."
)

while True:
    scan_market()
    time.sleep(300)
