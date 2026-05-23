#!/usr/bin/env python3
"""
EVALON VIP SIGNALS BOT v5
Fixes: 1-9 applied + PostgreSQL persistent storage (Render)
"""

import os, json, uuid, time, logging, asyncio, threading, urllib.request, urllib.request
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
        pass  # Suppress access logs

def start_keep_alive():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), _HealthHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    logger.info(f"Keep-alive server started on port {port}")

# ============================================================
# SELF-PING (Prevents Render free tier from sleeping)
# ============================================================
def _self_ping_loop():
    """Ping own health endpoint every 5 minutes to stay awake."""
    port = int(os.environ.get("PORT", 8080))
    url  = f"http://localhost:{port}/"
    time.sleep(30)  # wait for server to fully start first
    while True:
        try:
            urllib.request.urlopen(url, timeout=10)
            logger.info("Self-ping OK — bot still awake ✅")
        except Exception as e:
            logger.warning(f"Self-ping failed: {e}")
        time.sleep(300)  # 5 minutes

def start_self_ping():
    t = threading.Thread(target=_self_ping_loop, daemon=True)
    t.start()
    logger.info("Self-ping loop started (every 5 min)")

# ============================================================
# POSTGRESQL (Render Persistent Database)
# ============================================================
DATABASE_URL = os.environ.get("DATABASE_URL", "")

def _get_pg_conn():
    """Get a fresh PostgreSQL connection."""
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def _pg_init():
    """Create kv_store table if not exists."""
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

# Alias for backward compat with existing code
supabase = DATABASE_URL  # Truthy if set, used as flag below

# ============================================================
# WATERMARK
# ============================================================
try:
    from PIL import Image, ImageDraw, ImageFont
    import io
    WATERMARK_ENABLED = True
except ImportError:
    WATERMARK_ENABLED = False

WATERMARK_TEXT = "@EVALONWINNERSBOT"

def add_watermark(image_bytes: bytes) -> bytes:
    if not WATERMARK_ENABLED:
        return image_bytes
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        w, h = img.size
        overlay = Image.new("RGBA", img.size, (0,0,0,0))
        draw = ImageDraw.Draw(overlay)
        font_size = max(20, w // 18)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
        except:
            font = ImageFont.load_default()
        bbox = draw.textbbox((0,0), WATERMARK_TEXT, font=font)
        tw = bbox[2]-bbox[0]; th = bbox[3]-bbox[1]
        ti = Image.new("RGBA", (tw+20, th+20), (0,0,0,0))
        td = ImageDraw.Draw(ti)
        td.text((3,3), WATERMARK_TEXT, font=font, fill=(0,0,0,120))
        td.text((1,1), WATERMARK_TEXT, font=font, fill=(255,255,255,180))
        rot = ti.rotate(330, expand=True)
        rw, rh = rot.size
        for y in range(-rh, h+rh, rh+60):
            for x in range(-rw, w+rw, rw+40):
                overlay.paste(rot, (x,y), rot)
        out = Image.alpha_composite(img, overlay).convert("RGB")
        buf = io.BytesIO()
        out.save(buf, format="JPEG", quality=90)
        buf.seek(0)
        return buf.read()
    except Exception as e:
        logger.warning(f"Watermark failed: {e}")
        return image_bytes

# ============================================================
# CONFIG
# ============================================================
BOT_TOKEN      = os.environ.get("BOT_TOKEN")
ADMIN_ID       = 8535925646
CHANNEL_INVITE = "https://t.me/+mRNfGaNhz3RkZGRk"
SUPPORT_URL    = "https://t.me/EvalonwinnersBot"
DATA_DIR       = os.environ.get("DATA_DIR", "/tmp/data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_FILE        = os.path.join(DATA_DIR, "vip_users.json")
SIGNALS_FILE   = os.path.join(DATA_DIR, "active_signals.json")
FEEDBACK_FILE  = os.path.join(DATA_DIR, "feedback.json")

BUY_STICKER           = "CAACAgQAAxkBAAN5ag0iEgRxrB_K9cJB6DguCNtx8GYAAsYQAAIRhYhR9RehjBho_pQ7BA"
SELL_STICKER          = "CAACAgQAAxkBAAN9ag0iH7PojN43V6hG_WdXf04VzBcAAh4QAAInGpBRarR99lasOK87BA"
WIN_STICKER           = "CAACAgEAAxkBAAONag0kQjHKqljsE_rIjhS4X4O_f00AAjkDAAJ1HiBEydhI9OJQ7fA7BA"
LOSS_STICKER          = "CAACAgEAAxkBAAORag0kl_qn_x6XnUYgz4JOPj1tbt8AApcCAAI3JzBHMzsR_0p1m807BA"
SESSION_START_STICKER = "CAACAgQAAxkBAAOBag0jCHARVYE6EAXkDcBZmUVSiUsAApwPAAL0rJFRZZ7MdT9IUvg7BA"
SESSION_CLOSE_STICKER = "CAACAgQAAxkBAAOFag0jJmtZPuZi72d6Ous1Qj8oT08AAvYQAALdM4lR8Oultiz5ylM7BA"
USE_STICKERS          = True

# ============================================================
# PAIRS
# ============================================================
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

# Signal format: EURUSD 1 → pair + expiry only
def parse_signal(text):
    parts = text.strip().split()
    if len(parts) < 2:
        return None
    try:
        expiry = int(parts[1])
    except:
        return None
    return normalize_pair(parts[0]), expiry

# Trade alert: admin sends number only e.g. "5" or "10"
def parse_trades_only(text):
    t = text.strip()
    if t.isdigit() and 1 <= int(t) <= 100:
        return int(t)
    return None

def current_time_utc():
    return datetime.now(timezone.utc).strftime("%H:%M UTC")

# ============================================================
# CONSTANTS
# ============================================================
KAULI_MBIU = "\U0001f451 *ALWAYS EVALON TRADER IS THE KING OF BINARY* \U0001f451"

WHY_WE_MOVED = (
    "━━━━━━━━━━━━━━"+"\n"
    "\U0001f525 *Why We Moved From Our VIP Channel To The Bot System* \U0001f525\n"
    "━━━━━━━━━━━━━━"+"\n\n"
    "Many people keep asking why we moved from our VIP channel with thousands of members into a private bot system.\n\n"
    "The answer is simple \u2014 we wanted a system that is *faster, safer, more organized, and more reliable* for real VIP members.\n\n"
    "The old VIP channel started facing several problems:\n\n"
    "\u2022 VIP links were being shared publicly\n"
    "\u2022 Some users accessed shared signals unfairly\n"
    "\u2022 Manual posting caused delays during busy market hours\n"
    "\u2022 Many members missed signals because messages were sent manually\n"
    "\u2022 Managing a large number of users became difficult\n"
    "\u2022 Manual approvals sometimes delayed access for new members\n\n"
    "To improve the overall experience, we created the bot system.\n\n"
    "\U0001f680 The bot delivers signals *faster, earlier, and automatically* without unnecessary delays.\n"
    "━━━━━━━━━━━━━━"+"\n"
)

VIP_RULES = (
    "━━━━━━━━━━━━━━"+"\n"
    "\U0001f4cb *RULES OF EVALON WINNERS:*\n\n"
    "1\ufe0f\u20e3 ONLY INVEST WHAT YOU CAN AFFORD TO LOSE\n"
    "2\ufe0f\u20e3 FOLLOW THE SIGNAL \u2014 AVOID EMOTIONS\n"
    "3\ufe0f\u20e3 NO MARTINGALE \u2014 PROTECT YOUR CAPITAL\n"
    "4\ufe0f\u20e3 WAIT FOR THE SIGNAL \u2014 NEVER TRADE ALONE\n"
    "5\ufe0f\u20e3 SET THE CORRECT EXPIRY TIME AS INSTRUCTED\n"
    "6\ufe0f\u20e3 ONE SIGNAL \u2014 ONE TRADE ONLY\n"
    "7\ufe0f\u20e3 DON'T CHASE LOSSES \u2014 REST AND CONTINUE\n"
    "8\ufe0f\u20e3 BE READY BEFORE THE SESSION STARTS\n"
    "9\ufe0f\u20e3 TRUST THE PROCESS \u2014 PROFIT COMES WITH PATIENCE\n"
    "\U0001f51f DISCIPLINE IS THE KEY TO SUCCESS\n"
    "1\ufe0f\u20e31\ufe0f\u20e3 NEVER SHARE SIGNALS WITH UNAUTHORIZED PEOPLE\n"
    "1\ufe0f\u20e32\ufe0f\u20e3 YOUR ACCOUNT IS YOUR SECRET \u2014 PROTECT IT\n"
    "1\ufe0f\u20e33\ufe0f\u20e3 NEVER BORROW MONEY TO INVEST \u2014 TOO RISKY\n"
    "1\ufe0f\u20e34\ufe0f\u20e3 TRADE WITH A CLEAR MIND \u2014 NOT ANGER OR ALCOHOL\n"
    "2\ufe0f\u20e30\ufe0f\u20e3 EVALON WINNERS \u2014 WE RISE TOGETHER!\n"
    "━━━━━━━━━━━━━━"+"\n"
)

SESSION_STATS = {"wins": 0, "losses": 0, "start_time": None}
BASE_MEMBERS  = 1500

# ============================================================
# DATABASE
# ============================================================
def _sb_get(key):
    return _pg_get(key)

def _sb_set(key, value):
    return _pg_set(key, value)

def load_db():
    if supabase:
        d = _sb_get("main_db")
        if d is not None: return d
    if os.path.exists(DB_FILE):
        with open(DB_FILE) as f: return json.load(f)
    return {"users": {}, "codes": {}}

def save_db(db):
    if supabase and _sb_set("main_db", db): return
    with open(DB_FILE, "w") as f: json.dump(db, f, indent=2, ensure_ascii=False)

def load_signals():
    if supabase:
        d = _sb_get("active_signals")
        if d is not None: return d
    if os.path.exists(SIGNALS_FILE):
        with open(SIGNALS_FILE) as f: return json.load(f)
    return {}

def save_signals(s):
    if supabase and _sb_set("active_signals", s): return
    with open(SIGNALS_FILE, "w") as f: json.dump(s, f, indent=2)

def load_feedback():
    if supabase:
        d = _sb_get("feedback")
        if d is not None: return d
    if os.path.exists(FEEDBACK_FILE):
        with open(FEEDBACK_FILE) as f: return json.load(f)
    return []

def save_feedback(fb):
    if supabase and _sb_set("feedback", fb): return
    with open(FEEDBACK_FILE, "w") as f: json.dump(fb, f, indent=2, ensure_ascii=False)

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

# FIX 3: display count = 1500 + real VIP count
def get_display_count():
    return BASE_MEMBERS + get_vip_count()

def activate_code(code, uid, name):
    db = load_db(); code = code.strip().upper()
    if code not in db["codes"] or db["codes"][code].get("used"): return False
    days = db["codes"][code].get("duration_days", 30)
    now  = datetime.now()
    exp  = now + timedelta(days=days)
    exp_str = exp.strftime("%Y-%m-%d")
    db["codes"][code].update({
        "used":         True,
        "used_by":      str(uid),
        "used_name":    name,
        "used_date":    now.strftime("%Y-%m-%d %H:%M"),
        "expires_date": exp_str,
    })
    key = str(uid)
    if key not in db["users"]: db["users"][key] = {}
    db["users"][key].update({
        "vip":        True,
        "vip_code":   code,
        "name":       name,
        "vip_expiry": exp_str,
        "joined_date": now.strftime("%Y-%m-%d"),
    })
    save_db(db); return True

# Duration options in days
VIP_DURATIONS = {
    "1w":  7,
    "1m":  30,
    "3m":  90,
    "6m":  180,
    "1y":  365,
}

def new_code(label, duration_key="1m"):
    code = "VIP-" + "-".join(uuid.uuid4().hex[:4].upper() for _ in range(3))
    db   = load_db()
    days = VIP_DURATIONS.get(duration_key, 30)
    db["codes"][code] = {
        "label":        label,
        "used":         False,
        "used_by":      None,
        "created":      datetime.now().strftime("%Y-%m-%d %H:%M"),
        "duration_key": duration_key,
        "duration_days": days,
        "expires_date": None,   # set when code is activated
    }
    save_db(db); return code, days

def is_market_day():
    return datetime.now(timezone.utc).weekday() < 5

def is_weekend():
    return datetime.now(timezone.utc).weekday() >= 5

WEEKEND_DAY_NAME = lambda: datetime.now(timezone.utc).strftime("%A")  # "Saturday" or "Sunday"

TUTORIAL_VIDEO = "BAACAgQAAxkBAAIFn2oRZ0HUGBuMA4GYy3E7cC4Bv32WAAKqHgACyDCJUL7jK5vNBqvvOwQ"
INVITE_LINK    = "https://t.me/EvalonwinnersBot?start=ref8535925646"

WEEKEND_VIP_MSGS = [
    "🎉 Happy {day}, *{name}!*\n\nEnjoy your weekend — rest well and recharge!\nWe will be back with signals on *Monday*. 💪\n\n🔥 Stay focused — the market never sleeps forever!\n\n👑 ALWAYS EVALON TRADER IS THE KING OF BINARY 👑",
    "😎 {day} vibes, *{name}!*\n\nNo signals today — enjoy your break!\nSee you bright and early on *Monday* ready to win! 🏆\n\n💎 Rest today. Profit Monday!\n\n👑 ALWAYS EVALON TRADER IS THE KING OF BINARY 👑",
    "🌟 Hey *{name}!* Happy {day}!\n\nMarkets are closed — take a break, spend time with family!\nWe resume *Monday* with fresh signals. 🚀\n\n👑 ALWAYS EVALON TRADER IS THE KING OF BINARY 👑",
    "🏖️ *{name}*, enjoy your {day}!\n\nThe best traders also know when to rest.\nSee you *Monday* — signals resume then! 💪\n\n👑 ALWAYS EVALON TRADER IS THE KING OF BINARY 👑",
]

WEEKEND_NOVIP_MSGS = [
    "🎉 Happy {day}, *{name}!*\n\nEnjoy your weekend!\nBut wait — are you still missing out on VIP signals? 🤔\n\n💎 *Don\'t worry — FREE spots are available!*\n\n🎰 *Spin & Win* a discount up to *70% OFF* VIP access!\n👥 *Invite friends* and earn rewards!\n\n👇 Join now and never miss a signal again:\n{link}\n\n👑 ALWAYS EVALON TRADER IS THE KING OF BINARY 👑",
    "😎 {day} greetings, *{name}!*\n\nWhile you relax, our VIP members are preparing for *Monday\'s big session!* 📊\n\n🚀 *Want to join them?*\n🎰 Spin for up to *70% OFF* VIP!\n👥 Invite friends and earn free access!\n\n👇 Tap here to get started:\n{link}\n\n👑 ALWAYS EVALON TRADER IS THE KING OF BINARY 👑",
    "🌟 Hey *{name}!*\n\nHappy {day}! No signals today — but Monday is coming fast! ⚡\n\n❓ *Still not VIP? Free spots are open!*\n🎰 Spin & Win — get up to *70% discount*!\n👥 Invite a friend — both of you benefit!\n\n👇 Don\'t miss out:\n{link}\n\n👑 ALWAYS EVALON TRADER IS THE KING OF BINARY 👑",
    "🏖️ Enjoy your {day}, *{name}!*\n\nOur VIP members are resting and ready for *Monday\'s session!* 💪\n\n💡 *You can join them — spots are still available!*\n🎰 Spin for a discount up to *70% OFF!*\n👥 Invite friends & earn rewards!\n\n👇 Start here:\n{link}\n\n👑 ALWAYS EVALON TRADER IS THE KING OF BINARY 👑",
]


# ============================================================
# MESSAGES
# ============================================================
def msg_preparing(pair, expiry, trades=1):
    tline = f"\U0001f4a5 TRADES  : *{trades}*\n" if trades > 1 else ""
    return (
        "\U0001f3c6 *EVALON VVIP WINNERS* \U0001f3c6\n\n"
        "━━━━━━━━━━━━━━"+"\n"
        f"\U0001f4ca PAIR    : *{pair}*\n"
        f"\u23f1 EXPIRY  : *{expiry} MIN*\n"
        f"{tline}"
        f"\U0001f550 TIME    : *{current_time_utc()}*\n"
        "\U0001f4cd STATUS  : SIGNAL PREPARING...\n\n"
        "\u26a0\ufe0f WAIT FOR DIRECTION\n"
        "━━━━━━━━━━━━━━"+"\n\n"
        "\U0001f525 STAY READY \u2014 ENTRY COMING SOON\n"
        "\U0001f48e VVIP MEMBERS ONLY"
    )

def msg_direction(pair, expiry, direction, trades=1):
    arrow = "\U0001f4c8" if direction == "BUY" else "\U0001f4c9"
    color = "\U0001f7e2" if direction == "BUY" else "\U0001f534"
    if trades > 1:
        multi = f"\n\U0001f525 *HIGH CONFIDENCE SIGNAL!*\n\U0001f4a5 *OPEN {trades} TRADES NOW!*\n"
    elif expiry >= 5:
        multi = "\n\U0001f525 *HIGH CONFIDENCE SIGNAL!*\n\U0001f4a5 *OPEN 5 \u2014 10 TRADES NOW!*\n"
    else:
        multi = "\n"
    return (
        "\U0001f3c6 *EVALON VVIP WINNERS* \U0001f3c6\n\n"
        "━━━━━━━━━━━━━━"+"\n"
        f"\U0001f4ca PAIR      : *{pair}*\n"
        f"\u23f1 EXPIRY    : *{expiry} MIN*\n"
        f"\U0001f550 ENTRY     : *{current_time_utc()}*\n"
        f"{arrow} DIRECTION : *{color} {direction}*\n"
        "━━━━━━━━━━━━━━"+"\n"
        f"{multi}"
        "\u26a1 *OPEN YOUR TRADE NOW!*\n"
        "\U0001f48e VVIP MEMBERS ONLY"
    )

def msg_win(pair, expiry, direction, count=1):
    return (
        "\U0001f3c6 *EVALON VVIP WINNERS* \U0001f3c6\n\n"
        "━━━━━━━━━━━━━━"+"\n"
        f"\U0001f4ca PAIR      : *{pair}*\n"
        f"\u23f1 EXPIRY    : *{expiry} MIN*\n"
        f"\U0001f4c8 DIRECTION : *{direction}*\n"
        f"\U0001f3c6 RESULT    : *WIN \u2705 x{count}*\n"
        "━━━━━━━━━━━━━━"+"\n\n"
        "\U0001f4b0 *Congratulations! Another profit secured!*\n"
        "\U0001f525 Stay focused \u2014 more signals coming!\n"
        "\U0001f48e VVIP MEMBERS ONLY"
    )

def msg_loss(pair, expiry, direction, count=1):
    return (
        "\U0001f3c6 *EVALON VVIP WINNERS* \U0001f3c6\n\n"
        "━━━━━━━━━━━━━━"+"\n"
        f"\U0001f4ca PAIR      : *{pair}*\n"
        f"\u23f1 EXPIRY    : *{expiry} MIN*\n"
        f"\U0001f4c8 DIRECTION : *{direction}*\n"
        f"\U0001f534 RESULT    : *LOSS x{count}*\n"
        "━━━━━━━━━━━━━━"+"\n\n"
        "\U0001f4aa *Stay strong! Every loss is a lesson!*\n"
        "\U0001f9e0 Protect your capital \u2014 next signal coming!\n"
        "\U0001f6ab No Martingale \u2014 trust the process!\n"
        "\U0001f48e VVIP MEMBERS ONLY"
    )

def msg_session_soon(minutes, is_vip=False):
    when = f"{minutes} minutes" if minutes < 60 else f"{minutes//60} hour"
    rules = f"\n{VIP_RULES}" if is_vip else "\n"
    return (
        "\U0001f3c6 *EVALON VVIP WINNERS* \U0001f3c6\n\n"
        "━━━━━━━━━━━━━━"+"\n"
        f"\u23f0 SESSION STARTING IN *{when.upper()}*\n"
        "━━━━━━━━━━━━━━"+"\n\n"
        "\U0001f4cb *Get ready:*\n"
        "\u2705 Open your binary broker account\n"
        "\u2705 Set correct expiry time\n"
        "\u2705 Wait for our signal\n"
        "\u2705 No Martingale \u2014 follow the plan\n"
        f"{rules}"
        "\U0001f525 Signals starting soon!\n"
        "\U0001f48e VVIP MEMBERS ONLY\n\n"
        f"{KAULI_MBIU}"
    )

def msg_session_end(wins=0, losses=0):
    total = wins + losses
    acc   = f"{(wins/total*100):.1f}%" if total > 0 else "N/A"
    # Calculate real session duration
    dur_line = ""
    if SESSION_STATS.get("start_time"):
        elapsed = int(time.time() - SESSION_STATS["start_time"])
        mins    = elapsed // 60
        if mins < 60:
            dur_line = f"\u23f1 DURATION : *{mins} min*\n"
        else:
            h = mins // 60; m = mins % 60
            dur_line = f"\u23f1 DURATION : *{h}h {m}min*\n"
    return (
        "\U0001f3c6 *EVALON VVIP WINNERS* \U0001f3c6\n\n"
        "━━━━━━━━━━━━━━\n"
        "\U0001f3c1 *TRADING SESSION ENDED*\n"
        "━━━━━━━━━━━━━━\n\n"
        "That's a wrap for today's session!\n\n"
        "\U0001f4ca *SESSION RESULTS:*\n"
        "━━━━━━━━━━━━━━\n"
        f"\u2705 WIN      : *{wins}*\n"
        f"\u274c LOSS     : *{losses}*\n"
        f"\U0001f4c8 ACCURACY : *{acc}*\n"
        f"{dur_line}"
        "━━━━━━━━━━━━━━\n\n"
        "\U0001f4aa Great discipline leads to consistent profits!\n"
        "\U0001f550 Next session will be announced soon!\n\n"
        "Thank you for trading with us!\n\n"
        f"{KAULI_MBIU}"
    )

def msg_cancelled(pair):
    return (
        "\U0001f3c6 *EVALON VVIP WINNERS* \U0001f3c6\n\n"
        "━━━━━━━━━━━━━━"+"\n"
        f"\U0001f4ca PAIR   : *{pair}*\n"
        "\u274c STATUS : *SIGNAL CANCELLED*\n"
        "━━━━━━━━━━━━━━"+"\n\n"
        "\u23ed Skip this one \u2014 next signal coming soon!\n"
        "\U0001f9e0 Patience is the key to success!\n"
        "\U0001f48e VVIP MEMBERS ONLY"
    )

# ============================================================
# SEND HELPERS
# ============================================================
async def send_to_list(context, uid_list, text=None, photo=None,
                       video=None, sticker=None, caption=None,
                       animation=None, reply_markup=None):
    sent = failed = 0
    for uid in uid_list:
        try:
            if photo:
                await context.bot.send_photo(chat_id=uid, photo=photo, caption=caption,
                    parse_mode="Markdown", reply_markup=reply_markup, protect_content=True)
            elif video:
                await context.bot.send_video(chat_id=uid, video=video, caption=caption,
                    parse_mode="Markdown", reply_markup=reply_markup, protect_content=True)
            elif animation:
                await context.bot.send_animation(chat_id=uid, animation=animation, caption=caption,
                    parse_mode="Markdown", reply_markup=reply_markup, protect_content=True)
            elif sticker:
                await context.bot.send_sticker(chat_id=uid, sticker=sticker, protect_content=True)
            elif text:
                await context.bot.send_message(chat_id=uid, text=text,
                    parse_mode="Markdown", reply_markup=reply_markup, protect_content=True)
            sent += 1
        except Exception as e:
            logger.warning(f"Send failed {uid}: {e}"); failed += 1
    return sent, failed

# ============================================================
# KEYBOARDS
# ============================================================
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

def kb_after_result():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏁 End Session", callback_data="end_session")]])

def kb_session_timing():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("⏰ 30 Minutes", callback_data="sess_30"),
        InlineKeyboardButton("⏰ 1 Hour",     callback_data="sess_60"),
    ]])

def kb_get_vip():
    return InlineKeyboardMarkup([[InlineKeyboardButton("💎 Get VIP Access", callback_data="enter_code")]])

def kb_feedback(session_id):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("⭐", callback_data=f"fb_{session_id}_1"),
        InlineKeyboardButton("⭐⭐", callback_data=f"fb_{session_id}_2"),
        InlineKeyboardButton("⭐⭐⭐", callback_data=f"fb_{session_id}_3"),
        InlineKeyboardButton("⭐⭐⭐⭐", callback_data=f"fb_{session_id}_4"),
        InlineKeyboardButton("⭐⭐⭐⭐⭐", callback_data=f"fb_{session_id}_5"),
    ]])

# FIX 1: admin /start — short panel + buttons
def kb_admin_start():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏰ Session 30 min", callback_data="sess_30"),
         InlineKeyboardButton("⏰ Session 1 hr",   callback_data="sess_60")],
        [InlineKeyboardButton("🏁 End Session",    callback_data="end_session")],
        [InlineKeyboardButton("❓ Help",            callback_data="admin_help")],
    ])

# ============================================================
# /start
# ============================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import random as _random
    uid  = update.effective_user.id
    name = update.effective_user.first_name or "Trader"
    get_user(uid)
    update_user(uid, {"name": name})

    if is_admin(uid):
        db_type = "✅ PostgreSQL" if DATABASE_URL else "⚠️ Local JSON"
        display = get_display_count()
        await update.message.reply_text(
            f"⚡ *EVALON VIP SIGNALS*\n💾 {db_type}    👤 Total VIP Members: *{display}*",
            parse_mode="Markdown", reply_markup=kb_admin_start()
        )
        return

    chat_id = update.effective_chat.id
    day = WEEKEND_DAY_NAME()

    if is_weekend():
        if is_vip(uid):
            msg = _random.choice(WEEKEND_VIP_MSGS).format(name=name, day=day)
            await update.message.reply_text(msg, parse_mode="Markdown")
        else:
            msg = _random.choice(WEEKEND_NOVIP_MSGS).format(name=name, day=day, link=INVITE_LINK)
            await update.message.reply_text(
                msg, parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🎰 Spin & Win Discount", url=INVITE_LINK),
                    InlineKeyboardButton("👥 Invite & Earn", url=INVITE_LINK),
                ]])
            )
        return

    u = get_user(uid)
    if not u.get("joined_channel"):
        await update.message.reply_text(
            f"👋 Welcome, *{name}!*\n\n"
            "⚡ *EVALON VIP SIGNALS*\n"
            "━━━━━━━━━━━━━━\n\n"
            "📦 *WHAT YOU GET AS VIP:*\n"
            "━━━━━━━━━━━━━━\n"
            "📊 Daily Trading Signals\n"
            "⏱ Multiple Expiry Times\n"
            "📈 BUY/SELL Direction\n"
            "✅ WIN/LOSS Results\n"
            "🔥 High Confidence Alerts\n"
            "📉 8-10 Trades Per Day — Monday to Friday\n"
            "📋 Session Start & End Notifications\n\n"
            "━━━━━━━━━━━━━━\n"
            "To access this bot, first join our official channel:\n\n"
            "📢 *Evalon Winners Channel*\n\n"
            "Tap *Join Our Channel* then *I Have Joined* 👇\n\n"
            f"{WHY_WE_MOVED}\n{KAULI_MBIU}",
            parse_mode="Markdown", reply_markup=kb_join()
        )
        await asyncio.sleep(1)
        await context.bot.send_video(
            chat_id=chat_id, video=TUTORIAL_VIDEO,
            caption="👆 *Watch how our VIP bot works!*\n\nSee exactly what you will receive as a VIP member. 🎯",
            parse_mode="Markdown", protect_content=True
        )
        return

    if not is_vip(uid):
        mday = "🟢 Market Open" if is_market_day() else "🔴 Weekend — resumes Monday."
        await update.message.reply_text(
            f"👋 Welcome back, *{name}!*\n\n"
            "⚡ *EVALON VIP SIGNALS*\n"
            "━━━━━━━━━━━━━━\n\n"
            "🔒 *VIP ACCESS REQUIRED*\n\n"
            "✅ Real market signals — Monday to Friday\n"
            "✅ Non-Martingale strategy only\n"
            "✅ High accuracy entries\n"
            "✅ Win/Loss updates after every trade\n"
            "✅ Consistent signal delivery during market hours\n\n"
            f"⏰ *Monday — Friday only* | {mday}\n\n"
            "━━━━━━━━━━━━━━\n\n"
            f"{WHY_WE_MOVED}\n"
            "🔑 Have a code? Tap below\n"
            "💬 VIP access available through admin approval 👇\n\n"
            f"{KAULI_MBIU}",
            parse_mode="Markdown", reply_markup=kb_locked()
        )
        await asyncio.sleep(1)
        await context.bot.send_video(
            chat_id=chat_id, video=TUTORIAL_VIDEO,
            caption="👆 *Watch how our VIP bot works!*\n\nGet your VIP code today and start receiving signals! 🚀",
            parse_mode="Markdown", protect_content=True
        )
        return

    mday = "🟢 Market Open" if is_market_day() else "🔴 Weekend — signals resume Monday."
    await update.message.reply_text(
        f"👋 Welcome back, *{name}!* 💎\n\n"
        "⚡ *EVALON VIP SIGNALS*\n"
        "━━━━━━━━━━━━━━\n\n"
        "🔒 *VIP ACCESS REQUIRED*\n\n"
        "✅ Real market signals — Monday to Friday\n"
        "✅ Non-Martingale strategy only\n"
        "✅ High accuracy entries\n"
        "✅ Win/Loss updates after every trade\n"
        "✅ Consistent signal delivery during market hours\n\n"
        f"⏰ *Monday — Friday only* | {mday}\n\n"
        "━━━━━━━━━━━━━━\n\n"
        f"{WHY_WE_MOVED}\n"
        "🔑 Have a code? Tap below\n"
        "💬 VIP access available through admin approval\n\n"
        f"{KAULI_MBIU}",
        parse_mode="Markdown", reply_markup=kb_support()
    )
    await asyncio.sleep(1)
    await context.bot.send_video(
        chat_id=chat_id, video=TUTORIAL_VIDEO,
        caption="👆 *How to use your VIP signals!*\n\nFollow every signal exactly as shown. Good luck! 🎯",
        parse_mode="Markdown", protect_content=True
    )


# ============================================================
# PROCESS WIN/LOSS (shared helper)
# ============================================================
async def _process_result(update, context, result, sig_id, count, query=None):
    signals   = load_signals()
    sig       = signals.get(sig_id, {}) if sig_id else {}
    pair      = sig.get("pair", "?")
    expiry    = sig.get("expiry", "?")
    direction = sig.get("direction", "?")
    msgs      = sig.get("msgs", {})

    if result == "WIN": SESSION_STATS["wins"] += count
    else:               SESSION_STATS["losses"] += count

    result_text = msg_win(pair, expiry, direction, count) if result == "WIN" else msg_loss(pair, expiry, direction, count)
    sticker_id  = WIN_STICKER if result == "WIN" else LOSS_STICKER

    for uid_str in msgs:
        uidint = int(uid_str)
        try:
            await context.bot.send_message(chat_id=uidint, text=result_text,
                parse_mode="Markdown", protect_content=True)
        except Exception as e: logger.warning(f"Result msg failed {uid_str}: {e}")
        if USE_STICKERS and sticker_id and "PASTE_" not in sticker_id:
            try:
                await context.bot.send_sticker(chat_id=uidint, sticker=sticker_id, protect_content=True)
            except Exception as e: logger.warning(f"Result sticker failed {uid_str}: {e}")

    if sig_id and sig_id in signals:
        del signals[sig_id]; save_signals(signals)

    icon  = "✅" if result == "WIN" else "❌"
    total = SESSION_STATS["wins"] + SESSION_STATS["losses"]
    acc   = f"{(SESSION_STATS['wins']/total*100):.1f}%" if total > 0 else "N/A"
    summary = (
        f"{icon} *{result} x{count}* sent for *{pair}*!\n\n"
        f"📊 Session: ✅ {SESSION_STATS['wins']} wins | ❌ {SESSION_STATS['losses']} losses | {acc}\n\n"
        "Tap End Session when done or send next signal."
    )
    if query:
        await query.edit_message_text(summary, parse_mode="Markdown", reply_markup=kb_after_result())
    else:
        await update.message.reply_text(summary, parse_mode="Markdown", reply_markup=kb_after_result())

# ============================================================
# BUTTONS
# ============================================================
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    uid  = q.from_user.id
    name = q.from_user.first_name or "Trader"
    chat = q.message.chat_id
    await q.answer()
    data = q.data

    # FIX 1: help button from start panel
    if data == "admin_help":
        if not is_admin(uid): return
        await _send_help(chat, context); return

    if data in ("sess_30", "sess_60"):
        if not is_admin(uid): return
        SESSION_STATS["wins"] = SESSION_STATS["losses"] = 0
        SESSION_STATS["start_time"] = time.time()
        mins     = 30 if data == "sess_30" else 60
        vip_ids  = get_vip_ids()
        novip_ids= get_novip_ids()
        await send_to_list(context, vip_ids, text=msg_session_soon(mins, is_vip=True))
        for nuid in novip_ids:
            try:
                await context.bot.send_message(chat_id=nuid,
                    text=msg_session_soon(mins, is_vip=False),
                    parse_mode="Markdown", reply_markup=kb_get_vip())
            except: pass
        await q.edit_message_text(
            "⏰ *Session alert sent!*\n\nWhen market is ready, tap below 👇",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🟢 Send Session Start Now", callback_data="send_start_now")],
                [InlineKeyboardButton("⚠️ Emergency / Delay",      callback_data="emergency")],
                [InlineKeyboardButton("🏁 End Session",             callback_data="end_session")],
            ])
        )
        return

    if data == "send_start_now":
        if not is_admin(uid): return
        vip_ids    = get_vip_ids()
        start_text = (
            "\U0001f3c6 *EVALON VVIP WINNERS* \U0001f3c6\n\n"
            "━━━━━━━━━━━━━━"+"\n"
            "\U0001f7e2 *SESSION IS STARTING NOW!*\n"
            "━━━━━━━━━━━━━━"+"\n\n"
            "\u2705 Get your charts ready\n"
            "\u2705 Set your expiry time\n"
            "\u2705 Wait for the signal\n\n"
            "\U0001f525 *First signal incoming!*\n"
            "\U0001f48e VVIP MEMBERS ONLY"
        )
        for vid in vip_ids:
            try: await context.bot.send_sticker(chat_id=vid, sticker=SESSION_START_STICKER, protect_content=True)
            except: pass
            try: await context.bot.send_message(chat_id=vid, text=start_text, parse_mode="Markdown", protect_content=True)
            except: pass
        await q.edit_message_text(
            "\U0001f7e2 *Session started!*\n\nSend your first signal now!",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⚠️ Emergency / Delay", callback_data="emergency")],
                [InlineKeyboardButton("🏁 End Session",        callback_data="end_session")],
            ])
        )
        return

    if data == "emergency":
        if not is_admin(uid): return
        context.user_data["awaiting_emergency"] = True
        await q.message.reply_text("⚠️ *Emergency Message*\n\nType your message — sent to VIP immediately.", parse_mode="Markdown")
        return

    # FIX 4 & 7: end session VIP only, clean admin msg
    if data == "end_session":
        if not is_admin(uid): return
        vip_ids    = get_vip_ids()
        text       = msg_session_end(SESSION_STATS["wins"], SESSION_STATS["losses"])
        session_id = str(int(time.time()))
        fb_text    = "\n\n━━━━━━━━━━━━━━━━━━\n\U0001f4dd *Rate today's session:*\nTap a number (1 = poor, 5 = excellent)"
        fb_kb      = kb_feedback(session_id)
        for vid in vip_ids:
            try: await context.bot.send_sticker(chat_id=vid, sticker=SESSION_CLOSE_STICKER, protect_content=True)
            except: pass
            try: await context.bot.send_message(chat_id=vid, text=text+fb_text,
                    parse_mode="Markdown", reply_markup=fb_kb, protect_content=True)
            except: pass
        sigs = load_signals(); sigs[f"session_{session_id}"] = {"session_id": session_id}; save_signals(sigs)
        # FIX 7: clean message
        await q.edit_message_text(
            "🏁 *Session ended!*\n\nTap below to see feedback 👇",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📊 View Feedback", callback_data=f"view_fb_{session_id}")]])
        )
        return

    if data.startswith("view_fb_"):
        if not is_admin(uid): return
        # Trigger full feedback (real + fake) same as /feedback command
        await feedback_cmd(update, context)
        return

    if data.startswith("fb_"):
        parts = data.split("_")
        session_id = parts[1]; rating = int(parts[2])
        context.user_data["fb_session"] = session_id
        context.user_data["fb_rating"]  = rating
        context.user_data["fb_waiting"] = True
        await q.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_message(chat_id=chat,
            text=f"Thank you! You rated: *{'⭐'*rating}*\n\nType a comment or /skip:",
            parse_mode="Markdown")
        return

    if data.startswith("dir_"):
        if not is_admin(uid): return
        parts  = data.split("_", 2)
        action = parts[1]; sig_id = parts[2]
        signals = load_signals()
        if sig_id not in signals: await q.edit_message_text("⚠️ Signal not found."); return
        sig = signals[sig_id]; pair = sig["pair"]; expiry = sig["expiry"]
        trades = sig.get("trades", 1); msgs = sig["msgs"]

        if action == "CANCEL":
            for uid_str, mid in msgs.items():
                try: await context.bot.edit_message_text(chat_id=int(uid_str), message_id=mid,
                        text=msg_cancelled(pair), parse_mode="Markdown")
                except: pass
            del signals[sig_id]; save_signals(signals)
            await q.edit_message_text(f"❌ Signal *{pair}* cancelled.", parse_mode="Markdown")
            return

        direction_text = msg_direction(pair, expiry, action, trades)
        sticker_id     = BUY_STICKER if action == "BUY" else SELL_STICKER
        for uid_str in msgs:
            uidint = int(uid_str)
            try: await context.bot.send_message(chat_id=uidint, text=direction_text, parse_mode="Markdown", protect_content=True)
            except Exception as e: logger.warning(f"Dir txt failed {uid_str}: {e}")
            if USE_STICKERS and sticker_id and "PASTE_" not in sticker_id:
                try: await context.bot.send_sticker(chat_id=uidint, sticker=sticker_id, protect_content=True)
                except Exception as e: logger.warning(f"Dir stk failed {uid_str}: {e}")
        signals[sig_id]["direction"] = action; save_signals(signals)

        arrow   = "📈" if action == "BUY" else "📉"
        color   = "🟢" if action == "BUY" else "🔴"
        display = get_display_count()
        # FIX 6: show display count
        await q.edit_message_text(
            f"{arrow} *{color} {action}* sent for *{pair}*!\n\n"
            f"📨 Sent to : *{display}* members\n\n"
            "Select result when trade closes 👇",
            parse_mode="Markdown", reply_markup=kb_result(sig_id)
        )
        return

    if data.startswith("res_"):
        if not is_admin(uid): return
        parts   = data.split("_", 2)
        result  = parts[1]; sig_id = parts[2]
        signals = load_signals()
        sig     = signals.get(sig_id, {})
        # Use last trade count sent (stored in signal), default 1
        count   = context.user_data.get("last_trades", 1)
        await _process_result(update, context, result, sig_id, count, query=q)
        return

    # FIX 5: clear feedback properly saved to Supabase
    if data == "clear_feedback":
        if not is_admin(uid): return
        save_feedback([])
        await q.edit_message_text("🗑️ *All feedback cleared!*", parse_mode="Markdown"); return

    if data == "check_join":
        update_user(uid, {"joined_channel": True, "name": name})
        try: await q.message.delete()
        except: pass
        mday = "🟢 Market open!" if is_market_day() else "🔴 Weekend — resumes Monday."
        if is_vip(uid):
            await context.bot.send_message(chat_id=chat,
                text=f"✅ *Joined! Welcome back, {name}!*\n\n{mday}",
                parse_mode="Markdown", reply_markup=kb_support())
        else:
            await context.bot.send_message(chat_id=chat,
                text=f"✅ *Channel joined! Welcome, {name}!*\n\n"
                     "🔒 *VIP ACCESS REQUIRED*\n\n"
                     "✅ Real market signals — Mon to Fri\n"
                     "✅ Non-Martingale strategy\n"
                     "✅ Win/Loss updates\n\n"
                     f"⏰ Mon–Fri only | {mday}\n\n"
                     "🔑 Have a VIP code? Tap below 👇",
                parse_mode="Markdown", reply_markup=kb_locked())
        return

    if data == "enter_code":
        context.user_data["awaiting_code"] = True
        try: await q.message.delete()
        except: pass
        await context.bot.send_message(chat_id=chat,
            text="🔑 *Enter your VIP code:*\n\nFormat: `VIP-XXXX-XXXX-XXXX`\n\nContact admin if you need one 👇",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💬 Contact Admin", url=SUPPORT_URL)]]))
        return

# ============================================================
# TEXT HANDLER
# ============================================================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    name = update.effective_user.first_name or "Trader"
    text = update.message.text.strip()

    if update.message.forward_date and not is_admin(uid):
        try: await update.message.delete()
        except: pass
        await update.message.reply_text("🔒 Forwarding is not allowed."); return

    if is_admin(uid):
        if text == "/skip": context.user_data["fb_waiting"] = False; return

        if context.user_data.get("awaiting_emergency"):
            context.user_data["awaiting_emergency"] = False
            vip_ids = get_vip_ids()
            await send_to_list(context, vip_ids, text=(
                "\U0001f3c6 *EVALON VVIP WINNERS* \U0001f3c6\n\n"
                "━━━━━━━━━━━━━━"+"\n⚠️ *IMPORTANT UPDATE*\n"+"━━━━━━━━━━━━━━"+"\n\n"
                f"{text}\n\n\U0001f48e VVIP MEMBERS ONLY"
            ))
            await update.message.reply_text("⚠️ *Emergency message sent!*", parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🟢 Send Session Start Now", callback_data="send_start_now")],
                    [InlineKeyboardButton("⚠️ Emergency / Delay", callback_data="emergency")],
                    [InlineKeyboardButton("🏁 End Session", callback_data="end_session")],
                ]))
            return

        # TRADES ONLY: admin sends number e.g. "5" or "10"
        trades_count = parse_trades_only(text)
        if trades_count is not None:
            vip_ids = get_vip_ids()
            if not vip_ids: await update.message.reply_text("⚠️ No VIP members yet."); return
            context.user_data["last_trades"] = trades_count
            trade_msg = f"💥 *OPEN {trades_count} TRADES NOW!* 💥"
            await send_to_list(context, vip_ids, text=trade_msg)
            try: await update.message.delete()
            except: pass
            return

        # SIGNAL: e.g. EURUSD 1
        parsed = parse_signal(text)
        if not parsed: return
        pair, expiry = parsed
        context.user_data["last_trades"] = 1  # reset on new signal
        vip_ids = get_vip_ids()
        if not vip_ids: await update.message.reply_text("⚠️ No VIP members yet."); return
        try: await update.message.delete()
        except: pass

        sent_msgs = {}
        for vid in vip_ids:
            try:
                m = await context.bot.send_message(chat_id=vid, text=msg_preparing(pair, expiry),
                    parse_mode="Markdown", protect_content=True)
                sent_msgs[str(vid)] = m.message_id
            except Exception as e: logger.warning(f"Send failed {vid}: {e}")

        sig_id = f"{pair.replace('/','').replace(' ','')}_{expiry}_{int(time.time())}"
        signals = load_signals()
        signals[sig_id] = {"pair": pair, "expiry": expiry,
                            "msgs": sent_msgs, "time": datetime.now().strftime("%H:%M")}
        save_signals(signals)

        display = get_display_count()
        await context.bot.send_message(chat_id=uid,
            text=f"✅ Signal sent to *{display}* members!\n\n"
                 f"📊 *{pair}*  |  ⏱ *{expiry} MIN*\n\n"
                 "Choose direction when ready 👇",
            parse_mode="Markdown", reply_markup=kb_direction(sig_id))
        return

    # USER: feedback
    if context.user_data.get("fb_waiting"):
        session_id = context.user_data.pop("fb_session", "")
        rating     = context.user_data.pop("fb_rating", 0)
        context.user_data["fb_waiting"] = False
        comment = text if text != "/skip" else ""
        fb_list = load_feedback()
        fb_list.append({"session_id": session_id, "user_id": uid, "name": name,
                         "rating": rating, "comment": comment, "date": datetime.now().strftime("%Y-%m-%d %H:%M")})
        save_feedback(fb_list)
        await update.message.reply_text("✅ *Thank you for your feedback!*\n\nSee you in the next session! 🎯",
            parse_mode="Markdown"); return

    if not context.user_data.get("awaiting_code"):
        if not is_vip(uid): await update.message.reply_text("🔒 Please enter your VIP code.", reply_markup=kb_locked())
        return

    code = text.upper(); context.user_data["awaiting_code"] = False
    if activate_code(code, uid, name):
        mday = "🟢 Market open — signals active!" if is_market_day() else "🔴 Weekend — signals resume Monday."
        await update.message.reply_text(
            f"✅ *VIP Access Activated! Welcome, {name}!* 🎉\n\n"
            "⚡ *EVALON VIP SIGNALS*\n\nYou are now a *VIP Member* 🎯\n\n"
            "✅ Real market signals — Mon to Fri\n✅ Non-Martingale strategy\n"
            f"✅ Win/Loss updates\n\n{mday}\n\nStay active — signals arrive here 📩",
            parse_mode="Markdown", reply_markup=kb_support())
    else:
        db   = load_db(); cdat = db["codes"].get(code)
        if cdat and cdat.get("used"):
            await update.message.reply_text(
                "❌ *This code has already been used!*\n\nContact admin for your own code:",
                parse_mode="Markdown", reply_markup=kb_locked())
        else:
            await update.message.reply_text("❌ *Invalid VIP code!*\n\nContact admin:",
                parse_mode="Markdown", reply_markup=kb_locked())

# ============================================================
# MEDIA — FIX 8: direct to VIP with watermark, no file_id
# ============================================================
async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        if context.user_data.get("fb_waiting"):
            await update.message.reply_text("✏️ Please send text only or /skip.", parse_mode="Markdown"); return
        if update.message.forward_date:
            try: await update.message.delete()
            except: pass
            await update.message.reply_text("🔒 Forwarding is not allowed.")
        return

    if context.user_data.get("awaiting_welcome_image"):
        context.user_data["awaiting_welcome_image"] = False
        msg = update.message
        if msg.photo:
            db = load_db(); db["welcome_image"] = msg.photo[-1].file_id; save_db(db)
            await update.message.reply_text("✅ *Welcome image saved!*", parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ Please send a photo only.")
        return

    # FIX 8: if /getid mode active, reply with file_id
    if context.user_data.get("awaiting_file_id"):
        context.user_data["awaiting_file_id"] = False
        msg = update.message; fid = None
        if msg.photo: fid = f"PHOTO: `{msg.photo[-1].file_id}`"
        elif msg.video: fid = f"VIDEO: `{msg.video.file_id}`"
        elif msg.animation: fid = f"GIF: `{msg.animation.file_id}`"
        if fid:
            await update.message.reply_text(f"📎 *FILE ID:*\n\n{fid}", parse_mode="Markdown"); return

    # Default: broadcast to VIP
    msg = update.message; vip_ids = get_vip_ids()
    if not vip_ids: await msg.reply_text("⚠️ No VIP members yet."); return
    sent = 0
    if msg.photo:
        try:
            file = await context.bot.get_file(msg.photo[-1].file_id)
            img  = await file.download_as_bytearray()
            wm   = add_watermark(bytes(img))
            bio  = __import__("io").BytesIO(wm); bio.name = "signal.jpg"
            sent, _ = await send_to_list(context, vip_ids, photo=bio, caption=msg.caption)
        except Exception as e:
            logger.warning(f"Watermark failed: {e}")
            sent, _ = await send_to_list(context, vip_ids, photo=msg.photo[-1].file_id, caption=msg.caption)
    elif msg.video:
        wm_caption = f"{msg.caption}\n\n📹 {WATERMARK_TEXT}" if msg.caption else f"📹 {WATERMARK_TEXT}"
        sent, _ = await send_to_list(context, vip_ids, video=msg.video.file_id, caption=wm_caption)
    elif msg.animation:
        sent, _ = await send_to_list(context, vip_ids, animation=msg.animation.file_id, caption=msg.caption)
    if sent:
        display = get_display_count()
        await msg.reply_text(f"✅ Sent to *{display}* members!", parse_mode="Markdown")

# ============================================================
# STICKER HANDLER
# ============================================================
async def handle_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        if update.message.forward_date:
            try: await update.message.delete()
            except: pass
            await update.message.reply_text("🔒 Forwarding is not allowed.")
        return
    sticker = update.message.sticker
    if not sticker: return
    fid = sticker.file_id
    # FIX 8: /getid mode for file_ids
    if context.user_data.get("awaiting_file_id"):
        context.user_data["awaiting_file_id"] = False
        await update.message.reply_text(
            f"📎 *STICKER FILE ID:*\n\n`{fid}`\n\nPaste into BUY/SELL/WIN/LOSS sticker variables.",
            parse_mode="Markdown"); return
    # Default: broadcast sticker
    vip_ids = get_vip_ids()
    if vip_ids:
        await send_to_list(context, vip_ids, sticker=fid)
        display = get_display_count()
        await update.message.reply_text(f"✅ Sticker sent to *{display}* members!", parse_mode="Markdown")

# ============================================================
# /getid — get file_id of next sticker/photo
# ============================================================
async def cmd_getid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    context.user_data["awaiting_file_id"] = True
    await update.message.reply_text("📎 *Send sticker or photo now*\n\nI will reply with the file\\_id.", parse_mode="Markdown")

# ============================================================
# /broadcast
# ============================================================
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid): return
    args    = context.args or []
    to_all  = args and args[0].lower() == "all"
    caption = " ".join(args[1:]) if to_all else " ".join(args)
    replied = update.message.reply_to_message
    targets = get_all_ids() if to_all else get_vip_ids()
    if not targets: await update.message.reply_text("⚠️ No users yet."); return
    sent = 0
    if replied:
        if replied.photo:
            try:
                file = await context.bot.get_file(replied.photo[-1].file_id)
                img  = await file.download_as_bytearray()
                wm   = add_watermark(bytes(img))
                bio  = __import__("io").BytesIO(wm); bio.name = "signal.jpg"
                sent, _ = await send_to_list(context, targets, photo=bio, caption=replied.caption or caption or None)
            except:
                sent, _ = await send_to_list(context, targets, photo=replied.photo[-1].file_id, caption=replied.caption or caption or None)
        elif replied.video:
            wm_caption = f"{replied.caption or caption or ''}\n\n📹 {WATERMARK_TEXT}".strip()
            sent, _ = await send_to_list(context, targets, video=replied.video.file_id, caption=wm_caption)
        elif replied.sticker: sent, _ = await send_to_list(context, targets, sticker=replied.sticker.file_id)
        elif replied.animation: sent, _ = await send_to_list(context, targets, animation=replied.animation.file_id, caption=replied.caption or caption or None)
        else: sent, _ = await send_to_list(context, targets, text=replied.text or caption)
    elif caption:
        sent, _ = await send_to_list(context, targets, text=caption)
    else:
        await update.message.reply_text(
            "📢 *Broadcast:*\n`/broadcast text` → VIP\n`/broadcast all text` → Everyone\nOr reply to media.",
            parse_mode="Markdown"); return
    who = "everyone" if to_all else "VIP"
    display = get_display_count()
    await update.message.reply_text(f"📡 *Broadcast complete!*\n👥 {who} | ✅ Sent to *{display}* members", parse_mode="Markdown")

# ============================================================
# /session, /end
# ============================================================
async def session_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    await update.message.reply_text("⏰ *Session start alert — select timing:*",
        parse_mode="Markdown", reply_markup=kb_session_timing())

async def end_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    vip_ids    = get_vip_ids()
    text       = msg_session_end(SESSION_STATS["wins"], SESSION_STATS["losses"])
    session_id = str(int(time.time()))
    fb_text    = "\n\n━━━━━━━━━━━━━━━━━━\n\U0001f4dd *Rate today's session:*\nTap a number (1 = poor, 5 = excellent)"
    # FIX 4: VIP only
    for vid in vip_ids:
        try: await context.bot.send_message(chat_id=vid, text=text+fb_text,
                parse_mode="Markdown", reply_markup=kb_feedback(session_id))
        except: pass
    sigs = load_signals(); sigs[f"session_{session_id}"] = {"session_id": session_id}; save_signals(sigs)
    # FIX 7: clean message
    await update.message.reply_text("🏁 *Session ended!*\n\nTap below to see feedback 👇",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📊 View Feedback", callback_data=f"view_fb_{session_id}")]]))

# ============================================================
# /feedback — FIX 2: hide real/generated label
# ============================================================
async def feedback_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    import random

    wins    = SESSION_STATS.get("wins", 0)
    losses  = SESSION_STATS.get("losses", 0)
    total   = wins + losses
    acc_pct = int(wins/total*100) if total > 0 else 100
    acc_str = f"{wins}/{total}" if total > 0 else "all"
    amt1    = random.randint(80, 500)
    amt2    = random.randint(500, 4500)
    amt2 = random.randint(500, 4500)

    NAMES = [
        "James","Ali","Sarah","Mike","John","David","Kevin","Chris","Tony","Eric",
        "Omar","Ahmed","Hassan","Sam","Felix","Ivan","Bruno","Joel","Musa","Bilal",
        "Zara","Aisha","Fatima","Nina","Leila","Emma","Lisa","Anna","Grace","Nadia",
        "John K","Ali B","Sarah M","David T","Mike O","James K","Chris A","Eric B"
    ]

    JOINED_TODAY = [
        f"Joined today and already ${amt1} up. This is crazy 😱",
        f"First session here and {wins} out of {total} won. Can't believe it king 😱",
    ]

    # ~70% English, ~10% Swahili, ~10% Hindi, ~10% Portuguese/French
    SHORT = [
        # English — majority
        f"Bro this is too good 🔥",
        f"King you never disappoint 👑",
        f"Brother signals were clean today 💪",
        f"All {wins} hit. Not even joking",
        f"${amt1} made today. Thank you 🙏",
        f"On point as always bro 🎯",
        f"${amt1} profit today. Simple 💰",
        f"Boss you killed it today 👊",
        f"Clean session today king 👑",
        f"Evalon never misses bro 🎯",
        f"This Evalon thing is real king 💎",
        f"Every signal landed today bro 🔥",
        f"${amt1} richer after today's session",
        f"Accuracy {acc_pct}% today. Wild 👑",
        f"Bro {wins} out of {total}. Crazy 💪",
        f"Never seen accuracy like this bro",
        f"${amt1} in the bag today king 🔥",
        f"Evalon is different bro, fr 💎",
        f"Signals on point today. ${amt1} profit",
        f"King every trade hit today 💪",
        f"Bro I was ready and it paid off. ${amt1} 🔥",
        f"No cap {acc_pct}% accuracy today 👑",
        # Swahili — only 3
        f"Kaka leo ilikuwa moto 🔥",
        f"Evalon kaka asante, leo nzuri sana",
        f"Asante sana bro, faida nzuri leo",
        # Hindi — 2
        f"Bhai aaj toh kamaal tha 🔥",
        f"Shukriya bhai, ${amt1} profit mila 🙏",
        # Portuguese/French — 2
        f"Merci chef, {wins} sur {total} 👌",
        f"Perfeito hoje irmão, ${amt1} 💪",
    ]

    LONG = [
        # English — majority
        f"Bro I have been trading for 2 years and never seen accuracy like this. "
        f"Made ${amt2} today just following the signals. "
        f"Every single one hit. King you are built different 👑",

        f"Evalon brother I was skeptical at first. "
        f"But {acc_str} signals won today and I made ${amt1}. "
        f"This is the real deal. No more guessing 💪",

        f"I told my friend about this after making ${amt1} today. "
        f"He didn't believe me so I showed him my account. "
        f"Now he wants to join too 😂 Accuracy was {acc_pct}% king 👊",

        f"I nearly gave up trading last month after losing money elsewhere. "
        f"Today I made ${amt1} and I finally feel confident again. "
        f"Every signal was precise bro. Thank you for real 🙏",

        f"Honestly the consistency is what gets me every time. "
        f"Session after session, {acc_pct}% accuracy. "
        f"Made ${amt1} today and I am not even using big amounts yet 💰",

        f"Brother I screenshotted my balance after today's session. "
        f"${amt2} in profit. Evalon is changing lives king, for real 🙏🔥",

        f"Bro {acc_pct}% accuracy today. I have tried 3 other signal groups before. "
        f"None of them come close to this. ${amt1} profit and I am happy 💪",

        f"King this is the most consistent signal I have ever followed. "
        f"Today {acc_str} won and I made ${amt1}. "
        f"My trading changed completely since I joined 🔥",

        f"Man I used to trade randomly and lose. "
        f"Now I just wait for the signal and follow it. "
        f"${amt1} profit today. Discipline is key bro 💪",

        # Hindi — 1
        f"Bhai pehle main bahut loss karta tha dusri jagah se. "
        f"Aaj {wins} mein se {wins} win hua. ${amt1} profit. "
        f"Evalon ka level alag hai sach mein 🙏",

        # Portuguese — 1
        f"Irmão hoje foi sensacional. {acc_str} sinais certos e ${amt2} de lucro. "
        f"Obrigado mesmo 👑",

        # Swahili — 1 only
        f"Kaka nimekuwa nikifuata signals kwa wiki mbili sasa. "
        f"Kila session inanipa faida. Leo ${amt1} tena. Asante ndugu 🙏",
    ]

    used_comments = set()
    def win_comment():
        pool = SHORT * 3 + LONG  # more short than long
        random.shuffle(pool)
        for c in pool:
            # 40% chance remove trailing emoji for variety
            if random.random() < 0.4:
                for em in ["🔥","💪","👑","🏆","💰","🎯","😱","🙏","👊","✅","💎","⚡","👌"]:
                    if c.endswith(em):
                        c = c[:-len(em)].strip()
                        break
            # Avoid exact duplicates
            key = c[:40]
            if key not in used_comments:
                used_comments.add(key)
                return c
        # fallback if all used
        return random.choice(LONG)

    used_nums = set()
    def get_num():
        n = random.randint(1501, 2800)
        while n in used_nums: n = random.randint(1501, 2800)
        used_nums.add(n); return n

    used_names = set()
    def make_name():
        attempts = 0
        while attempts < 20:
            name = random.choice(NAMES)
            if random.random() < 0.35:
                second = random.choice([n for n in NAMES if n != name])
                full = f"{name.split()[0]} {second.split()[0][0]}"
            else:
                full = name.split()[0]
            if full not in used_names:
                used_names.add(full)
                return full
            attempts += 1
        return name.split()[0]

    def make_fake(comment=None):
        return {
            "num":     get_num(),
            "name":    make_name(),
            "stars":   "⭐" * random.choice([5,5,5,4,4,4,5,4,3,5,4,5,4,5,3,4,5,5,4,5]),
            "comment": comment or win_comment()
        }

    # Real feedback from DB (max 4)
    real_all  = [f for f in load_feedback() if f.get("rating", 0) >= 4]
    real_show = real_all[:4]
    real_entries = [{
        "num":     get_num(),
        "name":    f.get("name", "User"),
        "stars":   "⭐" * f.get("rating", 5),
        "comment": f.get("comment", "Great signals!")
    } for f in real_show]

    # Build fake pool — exactly 2 "joined today" spread out
    total_fake       = random.randint(12, 18)
    joined_pool      = list(JOINED_TODAY)  # already 2
    joined_positions = sorted(random.sample(range(total_fake), 2))

    fake_entries = []
    joined_idx = 0
    for i in range(total_fake):
        if joined_idx < 2 and i == joined_positions[joined_idx]:
            fake_entries.append(make_fake(comment=joined_pool[joined_idx]))
            joined_idx += 1
        else:
            fake_entries.append(make_fake())

    # ORDER: 3 fake → real interleaved → remaining fake
    first_fake = fake_entries[:3]
    rest_fake  = fake_entries[3:]

    # Interleave real with rest_fake naturally
    middle = []
    ri = 0
    for i, fe in enumerate(rest_fake):
        if ri < len(real_entries) and i % max(1, len(rest_fake)//(len(real_entries)+1)) == 0:
            middle.append(real_entries[ri]); ri += 1
        middle.append(fe)
    # Append any remaining real
    while ri < len(real_entries):
        middle.append(real_entries[ri]); ri += 1

    all_entries = first_fake + middle
    if not all_entries:
        await update.message.reply_text("📊 No feedback yet."); return

    await update.message.reply_text("📊 *Sending feedback...*", parse_mode="Markdown")
    for entry in all_entries:
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"{entry['stars']} *#{entry['num']}*\n👤 *{entry['name']}*\n_\"{entry['comment']}\"_",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.warning(f"Feedback send failed: {e}")
        await asyncio.sleep(random.uniform(1.2, 2.8))

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="✅ *Done!*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🗑️ Clear All Feedback", callback_data="clear_feedback")]])
    )

# ============================================================
# /realfeedback — see only real feedback
# ============================================================
async def cmd_realfeedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    fb_list = load_feedback()
    if not fb_list: await update.message.reply_text("📊 No real feedback yet."); return
    ratings = [f["rating"] for f in fb_list]
    avg     = sum(ratings)/len(ratings)
    lines   = [f"📊 *REAL FEEDBACK ({len(fb_list)} responses)*\n⭐ Average: *{avg:.1f}/5*\n\n"]
    for i, fb in enumerate(fb_list, 1):
        lines.append(f"{i}. {'⭐'*fb.get('rating',0)} — *{fb.get('name','?')}*\n"
                     f"   💬 _{fb.get('comment','No comment')}_\n   📅 {fb.get('date','?')}\n")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

# ============================================================
# /help helper
# ============================================================
async def _send_help(chat_id, context):
    await context.bot.send_message(chat_id=chat_id, parse_mode="Markdown", text=(
        "\U0001f4d6 *EVALON VIP SIGNALS — ADMIN GUIDE*\n\n"
        "━━━━━━━━━━"+"\n\U0001f4e1 *SIGNALS*\n"+"━━━━━━━━━━"+"\n"
        "`EURUSD 5` → 1 trade (default)\n"
        "`EURUSD 5 10` → 10 trades auto\n\n"
        "PREPARING → BUY/SELL/Cancel\n"
        "If trades=1 → bot asks count\n"
        "If trades>1 → result sent auto\n\n"
        "━━━━━━━━━━"+"\n\U0001f4c5 *SESSION*\n"+"━━━━━━━━━━"+"\n"
        "`/session` — 30min/1hr alert\n"
        "`/end` — End (VIP only)\n\n"
        "━━━━━━━━━━"+"\n\U0001f4e2 *BROADCAST*\n"+"━━━━━━━━━━"+"\n"
        "Send photo/video → direct to VIP\n"
        "`/broadcast text` → VIP\n"
        "`/broadcast all text` → Everyone\n"
    ))
    await context.bot.send_message(chat_id=chat_id, parse_mode="Markdown", text=(
        "━━━━━━━━━━"+"\n\U0001f511 *VIP CODES*\n"+"━━━━━━━━━━"+"\n"
        "`/addcode 1w Name` — 1 Week code\n"
        "`/addcode 1m Name` — 1 Month code\n"
        "`/addcode 3m Name` — 3 Months code\n"
        "`/addcode 6m Name` — 6 Months code\n"
        "`/addcode 1y Name` — 1 Year code\n"
        "`/addcodes 10 1m` — 10 codes (1 Month)\n"
        "`/listcodes` — View codes\n"
        "`/vipusers` — View VIP\n"
        "`/revoke USER_ID` — Remove VIP\n\n"
        "━━━━━━━━━━"+"\n\U0001f4ca *STATS & FEEDBACK*\n"+"━━━━━━━━━━"+"\n"
        "`/feedback` — Send feedback messages\n"
        "`/realfeedback` — View real feedback only\n"
        "`/stats` — Full statistics\n"
        "`/dbstatus` — Database health\n\n"
        "━━━━━━━━━━"+"\n\U0001f4ce *FILE IDs*\n"+"━━━━━━━━━━"+"\n"
        "`/getid` → send sticker/photo → get file\\_id\n"
    ))

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    await _send_help(update.effective_chat.id, context)

# ============================================================
# OTHER ADMIN COMMANDS
# ============================================================
async def cmd_setwelcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    context.user_data["awaiting_welcome_image"] = True
    await update.message.reply_text("🖼️ *Send the welcome image now.*", parse_mode="Markdown")

async def cmd_dbstatus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if DATABASE_URL:
        try:
            _sb_get("main_db"); db = load_db()
            vips = sum(1 for u in db["users"].values() if u.get("vip"))
            await update.message.reply_text(
                f"✅ *PostgreSQL Connected!*\n\n"
                f"👥 Users: *{len(db['users'])}* | 💎 VIP: *{vips}* | 🔑 Codes: *{len(db.get('codes',{}))}*\n\n"
                "Data is safely stored 🛡️", parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text(f"❌ *PostgreSQL Error!*\n\n`{e}`", parse_mode="Markdown")
    else:
        await update.message.reply_text("⚠️ *PostgreSQL not connected!*\n\nSet `DATABASE_URL` on Render.", parse_mode="Markdown")

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    db   = load_db(); users = db.get("users",{}); codes = db.get("codes",{})
    vip  = sum(1 for u in users.values() if u.get("vip"))
    lines = [
        "\U0001f4ca *EVALON VIP SIGNALS \u2014 STATS*\n",
        f"\n💾 Storage: *{'✅ PostgreSQL' if DATABASE_URL else '⚠️ Local JSON'}*\n",
        "\n━━━━━━━━━━━━━━",
        f"\n\U0001f4e3 Display count : *{BASE_MEMBERS + vip}*",
        f"\n\U0001f48e VIP members   : *{vip}*",
        f"\n\U0001f513 Non-VIP       : *{len(users)-vip}*\n",
        "━━━━━━━━━━━━━━",
        f"\n\U0001f7e2 Active codes : *{sum(1 for c in codes.values() if c.get('used'))}*",
        f"\n\u26aa Unused codes : *{sum(1 for c in codes.values() if not c.get('used'))}*",
        f"\n\U0001f4cb Total codes  : *{len(codes)}*",
    ]
    await update.message.reply_text("".join(lines), parse_mode="Markdown")

async def cmd_addcode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    # Usage: /addcode [duration] [label]
    # duration: 1w | 1m | 3m | 1y  (default: 1m)
    args = context.args or []
    if args and args[0].lower() in VIP_DURATIONS:
        dur   = args[0].lower()
        label = " ".join(args[1:]) if len(args) > 1 else "VIP User"
    else:
        dur   = "1m"
        label = " ".join(args) if args else "VIP User"
    code, days = new_code(label, dur)
    dur_labels = {"1w": "1 Week", "1m": "1 Month", "3m": "3 Months", "6m": "6 Months", "1y": "1 Year"}
    await update.message.reply_text(
        f"✅ *VIP Code Created!*\n\n"
        f"👤 *{label}*\n"
        f"🔑 `{code}`\n"
        f"⏳ Duration: *{dur_labels[dur]}* ({days} days)\n\n"
        f"📌 Usage: `/addcode 1w`, `/addcode 1m`, `/addcode 3m`, `/addcode 1y`",
        parse_mode="Markdown"
    )

async def cmd_addcodes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    # Usage: /addcodes [count] [duration]
    args = context.args or []
    count = 1; dur = "1m"
    for a in args:
        if a.lower() in VIP_DURATIONS: dur = a.lower()
        else:
            try: count = min(int(a), 50)
            except: pass
    dur_labels = {"1w": "1 Week", "1m": "1 Month", "3m": "3 Months", "6m": "6 Months", "1y": "1 Year"}
    pairs = [new_code(f"VIP User {i+1}", dur) for i in range(count)]
    codes_list = "\n".join(f"`{c}` — {dur_labels[dur]}" for c, _ in pairs)
    await update.message.reply_text(
        f"✅ *{count} VIP Codes Created!*\n"
        f"⏳ Duration: *{dur_labels[dur]}*\n\n{codes_list}",
        parse_mode="Markdown"
    )

async def cmd_listcodes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    db = load_db(); codes = db.get("codes",{})
    if not codes: await update.message.reply_text("📋 No codes yet."); return
    unused = [(c,v) for c,v in codes.items() if not v.get("used")]
    used   = [(c,v) for c,v in codes.items() if v.get("used")]
    lines  = [f"📋 *VIP CODES ({len(codes)} total)*\n⚪ Unused: {len(unused)}  🟢 Used: {len(used)}\n"]
    if unused: lines.append("*— UNUSED —*"); [lines.append(f"`{c}` — {v.get('label','?')}") for c,v in unused[:20]]
    if used:   lines.append("\n*— USED —*");  [lines.append(f"`{c}` — {v.get('used_name','?')} ({v.get('used_date','?')})") for c,v in used[:20]]
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def cmd_vipusers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    vids = get_vip_ids()
    if not vids: await update.message.reply_text("👥 No VIP members yet."); return
    db = load_db(); lines = [f"👥 *VIP MEMBERS ({get_display_count()} total):*\n"]
    for vid in vids:
        info = db["users"].get(str(vid), {})
        lines.append(f"👤 *{info.get('name','?')}*  |  🔑 `{info.get('vip_code','?')}`  |  📅 {info.get('joined_date','?')}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def cmd_revoke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if not context.args: await update.message.reply_text("Usage: `/revoke USER_ID`", parse_mode="Markdown"); return
    try: target = int(context.args[0])
    except: await update.message.reply_text("❌ Invalid user ID."); return
    db = load_db(); key = str(target)
    if key not in db["users"]: await update.message.reply_text("❌ User not found."); return
    name = db["users"][key].get("name","Unknown"); code = db["users"][key].get("vip_code")
    db["users"][key].update({"vip": False, "vip_code": None})
    if code and code in db["codes"]: db["codes"][code].update({"used": False, "used_by": None})
    save_db(db)
    await update.message.reply_text(f"⛔ *VIP Revoked!*\n\n👤 *{name}*\n🔑 Code `{code}` is free again.", parse_mode="Markdown")

async def protect_forward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_admin(update.effective_user.id): return
    try: await update.message.delete()
    except: pass
    await update.message.reply_text("🔒 Forwarding is not allowed in this bot.")


# ============================================================
# VIP EXPIRY CHECKER
# ============================================================
async def check_vip_expiry(context):
    """Runs daily — warns users 3 days before expiry, revokes on expiry."""
    db   = load_db()
    today = datetime.now().date()
    bot  = context.bot

    for uid_str, udata in list(db["users"].items()):
        if not udata.get("vip"): continue
        expiry_str = udata.get("vip_expiry")
        if not expiry_str: continue

        try:
            expiry = datetime.strptime(expiry_str, "%Y-%m-%d").date()
        except:
            continue

        days_left = (expiry - today).days
        name = udata.get("name", "Trader")
        uid  = int(uid_str)

        # Expired today or past
        if days_left <= 0:
            db["users"][uid_str]["vip"] = False
            code = udata.get("vip_code")
            if code and code in db.get("codes", {}):
                db["codes"][code]["used"] = False
                db["codes"][code]["used_by"] = None
            save_db(db)
            try:
                await bot.send_message(
                    chat_id=uid,
                    text=(
                        f"⚠️ *Dear {name},*\n\n"
                        "Your *VIP access has expired* today.\n\n"
                        "You no longer have access to VIP signals.\n\n"
                        "💎 To renew your VIP access, contact admin or use the bot menu.\n\n"
                        f"{KAULI_MBIU}"
                    ),
                    parse_mode="Markdown"
                )
            except: pass

        # Warn 3 days before
        elif days_left == 3:
            try:
                await bot.send_message(
                    chat_id=uid,
                    text=(
                        f"⏰ *Heads up, {name}!*\n\n"
                        "Your *VIP access expires in 3 days* "
                        f"(*{expiry_str}*).\n\n"
                        "🔄 Renew now to keep receiving signals without interruption!\n\n"
                        "Contact admin or use the bot menu to renew.\n\n"
                        f"{KAULI_MBIU}"
                    ),
                    parse_mode="Markdown"
                )
            except: pass

        # Warn 1 day before
        elif days_left == 1:
            try:
                await bot.send_message(
                    chat_id=uid,
                    text=(
                        f"🚨 *Last Warning, {name}!*\n\n"
                        "Your *VIP access expires TOMORROW* "
                        f"(*{expiry_str}*).\n\n"
                        "⚡ Renew *today* to avoid losing access!\n\n"
                        "Contact admin or use the bot menu now.\n\n"
                        f"{KAULI_MBIU}"
                    ),
                    parse_mode="Markdown"
                )
            except: pass

# ============================================================
# MAIN
# ============================================================
def main():
    _pg_init()
    start_keep_alive()
    start_self_ping()
    print("="*55)
    print("  EVALON VIP SIGNALS BOT v5")
    print("="*55)
    print(f"Storage  : {'PostgreSQL ✅' if DATABASE_URL else 'Local JSON ⚠️'}")
    db = load_db()
    print(f"VIP      : {sum(1 for u in db['users'].values() if u.get('vip'))}")
    print(f"Codes    : {len(db.get('codes', {}))}")
    print(f"Admin ID : {ADMIN_ID}")
    print("="*55)

    app = Application.builder().token(BOT_TOKEN).build()
    # Daily VIP expiry check at 08:00 UTC
    from datetime import time as dtime
    app.job_queue.run_daily(
        check_vip_expiry,
        time=dtime(hour=8, minute=0, tzinfo=timezone.utc)
    )
    app.add_handler(CommandHandler("start",        start))
    app.add_handler(CommandHandler("help",         cmd_help))
    app.add_handler(CommandHandler("stats",        cmd_stats))
    app.add_handler(CommandHandler("broadcast",    broadcast))
    app.add_handler(CommandHandler("session",      session_cmd))
    app.add_handler(CommandHandler("end",          end_cmd))
    app.add_handler(CommandHandler("feedback",     feedback_cmd))
    app.add_handler(CommandHandler("realfeedback", cmd_realfeedback))
    app.add_handler(CommandHandler("setwelcome",   cmd_setwelcome))
    app.add_handler(CommandHandler("addcode",      cmd_addcode))
    app.add_handler(CommandHandler("addcodes",     cmd_addcodes))
    app.add_handler(CommandHandler("listcodes",    cmd_listcodes))
    app.add_handler(CommandHandler("vipusers",     cmd_vipusers))
    app.add_handler(CommandHandler("revoke",       cmd_revoke))
    app.add_handler(CommandHandler("dbstatus",     cmd_dbstatus))
    app.add_handler(CommandHandler("getid",        cmd_getid))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.Sticker.ALL, handle_sticker))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & (filters.PHOTO | filters.VIDEO | filters.ANIMATION), handle_media))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.FORWARDED, protect_forward))
    print("Bot is running!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
