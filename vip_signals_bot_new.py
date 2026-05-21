#!/usr/bin/env python3
"""
EVALON VIP SIGNALS BOT - Full Featured v3
"""

import os, json, uuid, time, logging, asyncio
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)

# ============================================================
# WATERMARK
# ============================================================
try:
    from PIL import Image, ImageDraw, ImageFont
    import io
    WATERMARK_ENABLED = True
except ImportError:
    WATERMARK_ENABLED = False
    logger = logging.getLogger(__name__)
    logging.getLogger(__name__).warning("Pillow not installed — watermark disabled")

WATERMARK_TEXT = "@EVALONWINNERSBOT"

def add_watermark(image_bytes: bytes) -> bytes:
    """Add diagonal watermark text to image"""
    if not WATERMARK_ENABLED:
        return image_bytes
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        w, h = img.size

        # Create transparent overlay
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw    = ImageDraw.Draw(overlay)

        # Font size based on image width
        font_size = max(20, w // 18)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
        except:
            font = ImageFont.load_default()

        # Measure text
        bbox     = draw.textbbox((0, 0), WATERMARK_TEXT, font=font)
        txt_w    = bbox[2] - bbox[0]
        txt_h    = bbox[3] - bbox[1]

        # Create text image and rotate
        txt_img  = Image.new("RGBA", (txt_w + 20, txt_h + 20), (0, 0, 0, 0))
        txt_draw = ImageDraw.Draw(txt_img)

        # Shadow
        txt_draw.text((3, 3), WATERMARK_TEXT, font=font, fill=(0, 0, 0, 120))
        # Main text white with opacity
        txt_draw.text((1, 1), WATERMARK_TEXT, font=font, fill=(255, 255, 255, 180))

        rotated = txt_img.rotate(330, expand=True)
        rw, rh  = rotated.size

        # Tile watermark across image
        for y in range(-rh, h + rh, rh + 60):
            for x in range(-rw, w + rw, rw + 40):
                overlay.paste(rotated, (x, y), rotated)

        # Merge overlay with original
        watermarked = Image.alpha_composite(img, overlay).convert("RGB")

        output = io.BytesIO()
        watermarked.save(output, format="JPEG", quality=90)
        output.seek(0)
        return output.read()
    except Exception as e:
        logging.getLogger(__name__).warning(f"Watermark failed: {e}")
        return image_bytes
logger = logging.getLogger(__name__)

# ============================================================
# CONFIG
# ============================================================
BOT_TOKEN      = "8854877793:AAFactgLKt7CVcTlvlhoEKtzdkGCYs0G1fY"
ADMIN_ID       = 8535925646
CHANNEL_INVITE = "https://t.me/+mRNfGaNhz3RkZGRk"
SUPPORT_URL    = "https://t.me/EvalonwinnersBot"
DATA_DIR       = os.environ.get("DATA_DIR", "/data")
os.makedirs(DATA_DIR, exist_ok=True)

DB_FILE        = os.path.join(DATA_DIR, "vip_users.json")
SIGNALS_FILE   = os.path.join(DATA_DIR, "active_signals.json")
FEEDBACK_FILE  = os.path.join(DATA_DIR, "feedback.json")

# ── Sticker / Image file_ids ─────────────────────────────────
# Send each image/sticker to this bot -> it replies with file_id
# Then paste the file_id below
BUY_STICKER   = "CAACAgQAAxkBAAN5ag0iEgRxrB_K9cJB6DguCNtx8GYAAsYQAAIRhYhR9RehjBho_pQ7BA"
SELL_STICKER  = "CAACAgQAAxkBAAN9ag0iH7PojN43V6hG_WdXf04VzBcAAh4QAAInGpBRarR99lasOK87BA"
WIN_STICKER   = "CAACAgEAAxkBAAONag0kQjHKqljsE_rIjhS4X4O_f00AAjkDAAJ1HiBEydhI9OJQ7fA7BA"
LOSS_STICKER  = "CAACAgEAAxkBAAORag0kl_qn_x6XnUYgz4JOPj1tbt8AApcCAAI3JzBHMzsR_0p1m807BA"

# Set to True to send stickers, False to send text-only direction
USE_STICKERS = True

SESSION_START_STICKER = "CAACAgQAAxkBAAOBag0jCHARVYE6EAXkDcBZmUVSiUsAApwPAAL0rJFRZZ7MdT9IUvg7BA"
SESSION_CLOSE_STICKER = "CAACAgQAAxkBAAOFag0jJmtZPuZi72d6Ous1Qj8oT08AAvYQAALdM4lR8Oultiz5ylM7BA"

# ============================================================
# PAIR ALIASES
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

# ============================================================
# CONSTANTS
# ============================================================
KAULI_MBIU = "\U0001f451 *ALWAYS EVALON TRADER IS THE KING OF BINARY* \U0001f451"

WHY_WE_MOVED = (
    "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
    "\U0001f525 *Why We Moved From Our VIP Channel To The Bot System* \U0001f525\n"
    "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n\n"
    "Many people keep asking why we stopped focusing on our VIP channel "
    "that had more than 1,800 subscribers and decided to move into the bot system.\n\n"
    "The main reason is simple \u2014 we wanted to improve *speed, security, and signal delivery* for everyone.\n\n"
    "Our old VIP channel was growing very fast, but we started facing several problems:\n\n"
    "\u2705 VIP links were being shared everywhere\n"
    "\u2705 Some users were getting delayed approvals because of busy schedules\n"
    "\u2705 Many people missed signals because messages were sent manually\n"
    "\u2705 Managing thousands of members became difficult\n"
    "\u2705 Some non-members were accessing shared VIP content unfairly\n\n"
    "That's why we created the bot system.\n\n"
    "\U0001f680 The bot delivers signals *faster, earlier, and automatically* without delays.\n\n"
    "Another big advantage is security:\n\n"
    "\U0001f510 Every user receives a unique personal code\n"
    "\U0001f510 One code works for one account only\n"
    "\U0001f510 Even if someone shares the bot link, they still cannot access signals without a valid code\n"
    "\U0001f510 This helps protect the quality of our VIP service and keeps the system fair for real members only\n\n"
    "The bot system is now more *advanced, secure, faster, and easier* to manage compared to using only a VIP channel.\n"
    "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
)

VIP_RULES = (
    "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
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
    "1\ufe0f\u20e35\ufe0f\u20e3 TRUST YOURSELF BUT FOLLOW THE GUIDANCE\n"
    "1\ufe0f\u20e36\ufe0f\u20e3 SMALL CONSISTENT PROFITS \u2014 DON'T CHASE QUICK RICHES\n"
    "1\ufe0f\u20e37\ufe0f\u20e3 RECORD YOUR TRADES \u2014 LEARN FROM YOUR HISTORY\n"
    "1\ufe0f\u20e38\ufe0f\u20e3 REST WHEN TIRED \u2014 A TIRED MIND MAKES MISTAKES\n"
    "1\ufe0f\u20e39\ufe0f\u20e3 MISSED A SIGNAL \u2014 WAIT FOR THE NEXT ONE\n"
    "2\ufe0f\u20e30\ufe0f\u20e3 EVALON WINNERS \u2014 WE RISE TOGETHER, FOLLOW THE PLAN!\n"
    "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
)

# Session stats (in-memory, resets on new session)
SESSION_STATS = {"wins": 0, "losses": 0}

# ============================================================
# MESSAGE TEMPLATES
# ============================================================
def msg_preparing(pair, expiry):
    return (
        "\U0001f3c6 *EVALON VVIP WINNERS* \U0001f3c6\n\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        f"\U0001f4ca PAIR    : *{pair}*\n"
        f"\u23f1 EXPIRY  : *{expiry} MIN*\n"
        f"\U0001f550 TIME    : *{current_time_utc()}*\n"
        "\U0001f4cd STATUS  : SIGNAL PREPARING...\n\n"
        "\u26a0\ufe0f  WAIT FOR DIRECTION\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n\n"
        "\U0001f525 STAY READY \u2014 ENTRY COMING SOON\n"
        "\U0001f48e VVIP MEMBERS ONLY"
    )

def msg_direction(pair, expiry, direction):
    arrow = "\U0001f4c8" if direction == "BUY" else "\U0001f4c9"
    color = "\U0001f7e2" if direction == "BUY" else "\U0001f534"
    multi = (
        "\n\U0001f525 *HIGH CONFIDENCE SIGNAL!*\n"
        "\U0001f4a5 *OPEN 5 \u2014 10 TRADES NOW!*\n"
    ) if expiry >= 5 else "\n"
    return (
        "\U0001f3c6 *EVALON VVIP WINNERS* \U0001f3c6\n\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        f"\U0001f4ca PAIR      : *{pair}*\n"
        f"\u23f1 EXPIRY    : *{expiry} MIN*\n"
        f"\U0001f550 ENTRY     : *{current_time_utc()}*\n"
        f"{arrow} DIRECTION : *{color} {direction}*\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        f"{multi}"
        "\u26a1 *OPEN YOUR TRADE NOW!*\n"
        "\U0001f48e VVIP MEMBERS ONLY"
    )

def msg_win(pair, expiry, direction, count=1):
    return (
        "\U0001f3c6 *EVALON VVIP WINNERS* \U0001f3c6\n\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        f"\U0001f4ca PAIR      : *{pair}*\n"
        f"\u23f1 EXPIRY    : *{expiry} MIN*\n"
        f"\U0001f4c8 DIRECTION : *{direction}*\n"
        f"\U0001f3c6 RESULT    : *WIN \u2705 x{count}*\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n\n"
        "\U0001f4b0 *Congratulations! Another profit secured!*\n"
        "\U0001f525 Stay focused \u2014 more signals coming!\n"
        "\U0001f48e VVIP MEMBERS ONLY"
    )

def msg_loss(pair, expiry, direction, count=1):
    return (
        "\U0001f3c6 *EVALON VVIP WINNERS* \U0001f3c6\n\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        f"\U0001f4ca PAIR      : *{pair}*\n"
        f"\u23f1 EXPIRY    : *{expiry} MIN*\n"
        f"\U0001f4c8 DIRECTION : *{direction}*\n"
        f"\U0001f534 RESULT    : *LOSS x{count}*\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n\n"
        "\U0001f4aa *Stay strong! Every loss is a lesson!*\n"
        "\U0001f9e0 Protect your capital \u2014 next signal is coming!\n"
        "\U0001f6ab No Martingale \u2014 trust the process!\n"
        "\U0001f48e VVIP MEMBERS ONLY"
    )

def msg_session_soon(minutes, is_vip=False):
    when = f"{minutes} minutes" if minutes < 60 else f"{minutes // 60} hour"
    rules = f"\n{VIP_RULES}" if is_vip else "\n"
    return (
        "\U0001f3c6 *EVALON VVIP WINNERS* \U0001f3c6\n\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        f"\u23f0 SESSION STARTING IN *{when.upper()}*\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n\n"
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
    accuracy = f"{(wins/total*100):.1f}%" if total > 0 else "N/A"
    return (
        "\U0001f3c6 *EVALON VVIP WINNERS* \U0001f3c6\n\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        "\U0001f3c1 *TRADING SESSION ENDED*\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n\n"
        "That's a wrap for today's session!\n\n"
        "\U0001f4ca *SESSION RESULTS:*\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        f"\u2705 WIN      : *{wins}*\n"
        f"\u274c LOSS     : *{losses}*\n"
        f"\U0001f4c8 ACCURACY : *{accuracy}*\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n\n"
        "\U0001f4aa Great discipline leads to consistent profits!\n"
        "\U0001f550 Next session will be announced soon!\n\n"
        "Thank you for trading with us!\n\n"
        f"{KAULI_MBIU}"
    )

def msg_cancelled(pair):
    return (
        "\U0001f3c6 *EVALON VVIP WINNERS* \U0001f3c6\n\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        f"\U0001f4ca PAIR   : *{pair}*\n"
        "\u274c STATUS : *SIGNAL CANCELLED*\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n\n"
        "\u23ed Skip this one \u2014 next signal coming soon!\n"
        "\U0001f9e0 Patience is the key to success!\n"
        "\U0001f48e VVIP MEMBERS ONLY"
    )

# ============================================================
# DATABASE
# ============================================================
def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE) as f:
            return json.load(f)
    return {"users": {}, "codes": {}}

def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

def load_signals():
    if os.path.exists(SIGNALS_FILE):
        with open(SIGNALS_FILE) as f:
            return json.load(f)
    return {}

def save_signals(s):
    with open(SIGNALS_FILE, "w") as f:
        json.dump(s, f, indent=2)

def load_feedback():
    if os.path.exists(FEEDBACK_FILE):
        with open(FEEDBACK_FILE) as f:
            return json.load(f)
    return []

def save_feedback(fb):
    with open(FEEDBACK_FILE, "w") as f:
        json.dump(fb, f, indent=2, ensure_ascii=False)

def get_user(uid):
    db  = load_db()
    key = str(uid)
    if key not in db["users"]:
        db["users"][key] = {
            "vip": False, "vip_code": None,
            "joined_channel": False, "name": "",
            "joined_date": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        save_db(db)
    return db["users"][key]

def update_user(uid, data):
    db  = load_db()
    key = str(uid)
    if key not in db["users"]:
        get_user(uid); db = load_db()
    db["users"][key].update(data)
    save_db(db)

def is_admin(uid):  return uid == ADMIN_ID
def is_vip(uid):    return get_user(uid).get("vip", False)
def get_vip_ids():  return [int(k) for k,v in load_db()["users"].items() if v.get("vip")]
def get_all_ids():  return [int(k) for k in load_db()["users"]]

BASE_MEMBERS = 1500  # Base count for display purposes

def get_display_count() -> int:
    """Returns member count starting from 1500"""
    return BASE_MEMBERS + len(load_db()["users"])
def get_novip_ids():return [int(k) for k,v in load_db()["users"].items() if not v.get("vip")]

def activate_code(code, uid, name):
    db   = load_db()
    code = code.strip().upper()
    if code not in db["codes"] or db["codes"][code].get("used"):
        return False
    db["codes"][code].update({
        "used": True, "used_by": str(uid),
        "used_name": name, "used_date": datetime.now().strftime("%Y-%m-%d %H:%M")
    })
    key = str(uid)
    if key not in db["users"]: db["users"][key] = {}
    db["users"][key].update({"vip": True, "vip_code": code, "name": name})
    save_db(db)
    return True

def new_code(label):
    code = "VIP-" + "-".join(uuid.uuid4().hex[:4].upper() for _ in range(3))
    db   = load_db()
    db["codes"][code] = {
        "label": label, "used": False, "used_by": None,
        "created": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    save_db(db)
    return code

def is_market_day():
    return datetime.now(timezone.utc).weekday() < 5

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
                await context.bot.send_photo(chat_id=uid, photo=photo,
                    caption=caption, parse_mode="Markdown",
                    reply_markup=reply_markup, protect_content=True)
            elif video:
                await context.bot.send_video(chat_id=uid, video=video,
                    caption=caption, parse_mode="Markdown",
                    reply_markup=reply_markup, protect_content=True)
            elif animation:
                await context.bot.send_animation(chat_id=uid, animation=animation,
                    caption=caption, parse_mode="Markdown",
                    reply_markup=reply_markup, protect_content=True)
            elif sticker:
                await context.bot.send_sticker(chat_id=uid, sticker=sticker,
                    protect_content=True)
            elif text:
                await context.bot.send_message(chat_id=uid, text=text,
                    parse_mode="Markdown", reply_markup=reply_markup,
                    protect_content=True)
            sent += 1
        except Exception as e:
            logger.warning(f"Send failed {uid}: {e}")
            failed += 1
    return sent, failed

async def get_file_id_reply(update, context):
    """Admin sends any media -> bot replies with file_id"""
    if not is_admin(update.effective_user.id):
        return False
    msg = update.message
    fid = None
    if msg.sticker:  fid = f"STICKER: `{msg.sticker.file_id}`"
    elif msg.photo:  fid = f"PHOTO: `{msg.photo[-1].file_id}`"
    elif msg.video:  fid = f"VIDEO: `{msg.video.file_id}`"
    elif msg.animation: fid = f"GIF: `{msg.animation.file_id}`"
    if fid:
        await msg.reply_text(
            f"📎 *FILE ID:*\n\n{fid}\n\n"
            "Copy this and paste into the bot code\n"
            "under BUY_STICKER / SELL_STICKER / WIN_STICKER / LOSS_STICKER",
            parse_mode="Markdown"
        )
        return True
    return False

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
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 Contact Admin", url=SUPPORT_URL)]
    ])

def kb_direction(sig_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📈 BUY",          callback_data=f"dir_BUY_{sig_id}"),
            InlineKeyboardButton("📉 SELL",         callback_data=f"dir_SELL_{sig_id}"),
        ],
        [InlineKeyboardButton("❌ Cancel Signal",   callback_data=f"dir_CANCEL_{sig_id}")]
    ])

def kb_result(sig_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ WIN",           callback_data=f"res_WIN_{sig_id}"),
            InlineKeyboardButton("❌ LOSS",          callback_data=f"res_LOSS_{sig_id}"),
        ],
        [InlineKeyboardButton("🏁 End Session",     callback_data="end_session")]
    ])

def kb_after_result():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏁 End Session",     callback_data="end_session")]
    ])

def kb_session_timing():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏰ 30 Minutes",   callback_data="sess_30"),
            InlineKeyboardButton("⏰ 1 Hour",       callback_data="sess_60"),
        ]
    ])

def kb_get_vip():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💎 Get VIP Access",  callback_data="enter_code")]
    ])

def kb_feedback(session_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("1️⃣", callback_data=f"fb_{session_id}_1"),
            InlineKeyboardButton("2️⃣", callback_data=f"fb_{session_id}_2"),
            InlineKeyboardButton("3️⃣", callback_data=f"fb_{session_id}_3"),
            InlineKeyboardButton("4️⃣", callback_data=f"fb_{session_id}_4"),
            InlineKeyboardButton("5️⃣", callback_data=f"fb_{session_id}_5"),
        ]
    ])

def kb_admin_panel():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏰ Session in 30 min", callback_data="sess_30"),
         InlineKeyboardButton("⏰ Session in 1 hr",   callback_data="sess_60")],
        [InlineKeyboardButton("🏁 End Session",        callback_data="end_session")],
    ])

# ============================================================
# /start
# ============================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    name = update.effective_user.first_name or "Trader"
    get_user(uid)
    update_user(uid, {"name": name})

    if is_admin(uid):
        await update.message.reply_text(
            "⚡ *EVALON VIP SIGNALS — ADMIN PANEL*\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "📡 *Send a signal:*\n"
            "Type `EURUSD 5` — broadcasts to all VIP\n\n"
            "📎 *Get file_id of sticker/photo:*\n"
            "Send sticker/photo here — bot replies with ID\n\n"
            "📅 *Session controls:*\n"
            "`/session` — session start alert\n"
            "`/end` — end session + request feedback\n"
            "`/feedback` — view all feedback received\n\n"
            "📢 *Broadcast:*\n"
            "Send media → goes to VIP only\n"
            "`/broadcast text` → VIP only\n"
            "`/broadcast all text` → everyone\n\n"
            "🔧 *Codes:*\n"
            "`/addcode Label` · `/addcodes 10`\n"
            "`/listcodes` · `/vipusers` · `/revoke ID`",
            parse_mode="Markdown",
            reply_markup=kb_admin_panel()
        )
        return

    u = get_user(uid)
    if not u.get("joined_channel"):
        await update.message.reply_text(
            f"\U0001f44b Welcome, *{name}!*\n\n"
            "\u26a1 *EVALON VIP SIGNALS*\n"
            "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n\n"
            "\U0001f4e6 *WHAT YOU GET AS VIP:*\n"
            "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
            "\U0001f4ca Daily Trading Signals\n"
            "\u23f1 Multiple Expiry Times\n"
            "\U0001f4c8 BUY/SELL Direction\n"
            "\u2705 WIN/LOSS Results\n"
            "\U0001f525 High Confidence Alerts\n"
            "\U0001f4c9 8-10 Trades Per Day \u2014 Monday to Friday\n"
            "\U0001f4cb Session Start & End Notifications\n"
            "\U0001f4ca Daily Accuracy Report\n\n"
            "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
            "\u26a0\ufe0f *HOW IT WORKS:*\n"
            "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
            "1\ufe0f\u20e3 Wait for Session Start notification\n"
            "2\ufe0f\u20e3 Get ready with your broker\n"
            "3\ufe0f\u20e3 Receive signal \u2014 follow direction\n"
            "4\ufe0f\u20e3 For 5 MIN+ signals open 5-10 trades\n"
            "5\ufe0f\u20e3 Wait for WIN/LOSS result\n"
            "6\ufe0f\u20e3 End of session \u2014 see your accuracy\n\n"
            "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
            "To access this bot, first join\n"
            "our official signals channel:\n\n"
            "\U0001f4e2 *Evalon Winners Channel*\n\n"
            "Tap *Join Our Channel* then\n"
            "tap *I Have Joined* to continue \U0001f447\n\n"
            f"{WHY_WE_MOVED}\n"
            f"{KAULI_MBIU}",
            parse_mode="Markdown",
            reply_markup=kb_join()
        )
        return

    if not is_vip(uid):
        mday = "🟢 Market open — signals active!" if is_market_day() else "🔴 Weekend — signals resume Monday."
        await update.message.reply_text(
            f"\U0001f44b Welcome back, *{name}!*\n\n"
            "\u26a1 *EVALON VIP SIGNALS*\n"
            "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n\n"
            "\U0001f512 *VIP ACCESS REQUIRED*\n\n"
            "\U0001f4ca *What you get as a VIP member:*\n"
            "\u2705 Real market signals \u2014 Mon to Fri\n"
            "\u2705 Non-Martingale strategy only\n"
            "\u2705 High accuracy entries with entry time\n"
            "\u2705 Win/Loss updates on every trade\n"
            "\u2705 Private \u2014 no forwarding allowed\n\n"
            f"\u23f0 *Monday \u2014 Friday only*\n"
            f"{mday}\n\n"
            f"{WHY_WE_MOVED}\n"
            "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
            "\U0001f511 Have a code? Tap below\n"
            "\U0001f4ac Need one? Contact admin \U0001f447\n\n"
            f"{KAULI_MBIU}",
            parse_mode="Markdown",
            reply_markup=kb_locked()
        )
        return

    mday = "🟢 Market open — signals active!" if is_market_day() else "🔴 Weekend — signals resume Monday."
    await update.message.reply_text(
        f"⚡ *EVALON VIP SIGNALS*\n\n"
        f"Welcome back, *{name}!* 🎯\n\n"
        f"✅ You are a *VIP Member*\n\n"
        f"{mday}\n\n"
        "Stay active — signals arrive here directly 📩",
        parse_mode="Markdown",
        reply_markup=kb_support()
    )

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

    # ── SESSION TIMING ───────────────────────────────────────
    if data in ("sess_30", "sess_60"):
        if not is_admin(uid): return
        # Reset session stats
        SESSION_STATS["wins"] = 0
        SESSION_STATS["losses"] = 0
        mins         = 30 if data == "sess_30" else 60
        vip_text     = msg_session_soon(mins, is_vip=True)
        novip_text   = msg_session_soon(mins, is_vip=False)
        vip_ids      = get_vip_ids()
        novip_ids    = get_novip_ids()
        sv, fv       = await send_to_list(context, vip_ids, text=vip_text)
        sn = fn      = 0
        for nuid in novip_ids:
            try:
                await context.bot.send_message(
                    chat_id=nuid, text=novip_text,
                    parse_mode="Markdown", reply_markup=kb_get_vip()
                )
                sn += 1
            except Exception as e:
                fn += 1

        await q.edit_message_text(
            f"⏰ Session alert sent!\n\n"
            f"💎 VIP: {sv}  |  🔓 Non-VIP: {sn}  |  ❌ Failed: {fv+fn}\n\n"
            "When market is ready, tap below to send START signal 👇",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🟢 Send Session Start Now", callback_data="send_start_now")],
                [InlineKeyboardButton("⚠️ Emergency / Delay",      callback_data="emergency")],
                [InlineKeyboardButton("🏁 End Session",             callback_data="end_session")],
            ])
        )
        return

    # ── SEND SESSION START NOW (manual) ─────────────────────
    if data == "send_start_now":
        if not is_admin(uid): return
        vip_ids    = get_vip_ids()
        start_text = (
            "\U0001f3c6 *EVALON VVIP WINNERS* \U0001f3c6\n\n"
            "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
            "\U0001f7e2 *SESSION IS STARTING NOW!*\n"
            "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n\n"
            "\u2705 Get your charts ready\n"
            "\u2705 Set your expiry time\n"
            "\u2705 Wait for the signal\n\n"
            "\U0001f525 *First signal incoming!*\n"
            "\U0001f48e VVIP MEMBERS ONLY"
        )
        stk = txt = 0
        for vid in vip_ids:
            try:
                await context.bot.send_sticker(chat_id=vid, sticker=SESSION_START_STICKER,
                    protect_content=True)
                stk += 1
            except Exception as e:
                logger.warning(f"Start sticker failed {vid}: {e}")
            try:
                await context.bot.send_message(chat_id=vid, text=start_text,
                    parse_mode="Markdown", protect_content=True)
                txt += 1
            except Exception as e:
                logger.warning(f"Start text failed {vid}: {e}")

        await q.edit_message_text(
            f"\U0001f7e2 Session started!\n\n"
            f"\U0001f3af Stickers sent : {stk}\n"
            f"\U0001f4e8 Messages sent : {txt}\n\n"
            "Send your first signal now!",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⚠️ Emergency / Delay", callback_data="emergency")],
                [InlineKeyboardButton("\U0001f3c1 End Session",  callback_data="end_session")],
            ])
        )
        return

    # ── EMERGENCY / DELAY ────────────────────────────────────
    if data == "emergency":
        if not is_admin(uid): return
        context.user_data["awaiting_emergency"] = True
        await q.message.reply_text(
            "⚠️ *Emergency Message*\n\n"
            "Type your message below.\n"
            "It will be sent to all VIP members immediately.\n\n"
            "Example:\n"
            "_Session delayed — will notify when ready_\n"
            "_Market conditions changed — new time: 15:30 UTC_",
            parse_mode="Markdown"
        )
        return

    # ── END SESSION ──────────────────────────────────────────
    if data == "end_session":
        if not is_admin(uid): return
        vip_ids    = get_vip_ids()
        novip_ids  = get_novip_ids()
        text       = msg_session_end(SESSION_STATS["wins"], SESSION_STATS["losses"])
        session_id = str(int(time.time()))

        feedback_text = (
            "\n\n━━━━━━━━━━━━━━━━━━\n"
            "\U0001f4dd *Rate today's session:*\n"
            "Tap a number (1 = poor, 5 = excellent)"
        )
        fb_kb = kb_feedback(session_id)
        sv = fv = 0
        for vid in vip_ids:
            # Send close sticker first
            try:
                await context.bot.send_sticker(
                    chat_id=vid, sticker=SESSION_CLOSE_STICKER,
                    protect_content=True
                )
            except Exception as e:
                logger.warning(f"Close sticker failed {vid}: {e}")
            # Then session end text + feedback
            try:
                await context.bot.send_message(
                    chat_id=vid,
                    text=text + feedback_text,
                    parse_mode="Markdown",
                    reply_markup=fb_kb,
                    protect_content=True
                )
                sv += 1
            except Exception as e:
                fv += 1

        sn = fn = 0
        for nuid in novip_ids:
            try:
                await context.bot.send_message(
                    chat_id=nuid, text=text,
                    parse_mode="Markdown", reply_markup=kb_get_vip()
                )
                sn += 1
            except Exception as e:
                fn += 1

        sigs = load_signals()
        sigs[f"session_{session_id}"] = {"session_id": session_id}
        save_signals(sigs)

        await q.edit_message_text(
            f"🏁 Session ended!\n\n"
            f"💎 VIP (with feedback): {sv}\n"
            f"🔓 Non-VIP: {sn}\n"
            f"❌ Failed: {fv+fn}\n\n"
            "Tap below to see feedback 👇",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📊 View Feedback", callback_data=f"view_fb_{session_id}")]
            ])
        )
        return

    # ── VIEW FEEDBACK ────────────────────────────────────────
    if data.startswith("view_fb_"):
        if not is_admin(uid): return
        session_id = data.replace("view_fb_", "")
        fb_list    = load_feedback()
        session_fb = [f for f in fb_list if f.get("session_id") == session_id]

        if not session_fb:
            await q.answer("No feedback received yet.", show_alert=True)
            return

        lines = [f"📊 *SESSION FEEDBACK ({len(session_fb)} responses):*\n"]
        ratings = [f["rating"] for f in session_fb]
        avg     = sum(ratings) / len(ratings)
        lines.append(f"⭐ Average: *{avg:.1f} / 5*\n")
        for i, fb in enumerate(session_fb, 1):
            lines.append(
                f"{i}. ⭐ *{fb['rating']}/5* — {fb['name']}\n"
                f"   💬 _{fb.get('comment', 'No comment')}_"
            )
        await context.bot.send_message(
            chat_id=uid,
            text="\n".join(lines),
            parse_mode="Markdown"
        )
        await q.answer("Feedback loaded!", show_alert=False)
        return

    # ── FEEDBACK RATING ──────────────────────────────────────
    if data.startswith("fb_"):
        parts      = data.split("_")
        session_id = parts[1]
        rating     = int(parts[2])

        # Save rating, ask for comment
        context.user_data["fb_session"] = session_id
        context.user_data["fb_rating"]  = rating
        context.user_data["fb_waiting"] = True

        stars = "⭐" * rating
        await q.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_message(
            chat_id=chat,
            text=f"Thank you! You rated: *{stars}*\n\n"
                 "Would you like to add a comment?\n"
                 "Type your comment or send /skip to skip:",
            parse_mode="Markdown"
        )
        return

    # ── DIRECTION ────────────────────────────────────────────
    if data.startswith("dir_"):
        if not is_admin(uid): return
        parts   = data.split("_", 2)
        action  = parts[1]
        sig_id  = parts[2]
        signals = load_signals()

        if sig_id not in signals:
            await q.edit_message_text("⚠️ Signal not found.")
            return

        sig    = signals[sig_id]
        pair   = sig["pair"]
        expiry = sig["expiry"]
        msgs   = sig["msgs"]

        if action == "CANCEL":
            for uid_str, mid in msgs.items():
                try:
                    await context.bot.edit_message_text(
                        chat_id=int(uid_str), message_id=mid,
                        text=msg_cancelled(pair), parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.warning(f"Edit failed {uid_str}: {e}")
            del signals[sig_id]
            save_signals(signals)
            await q.edit_message_text(f"❌ Signal *{pair}* cancelled.", parse_mode="Markdown")
            return

        # BUY or SELL — send 2 messages:
        # MSG 1: direction text
        # MSG 2: sticker
        direction_text = msg_direction(pair, expiry, action)
        sticker_id     = BUY_STICKER if action == "BUY" else SELL_STICKER
        sent_txt = sent_stk = 0

        for uid_str in msgs:
            uidint = int(uid_str)
            # Send direction text as new message
            try:
                await context.bot.send_message(
                    chat_id=uidint,
                    text=direction_text,
                    parse_mode="Markdown",
                    protect_content=True
                )
                sent_txt += 1
            except Exception as e:
                logger.warning(f"Direction text failed {uid_str}: {e}")
            # Send sticker
            if USE_STICKERS and sticker_id and "PASTE_" not in sticker_id:
                try:
                    await context.bot.send_sticker(chat_id=uidint, sticker=sticker_id,
                        protect_content=True)
                    sent_stk += 1
                except Exception as e:
                    logger.warning(f"Sticker failed {uid_str}: {e}")

        signals[sig_id]["direction"] = action
        save_signals(signals)

        arrow = "📈" if action == "BUY" else "📉"
        color = "🟢" if action == "BUY" else "🔴"
        await q.edit_message_text(
            f"{arrow} *{color} {action}* sent for *{pair}*!\n\n"
            f"📨 Text sent : {sent_txt}\n"
            f"🎯 Stickers  : {sent_stk}\n\n"
            "Select result when trade closes 👇",
            parse_mode="Markdown",
            reply_markup=kb_result(sig_id)
        )
        return

    # ── RESULT ───────────────────────────────────────────────
    if data.startswith("res_"):
        if not is_admin(uid): return
        parts     = data.split("_", 2)
        result    = parts[1]
        sig_id    = parts[2]
        # Store pending result, ask for trade count
        context.user_data["pending_result"] = result
        context.user_data["pending_sig_id"] = sig_id
        context.user_data["awaiting_trade_count"] = True
        icon = "\u2705" if result == "WIN" else "\u274c"
        await q.message.reply_text(
            f"{icon} *{result}* — How many trades {result.lower()}?\n\n"
            "Reply with a number (e.g. `10`)",
            parse_mode="Markdown"
        )
        return

    # ── CLEAR FEEDBACK ───────────────────────────────────────
    if data == "clear_feedback":
        if not is_admin(uid): return
        save_feedback([])
        await q.edit_message_text("🗑️ *All feedback cleared!*", parse_mode="Markdown")
        return

    # ── CHECK JOIN ───────────────────────────────────────────
    if data == "check_join":
        update_user(uid, {"joined_channel": True, "name": name})
        try: await q.message.delete()
        except: pass
        if is_vip(uid):
            mday = "🟢 Market open!" if is_market_day() else "🔴 Weekend — resumes Monday."
            await context.bot.send_message(
                chat_id=chat,
                text=f"✅ *Joined! Welcome back, {name}!*\n\n{mday}",
                parse_mode="Markdown", reply_markup=kb_support()
            )
        else:
            mday = "🟢 Market open!" if is_market_day() else "🔴 Weekend — resumes Monday."
            await context.bot.send_message(
                chat_id=chat,
                text=f"✅ *Channel joined! Welcome, {name}!*\n\n"
                     "⚡ *EVALON VIP SIGNALS*\n"
                     "━━━━━━━━━━━━━━━━━━\n\n"
                     "🔒 *VIP ACCESS REQUIRED*\n\n"
                     "✅ Real market signals — Mon to Fri\n"
                     "✅ Non-Martingale strategy\n"
                     "✅ Entry time on every signal\n"
                     "✅ Win/Loss updates\n"
                     "✅ Private — no forwarding\n\n"
                     f"⏰ Mon–Fri only  |  {mday}\n\n"
                     "🔑 Have a VIP code? Tap below 👇",
                parse_mode="Markdown", reply_markup=kb_locked()
            )
        return

    # ── ENTER CODE ───────────────────────────────────────────
    if data == "enter_code":
        context.user_data["awaiting_code"] = True
        try: await q.message.delete()
        except: pass
        await context.bot.send_message(
            chat_id=chat,
            text="🔑 *Enter your VIP code:*\n\n"
                 "Format: `VIP-XXXX-XXXX-XXXX`\n\n"
                 "Don't have a code yet?\n"
                 "Contact admin to get yours 👇",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 Contact Admin", url=SUPPORT_URL)]
            ])
        )
        return

# ============================================================
# TEXT HANDLER
# ============================================================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    name = update.effective_user.first_name or "Trader"
    text = update.message.text.strip()

    # Block forwards
    if update.message.forward_date and not is_admin(uid):
        try: await update.message.delete()
        except: pass
        await update.message.reply_text("🔒 Forwarding is not allowed in this bot.")
        return

    # ── ADMIN SIGNAL SHORTHAND ───────────────────────────────
    if is_admin(uid):
        # Feedback comment skip
        if text == "/skip":
            context.user_data["fb_waiting"] = False
            return

        # Emergency message
        if context.user_data.get("awaiting_emergency"):
            context.user_data["awaiting_emergency"] = False
            vip_ids = get_vip_ids()
            emergency_text = (
                "\U0001f3c6 *EVALON VVIP WINNERS* \U0001f3c6\n\n"
                "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
                "\u26a0\ufe0f *IMPORTANT UPDATE*\n"
                "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n\n"
                f"{text}\n\n"
                "\U0001f48e VVIP MEMBERS ONLY"
            )
            sent, failed = await send_to_list(context, vip_ids, text=emergency_text)
            await update.message.reply_text(
                f"\u26a0\ufe0f *Emergency message sent!*\n\n"
                f"\u2705 Sent to *{sent}* VIP members!",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("\U0001f7e2 Send Session Start Now", callback_data="send_start_now")],
                    [InlineKeyboardButton("\u26a0\ufe0f Emergency / Delay",   callback_data="emergency")],
                    [InlineKeyboardButton("\U0001f3c1 End Session",            callback_data="end_session")],
                ])
            )
            return

        # ── TRADE COUNT (WIN/LOSS) ───────────────────────────
        if context.user_data.get("awaiting_trade_count"):
            try:
                count = int(text.strip())
            except ValueError:
                await update.message.reply_text("Please enter a valid number (e.g. `10`)", parse_mode="Markdown")
                return
            context.user_data["awaiting_trade_count"] = False
            result    = context.user_data.pop("pending_result", "WIN")
            sig_id    = context.user_data.pop("pending_sig_id", None)
            signals   = load_signals()
            sig       = signals.get(sig_id, {}) if sig_id else {}
            pair      = sig.get("pair", "?")
            expiry    = sig.get("expiry", "?")
            direction = sig.get("direction", "?")
            msgs      = sig.get("msgs", {})

            # Update session stats
            if result == "WIN":
                SESSION_STATS["wins"] += count
            else:
                SESSION_STATS["losses"] += count

            result_text = msg_win(pair, expiry, direction, count) if result == "WIN" else msg_loss(pair, expiry, direction, count)
            sticker_id  = WIN_STICKER if result == "WIN" else LOSS_STICKER
            sent = stk = 0

            for uid_str in msgs:
                uidint = int(uid_str)
                try:
                    await context.bot.send_message(
                        chat_id=uidint, text=result_text, parse_mode="Markdown",
                        protect_content=True
                    )
                    sent += 1
                except Exception as e:
                    logger.warning(f"Result failed {uid_str}: {e}")
                if USE_STICKERS and sticker_id and "PASTE_" not in sticker_id:
                    try:
                        await context.bot.send_sticker(chat_id=uidint, sticker=sticker_id,
                            protect_content=True)
                        stk += 1
                    except Exception as e:
                        logger.warning(f"Sticker failed {uid_str}: {e}")

            if sig_id and sig_id in signals:
                del signals[sig_id]
                save_signals(signals)

            icon = "\u2705" if result == "WIN" else "\u274c"
            total = SESSION_STATS["wins"] + SESSION_STATS["losses"]
            acc   = f"{(SESSION_STATS['wins']/total*100):.1f}%" if total > 0 else "N/A"
            await update.message.reply_text(
                f"{icon} *{result} x{count}* sent for *{pair}*!\n\n"
                f"\U0001f4e8 Sent: {sent}  |  \U0001f3af Stickers: {stk}\n\n"
                f"\U0001f4ca Session so far: \u2705 {SESSION_STATS['wins']} wins | \u274c {SESSION_STATS['losses']} losses | {acc}\n\n"
                "Tap End Session when done or send next signal.",
                parse_mode="Markdown",
                reply_markup=kb_after_result()
            )
            return

        parsed = parse_signal(text)
        if not parsed:
            return
        pair, expiry = parsed
        vip_ids = get_vip_ids()
        if not vip_ids:
            await update.message.reply_text("⚠️ No VIP members yet.")
            return

        try: await update.message.delete()
        except: pass

        preparing = msg_preparing(pair, expiry)
        sent_msgs = {}
        for vid in vip_ids:
            try:
                m = await context.bot.send_message(
                    chat_id=vid, text=preparing, parse_mode="Markdown",
                    protect_content=True
                )
                sent_msgs[str(vid)] = m.message_id
            except Exception as e:
                logger.warning(f"Send failed {vid}: {e}")

        sig_id  = f"{pair.replace('/','').replace(' ','')}_{expiry}_{int(time.time())}"
        signals = load_signals()
        signals[sig_id] = {
            "pair": pair, "expiry": expiry,
            "msgs": sent_msgs, "time": datetime.now().strftime("%H:%M")
        }
        save_signals(signals)

        await context.bot.send_message(
            chat_id=uid,
            text=f"✅ Signal sent to *{len(sent_msgs)}* VIP members!\n\n"
                 f"📊 *{pair}*  |  ⏱ *{expiry} MIN*\n\n"
                 "Choose direction when ready 👇",
            parse_mode="Markdown",
            reply_markup=kb_direction(sig_id)
        )
        return

    # ── FEEDBACK COMMENT ────────────────────────────────────
    if context.user_data.get("fb_waiting"):
        session_id = context.user_data.pop("fb_session", "")
        rating     = context.user_data.pop("fb_rating", 0)
        context.user_data["fb_waiting"] = False
        comment    = text if text != "/skip" else ""

        fb_list = load_feedback()
        fb_list.append({
            "session_id": session_id,
            "user_id":    uid,
            "name":       name,
            "rating":     rating,
            "comment":    comment,
            "date":       datetime.now().strftime("%Y-%m-%d %H:%M")
        })
        save_feedback(fb_list)

        await update.message.reply_text(
            "✅ *Thank you for your feedback!*\n\n"
            "Your response has been recorded.\n"
            "See you in the next session! 🎯",
            parse_mode="Markdown"
        )
        return

    # ── VIP FEEDBACK WAITING — block non-text ────────────────
    if context.user_data.get("fb_waiting"):
        await update.message.reply_text(
            "✏️ *Please send text only.*\n"
            "No photos or files allowed for feedback.\n\n"
            "Type your comment or send /skip to skip.",
            parse_mode="Markdown"
        )
        return

    # ── VIP CODE INPUT ───────────────────────────────────────
    if not context.user_data.get("awaiting_code"):
        if not is_vip(uid):
            await update.message.reply_text(
                "🔒 Please enter your VIP code.",
                reply_markup=kb_locked()
            )
        return

    code = text.upper()
    context.user_data["awaiting_code"] = False

    if activate_code(code, uid, name):
        logger.info(f"VIP activated: {uid} ({name}) code {code}")
        mday = "🟢 Market open — signals active!" if is_market_day() else "🔴 Weekend — signals resume Monday."
        await update.message.reply_text(
            f"✅ *VIP Access Activated! Welcome, {name}!* 🎉\n\n"
            "⚡ *EVALON VIP SIGNALS*\n\n"
            "You are now a *VIP Member* 🎯\n\n"
            "✅ Real market signals — Mon to Fri\n"
            "✅ Non-Martingale strategy\n"
            "✅ Entry time on every signal\n"
            "✅ Win/Loss updates\n\n"
            f"{mday}\n\n"
            "Stay active — signals arrive here 📩",
            parse_mode="Markdown",
            reply_markup=kb_support()
        )
    else:
        db   = load_db()
        cdat = db["codes"].get(code)
        if cdat and cdat.get("used"):
            await update.message.reply_text(
                "❌ *This code has already been used!*\n\n"
                "Each code is for one person only.\n"
                "Contact admin for your own code:",
                parse_mode="Markdown", reply_markup=kb_locked()
            )
        else:
            await update.message.reply_text(
                "❌ *Invalid VIP code!*\n\nContact admin to get your code:",
                parse_mode="Markdown", reply_markup=kb_locked()
            )

# ============================================================
# MEDIA HANDLER — admin sends photo/video/sticker
# ============================================================
async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    # Non-admin: block forwards, and notify if waiting feedback
    if not is_admin(uid):
        if context.user_data.get("fb_waiting"):
            await update.message.reply_text(
                "✏️ *Please send text only.*\n"
                "No photos or files allowed for feedback.\n\n"
                "Type your comment or send /skip to skip.",
                parse_mode="Markdown"
            )
            return
        if update.message.forward_date:
            try: await update.message.delete()
            except: pass
            await update.message.reply_text("🔒 Forwarding is not allowed.")
        return

    # Admin: save welcome image if awaiting
    if context.user_data.get("awaiting_welcome_image"):
        context.user_data["awaiting_welcome_image"] = False
        msg = update.message
        file_id = None
        if msg.photo:
            file_id = msg.photo[-1].file_id
        if file_id:
            db = load_db()
            db["welcome_image"] = file_id
            save_db(db)
            await update.message.reply_text(
                "✅ *Welcome image saved!*\n\n"
                "New users will now receive this image with the welcome message.",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text("❌ Please send a photo only.")
        return

    # Admin: reply with file_id for setup
    got_id = await get_file_id_reply(update, context)
    if got_id:
        return

    # Admin: broadcast media to VIP
    msg     = update.message
    vip_ids = get_vip_ids()
    if not vip_ids:
        await msg.reply_text("⚠️ No VIP members yet.")
        return

    sent = failed = 0
    if msg.photo:
        # Download, watermark, re-upload
        try:
            file     = await context.bot.get_file(msg.photo[-1].file_id)
            img_data = await file.download_as_bytearray()
            wm_data  = add_watermark(bytes(img_data))
            wm_bio   = __import__("io").BytesIO(wm_data)
            wm_bio.name = "signal.jpg"
            sent, failed = await send_to_list(context, vip_ids,
                photo=wm_bio, caption=msg.caption)
        except Exception as e:
            logger.warning(f"Watermark photo failed: {e}")
            sent, failed = await send_to_list(context, vip_ids,
                photo=msg.photo[-1].file_id, caption=msg.caption)
    elif msg.video:
        # Video — watermark not applied (too heavy), send as-is
        sent, failed = await send_to_list(context, vip_ids,
            video=msg.video.file_id, caption=msg.caption)
    elif msg.animation:
        sent, failed = await send_to_list(context, vip_ids,
            animation=msg.animation.file_id, caption=msg.caption)

    if sent or failed:
        await msg.reply_text(
            f"✅ Sent to *{sent}* VIP members!",
            parse_mode="Markdown"
        )

# ============================================================
# STICKER HANDLER — admin sends sticker -> get file_id or broadcast
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
    if not sticker:
        return

    # Check if admin is setting up sticker file_ids
    fid = sticker.file_id
    await update.message.reply_text(
        f"📎 *STICKER FILE ID:*\n\n`{fid}`\n\n"
        "Paste this into BUY_STICKER / SELL_STICKER / WIN_STICKER / LOSS_STICKER\n\n"
        "Also sending sticker to all VIP members...",
        parse_mode="Markdown"
    )

    # Broadcast sticker to VIP
    vip_ids = get_vip_ids()
    if vip_ids:
        sent, failed = await send_to_list(context, vip_ids, sticker=fid)
        await update.message.reply_text(
            f"✅ Sticker sent to *{sent}* VIP members!",
            parse_mode="Markdown"
        )

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

    if not targets:
        await update.message.reply_text("⚠️ No users yet.")
        return

    sent = failed = 0
    if replied:
        if replied.photo:
            try:
                file     = await context.bot.get_file(replied.photo[-1].file_id)
                img_data = await file.download_as_bytearray()
                wm_data  = add_watermark(bytes(img_data))
                wm_bio   = __import__("io").BytesIO(wm_data)
                wm_bio.name = "signal.jpg"
                sent, failed = await send_to_list(context, targets,
                    photo=wm_bio, caption=replied.caption or caption or None)
            except Exception as e:
                logger.warning(f"Watermark broadcast failed: {e}")
                sent, failed = await send_to_list(context, targets,
                    photo=replied.photo[-1].file_id, caption=replied.caption or caption or None)
        elif replied.video:
            sent, failed = await send_to_list(context, targets,
                video=replied.video.file_id, caption=replied.caption or caption or None)
        elif replied.sticker:
            sent, failed = await send_to_list(context, targets, sticker=replied.sticker.file_id)
        elif replied.animation:
            sent, failed = await send_to_list(context, targets,
                animation=replied.animation.file_id, caption=replied.caption or caption or None)
        else:
            sent, failed = await send_to_list(context, targets, text=replied.text or caption)
    elif caption:
        sent, failed = await send_to_list(context, targets, text=caption)
    else:
        await update.message.reply_text(
            "📢 *Broadcast usage:*\n\n"
            "VIP only: `/broadcast Your message`\n"
            "Everyone: `/broadcast all Your message`\n"
            "Or reply to any media with `/broadcast`",
            parse_mode="Markdown"
        )
        return

    who = "everyone" if to_all else "VIP members"
    await update.message.reply_text(
        f"📡 *Broadcast complete!*\n\n👥 {who}\n✅ Sent: {sent} members",
        parse_mode="Markdown"
    )

# ============================================================
# /session, /end, /feedback
# ============================================================
async def session_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    await update.message.reply_text(
        "⏰ *Session start alert — select timing:*",
        parse_mode="Markdown",
        reply_markup=kb_session_timing()
    )

async def end_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    # Trigger end_session via fake callback
    vip_ids    = get_vip_ids()
    novip_ids  = get_novip_ids()
    text       = msg_session_end()
    session_id = str(int(time.time()))
    fb_text    = (
        "\n\n━━━━━━━━━━━━━━━━━━\n"
        "\U0001f4dd *Rate today's session:*\n"
        "Tap a number (1 = poor, 5 = excellent)"
    )
    fb_kb = kb_feedback(session_id)
    sv = fv = 0
    for vid in vip_ids:
        try:
            await context.bot.send_message(
                chat_id=vid, text=text + fb_text,
                parse_mode="Markdown", reply_markup=fb_kb
            )
            sv += 1
        except: fv += 1

    sn = fn = 0
    for nuid in novip_ids:
        try:
            await context.bot.send_message(
                chat_id=nuid, text=text,
                parse_mode="Markdown", reply_markup=kb_get_vip()
            )
            sn += 1
        except: fn += 1

    sigs = load_signals()
    sigs[f"session_{session_id}"] = {"session_id": session_id}
    save_signals(sigs)

    await update.message.reply_text(
        f"🏁 *Session ended!*\n\n"
        f"💎 VIP (with feedback prompt): {sv}\n"
        f"🔓 Non-VIP: {sn}\n"
        f"❌ Failed: {fv+fn}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 View Feedback", callback_data=f"view_fb_{session_id}")]
        ])
    )

async def feedback_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    import random

    wins   = SESSION_STATS.get("wins", 0)
    losses = SESSION_STATS.get("losses", 0)
    total  = wins + losses

    # Build accuracy string for fake feedback
    if total > 0:
        acc_pct = int(wins / total * 100)
        acc_str = f"{wins}/{total}" if total > 0 else "all"
        acc_100 = acc_pct == 100
    else:
        acc_pct = 100
        acc_str = "all"
        acc_100 = True

    # Fake feedback pool
    NAMES = [
        "James","Ali","Sarah","Ravi","Carlos","Fatou","Mike","Zara",
        "John K","Patel","Sarah M","Ali B","James T","Priya","Tariq",
        "David","Marco","Aisha","Kevin","Fatima","Raj S","Chris",
        "Hassan","Nina","Pedro","Amara","Tony","Leila","Sam","Yusuf",
        "Kate","Arjun","Layla","Eric","Sofia","Ahmed","Grace","Omar",
        "Lisa","Karim","Anna","Bilal","Emma","Vikram","Nadia","Joel"
    ]

    def win_comment():
        templates = [
            # English 60%
            f"Session today was fire! Won ${random.randint(120,4500)} in just {wins} signals 🔥",
            f"{acc_str} won today, signals were clean and accurate 💪",
            f"Today {acc_pct}% accuracy! Every trade was perfect 👑",
            f"Won ${random.randint(150,3200)} today following every signal strictly 🙏",
            f"{wins} out of {total} won today. EVALON never disappoints 🏆",
            f"I joined today and I can't believe it! {wins} wins already 😱",
            f"Every day profits, thank you for this chance boss 💰",
            f"${random.randint(120,4500)} profit today. This is real! 🔥",
            f"All {wins} signals hit today. This is not luck, this is EVALON 👑",
            f"Been here 2 weeks now, every session profitable. Won ${random.randint(200,2000)} 💎",
            f"Today session {acc_pct}% thank you sir 🙏",
            f"Managed to win {wins} out of {total}, not bad at all 💪",
            # Swahili 12%
            f"Leo session ilikuwa nzuri sana, signals {wins}/{total} ziligonga. Asante sana 🏆",
            f"Nimeweza kupata faida leo! ${random.randint(120,1500)} kwa session moja tu 💰",
            f"Niliingia leo sijaamini! Signals zote ziligonga 😱",
            f"Kila siku faida, asante kwa fursa hii boss 🙏",
            # Urdu 13%
            f"Mashallah! Aaj sab signals perfect the. Bohot khushi hui 💰",
            f"Aaj ka session ekdum mast tha! {wins} mein se {wins} win. ${random.randint(200,2000)} pocket 🙏",
            f"Yaar aaj toh kamaal ho gaya! ${random.randint(120,4500)} profit hua 🔥",
            f"Bohot acha signal tha aaj, shukriya boss 🙏",
            # Hindi 20%
            f"Aaj {wins} signal sahi nikle, ${random.randint(890,3000)} profit hua. Bahut badhiya hai yaar 💪",
            f"Har roz profit! Aaj bhi {acc_pct}% accuracy. Thank you EVALON 🏆",
            f"Aaj join kiya aur vishwas nahi hua! Sab signals sahi the 😱",
            f"${random.randint(150,4500)} aaj kamaye. Ye real hai! 🔥",
            f"Bahut badiya session tha. {wins} wins out of {total} 👑",
            # Portuguese 5%
            f"Hoje foi incrível! {wins} de {total} acertaram. Muito obrigado EVALON 👑",
            f"Hoje ganhei ${random.randint(120,3000)}. Este sistema é real! 🔥",
        ]
        return random.choice(templates)

    # Generate fake feedback entries
    used_nums = set()
    def get_num():
        n = random.randint(1501, 2800)
        while n in used_nums:
            n = random.randint(1501, 2800)
        used_nums.add(n)
        return n

    stars_pool = [5,5,5,4,4,4,5,4,3,5,4,5,4,5,3,4,5,5,4,5]
    fake_count = random.randint(12, 18)
    fake_entries = []
    used_names = []
    for _ in range(fake_count):
        name = random.choice(NAMES)
        # Sometimes use two names
        if random.random() < 0.3:
            second = random.choice([n for n in NAMES if n != name])
            display_name = f"{name.split()[0]} {second.split()[0][0]}"
        else:
            display_name = name.split()[0]
        stars = random.choice(stars_pool)
        star_str = "⭐" * stars
        num = get_num()
        fake_entries.append({
            "num": num,
            "name": display_name,
            "stars": star_str,
            "comment": win_comment()
        })

    # Get real feedback (4 and 5 stars only)
    fb_list = load_feedback()
    real_entries = [f for f in fb_list if f.get("rating", 0) >= 4]

    # Combine: real first, then fake
    all_entries = []
    for fb in real_entries:
        all_entries.append({
            "num": random.randint(1501, 2800),
            "name": fb.get("name", "User"),
            "stars": "⭐" * fb.get("rating", 5),
            "comment": fb.get("comment", "Great signals!"),
            "real": True
        })
    for fe in fake_entries:
        all_entries.append(fe)

    if not all_entries:
        await update.message.reply_text("📊 No feedback yet.")
        return

    # Send one by one with delay
    await update.message.reply_text(
        f"📊 *Sending {len(all_entries)} feedback...*",
        parse_mode="Markdown"
    )

    for entry in all_entries:
        text = (
            f"{entry['stars']} *#{entry['num']}*\n"
            f"👤 *{entry['name']}*\n"
            f"_\"{entry['comment']}\"_"
        )
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=text,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.warning(f"Feedback send failed: {e}")
        await asyncio.sleep(random.uniform(1.5, 3.0))

    # Final summary with clear button
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"✅ *Done! {len(all_entries)} feedback sent.*\n\n"
             f"💎 Real: {len(real_entries)}  |  🤖 Generated: {len(fake_entries)}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🗑️ Clear All Feedback", callback_data="clear_feedback")]
        ])
    )


async def cmd_setwelcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    context.user_data["awaiting_welcome_image"] = True
    await update.message.reply_text(
        "🖼️ *Send the welcome image now.*\n\n"
        "It will be saved and sent to all new users with the welcome message.",
        parse_mode="Markdown"
    )

# ============================================================
# ADMIN COMMANDS
# ============================================================
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    msg1 = (
        "\U0001f4d6 *EVALON VIP SIGNALS — ADMIN GUIDE*\n\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        "\U0001f4e1 *SENDING SIGNALS*\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        "Type pair + expiry and send:\n"
        "`EURUSD 5` \u2192 EUR/USD 5 min\n"
        "`XAUUSD 1` \u2192 XAU/USD 1 min\n"
        "`GBPUSD 3` \u2192 GBP/USD 3 min\n\n"
        "Bot sends PREPARING to all VIP.\n"
        "Then you see buttons:\n"
        "\U0001f4c8 *BUY* \u2014 direction + sticker\n"
        "\U0001f4c9 *SELL* \u2014 direction + sticker\n"
        "\u274c *Cancel* \u2014 cancels signal\n\n"
        "After BUY/SELL:\n"
        "\u2705 *WIN* \u2014 win message + sticker\n"
        "\u274c *LOSS* \u2014 loss message + sticker\n"
        "\U0001f3c1 *End Session* \u2014 ends session\n\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        "\U0001f4c5 *SESSION CONTROLS*\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        "`/session` \u2014 Send session alert\n"
        "Choose 30 min or 1 hour notice.\n"
        "Tap *\U0001f7e2 Send Session Start Now*\n"
        "when market is ready.\n\n"
        "`/end` \u2014 End session\n"
        "Sends close sticker + end message\n"
        "to all VIP with feedback (1-5\u2b50)\n\n"
        "*\u26a0\ufe0f Emergency / Delay button*\n"
        "Tap after session alert, type message\n"
        "\u2014 sent to all VIP immediately.\n"
        "Example: Session delayed to 15:30 UTC"
    )
    msg2 = (
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        "\U0001f4e2 *BROADCAST*\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        "Send photo/video directly \u2192 VIP only\n\n"
        "`/broadcast text` \u2192 VIP only\n"
        "`/broadcast all text` \u2192 Everyone\n"
        "Reply to media + `/broadcast` \u2192 VIP\n"
        "Reply to media + `/broadcast all` \u2192 All\n\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        "\U0001f511 *VIP CODE MANAGEMENT*\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        "`/addcode Ali` \u2014 Create 1 code\n"
        "`/addcodes 10` \u2014 Create 10 codes\n"
        "`/listcodes` \u2014 View all codes\n"
        "  \u26aa Unused = not activated yet\n"
        "  \U0001f7e2 Used = already activated\n\n"
        "`/vipusers` \u2014 View all VIP members\n"
        "`/revoke USER_ID` \u2014 Remove VIP\n\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        "\U0001f4ca *FEEDBACK*\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        "`/feedback` \u2014 View all session ratings\n"
        "`/stats` \u2014 Full member statistics\n"
        "After /end tap *\U0001f4ca View Feedback*\n\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        "\U0001f4ce *GET STICKER FILE IDs*\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        "Send any sticker to this bot \u2014\n"
        "it replies with the file_id.\n"
        "Paste into code:\n"
        "`BUY_STICKER` `SELL_STICKER`\n"
        "`WIN_STICKER` `LOSS_STICKER`\n"
        "`SESSION_START_STICKER`\n"
        "`SESSION_CLOSE_STICKER`\n\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        "\u26a1 *QUICK PAIRS REFERENCE*\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        "Forex: `EURUSD` `GBPUSD` `USDJPY`\n"
        "Gold: `XAUUSD`  Silver: `XAGUSD`\n"
        "Crypto: `BTCUSD` `ETHUSD` `SOLUSD`\n"
        "Index: `NAS100` `US30` `GER40`\n"
        "OTC: `EURUSDOTC` `XAUUSDOTC`\n\n"
        "Expiry: `1` `2` `3` `5` `10` `15`\n\n"
        "Type `/help` anytime for this guide."
    )
    await update.message.reply_text(msg1, parse_mode="Markdown")
    await update.message.reply_text(msg2, parse_mode="Markdown")


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    db      = load_db()
    users   = db.get("users", {})
    codes   = db.get("codes", {})
    total   = len(users)
    vip     = sum(1 for u in users.values() if u.get("vip"))
    non_vip = total - vip
    unused  = sum(1 for c in codes.values() if not c.get("used"))
    used    = sum(1 for c in codes.values() if c.get("used"))
    display = BASE_MEMBERS + total

    lines_out = [
        "\U0001f4ca *EVALON VIP SIGNALS \u2014 STATS*\n",
        "\u2501" * 14,
        "\n\U0001f46e *MEMBERS*\n",
        "\u2501" * 14,
        f"\n\U0001f4e3 Total followers  : *{display}*",
        f"\n\U0001f48e VIP members      : *{vip}*",
        f"\n\U0001f513 Non-VIP (joined) : *{non_vip}*\n",
        "\u2501" * 14,
        "\n\U0001f511 *VIP CODES*\n",
        "\u2501" * 14,
        f"\n\U0001f7e2 Active codes : *{used}*",
        f"\n\u26aa Unused codes : *{unused}*",
        f"\n\U0001f4cb Total codes  : *{len(codes)}*",
    ]
    await update.message.reply_text("".join(lines_out), parse_mode="Markdown")

    fb_list = load_feedback()
    if fb_list:
        ratings = [f["rating"] for f in fb_list]
        avg     = sum(ratings) / len(ratings)
        fb_lines = [
            "\U0001f4dd *FEEDBACK SUMMARY*\n\n",
            f"Total responses : *{len(fb_list)}*\n",
            f"Average rating  : *{avg:.1f}/5* \u2b50\n\n",
            f"\U0001f31f 5 stars : {ratings.count(5)}\n",
            f"\u2b50 4 stars : {ratings.count(4)}\n",
            f"\u2b50 3 stars : {ratings.count(3)}\n",
            f"\u2b50 2 stars : {ratings.count(2)}\n",
            f"\u2b50 1 star  : {ratings.count(1)}",
        ]
        await update.message.reply_text("".join(fb_lines), parse_mode="Markdown")
    else:
        await update.message.reply_text("No feedback received yet.")


async def cmd_addcode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    label = " ".join(context.args) if context.args else "VIP User"
    code  = new_code(label)
    await update.message.reply_text(
        f"✅ *VIP Code Created!*\n\n👤 Label: *{label}*\n🔑 Code: `{code}`",
        parse_mode="Markdown"
    )

async def cmd_addcodes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    try:
        count = min(int(context.args[0]), 50) if context.args else 1
    except:
        count = 1
    codes = [new_code(f"VIP User {i+1}") for i in range(count)]
    await update.message.reply_text(
        f"✅ *{count} VIP Codes Created!*\n\n" + "\n".join(f"`{c}`" for c in codes),
        parse_mode="Markdown"
    )

async def cmd_listcodes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    db    = load_db()
    codes = db.get("codes", {})
    if not codes:
        await update.message.reply_text("📋 No codes yet.")
        return
    unused = [(c, v) for c, v in codes.items() if not v.get("used")]
    used   = [(c, v) for c, v in codes.items() if v.get("used")]
    lines  = [f"📋 *VIP CODES ({len(codes)} total)*\n⚪ Unused: {len(unused)}  🟢 Used: {len(used)}\n"]
    if unused:
        lines.append("*— UNUSED —*")
        for c, v in unused[:20]: lines.append(f"`{c}` — {v.get('label','?')}")
    if used:
        lines.append("\n*— USED —*")
        for c, v in used[:20]: lines.append(f"`{c}` — {v.get('used_name','?')} ({v.get('used_date','?')})")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def cmd_vipusers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    vids = get_vip_ids()
    if not vids:
        await update.message.reply_text("👥 No VIP members yet.")
        return
    db    = load_db()
    lines = [f"👥 *VIP MEMBERS ({get_display_count()} total):*\n"]
    for vid in vids:
        info = db["users"].get(str(vid), {})
        lines.append(f"👤 *{info.get('name','?')}*  |  🔑 `{info.get('vip_code','?')}`  |  📅 {info.get('joined_date','?')}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def cmd_revoke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if not context.args:
        await update.message.reply_text("Usage: `/revoke USER_ID`", parse_mode="Markdown")
        return
    try: target = int(context.args[0])
    except:
        await update.message.reply_text("❌ Invalid user ID.")
        return
    db  = load_db()
    key = str(target)
    if key not in db["users"]:
        await update.message.reply_text("❌ User not found.")
        return
    name = db["users"][key].get("name", "Unknown")
    code = db["users"][key].get("vip_code")
    db["users"][key]["vip"]      = False
    db["users"][key]["vip_code"] = None
    if code and code in db["codes"]:
        db["codes"][code]["used"] = False
        db["codes"][code]["used_by"] = None
    save_db(db)
    await update.message.reply_text(
        f"⛔ *VIP Revoked!*\n\n👤 *{name}*\n🔑 Code `{code}` is free again.",
        parse_mode="Markdown"
    )

async def protect_forward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_admin(update.effective_user.id): return
    try: await update.message.delete()
    except: pass
    await update.message.reply_text("🔒 Forwarding is not allowed in this bot.")

# ============================================================
# MAIN
# ============================================================
def main():
    print("=" * 55)
    print("  EVALON VIP SIGNALS BOT v3")
    print("=" * 55)
    db = load_db()
    print(f"VIP Members : {sum(1 for u in db['users'].values() if u.get('vip'))}")
    print(f"Codes       : {len(db.get('codes', {}))}")
    print(f"Admin ID    : {ADMIN_ID}")
    print("\nBot starting...")
    print("=" * 55)

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",       start))
    app.add_handler(CommandHandler("help",        cmd_help))
    app.add_handler(CommandHandler("stats",       cmd_stats))
    app.add_handler(CommandHandler("broadcast",   broadcast))
    app.add_handler(CommandHandler("session",     session_cmd))
    app.add_handler(CommandHandler("end",         end_cmd))
    app.add_handler(CommandHandler("feedback",    feedback_cmd))
    app.add_handler(CommandHandler("setwelcome",  cmd_setwelcome))
    app.add_handler(CommandHandler("addcode",     cmd_addcode))
    app.add_handler(CommandHandler("addcodes",    cmd_addcodes))
    app.add_handler(CommandHandler("listcodes",   cmd_listcodes))
    app.add_handler(CommandHandler("vipusers",    cmd_vipusers))
    app.add_handler(CommandHandler("revoke",      cmd_revoke))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & filters.Sticker.ALL, handle_sticker
    ))
    app.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & (filters.PHOTO | filters.VIDEO | filters.ANIMATION),
        handle_media
    ))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.FORWARDED, protect_forward))

    print("Bot is running!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
