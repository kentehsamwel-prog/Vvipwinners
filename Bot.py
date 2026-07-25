#!/usr/bin/env python3
"""
EVALON VIP SIGNALS BOT v9
Fixes: 1-9 applied + PostgreSQL persistent storage (Render)
v7: Forward/copy protection, VIP code bug fixed, protect_content on all messages
v8: Per-user watermark with ID, watermark text @EvalonwinnersBot, weekly stats in /stats
v9: Bilingual expiry notifications (SW+EN) with name, feedback approval system with channel forward
"""

import os, json, uuid, time, logging, asyncio, threading, urllib.request, urllib.request, subprocess, tempfile
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.error import Forbidden
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
            logger.info("Self-ping OK \u2014 bot still awake \u2705")
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
        logger.info("PostgreSQL connected & table ready \u2705")
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
except ImportError:
    pass
PHOTO_WATERMARK_ENABLED = True    # Photos: watermark ON
VIDEO_WATERMARK_ENABLED = False   # Videos: watermark OFF, per admin request

WATERMARK_TEXT = "@EvalonwinnersBot"

def add_watermark(image_bytes: bytes, user_id: int = None) -> bytes:
    """Add watermark to image. Larger text, cyan/green color for visibility."""
    if not PHOTO_WATERMARK_ENABLED:
        return image_bytes
    try:
        if user_id:
            wm_line1 = "@EvalonwinnersBot"
            wm_line2 = f"\U0001f511 ID: {user_id}"
        else:
            wm_line1 = "@EvalonwinnersBot"
            wm_line2 = None

        img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        w, h = img.size
        overlay = Image.new("RGBA", img.size, (0,0,0,0))
        draw = ImageDraw.Draw(overlay)
        # Larger font: w//12 (was w//18) to be clearly visible
        font_size = max(32, w // 12)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
            font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", max(22, font_size - 6))
        except:
            font = ImageFont.load_default()
            font_small = font

        # Build tile with both lines
        bbox1 = draw.textbbox((0, 0), wm_line1, font=font)
        tw1 = bbox1[2] - bbox1[0]; th1 = bbox1[3] - bbox1[1]
        if wm_line2:
            bbox2 = draw.textbbox((0, 0), wm_line2, font=font_small)
            tw2 = bbox2[2] - bbox2[0]; th2 = bbox2[3] - bbox2[1]
        else:
            tw2 = th2 = 0

        tile_w = max(tw1, tw2) + 28
        tile_h = th1 + (th2 + 8 if wm_line2 else 0) + 20
        ti = Image.new("RGBA", (tile_w, tile_h), (0, 0, 0, 0))
        td = ImageDraw.Draw(ti)
        # Dark shadow for contrast
        td.text((5, 5),   wm_line1, font=font, fill=(0, 0, 0, 160))
        # Cyan/teal color for line 1: (0, 230, 200) - visible on both dark and light backgrounds
        td.text((2, 2),   wm_line1, font=font, fill=(0, 230, 200, 210))
        if wm_line2:
            y2 = th1 + 10
            td.text((5, y2 + 3), wm_line2, font=font_small, fill=(0, 0, 0, 160))
            # Green color for line 2: (80, 255, 120)
            td.text((2, y2),     wm_line2, font=font_small, fill=(80, 255, 120, 210))

        rot = ti.rotate(330, expand=True)
        rw, rh = rot.size
        for y in range(-rh, h + rh, rh + 70):
            for x in range(-rw, w + rw, rw + 50):
                overlay.paste(rot, (x, y), rot)

        out = Image.alpha_composite(img, overlay).convert("RGB")
        buf = io.BytesIO()
        out.save(buf, format="JPEG", quality=90)
        buf.seek(0)
        return buf.read()
    except Exception as e:
        logger.warning(f"Watermark failed: {e}")
        return image_bytes


async def add_video_watermark(video_bytes: bytes, user_id=None) -> bytes:
    """Burn text watermark onto video using ffmpeg. Returns original bytes if ffmpeg fails."""
    if not VIDEO_WATERMARK_ENABLED:
        return video_bytes
    try:
        wm_line1 = "@EvalonwinnersBot"
        wm_line2 = f"ID:{user_id}" if user_id else ""
        # Build watermark text - two lines if user_id given
        if wm_line2:
            wm_text = f"{wm_line1} | {wm_line2}"
        else:
            wm_text = wm_line1

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as fin:
            fin.write(video_bytes)
            in_path = fin.name
        out_path = in_path.replace(".mp4", "_wm.mp4")

        # ffmpeg drawtext filter - larger text, cyan color, static tiled watermark grid
        # fontsize=42 (was 24), cyan color (0x00FFFF) for visibility on dark/light backgrounds
        tile_x = ["w/6", "w/2", "5*w/6", "w/4", "3*w/4"]
        tile_y = ["h/5", "h/3", "h/2", "2*h/3", "4*h/5"]
        filters = []
        for tx in tile_x:
            for ty in tile_y:
                filters.append(
                    f"drawtext=text='{wm_text}':"
                    f"fontsize=42:fontcolor=0x00FFFF@0.75:"
                    f"shadowcolor=black@0.80:shadowx=3:shadowy=3:"
                    f"x=({tx}-tw/2):y=({ty}-th/2):enable=1"
                )
        drawtext = ",".join(filters)

        cmd = [
            "ffmpeg", "-y", "-i", in_path,
            "-vf", drawtext,
            "-codec:a", "copy",
            "-preset", "ultrafast",
            out_path
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )
        await proc.wait()

        if proc.returncode == 0 and os.path.exists(out_path):
            with open(out_path, "rb") as f:
                result = f.read()
        else:
            logger.warning("ffmpeg video watermark failed, sending original")
            result = video_bytes

        # Cleanup
        for p in [in_path, out_path]:
            try: os.unlink(p)
            except: pass

        return result
    except Exception as e:
        logger.warning(f"Video watermark error: {e}")
        return video_bytes

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

# Channel where approved feedback will be forwarded + membership verification
FEEDBACK_CHANNEL_ID = os.environ.get("FEEDBACK_CHANNEL_ID", "-1003403743370")
CHANNEL_NUMERIC_ID  = int(os.environ.get("CHANNEL_NUMERIC_ID", "-1003403743370"))

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

# Signal format: EURUSD 1 \u2192 pair + expiry only
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

def next_candle_time(expiry):
    """Returns the UTC time (HH:MM) of the next candle boundary for the given expiry (minutes)."""
    now = datetime.now(timezone.utc)
    total_min = now.hour * 60 + now.minute
    next_total = ((total_min // expiry) + 1) * expiry
    next_total %= (24 * 60)
    hh, mm = divmod(next_total, 60)
    return f"{hh:02d}:{mm:02d} UTC"

def find_pending_signal(signals):
    """Finds the most recently created signal that hasn't had a direction sent yet."""
    for sig_id in reversed(list(signals.keys())):
        sig = signals[sig_id]
        if sig_id.startswith("session_"):
            continue
        if "direction" not in sig:
            return sig_id, sig
    return None, None

# ============================================================
# CONSTANTS
# ============================================================
KAULI_MBIU = "\U0001f451 *ALWAYS EVALON TRADER IS THE KING OF BINARY* \U0001f451"

WHY_WE_MOVED = (
    "--------------"+"\n"
    "\U0001f525 *Why We Moved From Our VIP Channel To The Bot System* \U0001f525\n"
    "--------------"+"\n\n"
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
    "--------------"+"\n"
)

VIP_RULES = (
    "--------------"+"\n"
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
    "--------------"+"\n"
)

SESSION_STATS    = {"win_pct": 0, "loss_pct": 0, "win_count": 0, "loss_count": 0, "start_time": None, "signal_count": 0, "locked": False}
SESSION_LOG      = []   # list of dicts: {pair, expiry, direction, result, count}
FULL_SESSION_LOG = []   # full ordered log: every message/sticker sent during session
PUBLIC_SIGNAL_MODE = False   # False = signals go to VIP only. True = VIP + Non-VIP.
                        # entry: {"type": "text"|"sticker", "content": str}
_BASE_MEMBERS_START = 1500
_BASE_MEMBERS_DATE  = datetime(2026, 6, 4, tzinfo=timezone.utc)  # Start date: 1500 members

def get_base_members():
    """Returns 1500 + days elapsed since June 4 2026 (grows +1 per day)."""
    days = (datetime.now(timezone.utc) - _BASE_MEMBERS_DATE).days
    return _BASE_MEMBERS_START + max(0, days)

# Weekly stats \u2014 stored in DB so they survive restarts
def _get_weekly_key():
    """Returns key like 'weekly_2026_W21' for current ISO week."""
    now = datetime.now(timezone.utc)
    return f"weekly_{now.year}_W{now.isocalendar()[1]:02d}"

def load_weekly_stats():
    key  = _get_weekly_key()
    data = _pg_get(key) if DATABASE_URL else None
    if data is None:
        # Try local fallback
        path = os.path.join(DATA_DIR, f"{key}.json")
        if os.path.exists(path):
            with open(path) as f: data = json.load(f)
    return data or {"wins": 0, "losses": 0, "sessions": 0, "week": key}

def save_weekly_stats(ws):
    key = _get_weekly_key()
    if DATABASE_URL:
        _pg_set(key, ws)
    else:
        path = os.path.join(DATA_DIR, f"{key}.json")
        with open(path, "w") as f: json.dump(ws, f)

def record_result_weekly(result: str, count: int = 1):
    ws = load_weekly_stats()
    if result == "WIN":
        ws["wins"] = ws.get("wins", 0) + count
    else:
        ws["losses"] = ws.get("losses", 0) + count
    save_weekly_stats(ws)

def record_session_weekly():
    ws = load_weekly_stats()
    ws["sessions"] = ws.get("sessions", 0) + 1
    save_weekly_stats(ws)

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

def mark_user_blocked(uid, blocked=True):
    """Marks/unmarks a user as having blocked the bot. Called when a send raises Forbidden."""
    db = load_db()
    u = db["users"].get(str(uid))
    if not u:
        return
    if blocked and not u.get("blocked"):
        u["blocked"] = True
        u["blocked_date"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        save_db(db)
    elif not blocked and u.get("blocked"):
        u["blocked"] = False
        save_db(db)
def get_vip_count(): return sum(1 for v in load_db()["users"].values() if v.get("vip"))

# Display count = base (grows +1/day from 1500) + real VIP count
def get_display_count():
    return get_base_members() + get_vip_count()

def get_referral_link(uid):
    return f"https://t.me/Kentehsharevvipbot?start=ref{uid}"

def get_referral_list(uid):
    db = load_db()
    return db.get("referrals", {}).get(str(uid), [])

def get_referral_count(uid):
    return len(get_referral_list(uid))

def has_used_trial(uid):
    """Returns True if this user_id has ever used a 1w (Free Trial) code."""
    db = load_db()
    return str(uid) in db.get("trial_users", {})

def grant_auto_trial(uid, name):
    """Grants a brand-new user 1 free VIP session automatically, no code needed.
    Unlike code-based trials, this expires after 1 completed session, not by date."""
    db = load_db(); key = str(uid)
    if key not in db["users"]: db["users"][key] = {}
    db["users"][key].update({
        "vip": True,
        "vip_code": "AUTO_TRIAL",
        "name": name,
        "trial_sessions_left": 1,
        "trial_welcomed": False,
    })
    db.setdefault("trial_users", {})
    if key not in db["trial_users"]:
        db["trial_users"][key] = {
            "name": name, "code": "AUTO_TRIAL",
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
    save_db(db)

def activate_code(code, uid, name):
    db = load_db(); code = code.strip().upper()
    if code not in db["codes"] or db["codes"][code].get("used"): return False

    # Check if this is a Free Trial code
    duration_key = db["codes"][code].get("duration_key", "1m")
    is_trial = (duration_key == "1w")

    # Block if user already used a trial before
    if is_trial and has_used_trial(uid):
        return "trial_abuse"

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

    # Record trial usage permanently (survives revoke/expiry)
    if is_trial:
        if "trial_users" not in db: db["trial_users"] = {}
        db["trial_users"][str(uid)] = {
            "name":      name,
            "code":      code,
            "date":      now.strftime("%Y-%m-%d %H:%M"),
        }

    save_db(db); return True

# Duration options in days
VIP_DURATIONS = {
    "1w":  7,
    "1m":  30,
    "3m":  90,
    "6m":  180,
    "1y":  365,
}

def new_code(label, duration_key="1m", custom_days=None):
    code = "VIP-" + "-".join(uuid.uuid4().hex[:4].upper() for _ in range(3))
    db   = load_db()
    if custom_days:
        days = custom_days
        dur_key = f"{custom_days}d"
    else:
        days    = VIP_DURATIONS.get(duration_key, 30)
        dur_key = duration_key
    db["codes"][code] = {
        "label":        label,
        "used":         False,
        "used_by":      None,
        "created":      datetime.now().strftime("%Y-%m-%d %H:%M"),
        "duration_key": dur_key,
        "duration_days": days,
        "expires_date": None,
    }
    save_db(db); return code, days

def is_market_day():
    return datetime.now(timezone.utc).weekday() < 5

def is_weekend():
    return datetime.now(timezone.utc).weekday() >= 5

WEEKEND_DAY_NAME = lambda: datetime.now(timezone.utc).strftime("%A")  # "Saturday" or "Sunday"

TUTORIAL_VIDEO = "BAACAgQAAxkBAAIFn2oRZ0HUGBuMA4GYy3E7cC4Bv32WAAKqHgACyDCJUL7jK5vNBqvvOwQ"
INVITE_LINK    = "https://t.me/Kentehsharevvipbot?start=ref8535925646"

WEEKEND_VIP_MSGS = [
    "\U0001f389 Happy {day}, *{name}!*\n\nEnjoy your weekend \u2014 rest well and recharge!\nWe will be back with signals on *Monday*. \U0001f4aa\n\n\U0001f525 Stay focused \u2014 the market never sleeps forever!\n\n\U0001f451 ALWAYS EVALON TRADER IS THE KING OF BINARY \U0001f451",
    "\U0001f60e {day} vibes, *{name}!*\n\nNo signals today \u2014 enjoy your break!\nSee you bright and early on *Monday* ready to win! \U0001f3c6\n\n\U0001f48e Rest today. Profit Monday!\n\n\U0001f451 ALWAYS EVALON TRADER IS THE KING OF BINARY \U0001f451",
    "\U0001f31f Hey *{name}!* Happy {day}!\n\nMarkets are closed \u2014 take a break, spend time with family!\nWe resume *Monday* with fresh signals. \U0001f680\n\n\U0001f451 ALWAYS EVALON TRADER IS THE KING OF BINARY \U0001f451",
    "\U0001f3d6\ufe0f *{name}*, enjoy your {day}!\n\nThe best traders also know when to rest.\nSee you *Monday* \u2014 signals resume then! \U0001f4aa\n\n\U0001f451 ALWAYS EVALON TRADER IS THE KING OF BINARY \U0001f451",
]

WEEKEND_NOVIP_MSGS = [
    "\U0001f389 Happy {day}, *{name}!*\n\nEnjoy your weekend!\nBut wait \u2014 are you still missing out on VIP signals? \U0001f914\n\n\U0001f48e *Don\'t worry \u2014 FREE spots are available!*\n\n\U0001f3b0 *Spin & Win* a discount up to *70% OFF* VIP access!\n\U0001f465 *Invite friends* and earn rewards!\n\n\U0001f447 Tap the buttons below to get started!\n\n\U0001f451 ALWAYS EVALON TRADER IS THE KING OF BINARY \U0001f451",
    "\U0001f60e {day} greetings, *{name}!*\n\nWhile you relax, our VIP members are preparing for *Monday\'s big session!* \U0001f4ca\n\n\U0001f680 *Want to join them?*\n\U0001f3b0 Spin for up to *70% OFF* VIP!\n\U0001f465 Invite friends and earn free access!\n\n\U0001f447 Tap the buttons below!\n\n\U0001f451 ALWAYS EVALON TRADER IS THE KING OF BINARY \U0001f451",
    "\U0001f31f Hey *{name}!*\n\nHappy {day}! No signals today \u2014 but Monday is coming fast! \u26a1\n\n\u2753 *Still not VIP? Free spots are open!*\n\U0001f3b0 Spin & Win \u2014 get up to *70% discount*!\n\U0001f465 Invite a friend \u2014 both of you benefit!\n\n\U0001f447 Tap below to get started!\n\n\U0001f451 ALWAYS EVALON TRADER IS THE KING OF BINARY \U0001f451",
    "\U0001f3d6\ufe0f Enjoy your {day}, *{name}!*\n\nOur VIP members are resting and ready for *Monday\'s session!* \U0001f4aa\n\n\U0001f4a1 *You can join them \u2014 spots are still available!*\n\U0001f3b0 Spin for a discount up to *70% OFF!*\n\U0001f465 Invite friends & earn rewards!\n\n\U0001f447 Tap below now!\n\n\U0001f451 ALWAYS EVALON TRADER IS THE KING OF BINARY \U0001f451",
]


# ============================================================
# MESSAGES
# ============================================================
def msg_preparing(pair, expiry, weight=5):
    return (
        "\U0001f3c6 *EVALON VVIP WINNERS* \U0001f3c6\n\n"
        "--------------"+"\n"
        f"\U0001f4ca PAIR    : *{pair}*\n"
        f"\u23f1 EXPIRY  : *{expiry} MIN*\n"
        f"\U0001f550 TIME    : *{current_time_utc()}*\n"
        f"\U0001f4b0 INVEST  : *{weight}%* of your capital\n"
        "\U0001f4cd STATUS  : SIGNAL PREPARING...\n\n"
        "\u26a0\ufe0f WAIT FOR DIRECTION\n"
        "--------------"+"\n\n"
        "\U0001f525 STAY READY \u2014 ENTRY COMING SOON\n"
        "\U0001f48e VVIP MEMBERS ONLY"
    )

def msg_direction(pair, expiry, direction, trades=1):
    arrow = "\U0001f4c8" if direction == "BUY" else "\U0001f4c9"
    color = "\U0001f7e2" if direction == "BUY" else "\U0001f534"
    return (
        "\U0001f3c6 *EVALON VVIP WINNERS* \U0001f3c6\n\n"
        "--------------"+"\n"
        f"\U0001f4ca PAIR      : *{pair}*\n"
        f"\u23f1 EXPIRY    : *{expiry} MIN*\n"
        f"\U0001f550 ENTRY     : *{next_candle_time(expiry)}*\n"
        f"{arrow} DIRECTION : *{color} {direction}*\n"
        "--------------"+"\n\n"
        "\u26a1 *OPEN YOUR TRADE NEW CANDLE!*\n"
        "\U0001f48e VVIP MEMBERS ONLY"
    )

def msg_candle_plan(pair, expiry, buy_action, sell_action):
    return (
        "\U0001f3c6 *EVALON VVIP WINNERS* \U0001f3c6\n\n"
        "--------------"+"\n"
        f"\U0001f4ca PAIR    : *{pair}*\n"
        f"\u23f1 EXPIRY  : *{expiry} MIN*\n"
        f"\U0001f550 TIME    : *{current_time_utc()}*\n"
        "--------------"+"\n\n"
        "\u26a1 *CANDLE CLOSE PLAN:*\n"
        f"\U0001f7e2 IF CANDLE CLOSES BUY  \u2192 OPEN *{buy_action}*\n"
        f"\U0001f534 IF CANDLE CLOSES SELL \u2192 OPEN *{sell_action}*\n"
        "--------------"+"\n\n"
        "\U0001f440 Watch closely \u2014 enter the moment the candle closes!\n"
        "\U0001f48e VVIP MEMBERS ONLY"
    )

def msg_win(pair, expiry, direction, pct=5):
    return (
        "\U0001f3c6 *EVALON VVIP WINNERS* \U0001f3c6\n\n"
        "--------------"+"\n"
        f"\U0001f4ca PAIR      : *{pair}*\n"
        f"\u23f1 EXPIRY    : *{expiry} MIN*\n"
        f"\U0001f4c8 DIRECTION : *{direction}*\n"
        f"\U0001f3c6 RESULT    : *WIN \u2705 {pct}%*\n"
        "--------------"+"\n\n"
        "\U0001f4b0 *Congratulations! Another profit secured!*\n"
        "\U0001f525 Stay focused \u2014 more signals coming!\n"
        "\U0001f48e VVIP MEMBERS ONLY"
    )

def msg_loss(pair, expiry, direction, pct=5):
    return (
        "\U0001f3c6 *EVALON VVIP WINNERS* \U0001f3c6\n\n"
        "--------------"+"\n"
        f"\U0001f4ca PAIR      : *{pair}*\n"
        f"\u23f1 EXPIRY    : *{expiry} MIN*\n"
        f"\U0001f4c8 DIRECTION : *{direction}*\n"
        f"\U0001f534 RESULT    : *LOSS \u274c {pct}%*\n"
        "--------------"+"\n\n"
        "\U0001f4aa *Stay strong! Every loss is a lesson!*\n"
        "\U0001f9e0 Protect your capital \u2014 next signal coming!\n"
        "\U0001f6ab No Martingale \u2014 trust the process!\n"
        "\U0001f48e VVIP MEMBERS ONLY"
    )

def msg_trial_welcome(name):
    return (
        "\U0001f389 *CONGRATULATIONS!* \U0001f389\n\n"
        f"Welcome to *EVALON VVIP WINNERS*, {name}!\n\n"
        "\U0001f381 As a new member, you've been given a *FREE VIP TRIAL SESSION* \u2014 "
        "no code, no payment, just our gift to you.\n\n"
        "\U0001f4ca You're about to receive the exact same signals our paying VIP "
        "members get \u2014 live, in real time.\n\n"
        "\U0001f440 Watch closely and see the value for yourself.\n"
        "\U0001f48e Enjoyed it? Grab full VIP access anytime with `/start` \u2192 Get VIP Access.\n\n"
        f"{KAULI_MBIU}"
    )

def msg_session_soon(minutes, is_vip=False):
    when = f"{minutes} minutes" if minutes < 60 else f"{minutes//60} hour"
    rules = f"\n{VIP_RULES}" if is_vip else "\n"
    return (
        "\U0001f3c6 *EVALON VVIP WINNERS* \U0001f3c6\n\n"
        "--------------"+"\n"
        f"\u23f0 SESSION STARTING IN *{when.upper()}*\n"
        "--------------"+"\n\n"
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

def msg_money_management():
    return (
        "\U0001f3c6 *EVALON VVIP WINNERS* \U0001f3c6\n\n"
        "--------------\n"
        "\U0001f4b0 *HOW WE PROTECT & GROW YOUR CAPITAL*\n"
        "--------------\n\n"
        "This group is built for *profit*, not loss \u2014 our rules exist so your "
        "account grows steadily, session after session.\n\n"
        "\U0001f4cc Signal 1 \u2014 invest only *5%* of your capital\n"
        "\U0001f4cc Every trade is a *NEW CANDLE* entry, direction sent before it closes\n\n"
        "\u26a0\ufe0f *A word of caution:* many traders online promise 100% win rates every "
        "day \u2014 that's exactly how people get deceived and end up losing everything. "
        "No one on earth can guarantee 100% in forex/binary, every single day. "
        "This group has never claimed that and never will.\n\n"
        "If any group promises you 100% daily, that's your sign to walk away \u2014 "
        "staying there only leads to bigger losses. Here, we aim for small, honest "
        "profit each day while your capital keeps growing. Just follow the group rules.\n\n"
        "\U0001f4c8 *About the Compounding Group:* it also does NOT promise 100% daily. "
        "We trade carefully, at a calm pace, with well-analyzed signals \u2014 "
        "quality over rushing. Recommended investment there is *25%* per signal. Our goal is "
        "always the same: protect your capital first, grow it steadily second.\n\n"
        "\U0001f512 Your capital is what matters most \u2014 we treat it like our own.\n\n"
        f"{KAULI_MBIU}"
    )

def msg_session_end(win_pct=0, loss_pct=0, win_count=0, loss_count=0):
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
    total_trades = win_count + loss_count
    net_pct  = win_pct - loss_pct
    total_pct = win_pct + loss_pct
    accuracy = f"{(win_pct/total_pct*100):.0f}%" if total_pct > 0 else "N/A"
    return (
        "\U0001f3c6 *EVALON VVIP WINNERS* \U0001f3c6\n\n"
        "--------------\n"
        "\U0001f3c1 *TRADING SESSION ENDED*\n"
        "--------------\n\n"
        "That's a wrap for today's session!\n\n"
        "\U0001f4ca *SESSION RESULTS:*\n"
        "--------------\n"
        f"\u2705 WIN      : *{win_pct}%*\n"
        f"\u274c LOSS     : *{loss_pct}%*\n"
        f"\U0001f4b0 TOTAL     : *{'+' if net_pct >= 0 else ''}{net_pct}%*\n"
        f"\U0001f3af ACCURACY  : *{accuracy}*\n"
        f"{dur_line}"
        "--------------\n\n"
        "\U0001f4aa Great discipline leads to consistent profits!\n"
        "\U0001f550 Next session will be announced soon!\n\n"
        "Thank you for trading with us!\n\n"
        f"{KAULI_MBIU}"
    )

def msg_cancelled(pair):
    return (
        "\U0001f3c6 *EVALON VVIP WINNERS* \U0001f3c6\n\n"
        "--------------"+"\n"
        f"\U0001f4ca PAIR   : *{pair}*\n"
        "\u274c STATUS : *SIGNAL CANCELLED*\n"
        "--------------"+"\n\n"
        "\u23ed Skip this one \u2014 next signal coming soon!\n"
        "\U0001f9e0 Patience is the key to success!\n"
        "\U0001f48e VVIP MEMBERS ONLY"
    )

# ============================================================
# SEND HELPERS
# ============================================================
async def send_to_list(context, uid_list, text=None, photo=None,
                       video=None, sticker=None, caption=None,
                       animation=None, reply_markup=None, parse_mode="Markdown"):
    async def _send_one(uid):
        try:
            if photo:
                await context.bot.send_photo(chat_id=uid, photo=photo, caption=caption,
                    parse_mode=parse_mode, reply_markup=reply_markup, protect_content=True)
            elif video:
                await context.bot.send_video(chat_id=uid, video=video, caption=caption,
                    parse_mode=parse_mode, reply_markup=reply_markup, protect_content=True)
            elif animation:
                await context.bot.send_animation(chat_id=uid, animation=animation, caption=caption,
                    parse_mode=parse_mode, reply_markup=reply_markup, protect_content=True)
            elif sticker:
                await context.bot.send_sticker(chat_id=uid, sticker=sticker, protect_content=True)
            elif text:
                pm = parse_mode if parse_mode else None
                kw = {"parse_mode": pm} if pm else {}
                await context.bot.send_message(chat_id=uid, text=text,
                    reply_markup=reply_markup, protect_content=True, **kw)
            mark_user_blocked(uid, False)
            return True
        except Forbidden:
            mark_user_blocked(uid, True)
            return False
        except Exception as e:
            logger.warning(f"Send failed {uid}: {e}"); return False

    results = await asyncio.gather(*[_send_one(uid) for uid in uid_list])
    sent   = sum(1 for r in results if r)
    failed = sum(1 for r in results if not r)
    return sent, failed

# ============================================================
# KEYBOARDS
# ============================================================
def kb_join():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("\U0001f4e2 Join Our Channel", url=CHANNEL_INVITE)],
        [InlineKeyboardButton("\u2705 I Have Joined",    callback_data="check_join")],
    ])

def kb_locked():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("\U0001f511 Enter VIP Code", callback_data="enter_code")],
        [InlineKeyboardButton("\U0001f4ac Contact Admin",  url=SUPPORT_URL)],
    ])

def kb_support():
    return InlineKeyboardMarkup([[InlineKeyboardButton("\U0001f4ac Contact Admin", url=SUPPORT_URL)]])

def kb_direction(sig_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("\U0001f4c8 BUY",  callback_data=f"dir_BUY_{sig_id}"),
         InlineKeyboardButton("\U0001f4c9 SELL", callback_data=f"dir_SELL_{sig_id}")],
        [InlineKeyboardButton("\u274c Cancel Signal", callback_data=f"dir_CANCEL_{sig_id}")]
    ])

def kb_result(sig_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("\u2705 WIN",  callback_data=f"res_WIN_{sig_id}"),
         InlineKeyboardButton("\u274c LOSS", callback_data=f"res_LOSS_{sig_id}")],
        [InlineKeyboardButton("\U0001f3c1 End Session", callback_data="end_session")]
    ])

def kb_after_result():
    return InlineKeyboardMarkup([[InlineKeyboardButton("\U0001f3c1 End Session", callback_data="end_session")]])

def kb_session_timing():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("\u23f0 5 Minutes",  callback_data="sess_30"),
        InlineKeyboardButton("\u23f0 30 Minutes", callback_data="sess_60"),
    ]])

def kb_get_vip():
    return InlineKeyboardMarkup([[InlineKeyboardButton("\U0001f48e Get VIP Access", callback_data="enter_code")]])

def kb_feedback(session_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("\u2b50", callback_data=f"fb_{session_id}_1"),
            InlineKeyboardButton("\u2b50\u2b50", callback_data=f"fb_{session_id}_2"),
            InlineKeyboardButton("\u2b50\u2b50\u2b50", callback_data=f"fb_{session_id}_3"),
            InlineKeyboardButton("\u2b50\u2b50\u2b50\u2b50", callback_data=f"fb_{session_id}_4"),
            InlineKeyboardButton("\u2b50\u2b50\u2b50\u2b50\u2b50", callback_data=f"fb_{session_id}_5"),
        ],
        [InlineKeyboardButton("\U0001f7e2 SESSION", callback_data="trigger_start")],
        [InlineKeyboardButton("\U0001f4ac Contact Admin", url=SUPPORT_URL)],
    ])

# FIX 1: admin /start \u2014 short panel + buttons
def kb_admin_start():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("\u23f0 Session 5 min",  callback_data="sess_30"),
         InlineKeyboardButton("\u23f0 Session 30 min", callback_data="sess_60")],
        [InlineKeyboardButton("\U0001f3c1 End Session",    callback_data="end_session")],
        [InlineKeyboardButton("\u2753 Help",            callback_data="admin_help")],
    ])

# ============================================================
# SESSION reply keyboard - persistent bottom keyboard
# ============================================================
def kb_session():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("SESSION")]],
        resize_keyboard=True
    )

# ============================================================
# /start
# ============================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import random as _random
    uid  = update.effective_user.id
    name = update.effective_user.first_name or "Trader"

    db_before = load_db()
    is_brand_new = str(uid) not in db_before.get("users", {})

    get_user(uid)
    update_user(uid, {"name": name})

    # Referral capture: link is https://t.me/Kentehsharevvipbot?start=ref<inviter_id>
    if is_brand_new:
        args = context.args or []
        if args and args[0].startswith("ref"):
            ref_part = args[0][3:]
            if ref_part.isdigit() and int(ref_part) != uid:
                inviter_id = int(ref_part)
                db = load_db()
                if str(inviter_id) in db.get("users", {}):
                    db.setdefault("referrals", {})
                    db["referrals"].setdefault(str(inviter_id), [])
                    already = any(r.get("uid") == uid for r in db["referrals"][str(inviter_id)])
                    if not already:
                        db["referrals"][str(inviter_id)].append({
                            "uid": uid, "name": name,
                            "date": datetime.now().strftime("%Y-%m-%d %H:%M")
                        })
                        db["users"][str(uid)]["referred_by"] = inviter_id
                        save_db(db)

    # Automatic free trial: every brand-new user gets 1 free VIP session, no code needed.
    if is_brand_new and not is_admin(uid):
        grant_auto_trial(uid, name)

    if is_admin(uid):
        db_type = "\u2705 PostgreSQL" if DATABASE_URL else "\u26a0\ufe0f Local JSON"
        display = get_display_count()
        await update.message.reply_text(
            f"\u26a1 *EVALON VIP SIGNALS*\n\U0001f4be {db_type}    \U0001f464 Total VIP Members: *{display}*",
            parse_mode="Markdown", reply_markup=kb_admin_start()
        )
        await update.message.reply_text("\U0001f7e2 Ready", reply_markup=kb_session())
        return

    chat_id = update.effective_chat.id
    day = WEEKEND_DAY_NAME()

    if is_weekend():
        if is_vip(uid):
            msg = _random.choice(WEEKEND_VIP_MSGS).format(name=name, day=day)
            await update.message.reply_text(msg, parse_mode="Markdown", protect_content=True)
            await context.bot.send_message(chat_id=update.effective_chat.id, text="\u2800", reply_markup=kb_session())
        else:
            msg = _random.choice(WEEKEND_NOVIP_MSGS).format(name=name, day=day, link=INVITE_LINK)
            await update.message.reply_text(
                msg, parse_mode="Markdown",
                protect_content=True,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("\U0001f3b0 Spin & Win Discount", url=INVITE_LINK),
                     InlineKeyboardButton("\U0001f465 Invite & Earn", url=INVITE_LINK)],
                    [InlineKeyboardButton("\U0001f511 Get VIP Access", callback_data="enter_code")],
                ])
            )
            await context.bot.send_message(chat_id=update.effective_chat.id, text="\u2800", reply_markup=kb_session())
        return

    u = get_user(uid)
    if not u.get("joined_channel"):
        await update.message.reply_text(
            f"\U0001f44b Welcome, *{name}!*\n\n"
            "\u26a1 *EVALON VIP SIGNALS*\n"
            "--------------\n\n"
            "\U0001f4e6 *WHAT YOU GET AS VIP:*\n"
            "--------------\n"
            "\U0001f4ca Daily Trading Signals\n"
            "\u23f1 Multiple Expiry Times\n"
            "\U0001f4c8 BUY/SELL Direction\n"
            "\u2705 WIN/LOSS Results\n"
            "\U0001f525 High Confidence Alerts\n"
            "\U0001f4c9 8-10 Trades Per Day \u2014 Monday to Friday\n"
            "\U0001f4cb Session Start & End Notifications\n\n"
            "--------------\n"
            "To access this bot, first join our official channel:\n\n"
            "\U0001f4e2 *Evalon Winners Channel*\n\n"
            "Tap *Join Our Channel* then *I Have Joined* \U0001f447\n\n"
            f"{WHY_WE_MOVED}\n{KAULI_MBIU}",
            parse_mode="Markdown", reply_markup=kb_join(), protect_content=True
        )
        await asyncio.sleep(1)
        await context.bot.send_video(
            chat_id=chat_id, video=TUTORIAL_VIDEO,
            caption="\U0001f446 *Watch how our VIP bot works!*\n\nSee exactly what you will receive as a VIP member. \U0001f3af",
            parse_mode="Markdown", protect_content=True
        )
        await context.bot.send_message(chat_id=chat_id, text="\u2800", reply_markup=kb_session())
        return

    if not is_vip(uid):
        mday = "\U0001f7e2 Market Open" if is_market_day() else "\U0001f534 Weekend \u2014 resumes Monday."
        await update.message.reply_text(
            f"\U0001f44b Welcome back, *{name}!*\n\n"
            "\u26a1 *EVALON VIP SIGNALS*\n"
            "--------------\n\n"
            "\U0001f512 *VIP ACCESS REQUIRED*\n\n"
            "\u2705 Real market signals \u2014 Monday to Friday\n"
            "\u2705 Non-Martingale strategy only\n"
            "\u2705 High accuracy entries\n"
            "\u2705 Win/Loss updates after every trade\n"
            "\u2705 Consistent signal delivery during market hours\n\n"
            f"\u23f0 *Monday \u2014 Friday only* | {mday}\n\n"
            "--------------\n\n"
            f"{WHY_WE_MOVED}\n"
            "\U0001f511 Have a code? Tap below\n"
            "\U0001f4ac VIP access available through admin approval \U0001f447\n\n"
            f"{KAULI_MBIU}",
            parse_mode="Markdown", reply_markup=kb_locked(), protect_content=True
        )
        await asyncio.sleep(1)
        await context.bot.send_video(
            chat_id=chat_id, video=TUTORIAL_VIDEO,
            caption="\U0001f446 *Watch how our VIP bot works!*\n\nGet your VIP code today and start receiving signals! \U0001f680",
            parse_mode="Markdown", protect_content=True
        )
        await context.bot.send_message(chat_id=chat_id, text="\u2800", reply_markup=kb_session())
        return

    mday = "\U0001f7e2 Market Open" if is_market_day() else "\U0001f534 Weekend \u2014 signals resume Monday."
    await update.message.reply_text(
        f"\U0001f44b Welcome back, *{name}!* \U0001f48e\n\n"
        "\u26a1 *EVALON VIP SIGNALS*\n"
        "--------------\n\n"
        "\U0001f512 *VIP ACCESS REQUIRED*\n\n"
        "\u2705 Real market signals \u2014 Monday to Friday\n"
        "\u2705 Non-Martingale strategy only\n"
        "\u2705 High accuracy entries\n"
        "\u2705 Win/Loss updates after every trade\n"
        "\u2705 Consistent signal delivery during market hours\n\n"
        f"\u23f0 *Monday \u2014 Friday only* | {mday}\n\n"
        "--------------\n\n"
        f"{WHY_WE_MOVED}\n"
        "\U0001f511 Have a code? Tap below\n"
        "\U0001f4ac VIP access available through admin approval\n\n"
        f"{KAULI_MBIU}",
        parse_mode="Markdown", reply_markup=kb_support(), protect_content=True
    )
    await asyncio.sleep(1)
    await context.bot.send_video(
        chat_id=chat_id, video=TUTORIAL_VIDEO,
        caption="\U0001f446 *How to use your VIP signals!*\n\nFollow every signal exactly as shown. Good luck! \U0001f3af",
        parse_mode="Markdown", protect_content=True
    )
    await context.bot.send_message(chat_id=chat_id, text="\u2800", reply_markup=kb_session())


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
    weight    = sig.get("weight", 5)   # 5% for signal 1, 15% for signal 2 (recovery)

    if result == "WIN":
        SESSION_STATS["win_pct"] += weight
        SESSION_STATS["win_count"] += 1
        if weight == 5:
            SESSION_STATS["locked"] = True   # won signal 1 -> stop for this session
    else:
        SESSION_STATS["loss_pct"] += weight
        SESSION_STATS["loss_count"] += 1
    if weight == 15:
        SESSION_STATS["locked"] = True   # signal 2 always ends the session, win or lose

    SESSION_LOG.append({"pair": pair, "expiry": expiry, "direction": direction, "result": result, "weight": weight})
    record_result_weekly(result, 1)

    result_text = msg_win(pair, expiry, direction, weight) if result == "WIN" else msg_loss(pair, expiry, direction, weight)
    sticker_id  = WIN_STICKER if result == "WIN" else LOSS_STICKER

    # Record result to full session log
    FULL_SESSION_LOG.append({"type": "text",    "content": result_text})
    if USE_STICKERS and sticker_id and "PASTE_" not in sticker_id:
        FULL_SESSION_LOG.append({"type": "sticker", "content": sticker_id})

    async def _send_result_one(uid_str):
        uidint = int(uid_str)
        try:
            await context.bot.send_message(chat_id=uidint, text=result_text,
                parse_mode="Markdown", protect_content=True)
            mark_user_blocked(uidint, False)
        except Forbidden:
            mark_user_blocked(uidint, True)
        except Exception as e: logger.warning(f"Result msg failed {uid_str}: {e}")
        if USE_STICKERS and sticker_id and "PASTE_" not in sticker_id:
            try:
                await context.bot.send_sticker(chat_id=uidint, sticker=sticker_id, protect_content=True)
            except Exception as e: logger.warning(f"Result sticker failed {uid_str}: {e}")

    await asyncio.gather(*[_send_result_one(uid_str) for uid_str in msgs])

    if sig_id and sig_id in signals:
        del signals[sig_id]; save_signals(signals)

    icon  = "\u2705" if result == "WIN" else "\u274c"

    # Build full session-style summary for admin (same look as user message)
    win_pct_sofar   = SESSION_STATS["win_pct"]
    loss_pct_sofar  = SESSION_STATS["loss_pct"]
    net_sofar       = win_pct_sofar - loss_pct_sofar
    tot_pct_sofar   = win_pct_sofar + loss_pct_sofar
    acc_sofar       = f"{(win_pct_sofar/tot_pct_sofar*100):.0f}%" if tot_pct_sofar > 0 else "N/A"
    dur_line = ""
    if SESSION_STATS.get("start_time"):
        elapsed = int(time.time() - SESSION_STATS["start_time"])
        mins    = elapsed // 60
        if mins < 60:
            dur_line = f"\u23f1 DURATION : *{mins} min*\n"
        else:
            h = mins // 60; m = mins % 60
            dur_line = f"\u23f1 DURATION : *{h}h {m}min*\n"

    admin_summary = (
        f"\U0001f3c6 *EVALON VVIP WINNERS* \U0001f3c6\n\n"
        "--------------\n"
        f"\U0001f4ca PAIR      : *{pair}*\n"
        f"\u23f1 EXPIRY    : *{expiry} MIN*\n"
        f"\U0001f4c8 DIRECTION : *{direction}*\n"
        f"{icon} RESULT    : *{result} {weight}%*\n"
        "--------------\n\n"
        "\U0001f4ca *SESSION SO FAR:*\n"
        "--------------\n"
        f"\u2705 WIN      : *{win_pct_sofar}%*\n"
        f"\u274c LOSS     : *{loss_pct_sofar}%*\n"
        f"\U0001f4b0 TOTAL     : *{'+' if net_sofar >= 0 else ''}{net_sofar}%*\n"
        f"\U0001f3af ACCURACY  : *{acc_sofar}*\n"
        f"{dur_line}"
        "--------------\n\n"
        "\U0001f48e VVIP MEMBERS ONLY"
    )

    admin_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("\U0001f3c1 End Session", callback_data="end_session")],
    ])

    if query:
        await query.edit_message_text(admin_summary, parse_mode="Markdown", reply_markup=admin_kb)
    else:
        await update.message.reply_text(admin_summary, parse_mode="Markdown", reply_markup=admin_kb)

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
        SESSION_STATS["win_pct"] = SESSION_STATS["loss_pct"] = 0
        SESSION_STATS["win_count"] = SESSION_STATS["loss_count"] = 0
        SESSION_STATS["signal_count"] = 0
        SESSION_STATS["locked"] = False
        SESSION_LOG.clear()
        FULL_SESSION_LOG.clear()
        SESSION_STATS["start_time"] = time.time()
        mins     = 5 if data == "sess_30" else 30
        vip_ids  = get_vip_ids()
        novip_ids= get_novip_ids()
        await send_to_list(context, vip_ids, text=msg_session_soon(mins, is_vip=True))

        # Welcome new free-trial members on their very first session
        db_trial = load_db()
        for vid in vip_ids:
            udata = db_trial["users"].get(str(vid), {})
            if udata.get("trial_sessions_left", 0) > 0 and not udata.get("trial_welcomed"):
                try:
                    await context.bot.send_message(chat_id=vid,
                        text=msg_trial_welcome(udata.get("name", "Trader")),
                        parse_mode="Markdown", protect_content=True)
                    db_trial["users"][str(vid)]["trial_welcomed"] = True
                except Exception as e:
                    logger.warning(f"Trial welcome failed {vid}: {e}")
        save_db(db_trial)

        for nuid in novip_ids:
            try:
                await context.bot.send_message(chat_id=nuid,
                    text=msg_session_soon(mins, is_vip=False),
                    parse_mode="Markdown", reply_markup=kb_get_vip())
            except: pass
        await send_to_list(context, get_all_ids(), text=msg_money_management())
        await q.edit_message_text(
            "\u23f0 *Session alert sent!*\n\nWhen market is ready, tap below \U0001f447",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("\U0001f7e2 Send Session Start Now", callback_data="send_start_now")],
                [InlineKeyboardButton("\u26a0\ufe0f Emergency / Delay",      callback_data="emergency")],
                [InlineKeyboardButton("\U0001f3c1 End Session",             callback_data="end_session")],
            ])
        )
        return

    if data == "send_start_now":
        if not is_admin(uid): return
        vip_ids    = get_vip_ids()
        start_text = (
            "\U0001f3c6 *EVALON VVIP WINNERS* \U0001f3c6\n\n"
            "--------------"+"\n"
            "\U0001f7e2 *SESSION IS STARTING NOW!*\n"
            "--------------"+"\n\n"
            "\u2705 Get your charts ready\n"
            "\u2705 Set your expiry time\n"
            "\u2705 Wait for the signal\n\n"
            "\U0001f525 *First signal incoming!*\n"
            "\U0001f48e VVIP MEMBERS ONLY"
        )
        # Record session start in full log
        FULL_SESSION_LOG.append({"type": "sticker", "content": SESSION_START_STICKER})
        FULL_SESSION_LOG.append({"type": "text",    "content": start_text})
        async def _send_session_start(vid):
            try: await context.bot.send_sticker(chat_id=vid, sticker=SESSION_START_STICKER, protect_content=True)
            except: pass
            try: await context.bot.send_message(chat_id=vid, text=start_text, parse_mode="Markdown", protect_content=True)
            except: pass
        await asyncio.gather(*[_send_session_start(vid) for vid in vip_ids])
        await q.edit_message_text(
            "\U0001f7e2 *Session started!*\n\nSend your first signal now!",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("\u26a0\ufe0f Emergency / Delay", callback_data="emergency")],
                [InlineKeyboardButton("\U0001f3c1 End Session",        callback_data="end_session")],
            ])
        )
        return

    if data == "emergency":
        if not is_admin(uid): return
        context.user_data["awaiting_emergency"] = True
        await q.message.reply_text("\u26a0\ufe0f *Emergency Message*\n\nType your message \u2014 sent to VIP immediately.", parse_mode="Markdown")
        return

    # END SESSION
    if data == "end_session":
        if not is_admin(uid): return
        vip_ids    = get_vip_ids()
        text       = msg_session_end(SESSION_STATS["win_pct"], SESSION_STATS["loss_pct"], SESSION_STATS["win_count"], SESSION_STATS["loss_count"])
        session_id = str(int(time.time()))
        record_session_weekly()
        # Record session end in full log
        FULL_SESSION_LOG.append({"type": "sticker", "content": SESSION_CLOSE_STICKER})
        FULL_SESSION_LOG.append({"type": "text",    "content": text})
        fb_text    = ("\n\n------------------\n\U0001f4dd *Rate today's session:*\n""Tap a number (1 = poor, 5 = excellent)\n\n""------------------\n""\U0001f916 *Auto-Copy Trades on Pocket Option?*\n""Want your trades copied automatically?\n""Tap Contact Admin below to get set up \U0001f447")
        fb_kb      = kb_feedback(session_id)
        async def _send_session_end(vid):
            try: await context.bot.send_sticker(chat_id=vid, sticker=SESSION_CLOSE_STICKER, protect_content=True)
            except: pass
            try: await context.bot.send_message(chat_id=vid, text=text+fb_text,
                    parse_mode="Markdown", reply_markup=fb_kb, protect_content=True)
            except: pass
        await asyncio.gather(*[_send_session_end(vid) for vid in vip_ids])

        # Expire free-trial VIP access: their session is now complete
        db_trial_end = load_db()
        for vid in vip_ids:
            udata = db_trial_end["users"].get(str(vid), {})
            if udata.get("trial_sessions_left", 0) > 0:
                udata["trial_sessions_left"] = 0
                udata["vip"] = False
                udata["trial_completed"] = True
        save_db(db_trial_end)

        # Auto-send account management offer 5 minutes after session ends
        try:
            if context.job_queue:
                context.job_queue.run_once(send_account_management_msg, when=300, name="acct_mgmt")
        except Exception as _je: logger.warning(f"job_queue run_once failed: {_je}")
        sigs = load_signals(); sigs[f"session_{session_id}"] = {"session_id": session_id}; save_signals(sigs)
        win_pct_end = SESSION_STATS["win_pct"]
        loss_pct_end = SESSION_STATS["loss_pct"]
        admin_end_text = (
            f"\U0001f3c1 *SESSION ENDED*\n\n"
            f"\u2705 Win: *{win_pct_end}%* | \u274c Loss: *{loss_pct_end}%*\n\n"
            f"Signals this session: *{len(SESSION_LOG)}*"
        )
        await q.edit_message_text(
            admin_end_text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("\u25b6\ufe0f Replay Session (Preview)", callback_data=f"replay_admin_{session_id}")],
                [InlineKeyboardButton("\U0001f4e2 Send Replay to Non-VIP",     callback_data=f"replay_novip_{session_id}")],
                [InlineKeyboardButton("\U0001f4e2 Send Results to Non-VIP",    callback_data="send_results_novip")],
                [InlineKeyboardButton("\U0001f4ca View Feedback",              callback_data=f"view_fb_{session_id}")],
                [InlineKeyboardButton("\U0001f4e2 Forward Stats to Channel",   callback_data=f"fwd_session_stats_{session_id}")],
                [InlineKeyboardButton("\U0001f4dd Custom Broadcast to VIP",    callback_data="custom_broadcast_vip")],
                [InlineKeyboardButton("\U0001f4dd Custom Broadcast to All",    callback_data="custom_broadcast_all")],
            ])
        )
        return

    if data.startswith("view_fb_"):
        if not is_admin(uid): return
        # Trigger full feedback (real + fake) same as /feedback command
        await feedback_cmd(update, context)
        return

    # Forward session stats to channel
    if data.startswith("fwd_session_stats_"):
        if not is_admin(uid): return
        win_pct_s  = SESSION_STATS["win_pct"]
        loss_pct_s = SESSION_STATS["loss_pct"]
        dur_line = ""
        if SESSION_STATS.get("start_time"):
            elapsed = int(time.time() - SESSION_STATS["start_time"])
            mins    = elapsed // 60
            if mins < 60:
                dur_line = f"\u23f1 DURATION  : *{mins} min*\n"
            else:
                h = mins // 60; m = mins % 60
                dur_line = f"\u23f1 DURATION  : *{h}h {m}min*\n"
        # Build per-trade breakdown
        trades_lines = ""
        for idx, entry in enumerate(SESSION_LOG, 1):
            icon_t = "\u2705" if entry["result"] == "WIN" else "\u274c"
            arrow_t = "\U0001f4c8" if entry["direction"] == "BUY" else "\U0001f4c9"
            trades_lines += f"{idx}\ufe0f\u20e3 {entry['pair']} | {arrow_t} {entry['direction']} | {icon_t} {entry['result']} {entry.get('weight', 5)}%\n"
        channel_stats = (
            "\U0001f3c6 *EVALON VVIP WINNERS* \U0001f3c6\n\n"
            "--------------\n"
            "\U0001f3c1 *SESSION RESULTS*\n"
            "--------------\n\n"
            f"\u2705 WIN      : *{win_pct_s}%*\n"
            f"\u274c LOSS     : *{loss_pct_s}%*\n"
            f"{dur_line}"
            "--------------\n\n"
        )
        if trades_lines:
            channel_stats += (
                "\U0001f4cb *TRADE BREAKDOWN:*\n"
                "--------------\n"
                f"{trades_lines}"
                "--------------\n\n"
            )
        channel_stats += f"{KAULI_MBIU}"
        try:
            await context.bot.send_message(
                chat_id=FEEDBACK_CHANNEL_ID,
                text=channel_stats,
                parse_mode="Markdown"
            )
            await q.answer("\u2705 Session stats sent to channel!", show_alert=True)
        except Exception as e:
            await q.answer(f"\u274c Failed: {e}", show_alert=True)
        return

    # Replay session to admin only (preview)
    if data.startswith("replay_admin_"):
        if not is_admin(uid): return
        if not FULL_SESSION_LOG:
            await q.answer("No session recorded yet.", show_alert=True)
            return
        await q.answer("Sending full preview to you now...", show_alert=False)
        for entry in FULL_SESSION_LOG:
            try:
                if entry["type"] == "text":
                    await context.bot.send_message(chat_id=uid, text=entry["content"], parse_mode="Markdown")
                elif entry["type"] == "sticker":
                    await context.bot.send_sticker(chat_id=uid, sticker=entry["content"])
                await asyncio.sleep(1.2)
            except Exception as e:
                logger.warning(f"Replay admin failed: {e}")
        return

    # Replay session to Non-VIP (as preview to attract them)
    if data.startswith("replay_novip_"):
        if not is_admin(uid): return
        if not SESSION_LOG:
            await q.answer("No signals recorded this session.", show_alert=True)
            return
        novip_ids = get_novip_ids()
        if not novip_ids:
            await q.answer("No non-VIP members found.", show_alert=True)
            return
        await q.answer(f"Sending replay to {len(novip_ids)} non-VIP members...", show_alert=False)
        for entry in SESSION_LOG:
            pair_r = entry["pair"]; exp_r = entry["expiry"]
            dir_r  = entry["direction"]; res_r = entry["result"]; cnt_r = entry.get("weight", 5)
            icon_r = "\u2705" if res_r == "WIN" else "\u274c"
            stk_dir = BUY_STICKER if dir_r == "BUY" else SELL_STICKER
            stk_res = WIN_STICKER if res_r == "WIN" else LOSS_STICKER
            dir_msg = msg_direction(pair_r, exp_r, dir_r)
            res_msg = msg_win(pair_r, exp_r, dir_r, cnt_r) if res_r == "WIN" else msg_loss(pair_r, exp_r, dir_r, cnt_r)
            for nuid in novip_ids:
                try:
                    await context.bot.send_message(chat_id=nuid, text=dir_msg,
                        parse_mode="Markdown", protect_content=True)
                    if USE_STICKERS and "PASTE_" not in stk_dir:
                        await context.bot.send_sticker(chat_id=nuid, sticker=stk_dir, protect_content=True)
                except: pass
            await asyncio.sleep(2)
            for nuid in novip_ids:
                try:
                    await context.bot.send_message(chat_id=nuid, text=res_msg,
                        parse_mode="Markdown", protect_content=True)
                    if USE_STICKERS and "PASTE_" not in stk_res:
                        await context.bot.send_sticker(chat_id=nuid, sticker=stk_res, protect_content=True)
                except: pass
            await asyncio.sleep(2)
        # Send final promo message to non-VIP
        win_pct_r  = SESSION_STATS["win_pct"]
        loss_pct_r = SESSION_STATS["loss_pct"]
        promo = (
            "\U0001f3c6 *EVALON VVIP WINNERS* \U0001f3c6\n\n"
            "--------------\n"
            "That was today's LIVE session \u2014 for VIP members only.\n\n"
            f"\U0001f4ca *SESSION RESULTS:*\n"
            f"\u2705 WIN      : *{win_pct_r}%*\n"
            f"\u274c LOSS     : *{loss_pct_r}%*\n"
            "--------------\n\n"
            "\U0001f48e Want to receive these signals LIVE?\n"
            "Get your VIP access today and never miss a trade!\n\n"
            "\U0001f4dd *Rate today's session:* (1 = poor, 5 = excellent)\n\n"
            f"{KAULI_MBIU}"
        )
        session_id_nv = str(int(time.time()))
        for nuid in novip_ids:
            try:
                await context.bot.send_message(
                    chat_id=nuid, text=promo,
                    parse_mode="Markdown", protect_content=True,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("\u2b50", callback_data=f"fb_{session_id_nv}_1"),
                         InlineKeyboardButton("\u2b50\u2b50", callback_data=f"fb_{session_id_nv}_2"),
                         InlineKeyboardButton("\u2b50\u2b50\u2b50", callback_data=f"fb_{session_id_nv}_3"),
                         InlineKeyboardButton("\u2b50\u2b50\u2b50\u2b50", callback_data=f"fb_{session_id_nv}_4"),
                         InlineKeyboardButton("\u2b50\u2b50\u2b50\u2b50\u2b50", callback_data=f"fb_{session_id_nv}_5")],
                        [InlineKeyboardButton("\U0001f511 Get VIP Access", callback_data="enter_code"),
                         InlineKeyboardButton("\U0001f4ac Contact Admin",  url=SUPPORT_URL)],
                        [InlineKeyboardButton("\U0001f4e2 Invite & Get VIP", url=get_referral_link(nuid))],
                    ])
                )
            except: pass
        await context.bot.send_message(
            chat_id=uid,
            text=f"\u2705 *Replay sent to {len(novip_ids)} non-VIP members!*",
            parse_mode="Markdown"
        )
        return

    # Send session results summary only to Non-VIP (no full replay)
    if data == "send_results_novip":
        if not is_admin(uid): return
        novip_ids = get_novip_ids()
        if not novip_ids:
            await q.answer("No non-VIP members found.", show_alert=True)
            return
        win_pct_r  = SESSION_STATS["win_pct"]
        loss_pct_r = SESSION_STATS["loss_pct"]
        results_msg = (
            "\U0001f3c6 *EVALON VVIP WINNERS* \U0001f3c6\n\n"
            "--------------\n"
            "\U0001f4ca *TODAY'S SESSION RESULTS:*\n"
            "--------------\n"
            f"\u2705 WIN      : *{win_pct_r}%*\n"
            f"\u274c LOSS     : *{loss_pct_r}%*\n"
            "--------------\n\n"
            "\U0001f48e These are the results our VIP members received today!\n"
            "Join VIP and start profiting with us!\n\n"
            "\U0001f4dd *Rate today's session:* (1 = poor, 5 = excellent)\n\n"
            f"{KAULI_MBIU}"
        )
        session_id_nv = str(int(time.time()))

        sent = 0
        for nuid in novip_ids:
            try:
                await context.bot.send_message(
                    chat_id=nuid, text=results_msg,
                    parse_mode="Markdown", protect_content=True,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("\u2b50", callback_data=f"fb_{session_id_nv}_1"),
                         InlineKeyboardButton("\u2b50\u2b50", callback_data=f"fb_{session_id_nv}_2"),
                         InlineKeyboardButton("\u2b50\u2b50\u2b50", callback_data=f"fb_{session_id_nv}_3"),
                         InlineKeyboardButton("\u2b50\u2b50\u2b50\u2b50", callback_data=f"fb_{session_id_nv}_4"),
                         InlineKeyboardButton("\u2b50\u2b50\u2b50\u2b50\u2b50", callback_data=f"fb_{session_id_nv}_5")],
                        [InlineKeyboardButton("\U0001f511 Get VIP Access", callback_data="enter_code"),
                         InlineKeyboardButton("\U0001f4ac Contact Admin",  url=SUPPORT_URL)],
                        [InlineKeyboardButton("\U0001f4e2 Invite & Get VIP", url=get_referral_link(nuid))],
                    ])
                )
                sent += 1
            except: pass
        await q.answer(f"\u2705 Sent to {sent} non-VIP members!", show_alert=True)
        return

    if data.startswith("fb_"):
        parts = data.split("_")
        session_id = parts[1]; rating = int(parts[2])
        context.user_data["fb_session"] = session_id
        context.user_data["fb_rating"]  = rating
        context.user_data["fb_waiting"] = True
        await q.edit_message_reply_markup(reply_markup=None)
        stars = "\u2b50" * rating
        await context.bot.send_message(chat_id=chat,
            text=f"Thank you! You rated: *{stars}*\n\nType a comment or /skip:",
            parse_mode="Markdown")
        return

    if data.startswith("dir_"):
        if not is_admin(uid): return
        parts  = data.split("_", 2)
        action = parts[1]; sig_id = parts[2]
        signals = load_signals()
        if sig_id not in signals: await q.edit_message_text("\u26a0\ufe0f Signal not found."); return
        sig = signals[sig_id]; pair = sig["pair"]; expiry = sig["expiry"]
        trades = sig.get("trades", 1); msgs = sig["msgs"]

        if action == "CANCEL":
            async def _send_cancel(item):
                uid_str, mid = item
                try: await context.bot.edit_message_text(chat_id=int(uid_str), message_id=mid,
                        text=msg_cancelled(pair), parse_mode="Markdown")
                except: pass
            await asyncio.gather(*[_send_cancel(item) for item in msgs.items()])
            del signals[sig_id]; save_signals(signals)
            # A cancelled signal never happened - free up its slot in the 5%/15% sequence
            if SESSION_STATS.get("signal_count", 0) > 0:
                SESSION_STATS["signal_count"] -= 1
            await q.edit_message_text(f"\u274c Signal *{pair}* cancelled.", parse_mode="Markdown")
            return

        direction_text = msg_direction(pair, expiry, action, trades)
        sticker_id     = BUY_STICKER if action == "BUY" else SELL_STICKER
        # Record direction in full session log
        FULL_SESSION_LOG.append({"type": "text",    "content": direction_text})
        if USE_STICKERS and sticker_id and "PASTE_" not in sticker_id:
            FULL_SESSION_LOG.append({"type": "sticker", "content": sticker_id})

        async def _send_direction(uid_str):
            uidint = int(uid_str)
            try:
                await context.bot.send_message(chat_id=uidint, text=direction_text, parse_mode="Markdown", protect_content=True)
                mark_user_blocked(uidint, False)
            except Forbidden:
                mark_user_blocked(uidint, True)
            except Exception as e: logger.warning(f"Dir txt failed {uid_str}: {e}")
            if USE_STICKERS and sticker_id and "PASTE_" not in sticker_id:
                try: await context.bot.send_sticker(chat_id=uidint, sticker=sticker_id, protect_content=True)
                except Exception as e: logger.warning(f"Dir stk failed {uid_str}: {e}")

        await asyncio.gather(*[_send_direction(uid_str) for uid_str in msgs])
        signals[sig_id]["direction"] = action; save_signals(signals)

        arrow   = "\U0001f4c8" if action == "BUY" else "\U0001f4c9"
        color   = "\U0001f7e2" if action == "BUY" else "\U0001f534"
        display = get_display_count()
        # FIX 6: show display count
        await q.edit_message_text(
            f"{arrow} *{color} {action}* sent for *{pair}*!\n\n"
            f"\U0001f4e8 Sent to : *{display}* members\n\n"
            "Select result when trade closes \U0001f447",
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

    # Send trade result to Non-VIP members
    if data.startswith("res_novip_"):
        if not is_admin(uid): return
        parts      = data.split("_", 4)
        nv_pair    = parts[2]
        nv_result  = parts[3]
        nv_count   = parts[4]
        novip_ids  = get_novip_ids()
        if not novip_ids:
            await q.answer("No non-VIP members found.", show_alert=True)
            return
        icon_nv = "\u2705" if nv_result == "WIN" else "\u274c"
        win_pct_nv  = SESSION_STATS["win_pct"]
        loss_pct_nv = SESSION_STATS["loss_pct"]
        novip_msg = (
            "\U0001f3c6 *EVALON VVIP WINNERS* \U0001f3c6\n\n"
            "--------------\n"
            f"\U0001f4ca PAIR      : *{nv_pair}*\n"
            f"{icon_nv} RESULT    : *{nv_result} {int(nv_count)*10}%*\n"
            "--------------\n\n"
            "\U0001f4ca *SESSION SO FAR:*\n"
            "--------------\n"
            f"\u2705 WIN      : *{win_pct_nv}%*\n"
            f"\u274c LOSS     : *{loss_pct_nv}%*\n"
            "--------------\n\n"
            "\U0001f48e *These are LIVE results our VIP members receive!*\n"
            "Get VIP access today and profit with us!\n\n"
            f"{KAULI_MBIU}"
        )
        sent_nv = 0
        for nuid in novip_ids:
            try:
                await context.bot.send_message(
                    chat_id=nuid, text=novip_msg,
                    parse_mode="Markdown", protect_content=True,
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("\U0001f511 Get VIP Access", callback_data="enter_code"),
                        InlineKeyboardButton("\U0001f4ac Contact Admin",  url=SUPPORT_URL),
                    ]])
                )
                sent_nv += 1
            except: pass
        await q.answer(f"\u2705 Sent to {sent_nv} non-VIP members!", show_alert=True)
        return

    # Forward result summary to channel
    if data.startswith("fwd_result_"):
        if not is_admin(uid): return
        # Format: fwd_result_{pair}_{result}_{count}_{sig_id}
        parts     = data.split("_", 5)
        # parts: ['fwd', 'result', pair, result, count, sig_id]
        fwd_pair   = parts[2]
        fwd_result = parts[3]
        fwd_count  = parts[4]
        win_pct_now   = SESSION_STATS["win_pct"]
        loss_pct_now  = SESSION_STATS["loss_pct"]
        icon_now   = "\u2705" if fwd_result == "WIN" else "\u274c"
        channel_text = (
            f"\U0001f3c6 *EVALON VVIP WINNERS* \U0001f3c6\n\n"
            "--------------\n"
            f"\U0001f4ca PAIR      : *{fwd_pair}*\n"
            f"{icon_now} RESULT    : *{fwd_result} {int(fwd_count)*10}%*\n"
            "--------------\n\n"
            "\U0001f4ca *SESSION SO FAR:*\n"
            "--------------\n"
            f"\u2705 WIN      : *{win_pct_now}%*\n"
            f"\u274c LOSS     : *{loss_pct_now}%*\n"
            "--------------\n\n"
            f"{KAULI_MBIU}"
        )
        try:
            await context.bot.send_message(
                chat_id=FEEDBACK_CHANNEL_ID,
                text=channel_text,
                parse_mode="Markdown"
            )
            await q.answer("\u2705 Sent to channel!", show_alert=True)
        except Exception as e:
            await q.answer(f"\u274c Failed: {e}", show_alert=True)
        return

    # FIX 5: clear feedback properly saved to Supabase
    if data == "clear_feedback":
        if not is_admin(uid): return
        save_feedback([])
        await q.edit_message_text("\U0001f5d1\ufe0f *All feedback cleared!*", parse_mode="Markdown"); return

    if data == "clear_real_feedback":
        if not is_admin(uid): return
        save_feedback([])
        await q.edit_message_text("\U0001f5d1\ufe0f *All real feedback cleared!*", parse_mode="Markdown"); return

    # /channelfeedback \u2014 toggle selection checkbox
    if data.startswith("cf_toggle_"):
        if not is_admin(uid): return
        idx = int(data.split("_")[2])
        selected = context.user_data.get("cf_selected", set())
        entries  = context.user_data.get("cf_entries", [])
        if idx in selected:
            selected.discard(idx)
            label = "\u2610 Select"
        else:
            selected.add(idx)
            label = "\u2705 Selected"
        context.user_data["cf_selected"] = selected
        entry = entries[idx] if idx < len(entries) else {}
        try:
            await q.edit_message_reply_markup(
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(label, callback_data=f"cf_toggle_{idx}")
                ]])
            )
        except: pass
        answer_text = "Selected \u2705" if label == "\u2705 Selected" else "Deselected \u2610"
        await q.answer(answer_text)
        return

    # /channelfeedback \u2014 forward selected entries to channel
    if data == "cf_forward":
        if not is_admin(uid): return
        selected = context.user_data.get("cf_selected", set())
        entries  = context.user_data.get("cf_entries", [])
        if not selected:
            await q.answer("\u26a0\ufe0f No entries selected!", show_alert=True)
            return
        await q.answer("Forwarding to channel...", show_alert=False)
        count = 0
        for idx in sorted(selected):
            if idx >= len(entries): continue
            entry = entries[idx]
            channel_text = (
                f"{entry['stars']}\n"
                f"\U0001f464 *{entry['name']}*\n"
                f"\U0001f4ac _{entry['comment']}_\n\n"
                f"\u26a1 *EVALON VIP SIGNALS*\n"
                f"\U0001f4f2 @EvalonwinnersBot"
            )
            try:
                await context.bot.send_message(
                    chat_id=FEEDBACK_CHANNEL_ID,
                    text=channel_text,
                    parse_mode="Markdown"
                )
                count += 1
                await asyncio.sleep(1.5)
            except Exception as e:
                logger.warning(f"cf channel send failed: {e}")
        context.user_data["cf_selected"] = set()
        # Send result as a new message so the selection buttons panel stays visible
        await context.bot.send_message(
            chat_id=chat,
            text=f"\u2705 *Done! Forwarded {count} feedback(s) to channel.*",
            parse_mode="Markdown"
        )
        return

    # Feedback approval \u2014 admin taps \u2705 Approve or \u274c Reject on individual pending item
    if data.startswith("fb_approve_") or data.startswith("fb_reject_"):
        if not is_admin(uid): return
        fb_id   = data.split("_", 2)[2]
        approve = data.startswith("fb_approve_")
        fb_list = load_feedback()
        entry   = next((f for f in fb_list if f.get("id") == fb_id), None)

        if not entry:
            await q.edit_message_text("\u26a0\ufe0f Feedback not found.", parse_mode="Markdown")
            return

        entry["pending"]  = False
        entry["approved"] = approve
        save_feedback(fb_list)

        stars_str = "\u2b50" * entry.get("rating", 5)
        comment   = entry.get("comment", "")
        fb_name   = entry.get("name", "Trader")
        status    = "\u2705 *Approved*" if approve else "\u274c *Rejected*"
        await q.edit_message_text(
            f"{status}\n\n\U0001f464 *{fb_name}*\n{stars_str}\n\U0001f4ac _{comment}_",
            parse_mode="Markdown"
        )
        return

    # Forward selected approved feedback to channel
    if data == "fb_forward_all":
        if not is_admin(uid): return
        fb_list  = load_feedback()
        approved = [f for f in fb_list if f.get("approved") and not f.get("forwarded")]
        if not approved:
            await q.edit_message_text("\u26a0\ufe0f No approved feedback to forward.", parse_mode="Markdown")
            return
        count = 0
        for entry in approved:
            stars_str = "\u2b50" * entry.get("rating", 5)
            comment   = entry.get("comment", "")
            fb_name   = entry.get("name", "Trader")
            channel_text = (
                f"{stars_str}\n"
                f"\U0001f464 *{fb_name}*\n"
                f"\U0001f4ac _{comment}_\n\n"
                f"\u26a1 *EVALON VIP SIGNALS*\n"
                f"\U0001f4f2 @EvalonwinnersBot"
            )
            try:
                await context.bot.send_message(
                    chat_id=FEEDBACK_CHANNEL_ID,
                    text=channel_text,
                    parse_mode="Markdown"
                )
                entry["forwarded"] = True
                count += 1
                await asyncio.sleep(1.5)
            except Exception as e:
                logger.warning(f"Channel forward failed: {e}")
        save_feedback(fb_list)
        await q.edit_message_text(
            f"\u2705 *Forwarded {count} feedback(s) to channel!*",
            parse_mode="Markdown"
        )
        return

    # Custom broadcast: admin types a message, sent to VIP or all
    if data in ("custom_broadcast_vip", "custom_broadcast_all"):
        if not is_admin(uid): return
        context.user_data["awaiting_custom_broadcast"] = data
        await context.bot.send_message(
            chat_id=chat,
            text=(
                "\U0001f4dd *Custom Broadcast*\n\n"
                "Type your message below.\n"
                "It will be sent to *VIP only* if you tapped VIP, or *all members* if you tapped All.\n\n"
                "Send /cancel to cancel."
            ),
            parse_mode="Markdown"
        )
        return

    if data == "trigger_start":
        # SESSION button - behave exactly like /start
        fake_update = update
        await start(fake_update, context)
        return

    if data == "check_join":
        # Verify real membership or pending join request
        is_member = False
        try:
            member = await context.bot.get_chat_member(
                chat_id=CHANNEL_NUMERIC_ID, user_id=uid
            )
            status = member.status
            # Accept: member, administrator, creator, or restricted (still in channel)
            # Also accept: left with pending request \u2014 caught below
            if status in ("member", "administrator", "creator", "restricted"):
                is_member = True
        except Exception as e:
            logger.warning(f"get_chat_member failed: {e}")
            # If bot can't check (not admin in channel), fall through to trust
            is_member = True

        if not is_member:
            # Check if they have a pending join request via get_chat_member returning 'left'
            # Telegram doesn't expose pending requests directly \u2014 we check via ChatMember
            # Strategy: if status is 'left' we check if they tapped join (we can't verify)
            # Show them a message to send request first
            await q.answer(
                "\u26a0\ufe0f You have not joined yet. Please send a join request first.",
                show_alert=True
            )
            return

        update_user(uid, {"joined_channel": True, "name": name})
        try: await q.message.delete()
        except: pass
        mday = "\U0001f7e2 Market open!" if is_market_day() else "\U0001f534 Weekend \u2014 resumes Monday."
        if is_vip(uid):
            await context.bot.send_message(chat_id=chat,
                text=f"\u2705 *Joined! Welcome back, {name}!*\n\n{mday}",
                parse_mode="Markdown", reply_markup=kb_support(), protect_content=True)
        else:
            await context.bot.send_message(chat_id=chat,
                text=f"\u2705 *Channel joined! Welcome, {name}!*\n\n"
                     "\U0001f512 *VIP ACCESS REQUIRED*\n\n"
                     "\u2705 Real market signals \u2014 Mon to Fri\n"
                     "\u2705 Non-Martingale strategy\n"
                     "\u2705 Win/Loss updates\n\n"
                     f"\u23f0 Mon\u2013Fri only | {mday}\n\n"
                     "\U0001f511 Have a VIP code? Tap below \U0001f447",
                parse_mode="Markdown", reply_markup=kb_locked(), protect_content=True)
        return

    if data == "enter_code":
        context.user_data["awaiting_code"] = True
        try: await q.message.delete()
        except: pass
        await context.bot.send_message(chat_id=chat,
            text="\U0001f511 *Enter your VIP code:*\n\nFormat: `VIP-XXXX-XXXX-XXXX`\n\nContact admin if you need one \U0001f447",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("\U0001f4ac Contact Admin", url=SUPPORT_URL)]]))
        return

# ============================================================
# TEXT HANDLER
# ============================================================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    name = update.effective_user.first_name or "Trader"
    text = update.message.text.strip()

    # SESSION keyboard button - same as /start
    if text == "SESSION":
        await start(update, context)
        return

    if update.message.forward_date and not is_admin(uid):
        try: await update.message.delete()
        except: pass
        await update.message.reply_text(
            "\U0001f512 *Forwarding is not allowed in this bot.*\n\nAll content is protected.",
            parse_mode="Markdown"
        )
        return

    if is_admin(uid):
        if text == "/skip": context.user_data["fb_waiting"] = False; return

        if text == "/cancel":
            context.user_data.pop("awaiting_custom_broadcast", None)
            context.user_data.pop("awaiting_emergency", None)
            await update.message.reply_text("\u274c Cancelled.", parse_mode="Markdown")
            return

        if context.user_data.get("awaiting_custom_broadcast"):
            mode = context.user_data.pop("awaiting_custom_broadcast")
            if mode == "custom_broadcast_vip":
                targets = get_vip_ids()
                label = "VIP"
            else:
                targets = get_all_ids()
                label = "All"
            if not targets:
                await update.message.reply_text("\u26a0\ufe0f No members found.", parse_mode="Markdown")
                return
            sent, failed = await send_to_list(context, targets, text=text, parse_mode=None)
            await update.message.reply_text(
                f"\u2705 *Broadcast sent!*\n\n\U0001f465 {label}: \u2705 *{sent}* sent | \u274c *{failed}* failed",
                parse_mode="Markdown"
            )
            return

        if context.user_data.get("awaiting_emergency"):
            context.user_data["awaiting_emergency"] = False
            vip_ids = get_vip_ids()
            await send_to_list(context, vip_ids, text=(
                "\U0001f3c6 *EVALON VVIP WINNERS* \U0001f3c6\n\n"
                "--------------"+"\n\u26a0\ufe0f *IMPORTANT UPDATE*\n"+"--------------"+"\n\n"
                f"{text}\n\n\U0001f48e VVIP MEMBERS ONLY"
            ))
            await update.message.reply_text("\u26a0\ufe0f *Emergency message sent!*", parse_mode="Markdown", protect_content=True,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("\U0001f7e2 Send Session Start Now", callback_data="send_start_now")],
                    [InlineKeyboardButton("\u26a0\ufe0f Emergency / Delay", callback_data="emergency")],
                    [InlineKeyboardButton("\U0001f3c1 End Session", callback_data="end_session")],
                ]))
            return

        # CANDLE-CLOSE PLAN: admin sends two words e.g. "buy sell" while a signal is
        # live and direction hasn't been sent yet. Replaces the old "type a number" trick.
        cwords = text.strip().lower().split()
        if len(cwords) == 2 and cwords[0] in ("buy", "sell") and cwords[1] in ("buy", "sell"):
            signals = load_signals()
            pend_id, pend_sig = find_pending_signal(signals)
            if not pend_sig:
                await update.message.reply_text("\u26a0\ufe0f No signal waiting for direction right now.")
                return
            pend_targets = [int(k) for k in pend_sig.get("msgs", {})]
            cond_text = msg_candle_plan(pend_sig["pair"], pend_sig["expiry"], cwords[0].upper(), cwords[1].upper())
            FULL_SESSION_LOG.append({"type": "text", "content": cond_text})
            await send_to_list(context, pend_targets, text=cond_text)
            try: await update.message.delete()
            except: pass
            return

        # SIGNAL: e.g. EURUSD 1
        parsed = parse_signal(text)
        if not parsed: return
        pair, expiry = parsed

        # Capital-protection lock: max 2 signals per session (5% then 15% recovery)
        if SESSION_STATS.get("locked") or SESSION_STATS.get("signal_count", 0) >= 2:
            await update.message.reply_text(
                "\u26a0\ufe0f *Session limit reached (2 signals).*\n\n"
                "To protect your capital, no more signals will be sent this session. "
                "End the session and wait for the next one.",
                parse_mode="Markdown")
            return

        weight = 5 if SESSION_STATS.get("signal_count", 0) == 0 else 15

        targets = get_all_ids() if PUBLIC_SIGNAL_MODE else get_vip_ids()
        if not targets: await update.message.reply_text("\u26a0\ufe0f No members yet."); return
        try: await update.message.delete()
        except: pass

        sent_msgs = {}
        async def _send_preparing(vid):
            try:
                m = await context.bot.send_message(chat_id=vid, text=msg_preparing(pair, expiry, weight),
                    parse_mode="Markdown", protect_content=True)
                mark_user_blocked(vid, False)
                return str(vid), m.message_id
            except Forbidden:
                mark_user_blocked(vid, True); return None, None
            except Exception as e:
                logger.warning(f"Send failed {vid}: {e}"); return None, None

        results = await asyncio.gather(*[_send_preparing(vid) for vid in targets])
        for vid_str, mid in results:
            if vid_str: sent_msgs[vid_str] = mid

        sig_id = f"{pair.replace('/','').replace(' ','')}_{expiry}_{int(time.time())}"
        signals = load_signals()
        signals[sig_id] = {"pair": pair, "expiry": expiry, "weight": weight,
                            "msgs": sent_msgs, "time": datetime.now().strftime("%H:%M")}
        save_signals(signals)
        SESSION_STATS["signal_count"] = SESSION_STATS.get("signal_count", 0) + 1

        display = get_display_count()
        mode_note = " (VIP + Non-VIP)" if PUBLIC_SIGNAL_MODE else ""
        await context.bot.send_message(chat_id=uid,
            text=f"\u2705 Signal sent to *{display}* members{mode_note}!\n\n"
                 f"\U0001f4ca *{pair}*  |  \u23f1 *{expiry} MIN*  |  \U0001f4b0 *{weight}%*\n\n"
                 "Choose direction when ready \U0001f447",
            parse_mode="Markdown", reply_markup=kb_direction(sig_id))
        return

    # USER: feedback
    if context.user_data.get("fb_waiting"):
        session_id = context.user_data.pop("fb_session", "")
        rating     = context.user_data.pop("fb_rating", 0)
        context.user_data["fb_waiting"] = False
        comment = text if text != "/skip" else ""

        # Save to DB as pending (awaiting admin approval)
        fb_list = load_feedback()
        fb_id   = str(uuid.uuid4())[:8]
        fb_entry = {
            "id":         fb_id,
            "session_id": session_id,
            "user_id":    uid,
            "name":       name,
            "rating":     rating,
            "comment":    comment,
            "date":       datetime.now().strftime("%Y-%m-%d %H:%M"),
            "approved":   False,
            "pending":    True,
        }
        fb_list.append(fb_entry)
        save_feedback(fb_list)

        # Thank the member \u2014 no admin notification (feedback saved silently)
        await update.message.reply_text(
            "\u2705 *Thank you for your feedback!*\n\nSee you in the next session! \U0001f3af",
            parse_mode="Markdown"
        )
        # Feedback saved silently \u2014 admin can view anytime via /realfeedbacks
        logger.info(f"Feedback saved silently: user={uid} name={name} rating={rating} id={fb_id}")
        return

    # Accept code directly even without pressing button first
    if not context.user_data.get("awaiting_code"):
        # Check if it looks like a VIP code
        if text.upper().startswith("VIP-"):
            context.user_data["awaiting_code"] = True
        elif not is_vip(uid):
            await update.message.reply_text("\U0001f512 Please enter your VIP code.", reply_markup=kb_locked())
            return
        else:
            return  # VIP user sent random text \u2014 ignore silently

    # Safety: only treat as code if it really looks like one
    if not text.upper().startswith("VIP-"):
        context.user_data["awaiting_code"] = False
        return

    code = text.upper()
    context.user_data["awaiting_code"] = False
    result = activate_code(code, uid, name)
    if result is True:
        mday = "\U0001f7e2 Market open \u2014 signals active!" if is_market_day() else "\U0001f534 Weekend \u2014 signals resume Monday."
        await update.message.reply_text(
            f"\u2705 *VIP Access Activated! Welcome, {name}!* \U0001f389\n\n"
            "\u26a1 *EVALON VIP SIGNALS*\n\nYou are now a *VIP Member* \U0001f3af\n\n"
            "\u2705 Real market signals \u2014 Mon to Fri\n\u2705 Non-Martingale strategy\n"
            f"\u2705 Win/Loss updates\n\n{mday}\n\nStay active \u2014 signals arrive here \U0001f4e9",
            parse_mode="Markdown", reply_markup=kb_support(), protect_content=True)
    elif result == "trial_abuse":
        await update.message.reply_text(
            "\U0001f6ab *Free Trial Not Available*\n\n"
            "It looks like you have already used a Free Trial on this account before.\n\n"
            "Each user is eligible for *one Free Trial only*.\n\n"
            "To continue receiving VIP signals, please contact admin to subscribe to a full VIP plan. "
            "We have flexible options starting from 1 month.\n\n"
            "\U0001f4aa *Thank you for being part of Evalon Trader \u2014 let\u2019s take it to the next level!*",
            parse_mode="Markdown", reply_markup=kb_support(), protect_content=True)
    else:
        db   = load_db(); cdat = db["codes"].get(code)
        if cdat and cdat.get("used"):
            await update.message.reply_text(
                "\u274c *This code has already been used!*\n\nContact admin for your own code:",
                parse_mode="Markdown", reply_markup=kb_locked(), protect_content=True)
        else:
            await update.message.reply_text("\u274c *Invalid VIP code!*\n\nContact admin:",
                parse_mode="Markdown", reply_markup=kb_locked(), protect_content=True)

# ============================================================
# MEDIA \u2014 FIX 8: direct to VIP with watermark, no file_id
# ============================================================
async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        if context.user_data.get("fb_waiting"):
            await update.message.reply_text("\u270f\ufe0f Please send text only or /skip.", parse_mode="Markdown"); return
        if update.message.forward_date:
            try: await update.message.delete()
            except: pass
            await update.message.reply_text("\U0001f512 Forwarding is not allowed.")
        return

    if context.user_data.get("awaiting_welcome_image"):
        context.user_data["awaiting_welcome_image"] = False
        msg = update.message
        if msg.photo:
            db = load_db(); db["welcome_image"] = msg.photo[-1].file_id; save_db(db)
            await update.message.reply_text("\u2705 *Welcome image saved!*", parse_mode="Markdown")
        else:
            await update.message.reply_text("\u274c Please send a photo only.")
        return

    # FIX 8: if /getid mode active, reply with file_id
    if context.user_data.get("awaiting_file_id"):
        context.user_data["awaiting_file_id"] = False
        msg = update.message; fid = None
        if msg.photo: fid = f"PHOTO: `{msg.photo[-1].file_id}`"
        elif msg.video: fid = f"VIDEO: `{msg.video.file_id}`"
        elif msg.animation: fid = f"GIF: `{msg.animation.file_id}`"
        if fid:
            await update.message.reply_text(f"\U0001f4ce *FILE ID:*\n\n{fid}", parse_mode="Markdown"); return

    # Default: photo \u2192 VIP only (with watermark), video \u2192 VIP + Non-VIP
    msg = update.message
    vip_ids   = get_vip_ids()
    novip_ids = get_novip_ids()
    all_ids   = get_all_ids()
    sent = 0
    if msg.photo:
        # Photo \u2192 VIP only
        # Watermark ONCE (no user ID), reuse file_id for all members (fast)
        if not vip_ids: await msg.reply_text("\u26a0\ufe0f No VIP members yet."); return
        cached_file_id = None
        try:
            file    = await context.bot.get_file(msg.photo[-1].file_id)
            raw_img = bytes(await file.download_as_bytearray())
            wm      = add_watermark(raw_img, user_id=None)  # single watermark, no ID
            bio     = __import__("io").BytesIO(wm); bio.name = "signal.jpg"
            # Send to first member, get back file_id to reuse for rest
            first_id = vip_ids[0]
            sent_msg = await context.bot.send_photo(
                chat_id=first_id, photo=bio,
                caption=msg.caption, parse_mode="Markdown", protect_content=True)
            cached_file_id = sent_msg.photo[-1].file_id
            sent += 1
        except Exception as e:
            logger.warning(f"Photo watermark/first send failed: {e}")

        for vid in vip_ids[1:]:
            try:
                if cached_file_id:
                    await context.bot.send_photo(
                        chat_id=vid, photo=cached_file_id,
                        caption=msg.caption, parse_mode="Markdown", protect_content=True)
                else:
                    await context.bot.send_photo(
                        chat_id=vid, photo=msg.photo[-1].file_id,
                        caption=msg.caption, parse_mode="Markdown", protect_content=True)
                sent += 1
            except Exception as e:
                logger.warning(f"Photo send failed {vid}: {e}")
        if sent:
            await msg.reply_text(f"\u2705 Photo sent to *{sent}* VIP members!", parse_mode="Markdown")
    elif msg.video:
        # Video \u2192 VIP + Non-VIP + Channel (no protect_content, watermark per user)
        targets = list(set(vip_ids + novip_ids))
        if not targets: await msg.reply_text("\u26a0\ufe0f No members yet."); return

        # Download video once
        processing_msg = await msg.reply_text("\u23f3 Processing video watermark...")
        try:
            file = await context.bot.get_file(msg.video.file_id)
            raw_video = bytes(await file.download_as_bytearray())
        except Exception as e:
            logger.warning(f"Video download failed: {e}")
            raw_video = None

        sent_vip = sent_novip = 0
        for tid in targets:
            try:
                if raw_video:
                    wm_video = await add_video_watermark(raw_video, user_id=tid)
                    bio = __import__("io").BytesIO(wm_video); bio.name = "video.mp4"
                    await context.bot.send_video(
                        chat_id=tid, video=bio,
                        caption=msg.caption, parse_mode="Markdown",
                        protect_content=False
                    )
                else:
                    await context.bot.send_video(
                        chat_id=tid, video=msg.video.file_id,
                        caption=msg.caption, parse_mode="Markdown",
                        protect_content=False
                    )
                if tid in vip_ids: sent_vip += 1
                else: sent_novip += 1
            except Exception as e:
                logger.warning(f"Video send failed {tid}: {e}")

        # Send to channel (no per-user watermark, use generic watermark)
        sent_channel = False
        try:
            if raw_video:
                ch_video = await add_video_watermark(raw_video)
                bio_ch = __import__("io").BytesIO(ch_video); bio_ch.name = "video.mp4"
                await context.bot.send_video(
                    chat_id=CHANNEL_NUMERIC_ID, video=bio_ch,
                    caption=msg.caption, parse_mode="Markdown"
                )
            else:
                await context.bot.send_video(
                    chat_id=CHANNEL_NUMERIC_ID, video=msg.video.file_id,
                    caption=msg.caption, parse_mode="Markdown"
                )
            sent_channel = True
        except Exception as e:
            logger.warning(f"Video to channel failed: {e}")

        try: await processing_msg.delete()
        except: pass

        ch_status = "\u2705 Channel" if sent_channel else "\u274c Channel failed"
        await msg.reply_text(
            f"\u2705 Video sent!\n\n\U0001f48e VIP: *{sent_vip}* | \U0001f513 Non-VIP: *{sent_novip}*\n{ch_status}",
            parse_mode="Markdown"
        )
    elif msg.animation:
        targets = list(set(vip_ids + novip_ids))
        sent, _ = await send_to_list(context, targets, animation=msg.animation.file_id, caption=msg.caption)
        if sent:
            await msg.reply_text(f"\u2705 GIF sent to *{sent}* members!", parse_mode="Markdown")

# ============================================================
# STICKER HANDLER
# ============================================================
async def handle_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        if update.message.forward_date:
            try: await update.message.delete()
            except: pass
            await update.message.reply_text("\U0001f512 Forwarding is not allowed.")
        return
    sticker = update.message.sticker
    if not sticker: return
    fid = sticker.file_id
    # FIX 8: /getid mode for file_ids
    if context.user_data.get("awaiting_file_id"):
        context.user_data["awaiting_file_id"] = False
        await update.message.reply_text(
            f"\U0001f4ce *STICKER FILE ID:*\n\n`{fid}`\n\nPaste into BUY/SELL/WIN/LOSS sticker variables.",
            parse_mode="Markdown"); return
    # Default: broadcast sticker
    vip_ids = get_vip_ids()
    if vip_ids:
        await send_to_list(context, vip_ids, sticker=fid)
        display = get_display_count()
        await update.message.reply_text(f"\u2705 Sticker sent to *{display}* members!", parse_mode="Markdown")

# ============================================================
# /getid \u2014 get file_id of next sticker/photo
# ============================================================
async def cmd_getid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    context.user_data["awaiting_file_id"] = True
    await update.message.reply_text("\U0001f4ce *Send sticker or photo now*\n\nI will reply with the file\\_id.", parse_mode="Markdown")

# ============================================================
# /broadcast
# ============================================================
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid): return
    args    = context.args or []
    to_all  = args and args[0].lower() == "all"
    # Preserve full text including newlines - extract from raw message text
    raw_text = update.message.text or ""
    cmd_end  = raw_text.find(" ", 1)  # skip /broadcast
    if cmd_end == -1:
        caption = ""
    else:
        rest = raw_text[cmd_end+1:]
        if to_all:
            # skip the "all" keyword
            all_end = rest.find(" ")
            caption = rest[all_end+1:] if all_end != -1 else ""
        else:
            caption = rest
    replied = update.message.reply_to_message
    targets = get_all_ids() if to_all else get_vip_ids()
    if not targets: await update.message.reply_text("\u26a0\ufe0f No users yet."); return
    sent = 0
    if replied:
        if replied.photo:
            try:
                file    = await context.bot.get_file(replied.photo[-1].file_id)
                raw_img = bytes(await file.download_as_bytearray())
            except:
                raw_img = None
            cap = replied.caption or caption or None
            for tid in targets:
                try:
                    if raw_img:
                        wm  = add_watermark(raw_img, user_id=tid)
                        bio = __import__("io").BytesIO(wm); bio.name = "signal.jpg"
                        await context.bot.send_photo(chat_id=tid, photo=bio,
                            caption=cap, parse_mode="Markdown", protect_content=True)
                    else:
                        await context.bot.send_photo(chat_id=tid, photo=replied.photo[-1].file_id,
                            caption=cap, parse_mode="Markdown", protect_content=True)
                    sent += 1
                except Exception as e:
                    logger.warning(f"Broadcast photo failed {tid}: {e}")
        elif replied.video:
            vid_caption = (replied.caption or caption or "").strip()
            sent, _ = await send_to_list(context, targets, video=replied.video.file_id, caption=vid_caption)
        elif replied.sticker: sent, _ = await send_to_list(context, targets, sticker=replied.sticker.file_id)
        elif replied.animation: sent, _ = await send_to_list(context, targets, animation=replied.animation.file_id, caption=replied.caption or caption or None)
        else: sent, _ = await send_to_list(context, targets, text=replied.text or caption)
    elif caption:
        # send as plain text to preserve exact formatting/newlines
        sent, _ = await send_to_list(context, targets, text=caption, parse_mode=None)
    else:
        await update.message.reply_text(
            "\U0001f4e2 *Broadcast:*\n`/broadcast text` \u2192 VIP\n`/broadcast all text` \u2192 Everyone\nOr reply to media.",
            parse_mode="Markdown"); return
    who = "everyone" if to_all else "VIP"
    display = get_display_count()
    await update.message.reply_text(f"\U0001f4e1 *Broadcast complete!*\n\U0001f465 {who} | \u2705 Sent to *{display}* members", parse_mode="Markdown")

# ============================================================
# /session, /end
# ============================================================
async def session_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    await update.message.reply_text("\u23f0 *Session start alert \u2014 select timing:*",
        parse_mode="Markdown", reply_markup=kb_session_timing())

async def end_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    vip_ids    = get_vip_ids()
    text       = msg_session_end(SESSION_STATS["win_pct"], SESSION_STATS["loss_pct"], SESSION_STATS["win_count"], SESSION_STATS["loss_count"])
    session_id = str(int(time.time()))
    fb_text    = (
        "\n\n------------------\n\U0001f4dd *Rate today's session:*\n"
        "Tap a number (1 = poor, 5 = excellent)\n\n"
        "------------------\n"
        "\U0001f916 *Auto-Copy Trades on Pocket Option?*\n"
        "Want your trades copied automatically?\n"
        "Tap Contact Admin below to get set up \U0001f447"
    )
    # FIX 4: VIP only
    for vid in vip_ids:
        try: await context.bot.send_message(chat_id=vid, text=text+fb_text,
                parse_mode="Markdown", reply_markup=kb_feedback(session_id))
        except: pass

    # Expire free-trial VIP access: their session is now complete
    db_trial_end = load_db()
    for vid in vip_ids:
        udata = db_trial_end["users"].get(str(vid), {})
        if udata.get("trial_sessions_left", 0) > 0:
            udata["trial_sessions_left"] = 0
            udata["vip"] = False
            udata["trial_completed"] = True
    save_db(db_trial_end)

    sigs = load_signals(); sigs[f"session_{session_id}"] = {"session_id": session_id}; save_signals(sigs)
    # Auto-send account management offer 5 minutes after session ends
    try:
        if context.job_queue:
            context.job_queue.run_once(send_account_management_msg, when=300, name="acct_mgmt")
    except Exception as _je: logger.warning(f"job_queue run_once failed: {_je}")
    # FIX 7: clean message
    await update.message.reply_text("\U0001f3c1 *Session ended!*\n\nTap below to see feedback \U0001f447",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("\U0001f4ca View Feedback", callback_data=f"view_fb_{session_id}")]]))

# ============================================================
# GLOBAL NAME POOL - diverse names from all regions
# ============================================================
_GLOBAL_NAMES = [
    "James","Ali","Sarah","Mike","John","David","Kevin","Chris","Tony","Eric",
    "Omar","Hassan","Sam","Felix","Joel","Musa","Bilal","Zara","Aisha","Fatima",
    "Nina","Grace","Nadia","Victor","Patrick","Raymond","George","Simon","Thomas",
    "Nathan","Daniel","Andrew","Marcus","Leon","Paul","Rita","Diana","Sandra",
    "Julia","Helen","Vera","Cindy","Monica","Irene","Ruth","Ivan","Bruno",
    "Khalid","Yusuf","Hamza","Samir","Nour","Layla","Mariam","Rania",
    "Amira","Kareem","Walid","Faris","Ziad","Hana","Sana","Rana","Dina","Lina",
    "Ahmad","Mohammed","Abdullah","Ibrahim","Mustafa","Yasmin","Salma","Heba",
    "Raj","Arjun","Vikram","Rohan","Priya","Ananya","Kavya","Rahul","Amit","Sanjay",
    "Ravi","Deepak","Suresh","Naveen","Kiran","Pooja","Neha","Asha","Meera","Divya",
    "Imran","Faisal","Usman","Ayesha","Zainab","Hira","Sadia","Farid",
    "Adeel","Shahid","Junaid","Rizwan","Asma","Saira","Waqar","Kamran",
    "Budi","Andi","Dian","Sari","Rizky","Farhan","Nurul","Putri","Dewi","Agus",
    "Hendra","Wahyu","Indra","Fitri","Rina","Yuli","Bayu","Fajar","Dito",
    "Carlos","Miguel","Diego","Luis","Juan","Ana","Maria","Rosa","Elena","Sofia",
    "Pedro","Rafael","Fernando","Gabriel","Valentina","Isabella","Camila","Lucia",
    "Alexei","Dmitri","Sergei","Pavel","Natasha","Olga","Viktor","Andrei",
    "Wei","Jing","Xiao","Ming","Ling","Chen","Jin","Park","Kim",
    "Kofi","Kwame","Ama","Yaw","Kwesi","Adwoa","Kojo","Akosua",
    "Chidi","Emeka","Ngozi","Ike","Adaeze","Tunde","Bisi","Femi","Yemi","Sola",
    "Tendai","Chipo","Farai","Tatenda","Rudo","Simba","Tariro",
]
_LAST_INITIALS = list("ABCDEFGHJKLMNOPRSTWY")

def _make_global_name(used):
    import random as _r
    for _ in range(40):
        base = _r.choice(_GLOBAL_NAMES)
        first = base.split()[0]
        full = (first + " " + _r.choice(_LAST_INITIALS)) if _r.random() < 0.40 else first
        if full not in used:
            used.add(full)
            return full
    return base.split()[0]

# ============================================================
# GLOBAL NAME POOL
# ============================================================
_GLOBAL_NAMES = [
    "James","Ali","Sarah","Mike","John","David","Kevin","Chris","Tony","Eric",
    "Omar","Hassan","Sam","Felix","Ivan","Bruno","Joel","Musa","Bilal","Zara",
    "Aisha","Fatima","Nina","Grace","Nadia","Victor","Patrick","Raymond","George",
    "Simon","Thomas","Nathan","Daniel","Andrew","Marcus","Leon","Paul","Rita",
    "Diana","Sandra","Julia","Helen","Vera","Cindy","Monica","Irene","Ruth",
    "Khalid","Yusuf","Hamza","Samir","Layla","Mariam","Rania","Amira","Kareem",
    "Raj","Arjun","Priya","Rahul","Amit","Kiran","Pooja","Neha","Imran","Faisal",
    "Usman","Ayesha","Zainab","Adeel","Rizwan","Carlos","Miguel","Diego","Sofia",
    "Kofi","Kwame","Ama","Chidi","Emeka","Ngozi","Tunde","Femi","Simba","Farai",
    "John K","Ali B","Sarah M","David T","Mike O","James K","Chris A","Eric B",
    "Tony M","Omar A","Sam L","Felix K","Ivan D","Bruno T","Joel R","Musa H",
    "Raj K","Imran A","Khalid M","Carlos R","Kofi A","Chidi B","Priya S","Ayesha N",
]
_LAST_INITIALS = list("ABCDEFGHJKLMNOPRSTWY")

def _make_global_name(used):
    import random as _r
    for _ in range(40):
        base = _r.choice(_GLOBAL_NAMES)
        first = base.split()[0]
        full = (first + " " + _r.choice(_LAST_INITIALS)) if _r.random() < 0.40 else first
        if full not in used:
            used.add(full); return full
    return base.split()[0]

# ============================================================
# /feedback - real + fake mixed, no approval needed
# ============================================================
async def cmd_myinvites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid   = update.effective_user.id
    link  = get_referral_link(uid)
    refs  = get_referral_list(uid)
    count = len(refs)
    lines = [
        "\U0001f465 *YOUR INVITE DASHBOARD*\n",
        f"\n\U0001f517 Your link:\n`{link}`\n",
        f"\n\U0001f4ca People invited: *{count}*\n",
    ]
    if refs:
        lines.append("\n--------------\n")
        for r in refs[-20:]:
            lines.append(f"\U0001f464 {r.get('name','?')}  |  \U0001f4c5 {r.get('date','?')}\n")
        if count > 20:
            lines.append(f"\n_...and {count - 20} more_\n")
    else:
        lines.append("\nShare your link above \u2014 once someone joins through it, they'll show up here!\n")
    lines.append(f"\n\U0001f525 The more you invite, the more free VIP access you can earn.\n")
    await update.message.reply_text(
        "".join(lines), parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("\U0001f4e2 Share Invite Link", url=f"https://t.me/share/url?url={link}"),
        ]])
    )

async def feedback_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    import random

    wins    = SESSION_STATS.get("wins", 0)
    losses  = SESSION_STATS.get("losses", 0)
    total   = wins + losses
    acc_pct = int(wins/total*100) if total > 0 else 100
    acc_str = f"{wins}/{total}" if total > 0 else "all"

    _jamt1 = random.choice([1134, 1278, 1403, 1551, 1687, 1812, 1956, 2103, 2287, 2467])
    JOINED_TODAY = [
        f"First session here and already {wins} out of {total} won. This is unbelievable",
        f"Joined today. Already made ${_jamt1} just following the signals. No joke",
    ]

    SMALL_AMOUNTS  = [812,847,873,916,954,978,1023,1087,1134,1178,1215,1267,1312,1389,1423,1478]
    MEDIUM_AMOUNTS = [1534,1612,1689,1743,1823,1956,2012,2089,2134,2234,2389,2512,2678,2834,2967]
    LARGE_AMOUNTS  = [3123,3289,3456,3612,3789,3956,4123,4312,4478,4634,4812,4978,5134,5312,5567]
    XLARGE_AMOUNTS = [5812,6134,6389,6623,6978,7234,7512,7823,8134,8456,8712,9234,9789,10123,10789]
    ALL_AMOUNTS    = SMALL_AMOUNTS + MEDIUM_AMOUNTS + LARGE_AMOUNTS + XLARGE_AMOUNTS
    used_amounts   = set()

    def get_unique_amount(pool=None):
        src = pool if pool else ALL_AMOUNTS
        available = [a for a in src if a not in used_amounts]
        if not available: available = src
        amt = random.choice(available)
        used_amounts.add(amt)
        return amt

    used_comments = set()
    def win_comment():
        a1 = get_unique_amount(SMALL_AMOUNTS + MEDIUM_AMOUNTS)
        a2 = get_unique_amount(LARGE_AMOUNTS + XLARGE_AMOUNTS)
        _SHORT = [
            f"Boss signals were clean today",
            f"King you never disappoint",
            f"Brother every single one hit today",
            f"All {wins} won. Not even joking",
            f"${a1} made just today. Thank you",
            f"On point as always bro",
            f"${a1} profit. Simple and clean",
            f"Boss you delivered today",
            f"Clean session from start to finish",
            f"Evalon never misses",
            f"This thing is real king",
            f"Every signal landed today",
            f"${a1} richer after this session",
            f"Accuracy {acc_pct}% today. Unreal",
            f"Never seen this kind of accuracy before",
            f"${a1} in the bag today",
            f"Evalon hits different every time",
            f"Signals on point. ${a1} profit",
            f"Every trade hit today king",
            f"Was ready and it paid off. ${a1}",
            f"No cap {acc_pct}% accuracy today",
            f"Not one loss today",
            f"Consistency is the key here king",
            f"Session was perfect today",
            f"Every entry was spot on",
            f"${a1} made. Follow the signal and profit",
            f"This accuracy is something else. ${a1}",
            f"Followed every signal. ${a1} in profit",
            f"Another solid session king",
            f"${a1} secured. Thank you",
            f"Results speak for themselves today",
            f"King you are too consistent",
            f"Profit again today. ${a1} clean",
            f"Session was fire today",
            f"This is why I renewed my VIP. ${a1}",
            f"Locked in and made ${a1} today",
            f"Discipline plus Evalon equals profit",
            f"${a1} just from following instructions",
            f"Today was effortless. ${a1}",
            f"Bro I keep making money here",
            f"Another day another profit. ${a1}",
            f"Evalon never lets me down",
            f"${a1} is a good day for me",
            f"Accuracy was top tier today",
            f"Boss session was on fire",
        ]
        _LONG = [
            f"I have been trading for 2 years and never seen accuracy like this. Made ${a2} today just following the signals. Every single one hit. King you are built different",
            f"I was skeptical at first. But {acc_str} signals won today and I made ${a2}. This is the real deal. No more guessing",
            f"I told my friend about this after making ${a2} today. He did not believe me so I showed him my account. Now he wants to join too. Accuracy was {acc_pct}%",
            f"I nearly gave up trading last month after losing elsewhere. Today I made ${a2} and I finally feel confident again. Every signal was precise. Thank you for real",
            f"The consistency is what gets me every time. Session after session {acc_pct}% accuracy. Made ${a2} today and I am not even using big amounts yet",
            f"I screenshotted my balance after today. ${a2} in profit. Evalon is changing lives for real",
            f"{acc_pct}% accuracy today. I have tried 3 other signal groups before. None of them come close to this. ${a2} profit and I am happy",
            f"This is the most consistent signal I have ever followed. Today {acc_str} won and I made ${a2}. My trading changed completely since I joined",
            f"I used to trade randomly and lose. Now I just wait for the signal and follow it. ${a2} profit today. Discipline is key",
            f"I joined last week and already made back what I lost in 3 months elsewhere. Today was {acc_pct}% accuracy and ${a2} profit. Evalon is built different",
            f"I follow every signal without hesitation now. Today {acc_str} won and I cleared ${a2}. Trust the process and it pays every time",
            f"Started with small amounts just to test. After today {acc_pct}% accuracy and ${a2} profit I am going bigger next session. King you never miss",
            f"My brother recommended Evalon and I thought it was just another group. After today making ${a2} with {acc_pct}% accuracy I am a believer. This is different",
            f"I wake up ready because I know the signals are coming. Today {acc_str} hit and I walked away with ${a2}. Best decision I made joining this group",
            f"Three months with Evalon and I have not had a bad week yet. Today alone ${a2} profit with {acc_pct}% accuracy. King keep it up",
            f"People ask me where I get my signals from. I just smile and stay quiet. ${a2} today says everything",
            f"I used to overthink every trade. Now I just wait for the signal open and close. ${a2} made today with zero stress",
            f"Evalon taught me patience pays. Waited for each signal today and made ${a2}. Every entry was clean",
            f"My account has grown every single week since joining. Today {acc_pct}% accuracy and ${a2} profit. This is sustainable trading",
            f"I show my daily profits to my family now. Today ${a2} just from following signals. They stopped doubting me",
        ]
        pool = _SHORT * 3 + _LONG
        random.shuffle(pool)
        for c in pool:
            key = c[:40]
            if key not in used_comments:
                used_comments.add(key)
                return c
        return random.choice(_LONG)

    used_nums = set()
    def get_num():
        n = random.randint(1501, 2800)
        while n in used_nums: n = random.randint(1501, 2800)
        used_nums.add(n); return n

    used_names = set()
    def make_fake(comment=None):
        return {
            "num":     get_num(),
            "name":    _make_global_name(used_names),
            "stars":   "\u2b50" * random.choice([5,5,5,4,4,4,5,4,3,5,4,5,4,5,3,4,5,5,4,5]),
            "comment": comment or win_comment()
        }

    # Real feedback - no approval needed, show all with rating >= 3
    real_all = [f for f in load_feedback() if f.get("rating", 0) >= 3 and f.get("comment", "").strip()]
    real_entries = [{
        "num":     get_num(),
        "name":    f.get("name", "User"),
        "stars":   "\u2b50" * f.get("rating", 5),
        "comment": f.get("comment", "Great signals!")
    } for f in real_all]

    total_fake       = random.randint(25, 32)
    joined_positions = sorted(random.sample(range(total_fake), 2))
    fake_entries = []
    joined_idx = 0
    for i in range(total_fake):
        if joined_idx < 2 and i == joined_positions[joined_idx]:
            fake_entries.append(make_fake(comment=JOINED_TODAY[joined_idx]))
            joined_idx += 1
        else:
            fake_entries.append(make_fake())

    # ORDER: 3 fake first, then real interleaved with remaining fakes
    first_count = 3
    first_fake  = fake_entries[:first_count]
    rest_fake   = fake_entries[first_count:]
    middle = []
    ri = 0
    num_real = len(real_entries)
    if num_real > 0 and rest_fake:
        gap = max(2, len(rest_fake) // (num_real + 1))
        fc = 0
        for fe in rest_fake:
            middle.append(fe); fc += 1
            if ri < num_real and fc % gap == 0:
                middle.append(real_entries[ri]); ri += 1
        while ri < num_real:
            middle.append(real_entries[ri]); ri += 1
    else:
        middle = rest_fake[:]
        while ri < num_real:
            middle.append(real_entries[ri]); ri += 1

    all_entries = first_fake + middle
    if not all_entries:
        await update.message.reply_text("\U0001f4ca No feedback yet."); return

    await update.message.reply_text("\U0001f4ca *Sending feedback...*", parse_mode="Markdown")
    for entry in all_entries:
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=entry["stars"]+" *#"+str(entry["num"])+"*\n\U0001f464 *"+entry["name"]+"*\n_\""+entry["comment"]+"\"_",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.warning(f"Feedback send failed: {e}")
        await asyncio.sleep(random.uniform(1.2, 2.8))

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="\u2705 *Done!*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("\U0001f5d1\ufe0f Clear All Feedback", callback_data="clear_feedback")]])
    )


# ============================================================
# /channelfeedback \u2014 feedback with checkboxes to forward selected to channel
# ============================================================
async def cmd_channelfeedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    import random

    wins    = SESSION_STATS.get("wins", 0)
    losses  = SESSION_STATS.get("losses", 0)
    total   = wins + losses
    acc_pct = int(wins/total*100) if total > 0 else 100
    acc_str = f"{wins}/{total}" if total > 0 else "all"
    amt1    = random.randint(80, 500)
    amt2    = random.randint(500, 4500)

    NAMES = [
        "James","Ali","Sarah","Mike","John","David","Kevin","Chris","Tony","Eric",
        "Omar","Ahmed","Hassan","Sam","Felix","Ivan","Bruno","Joel","Musa","Bilal",
        "Zara","Aisha","Fatima","Nina","Leila","Emma","Lisa","Anna","Grace","Nadia",
        "John K","Ali B","Sarah M","David T","Mike O","James K","Chris A","Eric B"
    ]

    _CF_SMALL  = [87,112,134,156,178,195,203,217,234,251,263,278,291,305,318,332,347,361,374,389]
    _CF_MEDIUM = [412,438,456,473,491,508,524,537,562,578,591,614,627,643,658,671,689,703,724,746]
    _CF_LARGE  = [812,847,873,916,954,978,1043,1087,1134,1178,1215,1267,1312,1389,1423,1478,1534,1612,1689,1743]
    _CF_XLARGE = [1823,1956,2134,2287,2413,2567,2734,2891,3124,3356,3578,3812,4123,4389,4612,4834,5123,5478,5812,6234,6578,6891,7124]
    _cf_used_amounts = set()

    def _cf_get_amt(pool=None):
        src = pool if pool else (_CF_SMALL + _CF_MEDIUM + _CF_LARGE + _CF_XLARGE)
        avail = [a for a in src if a not in _cf_used_amounts]
        if not avail: avail = src
        a = random.choice(avail)
        _cf_used_amounts.add(a)
        return a

    _jamt_cf = _cf_get_amt(_CF_SMALL + _CF_MEDIUM)
    JOINED_TODAY = [
        f"Joined today and already ${_jamt_cf} up. This is crazy \U0001f631",
        f"First session here and {wins} out of {total} won. Can't believe it king \U0001f631",
    ]

    used_comments = set()
    def win_comment():
        a1 = _cf_get_amt(_CF_SMALL + _CF_MEDIUM)
        a2 = _cf_get_amt(_CF_LARGE + _CF_XLARGE)
        _S = [
            f"Bro this is too good \U0001f525", f"King you never disappoint \U0001f451",
            f"Brother signals were clean today \U0001f4aa", f"All {wins} hit. Not even joking",
            f"${a1} made today. Thank you \U0001f64f", f"On point as always bro \U0001f3af",
            f"${a1} profit today. Simple \U0001f4b0", f"Boss you killed it today \U0001f44a",
            f"Clean session today king \U0001f451", f"Evalon never misses bro \U0001f3af",
            f"This Evalon thing is real king \U0001f48e", f"Every signal landed today bro \U0001f525",
            f"${a1} richer after today's session", f"Accuracy {acc_pct}% today. Wild \U0001f451",
            f"Bro {wins} out of {total}. Crazy \U0001f4aa", f"Never seen accuracy like this bro",
            f"${a1} in the bag today king \U0001f525", f"Evalon is different bro, fr \U0001f48e",
            f"Signals on point today. ${a1} profit", f"King every trade hit today \U0001f4aa",
            f"Bro I was ready and it paid off. ${a1} \U0001f525", f"No cap {acc_pct}% accuracy today \U0001f451",
            f"Not one loss today bro \U0001f3af", f"${a1} and it's not even afternoon \U0001f4b0",
            f"Bro Evalon hits different every time \U0001f525", f"Session was clean start to finish king \U0001f451",
            f"Every entry was spot on today bro \U0001f4aa", f"${a1} made. Simple follow and profit \U0001f3af",
            f"This accuracy is unreal bro. ${a1} \U0001f48e", f"Followed every signal. ${a1} in profit \U0001f64f",
            f"Man today was fire \U0001f525", f"Thanks so much bro, solid profit today",
            f"Bro today was amazing \U0001f525", f"Thank you bro, ${a1} profit landed \U0001f64f",
            f"Thanks chief, {wins} out of {total} \U0001f44c", f"Perfect today bro, ${a1} \U0001f4aa",
        ]
        _L = [
            f"Bro I have been trading for 2 years and never seen accuracy like this. Made ${a2} today just following the signals. Every single one hit. King you are built different \U0001f451",
            f"Evalon brother I was skeptical at first. But {acc_str} signals won today and I made ${a1}. This is the real deal. No more guessing \U0001f4aa",
            f"I told my friend about this after making ${a1} today. He didn't believe me so I showed him my account. Now he wants to join too \U0001f602 Accuracy was {acc_pct}% king \U0001f44a",
            f"I nearly gave up trading last month after losing money elsewhere. Today I made ${a1} and I finally feel confident again. Every signal was precise bro. Thank you for real \U0001f64f",
            f"Honestly the consistency is what gets me every time. Session after session, {acc_pct}% accuracy. Made ${a1} today and I am not even using big amounts yet \U0001f4b0",
            f"Brother I screenshotted my balance after today's session. ${a2} in profit. Evalon is changing lives king, for real \U0001f64f\U0001f525",
            f"Bro {acc_pct}% accuracy today. I have tried 3 other signal groups before. None of them come close to this. ${a1} profit and I am happy \U0001f4aa",
            f"King this is the most consistent signal I have ever followed. Today {acc_str} won and I made ${a1}. My trading changed completely since I joined \U0001f525",
            f"Man I used to trade randomly and lose. Now I just wait for the signal and follow it. ${a1} profit today. Discipline is key bro \U0001f4aa",
            f"I joined last week and already made back what I lost in 3 months elsewhere. Today was {acc_pct}% accuracy and ${a1} profit. Evalon is built different king \U0001f48e",
            f"Bro I follow every signal without hesitation now. Today {acc_str} won and I cleared ${a1}. Trust the process and it pays every time \U0001f3af",
            f"Started with small amounts just to test. After today's {acc_pct}% accuracy and ${a1} profit I am going bigger next session. King you never miss \U0001f451",
            f"Bro I used to lose a lot trading elsewhere. Today {wins} out of {wins} won. ${a1} profit. Evalon's level is honestly different \U0001f64f",
            f"Brother today was sensational. {acc_str} signals hit and ${a2} in profit. Truly grateful \U0001f451",
            f"I've been following signals for two weeks now. Every session brings profit. Today ${a1} again. Thank you \U0001f64f",
        ]
        pool = _S * 3 + _L
        random.shuffle(pool)
        for c in pool:
            if random.random() < 0.4:
                for em in ["\U0001f525","\U0001f4aa","\U0001f451","\U0001f3c6","\U0001f4b0","\U0001f3af","\U0001f631","\U0001f64f","\U0001f44a","\u2705","\U0001f48e","\u26a1","\U0001f44c"]:
                    if c.endswith(em): c = c[:-len(em)].strip(); break
            key = c[:40]
            if key not in used_comments:
                used_comments.add(key); return c
        return random.choice(_L)

    used_nums = set()
    def get_num():
        n = random.randint(1501, 2800)
        while n in used_nums: n = random.randint(1501, 2800)
        used_nums.add(n); return n

    used_names = set()
    def make_name():
        for _ in range(20):
            nm = random.choice(NAMES)
            full = f"{nm.split()[0]} {random.choice(NAMES).split()[0][0]}" if random.random() < 0.35 else nm.split()[0]
            if full not in used_names:
                used_names.add(full); return full
        return nm.split()[0]

    def make_entry(comment=None):
        return {
            "num":     get_num(),
            "name":    make_name(),
            "stars":   "\u2b50" * random.choice([5,5,5,4,4,4,5,4,3,5,4,5]),
            "comment": comment or win_comment()
        }

    # Real approved feedback (max 4)
    real_all   = [f for f in load_feedback() if f.get("rating", 0) >= 4 and f.get("approved", False)]
    real_show  = real_all[:4]
    real_entries = [{"num": get_num(), "name": f.get("name","User"),
                     "stars": "\u2b50"*f.get("rating",5), "comment": f.get("comment","Great signals!")} for f in real_show]

    total_fake       = random.randint(25, 32)
    joined_positions = sorted(random.sample(range(total_fake), 2))
    fake_entries = []
    joined_idx = 0
    for i in range(total_fake):
        if joined_idx < 2 and i == joined_positions[joined_idx]:
            fake_entries.append(make_entry(comment=JOINED_TODAY[joined_idx])); joined_idx += 1
        else:
            fake_entries.append(make_entry())

    first_count_cf = random.randint(2, 3)
    first_fake = fake_entries[:first_count_cf]; rest_fake = fake_entries[first_count_cf:]
    middle = []; ri = 0
    gap_cf = max(1, len(rest_fake) // (len(real_entries) + 1)) if real_entries else len(rest_fake)
    next_real_cf = gap_cf
    fake_cnt_cf  = 0
    for fe in rest_fake:
        if ri < len(real_entries) and fake_cnt_cf >= next_real_cf:
            middle.append(real_entries[ri]); ri += 1
            next_real_cf = fake_cnt_cf + gap_cf
        middle.append(fe)
        fake_cnt_cf += 1
    while ri < len(real_entries):
        middle.append(real_entries[ri]); ri += 1

    all_entries = first_fake + middle

    # Store entries in context for forwarding
    context.user_data["cf_entries"] = all_entries
    context.user_data["cf_selected"] = set()

    # Send header
    await update.message.reply_text(
        f"\U0001f4cb *{len(all_entries)} feedback entries ready*\n\n"
        "Tap each one to select \u2705 for forwarding to channel.\n"
        "When done, tap *Forward Selected* \U0001f447",
        parse_mode="Markdown"
    )

    # Send each entry with a toggle button
    for i, entry in enumerate(all_entries):
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"{entry['stars']} *#{entry['num']}*\n\U0001f464 *{entry['name']}*\n\U0001f4ac _{entry['comment']}_",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("\u2610 Select", callback_data=f"cf_toggle_{i}")
                ]])
            )
        except Exception as e:
            logger.warning(f"cf entry send failed: {e}")
        await asyncio.sleep(random.uniform(0.8, 1.5))

    # Forward button at the end
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="\u2705 *Select entries above, then forward:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("\U0001f4e2 Forward Selected to Channel", callback_data="cf_forward")
        ]])
    )

# ============================================================
# /reviewfeedback \u2014 admin reviews pending feedback queue
# ============================================================
async def cmd_reviewfeedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    fb_list  = load_feedback()
    pending  = [f for f in fb_list if f.get("pending", False)]
    approved = [f for f in fb_list if f.get("approved") and not f.get("forwarded")]

    if not pending and not approved:
        await update.message.reply_text(
            "\U0001f4ed *No pending or approved feedback.*\n\nWaiting for members to submit after sessions.",
            parse_mode="Markdown"
        ); return

    # Show pending items one by one with approve/reject buttons
    if pending:
        await update.message.reply_text(
            f"\U0001f4cb *{len(pending)} pending feedback(s) to review:*\n\nTap \u2705 to approve or \u274c to reject each one.",
            parse_mode="Markdown"
        )
        for entry in pending:
            stars_str = "\u2b50" * entry.get("rating", 5)
            comment   = entry.get("comment", "No comment")
            fb_name   = entry.get("name", "Trader")
            fb_id     = entry.get("id", "")
            fb_date   = entry.get("date", "")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=(
                    f"\U0001f464 *{fb_name}*\n"
                    f"{stars_str}\n"
                    f"\U0001f4ac _{comment}_\n"
                    f"\U0001f4c5 {fb_date}"
                ),
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("\u2705 Approve", callback_data=f"fb_approve_{fb_id}"),
                    InlineKeyboardButton("\u274c Reject",  callback_data=f"fb_reject_{fb_id}"),
                ]])
            )
            await asyncio.sleep(0.5)

    # Show "Forward All Approved" button if there are approved ones not yet forwarded
    if approved:
        await update.message.reply_text(
            f"\u2705 *{len(approved)} approved feedback(s) ready to forward to channel.*\n\n"
            f"Tap the button below when you are ready to send them all.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(f"\U0001f4e2 Forward All ({len(approved)}) to Channel", callback_data="fb_forward_all")
            ]])
        )

# ============================================================
# /realfeedback - show real feedback only + clear button
# ============================================================
async def cmd_realfeedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    fb_list = load_feedback()
    if not fb_list:
        await update.message.reply_text(
            "\U0001f4ca *No real feedback yet.*\n\nFeedback appears here after VIP members rate sessions.",
            parse_mode="Markdown"
        ); return

    ratings = [f["rating"] for f in fb_list if "rating" in f]
    avg     = sum(ratings)/len(ratings) if ratings else 0
    await update.message.reply_text(
        f"\U0001f4ca *REAL FEEDBACK \u2014 {len(fb_list)} total*\n\u2b50 Average: *{avg:.1f}/5*",
        parse_mode="Markdown"
    )

    for fb in fb_list:
        stars   = "\u2b50" * fb.get("rating", 0)
        comment = fb.get("comment","No comment")
        name    = fb.get("name","?")
        date    = fb.get("date","")
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=stars + "\n\U0001f464 *" + name + "*\n\U0001f4ac _" + comment + "_\n\U0001f4c5 " + date,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.warning(f"realfeedback send failed: {e}")
        await asyncio.sleep(0.3)

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"\u2705 *{len(fb_list)} feedback(s) shown above.*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("\U0001f5d1\ufe0f Clear ALL Real Feedback", callback_data="clear_real_feedback")
        ]])
    )

# Alias
async def cmd_realfeedbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_realfeedback(update, context)

# ============================================================
# /help helper
# ============================================================
async def _send_help(chat_id, context):
    await context.bot.send_message(chat_id=chat_id, parse_mode="Markdown", text=(
        "\U0001f4d6 *EVALON VIP SIGNALS \u2014 ADMIN GUIDE*\n\n"
        "--------------\n\U0001f4e1 *SIGNALS*\n--------------\n"
        "`EURUSD 5` \u2014 Send signal for 1 trade\n"
        "  \u2514 Bot will ask for trade count after direction\n"
        "`EURUSD 5 10` \u2014 Send signal for 10 trades auto\n"
        "  \u2514 Result sent automatically after BUY/SELL\n"
        "`buy sell` (two words) \u2014 Send *CANDLE CLOSE PLAN* for the signal waiting on direction\n"
        "  \u2514 e.g. candle closes BUY \u2192 open 1st word; closes SELL \u2192 open 2nd word\n"
        "`/publicsignal on` / `off` \u2014 Send future signals to VIP+Non-VIP or VIP only\n\n"
        "\U0001f4cd After signal: tap *BUY / SELL / Cancel*\n"
        "\u2705 After direction: tap *WIN / LOSS* (kila moja = 10%)\n\n"
        "--------------\n\U0001f4c5 *SESSION*\n--------------\n"
        "`/session` \u2014 Send 5min or 30min session alert to VIP\n"
        "  \u2514 Tap *Send Start Now* to begin session\n"
        "  \u2514 Tap *Emergency/Delay* to send urgent message\n"
        "`/end` \u2014 End session and send results to VIP\n\n"
        "Buttons after `/end`:\n"
        "\u25b6\ufe0f *Replay Session* \u2014 Preview all signals (you only)\n"
        "\U0001f4e2 *Send Replay to Non-VIP* \u2014 Attract non-VIP members\n"
        "\U0001f4e2 *Send Results to Non-VIP* \u2014 Results summary only\n"
        "\U0001f4e2 *Forward Stats to Channel* \u2014 Post to channel\n\n"
        "--------------\n\U0001f4e2 *BROADCAST*\n--------------\n"
        "Send photo \u2192 VIP only (watermarked)\n"
        "Send video \u2192 VIP + Non-VIP + Channel (no watermark)\n"
        "Send sticker \u2192 VIP only\n"
        "`/broadcast [text]` \u2192 Text to VIP\n"
        "`/broadcast all [text]` \u2192 Text to everyone\n"
        "Reply to media + `/broadcast` \u2192 Media to VIP\n"
        "Reply to media + `/broadcast all` \u2192 Media to everyone\n"
    ))
    await context.bot.send_message(chat_id=chat_id, parse_mode="Markdown", text=(
        "--------------\n\U0001f511 *VIP CODES*\n--------------\n"
        "`/addcode 1w Name` \u2014 1 Week code (Free Trial)\n"
        "`/addcode 1m Name` \u2014 1 Month code\n"
        "`/addcode 3m Name` \u2014 3 Months code\n"
        "`/addcode 6m Name` \u2014 6 Months code\n"
        "`/addcode 1y Name` \u2014 1 Year code\n"
        "`/addcode 10d Name` \u2014 Custom: any number of days\n"
        "`/addcodes 10 1m` \u2014 Generate 10 codes (1 Month)\n"
        "`/listcodes` \u2014 View all codes (used/unused)\n"
        "`/vipusers` \u2014 View all VIP members + expiry dates\n"
        "`/trialusers` \u2014 View all users who used Free Trial (ID + name)\n"
        "`/allusers` \u2014 View all users (ID + name + VIP status)\n"
        "`/blockedusers` \u2014 View users who blocked the bot\n"
        "`/referrals` \u2014 Top inviters leaderboard\n"
        "`/referrals <user_id>` \u2014 See who a specific user invited\n"
        "`/revoke 123456789` \u2014 Remove VIP access from member\n\n"
        "--------------\n\U0001f4ca *STATS & FEEDBACK*\n--------------\n"
        "`/stats` \u2014 Full stats: wins, losses, members, weekly\n"
        "`/dbstatus` \u2014 Check database health (PostgreSQL)\n"
        "`/feedback` — Fake + real feedback mixed (no approval needed)\n"
        "`/realfeedback` — View real feedback only + Clear button\n\n"
        "\U0001f4a1 _Real feedback saved automatically after each session rating._\n\n"
        "--------------\n\U0001f4e2 *CUSTOM BROADCAST*\n--------------\n"
        "After `/end`, tap *Custom Broadcast to VIP* or *All*\n"
        "Type message → sent exactly as written. `/cancel` to stop\n\n"
        "--------------\n\U0001f5bc *MEDIA & FILE IDs*\n--------------\n"
        "`/getid` \u2014 Send sticker/photo \u2192 get its file\\_id\n"
        "`/setwelcome` \u2014 Send photo \u2192 set as welcome image\n\n"
        "--------------\n\u2699\ufe0f *GENERAL*\n--------------\n"
        "`/start` or tap *SESSION* button — Show welcome / status\n"
        "`/help` \u2014 Show this admin guide (admin only)\n"
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
    await update.message.reply_text("\U0001f5bc\ufe0f *Send the welcome image now.*", parse_mode="Markdown")

async def cmd_dbstatus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if DATABASE_URL:
        try:
            _sb_get("main_db"); db = load_db()
            vips = sum(1 for u in db["users"].values() if u.get("vip"))
            await update.message.reply_text(
                f"\u2705 *PostgreSQL Connected!*\n\n"
                f"\U0001f465 Users: *{len(db['users'])}* | \U0001f48e VIP: *{vips}* | \U0001f511 Codes: *{len(db.get('codes',{}))}*\n\n"
                "Data is safely stored \U0001f6e1\ufe0f", parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text(f"\u274c *PostgreSQL Error!*\n\n`{e}`", parse_mode="Markdown")
    else:
        await update.message.reply_text("\u26a0\ufe0f *PostgreSQL not connected!*\n\nSet `DATABASE_URL` on Render.", parse_mode="Markdown")

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    db    = load_db(); users = db.get("users", {}); codes = db.get("codes", {})
    vip   = sum(1 for u in users.values() if u.get("vip"))
    ws    = load_weekly_stats()
    ww    = ws.get("wins", 0)
    wl    = ws.get("losses", 0)
    wtot  = ww + wl
    wacc  = f"{(ww/wtot*100):.1f}%" if wtot > 0 else "N/A"
    wsess = ws.get("sessions", 0)
    week  = ws.get("week", "?")

    # Current session
    swp   = SESSION_STATS["win_pct"]
    slp   = SESSION_STATS["loss_pct"]

    storage_str = "\u2705 PostgreSQL" if DATABASE_URL else "\u26a0\ufe0f Local JSON"
    lines = [
        "\U0001f4ca *EVALON VIP SIGNALS \u2014 STATS*\n",
        f"\n\U0001f4be Storage: *{storage_str}*\n",
        "\n--------------",
        f"\n\U0001f4e3 Display count : *{get_base_members() + vip}*",
        f"\n\U0001f48e VIP members   : *{vip}*",
        f"\n\U0001f513 Non-VIP       : *{len(users) - vip}*\n",
        "--------------",
        f"\n\U0001f7e2 Active codes : *{sum(1 for c in codes.values() if c.get('used'))}*",
        f"\n\u26aa Unused codes : *{sum(1 for c in codes.values() if not c.get('used'))}*",
        f"\n\U0001f4cb Total codes  : *{len(codes)}*\n",
        "--------------",
        f"\n\U0001f4c5 *WEEKLY STATS* ({week})",
        f"\n\u2705 Wins     : *{ww}*",
        f"\n\u274c Losses   : *{wl}*",
        f"\n\U0001f4c8 Accuracy : *{wacc}*",
        f"\n\U0001f3c1 Sessions : *{wsess}*\n",
        "--------------",
        f"\n\u26a1 *CURRENT SESSION*",
        f"\n\u2705 Win      : *{swp}%*",
        f"\n\u274c Loss     : *{slp}%*",
    ]
    await update.message.reply_text("".join(lines), parse_mode="Markdown")

async def cmd_addcode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    # Usage: /addcode [duration] [label]
    # duration: 1w | 1m | 3m | 6m | 1y | Xd (e.g. 10d, 3d, 45d)
    args = context.args or []
    dur         = "1m"
    label       = "VIP User"
    custom_days = None

    if args:
        first = args[0].lower()
        # Check custom days format e.g. 10d, 3d
        if first.endswith("d") and first[:-1].isdigit():
            custom_days = int(first[:-1])
            custom_days = max(1, min(custom_days, 3650))  # 1 day to 10 years cap
            label = " ".join(args[1:]) if len(args) > 1 else "VIP User"
        elif first in VIP_DURATIONS:
            dur   = first
            label = " ".join(args[1:]) if len(args) > 1 else "VIP User"
        else:
            label = " ".join(args)

    code, days = new_code(label, dur, custom_days=custom_days)

    if custom_days:
        dur_display = f"{custom_days} Days"
    else:
        dur_display = {"1w": "1 Week (Free Trial)", "1m": "1 Month", "3m": "3 Months", "6m": "6 Months", "1y": "1 Year"}[dur]

    await update.message.reply_text(
        f"\u2705 *VIP Code Created!*\n\n"
        f"\U0001f464 *{label}*\n"
        f"\U0001f511 `{code}`\n"
        f"\u23f3 Duration: *{dur_display}* ({days} days)\n\n"
        f"\U0001f4cc Usage: `/addcode 10d Name` `/addcode 3d Name` `/addcode 1m Name`",
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
    codes_list = "\n".join(f"`{c}` \u2014 {dur_labels[dur]}" for c, _ in pairs)
    await update.message.reply_text(
        f"\u2705 *{count} VIP Codes Created!*\n"
        f"\u23f3 Duration: *{dur_labels[dur]}*\n\n{codes_list}",
        parse_mode="Markdown"
    )

async def cmd_listcodes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    db = load_db(); codes = db.get("codes",{})
    if not codes: await update.message.reply_text("\U0001f4cb No codes yet."); return
    unused = [(c,v) for c,v in codes.items() if not v.get("used")]
    used   = [(c,v) for c,v in codes.items() if v.get("used")]
    lines  = [f"\U0001f4cb *VIP CODES ({len(codes)} total)*\n\u26aa Unused: {len(unused)}  \U0001f7e2 Used: {len(used)}\n"]
    if unused: lines.append("*\u2014 UNUSED \u2014*"); [lines.append(f"`{c}` \u2014 {v.get('label','?')}") for c,v in unused[:20]]
    if used:   lines.append("\n*\u2014 USED \u2014*");  [lines.append(f"`{c}` \u2014 {v.get('used_name','?')} ({v.get('used_date','?')})") for c,v in used[:20]]
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def cmd_publicsignal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global PUBLIC_SIGNAL_MODE
    if not is_admin(update.effective_user.id): return
    args = context.args or []
    if not args:
        status = "\u2705 *ON* \u2014 VIP + Non-VIP" if PUBLIC_SIGNAL_MODE else "\U0001f512 *OFF* \u2014 VIP only"
        await update.message.reply_text(
            f"\U0001f4e1 *Public Signal Mode:* {status}\n\nUse `/publicsignal on` or `/publicsignal off`",
            parse_mode="Markdown")
        return
    mode = args[0].lower()
    if mode == "on":
        PUBLIC_SIGNAL_MODE = True
        await update.message.reply_text("\u2705 *Public Signal Mode: ON*\nFuture signals will be sent to VIP + Non-VIP.", parse_mode="Markdown")
    elif mode == "off":
        PUBLIC_SIGNAL_MODE = False
        await update.message.reply_text("\U0001f512 *Public Signal Mode: OFF*\nSignals will go to VIP only again.", parse_mode="Markdown")
    else:
        await update.message.reply_text("Use `/publicsignal on` or `/publicsignal off`", parse_mode="Markdown")

async def cmd_vipusers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    vids = get_vip_ids()
    if not vids: await update.message.reply_text("\U0001f465 No VIP members yet."); return
    db = load_db(); lines = [f"\U0001f465 *VIP MEMBERS ({get_display_count()} total):*\n"]
    for vid in vids:
        info = db["users"].get(str(vid), {})
        lines.append(f"\U0001f464 *{info.get('name','?')}*  |  \U0001f511 `{info.get('vip_code','?')}`  |  \U0001f4c5 {info.get('joined_date','?')}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def cmd_trialusers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    db = load_db()
    trial_users = db.get("trial_users", {})
    if not trial_users:
        await update.message.reply_text("\U0001f194 *No Free Trial users yet.*", parse_mode="Markdown")
        return
    lines = [f"\U0001f194 *FREE TRIAL USERS \u2014 {len(trial_users)} total*\n"]
    for uid_str, info in trial_users.items():
        name = info.get("name", "?")
        date = info.get("date", "?")
        code = info.get("code", "?")
        lines.append(
            f"\U0001f464 *{name}*\n"
            f"   \U0001f194 ID: `{uid_str}`\n"
            f"   \U0001f511 `{code}`\n"
            f"   \U0001f4c5 {date}\n"
        )
    # Split if too long
    text = "\n".join(lines)
    if len(text) > 4000:
        chunks = []
        chunk = lines[0] + "\n"
        for line in lines[1:]:
            if len(chunk) + len(line) > 4000:
                chunks.append(chunk)
                chunk = line + "\n"
            else:
                chunk += line + "\n"
        chunks.append(chunk)
        for chunk in chunks:
            await update.message.reply_text(chunk, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, parse_mode="Markdown")

async def cmd_allusers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    db = load_db()
    users = db.get("users", {})
    if not users:
        await update.message.reply_text("\U0001f465 *No users yet.*", parse_mode="Markdown")
        return
    lines = [f"\U0001f465 *ALL USERS \u2014 {len(users)} total*\n"]
    referrals = db.get("referrals", {})
    for uid_str, info in users.items():
        name = info.get("name", "?")
        vip_tag = "\U0001f48e VIP" if info.get("vip") else "\U0001f194 Non-VIP"
        joined = info.get("joined_date", info.get("date", "?"))
        invited_n = len(referrals.get(uid_str, []))
        lines.append(
            f"\U0001f464 *{name}*\n"
            f"   \U0001f194 ID: `{uid_str}`\n"
            f"   {vip_tag}\n"
            f"   \U0001f4c5 {joined}\n"
            f"   \U0001f465 Invited: *{invited_n}*\n"
        )
    text = "\n".join(lines)
    if len(text) > 4000:
        chunks = []
        chunk = lines[0] + "\n"
        for line in lines[1:]:
            if len(chunk) + len(line) > 4000:
                chunks.append(chunk)
                chunk = line + "\n"
            else:
                chunk += line + "\n"
        chunks.append(chunk)
        for chunk in chunks:
            await update.message.reply_text(chunk, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, parse_mode="Markdown")

async def cmd_referrals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    db = load_db()
    referrals = db.get("referrals", {})
    users = db.get("users", {})
    args = context.args or []

    if args:
        # /referrals <user_id> -> full list of who that user invited
        target = args[0]
        info = users.get(target, {})
        refs = referrals.get(target, [])
        name = info.get("name", "?")
        lines = [f"\U0001f465 *{name}* (`{target}`) invited *{len(refs)}* people:\n"]
        for r in refs:
            lines.append(f"\U0001f464 {r.get('name','?')}  |  ID `{r.get('uid','?')}`  |  \U0001f4c5 {r.get('date','?')}\n")
        if not refs:
            lines.append("\n_No invites yet._")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        return

    # No args -> leaderboard of top inviters
    if not referrals:
        await update.message.reply_text("\U0001f465 *No referrals recorded yet.*", parse_mode="Markdown")
        return
    ranked = sorted(referrals.items(), key=lambda kv: len(kv[1]), reverse=True)
    lines = ["\U0001f3c6 *TOP INVITERS*\n"]
    for uid_str, refs in ranked[:20]:
        name = users.get(uid_str, {}).get("name", "?")
        lines.append(f"\U0001f464 *{name}* (`{uid_str}`) \u2014 *{len(refs)}* invited\n")
    lines.append("\n_Use `/referrals <user_id>` to see who a specific user invited._")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def cmd_blockedusers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    db = load_db()
    users = db.get("users", {})
    blocked = {k: v for k, v in users.items() if v.get("blocked")}
    if not blocked:
        await update.message.reply_text("\u2705 *No one has blocked the bot.*", parse_mode="Markdown")
        return
    lines = [f"\U0001f6ab *USERS WHO BLOCKED THE BOT \u2014 {len(blocked)} total*\n"]
    for uid_str, info in blocked.items():
        name = info.get("name", "?")
        vip_tag = "\U0001f48e VIP" if info.get("vip") else "\U0001f194 Non-VIP"
        bdate = info.get("blocked_date", "?")
        lines.append(
            f"\U0001f464 *{name}*\n"
            f"   \U0001f194 ID: `{uid_str}`\n"
            f"   {vip_tag}\n"
            f"   \U0001f6ab Blocked: {bdate}\n"
        )
    text = "\n".join(lines)
    if len(text) > 4000:
        chunks = []
        chunk = lines[0] + "\n"
        for line in lines[1:]:
            if len(chunk) + len(line) > 4000:
                chunks.append(chunk)
                chunk = line + "\n"
            else:
                chunk += line + "\n"
        chunks.append(chunk)
        for chunk in chunks:
            await update.message.reply_text(chunk, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, parse_mode="Markdown")

async def cmd_revoke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if not context.args: await update.message.reply_text("Usage: `/revoke USER_ID`", parse_mode="Markdown"); return
    try: target = int(context.args[0])
    except: await update.message.reply_text("\u274c Invalid user ID."); return
    db = load_db(); key = str(target)
    if key not in db["users"]: await update.message.reply_text("\u274c User not found."); return
    name = db["users"][key].get("name","Unknown"); code = db["users"][key].get("vip_code")
    db["users"][key].update({"vip": False, "vip_code": None})
    # Delete code permanently \u2014 cannot be reused by anyone
    if code and code in db["codes"]:
        del db["codes"][code]
    save_db(db)
    await update.message.reply_text(f"\u26d4 *VIP Revoked!*\n\n\U0001f464 *{name}*\n\U0001f511 Code `{code}` has been permanently deleted.", parse_mode="Markdown")

async def protect_forward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Block all forwarded messages from non-admins."""
    if is_admin(update.effective_user.id): return
    try: await update.message.delete()
    except: pass
    await update.message.reply_text(
        "\U0001f512 *Forwarding is not allowed in this bot.*\n\nAll content is protected.",
        parse_mode="Markdown"
    )


# ============================================================
# VIP EXPIRY CHECKER
# ============================================================
def start_expiry_checker():
    """Background thread \u2014 checks VIP expiry once per day at 08:00 UTC."""
    import asyncio as _asyncio

    def _loop():
        while True:
            now = datetime.now(timezone.utc)
            # Sleep until next 08:00 UTC
            target = now.replace(hour=8, minute=0, second=0, microsecond=0)
            if now >= target:
                target = target.replace(day=target.day + 1)
            sleep_secs = (target - now).total_seconds()
            time.sleep(sleep_secs)
            # Run expiry check
            try:
                loop = _asyncio.new_event_loop()
                loop.run_until_complete(_run_expiry_check())
                loop.close()
            except Exception as e:
                logger.warning(f"Expiry checker error: {e}")

    t = threading.Thread(target=_loop, daemon=True)
    t.start()
    logger.info("VIP expiry checker started \u2705")

async def _run_expiry_check():
    """Called by background thread \u2014 needs bot instance."""
    from telegram import Bot
    bot = Bot(token=BOT_TOKEN)
    async with bot:
        await _do_expiry_check(bot)

async def _do_expiry_check(bot):
    db    = load_db()
    today = datetime.now().date()
    for uid_str, udata in list(db["users"].items()):
        if not udata.get("vip"): continue
        expiry_str = udata.get("vip_expiry")
        if not expiry_str: continue
        try:
            expiry = datetime.strptime(expiry_str, "%Y-%m-%d").date()
        except: continue
        days_left = (expiry - today).days
        name = udata.get("name", "Trader")
        uid  = int(uid_str)

        if days_left <= 0:
            db["users"][uid_str]["vip"] = False
            code = udata.get("vip_code")
            if code and code in db.get("codes", {}):
                del db["codes"][code]
            db["users"][uid_str]["vip_code"] = None
            save_db(db)
            try:
                await bot.send_message(
                    chat_id=uid,
                    text=(
                        f"\u26a0\ufe0f *Dear {name},*\n\n"
                        f"Your *VIP access has expired* today ({expiry_str}).\n"
                        f"You no longer have access to signals.\n\n"
                        f"\U0001f48e Contact admin to renew your VIP access.\n\n"
                        f"{KAULI_MBIU}"
                    ),
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("\U0001f4ac Contact Admin", url=SUPPORT_URL)
                    ]])
                )
            except: pass

        elif days_left == 3:
            # Check if this is a Free Trial (Wiki 1 / 1w) license
            code = udata.get("vip_code")
            db_codes = db.get("codes", {})
            is_free_trial = (
                code and code in db_codes and
                db_codes[code].get("duration_key") == "1w"
            )
            try:
                if is_free_trial:
                    await bot.send_message(
                        chat_id=uid,
                        text=(
                            f"\u23f0 *Dear {name},*\n\n"
                            f"Your *Free Trial* will end in *3 days* ({expiry_str}).\n\n"
                            f"To continue receiving VIP signals, you have two options:\n\n"
                            f"\u2705 Subscribe to *Evalon Trader VIP* and continue enjoying all premium signals, updates, and VIP benefits without interruption.\n\n"
                            f"\u2705 Or continue using *Free Trial* rewards by inviting your friends.\n\n"
                            f"\U0001f4cc Invite at least *5 people* to qualify for additional Free Trial days.\n\n"
                            f"The more people you invite, the more free access and VIP signals you can continue to enjoy.\n\n"
                            f"If you do not wish to invite others, you can subscribe to VIP and continue receiving signals without any limitations.\n\n"
                            f"\U0001f451 *ALWAYS EVALON TRADER IS THE KING OF FINANCE* \U0001f451"
                        ),
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("\U0001f4ac Contact Admin", url=SUPPORT_URL)
                        ]])
                    )
                else:
                    await bot.send_message(
                        chat_id=uid,
                        text=(
                            f"\u23f0 *Dear {name},*\n\n"
                            f"Your VIP access *expires in 3 days* \u2014 on *{expiry_str}*.\n\n"
                            f"Contact admin now to renew and keep receiving signals without interruption.\n\n"
                            f"{KAULI_MBIU}"
                        ),
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("\U0001f4ac Contact Admin", url=SUPPORT_URL)
                        ]])
                    )
            except: pass

        elif days_left == 1:
            try:
                await bot.send_message(
                    chat_id=uid,
                    text=(
                        f"\U0001f6a8 *Last Warning, {name}!*\n\n"
                        f"Your VIP access *expires TOMORROW* \u2014 *{expiry_str}*.\n\n"
                        f"Renew *today* to avoid losing access to signals!\n\n"
                        f"{KAULI_MBIU}"
                    ),
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("\U0001f4ac Contact Admin", url=SUPPORT_URL)
                    ]])
                )
            except: pass

async def check_vip_expiry(context):
    """Runs daily \u2014 warns users 3 days before expiry, revokes on expiry."""
    db    = load_db()
    today = datetime.now().date()
    bot   = context.bot

    for uid_str, udata in list(db["users"].items()):
        if not udata.get("vip"): continue
        expiry_str = udata.get("vip_expiry")
        if not expiry_str: continue
        try:
            expiry = datetime.strptime(expiry_str, "%Y-%m-%d").date()
        except: continue

        days_left = (expiry - today).days
        name = udata.get("name", "Trader")
        uid  = int(uid_str)

        if days_left <= 0:
            db["users"][uid_str]["vip"] = False
            code = udata.get("vip_code")
            if code and code in db.get("codes", {}):
                del db["codes"][code]
            db["users"][uid_str]["vip_code"] = None
            save_db(db)
            try:
                await bot.send_message(
                    chat_id=uid,
                    text=(
                        f"\u26a0\ufe0f *Dear {name},*\n\n"
                        f"Your *VIP access has expired* today ({expiry_str}).\n"
                        f"You no longer have access to signals.\n\n"
                        f"\U0001f48e Contact admin to renew your VIP access.\n\n"
                        f"{KAULI_MBIU}"
                    ),
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("\U0001f4ac Contact Admin", url=SUPPORT_URL)
                    ]])
                )
            except: pass

        elif days_left == 3:
            # Check if this is a Free Trial (Wiki 1 / 1w) license
            code = udata.get("vip_code")
            db_codes = db.get("codes", {})
            is_free_trial = (
                code and code in db_codes and
                db_codes[code].get("duration_key") == "1w"
            )
            try:
                if is_free_trial:
                    await bot.send_message(
                        chat_id=uid,
                        text=(
                            f"\u23f0 *Dear {name},*\n\n"
                            f"Your *Free Trial* will end in *3 days* ({expiry_str}).\n\n"
                            f"To continue receiving VIP signals, you have two options:\n\n"
                            f"\u2705 Subscribe to *Evalon Trader VIP* and continue enjoying all premium signals, updates, and VIP benefits without interruption.\n\n"
                            f"\u2705 Or continue using *Free Trial* rewards by inviting your friends.\n\n"
                            f"\U0001f4cc Invite at least *5 people* to qualify for additional Free Trial days.\n\n"
                            f"The more people you invite, the more free access and VIP signals you can continue to enjoy.\n\n"
                            f"If you do not wish to invite others, you can subscribe to VIP and continue receiving signals without any limitations.\n\n"
                            f"\U0001f451 *ALWAYS EVALON TRADER IS THE KING OF FINANCE* \U0001f451"
                        ),
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("\U0001f4ac Contact Admin", url=SUPPORT_URL)
                        ]])
                    )
                else:
                    await bot.send_message(
                        chat_id=uid,
                        text=(
                            f"\u23f0 *Dear {name},*\n\n"
                            f"Your VIP access *expires in 3 days* \u2014 on *{expiry_str}*.\n\n"
                            f"Contact admin now to renew and keep receiving signals without interruption.\n\n"
                            f"{KAULI_MBIU}"
                        ),
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("\U0001f4ac Contact Admin", url=SUPPORT_URL)
                        ]])
                    )
            except: pass

        elif days_left == 1:
            try:
                await bot.send_message(
                    chat_id=uid,
                    text=(
                        f"\U0001f6a8 *Last Warning, {name}!*\n\n"
                        f"Your VIP access *expires TOMORROW* \u2014 *{expiry_str}*.\n\n"
                        f"Renew *today* to avoid losing access to signals!\n\n"
                        f"{KAULI_MBIU}"
                    ),
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("\U0001f4ac Contact Admin", url=SUPPORT_URL)
                    ]])
                )
            except: pass


# ============================================================
# ACCOUNT MANAGEMENT AUTO-MESSAGE - sent 5 min after session end
# ============================================================
async def send_account_management_msg(context):
    """Called automatically 5 minutes after session ends. Sends to VIP only."""
    vip_ids = get_vip_ids()
    if not vip_ids: return
    msg = (
        "\U0001f48e *EXCLUSIVE VIP OFFER*\n\n"
        "As a valued Evalon VIP member, you have access to a special reward.\n\n"
        "\U0001f91d *Invite your friends and get FREE Account Management!*\n\n"
        "We will personally manage your Pocket Option account and grow your income faster \u2014 "
        "at no extra cost to you.\n\n"
        "\u2705 *How it works:*\n"
        "\u2022 Invite friends to join Evalon VIP\n"
        "\u2022 Once they join, you qualify for FREE Account Management\n"
        "\u2022 We trade your account professionally and grow it for you\n\n"
        "\U0001f525 The more you invite, the more you earn.\n\n"
        f"{KAULI_MBIU}"
    )
    for uid in vip_ids:
        try:
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("\U0001f91d Invite Friends", url=get_referral_link(uid))
            ]])
            await context.bot.send_message(
                chat_id=uid, text=msg,
                parse_mode="Markdown", reply_markup=kb,
                protect_content=True
            )
        except Exception as e:
            logger.warning(f"account_mgmt send failed {uid}: {e}")
        await asyncio.sleep(0.1)


# ============================================================
# WEEKLY STATS JOB - runs every Monday
# ============================================================
async def send_weekly_stats_job(context):
    ws     = load_weekly_stats()
    wins   = ws.get("wins", 0)
    losses = ws.get("losses", 0)
    total  = wins + losses
    acc    = f"{wins/total*100:.1f}%" if total > 0 else "N/A"
    vip_ids = get_vip_ids()
    if not vip_ids: return
    msg = (
        "\U0001f4ca *EVALON WEEKLY SUMMARY*\n\n"
        f"\u2705 Wins   : *{wins}*\n"
        f"\u274c Losses : *{losses}*\n"
        f"\U0001f4c8 Accuracy: *{acc}*\n\n"
        "Keep following every signal for maximum results.\n\n"
        f"{KAULI_MBIU}"
    )
    await send_to_list(context, vip_ids, text=msg, parse_mode="Markdown")
    # Reset weekly stats
    save_weekly_stats({"wins": 0, "losses": 0, "sessions": 0})

# ============================================================
# MONTHLY STATS JOB - runs 1st of each month
# ============================================================
async def send_monthly_stats_job(context):
    import calendar
    from datetime import datetime as _dt
    if _dt.now().day != 1: return  # only run on 1st of month
    month_name = calendar.month_name[_dt.now().month - 1 or 12]
    ws     = load_weekly_stats()
    wins   = ws.get("wins", 0)
    losses = ws.get("losses", 0)
    total  = wins + losses
    acc    = f"{wins/total*100:.1f}%" if total > 0 else "N/A"
    vip_ids = get_vip_ids()
    if not vip_ids: return
    msg = (
        f"\U0001f3c6 *EVALON MONTHLY REPORT \u2014 {month_name.upper()}*\n\n"
        f"\u2705 Total Wins    : *{wins}*\n"
        f"\u274c Total Losses  : *{losses}*\n"
        f"\U0001f4c8 Accuracy      : *{acc}*\n\n"
        "Thank you for trading with Evalon this month.\n"
        "Stay consistent and the profits follow.\n\n"
        f"{KAULI_MBIU}"
    )
    await send_to_list(context, vip_ids, text=msg, parse_mode="Markdown")

# ============================================================
async def cmd_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    import random, time as _t
    random.seed(_t.time())

    _LB_NAMES = [
        "James K","Omar A","Priya S","Carlos M","Khalid B","Sarah T","Chidi N",
        "Rahul V","Felix O","Ayesha R","Miguel C","Kofi A","Imran H","Diana L",
        "Arjun P","Fatima Z","Bruno E","Simba T","Sanjay D","Elena R",
    ]
    _used = set()
    def lb_name():
        for _ in range(30):
            n = random.choice(_LB_NAMES)
            if n not in _used:
                _used.add(n); return n
        return random.choice(_LB_NAMES)

    PROFIT_POOL = [
        4567,5123,5678,6234,6789,7123,7567,8012,8456,8912,
        9234,9678,10123,10567,11034,11456,11890,12345,12789,13234
    ]
    random.shuffle(PROFIT_POOL)
    profits = sorted(PROFIT_POOL[:10], reverse=True)

    medals = ["\U0001f947","\U0001f948","\U0001f949","4\ufe0f\u20e3","5\ufe0f\u20e3",
              "6\ufe0f\u20e3","7\ufe0f\u20e3","8\ufe0f\u20e3","9\ufe0f\u20e3","\U0001f51f"]

    lines = ["\U0001f3c6 *TOP 10 TRADERS THIS WEEK*\n\n"]
    for i, profit in enumerate(profits):
        lines.append(f"{medals[i]} *{lb_name()}* \u2014 *${profit:,}*\n")

    lines.append("\n\U0001f4b0 _Keep following every signal to stay on top!_\n")
    lines.append(f"\n{KAULI_MBIU}")

    msg = "".join(lines)
    # Store for approval
    context.bot_data["pending_leaderboard"] = msg
    # Show preview to admin
    await update.message.reply_text(
        "\U0001f440 *LEADERBOARD PREVIEW*\n\nReview below then approve or cancel:",
        parse_mode="Markdown"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")
    await update.message.reply_text(
        "Send to all VIP members?",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("\u2705 Approve & Send", callback_data="lb_approve"),
            InlineKeyboardButton("\u274c Cancel",         callback_data="lb_cancel"),
        ]])
    )

# ============================================================
# MAIN
# ============================================================
def main():
    _pg_init()
    start_keep_alive()
    start_self_ping()
    start_expiry_checker()
    print("="*55)
    print("  EVALON VIP SIGNALS BOT v9")
    print("="*55)
    storage_label = "PostgreSQL \u2705" if DATABASE_URL else "Local JSON \u26a0\ufe0f"
    print(f"Storage  : {storage_label}")
    db = load_db()
    print(f"VIP      : {sum(1 for u in db['users'].values() if u.get('vip'))}")
    print(f"Codes    : {len(db.get('codes', {}))}")
    print(f"Admin ID : {ADMIN_ID}")
    print("="*55)

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",        start))
    app.add_handler(CommandHandler("help",         cmd_help))
    app.add_handler(CommandHandler("stats",        cmd_stats))
    app.add_handler(CommandHandler("broadcast",    broadcast))
    app.add_handler(CommandHandler("session",      session_cmd))
    app.add_handler(CommandHandler("end",          end_cmd))
    app.add_handler(CommandHandler("feedback",        feedback_cmd))
    app.add_handler(CommandHandler("myinvites",       cmd_myinvites))
    app.add_handler(CommandHandler("channelfeedback", cmd_channelfeedback))
    app.add_handler(CommandHandler("realfeedback",    cmd_realfeedback))
    app.add_handler(CommandHandler("realfeedbacks",   cmd_realfeedbacks))
    app.add_handler(CommandHandler("reviewfeedback",  cmd_reviewfeedback))
    app.add_handler(CommandHandler("setwelcome",   cmd_setwelcome))
    app.add_handler(CommandHandler("addcode",      cmd_addcode))
    app.add_handler(CommandHandler("addcodes",     cmd_addcodes))
    app.add_handler(CommandHandler("listcodes",    cmd_listcodes))
    app.add_handler(CommandHandler("vipusers",     cmd_vipusers))
    app.add_handler(CommandHandler("allusers",     cmd_allusers))
    app.add_handler(CommandHandler("blockedusers", cmd_blockedusers))
    app.add_handler(CommandHandler("referrals",    cmd_referrals))
    app.add_handler(CommandHandler("publicsignal", cmd_publicsignal))
    app.add_handler(CommandHandler("trialusers",   cmd_trialusers))
    app.add_handler(CommandHandler("revoke",       cmd_revoke))
    app.add_handler(CommandHandler("dbstatus",     cmd_dbstatus))
    app.add_handler(CommandHandler("getid",        cmd_getid))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.Sticker.ALL, handle_sticker))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & (filters.PHOTO | filters.VIDEO | filters.ANIMATION), handle_media))
    app.add_handler(MessageHandler(filters.FORWARDED, protect_forward))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    # Schedule daily jobs if job_queue is available
    try:
        from datetime import time as dt_time
        if app.job_queue:
            app.job_queue.run_daily(check_vip_expiry,        time=dt_time(8, 0, 0))
            app.job_queue.run_daily(send_weekly_stats_job,   time=dt_time(9, 0, 0), days=(1,))
            app.job_queue.run_daily(send_monthly_stats_job,  time=dt_time(9, 0, 1))
            print("Job queue registered OK")
        else:
            print("WARNING: job_queue is None - APScheduler not installed")
    except Exception as e:
        print(f"WARNING: job_queue setup failed: {e}")
    print("Bot is running!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
