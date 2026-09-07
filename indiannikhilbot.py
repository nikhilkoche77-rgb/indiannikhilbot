import time
import requests
import yfinance as yf

# --- APNI DETAILS DAALEIN ---
TELEGRAM_TOKEN = "8876905313:AAHWQ8cD9jADvepC4lQE1psRH9WOxxL21qA"
CHAT_ID = "1345385952"

# Stocks ki watchlist (IFCI, PFC, Patanjali jaise high-momentum stocks)
WATCHLIST = [
    "IFCI.NS", "PFC.NS", "PATANJALI.NS", "TATASTEEL.NS", 
    "BEL.NS", "BHEL.NS", "RELIANCE.NS", "TATAMOTORS.NS"
]

def send_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"Alert error: {e}")

def scan_market():
    print(f"[{time.strftime('%H:%M:%S')}] Scanning watchlist for Big Moves...")
    for symbol in WATCHLIST:
        try:
            # 15-minute candles fetch karna
            df = yf.download(tickers=symbol, period="5d", interval="15m", progress=False)
            if len(df) < 25:
                continue

            # Multi-index fix
            if isinstance(df.columns, tuple):
                df.columns = [col[0] for col in df.columns]

            # 20-candle Volume Average aur High/Low calculate karna
            df['Vol_Avg'] = df['Volume'].rolling(window=20).mean()
            df['High_20'] = df['High'].shift(1).rolling(window=20).max()
            df['Low_20'] = df['Low'].shift(1).rolling(window=20).min()

            curr_close = float(df['Close'].iloc[-1])
            curr_vol = float(df['Volume'].iloc[-1])
            avg_vol = float(df['Vol_Avg'].iloc[-1])
            high_20 = float(df['High_20'].iloc[-1])
            low_20 = float(df['Low_20'].iloc[-1])

            # Condition: Volume 2x se zyada ho normal se
            is_volume_spike = curr_vol > (avg_vol * 2.0)

            # 1. BIG BULLISH BREAKOUT (Like IFCI)
            if curr_close > high_20 and is_volume_spike:
                sl = round(curr_close * 0.985, 2)       # 1.5% SL
                tgt = round(curr_close * 1.04, 2)       # 4% Target
                
                msg = (
                    f"🚀 *BIG BULLISH BREAKOUT!*\n\n"
                    f"📈 *Stock:* {symbol}\n"
                    f"💰 *Price:* ₹{curr_close:.2f}\n"
                    f"📊 *Volume:* {round(curr_vol/avg_vol, 1)}x Spike!\n"
                    f"🎯 *Target:* ₹{tgt}\n"
                    f"🛑 *SL:* ₹{sl}\n\n"
                    f"👉 Groww app me chart check karein!"
                )
                send_alert(msg)
                print(f"Alert sent for {symbol} (BUY)")

            # 2. BIG CRASH / BREAKDOWN (Like PFC/Patanjali)
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
send_alert("✅ *Breakout Bot Online!* Laptop se market monitoring shuru ho gayi hai.")

# Har 5 minute me background me scan chalega
while True:
    scan_market()
    time.sleep(300)
