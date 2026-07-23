#!/usr/bin/env python3
"""
EVALON VIP SIGNALS BOT v12 - Full Code Update
"""

import os, json, uuid, time, logging, asyncio, threading, urllib.request, tempfile
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
# KEEP-ALIVE (Prevents Render from sleeping)
# ============================================================
class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK - EVALON BOT RUNNING")
    def log_message(self, *args):
        pass

def start_keep_alive():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), _HealthHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    logger.info(f"Keep-alive server started on port {port}")

def _self_ping_loop():
    port = int(os.environ.get("PORT", 8080))
    url  = f"http://localhost:{port}/"
    time.sleep(30)
    while True:
        try:
            urllib.request.urlopen(url, timeout=10)
            logger.info("Self-ping OK — bot still awake ✅")
        except Exception as e:
            logger.warning(f"Self-ping failed: {e}")
        time.sleep(300)

def start_self_ping():
    t = threading.Thread(target=_self_ping_loop, daemon=True)
    t.start()
    logger.info("Self-ping loop started (every 5 min)")

# ============================================================
# POSTGRESQL (Render Persistent Database)
# ============================================================
DATABASE_URL = os.environ.get("DATABASE_URL", "")

def _get_pg_conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def _pg_init():
    if not DATABASE_URL:
        return
    try:
        conn = _get_pg_conn()
        cur  = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS kv_store (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)
        conn.commit()
        cur.close(); conn.close()
        logger.info("PostgreSQL connected & table ready ✅")
    except Exception as e:
        logger.warning(f"PostgreSQL init error: {e}")

def _pg_get(key):
    if not DATABASE_URL:
        return None
    try:
        conn = _get_pg_conn()
        cur  = conn.cursor()
        cur.execute("SELECT value FROM kv_store WHERE key = %s", (key,))
        row = cur.fetchone()
        cur.close(); conn.close()
        if row:
            return json.loads(row["value"])
    except Exception as e:
        logger.warning(f"PG GET {key}: {e}")
    return None

def _pg_set(key, value):
    if not DATABASE_URL:
        return False
    try:
        conn = _get_pg_conn()
        cur  = conn.cursor()
        cur.execute("""
            INSERT INTO kv_store (key, value)
            VALUES (%s, %s)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
        """, (key, json.dumps(value, ensure_ascii=False)))
        conn.commit()
        cur.close(); conn.close()
        return True
    except Exception as e:
        logger.warning(f"PG SET {key}: {e}")
        return False

supabase = DATABASE_URL

BOT_TOKEN      = os.environ.get("BOT_TOKEN")
ADMIN_ID       = 8535925646
CHANNEL_INVITE = "https://t.me/+mRNfGaNhz3RkZGRk"
SUPPORT_URL    = "https://t.me/EvalonwinnersBot"
DATA_DIR       = os.environ.get("DATA_DIR", "/tmp/data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_FILE        = os.path.join(DATA_DIR, "vip_users.json")
SIGNALS_FILE   = os.path.join(DATA_DIR, "active_signals.json")

BUY_STICKER           = "CAACAgQAAxkBAAN5ag0iEgRxrB_K9cJB6DguCNtx8GYAAsYQAAIRhYhR9RehjBho_pQ7BA"
SELL_STICKER          = "CAACAgQAAxkBAAN9ag0iH7PojN43V6hG_WdXf04VzBcAAh4QAAInGpBRarR99lasOK87BA"
WIN_STICKER           = "CAACAgEAAxkBAAONag0kQjHKqljsE_rIjhS4X4O_f00AAjkDAAJ1HiBEydhI9OJQ7fA7BA"
LOSS_STICKER          = "CAACAgEAAxkBAAORag0kl_qn_x6XnUYgz4JOPj1tbt8AApcCAAI3JzBHMzsR_0p1m807BA"
SESSION_CLOSE_STICKER = "CAACAgQAAxkBAAOFag0jJmtZPuZi72d6Ous1Qj8oT08AAvYQAALdM4lR8Oultiz5ylM7BA"
USE_STICKERS          = True

PAIR_ALIASES = {
    "EURUSD":"EUR/USD","GBPUSD":"GBP/USD","USDJPY":"USD/JPY","USDCHF":"USD/CHF",
    "AUDUSD":"AUD/USD","NZDUSD":"NZD/USD","USDCAD":"USD/CAD","EURGBP":"EUR/GBP",
    "EURJPY":"EUR/JPY","EURAUD":"EUR/AUD","EURCAD":"EUR/CAD","EURCHF":"EUR/CHF",
    "GBPJPY":"GBP/JPY","GBPAUD":"GBP/AUD","GBPCAD":"GBP/CAD","GBPCHF":"GBP/CHF",
    "AUDJPY":"AUD/JPY","AUDCAD":"AUD/CAD","AUDCHF":"AUD/CHF","AUDNZD":"AUD/NZD",
    "NZDJPY":"NZD/JPY","NZDCAD":"NZD/CAD","CHFJPY":"CHF/JPY","CADJPY":"CAD/JPY",
    "XAUUSD":"XAU/USD","XAGUSD":"XAG/USD","BTCUSD":"BTC/USD","ETHUSD":"ETH/USD",
    "BNBUSD":"BNB/USD","XRPUSD":"XRP/USD","SOLUSD":"SOL/USD","DOGEUSD":"DOGE/USD",
    "US30":"US30","SPX500":"SPX500","NAS100":"NAS100","GER40":"GER40",
    "UK100":"UK100","JPN225":"JPN225","FRA40":"FRA40","AUS200":"AUS200",
}

def normalize_pair(raw):
    r = raw.upper().replace("/","").replace("-","").replace(" ","")
    return PAIR_ALIASES.get(r, raw.upper())

def parse_signal(text):
    parts = text.strip().split()
    if len(parts) < 2:
        return None
    try:
        expiry = int(parts[1])
    except:
        return None
    return normalize_pair(parts[0]), expiry

def current_time_utc():
    return datetime.now(timezone.utc).strftime("%H:%M UTC")

KAULI_MBIU = "👑 *ALWAYS EVALON TRADER IS THE KING OF BINARY* 👑"

VIP_RULES = (
    "--------------"+"\n"
    "📋 *RULES & MONEY MANAGEMENT:*\n\n"
    "1️⃣ INVEST ONLY 10% PER SIGNAL\n"
    "2️⃣ BINARY TRADING HAS RISKS — PROTECT YOUR CAPITAL\n"
    "3️⃣ IF WE LOSS, WE CLOSE SESSION & WAIT FOR ANOTHER DAY\n"
    "4️⃣ AVOID OVER-TRADING — DO NOT FORCE TRADES\n"
    "👑 EVALON WINNERS — WE RISE TOGETHER!\n"
    "--------------"+"\n"
)

SESSION_STATS = {"wins": 0, "losses": 0, "start_time": None}
SESSION_LOG   = []   

def load_db():
    if supabase:
        d = _pg_get("main_db")
        if d is not None: return d
    if os.path.exists(DB_FILE):
        with open(DB_FILE) as f: return json.load(f)
    return {"users": {}, "codes": {}}

def save_db(db):
    if supabase and _pg_set("main_db", db): return
    with open(DB_FILE, "w") as f: json.dump(db, f, indent=2, ensure_ascii=False)

def load_signals():
    if supabase:
        d = _pg_get("active_signals")
        if d is not None: return d
    if os.path.exists(SIGNALS_FILE):
        with open(SIGNALS_FILE) as f: return json.load(f)
    return {}

def save_signals(s):
    if supabase and _pg_set("active_signals", s): return
    with open(SIGNALS_FILE, "w") as f: json.dump(s, f, indent=2)

def get_user(uid):
    db = load_db(); key = str(uid)
    if key not in db["users"]:
        db["users"][key] = {
            "vip": False, "vip_code": None, "joined_channel": False, "name": "",
            "joined_date": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        save_db(db)
    return db["users"][key]

def update_user(uid, data):
    db = load_db(); key = str(uid)
    if key not in db["users"]: get_user(uid); db = load_db()
    db["users"][key].update(data); save_db(db)

def is_admin(uid):   return uid == ADMIN_ID
def is_vip(uid):     return get_user(uid).get("vip", False)
def get_vip_ids():   return [int(k) for k,v in load_db()["users"].items() if v.get("vip")]
def get_all_ids():   return [int(k) for k in load_db()["users"]]
def get_novip_ids(): return [int(k) for k,v in load_db()["users"].items() if not v.get("vip")]
def get_vip_count(): return sum(1 for v in load_db()["users"].values() if v.get("vip"))
def get_display_count(): return 1500 + get_vip_count()

def activate_code(code, uid, name):
    db = load_db(); code = code.strip().upper()
    if code not in db["codes"] or db["codes"][code].get("used"): return False
    days = db["codes"][code].get("duration_days", 30)
    now  = datetime.now()
    exp  = now + timedelta(days=days)
    exp_str = exp.strftime("%Y-%m-%d")
    db["codes"][code].update({
        "used": True, "used_by": str(uid), "used_name": name,
        "used_date": now.strftime("%Y-%m-%d %H:%M"), "expires_date": exp_str,
    })
    key = str(uid)
    if key not in db["users"]: db["users"][key] = {}
    db["users"][key].update({
        "vip": True, "vip_code": code, "name": name,
        "vip_expiry": exp_str, "joined_date": now.strftime("%Y-%m-%d"),
    })
    save_db(db); return True

# ============================================================
# MESSAGE TEMPLATES
# ============================================================
def msg_preparing(pair, expiry, custom_text=None):
    custom_line = f"📌 *STRATEGY NOTE: {custom_text}*\n" if custom_text else ""
    return (
        "🏆 *EVALON VVIP WINNERS* 🏆\n\n"
        "--------------"+"\n"
        f"📊 PAIR    : *{pair}*\n"
        f"⏳ EXPIRY  : *{expiry} MIN*\n"
        f"🕐 ENTRY   : *New Candle*\n"
        f"{custom_line}"
        f"⏰ TIME    : *{current_time_utc()}*\n"
        "📍 STATUS  : SIGNAL PREPARING...\n\n"
        "⚠️ *REMINDER:* Invest only 10% per signal. Protect your capital, binary trading has risks!\n"
        "--------------"+"\n\n"
        "🔥 STAY READY — ENTRY COMING SOON\n"
        "💎 VVIP MEMBERS ONLY"
    )

def msg_direction(pair, expiry, direction):
    arrow = "📈" if direction == "BUY" else "📉"
    color = "🟢" if direction == "BUY" else "🔴"
    return (
        "🏆 *EVALON VVIP WINNERS* 🏆\n\n"
        "--------------"+"\n"
        f"📊 PAIR      : *{pair}*\n"
        f"⏳ EXPIRY    : *{expiry} MIN*\n"
        f"🕐 ENTRY     : *New Candle*\n"
        f"⏰ TIME      : *{current_time_utc()}*\n"
        f"{arrow} DIRECTION : *{color} {direction}*\n"
        "--------------"+"\n\n"
        "⚡ *OPEN YOUR TRADE NOW!*\n"
        "💎 VVIP MEMBERS ONLY"
    )

def msg_win(pair, expiry, direction):
    return (
        "🏆 *EVALON VVIP WINNERS* 🏆\n\n"
        "--------------"+"\n"
        f"📊 PAIR      : *{pair}*\n"
        f"⏳ EXPIRY    : *{expiry} MIN*\n"
        f"📈 DIRECTION : *{direction}*\n"
        f"🏆 RESULT    : *WIN ✅ (10%)*\n"
        "--------------"+"\n\n"
        "💰 *Congratulations! Profit secured!*\n"
        "💎 VVIP MEMBERS ONLY"
    )

def msg_loss(pair, expiry, direction):
    return (
        "🏆 *EVALON VVIP WINNERS* 🏆\n\n"
        "--------------"+"\n"
        f"📊 PAIR      : *{pair}*\n"
        f"⏳ EXPIRY    : *{expiry} MIN*\n"
        f"📈 DIRECTION : *{direction}*\n"
        f"🔴 RESULT    : *LOSS (10%)*\n"
        "--------------"+"\n\n"
        "⚠️ *Loss recorded. As per our rules, consider closing session to protect capital!*\n"
        "💎 VVIP MEMBERS ONLY"
    )

def msg_session_end(wins=0, losses=0):
    win_pct = wins * 10
    loss_pct = losses * 10
    return (
        "🏆 *EVALON VVIP WINNERS* 🏆\n\n"
        "--------------\n"
        "🏁 *TRADING SESSION ENDED*\n"
        "--------------\n\n"
        "📊 *SESSION RESULTS SUMMARY:*\n"
        "--------------\n"
        f"✅ TOTAL WINS  : *Win {win_pct}%*\n"
        f"❌ TOTAL LOSSES: *Loss {loss_pct}%*\n"
        "--------------\n\n"
        "💡 *Capital protected successfully. See you next session!*\n"
        f"{KAULI_MBIU}"
    )

# ============================================================
# KEYBOARDS & HELPERS
# ============================================================
async def send_to_list(context, uid_list, text=None, sticker=None):
    async def _send_one(uid):
        try:
            if sticker:
                await context.bot.send_sticker(chat_id=uid, sticker=sticker, protect_content=True)
            elif text:
                await context.bot.send_message(chat_id=uid, text=text, parse_mode="Markdown", protect_content=True)
            return True
        except: return False
    results = await asyncio.gather(*[_send_one(uid) for uid in uid_list])
    return sum(1 for r in results if r)

def kb_join():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Our Channel", url=CHANNEL_INVITE)],
        [InlineKeyboardButton("✅ I Have Joined",    callback_data="check_join")],
    ])

def kb_locked():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔑 Enter VIP Code", callback_data="enter_code")],
        [InlineKeyboardButton("💬 Contact Admin",  url=SUPPORT_URL)],
    ])

def kb_support():
    return InlineKeyboardMarkup([[InlineKeyboardButton("💬 Contact Admin", url=SUPPORT_URL)]])

def kb_direction(sig_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📈 BUY",  callback_data=f"dir_BUY_{sig_id}"),
         InlineKeyboardButton("📉 SELL", callback_data=f"dir_SELL_{sig_id}")],
        [InlineKeyboardButton("❌ Cancel Signal", callback_data=f"dir_CANCEL_{sig_id}")]
    ])

def kb_result(sig_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ WIN",  callback_data=f"res_WIN_{sig_id}"),
         InlineKeyboardButton("❌ LOSS", callback_data=f"res_LOSS_{sig_id}")],
        [InlineKeyboardButton("🏁 End Session", callback_data="end_session")]
    ])

def kb_admin_start():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏰ Session 5 min",  callback_data="sess_30"),
         InlineKeyboardButton("⏰ Session 30 min", callback_data="sess_60")],
        [InlineKeyboardButton("🏁 End Session",    callback_data="end_session")],
    ])

def kb_session():
    return ReplyKeyboardMarkup([[KeyboardButton("SESSION")]], resize_keyboard=True)

# ============================================================
# HANDLERS
# ============================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    name = update.effective_user.first_name or "Trader"
    get_user(uid)
    update_user(uid, {"name": name})

    if is_admin(uid):
        await update.message.reply_text(
            f"⚡ *EVALON VIP ADMIN PANEL*\n👥 Total VIP Members: *{get_display_count()}*",
            parse_mode="Markdown", reply_markup=kb_admin_start()
        )
        await update.message.reply_text("🟢 Ready", reply_markup=kb_session())
        return

    u = get_user(uid)
    if not u.get("joined_channel"):
        await update.message.reply_text(
            f"👋 Welcome, *{name}!*\nPlease join our official channel first:",
            parse_mode="Markdown", reply_markup=kb_join(), protect_content=True
        )
        return

    if not is_vip(uid):
        await update.message.reply_text(
            f"👋 Welcome back, *{name}!*\n\n🔒 *VIP ACCESS REQUIRED*",
            parse_mode="Markdown", reply_markup=kb_locked(), protect_content=True
        )
        return

    await update.message.reply_text(
        f"👋 Welcome back, *{name}!* 💎\n\n⚡ *EVALON VIP SIGNALS ACTIVE*\n{KAULI_MBIU}",
        parse_mode="Markdown", reply_markup=kb_support(), protect_content=True
    )

async def _process_result(update, context, result, sig_id, query=None):
    signals   = load_signals()
    sig       = signals.get(sig_id, {}) if sig_id else {}
    pair      = sig.get("pair", "?")
    expiry    = sig.get("expiry", "?")
    direction = sig.get("direction", "?")
    msgs      = sig.get("msgs", {})

    if result == "WIN":
        SESSION_STATS["wins"] += 1
    else:
        SESSION_STATS["losses"] += 1

    SESSION_LOG.append({"pair": pair, "expiry": expiry, "direction": direction, "result": result})

    result_text = msg_win(pair, expiry, direction) if result == "WIN" else msg_loss(pair, expiry, direction)
    sticker_id  = WIN_STICKER if result == "WIN" else LOSS_STICKER

    async def _send_result_one(uid_str):
        uidint = int(uid_str)
        try:
            await context.bot.send_message(chat_id=uidint, text=result_text, parse_mode="Markdown", protect_content=True)
            if USE_STICKERS and sticker_id:
                await context.bot.send_sticker(chat_id=uidint, sticker=sticker_id, protect_content=True)
        except: pass

    await asyncio.gather(*[_send_result_one(uid_str) for uid_str in msgs])

    if sig_id and sig_id in signals:
        del signals[sig_id]; save_signals(signals)

    admin_summary = (
        f"🏆 *EVALON VVIP WINNERS* 🏆\n\n"
        f"📊 PAIR : *{pair}*\n"
        f"📈 RESULT : *{result} (10%)*\n\n"
        f"📊 Total Session - Wins: {SESSION_STATS['wins']*10}% | Losses: {SESSION_STATS['losses']*10}%"
    )
    if query:
        await query.edit_message_text(admin_summary, parse_mode="Markdown")
    else:
        await update.message.reply_text(admin_summary, parse_mode="Markdown")

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    uid  = q.from_user.id
    await q.answer()
    data = q.data

    if data in ("sess_30", "sess_60"):
        if not is_admin(uid): return
        SESSION_STATS["wins"] = SESSION_STATS["losses"] = 0
        SESSION_LOG.clear()
        SESSION_STATS["start_time"] = time.time()
        mins = 5 if data == "sess_30" else 30
        vip_ids = get_vip_ids()
        novip_ids = get_novip_ids()
        
        dual_text_1 = f"⏰ *SESSION STARTING IN {mins} MINUTES*\n{VIP_RULES}"
        dual_text_2 = "📢 *SESSION NOTICE:* Get your trading terminals ready, market action is about to begin!"
        
        for target_id in list(set(vip_ids + novip_ids)):
            try:
                await context.bot.send_message(chat_id=target_id, text=dual_text_1, parse_mode="Markdown", protect_content=True)
                await context.bot.send_message(chat_id=target_id, text=dual_text_2, parse_mode="Markdown", protect_content=True)
            except: pass

        await q.edit_message_text("✅ *Session alerts successfully sent to VIP and Non-VIP!*", parse_mode="Markdown")
        return

    if data == "end_session":
        if not is_admin(uid): return
        vip_ids = get_vip_ids()
        text = msg_session_end(SESSION_STATS["wins"], SESSION_STATS["losses"])
        await send_to_list(context, vip_ids, text=text)
        await send_to_list(context, vip_ids, sticker=SESSION_CLOSE_STICKER)
        await q.edit_message_text("🏁 *Session successfully ended and summary broadcasted.*", parse_mode="Markdown")
        return

    if data.startswith("dir_"):
        if not is_admin(uid): return
        parts  = data.split("_", 2)
        action = parts[1]; sig_id = parts[2]
        signals = load_signals()
        if sig_id not in signals: 
            await q.edit_message_text("⚠️ Signal not found.")
            return
        sig = signals[sig_id]; pair = sig["pair"]; expiry = sig["expiry"]
        msgs = sig["msgs"]

        if action == "CANCEL":
            del signals[sig_id]; save_signals(signals)
            await q.edit_message_text(f"❌ Signal *{pair}* cancelled.", parse_mode="Markdown")
            return

        direction_text = msg_direction(pair, expiry, action)
        sticker_id = BUY_STICKER if action == "BUY" else SELL_STICKER

        async def _send_direction(uid_str):
            uidint = int(uid_str)
            try: 
                await context.bot.send_message(chat_id=uidint, text=direction_text, parse_mode="Markdown", protect_content=True)
                if USE_STICKERS and sticker_id:
                    await context.bot.send_sticker(chat_id=uidint, sticker=sticker_id, protect_content=True)
            except: pass

        await asyncio.gather(*[_send_direction(uid_str) for uid_str in msgs])
        signals[sig_id]["direction"] = action; save_signals(signals)

        await q.edit_message_text(f"📈 *{action}* sent for *{pair}*!\nSelect result below 👇", parse_mode="Markdown", reply_markup=kb_result(sig_id))
        return

    if data.startswith("res_"):
        if not is_admin(uid): return
        parts  = data.split("_", 2)
        result = parts[1]; sig_id = parts[2]
        await _process_result(update, context, result, sig_id, query=q)
        return

    if data == "check_join":
        update_user(uid, {"joined_channel": True})
        try: await q.message.delete()
        except: pass
        await context.bot.send_message(chat_id=q.message.chat_id, text="✅ *Channel verified!*", parse_mode="Markdown", reply_markup=kb_locked())
        return

    if data == "enter_code":
        context.user_data["awaiting_code"] = True
        try: await q.message.delete()
        except: pass
        await context.bot.send_message(chat_id=q.message.chat_id, text="🔑 *Enter your VIP code below:*", parse_mode="Markdown")
        return

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    name = update.effective_user.first_name or "Trader"
    text = update.message.text.strip()

    if text == "SESSION":
        await start(update, context)
        return

    if is_admin(uid):
        if text.lower() == "/users":
            db = load_db()
            users_list = db.get("users", {})
            msg = f"👥 *TOTAL USERS ({len(users_list)}):*\n\n"
            for u_id, u_info in users_list.items():
                msg += f"ID: `{u_id}` — Name: *{u_info.get('name', 'N/A')}* — VIP: {u_info.get('vip', False)}\n"
            await update.message.reply_text(msg[:4000], parse_mode="Markdown")
            return

        # FEATURE 4: Direct text parser (mf. "sell sell" au "buy buy")
        lower_t = text.lower()
        if lower_t in ("sell sell", "sell", "buy buy", "buy"):
            signals = load_signals()
            if not signals:
                await update.message.reply_text("⚠️ Hakuna signal inayendelea (Active signal). Tafadhali tuma kwanza Pair na Expiry mfano: `EURUSD 1`", parse_mode="Markdown")
                return
            
            sig_id = list(signals.keys())[-1]
            sig = signals[sig_id]
            pair = sig["pair"]
            expiry = sig["expiry"]
            msgs = sig["msgs"]

            direction = "BUY" if "buy" in lower_t else "SELL"
            direction_text = msg_direction(pair, expiry, direction)
            sticker_id = BUY_STICKER if direction == "BUY" else SELL_STICKER

            async def _send_direction(uid_str):
                uidint = int(uid_str)
                try: 
                    await context.bot.send_message(chat_id=uidint, text=direction_text, parse_mode="Markdown", protect_content=True)
                    if USE_STICKERS and sticker_id:
                        await context.bot.send_sticker(chat_id=uidint, sticker=sticker_id, protect_content=True)
                except: pass

            await asyncio.gather(*[_send_direction(uid_str) for uid_str in msgs])
            signals[sig_id]["direction"] = direction; save_signals(signals)

            try: await update.message.delete()
            except: pass
            
            await context.bot.send_message(chat_id=uid, text=f"📈 *{direction}* imetumwa moja kwa moja kupitia neno *'{text}'*!\nChagua matokeo hapa chini 👇", parse_mode="Markdown", reply_markup=kb_result(sig_id))
            return

        is_universal = text.lower().startswith("/signal")
        clean_text = text[7:].strip() if is_universal else text

        parsed = parse_signal(clean_text)
        if parsed:
            pair, expiry = parsed
            custom_txt = clean_text[len(parsed[0])+len(str(parsed[1]))+2:].strip() or None
            
            target_ids = get_all_ids() if is_universal else get_vip_ids()
            if not target_ids: 
                await update.message.reply_text("⚠️ No users found in database.")
                return
            try: await update.message.delete()
            except: pass

            sent_msgs = {}
            async def _send_preparing(vid):
                try:
                    m = await context.bot.send_message(chat_id=vid, text=msg_preparing(pair, expiry, custom_txt), parse_mode="Markdown", protect_content=True)
                    return str(vid), m.message_id
                except: return None, None

            results = await asyncio.gather(*[_send_preparing(vid) for vid in target_ids])
            for vid_str, mid in results:
                if vid_str: sent_msgs[vid_str] = mid

            sig_id = f"{pair.replace('/','')}_{expiry}_{int(time.time())}"
            signals = load_signals()
            signals[sig_id] = {"pair": pair, "expiry": expiry, "custom_txt": custom_txt, "msgs": sent_msgs}
            save_signals(signals)

            await context.bot.send_message(chat_id=uid, text=f"✅ Signal broadcasted to *{len(target_ids)}* users!\nPair: {pair}\n\n*Au andika moja kwa moja 'buy' au 'sell' kutuma direction.*", parse_mode="Markdown", reply_markup=kb_direction(sig_id))
            return

    if text.upper().startswith("VIP-"):
        result = activate_code(text, uid, name)
        if result is True:
            await update.message.reply_text("✅ *VIP Access Activated Successfully!* 🎉", parse_mode="Markdown", reply_markup=kb_support())
        else:
            await update.message.reply_text("❌ *Invalid or already used VIP code.*", parse_mode="Markdown", reply_markup=kb_locked())

def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN environment variable not set!")
        return

    start_keep_alive()
    if DATABASE_URL:
        _pg_init()
        start_self_ping()

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("signal", handle_text))
    application.add_handler(CommandHandler("users", handle_text))
    application.add_handler(CallbackQueryHandler(buttons))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Evalon Signals Bot v12 started successfully ✅")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
