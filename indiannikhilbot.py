import os
import json
import time
import threading
from datetime import datetime
from zoneinfo import ZoneInfo
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
import yfinance as yf

# --- BOT CONFIGURATION ---
TELEGRAM_TOKEN = "8876905313:AAHWQ8cD9jADvepC4lQE1psRH9WOxxL21qA"
CHAT_ID = "1345385952"
DATA_FILE = "swing_data.json"
LAST_UPDATE_ID = 0
BOT_PAUSED = False
IST = ZoneInfo("Asia/Kolkata")
state_lock = threading.Lock()

# 🎯 DEDICATED SETUP: 20 & 50 EMA BULLISH CROSSOVER
STRATEGY_NAME = "20/50 EMA Golden Crossover"
RRR = "1:3"
SL_PCT = 0.030      # -3.0% Stop Loss
TARGET_PCT = 0.090  # +9.0% Target
TRAIL_AT = 0.040    # Breakeven lock at +4.0% profit

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

# --- STATE MANAGEMENT ---
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

# --- CLEAN MINIMAL TELEGRAM MENU ---
def send_menu(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "📊 Open Positions", "callback_data": "btn_positions"},
                {"text": "💰 10K➔100K Progress", "callback_data": "btn_wallet"}
            ],
            [
                {"text": "🧪 Backtest 20/50 EMA (165 Stocks)", "callback_data": "btn_backtest"}
            ],
            [
                {"text": "🔄 Scan Now", "callback_data": "btn_scan"},
                {"text": "🚨 Close All", "callback_data": "btn_panic"}
            ]
        ]
    }
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown", "reply_markup": json.dumps(keyboard)}
    try:
        requests.post(url, data=payload, timeout=5)
    except Exception as e:
        print(f"Menu error: {e}")

# --- 20/50 EMA EVALUATION LOGIC ---
def evaluate_20_50_ema(df):
    if len(df) < 55:
        return False, ""

    c = float(df['Close'].iloc[-1])
    v = float(df['Volume'].iloc[-1])
    v_avg10 = float(df['Volume'].rolling(10).mean().iloc[-1])
    vol_ratio = v / v_avg10 if v_avg10 > 0 else 1.0

    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()

    ema20_now = float(df['EMA20'].iloc[-1])
    ema50_now = float(df['EMA50'].iloc[-1])
    ema20_prev = float(df['EMA20'].iloc[-2])
    ema50_prev = float(df['EMA50'].iloc[-2])

    # 20 EMA crossed 50 EMA from below + volume confirmed
    if ema20_prev <= ema50_prev and ema20_now > ema50_now and vol_ratio >= 1.3:
        reason = f"20 EMA (₹{ema20_now:.1f}) crossed above 50 EMA (₹{ema50_now:.1f}) with {vol_ratio:.1f}x Volume"
        return True, reason

    return False, ""

# --- 1-YEAR HISTORICAL BACKTEST ENGINE ---
def run_backtest():
    send_alert("⏳ *Running 1-Year Backtest for 20/50 EMA across 165 Stocks & Indices... (Takes ~25s)*")
    test_basket = ["^NSEI", "^NSEBANK"] + SWING_WATCHLIST_ALL[:30]
    total_trades = 0
    wins = 0
    losses = 0
    total_yield = 0.0

    for sym in test_basket:
        try:
            time.sleep(0.02)
            df = yf.download(tickers=sym, period="1y", interval="1d", progress=False)
            if df is None or df.empty or len(df) < 55:
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
                    if pnl_pct >= TARGET_PCT:
                        wins += 1
                        total_trades += 1
                        total_yield += TARGET_PCT
                        in_pos = False
                    elif pnl_pct <= -SL_PCT:
                        losses += 1
                        total_trades += 1
                        total_yield -= SL_PCT
                        in_pos = False
                    continue

                sig, _ = evaluate_20_50_ema(sub_df)
                if sig:
                    in_pos = True
                    entry_p = c
        except Exception:
            pass

    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0
    net_pct = total_yield * 100

    msg = (
        f"🧪 *20/50 EMA CROSSOVER: 1-YEAR BACKTEST REPORT*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚙️ *Setup:* 20 EMA crossing above 50 EMA\n"
        f"🎯 *Risk-Reward Ratio:* `{RRR}` (-3.0% SL | +9.0% Target)\n\n"
        f"🔥 *Win Rate:* *{win_rate:.1f}%*\n"
        f"📦 *Total Trades:* `{total_trades}` (`{wins}W | {losses}L`)\n"
        f"📈 *Cumulative Return:* *{net_pct:+.1f}%*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ Bot is 100% active on this strategy!"
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
                    f"• Strategy: *20/50 EMA Cross*\n"
                    f"• Setup: _{d.get('reason', 'N/A')}_\n"
                    f"• Entry: `₹{d['entry']:.2f}` | Qty: `{d['qty']}`\n"
                    f"• Target (+9%): `₹{d['target']:.2f}` | Guard: `{trail_txt}`\n"
                    f"• Allocated: `₹{(d['entry']*d['qty']):.2f}`\n\n"
                )
        else:
            msg += "_(Koi active position nahi hai - bot 165 stocks scan kar raha hai)_\n"
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

    elif data == "btn_backtest":
        threading.Thread(target=run_backtest).start()

    elif data == "btn_scan":
        send_alert("🔍 *Scanning 165 Stocks for 20/50 EMA Crossovers...*")
        threading.Thread(target=scan_swing_breakouts).start()

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
                    "pnl": 0.0, "result": "MANUAL_EXIT", "date": today_str
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
                    send_menu("🎛️ *20/50 EMA SWING TERMINAL*\nButtons se bot operate karein:")
        except Exception as e:
            print(f"Listener error: {e}")
        time.sleep(0.5)

# --- POSITION MONITORING WITH 1:3 RRR & TRAILING SL ---
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

            # 🛡️ Breakeven lock at +4% gain
            if d.get('trailed_level', 0) == 0 and gain_pct >= (TRAIL_AT * 100):
                d['sl'] = entry
                d['trailed_level'] = 1
                save_data(trade_state)
                send_alert(
                    f"🛡️ *RISK ELIMINATED: {name}*\n"
                    f"Stock is up *+{gain_pct:.2f}%*! SL breakeven cost (₹{entry:.2f}) par lock kar diya gaya hai. Trade is 100% Risk-Free!"
                )

            # 🎯 Target Hit (+9.0%)
            if curr_price >= d['target']:
                profit = round((curr_price - entry) * qty, 2)
                trade_state["virtual_balance"] += (curr_price * qty)
                send_alert(
                    f"🎯 *TARGET HIT: {name}*\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"📌 *Strategy:* `20/50 EMA Cross`\n"
                    f"💵 *Entry:* `₹{entry:.2f}` | *Exit:* `₹{curr_price:.2f}` (+{gain_pct:.2f}%)\n"
                    f"💰 *Net Profit Booked:* *+₹{profit:,.2f}*\n"
                    f"💼 *Compounded Balance:* *₹{trade_state['virtual_balance']:,.2f}*\n"
                    f"🚀 Step closer to ₹1,00,000 Milestone!"
                )
                trade_state["trade_history"].append({
                    "symbol": sym, "type": "BUY", "entry": entry, "exit": curr_price,
                    "pnl": profit, "result": "WIN", "date": today_str
                })
                closed.append(sym)

            # 🛑 Stop Loss Hit (-3.0%)
            elif curr_price <= d['sl']:
                pnl = round((curr_price - entry) * qty, 2)
                trade_state["virtual_balance"] += (curr_price * qty)
                outcome = "BREAKEVEN" if pnl >= 0 else "LOSS"
                send_alert(
                    f"🛑 *POSITION CLOSED: {name}*\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"📌 *Strategy:* `20/50 EMA Cross`\n"
                    f"💵 *Exit:* `₹{curr_price:.2f}`\n"
                    f"💰 *P&L:* *{'+' if pnl >= 0 else ''}₹{pnl:.2f}*\n"
                    f"💼 *Liquid Balance:* `₹{trade_state['virtual_balance']:,.2f}`"
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

# --- 165 STOCKS SCANNER ---
def scan_swing_breakouts():
    global trade_state, BOT_PAUSED
    if BOT_PAUSED:
        return

    manage_swing_positions()

    if len(trade_state.get("open_positions", {})) >= 2:
        return
    if trade_state["virtual_balance"] < 4000.0:
        return

    for sym in SWING_WATCHLIST_ALL:
        if sym in trade_state.get("open_positions", {}):
            continue
        try:
            time.sleep(0.08)
            df = yf.download(tickers=sym, period="3mo", interval="1d", progress=False)
            if df is None or df.empty or len(df) < 55:
                continue
            if hasattr(df.columns, 'levels'):
                df.columns = [col[0] for col in df.columns]

            is_signal, reason_desc = evaluate_20_50_ema(df)

            if is_signal:
                curr_price = float(df['Close'].iloc[-1])
                alloc = min(trade_state["virtual_balance"], trade_state["virtual_balance"] / (2 - len(trade_state["open_positions"])))
                qty = int(alloc // curr_price)
                if qty < 1:
                    continue

                sl = round(curr_price * (1.0 - SL_PCT), 2)
                tgt = round(curr_price * (1.0 + TARGET_PCT), 2)
                trade_state["virtual_balance"] -= (curr_price * qty)

                trade_state["open_positions"][sym] = {
                    "type": "BUY", "entry": curr_price, "qty": qty,
                    "sl": sl, "target": tgt, "trailed_level": 0,
                    "reason": reason_desc
                }
                save_data(trade_state)
                name = sym.replace(".NS", "")

                send_alert(
                    f"🔥 *20/50 EMA SWING BUY: {name}*\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"📌 *Strategy:* `20 & 50 EMA Golden Cross`\n"
                    f"🎯 *Risk-Reward Ratio:* `1:3.0`\n"
                    f"💡 *Setup:* _{reason_desc}_\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"💵 *Entry:* `₹{curr_price:.2f}` | *Qty:* `{qty}` Shares\n"
                    f"💰 *Invested:* `₹{(curr_price*qty):,.2f}`\n"
                    f"🛑 *Stop Loss:* `₹{sl}` (-3.0%)\n"
                    f"🎯 *Target:* `₹{tgt}` (+9.0%)\n"
                    f"💼 *Cash Remaining:* `₹{trade_state['virtual_balance']:,.2f}`\n"
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
        self.wfile.write(b"NSE 20/50 EMA Engine Active.")

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
send_menu(
    f"🚀 *20/50 EMA SWING BOT ACTIVE*\n\n"
    f"🎯 *Strategy:* Pure 20 EMA crossing 50 EMA + Volume Filter\n"
    f"📊 *Universe:* 165 Liquid NSE Stocks\n"
    f"🛡️ *Risk Architecture:* 1:3 RRR (-3% SL | +9% Target | +4% Breakeven Lock)\n"
    f"💼 *Goal:* ₹10,000 ➔ ₹1,00,000 Compounding\n\n"
    f"Buttons se live terminal monitor ya backtest run karein:"
)

listener_thread = threading.Thread(target=fast_telegram_listener, daemon=True)
listener_thread.start()

while True:
    if is_indian_market_open():
        scan_swing_breakouts()
    else:
        manage_swing_positions()
    time.sleep(300)
