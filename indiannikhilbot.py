import time
import requests
import yfinance as yf

# --- APNI DETAILS ---
TELEGRAM_TOKEN = "8876905313:AAHWQ8cD9jADvepC4lQE1psRH9WOxxL21qA"
CHAT_ID = "1345385952"

# Small Capital Ko Fast Grow Karne Wale High-Momentum Stocks
WATCHLIST = [
    # ⚡ Super High Momentum PSU & Power (Big Moves)
    "IFCI.NS", "PFC.NS", "RECLTD.NS", "IREDA.NS", "SJVN.NS", "NHPC.NS", 
    "BHEL.NS", "BEL.NS", "HUDCO.NS", "NBCC.NS", "IRFC.NS", "RVNL.NS", 
    "RAILTEL.NS", "IRCON.NS", "RITES.NS", "MAZDOCK.NS", "COCHINSHIP.NS",

    # 🚀 High Beta Volatility (Penny to Midcap Movers)
    "SUZLON.NS", "RPOWER.NS", "JPPOWER.NS", "IDEA.NS", "YESBANK.NS", 
    "PATANJALI.NS", "GMRINFRA.NS", "IDFCFIRSTB.NS", "PNB.NS", "UNIONBANK.NS",
    "BANKINDIA.NS", "CENTRALBK.NS", "UCOBANK.NS", "IOB.NS",

    # 🔥 Metals & Energy
    "TATASTEEL.NS", "SAIL.NS", "NMDC.NS", "NATIONALUM.NS", "HINDALCO.NS", 
    "JINDALSTEL.NS", "VEDL.NS", "COALINDIA.NS", "ONGC.NS", "OIL.NS",

    # 📈 High-Volume Midcaps & New-Age
    "ZOMATO.NS", "PAYTM.NS", "NYKAA.NS", "DELHIVERY.NS", "POLICYBZR.NS",
    "MOTHERSON.NS", "TATACHEM.NS", "ASHOKLEY.NS", "EXIDEIND.NS",

    # 🎯 Fast Swing Financials
    "ABCAPITAL.NS", "MANAPPURAM.NS", "MUTHOOTFIN.NS", "CANBK.NS", "BANDHANBNK.NS",
    "FEDERALBNK.NS", "POONAWALLA.NS", "L&TFH.NS", "CHOLAFIN.NS"
]

def send_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print(f"Alert error: {e}")

def scan_market():
    print(f"\n[{time.strftime('%H:%M:%S')}] Scanning {len(WATCHLIST)} High-Momentum Stocks...")
    for symbol in WATCHLIST:
        try:
            time.sleep(0.2)  # Server safe delay
            df = yf.download(tickers=symbol, period="5d", interval="15m", progress=False)
            
            if df is None or df.empty or len(df) < 25:
                continue

            if hasattr(df.columns, 'levels'):
                df.columns = [col[0] for col in df.columns]

            # Calculations
            df['Vol_Avg'] = df['Volume'].rolling(window=20).mean()
            df['High_20'] = df['High'].shift(1).rolling(window=20).max()
            df['Low_20'] = df['Low'].shift(1).rolling(window=20).min()

            curr_close = float(df['Close'].iloc[-1])
            curr_vol = float(df['Volume'].iloc[-1])
            avg_vol = float(df['Vol_Avg'].iloc[-1])
            high_20 = float(df['High_20'].iloc[-1])
            low_20 = float(df['Low_20'].iloc[-1])

            # 2x Volume Burst
            is_volume_spike = curr_vol > (avg_vol * 2.0)

            # 1. BIG BULLISH BREAKOUT
            if curr_close > high_20 and is_volume_spike:
                sl = round(curr_close * 0.985, 2)
                tgt = round(curr_close * 1.04, 2)
                
                msg = (
                    f"🚀 *BIG BULLISH BREAKOUT!*\n\n"
                    f"📈 *Stock:* {symbol}\n"
                    f"💰 *Price:* ₹{curr_close:.2f}\n"
                    f"📊 *Volume:* {round(curr_vol/avg_vol, 1)}x Spike!\n"
                    f"🎯 *Target:* ₹{tgt}\n"
                    f"🛑 *SL:* ₹{sl}\n\n"
                    f"👉 Groww app me check karein!"
                )
                send_alert(msg)
                print(f"Alert sent for {symbol} (BUY)")

            # 2. BIG BREAKDOWN / CRASH
            elif curr_close < low_20 and is_volume_spike:
                sl = round(curr_close * 1.015, 2)
                tgt = round(curr_close * 0.96, 2)
                
                msg = (
                    f"🔻 *BIG BREAKDOWN / CRASH!*\n\n"
                    f"📉 *Stock:* {symbol}\n"
                    f"💰 *Price:* ₹{curr_close:.2f}\n"
                    f"📊 *Volume:* {round(curr_vol/avg_vol, 1)}x Spike!\n"
                    f"🎯 *Target (Short):* ₹{tgt}\n"
                    f"🛑 *SL:* ₹{sl}\n\n"
                    f"👉 Heavy selling alert! Check Groww."
                )
                send_alert(msg)
                print(f"Alert sent for {symbol} (SELL)")

        except Exception as e:
            print(f"Error checking {symbol}: {e}")

# Startup alert
send_alert(f"✅ *Scanner Active!* Ab {len(WATCHLIST)} High-Momentum stocks track ho rahe hain.")

# 5-minute loop
while True:
    scan_market()
    time.sleep(300)
