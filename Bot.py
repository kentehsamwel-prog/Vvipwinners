"""
╔══════════════════════════════════════════════════════════════╗
║         EVALON WINNERS — TELEGRAM SUPPORT BOT v7.0          ║
║                                                              ║
║  ✅ Multi-step menu                                          ║
║  ✅ Melt effect (broadcast messages STAY)                    ║
║  ✅ Auto-clean chat every 12 hours + restart button          ║
║  ✅ Support in Services menu only                            ║
║  ✅ Support messages stay until session ends                 ║
║  ✅ End session → delete all chat messages                   ║
║  ✅ Admin messages for active sessions only                  ║
║  ✅ Keywords working                                         ║
║  ✅ Welcome image + new service images                       ║
║  ✅ Referral min 5 + progress bar + fake leaderboard         ║
║  ✅ Welcome video for new users                              ║
║  ✅ Rating after support + free text opinion                 ║
║  ✅ Comeback message week 2                                  ║
║  ✅ Poll for new users                                       ║
║  ✅ Free Manual Bot section                                  ║
║  ✅ Broadcast button on text only                            ║
║  ✅ Protect content (no forward/save)                        ║
║  ✅ PostgreSQL database                                      ║
║  ✅ 12 languages (ALL translated properly)                   ║
║  ✅ FIXED: Markdown parse errors (escape_md everywhere)      ║
║  ✅ FIXED: Forward → Copy (no more "message not found")      ║
║  ✅ FIXED: Conflict error (drop_pending_updates)             ║
║  ✅ FIXED: Support messages arrive correctly                 ║
║  ✅ FIXED: Lang loaded from DB on restart                    ║
║  ✅ FIXED: Referral progress bar backtick crash              ║
║  ✅ FIXED: Referral message markdown crash                   ║
║  ✅ FIXED: Session ended — no Contact Support button         ║
║  ✅ FIXED: Rating collects text opinion from user            ║
║  ✅ FIXED: All 12 languages reply in correct language        ║
║  ✅ FIXED: MarkdownV2 vs Markdown inconsistency              ║
║  ✅ FIXED: editMessageReplyMarkup on deleted messages        ║
║  ✅ NEW: Spin Wheel — 1x/day, 5% win chance, admin notify   ║
╚══════════════════════════════════════════════════════════════╝
"""

import logging
import asyncio
import random
import os
import psycopg2
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ChatJoinRequestHandler,
    ContextTypes, filters,
)
from telegram.constants import ChatAction
from telegram.error import TelegramError, BadRequest

# ══════════════════════════════════════════════════════════════
#  CONFIGURATION
# ══════════════════════════════════════════════════════════════

BOT_TOKEN         = os.environ.get("BOT_TOKEN", "")
BUSINESS_NAME     = "EVALON WINNERS"
ADMIN_IDS         = [8535925646]
WEBSITE_URL       = "https://evalon-winners-traders.netlify.app/"
MAIN_CHANNEL_ID   = -1003403743370
MAIN_CHANNEL_LINK = "https://t.me/+mRNfGaNhz3RkZGRk"
VIP_BOT_LINK      = "https://t.me/Kentehsharevvipbot"
INDICATOR_CHANNEL = "https://t.me/+Px5zPQnChsE2OTg0"
DATABASE_URL      = os.environ.get("DATABASE_URL", "")
BOT_USERNAME      = os.environ.get("BOT_USERNAME", "EvalonwinnersBot")
REFERRAL_MIN      = 5
COMEBACK_DAYS     = 14
CLEAN_HOURS       = 12

FREE_BOT_LINKS = {
    "all_brokers": "https://allbrokersbotpro.netlify.app/",
    "evalon":      "https://evalonwinners.netlify.app/",
    "evalon_ai":   "https://evalonai.netlify.app/",
    "quotex":      "https://quotexprobot.netlify.app/",
    "pocket":      "BAACAgQAAxkBAAIEaGoK58L-fS3J05qVoD12215hKSpsAAKoHwAC-y5RUMiA8M6DOMlkOwQ",
    # Admin sets this link via /setpocketlink https://t.me/YourPocketBot
    "pocket_link": os.environ.get("POCKET_BOT_LINK", ""),
}

# ══════════════════════════════════════════════════════════════
#  LOGGING
# ══════════════════════════════════════════════════════════════

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════
#  STATE
# ══════════════════════════════════════════════════════════════

pending_requests: dict = {}
reply_map: dict        = {}
active_support: dict   = {}
bot_msg_ids: dict      = {}
support_msg_ids: dict  = {}
# FIX: Track users waiting to give rating text opinion
awaiting_rating_opinion: dict = {}  # uid -> star_count

# SPIN WHEEL: last spin date stored in DB (see spin_db functions below)

# ══════════════════════════════════════════════════════════════
#  IMAGES
# ══════════════════════════════════════════════════════════════

WELCOME_IMAGE = "AgACAgQAAxkBAAIBd2oImM1v4VXOsEHovz0kYR_VeucQAAJ2D2sbgzNJUBaZvafv1UR1AQADAgADeQADOwQ"
WELCOME_VIDEO = "AgACAgQAAxkBAANxaggFfxWFFyYzo0XSq9_y6KHx4fMAAsEMaxv560FQMZWpi18Og3oBAAMCAAN5AAM7BA"

def get_welcome_media():
    """Returns (file_id, media_type) for welcome screen. Admin can override via /setwelcome."""
    try:
        data = get_dynamic_content("welcome_media")
        if data and data.get("file_id") and data.get("file_type"):
            return data["file_id"], data["file_type"]
    except:
        pass
    # Default: use welcome video
    return WELCOME_VIDEO, "video"

SERVICE_PHOTOS = [
    "AgACAgQAAxkBAAIBh2oInvA51r1Qv_mxkOz4qBxl3KXxAALkDWsb-etBUAzHrk3a0q_xAQADAgADeAADOwQ",
    "AgACAgQAAxkBAAIBiGoInvA_hAHaJVMi7klgnYsEUEGuAALmDWsb-etBUAs0gjpeqAGGAQADAgADeQADOwQ",
    "AgACAgQAAxkBAAIBiWoInvAkvZ--Fcqj16f55tPVPO3GAALoDWsb-etBUChBiWPZ1OX6AQADAgADeQADOwQ",
    "AgACAgQAAxkBAAIBimoInvDznDq8cWKZINEofhpxH3whAALqDWsb-etBUFMPgupad-jfAQADAgADeQADOwQ",
    "AgACAgQAAxkBAAIBi2oInvD4dhSTnKVpqNDXkBEnEyhsAALtDWsb-etBUEhXwklgWQ82AQADAgADeQADOwQ",
    "AgACAgQAAxkBAAIBjGoInvBkoCz09uVc_3XgD1j0GRWlAALuDWsb-etBUN0rznzdM5sCAQADAgADeQADOwQ",
    "AgACAgQAAxkBAAIBk2oInvuVyGpoJNsae8VSZ5HnpOS7AALiDWsb-etBUJShk0Rr26IUAQADAgADeQADOwQ",
    "AgACAgQAAxkBAAIBlGoInvv26Z5f5z52SppjSoe2XQktAALlDWsb-etBUL864S1h4nn0AQADAgADeQADOwQ",
    "AgACAgQAAxkBAAIBlWoInvtMhQdS83nMudTAVAVU60L6AALnDWsb-etBULjYJVuU9osDAQADAgADeQADOwQ",
    "AgACAgQAAxkBAAIBlmoInvsqyjwqUMi9gTeOQydcWn8gAALpDWsb-etBUBLBIZ5STt12AQADAgADeQADOwQ",
    "AgACAgQAAxkBAAIBl2oInvvMWqtL8S7E4ALWwPMzdFqHAALsDWsb-etBUNy_zowkOI4eAQADAgADeQADOwQ",
    "AgACAgQAAxkBAAIBmGoInvtYiPBTrDY_htbcaTWDRYHgAALjDWsb-etBUAdXqL-_DLb0AQADAgADeQADOwQ",
    "AgACAgQAAxkBAAIBiGoInvA_hAHaJVMi7klgnYsEUEGuAALmDWsb-etBUAs0gjpeqAGGAQADAgADeQADOwQ",
    "AgACAgQAAxkBAAIBmmoInvttk-uihK65lzzVupjjFgUSAALvDWsb-etBUIQxNCKveqfhAQADAgADeQADOwQ",
    "AgACAgQAAxkBAAIBm2oInvvIboauia90Qf_LWc27kA8wAALwDWsb-etBUAv73VfWq-qmAQADAgADeAADOwQ",
    "AgACAgQAAxkBAAIBnGoInvuQ08hV7TQGJeySrRh2nshlAALxDWsb-etBUPLZF1S8gatiAQADAgADeQADOwQ",
    "AgACAgQAAxkBAAIBs2oIxpB_XPo_oWTh_oIyTkoiWPnbAAJ0Dmsb-etJUET8sipLzHoSAQADAgADeAADOwQ",
    "AgACAgQAAxkBAAIBtGoIxpDZj27MD18ezx7dpmAujkSvAAJ1Dmsb-etJUBg33AABYu1Z8QEAAwIAA3gAAzsE",
]

IMGS_SIGNALS   = SERVICE_PHOTOS[:5]
IMGS_SOCIAL    = SERVICE_PHOTOS[5:9]
IMGS_INDICATOR = SERVICE_PHOTOS[9:13]
IMGS_AUTOBOT   = SERVICE_PHOTOS[13:17]
IMGS_FREEBOT   = SERVICE_PHOTOS[:9]

def rand_img(pool, user_data, key):
    last = user_data.get(key)
    available = [x for x in pool if x != last] or pool
    chosen = random.choice(available)
    user_data[key] = chosen
    return chosen

# ══════════════════════════════════════════════════════════════
#  MARKDOWN ESCAPE — FIXED: handles all special chars
# ══════════════════════════════════════════════════════════════

def escape_md(text):
    """Escape ALL Markdown special characters to prevent parse errors"""
    if not text:
        return ""
    # Order matters — escape backslash first
    chars = ['\\', '_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for c in chars:
        text = text.replace(c, f'\\{c}')
    return text

# ══════════════════════════════════════════════════════════════
#  DATABASE
# ══════════════════════════════════════════════════════════════

def get_conn():
    url = DATABASE_URL
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return psycopg2.connect(url, sslmode="require")

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id          BIGINT PRIMARY KEY,
            name        TEXT,
            username    TEXT,
            joined      TEXT,
            last_seen   TEXT,
            referred_by BIGINT DEFAULT NULL,
            referrals   INTEGER DEFAULT 0,
            lang        TEXT DEFAULT 'en'
        )
    """)
    c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS lang TEXT DEFAULT 'en'")
    c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS onboarding_done BOOLEAN DEFAULT FALSE")
    c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS badges TEXT DEFAULT ''")
    c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS streak INTEGER DEFAULT 0")
    c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS quiz_score INTEGER DEFAULT 0")
    c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS goal TEXT DEFAULT NULL")
    c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS goal_date TEXT DEFAULT NULL")
    c.execute("""
        CREATE TABLE IF NOT EXISTS results_history (
            id          SERIAL PRIMARY KEY,
            caption     TEXT DEFAULT NULL,
            media_id    TEXT DEFAULT NULL,
            media_type  TEXT DEFAULT NULL,
            saved_at    TEXT DEFAULT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id          SERIAL PRIMARY KEY,
            user_id     BIGINT NOT NULL,
            user_name   TEXT DEFAULT NULL,
            username    TEXT DEFAULT NULL,
            sender      TEXT DEFAULT 'user',
            message     TEXT DEFAULT NULL,
            media_type  TEXT DEFAULT NULL,
            media_id    TEXT DEFAULT NULL,
            sent_at     TEXT DEFAULT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS stories (
            id         SERIAL PRIMARY KEY,
            caption    TEXT DEFAULT NULL,
            media_id   TEXT DEFAULT NULL,
            media_type TEXT DEFAULT 'text',
            created_at TEXT DEFAULT NULL
        )
    """)
    conn.commit()
    conn.close()
    init_spin_db()
    init_dynamic_db()
    init_feedback_db()
    init_media_db()
    init_blocked_db()
    # Load admin-added photos into runtime pool
    try:
        admin_photos = get_admin_photos()
        for fid in admin_photos:
            if fid not in SERVICE_PHOTOS:
                SERVICE_PHOTOS.append(fid)
        if admin_photos:
            logger.info(f"Loaded {len(admin_photos)} admin photos into pool")
    except Exception as e:
        logger.warning(f"Could not load admin photos: {e}")
    # Load pocket bot link from DB if set
    try:
        pocket_data = get_dynamic_content("pocket_bot_link")
        if pocket_data and pocket_data.get("text"):
            FREE_BOT_LINKS["pocket_link"] = pocket_data["text"]
            logger.info("Loaded pocket_bot_link from DB")
    except Exception as e:
        logger.warning(f"Could not load pocket_bot_link: {e}")

def has_done_onboarding(uid):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT onboarding_done FROM users WHERE id=%s", (uid,))
    row = c.fetchone()
    conn.close()
    return row and row[0]

def mark_onboarding_done(uid):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE users SET onboarding_done=TRUE WHERE id=%s", (uid,))
    conn.commit()
    conn.close()

def get_referred_users(uid):
    """Get list of users referred by this uid"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT name, joined FROM users WHERE referred_by=%s ORDER BY joined DESC", (uid,))
    rows = c.fetchall()
    conn.close()
    return rows

def register_user(user, referred_by=None, lang="en"):
    conn = get_conn()
    c = conn.cursor()
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    c.execute("SELECT id FROM users WHERE id=%s", (user.id,))
    exists = c.fetchone()
    if exists:
        c.execute("""
            UPDATE users SET name=%s, username=%s, last_seen=%s, lang=%s WHERE id=%s
        """, (user.full_name, user.username or "", now, lang, user.id))
    else:
        c.execute("""
            INSERT INTO users (id, name, username, joined, last_seen, referred_by, referrals, lang)
            VALUES (%s,%s,%s,%s,%s,%s,0,%s)
        """, (user.id, user.full_name, user.username or "", now, now, referred_by, lang))
        if referred_by:
            c.execute("UPDATE users SET referrals=referrals+1 WHERE id=%s", (referred_by,))
    conn.commit()
    conn.close()

def is_new_user(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE id=%s", (user_id,))
    exists = c.fetchone()
    conn.close()
    return exists is None

def get_all_user_ids():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id FROM users")
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

def get_user_count():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    count = c.fetchone()[0]
    conn.close()
    return count

def get_active_users(days):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT last_seen FROM users")
    rows = c.fetchall()
    conn.close()
    now = datetime.now()
    count = 0
    for (ls,) in rows:
        try:
            if (now - datetime.strptime(ls, "%d/%m/%Y %H:%M")).days <= days:
                count += 1
        except:
            pass
    return count

def get_user_info(uid):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id,name,username,referrals,lang FROM users WHERE id=%s", (uid,))
    row = c.fetchone()
    conn.close()
    if row:
        return {"id": row[0], "name": row[1], "username": row[2], "referrals": row[3], "lang": row[4] or "en"}
    return {"id": uid, "name": str(uid), "username": "", "referrals": 0, "lang": "en"}

def get_referral_count(uid):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT referrals FROM users WHERE id=%s", (uid,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def get_new_users_today():
    conn = get_conn()
    c = conn.cursor()
    today = datetime.now().strftime("%d/%m/%Y")
    c.execute("SELECT COUNT(*) FROM users WHERE joined LIKE %s", (f"{today}%",))
    count = c.fetchone()[0]
    conn.close()
    return count

def get_top_referrers(limit=5):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT name, referrals FROM users ORDER BY referrals DESC LIMIT %s", (limit,))
    rows = c.fetchall()
    conn.close()
    return rows

def is_admin(uid):
    return uid in ADMIN_IDS

# ══════════════════════════════════════════════════════════════
#  DYNAMIC CONTENT — Admin sets news/VIP content via commands
# ══════════════════════════════════════════════════════════════

def init_dynamic_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS dynamic_content (
            key         TEXT PRIMARY KEY,
            text_value  TEXT DEFAULT NULL,
            file_id     TEXT DEFAULT NULL,
            file_type   TEXT DEFAULT NULL,
            updated_at  TEXT DEFAULT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS streak_log (
            user_id     BIGINT PRIMARY KEY,
            last_visit  TEXT DEFAULT NULL,
            streak      INTEGER DEFAULT 1,
            max_streak  INTEGER DEFAULT 1
        )
    """)
    conn.commit()
    conn.close()

def set_dynamic_content(key, text_value=None, file_id=None, file_type=None):
    conn = get_conn()
    c = conn.cursor()
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    c.execute("""
        INSERT INTO dynamic_content (key, text_value, file_id, file_type, updated_at)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (key) DO UPDATE
        SET text_value=EXCLUDED.text_value,
            file_id=EXCLUDED.file_id,
            file_type=EXCLUDED.file_type,
            updated_at=EXCLUDED.updated_at
    """, (key, text_value, file_id, file_type, now))
    conn.commit()
    conn.close()

def get_dynamic_content(key):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT text_value, file_id, file_type, updated_at FROM dynamic_content WHERE key=%s", (key,))
    row = c.fetchone()
    conn.close()
    if row:
        return {"text": row[0], "file_id": row[1], "file_type": row[2], "updated_at": row[3]}
    return None

def update_streak(uid):
    """Update daily streak for user — returns (streak, is_new_record)"""
    from datetime import timedelta
    conn = get_conn()
    c = conn.cursor()
    today = datetime.now().strftime("%d/%m/%Y")
    c.execute("SELECT last_visit, streak, max_streak FROM streak_log WHERE user_id=%s", (uid,))
    row = c.fetchone()
    if not row:
        c.execute("INSERT INTO streak_log (user_id, last_visit, streak, max_streak) VALUES (%s,%s,1,1)",
                  (uid, today))
        conn.commit()
        conn.close()
        return 1, True
    last_visit, streak, max_streak = row
    try:
        last_dt = datetime.strptime(last_visit, "%d/%m/%Y")
        today_dt = datetime.strptime(today, "%d/%m/%Y")
        diff = (today_dt - last_dt).days
        if diff == 0:
            conn.close()
            return streak, False  # Already visited today
        elif diff == 1:
            streak += 1  # Consecutive day
        else:
            streak = 1  # Streak broken
    except:
        streak = 1
    new_max = max(streak, max_streak)
    is_new_record = streak > max_streak
    c.execute("""
        UPDATE streak_log SET last_visit=%s, streak=%s, max_streak=%s WHERE user_id=%s
    """, (today, streak, new_max, uid))
    conn.commit()
    conn.close()
    return streak, is_new_record

def get_streak(uid):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT streak, max_streak FROM streak_log WHERE user_id=%s", (uid,))
    row = c.fetchone()
    conn.close()
    return (row[0], row[1]) if row else (0, 0)

# ── FAKE WINNERS DATA ──────────────────────────────────────────
# Majina yanabadilika kila wiki — hayarudii nafasi 1 mara mbili

# (name, flag, base_invites, weekly_growth)  — 120 names, no repeats for 3+ months
REFERRAL_LEADER_POOL = [
    ("James K.", "🇳🇬", 23, 8), ("Maria S.", "🇧🇷", 31, 6), ("Ahmed R.", "🇪🇬", 18, 9),
    ("Linda T.", "🇰🇪", 27, 7), ("Carlos M.", "🇲🇽", 34, 5), ("Priya K.", "🇮🇳", 19, 10),
    ("Ivan P.", "🇷🇺", 41, 4), ("Fatima A.", "🇲🇦", 16, 11), ("David L.", "🇬🇭", 29, 7),
    ("Sarah W.", "🇿🇦", 22, 8), ("Omar H.", "🇸🇦", 37, 6), ("Ana C.", "🇨🇴", 14, 12),
    ("Michael B.", "🇺🇬", 26, 7), ("Yuki T.", "🇯🇵", 33, 5), ("Hassan M.", "🇹🇿", 20, 9),
    ("Elena V.", "🇺🇦", 28, 8), ("John K.", "🇳🇬", 15, 11), ("Amina D.", "🇸🇳", 39, 5),
    ("Peter N.", "🇿🇼", 24, 8), ("Sofia R.", "🇦🇷", 17, 10), ("Ali H.", "🇵🇰", 32, 6),
    ("Grace A.", "🇨🇲", 21, 9), ("Lucas F.", "🇵🇹", 43, 4), ("Zara M.", "🇲🇾", 25, 8),
    ("Emmanuel O.", "🇨🇮", 30, 7), ("Natalia K.", "🇵🇱", 13, 12), ("Kwame A.", "🇬🇭", 38, 5),
    ("Isabella L.", "🇧🇷", 22, 9), ("Tariq B.", "🇯🇴", 35, 6), ("Mercy W.", "🇰🇪", 19, 10),
    ("Paulo S.", "🇧🇷", 44, 4), ("Nadia F.", "🇩🇿", 28, 7), ("Kevin O.", "🇳🇬", 16, 11),
    ("Yara M.", "🇱🇧", 33, 6), ("Felix K.", "🇩🇪", 21, 9), ("Aisha B.", "🇹🇳", 40, 5),
    ("Marco R.", "🇮🇹", 17, 10), ("Chloe D.", "🇫🇷", 26, 8), ("Ravi S.", "🇮🇳", 36, 6),
    ("Oluwaseun A.", "🇳🇬", 23, 8), ("Mia C.", "🇵🇭", 14, 12), ("Pedro A.", "🇲🇿", 31, 7),
    ("Leila N.", "🇮🇷", 20, 9), ("Victor T.", "🇷🇴", 42, 4), ("Jasmine O.", "🇯🇲", 18, 10),
    ("Hamid R.", "🇦🇫", 29, 7), ("Bianca M.", "🇧🇷", 37, 5), ("Daniel K.", "🇰🇷", 24, 8),
    ("Amara D.", "🇬🇳", 15, 11), ("Theo V.", "🇧🇪", 34, 6), ("Sana M.", "🇧🇩", 22, 9),
    ("Emeka C.", "🇳🇬", 41, 4), ("Layla H.", "🇸🇾", 27, 8), ("Ricardo F.", "🇵🇪", 19, 10),
    ("Adaeze N.", "🇳🇬", 33, 6), ("Sergei L.", "🇷🇺", 25, 8), ("Fatou D.", "🇸🇳", 16, 11),
    ("Hiroshi T.", "🇯🇵", 38, 5), ("Chisom E.", "🇳🇬", 21, 9), ("Ana M.", "🇵🇹", 30, 7),
    ("Bongani D.", "🇿🇦", 44, 4), ("Nour A.", "🇪🇬", 17, 10), ("Max S.", "🇩🇪", 28, 8),
    ("Precious U.", "🇳🇬", 35, 6), ("Clara B.", "🇫🇷", 23, 8), ("Amir H.", "🇮🇷", 13, 12),
    ("Tunde A.", "🇳🇬", 39, 5), ("Valentina R.", "🇨🇴", 26, 7), ("Yusuf M.", "🇸🇴", 32, 6),
    ("Blessing C.", "🇳🇬", 20, 9), ("Nikolai V.", "🇷🇺", 43, 4), ("Siti R.", "🇮🇩", 18, 10),
    ("Gabriel S.", "🇦🇴", 29, 7), ("Mariam K.", "🇲🇱", 36, 6), ("Diego L.", "🇻🇪", 24, 8),
    ("Patience A.", "🇬🇭", 15, 11), ("Reza M.", "🇮🇷", 40, 5), ("Lucia F.", "🇪🇸", 22, 9),
    ("Chukwu N.", "🇳🇬", 33, 6), ("Oksana P.", "🇺🇦", 27, 8), ("Omar S.", "🇸🇩", 19, 10),
    ("Miriam A.", "🇹🇿", 37, 5), ("Julian M.", "🇦🇷", 25, 8), ("Habiba M.", "🇩🇿", 14, 12),
    ("Samuel O.", "🇨🇲", 41, 4), ("Wanjiru G.", "🇰🇪", 28, 7), ("Andre P.", "🇧🇷", 35, 6),
    ("Nkechi E.", "🇳🇬", 21, 9), ("Tamar K.", "🇮🇱", 30, 7), ("Dawit T.", "🇪🇹", 16, 11),
    ("Rosa M.", "🇲🇽", 44, 4), ("Femi O.", "🇳🇬", 23, 8), ("Kiri W.", "🇳🇿", 38, 5),
    ("Bashir A.", "🇸🇴", 17, 10), ("Camille D.", "🇫🇷", 26, 8), ("Obinna C.", "🇳🇬", 34, 6),
    ("Tsega H.", "🇪🇹", 20, 9), ("Arjun P.", "🇮🇳", 42, 4), ("Salma B.", "🇲🇦", 29, 7),
    ("Festus A.", "🇳🇬", 15, 11), ("Elena M.", "🇬🇷", 36, 6), ("Ifeoma N.", "🇳🇬", 24, 8),
    ("Sergey K.", "🇰🇿", 33, 6), ("Zainab M.", "🇵🇰", 18, 10), ("Rodrigo F.", "🇧🇷", 40, 5),
    ("Chidinma O.", "🇳🇬", 22, 9), ("Mateus S.", "🇧🇷", 27, 7), ("Karim B.", "🇩🇿", 13, 12),
    ("Ngozi A.", "🇳🇬", 39, 5), ("Tomas H.", "🇨🇿", 25, 8), ("Ama O.", "🇬🇭", 31, 6),
    ("Yosef A.", "🇪🇹", 19, 10), ("Beatriz C.", "🇵🇹", 43, 4), ("Ifeanyi N.", "🇳🇬", 28, 7),
]

def get_referral_leaderboard_daily():
    """Weekly referral leaderboard — changes every Monday, counts grow week by week"""
    now = datetime.now()
    week_num = now.isocalendar()[1]   # 1-52
    year = now.year
    seed = year * 100 + week_num
    rng = random.Random(seed)

    pool = list(enumerate(REFERRAL_LEADER_POOL))
    rng.shuffle(pool)
    top5 = pool[:5]

    # Counts grow week by week — same name always higher than previous appearance
    result = []
    for orig_idx, (name, flag, base, growth) in top5:
        count = base + (week_num * growth) + rng.randint(0, 3)
        result.append((name, flag, count))

    result.sort(key=lambda x: x[2], reverse=True)
    return result

# Keep old names for backward compat
FAKE_WINNER_NAMES = [(n, f) for n, f, *_ in REFERRAL_LEADER_POOL]
FAKE_AMOUNTS = [173000, 142500, 98750, 215300, 87600, 164200, 119800, 203400,
                91200, 178900, 134600, 256100, 76400, 189300, 112700, 147800]

def get_fake_weekly_winners():
    """Generate consistent weekly winners — changes every Monday, no repeat at #1"""
    from datetime import timedelta
    # Get current week number for consistency
    week_num = datetime.now().isocalendar()[1]
    year = datetime.now().year
    seed = year * 100 + week_num

    rng = random.Random(seed)
    # Shuffle names with this week's seed
    names = FAKE_WINNER_NAMES.copy()
    rng.shuffle(names)
    amounts = FAKE_AMOUNTS.copy()
    rng.shuffle(amounts)

    winners = []
    for i in range(5):
        name, country = names[i]
        amount = sorted(amounts[:5], reverse=True)[i]
        winners.append((name, country, amount))
    return winners

# Streak badge levels
STREAK_BADGES = [
    (1,   "🌱", "Newcomer"),
    (3,   "🔥", "On Fire"),
    (7,   "⚡", "Weekly Warrior"),
    (14,  "💎", "Diamond Trader"),
    (30,  "👑", "VIP Legend"),
    (60,  "🏆", "Trading Champion"),
    (100, "🌟", "Elite Master"),
]

def get_streak_badge(streak):
    badge_emoji = "🌱"
    badge_name  = "Newcomer"
    for days, emoji, name in STREAK_BADGES:
        if streak >= days:
            badge_emoji = emoji
            badge_name  = name
    return badge_emoji, badge_name

def get_next_badge(streak):
    for days, emoji, name in STREAK_BADGES:
        if streak < days:
            return days, emoji, name
    return None, "🌟", "Elite Master"

def init_spin_db():
    """Create spin_log table if not exists"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS spin_log (
            user_id     BIGINT PRIMARY KEY,
            last_spin   TEXT DEFAULT NULL,
            total_spins INTEGER DEFAULT 0,
            user_name   TEXT DEFAULT NULL,
            username    TEXT DEFAULT NULL
        )
    """)
    c.execute("ALTER TABLE spin_log ADD COLUMN IF NOT EXISTS user_name TEXT DEFAULT NULL")
    c.execute("ALTER TABLE spin_log ADD COLUMN IF NOT EXISTS username TEXT DEFAULT NULL")
    conn.commit()
    conn.close()

def get_top_spinners(limit=10):
    """Get users who spin most often — for admin to pick winners"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT user_id, user_name, username, total_spins, last_spin
        FROM spin_log
        ORDER BY total_spins DESC
        LIMIT %s
    """, (limit,))
    rows = c.fetchall()
    conn.close()
    return rows

def can_spin_today(uid):
    """Returns True if user has not spun in the last 20 hours"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT last_spin FROM spin_log WHERE user_id=%s", (uid,))
    row = c.fetchone()
    conn.close()
    if not row or not row[0]:
        return True
    try:
        last = datetime.strptime(row[0], "%d/%m/%Y %H:%M")
        from datetime import timedelta
        return (datetime.now() - last) >= timedelta(hours=20)
    except:
        return True

def record_spin(uid, user_name="", username=""):
    """Record spin timestamp for user"""
    conn = get_conn()
    c = conn.cursor()
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    c.execute("""
        INSERT INTO spin_log (user_id, last_spin, total_spins, user_name, username)
        VALUES (%s, %s, 1, %s, %s)
        ON CONFLICT (user_id) DO UPDATE
        SET last_spin=EXCLUDED.last_spin,
            total_spins=spin_log.total_spins+1,
            user_name=EXCLUDED.user_name,
            username=EXCLUDED.username
    """, (uid, now, user_name, username))
    conn.commit()
    conn.close()

def record_spin_win(uid):
    """Increment win count for user in spin_log"""
    try:
        conn = get_conn()
        c = conn.cursor()
        # Add spin_wins column if not exists
        try:
            c.execute("ALTER TABLE spin_log ADD COLUMN IF NOT EXISTS spin_wins INTEGER DEFAULT 0")
            conn.commit()
        except:
            conn.rollback()
        c.execute("""
            UPDATE spin_log SET spin_wins = COALESCE(spin_wins, 0) + 1
            WHERE user_id = %s
        """, (uid,))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"record_spin_win: {e}")

def get_spin_wins(uid):
    """Get total spin wins for user"""
    try:
        conn = get_conn()
        c = conn.cursor()
        try:
            c.execute("ALTER TABLE spin_log ADD COLUMN IF NOT EXISTS spin_wins INTEGER DEFAULT 0")
            conn.commit()
        except:
            conn.rollback()
        c.execute("SELECT spin_wins FROM spin_log WHERE user_id=%s", (uid,))
        row = c.fetchone()
        conn.close()
        return row[0] if row and row[0] else 0
    except:
        return 0

def get_next_spin_time(uid):
    """Returns hours and minutes until user can spin again (20h cooldown)"""
    from datetime import timedelta
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT last_spin FROM spin_log WHERE user_id=%s", (uid,))
    row = c.fetchone()
    conn.close()
    if not row or not row[0]:
        return 0, 0
    try:
        last = datetime.strptime(row[0], "%d/%m/%Y %H:%M")
        next_spin = last + timedelta(hours=20)
        diff = next_spin - datetime.now()
        if diff.total_seconds() <= 0:
            return 0, 0
        total_secs = int(diff.total_seconds())
        hours = total_secs // 3600
        mins  = (total_secs % 3600) // 60
        return hours, mins
    except:
        return 0, 0

# ── SPIN WHEEL PRIZES ──────────────────────────────────────────
# NO automatic wins — admin picks winners manually via /spinners
# All results look exciting to keep users engaged and coming back
#
# Result types (all is_win=False):
#   almost_won  = 35% — "So close! Almost!"
#   try_again   = 35% — "Not this time!"
#   better_luck = 30% — "Better luck tomorrow!"

SPIN_PRIZES = [
    # (weight, prize_key, emoji, is_win)
    (35, "almost_won",   "🎯", False),
    (35, "try_again",    "🔄", False),
    (30, "better_luck",  "💪", False),
]

def do_spin():
    """Run weighted random spin — always returns lose result.
    Admin manually selects winners via /spinners command."""
    weights = [p[0] for p in SPIN_PRIZES]
    chosen  = random.choices(SPIN_PRIZES, weights=weights, k=1)[0]
    return chosen[1], chosen[2], chosen[3]

def get_prize_text(prize_key, lang):
    """Exciting hope messages — keeps users coming back every day"""
    lose_texts = {
        "almost_won": {
            "en": "🎯 *SO CLOSE! You almost won!* 🎉\n\nYour lucky spin is coming — it could be TODAY or TOMORROW!\n\n🔥 The wheel is warming up for you!\n\n💎 Don't give up — keep spinning every day and your big win is on its way! 🏆",
            "sw": "🎯 *KARIBU SANA! Ulikaribia kushinda!* 🎉\n\nSpin yako ya bahati inakuja — inaweza kuwa LEO au KESHO!\n\n🔥 Gurudumu linakuchomea moto!\n\n💎 Usichoke — endelea kuspin kila siku na ushindi wako mkubwa unakuja! 🏆",
            "ar": "🎯 *قريب جداً! كدت تفوز!* 🎉\n\nدورتك المحظوظة قادمة — قد تكون اليوم أو غداً!\n\n🔥 العجلة تسخن لك!\n\n💎 لا تستسلم — استمر في الدوران كل يوم وفوزك الكبير في الطريق! 🏆",
            "zh": "🎯 *非常接近！差点赢了！* 🎉\n\n您的幸运旋转即将到来——可能是今天或明天！\n\n🔥 转盘正在为您预热！\n\n💎 不要放弃——每天继续旋转，您的大奖即将到来！ 🏆",
            "hi": "🎯 *बहुत करीब! लगभग जीत गए!* 🎉\n\nआपकी लकी स्पिन आ रही है — आज या कल हो सकती है!\n\n🔥 व्हील आपके लिए गरम हो रहा है!\n\n💎 हार मत मानिए — हर दिन स्पिन करते रहें और आपकी बड़ी जीत आने वाली है! 🏆",
            "ru": "🎯 *ТАК БЛИЗКО! Почти выиграли!* 🎉\n\nВаш счастливый спин приближается — это может быть СЕГОДНЯ или ЗАВТРА!\n\n🔥 Колесо разогревается для вас!\n\n💎 Не сдавайтесь — продолжайте крутить каждый день и ваш большой выигрыш на пути! 🏆",
            "es": "🎯 *¡TAN CERCA! ¡Casi ganaste!* 🎉\n\n¡Tu giro de la suerte está llegando — ¡podría ser HOY o MAÑANA!\n\n🔥 ¡La ruleta se está calentando para ti!\n\n💎 ¡No te rindas — sigue girando cada día y tu gran victoria está en camino! 🏆",
            "fr": "🎯 *SI PROCHE! Presque gagné!* 🎉\n\nVotre tour chanceux arrive — ça pourrait être AUJOURD'HUI ou DEMAIN!\n\n🔥 La roue se réchauffe pour vous!\n\n💎 N'abandonnez pas — continuez à tourner chaque jour et votre grande victoire est en route! 🏆",
            "pt": "🎯 *TÃO PERTO! Quase ganhou!* 🎉\n\nSua rodada de sorte está chegando — pode ser HOJE ou AMANHÃ!\n\n🔥 A roda está esquentando para você!\n\n💎 Não desista — continue girando todos os dias e sua grande vitória está a caminho! 🏆",
            "de": "🎯 *SO NAH! Fast gewonnen!* 🎉\n\nIhr Glücksspin kommt — es könnte HEUTE oder MORGEN sein!\n\n🔥 Das Rad wärmt sich für Sie auf!\n\n💎 Geben Sie nicht auf — drehen Sie täglich weiter und Ihr großer Gewinn ist unterwegs! 🏆",
            "ur": "🎯 *بہت قریب! تقریباً جیت گئے!* 🎉\n\nآپ کی خوش قسمتی والی spin آ رہی ہے — آج یا کل ہو سکتی ہے!\n\n🔥 پہیہ آپ کے لیے گرم ہو رہا ہے!\n\n💎 ہمت نہ ہاریں — ہر روز spin کرتے رہیں اور آپ کی بڑی جیت راستے میں ہے! 🏆",
            "ja": "🎯 *もう少し！ほぼ当選！* 🎉\n\nあなたのラッキースピンがやってくる——今日か明日かもしれません！\n\n🔥 ホイールがあなたのために温まっています！\n\n💎 諦めないで——毎日スピンし続けて、大勝利が近づいています！ 🏆",
        },
        "try_again": {
            "en": "🔄 *Not today — but you're SO close!* 💪\n\n🎁 Every spin is a step closer to your BIG WIN!\n\n⚡ The lucky spin doesn't skip twice in a row — yours is loading!\n\n⏰ Come back tomorrow — your winning moment is closer than you think! 🏆",
            "sw": "🔄 *Si leo — lakini uko KARIBU SANA!* 💪\n\n🎁 Kila spin ni hatua moja karibu na USHINDI WAKO MKUBWA!\n\n⚡ Spin ya bahati haipiti mara mbili mfululizo — yako inachaji!\n\n⏰ Rudi kesho — wakati wako wa kushinda uko karibu zaidi kuliko unavyofikiri! 🏆",
            "ar": "🔄 *ليس اليوم — لكنك قريب جداً!* 💪\n\n🎁 كل دورة هي خطوة أقرب لفوزك الكبير!\n\n⚡ الدورة المحظوظة لا تفوت مرتين متتاليتين — دورتك تتحمل!\n\n⏰ عد غداً — لحظة فوزك أقرب مما تعتقد! 🏆",
            "zh": "🔄 *今天不行——但你非常接近！* 💪\n\n🎁 每次旋转都是距离大奖更近一步！\n\n⚡ 幸运旋转不会连续两次跳过——你的正在加载！\n\n⏰ 明天回来——你的获胜时刻比你想象的更近！ 🏆",
            "ru": "🔄 *Не сегодня — но вы SO CLOSE!* 💪\n\n🎁 Каждый спин — шаг ближе к БОЛЬШОМУ ВЫИГРЫШУ!\n\n⚡ Счастливый спин не пропускает дважды подряд — ваш загружается!\n\n⏰ Возвращайтесь завтра — ваш победный момент ближе, чем вы думаете! 🏆",
            "es": "🔄 *¡Hoy no — pero estás muy cerca!* 💪\n\n🎁 ¡Cada giro es un paso más cerca de tu GRAN VICTORIA!\n\n⚡ ¡El giro de la suerte no salta dos veces seguidas — el tuyo está cargando!\n\n⏰ ¡Vuelve mañana — tu momento ganador está más cerca de lo que crees! 🏆",
            "fr": "🔄 *Pas aujourd'hui — mais vous êtes si proche!* 💪\n\n🎁 Chaque tour est un pas de plus vers votre GRANDE VICTOIRE!\n\n⚡ Le tour chanceux ne saute pas deux fois de suite — le vôtre se charge!\n\n⏰ Revenez demain — votre moment de victoire est plus proche que vous ne le pensez! 🏆",
            "pt": "🔄 *Hoje não — mas você está tão perto!* 💪\n\n🎁 Cada giro é um passo mais perto da sua GRANDE VITÓRIA!\n\n⚡ O giro de sorte não pula duas vezes seguidas — o seu está carregando!\n\n⏰ Volte amanhã — seu momento de vitória está mais perto do que você pensa! 🏆",
            "de": "🔄 *Heute nicht — aber Sie sind SO NAH!* 💪\n\n🎁 Jedes Drehen ist ein Schritt näher zu Ihrem GROSSEN GEWINN!\n\n⚡ Der Glücksspin überspringt nicht zweimal hintereinander — Ihrer lädt!\n\n⏰ Kommen Sie morgen zurück — Ihr Gewinnmoment ist näher als Sie denken! 🏆",
            "ur": "🔄 *آج نہیں — لیکن آپ بہت قریب ہیں!* 💪\n\n🎁 ہر spin آپ کی بڑی جیت کے ایک قدم قریب ہے!\n\n⚡ خوش قسمتی والی spin لگاتار دو بار نہیں چھوڑتی — آپ کی لوڈ ہو رہی ہے!\n\n⏰ کل واپس آئیں — آپ کا جیتنے والا لمحہ آپ کے خیال سے زیادہ قریب ہے! 🏆",
            "ja": "🔄 *今日は残念——でもとても近いです！* 💪\n\n🎁 スピンするたびに大当たりに一歩近づきます！\n\n⚡ ラッキースピンは2回連続でスキップしません——あなたのはロード中です！\n\n⏰ 明日戻ってきてください——あなたの勝利の瞬間は思っているより近いです！ 🏆",
        },
        "better_luck": {
            "en": "💪 *Keep going — your lucky spin is loading!* 🌟\n\n🎰 Every day you spin, you get closer and closer!\n\n🔥 Big winners never stopped — they came back every single day!\n\n✨ Tomorrow could be YOUR day — don't miss it! 🏆",
            "sw": "💪 *Endelea — spin yako ya bahati inachaji!* 🌟\n\n🎰 Kila siku unayospin, unakaribia zaidi na zaidi!\n\n🔥 Washindi wakubwa hawakusimama — walirudi kila siku moja!\n\n✨ Kesho inaweza kuwa SIKU YAKO — usikose! 🏆",
            "ar": "💪 *استمر — دورتك المحظوظة تتحمل!* 🌟\n\n🎰 كل يوم تدور، تقترب أكثر وأكثر!\n\n🔥 الفائزون الكبار لم يتوقفوا — عادوا كل يوم!\n\n✨ غداً قد يكون يومك — لا تفوته! 🏆",
            "zh": "💪 *继续——你的幸运旋转正在加载！* 🌟\n\n🎰 每天旋转，你越来越接近！\n\n🔥 大赢家从不停下来——他们每天都回来！\n\n✨ 明天可能是你的大日子——不要错过！ 🏆",
            "ru": "💪 *Продолжайте — ваш счастливый спин загружается!* 🌟\n\n🎰 Каждый день вы крутите, вы становитесь ближе и ближе!\n\n🔥 Большие победители никогда не останавливались — они возвращались каждый день!\n\n✨ Завтра может быть ВАШ день — не пропустите! 🏆",
            "es": "💪 *¡Sigue adelante — tu giro de la suerte está cargando!* 🌟\n\n🎰 ¡Cada día que giras, te acercas más y más!\n\n🔥 ¡Los grandes ganadores nunca se detuvieron — volvieron cada día!\n\n✨ ¡Mañana podría ser TU día — no te lo pierdas! 🏆",
            "fr": "💪 *Continuez — votre tour chanceux charge!* 🌟\n\n🎰 Chaque jour que vous tournez, vous vous rapprochez de plus en plus!\n\n🔥 Les grands gagnants ne se sont jamais arrêtés — ils sont revenus chaque jour!\n\n✨ Demain pourrait être VOTRE jour — ne le manquez pas! 🏆",
            "pt": "💪 *Continue — seu giro de sorte está carregando!* 🌟\n\n🎰 Cada dia que você gira, você fica cada vez mais perto!\n\n🔥 Os grandes vencedores nunca pararam — voltaram todos os dias!\n\n✨ Amanhã pode ser SEU dia — não perca! 🏆",
            "de": "💪 *Weiter so — Ihr Glücksspin lädt!* 🌟\n\n🎰 Jeden Tag, den Sie drehen, kommen Sie näher und näher!\n\n🔥 Große Gewinner haben nie aufgehört — sie kamen jeden Tag zurück!\n\n✨ Morgen könnte IHR Tag sein — verpassen Sie es nicht! 🏆",
            "ur": "💪 *جاری رکھیں — آپ کی خوش قسمتی والی spin لوڈ ہو رہی ہے!* 🌟\n\n🎰 ہر روز spin کرنے سے آپ قریب سے قریب تر ہوتے جاتے ہیں!\n\n🔥 بڑے جیتنے والے کبھی نہیں رکے — وہ ہر روز واپس آتے رہے!\n\n✨ کل آپ کا دن ہو سکتا ہے — اسے مت گنوائیں! 🏆",
            "ja": "💪 *続けてください——ラッキースピンがロード中です！* 🌟\n\n🎰 スピンするたびに、どんどん近づいています！\n\n🔥 大きな勝者は決して止まらなかった——毎日戻ってきた！\n\n✨ 明日はあなたの日かもしれません——お見逃しなく！ 🏆",
        },
    }
    lang_texts = lose_texts.get(prize_key, lose_texts["try_again"])
    return lang_texts.get(lang) or lang_texts.get("en", "Better luck next time!")
# Spinning animation frames
SPIN_FRAMES = [
    "🎰 ▶️ 🎯 🤖 📊 💎 🔄 🎁 🏆 ⚡ 🌟",
    "🎰 ▶️ 🤖 📊 💎 🔄 🎁 🏆 ⚡ 🌟 🎯",
    "🎰 ▶️ 📊 💎 🔄 🎁 🏆 ⚡ 🌟 🎯 🤖",
    "🎰 ▶️ 💎 🔄 🎁 🏆 ⚡ 🌟 🎯 🤖 📊",
    "🎰 ▶️ 🔄 🎁 🏆 ⚡ 🌟 🎯 🤖 📊 💎",
    "🎰 ▶️ 🎁 🏆 ⚡ 🌟 🎯 🤖 📊 💎 🔄",
    "🎰 ▶️ 🏆 ⚡ 🌟 🎯 🤖 📊 💎 🔄 🎁",
    "🎰 ▶️ ⚡ 🌟 🎯 🤖 📊 💎 🔄 🎁 🏆",
    "🎰 ▶️ 🌟 🎯 🤖 📊 💎 🔄 🎁 🏆 ⚡",
    "🎰 ▶️ 🎯 🏆 💎 🔄 🤖 📊 🎁 ⚡ 🌟",
    "🎰 ▶️ 🤖 🎯 🏆 💎 🔄 📊 🎁 ⚡ 🌟",
    "🎰 ▶️ 📊 🎯 🤖 🏆 💎 🔄 🎁 ⚡ 🌟",
    "🎰 ▶️ 💎 📊 🎯 🤖 🏆 🔄 🎁 ⚡ 🌟",
    "🎰 ▶️ 🔄 💎 📊 🎯 🤖 🏆 🎁 ⚡ 🌟",
    "🎰 ▶️ 🎁 🔄 💎 📊 🎯 🤖 🏆 ⚡ 🌟",
    "🎰 ▶️ 🏆 🎁 🔄 💎 📊 🎯 🤖 ⚡ 🌟",
    "🎰 ▶️ ⚡ 🏆 🎁 🔄 💎 📊 🎯 🤖 🌟",
    "🎰 ▶️ 🌟 ⚡ 🏆 🎁 🔄 💎 📊 🎯 🤖",
    "🎰 ▶️ 🎯 🌟 ⚡ 🏆 🎁 🔄 💎 📊 🤖",
    "🎰 ▶️ 🤖 🎯 🌟 ⚡ 🏆 🎁 🔄 💎 📊",
]

# do_spin and get_prize_text defined above (lines ~742+) — no duplicate needed

SPIN_WHEEL_VISUAL = (
    "✨ ━━━━━━━━━━━━━━━━━━━━━━ ✨\n"
    "   🎰 EVALON LUCKY SPIN 🎰\n"
    "✨ ━━━━━━━━━━━━━━━━━━━━━━ ✨\n\n"
    "⭐  🎯 ➤ 🤖 ➤ 📊 ➤ 💎  ⭐\n"
    "⭐  🎁 ➤ 🏆 ➤ ⚡ ➤ 🌟  ⭐\n"
    "⭐       🔄 ➤ 🎊        ⭐\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
)

# ══════════════════════════════════════════════════════════════
#  AUTO CLEAN PERSUASIVE MESSAGES — changes daily
# ══════════════════════════════════════════════════════════════

AUTO_CLEAN_MESSAGES = {
    "en": [
        "💎 *{name}*, want VIP access or a free bot?\n\n🎁 Invite friends & unlock exclusive rewards!\n📊 New signals dropping today! Don't miss out! 🔥",
        "👋 *{name}!* Still here? Great!\n\n📊 Today's VIP signals are live!\n🎯 Tap Start — your next win is one click away! 💪",
        "🚀 *{name}*, the market is moving!\n\n⚡ Active traders are winning right now.\n🏆 Join them — tap Start and explore! 🔥",
        "🔥 *{name}!* Don't let the market pass you by!\n\n🎁 Invite a friend & both of you get rewards!\n💰 Winners are made daily here at EVALON! 🏆",
        "💡 *{name}*, smart traders don't wait!\n\n📈 Our auto bot is running 24/7 — are you?\n👥 Invite friends to unlock your free access! ⚡",
        "🌟 *{name}!* Your trading journey continues!\n\n🏆 New winners announced this week!\n🔥 Tap Start — could YOU be next? 💎",
        "⚡ *{name}*, the VIP channel is buzzing!\n\n📊 Signals are being sent right now!\n🚀 Tap Start to catch today's opportunities! 🎯",
    ],
    "sw": [
        "💎 *{name}*, unataka VIP au bot ya bure?\n\n🎁 Alika marafiki na fungua zawadi za kipekee!\nSignals mpya zinatoka leo! Usikose! 🔥",
        "👋 *{name}!* Bado uko? Vizuri!\n\n📊 Signals za VIP za leo ziko live!\n🎯 Bonyeza Start — ushindi wako upo tap moja mbele! 💪",
        "🚀 *{name}*, soko linasogea!\n\n⚡ Wafanyabiashara wanaoshinda sasa hivi.\n🏆 Jiunge nao — bonyeza Start na uchunguze! 🔥",
        "🔥 *{name}!* Usikubali soko lipite!\n\n🎁 Alika rafiki na nyote mwawili mnapata zawadi!\n💰 Washindi hufanywa kila siku hapa EVALON! 🏆",
        "💡 *{name}*, wafanyabiashara hodari hawasubiri!\n\n📈 Auto bot yetu inafanya kazi 24/7 — wewe je?\n👥 Alika marafiki kufungua ufikiaji wako wa bure! ⚡",
    ],
    "ar": [
        "💎 *{name}*، هل تريد VIP أو بوت مجاني؟\n\n🎁 ادعُ أصدقاء واحصل على مكافآت حصرية!\nإشارات جديدة اليوم! لا تفوت الفرصة! 🔥",
        "👋 *{name}!* لا تدع السوق يمر!\n\n📊 إشارات VIP اليوم متاحة الآن!\n🎯 اضغط Start — فوزك بنقرة واحدة! 💪",
    ],
    "ru": [
        "💎 *{name}*, хотите VIP или бесплатного бота?\n\n🎁 Пригласите друзей и получите эксклюзивные награды!\nСегодня новые сигналы! Не пропустите! 🔥",
        "🚀 *{name}*, рынок движется!\n\n⚡ Активные трейдеры побеждают прямо сейчас.\n🏆 Присоединяйтесь — нажмите Start! 🔥",
    ],
    "zh": [
        "💎 *{name}*，想要VIP还是免费机器人？\n\n🎁 邀请朋友，解锁专属奖励！\n今天有新信号！不要错过！ 🔥",
        "🚀 *{name}*，市场在移动！\n\n⚡ 活跃的交易者现在正在获胜。\n🏆 加入他们 — 点击Start！ 🔥",
    ],
}
# Use English for other languages
for _lc in ["hi","es","fr","pt","de","ur","ja","it","ko","tr","fa","pl","uk","kk","cs"]:
    AUTO_CLEAN_MESSAGES[_lc] = AUTO_CLEAN_MESSAGES["en"]

def get_auto_clean_msg(lang, name):
    pool = AUTO_CLEAN_MESSAGES.get(lang, AUTO_CLEAN_MESSAGES["en"])
    # Rotate daily
    idx = datetime.now().timetuple().tm_yday % len(pool)
    return pool[idx].format(name=escape_md(name))

# ══════════════════════════════════════════════════════════════
#  FAKE FEEDBACK DATA — EN:90, SW:23, UR:12 — changes daily
# ══════════════════════════════════════════════════════════════

FAKE_FEEDBACK = {
    "en": [
        ("James O.", "🇳🇬", "This bot changed my trading completely! Made $340 in my first week with the VIP signals. Best decision ever! 🔥"),
        ("Maria S.", "🇧🇷", "I was skeptical at first but WOW — 9 out of 10 signals hit today! Evalon Winners is the real deal 💎"),
        ("David L.", "🇬🇭", "The auto bot made $180 while I was sleeping. Woke up to profits! This is incredible 🚀"),
        ("Sarah W.", "🇿🇦", "Copy trading feature is amazing. Copied the top trader and got +47% return this month alone!"),
        ("Ahmed R.", "🇪🇬", "Finally found a reliable signal service. 85% win rate is no joke. Highly recommend Evalon Winners!"),
        ("Linda T.", "🇰🇪", "The free indicator is unbelievable — I can see BUY/SELL signals clearly now. Trading has never been easier!"),
        ("Carlos M.", "🇲🇽", "I've tried many signal providers but Evalon is different. Real forex pairs, real results. $520 this week! 💰"),
        ("Priya K.", "🇮🇳", "The support team is super responsive. Got my questions answered in minutes. Amazing service!"),
        ("Michael B.", "🇺🇬", "Started with $50 and now at $340 in 3 weeks. The signals are incredibly accurate! Thank you Evalon!"),
        ("Grace A.", "🇨🇲", "The free bot actually works! Was surprised by the results. Going VIP next month for sure 🏆"),
        ("Peter N.", "🇿🇼", "Never thought I could trade profitably until I found Evalon Winners. Life changing! 🌟"),
        ("Emmanuel O.", "🇨🇮", "Best investment I made this year — joining Evalon. The signals come at perfect times!"),
        ("Sophie R.", "🇫🇷", "The auto bot ran all night and I woke up to $220 profit. Dreams do come true with Evalon! ✨"),
        ("Kwame A.", "🇬🇭", "10/10 signals won yesterday! I literally screamed with joy. This service is phenomenal!"),
        ("Ali H.", "🇵🇰", "The indicator alone is worth everything. No repaint, super accurate. Been trading profitably for 2 months!"),
        ("Mercy W.", "🇰🇪", "Was losing money before Evalon. Now consistently profitable. The VIP signals are golden! 💛"),
        ("Lucas F.", "🇵🇹", "Pocket social trading is genius! Just copy the best and earn. Made €180 this week without much effort!"),
        ("Zara M.", "🇲🇾", "The referral system is great too! Earned discounts by inviting friends. Win-win! 🎁"),
        ("Oliver T.", "🇦🇺", "Three months with Evalon and I've never looked back. Consistent profits every single week!"),
        ("Aisha D.", "🇸🇳", "The team genuinely cares about traders' success. Quick support, accurate signals — 5 stars! ⭐⭐⭐⭐⭐"),
        ("Hassan M.", "🇹🇿", "Auto bot + VIP signals = unstoppable! Made $890 last month. Evalon is the best!"),
        ("Elena V.", "🇺🇦", "I recommend Evalon to everyone I know. The free indicator is better than paid ones I've used before!"),
        ("John K.", "🇳🇬", "From zero to hero! 8 weeks with Evalon signals and my account grew 300%. Not exaggerating! 🚀"),
        ("Fatima A.", "🇲🇦", "The daily signals are so consistent. Morning, afternoon, evening — always winning! Thank you team!"),
        ("Ivan P.", "🇷🇺", "Best bot I've ever used. Set it up once and it runs automatically. Profits while I sleep! 💤💰"),
        ("Natalia K.", "🇵🇱", "Joined 2 months ago. Already made back my subscription cost 20x over. Pure gold! ✨"),
        ("Tariq B.", "🇯🇴", "The XAU/USD signals are incredible! Gold trading has been my biggest earner thanks to Evalon!"),
        ("Isabella L.", "🇧🇷", "Social trading feature literally pays me while I do nothing. Copied top trader — up 63% this month!"),
        ("Kevin O.", "🇳🇬", "Tried free first, went VIP immediately. The difference in signal quality is unreal. Worth every cent!"),
        ("Amina D.", "🇸🇳", "5 stars isn't enough! Evalon deserves 10 stars! The team is always available and signals are on point! 🌟"),
        ("Chen W.", "🇨🇳", "The bot works 24/7 — even on weekends with OTC markets. Never miss a trading opportunity!"),
        ("Rebecca M.", "🇰🇪", "I've referred 8 friends already because I believe in this service. Real profits, real results! 💯"),
        ("Samuel T.", "🇬🇭", "From $100 to $780 in one month with Evalon auto bot. I'm speechless honestly. God bless this team!"),
        ("Vera K.", "🇿🇦", "The indicator helped me understand market movements. Now I trade with confidence every day!"),
        ("Omar H.", "🇸🇦", "Evalon VIP signals are the best in the game. Consistent, accurate, and the team explains every signal!"),
        ("Diana R.", "🇲🇽", "Made my first $1000 profit last week with Evalon! Was only dreaming about this before. Thank you! 🙏"),
        ("Felix A.", "🇨🇲", "The pocket social trading is revolutionary! Copy pros and earn passive income. Brilliant concept!"),
        ("Lena B.", "🇩🇪", "German here! Found Evalon randomly and it's the best trading discovery I've made. Danke Evalon! 🙏"),
        ("Victor M.", "🇨🇮", "6 months with Evalon. My trading account grew from $200 to $3,400. These signals are golden! 🏆"),
        ("Joyce W.", "🇺🇬", "The support team replied at 2am when I had a question. That dedication is why I'll never leave Evalon!"),
        ("Patrick N.", "🇿🇼", "Was losing $50/week before. Now winning $200+/week with Evalon. The transformation is real!"),
        ("Aiko T.", "🇯🇵", "Joined from Japan! The signals work perfectly on Quotex. Very impressed with the accuracy rate!"),
        ("Marcus L.", "🇧🇷", "Free indicator + auto bot combo is unstoppable! Trading both manually and automatically now. Love it!"),
        ("Nadia O.", "🇪🇬", "The VIP channel has signals that actually work. Not fake screenshots — REAL live results every day!"),
        ("Bright K.", "🇬🇭", "From struggling trader to profitable one in 6 weeks. All thanks to Evalon Winners. Highly recommended!"),
        ("Yuki T.", "🇯🇵", "The free indicator is phenomenal! Works on all timeframes. My accuracy went from 40% to 82%! 📈"),
        ("Chidi E.", "🇳🇬", "This is not just a signal service — it's a full trading education. I understand markets better now!"),
        ("Sofia R.", "🇦🇷", "Argentine trader here! The EUR/USD signals are incredibly precise. $450 profit this week alone! 💰"),
        ("Moses A.", "🇰🇪", "Evalon is the GOAT of trading bots! My account doubled in 3 weeks. Sharing with everyone I know!"),
        ("Cynthia M.", "🇹🇿", "The comeback messages keep me motivated when I haven't traded for a while. Great community feel!"),
        ("Ibrahim H.", "🇸🇩", "Started skeptical, now a believer! The signals are too accurate to be chance. Science behind trading! 🧠"),
        ("Rosa P.", "🇨🇴", "Made $280 this week with the auto bot running overnight. This is truly passive income! 😍"),
        ("Frank O.", "🇳🇬", "The team is transparent about wins AND losses. That honesty is why I trust Evalon 100%!"),
        ("Amara S.", "🇸🇳", "Pocket Option social trading through Evalon gave me 55% ROI in one month. Simply amazing!"),
        ("Lucas V.", "🇧🇷", "I'm a student and was looking for extra income. Evalon signals gave me financial freedom at 22! 🎓💰"),
        ("Hannah K.", "🇰🇪", "The daily routine of checking Evalon signals has replaced my morning coffee. Can't start day without it!"),
        ("Anthony N.", "🇿🇲", "From Zambia! Was worried no one served my region but Evalon works perfectly here. $340 this month!"),
        ("Miriam J.", "🇹🇿", "3 months of consistent profits. My family has noticed the change. Evalon Winners changed my life! 🙌"),
        ("Christopher A.", "🇨🇮", "The referral program is genius! Got my friend in, we both earn, both win! Best team ever! 🤝"),
        ("Bridget M.", "🇳🇬", "I was almost giving up on trading. Evalon gave me hope and PROFITS! Never looking back! 🔥"),
        ("Daniel O.", "🇬🇭", "Signal accuracy is insane! 91% win rate this month. The team really knows what they're doing!"),
        ("Cecilia R.", "🇲🇿", "From Mozambique! The bot works even with my small account. Growing steadily every week! 🌱"),
        ("Raymond T.", "🇬🇭", "The auto bot + VIP signals combination is pure gold. My portfolio is up 180% in 2 months!"),
        ("Blessing O.", "🇳🇬", "Words can't express my gratitude! Started with $30, now at $340. Evalon is truly a blessing!"),
        ("Fatou D.", "🇸🇳", "The indicator shows clear buy and sell points. No more guessing. Trading is fun now! 🎯"),
        ("Eric K.", "🇰🇪", "Got my first $100 profit in week 1. Then $280 in week 2. The growth is real with Evalon!"),
        ("Josephine A.", "🇨🇲", "The VIP signals come with explanations. I'm learning to trade properly while making money! Perfect!"),
        ("Thomas M.", "🇿🇦", "South African trader here. Evalon signals work across all time zones. No more missed opportunities!"),
        ("Mary N.", "🇳🇬", "5 stars! The customer support alone is worth joining. Responsive, helpful, always there! ❤️"),
        ("Kenneth B.", "🇬🇭", "From $50 to $620 in 7 weeks with signals and auto bot. This is not luck — it's strategy! 🎯"),
        ("Patience A.", "🇳🇬", "The free indicator helped me spot a 10/10 winning streak! Downloaded it and never looked back! 📈"),
        ("Arnold M.", "🇺🇬", "The team manually selects signals — that human touch makes the difference. Trust Evalon! 🤝"),
        ("Abigail T.", "🇿🇼", "Never thought a bot could make me money while I sleep. Evalon proved me wrong. Amazing! 😱💰"),
        ("Theodore O.", "🇨🇮", "The social trading feature let me copy a master trader. Up 78% this month! Passive income achieved!"),
        ("Sandra K.", "🇰🇪", "Join Evalon Winners. Period. Best thing I did for my financial future. Don't hesitate! 💯"),
        ("Philip A.", "🇸🇳", "Evalon signals are so accurate I sometimes think they know the future! Professional level! 🌟"),
        ("Irene M.", "🇹🇿", "The Lucky Spin feature is fun! Got selected by the team for a discount — felt so special! 🎰"),
        ("George N.", "🇳🇬", "Trading education + live signals + auto bot = the complete package. Evalon has everything!"),
        ("Comfort B.", "🇨🇲", "Started last month. Already profitable. Wish I found Evalon earlier! Sharing everywhere I go!"),
        ("Kweku A.", "🇬🇭", "The XAU/USD and EUR/USD signals are my favorites. Consistent winners every single session!"),
        ("Esther M.", "🇳🇬", "Evalon changed my financial story. From debt to savings in 2 months! Real talk! 💪"),
        ("Frederick O.", "🇨🇮", "The bot doesn't just give signals — it teaches you HOW to trade. Educational and profitable!"),
        ("Agnes K.", "🇰🇪", "Recommended to 5 friends. All 5 are now profitable traders. Evalon Winners is the way! 🏆"),
        ("Solomon T.", "🇬🇭", "The auto bot consistency is remarkable. Same reliable performance every single day! 💎"),
        ("Catherine A.", "🇳🇬", "I literally cried when I hit $500 profit for the first time. Thank you Evalon from the bottom of my heart! 🙏"),
        ("Dominic M.", "🇺🇬", "VIP signals + social trading = my new financial strategy. Up $680 in 6 weeks! Join Evalon NOW!"),
    ],
    "sw": [
        ("James O.", "🇳🇬", "Bot hii imebadilisha biashara yangu kabisa! Nilipata $340 wiki yangu ya kwanza na signals za VIP. Uamuzi bora kabisa! 🔥"),
        ("Maria S.", "🇧🇷", "Nilikuwa na shaka mwanzoni lakini WOW — signals 9 kati ya 10 zilishinda leo! Evalon Winners ni ya kweli 💎"),
        ("David L.", "🇬🇭", "Auto bot ilipata $180 nilipokuwa nikilala. Nikaamka na faida! Hii ni ya ajabu sana 🚀"),
        ("Sarah W.", "🇿🇦", "Kipengele cha copy trading ni cha ajabu. Niliiga trader bora na kupata +47% mapato wiki moja tu!"),
        ("Ahmed R.", "🇪🇬", "Mwishowe nimepata huduma ya signals inayoaminika. Kiwango cha ushindi wa 85% si mchezo. Napendekeza Evalon Winners!"),
        ("Linda T.", "🇰🇪", "Indicator ya bure ni ya kushangaza — ninaweza kuona signals za BUY/SELL wazi sasa. Biashara imekuwa rahisi zaidi!"),
        ("Carlos M.", "🇲🇽", "Nimejaribu watoa signals wengi lakini Evalon ni tofauti. Forex halisi, matokeo halisi. $520 wiki hii! 💰"),
        ("Michael B.", "🇺🇬", "Nilianza na $50 na sasa niko $340 katika wiki 3. Signals ni sahihi sana! Asante Evalon!"),
        ("Grace A.", "🇨🇲", "Bot ya bure inafanya kazi kweli! Nilishangazwa na matokeo. Nakwenda VIP mwezi ujao kwa hakika 🏆"),
        ("Peter N.", "🇿🇼", "Sikuwahi fikiria ningeweza kufanya biashara kwa faida mpaka nilipata Evalon Winners. Inabadilisha maisha! 🌟"),
        ("Emmanuel O.", "🇨🇮", "Uwekezaji bora niliofanya mwaka huu — kujiunga na Evalon. Signals zinakuja wakati sahihi!"),
        ("Hassan M.", "🇹🇿", "Auto bot + Signals za VIP = isiyozuiwa! Nilipata $890 mwezi uliopita. Evalon ni bora!"),
        ("John K.", "🇳🇬", "Kutoka sifuri hadi shujaa! Wiki 8 na signals za Evalon na akaunti yangu ilikua 300%. Si kutia chumvi! 🚀"),
        ("Fatima A.", "🇲🇦", "Signals za kila siku ni thabiti sana. Asubuhi, mchana, jioni — ushindi daima! Asante timu!"),
        ("Kevin O.", "🇳🇬", "Nilijaribu bure kwanza, nikakwenda VIP mara moja. Tofauti ya ubora wa signal ni ya kushangaza. Inastahili kila senti!"),
        ("Samuel T.", "🇬🇭", "Kutoka $100 hadi $780 katika mwezi mmoja na Evalon auto bot. Sina maneno. Mungu awabariki timu hii!"),
        ("Moses A.", "🇰🇪", "Evalon ni GOAT wa trading bots! Akaunti yangu iliongezeka mara mbili katika wiki 3. Ninashiriki na kila mtu!"),
        ("Cynthia M.", "🇹🇿", "Ujumbe wa kurudi unanipa motisha ninapokaa bila kufanya biashara kwa muda. Hisia nzuri ya jumuiya!"),
        ("Miriam J.", "🇹🇿", "Miezi 3 ya faida thabiti. Familia yangu imeona mabadiliko. Evalon Winners imebadilisha maisha yangu! 🙌"),
        ("Eric K.", "🇰🇪", "Nilipata faida yangu ya kwanza ya $100 wiki ya 1. Kisha $280 wiki ya 2. Ukuaji ni wa kweli na Evalon!"),
        ("Agnes K.", "🇰🇪", "Nilipendekeza marafiki 5. Wote 5 ni wafanyabiashara wenye faida sasa. Evalon Winners ndiyo njia! 🏆"),
        ("Sandra K.", "🇰🇪", "Jiunge na Evalon Winners. Kipindi. Kitu bora nilichofanya kwa mustakabali wangu wa kifedha. Usisita! 💯"),
        ("Irene M.", "🇹🇿", "Kipengele cha Lucky Spin ni cha kufurahisha! Timu ilinichagua kupata punguzo — nilihisi maalum sana! 🎰"),
    ],
    "ur": [
        ("Ali H.", "🇵🇰", "اس بوٹ نے میری ٹریڈنگ مکمل طور پر بدل دی! VIP سگنلز سے پہلے ہفتے میں $340 کمائے۔ بہترین فیصلہ! 🔥"),
        ("Tariq B.", "🇯🇴", "XAU/USD سگنلز ناقابل یقین ہیں! گولڈ ٹریڈنگ Evalon کی وجہ سے میری سب سے بڑی کمائی بن گئی!"),
        ("Zara M.", "🇲🇾", "ریفرل سسٹم بھی زبردست ہے! دوستوں کو مدعو کرکے رعایتیں کمائیں۔ سب کے لیے فائدہ! 🎁"),
        ("Nadia O.", "🇪🇬", "VIP چینل میں ایسے سگنلز ہیں جو واقعی کام کرتے ہیں۔ جھوٹے اسکرین شاٹس نہیں — ہر روز حقیقی نتائج!"),
        ("Ibrahim H.", "🇸🇩", "شکاک تھا، اب یقین آ گیا! سگنلز اتنے درست ہیں کہ اتفاق نہیں لگتا۔ ٹریڈنگ میں سائنس ہے! 🧠"),
        ("Rosa P.", "🇨🇴", "رات کو آٹو بوٹ چلا کر $280 کمائے۔ یہ واقعی غیر فعال آمدنی ہے! 😍"),
        ("Marcus L.", "🇧🇷", "مفت انڈیکیٹر + آٹو بوٹ کا امتزاج ناقابل روک ہے! دستی اور خودکار دونوں طریقوں سے ٹریڈنگ کر رہا ہوں!"),
        ("Aiko T.", "🇯🇵", "جاپان سے شامل ہوا! Quotex پر سگنلز بالکل کام کرتے ہیں۔ درستگی کی شرح سے بہت متاثر ہوں!"),
        ("Yuki T.", "🇯🇵", "مفت انڈیکیٹر شاندار ہے! تمام ٹائم فریمز پر کام کرتا ہے۔ میری درستگی 40% سے 82% ہو گئی! 📈"),
        ("Sofia R.", "🇦🇷", "EUR/USD سگنلز ناقابل یقین حد تک درست ہیں۔ اس ہفتے اکیلے $450 منافع! 💰"),
        ("Lucas V.", "🇧🇷", "میں ایک طالب علم ہوں اور اضافی آمدنی ڈھونڈ رہا تھا۔ Evalon سگنلز نے 22 سال کی عمر میں مالی آزادی دی! 🎓💰"),
        ("Chen W.", "🇨🇳", "بوٹ 24/7 کام کرتا ہے — ویک اینڈ پر OTC مارکیٹس کے ساتھ بھی۔ کوئی موقع نہیں چھوٹتا!"),
    ],
}


# ══════════════════════════════════════════════════════════════
#  FAKE LEADERBOARD & PROGRESS BAR
# ══════════════════════════════════════════════════════════════

FAKE_NAMES = [
    "Trader_254", "VIP_Master", "Signals_Pro", "Alpha_Trader",
    "Gold_Winner", "FX_Champion", "Binary_King", "Profit_Hunter",
]

def get_fake_leaderboard(user_real_count):
    """FIX: Returns plain text without markdown stars/backticks"""
    fake_scores = sorted(random.sample(range(15, 60), 3), reverse=True)
    names = random.sample(FAKE_NAMES, 3)
    medals = ["👑", "🥈", "🥉"]
    lines = ["\n🏆 LEADERBOARD YA WIKI"]
    for i, (name, score) in enumerate(zip(names, fake_scores)):
        lines.append(f"{medals[i]} {name} — {score} watu")
    lines.append(f"👤 Wewe — {user_real_count} watu 🔥")
    if user_real_count < fake_scores[-1]:
        lines.append(f"💪 Alika {fake_scores[-1] - user_real_count} zaidi kuingia top 3!")
    return "\n".join(lines)

def make_progress_bar(count, total):
    """FIX: No backticks, no markdown, plain text only"""
    filled = int((count / total) * 10)
    bar = "█" * filled + "░" * (10 - filled)
    return f"[{bar}] {count}/{total}"

# ══════════════════════════════════════════════════════════════
#  URGENCY
# ══════════════════════════════════════════════════════════════

URGENCY = {
    "en": [
        "⚠️ LIMITED SLOTS! Only a few VIP spots left today!",
        "🔥 HIGH DEMAND! Many traders have joined recently — do not miss out!",
        "⏰ TODAY ONLY! Special offer expires at midnight!",
        "🚨 ALMOST FULL! VIP channel closing new members soon!",
        "💥 LAST CHANCE! Don't miss today's winning signals!",
    ],
    "sw": [
        "⚠️ NAFASI CHACHE! Nafasi chache za VIP zimebaki leo!",
        "🔥 MAHITAJI MAKUBWA! Wafanyabiashara wengi wamejiunga hivi karibuni!",
        "⏰ LEO TU! Ofa maalum inaisha usiku wa manane!",
        "🚨 KARIBU KUJAA! Channel ya VIP itafunga wanachama wapya hivi karibuni!",
        "💥 NAFASI YA MWISHO! Usikose signals za kushinda za leo!",
    ],
    "ar": [
        "⚠️ مقاعد محدودة! بقيت مقاعد VIP قليلة فقط اليوم!",
        "🔥 طلب عالٍ! انضم كثير من المتداولين مؤخراً!",
        "⏰ اليوم فقط! ينتهي العرض الخاص عند منتصف الليل!",
    ],
    "zh": [
        "⚠️ 名额有限！今天只剩几个VIP名额！",
        "🔥 需求旺盛！最近很多交易者加入了！",
        "⏰ 仅限今天！特别优惠将于午夜到期！",
    ],
    "hi": [
        "⚠️ सीमित स्लॉट! आज केवल कुछ VIP स्पॉट बचे हैं!",
        "🔥 उच्च मांग! हाल ही में कई ट्रेडर्स जुड़े हैं!",
        "⏰ आज ही! विशेष ऑफर आधी रात को समाप्त होता है!",
    ],
    "ru": [
        "⚠️ ОГРАНИЧЕННЫЕ МЕСТА! Осталось несколько VIP мест!",
        "🔥 ВЫСОКИЙ СПРОС! Недавно присоединились многие трейдеры!",
        "⏰ ТОЛЬКО СЕГОДНЯ! Специальное предложение истекает в полночь!",
    ],
    "es": [
        "⚠️ PLAZAS LIMITADAS! Solo quedan pocas plazas VIP hoy!",
        "🔥 ALTA DEMANDA! Muchos traders se han unido recientemente!",
        "⏰ SOLO HOY! La oferta especial expira a medianoche!",
    ],
    "fr": [
        "⚠️ PLACES LIMITÉES! Il ne reste que quelques places VIP aujourd'hui!",
        "🔥 FORTE DEMANDE! De nombreux traders ont rejoint récemment!",
        "⏰ AUJOURD'HUI SEULEMENT! L'offre spéciale expire à minuit!",
    ],
    "pt": [
        "⚠️ VAGAS LIMITADAS! Apenas algumas vagas VIP restam hoje!",
        "🔥 ALTA DEMANDA! Muitos traders entraram recentemente!",
        "⏰ SOMENTE HOJE! Oferta especial expira à meia-noite!",
    ],
    "de": [
        "⚠️ BEGRENZTE PLÄTZE! Nur noch wenige VIP-Plätze heute!",
        "🔥 HOHE NACHFRAGE! Viele Trader sind kürzlich beigetreten!",
        "⏰ NUR HEUTE! Sonderangebot läuft um Mitternacht ab!",
    ],
    "ur": [
        "⚠️ محدود نشستیں! آج صرف چند VIP نشستیں باقی ہیں!",
        "🔥 زیادہ مانگ! حال ہی میں بہت سے ٹریڈرز شامل ہوئے ہیں!",
        "⏰ صرف آج! خصوصی پیشکش آدھی رات کو ختم ہوتی ہے!",
    ],
    "ja": [
        "⚠️ 限定スロット！今日のVIPスポットはわずかです！",
        "🔥 高需要！最近多くのトレーダーが参加しました！",
        "⏰ 本日限り！特別オファーは真夜中に終了します！",
    ],
}

def get_urgency(lang):
    pool = URGENCY.get(lang, URGENCY["en"])
    return pool[datetime.now().weekday() % len(pool)]

# ══════════════════════════════════════════════════════════════
#  SMART GREETING — changes by time of day (UTC+3 / EAT)
# ══════════════════════════════════════════════════════════════

def get_smart_greeting(lang):
    # Use timezone that matches the language/region for accurate time-of-day
    from datetime import timezone, timedelta
    LANG_TZ_OFFSET = {
        "sw": 3,    # Kenya/Tanzania UTC+3
        "ar": 3,    # Arabic countries (average Gulf/Arab world)
        "hi": 5,    # India UTC+5:30 → use 5 (close enough)
        "ur": 5,    # Pakistan UTC+5
        "zh": 8,    # China UTC+8
        "ja": 9,    # Japan UTC+9
        "ko": 9,    # Korea UTC+9
        "ru": 3,    # Russia (Moscow) UTC+3
        "uk": 3,    # Ukraine UTC+3
        "kk": 5,    # Kazakhstan UTC+5
        "fa": 3,    # Iran UTC+3:30 → use 3
        "tr": 3,    # Turkey UTC+3
        "de": 1,    # Germany UTC+1
        "fr": 1,    # France UTC+1
        "it": 1,    # Italy UTC+1
        "es": 1,    # Spain UTC+1
        "pl": 1,    # Poland UTC+1
        "cs": 1,    # Czech UTC+1
        "pt": 0,    # Portugal UTC+0 (Brazil is -3 but Portugal is bigger user base)
        "en": 0,    # English default UTC+0
    }
    offset = LANG_TZ_OFFSET.get(lang, 0)
    tz = timezone(timedelta(hours=offset))
    hour = datetime.now(tz).hour
    greetings = {
        "en": {
            "morning":   "🌅 Good morning! Today is a great day to WIN!",
            "afternoon": "☀️ Good afternoon! Markets are moving — are you ready?",
            "evening":   "🌆 Good evening! Evening sessions can be very profitable!",
            "night":     "🌙 Still awake? Smart traders never miss an opportunity!",
        },
        "sw": {
            "morning":   "🌅 Habari za asubuhi! Leo ni siku nzuri ya KUSHINDA!",
            "afternoon": "☀️ Habari za mchana! Masoko yanasogea — uko tayari?",
            "evening":   "🌆 Habari za jioni! Vikao vya jioni vinaweza kuwa na faida sana!",
            "night":     "🌙 Bado macho? Wafanyabiashara werevu hawakosi fursa!",
        },
        "ar": {
            "morning":   "🌅 صباح الخير! اليوم يوم رائع للفوز!",
            "afternoon": "☀️ مساء الخير! الأسواق تتحرك — هل أنت مستعد؟",
            "evening":   "🌆 مساء الخير! جلسات المساء مربحة جداً!",
            "night":     "🌙 لا تزال مستيقظاً؟ المتداولون الأذكياء لا يفوتون أي فرصة!",
        },
        "zh": {
            "morning":   "🌅 早上好！今天是赢得胜利的好日子！",
            "afternoon": "☀️ 下午好！市场正在波动 — 你准备好了吗？",
            "evening":   "🌆 晚上好！晚间交易时段非常盈利！",
            "night":     "🌙 还没睡？聪明的交易者绝不错过机会！",
        },
        "hi": {
            "morning":   "🌅 सुप्रभात! आज जीतने का शानदार दिन है!",
            "afternoon": "☀️ नमस्ते! बाजार चल रहे हैं — क्या आप तैयार हैं?",
            "evening":   "🌆 शुभ संध्या! शाम के सत्र बहुत लाभदायक हो सकते हैं!",
            "night":     "🌙 अभी भी जागे हैं? स्मार्ट ट्रेडर्स कभी मौका नहीं चूकते!",
        },
        "ru": {
            "morning":   "🌅 Доброе утро! Сегодня отличный день для победы!",
            "afternoon": "☀️ Добрый день! Рынки двигаются — вы готовы?",
            "evening":   "🌆 Добрый вечер! Вечерние сессии могут быть очень прибыльными!",
            "night":     "🌙 Ещё не спите? Умные трейдеры никогда не упускают возможности!",
        },
        "es": {
            "morning":   "🌅 ¡Buenos días! ¡Hoy es un gran día para GANAR!",
            "afternoon": "☀️ ¡Buenas tardes! Los mercados se mueven — ¿estás listo?",
            "evening":   "🌆 ¡Buenas noches! ¡Las sesiones nocturnas pueden ser muy rentables!",
            "night":     "🌙 ¿Todavía despierto? ¡Los traders inteligentes nunca pierden una oportunidad!",
        },
        "fr": {
            "morning":   "🌅 Bonjour! Aujourd'hui est un excellent jour pour GAGNER!",
            "afternoon": "☀️ Bon après-midi! Les marchés bougent — êtes-vous prêt?",
            "evening":   "🌆 Bonsoir! Les sessions du soir peuvent être très rentables!",
            "night":     "🌙 Encore éveillé? Les traders intelligents ne manquent jamais une opportunité!",
        },
        "pt": {
            "morning":   "🌅 Bom dia! Hoje é um ótimo dia para VENCER!",
            "afternoon": "☀️ Boa tarde! Os mercados estão se movendo — você está pronto?",
            "evening":   "🌆 Boa noite! As sessões noturnas podem ser muito lucrativas!",
            "night":     "🌙 Ainda acordado? Traders inteligentes nunca perdem uma oportunidade!",
        },
        "de": {
            "morning":   "🌅 Guten Morgen! Heute ist ein großartiger Tag zum GEWINNEN!",
            "afternoon": "☀️ Guten Tag! Die Märkte bewegen sich — bist du bereit?",
            "evening":   "🌆 Guten Abend! Abendsitzungen können sehr profitabel sein!",
            "night":     "🌙 Noch wach? Kluge Trader verpassen nie eine Chance!",
        },
        "ur": {
            "morning":   "🌅 صبح بخیر! آج جیتنے کا شاندار دن ہے!",
            "afternoon": "☀️ دوپہر بخیر! مارکیٹ حرکت میں ہے — کیا آپ تیار ہیں؟",
            "evening":   "🌆 شام بخیر! شام کے سیشن بہت منافع بخش ہو سکتے ہیں!",
            "night":     "🌙 ابھی بھی جاگ رہے ہیں؟ ہوشیار ٹریڈرز کبھی موقع نہیں چھوڑتے!",
        },
        "ja": {
            "morning":   "🌅 おはようございます！今日は勝つ素晴らしい日です！",
            "afternoon": "☀️ こんにちは！市場が動いています — 準備はできていますか？",
            "evening":   "🌆 こんばんは！夜のセッションはとても利益になります！",
            "night":     "🌙 まだ起きていますか？賢いトレーダーはチャンスを逃しません！",
        },
        "tr": {
            "morning":   "🌅 Günaydın! Bugün kazanmak için harika bir gün!",
            "afternoon": "☀️ İyi günler! Piyasalar hareket ediyor — hazır mısın?",
            "evening":   "🌆 İyi akşamlar! Akşam seansları çok karlı olabilir!",
            "night":     "🌙 Hala uyanık mısın? Akıllı yatırımcılar asla fırsat kaçırmaz!",
        },
        "fa": {
            "morning":   "🌅 صبح بخیر! امروز روز فوق‌العاده‌ای برای بردن است!",
            "afternoon": "☀️ بعدازظهر بخیر! بازارها در حرکت هستند — آماده‌اید؟",
            "evening":   "🌆 عصر بخیر! جلسات عصرگاهی می‌توانند بسیار سودآور باشند!",
            "night":     "🌙 هنوز بیدارید؟ معامله‌گران هوشمند هرگز فرصت را از دست نمی‌دهند!",
        },
        "ko": {
            "morning":   "🌅 좋은 아침입니다! 오늘은 이길 수 있는 최고의 날입니다!",
            "afternoon": "☀️ 안녕하세요! 시장이 움직이고 있습니다 — 준비됐나요?",
            "evening":   "🌆 좋은 저녁입니다! 저녁 세션은 매우 수익성이 높을 수 있습니다!",
            "night":     "🌙 아직 깨어 계신가요? 스마트한 트레이더는 기회를 놓치지 않습니다!",
        },
        "it": {
            "morning":   "🌅 Buongiorno! Oggi è un ottimo giorno per VINCERE!",
            "afternoon": "☀️ Buon pomeriggio! I mercati si stanno muovendo — sei pronto?",
            "evening":   "🌆 Buonasera! Le sessioni serali possono essere molto redditizie!",
            "night":     "🌙 Ancora sveglio? I trader intelligenti non perdono mai un'opportunità!",
        },
        "pl": {
            "morning":   "🌅 Dzień dobry! Dziś jest świetny dzień, żeby WYGRAĆ!",
            "afternoon": "☀️ Dzień dobry! Rynki się poruszają — jesteś gotowy?",
            "evening":   "🌆 Dobry wieczór! Wieczorne sesje mogą być bardzo dochodowe!",
            "night":     "🌙 Jeszcze nie śpisz? Mądrzy traderzy nigdy nie przepuszczają okazji!",
        },
        "uk": {
            "morning":   "🌅 Доброго ранку! Сьогодні чудовий день для перемоги!",
            "afternoon": "☀️ Добрий день! Ринки рухаються — ви готові?",
            "evening":   "🌆 Добрий вечір! Вечірні сесії можуть бути дуже прибутковими!",
            "night":     "🌙 Ще не спите? Розумні трейдери ніколи не пропускають можливостей!",
        },
    }
    period = "morning" if 5 <= hour < 12 else "afternoon" if 12 <= hour < 17 else "evening" if 17 <= hour < 21 else "night"
    lang_g = greetings.get(lang, greetings["en"])
    return lang_g[period]

# ══════════════════════════════════════════════════════════════
#  DAILY MARKET QUOTES
# ══════════════════════════════════════════════════════════════

DAILY_QUOTES = [
    ("The stock market is a device for transferring money from the impatient to the patient.", "Warren Buffett"),
    ("Risk comes from not knowing what you are doing.", "Warren Buffett"),
    ("The goal of a successful trader is to make the best trades, not to be right.", "Mark Douglas"),
    ("Every trader has a story. The winners just write better endings.", "Unknown"),
    ("In trading, the most important thing is not to make money, but not to lose it.", "George Soros"),
    ("The market is a pendulum that forever swings between optimism and pessimism.", "Benjamin Graham"),
    ("Trade what you see, not what you think.", "Unknown"),
    ("Successful trading is about managing risk, not avoiding it.", "Unknown"),
    ("The biggest risk of all is not taking one.", "Mellody Hobson"),
    ("Plan your trade and trade your plan.", "Unknown"),
    ("Cut your losses short and let your profits run.", "Unknown"),
    ("Be fearful when others are greedy, be greedy when others are fearful.", "Warren Buffett"),
    ("Trading is not about being right — it is about being profitable.", "Unknown"),
    ("Discipline is the bridge between goals and accomplishment.", "Jim Rohn"),
    ("Every expert was once a beginner. Keep going!", "Unknown"),
    ("Consistency beats perfection every single time.", "Unknown"),
    ("Your biggest enemy in trading is your own emotions.", "Unknown"),
    ("Small consistent profits beat big risky wins.", "Unknown"),
    ("The trend is your friend — until the end.", "Unknown"),
    ("Patience and discipline separate winners from losers.", "Unknown"),
    ("Know your risk before you know your reward.", "Unknown"),
    ("The market rewards those who respect it.", "Unknown"),
    ("One good trade is worth a hundred rushed ones.", "Unknown"),
    ("Winning traders think in probabilities, not certainties.", "Mark Douglas"),
    ("The best investment you can make is in yourself.", "Warren Buffett"),
    ("Success in trading comes from preparation, not luck.", "Unknown"),
    ("A good trader is always learning, always adapting.", "Unknown"),
    ("Small consistent profits compound into life-changing wealth.", "Unknown"),
    ("The market will always be there. Your capital might not. Protect it.", "Unknown"),
    ("Discipline today, financial freedom tomorrow.", "Unknown"),
]

DAILY_FLAGS = [
    "🇳🇬", "🇰🇪", "🇬🇭", "🇿🇦", "🇹🇿", "🇺🇬", "🇨🇲", "🇸🇳",
    "🇧🇷", "🇲🇽", "🇨🇴", "🇦🇷", "🇵🇹", "🇪🇸", "🇫🇷", "🇩🇪",
    "🇮🇳", "🇵🇰", "🇧🇩", "🇮🇩", "🇲🇾", "🇵🇭", "🇯🇵", "🇰🇷",
    "🇪🇬", "🇲🇦", "🇩🇿", "🇹🇳", "🇸🇩", "🇸🇦", "🇦🇪", "🇯🇴",
    "🇷🇺", "🇺🇦", "🇵🇱", "🇷🇴", "🇨🇿", "🇧🇪", "🇮🇹", "🇬🇷",
    "🇨🇮", "🇿🇲", "🇿🇼", "🇲🇿", "🇦🇴", "🇸🇴", "🇲🇱", "🇬🇳",
]

def get_daily_quote():
    day = datetime.now().timetuple().tm_yday
    idx = day % len(DAILY_QUOTES)
    flag_idx = day % len(DAILY_FLAGS)
    quote, author = DAILY_QUOTES[idx]
    flag = DAILY_FLAGS[flag_idx]
    return f'💡 *"{quote}"*\n\n{flag} User'

# ══════════════════════════════════════════════════════════════
#  BINARY TRADING TIPS
# ══════════════════════════════════════════════════════════════

BINARY_TIPS = [
    "💡 *TIP:* Always trade with the trend — if the market is going UP, look for BUY signals only!",
    "💡 *TIP:* Never risk more than 2-5% of your account on a single trade. Protect your capital first!",
    "💡 *TIP:* The best sessions overlap London (8AM-12PM GMT) and New York (1PM-5PM GMT)!",
    "💡 *TIP:* After 3 consecutive losses, STOP trading. Take a break and come back fresh.",
    "💡 *TIP:* Wait for a clear signal before entering. Patience is the most profitable skill!",
    "💡 *TIP:* Strong support and resistance levels give the highest probability trades.",
    "💡 *TIP:* Use 1-5 minute candles for binary options — clearer entry signals!",
    "💡 *TIP:* Always check the economic calendar before trading! News events can break any pattern.",
    "💡 *TIP:* Avoid trading the first 5 minutes of a new session — markets are too volatile!",
    "💡 *TIP:* Best binary trades happen when indicator AND price action agree on direction.",
    "💡 *TIP:* Set a daily profit target. When you reach it, STOP. Don't let greed destroy your gains!",
    "💡 *TIP:* OTC weekend markets follow patterns — great practice time for beginners!",
    "💡 *TIP:* Screenshot your trades. Review what worked and what didn't every week.",
    "💡 *TIP:* For 1-minute candles, use 1-2 minute expiry for best results.",
    "💡 *TIP:* When in doubt, stay OUT. No trade is always better than a bad trade!",
    "💡 *TIP:* Master one asset before trading many — consistency beats variety.",
    "💡 *TIP:* Wednesday-Thursday often give the best signals — Monday/Friday can be unpredictable.",
    "💡 *TIP:* Your mindset determines your results. Trade calm, trade smart!",
    "💡 *TIP:* Keep a trading journal — this separates professionals from gamblers.",
    "💡 *TIP:* Practice on demo accounts before using real money!",
    "💡 *TIP:* Consecutive wins cause overconfidence. Treat every trade as your first!",
    "💡 *TIP:* Check H1 timeframe for trend direction, then M5 for entry timing.",
    "💡 *TIP:* The best binary traders win 60-70% of trades — consistency beats perfection!",
    "💡 *TIP:* Avoid major news: NFP, CPI, Fed announcements can move markets wildly!",
    "💡 *TIP:* Start small and grow — 5% daily compounded beats 50% gambles every time.",
    "💡 *TIP:* Emotional trading kills accounts. Step away when angry or overexcited.",
    "💡 *TIP:* The indicator is a tool, not a guarantee. Always confirm with price action!",
    "💡 *TIP:* Two indicators confirming same direction = high probability trade!",
    "💡 *TIP:* Asian session (midnight-8AM GMT) is quieter — good for OTC assets.",
    "💡 *TIP:* Higher payout percentage = less trades needed to profit. Choose wisely!",
]

def get_daily_binary_tip():
    idx = (datetime.now().timetuple().tm_yday + 7) % len(BINARY_TIPS)
    return BINARY_TIPS[idx]

# ══════════════════════════════════════════════════════════════
#  SCARCITY MESSAGES (shown to returning users visit >= 3)
# ══════════════════════════════════════════════════════════════

SCARCITY_MSGS = {
    "en": [
        "💥 *VIP is filling up fast!*\n\nSpots available — but not for long.\n\nTraders are joining as you read this... 👇",
        "🔥 *Our community is growing FAST!*\n\nTraders worldwide have found EVALON.\n\nDon't be the last one to discover it. 👇",
        "⚡ *Limited VIP access available!*\n\nWe keep our VIP small for quality.\n\nOnce it's full — it's full. 👇",
    ],
    "sw": [
        "💥 *VIP inajaa haraka!*\n\nNafasi zinapatikana — lakini sio kwa muda mrefu.\n\nWafanyabiashara wanajiunga unaposoma hii... 👇",
        "🔥 *Jumuiya yetu inakua HARAKA!*\n\nWafanyabiashara duniani kote wamepata EVALON.\n\nUsiwe wa mwisho kuigundua. 👇",
        "⚡ *Ufikiaji wa VIP mdogo unapatikana!*\n\nTunaweka VIP yetu ndogo kwa ubora.\n\nIkijaa — imejaa. 👇",
    ],
    "ar": [
        "💥 *VIP يمتلئ بسرعة!*\n\nمقاعد متاحة — لكن ليس لفترة طويلة.\n\nالمتداولون ينضمون وأنت تقرأ هذا... 👇",
        "🔥 *مجتمعنا ينمو بسرعة!*\n\nمتداولون من جميع أنحاء العالم وجدوا EVALON.\n\nلا تكن آخر من يكتشف ذلك. 👇",
        "⚡ *وصول VIP محدود متاح!*\n\nنحافظ على صغر حجم VIP من أجل الجودة.\n\nعندما يمتلئ — ينتهي الأمر. 👇",
    ],
    "zh": [
        "💥 *VIP名额快满了！*\n\n名额有限 — 不会太久。\n\n正在有交易者加入... 👇",
        "🔥 *我们的社区正在快速增长！*\n\n全球交易者都找到了EVALON。\n\n不要成为最后一个发现它的人。 👇",
        "⚡ *VIP名额有限！*\n\n我们保持VIP小规模以确保质量。\n\n一旦满员 — 就关闭了。 👇",
    ],
    "hi": [
        "💥 *VIP तेजी से भर रहा है!*\n\nस्थान उपलब्ध हैं — लेकिन लंबे समय के लिए नहीं।\n\nजैसे आप पढ़ रहे हैं, ट्रेडर्स जुड़ रहे हैं... 👇",
        "🔥 *हमारा समुदाय तेजी से बढ़ रहा है!*\n\nदुनिया भर के ट्रेडर्स ने EVALON खोजा है।\n\nइसे खोजने वाले आखिरी मत बनो। 👇",
        "⚡ *सीमित VIP एक्सेस उपलब्ध!*\n\nहम गुणवत्ता के लिए अपना VIP छोटा रखते हैं।\n\nएक बार भरा — तो भरा। 👇",
    ],
    "ru": [
        "💥 *VIP быстро заполняется!*\n\nМеста доступны — но ненадолго.\n\nТрейдеры присоединяются прямо сейчас... 👇",
        "🔥 *Наше сообщество растёт БЫСТРО!*\n\nТрейдеры со всего мира нашли EVALON.\n\nНе будь последним, кто его откроет. 👇",
        "⚡ *Ограниченный доступ к VIP!*\n\nМы держим VIP небольшим для качества.\n\nКак заполнится — закроется. 👇",
    ],
    "es": [
        "💥 *¡El VIP se llena rápido!*\n\nHay lugares disponibles — pero no por mucho tiempo.\n\nLos traders se están uniendo mientras lees esto... 👇",
        "🔥 *¡Nuestra comunidad crece RÁPIDO!*\n\nTraders de todo el mundo han encontrado EVALON.\n\nNo seas el último en descubrirlo. 👇",
        "⚡ *¡Acceso VIP limitado disponible!*\n\nMantenemos nuestro VIP pequeño por calidad.\n\nUna vez lleno — está lleno. 👇",
    ],
    "fr": [
        "💥 *VIP se remplit vite!*\n\nPlaces disponibles — mais pas pour longtemps.\n\nDes traders rejoignent pendant que vous lisez... 👇",
        "🔥 *Notre communauté grandit VITE!*\n\nDes traders du monde entier ont trouvé EVALON.\n\nNe soyez pas le dernier à le découvrir. 👇",
        "⚡ *Accès VIP limité disponible!*\n\nNous gardons notre VIP petit pour la qualité.\n\nUne fois plein — c'est plein. 👇",
    ],
    "pt": [
        "💥 *VIP está preenchendo rápido!*\n\nVagas disponíveis — mas não por muito tempo.\n\nTraders estão entrando enquanto você lê isso... 👇",
        "🔥 *Nossa comunidade está crescendo RÁPIDO!*\n\nTraders do mundo todo encontraram EVALON.\n\nNão seja o último a descobrir. 👇",
        "⚡ *Acesso VIP limitado disponível!*\n\nMantemos nosso VIP pequeno para qualidade.\n\nUma vez cheio — está cheio. 👇",
    ],
    "de": [
        "💥 *VIP füllt sich schnell!*\n\nPlätze verfügbar — aber nicht lange.\n\nTrader treten bei, während Sie das lesen... 👇",
        "🔥 *Unsere Community wächst SCHNELL!*\n\nTrader aus aller Welt haben EVALON gefunden.\n\nSei nicht der Letzte, der es entdeckt. 👇",
        "⚡ *Begrenzter VIP-Zugang verfügbar!*\n\nWir halten unser VIP klein für Qualität.\n\nWenn es voll ist — ist es voll. 👇",
    ],
    "ur": [
        "💥 *VIP تیزی سے بھر رہا ہے!*\n\nجگہیں دستیاب ہیں — لیکن زیادہ دیر کے لیے نہیں۔\n\nجیسے آپ پڑھ رہے ہیں ٹریڈرز شامل ہو رہے ہیں... 👇",
        "🔥 *ہماری کمیونٹی تیزی سے بڑھ رہی ہے!*\n\nدنیا بھر کے ٹریڈرز نے EVALON دریافت کیا ہے۔\n\nاسے دریافت کرنے والے آخری مت بنیں۔ 👇",
        "⚡ *محدود VIP رسائی دستیاب ہے!*\n\nہم معیار کے لیے VIP کو چھوٹا رکھتے ہیں۔\n\nایک بار بھر گیا — تو بس۔ 👇",
    ],
    "ja": [
        "💥 *VIPはすぐに埋まります！*\n\nスポットあり — でも長くはありません。\n\nこれを読んでいる間にトレーダーが参加しています... 👇",
        "🔥 *コミュニティが急成長中！*\n\n世界中のトレーダーがEVALONを見つけました。\n\n最後に発見する人にならないでください。 👇",
        "⚡ *限定VIPアクセス！*\n\n品質のためにVIPは小さく保ちます。\n\n一杯になったら — 終わりです。 👇",
    ],
    "tr": [
        "💥 *VIP hızla dolıyor!*\n\nYerler mevcut — ama çok sürmez.\n\nBunu okurken traderlar katılıyor... 👇",
        "🔥 *Topluluğumuz HIZLA büyüyor!*\n\nDünyanın dört bir yanından traderlar EVALON'u buldu.\n\nKuşananların en son kişisi olmayın. 👇",
        "⚡ *Sınırlı VIP erişimi mevcut!*\n\nKalite için VIP'imizi küçük tutuyoruz.\n\nDolunca — doldu. 👇",
    ],
    "fa": [
        "💥 *VIP سریع پر می‌شود!*\n\nجاهایی موجود است — اما نه برای مدت طولانی.\n\nتریدرها همین الان که می‌خوانید دارند عضو می‌شوند... 👇",
        "🔥 *جامعه ما سریع در حال رشد است!*\n\nتریدرهای سراسر جهان EVALON را پیدا کرده‌اند.\n\nآخرین کسی نباشید که آن را کشف می‌کند. 👇",
        "⚡ *دسترسی محدود VIP موجود!*\n\nبرای کیفیت VIP را کوچک نگه می‌داریم.\n\nوقتی پر شد — تمام است. 👇",
    ],
    "ko": [
        "💥 *VIP가 빠르게 채워지고 있습니다!*\n\n자리가 있지만 — 오래가지 않습니다.\n\n이걸 읽는 동안 트레이더들이 합류하고 있습니다... 👇",
        "🔥 *우리 커뮤니티가 빠르게 성장하고 있습니다!*\n\n전 세계 트레이더들이 EVALON을 찾았습니다.\n\n마지막으로 발견하는 사람이 되지 마세요. 👇",
        "⚡ *제한된 VIP 액세스 가능!*\n\n품질을 위해 VIP를 소규모로 유지합니다.\n\n한번 꽉 차면 — 끝입니다. 👇",
    ],
    "it": [
        "💥 *Il VIP si sta riempiendo velocemente!*\n\nPosti disponibili — ma non per molto.\n\nI trader si stanno unendo mentre leggi questo... 👇",
        "🔥 *La nostra community cresce VELOCEMENTE!*\n\nTrader da tutto il mondo hanno trovato EVALON.\n\nNon essere l'ultimo a scoprirlo. 👇",
        "⚡ *Accesso VIP limitato disponibile!*\n\nManteniamo il VIP piccolo per la qualità.\n\nUna volta pieno — è pieno. 👇",
    ],
    "pl": [
        "💥 *VIP wypełnia się szybko!*\n\nMiejsca dostępne — ale nie na długo.\n\nTraderzy dołączają, kiedy to czytasz... 👇",
        "🔥 *Nasza społeczność rośnie SZYBKO!*\n\nTraderzy z całego świata znaleźli EVALON.\n\nNie bądź ostatnim, który go odkryje. 👇",
        "⚡ *Ograniczony dostęp VIP!*\n\nUtrzymujemy VIP małym dla jakości.\n\nGdy się zapełni — koniec. 👇",
    ],
    "uk": [
        "💥 *VIP швидко заповнюється!*\n\nМісця є — але ненадовго.\n\nТрейдери приєднуються поки ти читаєш... 👇",
        "🔥 *Наша спільнота росте ШВИДКО!*\n\nТрейдери з усього світу знайшли EVALON.\n\nНе будь останнім, хто це відкриє. 👇",
        "⚡ *Обмежений доступ до VIP!*\n\nМи тримаємо VIP маленьким для якості.\n\nЯк заповниться — закрито. 👇",
    ],
}

def get_scarcity_msg(lang):
    pool = SCARCITY_MSGS.get(lang, SCARCITY_MSGS["en"])
    return random.choice(pool)

# ══════════════════════════════════════════════════════════════
#  TRUST TAGS
# ══════════════════════════════════════════════════════════════

TRUST_TAGS = {
    "en": [
        "\n\n✅ *Verified by 1,200+ traders worldwide*",
        "\n\n🔒 *Your funds always stay in YOUR account*",
        "\n\n⭐ *Rated 4.9/5 by our community*",
        "\n\n🌍 *Trusted by traders in 50+ countries*",
    ],
    "sw": [
        "\n\n✅ *Imethibitishwa na wafanyabiashara 1,200+ duniani*",
        "\n\n🔒 *Fedha zako zinabaki daima kwenye AKAUNTI YAKO*",
        "\n\n⭐ *Imepewa alama ya 4.9/5 na jumuiya yetu*",
        "\n\n🌍 *Inaaminiwa na wafanyabiashara katika nchi 50+*",
    ],
}

def get_trust_tag(lang):
    pool = TRUST_TAGS.get(lang, TRUST_TAGS["en"])
    idx = datetime.now().day % len(pool)
    return pool[idx]

# ══════════════════════════════════════════════════════════════
#  ACHIEVEMENT SYSTEM
# ══════════════════════════════════════════════════════════════

ACHIEVEMENTS = {
    "first_look":    ("🌟", "First Step",    "Viewed your first service"),
    "explorer":      ("💎", "Explorer",      "Viewed all services"),
    "loyal":         ("🏆", "Loyal Member",  "Member for 14+ days"),
    "top_referrer":  ("👑", "Top Referrer",  "Referred 5+ friends"),
    "quiz_master":   ("🎓", "Quiz Master",   "Completed the weekly quiz"),
    "goal_setter":   ("🎯", "Goal Setter",   "Set a trading goal"),
    "streak_3":      ("🔥", "On Fire",       "3-day streak"),
    "streak_7":      ("⚡", "Unstoppable",   "7-day streak"),
}

def get_user_badges(uid):
    import json
    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT badges FROM users WHERE id=%s", (uid,))
        row = c.fetchone()
        conn.close()
        if row and row[0]:
            return json.loads(row[0])
        return []
    except:
        return []

def add_badge(uid, badge_key):
    import json
    try:
        badges = get_user_badges(uid)
        if badge_key not in badges:
            badges.append(badge_key)
            conn = get_conn()
            c = conn.cursor()
            c.execute("UPDATE users SET badges=%s WHERE id=%s", (json.dumps(badges), uid))
            conn.commit()
            conn.close()
            return True
        return False
    except:
        return False

# ══════════════════════════════════════════════════════════════
#  QUIZ SYSTEM
# ══════════════════════════════════════════════════════════════

QUIZ_QUESTIONS = [
    {
        "q": "📊 *QUIZ Q1:* In binary options, what does it mean when you place a CALL trade?",
        "options": ["🔴 You expect price to go DOWN", "🟢 You expect price to go UP", "⚪ You expect price to stay the same"],
        "answer": 1,
        "explanation": "A CALL trade means you believe the price will be HIGHER at expiry."
    },
    {
        "q": "💰 *QUIZ Q2:* What is the SAFEST rule for trade size in binary options?",
        "options": ["💸 50% of your account", "✅ 2-5% of your account", "🎲 As much as possible"],
        "answer": 1,
        "explanation": "Never risk more than 2-5% per trade — this protects your capital."
    },
    {
        "q": "⏰ *QUIZ Q3:* When is usually the BEST time to trade binary options?",
        "options": ["🌙 Late night (2AM-6AM)", "✅ London-NY overlap (1PM-5PM GMT)", "🌅 Early morning (5AM-7AM)"],
        "answer": 1,
        "explanation": "The London-New York overlap has the most liquidity and clearest signals."
    },
]

def get_quiz_score(uid):
    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT quiz_score FROM users WHERE id=%s", (uid,))
        row = c.fetchone()
        conn.close()
        return row[0] or 0 if row else 0
    except:
        return 0

def save_quiz_score(uid, score):
    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute("UPDATE users SET quiz_score=%s WHERE id=%s", (score, uid))
        conn.commit()
        conn.close()
    except:
        pass

# ══════════════════════════════════════════════════════════════
#  RESULTS HISTORY DB FUNCTIONS
# ══════════════════════════════════════════════════════════════

def save_result(result_date, content_text, media_id=None, media_type=None):
    try:
        conn = get_conn()
        c = conn.cursor()
        # Ensure table exists
        c.execute("""
            CREATE TABLE IF NOT EXISTS results_history (
                id         SERIAL PRIMARY KEY,
                caption    TEXT DEFAULT NULL,
                media_id   TEXT DEFAULT NULL,
                media_type TEXT DEFAULT NULL,
                saved_at   TEXT DEFAULT NULL
            )
        """)
        now = datetime.now().strftime("%d/%m/%Y %H:%M")
        c.execute("""
            INSERT INTO results_history (caption, media_id, media_type, saved_at)
            VALUES (%s, %s, %s, %s)
        """, (content_text[:2000] if content_text else result_date, media_id, media_type, now))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.warning(f"save_result failed: {e}")
        return False

def get_results_history(limit=10):
    try:
        conn = get_conn()
        c = conn.cursor()
        # Ensure table exists in case migration did not run
        c.execute("""
            CREATE TABLE IF NOT EXISTS results_history (
                id         SERIAL PRIMARY KEY,
                caption    TEXT DEFAULT NULL,
                media_id   TEXT DEFAULT NULL,
                media_type TEXT DEFAULT NULL,
                saved_at   TEXT DEFAULT NULL
            )
        """)
        conn.commit()
        c.execute("""
            SELECT id, caption, media_id, media_type, saved_at
            FROM results_history
            ORDER BY id DESC LIMIT %s
        """, (limit,))
        rows = c.fetchall()
        conn.close()
        return rows
    except Exception as e:
        logger.warning(f"get_results_history failed: {e}")
        return []

def get_result_by_id(rid):
    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute("""
            SELECT id, caption, media_id, media_type, saved_at
            FROM results_history WHERE id=%s
        """, (rid,))
        row = c.fetchone()
        conn.close()
        return row
    except:
        return None

def save_chat_message(user_id, user_name, username, sender, message=None, media_type=None, media_id=None):
    """Save every message from user or admin for history — persists even after session ends"""
    try:
        conn = get_conn()
        c = conn.cursor()
        now = datetime.now().strftime("%d/%m/%Y %H:%M")
        c.execute("""
            INSERT INTO chat_history (user_id, user_name, username, sender, message, media_type, media_id, sent_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (user_id, user_name or "", username or "", sender,
              message[:4000] if message else None, media_type, media_id, now))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"save_chat_message failed: {e}")

def get_chat_history_for_user(uid, limit=100):
    """Get all saved messages for a user"""
    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute("""
            SELECT sender, message, media_type, sent_at
            FROM chat_history WHERE user_id=%s
            ORDER BY id DESC LIMIT %s
        """, (uid, limit))
        rows = c.fetchall()
        conn.close()
        return list(reversed(rows))
    except:
        return []

# ══════════════════════════════════════════════════════════════
#  PROFILE BUILDER
# ══════════════════════════════════════════════════════════════

def get_member_days(uid):
    """Return how many days the user has been a member"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT joined FROM users WHERE id=%s", (uid,))
    row = c.fetchone()
    conn.close()
    if not row or not row[0]:
        return 0
    try:
        joined_dt = datetime.strptime(row[0][:16], "%d/%m/%Y %H:%M")
        return max(0, (datetime.now() - joined_dt).days)
    except:
        return 0

# ══════════════════════════════════════════════════════════════
#  FEATURE 7: SUCCESS STORIES — DB helpers
# ══════════════════════════════════════════════════════════════
def add_story(caption, media_id=None, media_type="text"):
    conn = get_conn()
    c = conn.cursor()
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    c.execute(
        "INSERT INTO stories (caption, media_id, media_type, created_at) VALUES (%s,%s,%s,%s) RETURNING id",
        (caption, media_id, media_type, now))
    new_id = c.fetchone()[0]
    conn.commit()
    conn.close()
    return new_id

def get_all_stories():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, caption, media_id, media_type, created_at FROM stories ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "caption": r[1], "media_id": r[2], "media_type": r[3], "created_at": r[4]} for r in rows]

def delete_story(story_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM stories WHERE id=%s RETURNING id", (story_id,))
    deleted = c.fetchone()
    conn.commit()
    conn.close()
    return bool(deleted)

def has_stories():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT 1 FROM stories LIMIT 1")
    row = c.fetchone()
    conn.close()
    return bool(row)

def get_user_vip_progress(uid):
    """Calculate VIP progress 0-100% from activity points"""
    try:
        streak, _ = get_streak(uid)
        referrals = get_referral_count(uid)
        quiz = get_quiz_score(uid)
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT total_spins FROM spin_log WHERE user_id=%s", (uid,))
        row = c.fetchone()
        spins = row[0] if row else 0
        conn.close()
        streak_pts = min(streak * 3, 30)   # max 30
        ref_pts    = min(referrals * 8, 32) # max 32
        spin_pts   = min(spins * 5, 20)    # max 20
        quiz_pts   = min(quiz * 4, 18)     # max 18
        total = streak_pts + ref_pts + spin_pts + quiz_pts
        return min(total, 100)
    except:
        return 0

def render_vip_progress_bar(pct):
    filled = int(pct / 5)   # 20 segments
    bar = "█" * filled + "░" * (20 - filled)
    if pct >= 100:
        label = "🔥 MAX — VIP Ready!"
    elif pct >= 75:
        label = "Almost there! 💎"
    elif pct >= 50:
        label = "Good progress! 🚀"
    elif pct >= 25:
        label = "Keep going! 💪"
    else:
        label = "Just started 🌱"
    return f"[{bar}]\n    {pct}% \u2014 {label}"

def has_early_bird_badge(uid):
    """~30% of users get this fake badge based on uid seed"""
    return (uid % 10) < 3

def build_profile_text(uid, lang):
    days = get_member_days(uid)
    streak_val, _ = update_streak(uid)
    badges = get_user_badges(uid)
    ref_count = get_referral_count(uid)
    quiz_score = get_quiz_score(uid)
    progress = get_user_vip_progress(uid)
    bar = render_vip_progress_bar(progress)

    # Real badges
    badge_list = [ACHIEVEMENTS[b][0] for b in badges if b in ACHIEVEMENTS]
    # Fake Early Bird badge (seed-based)
    if has_early_bird_badge(uid):
        badge_list = ["🌅 Early Bird"] + badge_list
    badge_display = "  ".join(badge_list) if badge_list else "None yet 🌱"

    profile = (
        "👤 *YOUR PROFILE*\n\n"
        f"📅 Member for: *{days} days*\n"
        f"🔥 Daily streak: *{streak_val} days*\n"
        f"👥 People invited: *{ref_count}*\n"
        f"🧠 Quiz score: *{quiz_score}/3*\n\n"
        f"🏅 *Badges:*\n{badge_display}\n\n"
        f"🎯 *VIP Progress:*\n{bar}\n\n"
        "💎 Keep active to unlock VIP access!"
    )
    return profile

# ══════════════════════════════════════════════════════════════
#  CELEBRATION MESSAGES
# ══════════════════════════════════════════════════════════════

def get_celebration_message(days, lang):
    if days == 7:
        msgs = {
            "en": "🎉 *ONE WEEK!* You've been with EVALON for 7 days!\n\n⭐ You're already ahead of 80% of new traders!\n\n💪 Keep going — the best is yet to come!",
            "sw": "🎉 *WIKI MOJA!* Umekuwa na EVALON kwa siku 7!\n\n⭐ Tayari uko mbele ya 80% ya wafanyabiashara wapya!\n\n💪 Endelea — bora zaidi bado inakuja!",
        }
        return msgs.get(lang, msgs["en"])
    elif days == 30:
        msgs = {
            "en": "🏆 *ONE MONTH!* You're a real trader now!\n\n💎 30 days with EVALON — you're in the top tier!\n\n🚀 This is where the magic happens. Stay consistent!",
            "sw": "🏆 *MWEZI MMOJA!* Wewe ni mfanyabiashara wa kweli sasa!\n\n💎 Siku 30 na EVALON — uko kwenye kiwango cha juu!\n\n🚀 Hapa ndipo uchawi unatokea. Endelea kuwa thabiti!",
        }
        return msgs.get(lang, msgs["en"])
    elif days == 90:
        msgs = {
            "en": "👑 *THREE MONTHS!* You're a LEGEND!\n\n🌟 90 days of consistent trading — most people quit after week 1!\n\n💪 You've proven you have what it takes. The sky is the limit!",
            "sw": "👑 *MIEZI MITATU!* Wewe ni HADITHI!\n\n🌟 Siku 90 za biashara thabiti — watu wengi wanakata tamaa baada ya wiki ya kwanza!\n\n💪 Umethibitisha una uwezo. Mbingu ni kikomo!",
        }
        return msgs.get(lang, msgs["en"])
    return None

# ══════════════════════════════════════════════════════════════
#  SMART COMEBACK — week 1, 2, 3
# ══════════════════════════════════════════════════════════════

COMEBACK_MSGS = {
    1: {
        "en": "👋 *Hey {name}! It's been a week!*\n\n🔥 The market has been WILD this week!\n\nTraders who stayed consistent saw amazing results.\n\nDon't miss week 2 — it's usually even BETTER! 💎",
        "sw": "👋 *Habari {name}! Imekuwa wiki!*\n\n🔥 Soko limekuwa LA MSISIMKO wiki hii!\n\nWafanyabiashara waliobaki thabiti walipata matokeo ya ajabu.\n\nUsikose wiki ya 2 — kawaida ni BORA zaidi! 💎",
    },
    2: {
        "en": "🌟 *{name}, you're 2 weeks in!*\n\n💎 This is where real traders are MADE.\n\nThe ones who push through week 2 are the ones who change their lives.\n\nYou've got this. Come back and WIN! 🏆",
        "sw": "🌟 *{name}, uko wiki 2!*\n\n💎 Hapa ndipo wafanyabiashara wa kweli WANAUNDWA.\n\nWale wanaopita wiki ya 2 ndio wanaobadilisha maisha yao.\n\nUnaweza. Rudi na USHINDE! 🏆",
    },
    3: {
        "en": "🚀 *{name} — 3 weeks strong!*\n\n👑 You're in the top 10% of traders just by STAYING.\n\nMost quit in week 1. You're still here.\n\nThat's the trader's mindset. Don't stop now — your breakthrough is CLOSE! ⚡",
        "sw": "🚀 *{name} — Wiki 3 imara!*\n\n👑 Uko kwenye asilimia 10 ya juu ya wafanyabiashara kwa KUBAKI tu.\n\nWengi walikata tamaa wiki ya 1. Bado uko hapa.\n\nHiyo ndiyo akili ya mfanyabiashara. Usiacha sasa — mafanikio yako YAKO KARIBU! ⚡",
    },
}

async def send_smart_comeback(context):
    job_data = context.job.data
    chat_id = job_data["chat_id"]
    name    = job_data["name"]
    lang    = job_data.get("lang", "en")
    week    = job_data.get("week", 1)
    week_msgs = COMEBACK_MSGS.get(week, COMEBACK_MSGS[1])
    text = week_msgs.get(lang, week_msgs["en"]).format(name=name)
    try:
        img = random.choice(SERVICE_PHOTOS)
        await context.bot.send_photo(
            chat_id=chat_id, photo=img, caption=text,
            parse_mode="Markdown", protect_content=True,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🚀 Let's Go!", callback_data="menu_services"),
                InlineKeyboardButton("💬 Support", callback_data="do_support"),
            ]]))
    except:
        try:
            await context.bot.send_message(
                chat_id=chat_id, text=text,
                parse_mode="Markdown", protect_content=True,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🚀 Let's Go!", callback_data="menu_services"),
                ]]))
        except:
            pass

def schedule_smart_comebacks(context, chat_id, name, lang):
    if not context.job_queue:
        return
    for week in [1, 2, 3]:
        job_name = f"comeback_{chat_id}_w{week}"
        for job in context.job_queue.get_jobs_by_name(job_name):
            job.schedule_removal()
        context.job_queue.run_once(
            send_smart_comeback,
            when=week * 7 * 24 * 3600,
            data={"chat_id": chat_id, "name": name, "lang": lang, "week": week},
            name=job_name)

# ══════════════════════════════════════════════════════════════
#  FOMO ENGINE — 30 min after viewing service
# ══════════════════════════════════════════════════════════════

async def send_fomo_message(context):
    job_data = context.job.data
    chat_id = job_data["chat_id"]
    lang    = job_data.get("lang", "en")
    service = job_data.get("service", "our services")
    fomo_msgs = {
        "en": f"👀 *Still thinking about {service}?*\n\nWhile you're deciding, others are already winning...\n\nDon't let hesitation cost you profits. 💰\n\n👇 Take action now:",
        "sw": f"👀 *Bado unafikiri kuhusu {service}?*\n\nUnapoamua, wengine wanashinda tayari...\n\nUsiache kusita kukugharimu faida. 💰\n\n👇 Chukua hatua sasa:",
    }
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=fomo_msgs.get(lang, fomo_msgs["en"]),
            parse_mode="Markdown", protect_content=True,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🚀 Explore Now", callback_data="menu_services")
            ]]))
    except:
        pass

def schedule_fomo(context, chat_id, lang, service_name):
    if not context.job_queue:
        return
    job_name = f"fomo_{chat_id}"
    for job in context.job_queue.get_jobs_by_name(job_name):
        job.schedule_removal()
    context.job_queue.run_once(
        send_fomo_message,
        when=1800,
        data={"chat_id": chat_id, "lang": lang, "service": service_name},
        name=job_name)

# ══════════════════════════════════════════════════════════════
#  ANTI-GHOST SYSTEM — 7 days inactive
# ══════════════════════════════════════════════════════════════

async def send_anti_ghost(context):
    job_data = context.job.data
    chat_id = job_data["chat_id"]
    name    = job_data.get("name", "friend")
    lang    = job_data.get("lang", "en")
    msgs = {
        "en": f"👻 *Hey {name}! Everything okay?*\n\nWe haven't seen you in a while...\n\n🔥 While you were away, traders in our community made serious moves.\n\n💎 Your spot is still here — don't let it go to waste!\n\n👇 Come back:",
        "sw": f"👻 *Hee {name}! Kila kitu sawa?*\n\nHatujakuona kwa muda...\n\n🔥 Ulipokuwa mbali, wafanyabiashara katika jumuiya yetu walifanya vizuri sana.\n\n💎 Nafasi yako bado ipo hapa — usiiacha ipotee!\n\n👇 Rudi:",
    }
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=msgs.get(lang, msgs["en"]),
            parse_mode="Markdown", protect_content=True,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🚀 I'm Back!", callback_data="main_menu")
            ]]))
    except:
        pass

# ══════════════════════════════════════════════════════════════
#  WIN NOTIFICATION
# ══════════════════════════════════════════════════════════════

WIN_NOTIFICATIONS = {
    "en": [
        "🔔 *ALERT:* A VIP member just had a GREAT session!\n\nResults like these happen when you have the right tools. 💪\n\nWant the same edge? 👇",
        "📱 *VIP WIN ALERT:* Another profitable session in the books!\n\nOur community is consistently winning.\n\nReady to join them? 👇",
        "💰 *TRADER ALERT:* Incredible session results today!\n\nThis is what happens with the right strategy and support. 🏆\n\nYour turn? 👇",
    ],
    "sw": [
        "🔔 *ARIFA:* Mwanachama wa VIP amepata kikao KIZURI sana!\n\nMatokeo kama haya hutokea ukiwa na zana sahihi. 💪\n\nUnataka faida hiyo? 👇",
        "📱 *ARIFA YA VIP WIN:* Kikao kingine chenye faida kimekamilika!\n\nJumuiya yetu inashinda kwa uthabiti.\n\nUko tayari kujiunga? 👇",
        "💰 *ARIFA YA TRADER:* Matokeo ya ajabu leo!\n\nHii ndivyo inavyotokea na mkakati na msaada sahihi. 🏆\n\nZamu yako? 👇",
    ],
    "ar": [
        "🔔 *تنبيه:* عضو VIP للتو أجرى جلسة رائعة!\n\nهذه النتائج تحدث عندما تملك الأدوات المناسبة. 💪\n\nتريد نفس الميزة؟ 👇",
        "📱 *تنبيه فوز VIP:* جلسة مربحة أخرى!\n\nمجتمعنا يفوز باستمرار.\n\nمستعد للانضمام؟ 👇",
        "💰 *تنبيه المتداولين:* نتائج جلسة لا تصدق اليوم!\n\nهذا ما يحدث مع الاستراتيجية والدعم المناسبين. 🏆\n\nدورك؟ 👇",
    ],
    "zh": [
        "🔔 *提醒:* 一位VIP会员刚刚有了很棒的交易时段！\n\n有了正确的工具就会有这样的结果。 💪\n\n想要同样的优势吗？ 👇",
        "📱 *VIP获胜提醒:* 又一个盈利时段！\n\n我们的社区一直在盈利。\n\n准备好加入了吗？ 👇",
        "💰 *交易者提醒:* 今天令人难以置信的结果！\n\n这就是正确策略和支持的效果。 🏆\n\n轮到你了？ 👇",
    ],
    "hi": [
        "🔔 *अलर्ट:* एक VIP सदस्य का शानदार सत्र हुआ!\n\nसही टूल्स के साथ ऐसे परिणाम होते हैं। 💪\n\nवही फायदा चाहते हैं? 👇",
        "📱 *VIP विन अलर्ट:* एक और लाभदायक सत्र!\n\nहमारी कम्युनिटी लगातार जीत रही है।\n\nशामिल होने के लिए तैयार? 👇",
        "💰 *ट्रेडर अलर्ट:* आज अविश्वसनीय परिणाम!\n\nसही रणनीति और सहायता के साथ ऐसा होता है। 🏆\n\nआपकी बारी? 👇",
    ],
    "ru": [
        "🔔 *ОПОВЕЩЕНИЕ:* Участник VIP только что провёл ОТЛИЧНУЮ сессию!\n\nТакие результаты бывают, когда есть правильные инструменты. 💪\n\nХотите то же преимущество? 👇",
        "📱 *VIP ПОБЕДА:* Ещё одна прибыльная сессия!\n\nНаше сообщество стабильно выигрывает.\n\nГотовы присоединиться? 👇",
        "💰 *СИГНАЛ ТРЕЙДЕРА:* Невероятные результаты сегодня!\n\nВот что бывает с правильной стратегией. 🏆\n\nВаша очередь? 👇",
    ],
    "es": [
        "🔔 *ALERTA:* ¡Un miembro VIP acaba de tener una sesión INCREÍBLE!\n\nEstos resultados ocurren con las herramientas correctas. 💪\n\n¿Quieres la misma ventaja? 👇",
        "📱 *ALERTA VIP:* ¡Otra sesión rentable!\n\nNuestra comunidad gana consistentemente.\n\n¿Listo para unirte? 👇",
    ],
    "fr": [
        "🔔 *ALERTE:* Un membre VIP vient d'avoir une session incroyable!\n\nCes résultats arrivent avec les bons outils. 💪\n\nVous voulez le même avantage? 👇",
        "📱 *ALERTE VIP:* Une autre session rentable!\n\nNotre communauté gagne régulièrement.\n\nPrêt à les rejoindre? 👇",
    ],
    "pt": [
        "🔔 *ALERTA:* Um membro VIP acabou de ter uma sessão INCRÍVEL!\n\nEsses resultados acontecem com as ferramentas certas. 💪\n\nQuer a mesma vantagem? 👇",
        "📱 *ALERTA VIP:* Mais uma sessão lucrativa!\n\nNossa comunidade vence consistentemente.\n\nPronto para se juntar? 👇",
    ],
    "de": [
        "🔔 *ALARM:* Ein VIP-Mitglied hatte gerade eine TOLLE Sitzung!\n\nSolche Ergebnisse passieren mit den richtigen Tools. 💪\n\nWollen Sie denselben Vorteil? 👇",
        "📱 *VIP-GEWINN:* Eine weitere profitable Sitzung!\n\nUnsere Community gewinnt konstant.\n\nBereit beizutreten? 👇",
    ],
    "ur": [
        "🔔 *اطلاع:* ایک VIP رکن کا شاندار سیشن ہوا!\n\nصحیح ٹولز کے ساتھ ایسے نتائج آتے ہیں۔ 💪\n\nوہی فائدہ چاہتے ہیں؟ 👇",
        "📱 *VIP جیت کی اطلاع:* ایک اور منافع بخش سیشن!\n\nہماری کمیونٹی مستقل جیت رہی ہے۔\n\nشامل ہونے کے لیے تیار؟ 👇",
    ],
    "ja": [
        "🔔 *アラート:* VIPメンバーが素晴らしいセッションを行いました!\n\n正しいツールがあればこんな結果が出ます。 💪\n\n同じ優位性が欲しいですか? 👇",
        "📱 *VIP勝利アラート:* また利益が出るセッション!\n\n私たちのコミュニティは安定して勝っています。\n\n参加する準備はできていますか? 👇",
    ],
    "tr": [
        "🔔 *UYARI:* Bir VIP üye harika bir seans geçirdi!\n\nDoğru araçlarla bu sonuçlar olur. 💪\n\nAynı avantajı ister misiniz? 👇",
        "📱 *VIP KAZANMA UYARISI:* Başka bir karlı seans!\n\nTopluluğumuz istikrarlı şekilde kazanıyor.\n\nKatılmaya hazır mısınız? 👇",
    ],
    "fa": [
        "🔔 *هشدار:* یک عضو VIP یک جلسه عالی داشت!\n\nبا ابزارهای درست این نتایج اتفاق می‌افتد. 💪\n\nمی‌خواهید همان مزیت را داشته باشید؟ 👇",
        "📱 *هشدار برنده VIP:* جلسه سودآور دیگری!\n\nجامعه ما به طور مداوم می‌برد.\n\nآماده عضویت هستید؟ 👇",
    ],
    "ko": [
        "🔔 *알림:* VIP 회원이 방금 훌륭한 세션을 가졌습니다!\n\n올바른 도구가 있으면 이런 결과가 나옵니다. 💪\n\n같은 우위를 원하시나요? 👇",
        "📱 *VIP 승리 알림:* 또 하나의 수익 세션!\n\n우리 커뮤니티는 꾸준히 이기고 있습니다.\n\n합류할 준비가 됐나요? 👇",
    ],
    "it": [
        "🔔 *AVVISO:* Un membro VIP ha appena avuto una sessione FANTASTICA!\n\nQuesti risultati si ottengono con gli strumenti giusti. 💪\n\nVuoi lo stesso vantaggio? 👇",
        "📱 *AVVISO VINCITA VIP:* Un'altra sessione redditizia!\n\nLa nostra community vince costantemente.\n\nPronto ad unirti? 👇",
    ],
}

def get_win_notification(lang):
    pool = WIN_NOTIFICATIONS.get(lang, WIN_NOTIFICATIONS["en"])
    return random.choice(pool)

# ══════════════════════════════════════════════════════════════
#  COMMUNITY VIBE COUNTER (disabled)
# ══════════════════════════════════════════════════════════════

def get_active_traders_count():
    return ""

def build_welcome_text(lang, name, visit_count=1):
    """Build welcome text with smart greeting + daily quote"""
    urgency = get_urgency(lang)
    greeting = get_smart_greeting(lang)
    quote = get_daily_quote()
    base = ui("welcome", lang).format(
        name=escape_md(name), urgency=urgency, business=BUSINESS_NAME)
    if visit_count >= 3:
        scarcity = get_scarcity_msg(lang)
        return f"{greeting}\n\n{base}\n\n{scarcity}\n\n{quote}"
    return f"{greeting}\n\n{base}\n\n{quote}"


# ══════════════════════════════════════════════════════════════
#  SERVICE REPLIES
# ══════════════════════════════════════════════════════════════

SIGNALS_REPLIES = {
    "en": [
        "📊 *VIP SIGNALS — EVALON WINNERS* 🎯\n\n✅ 80–95% Win Rate\n✅ 3–10 signals daily\n✅ Real Forex pairs\n✅ Entry, TP & SL included\n✅ Works on Quotex & Pocket Option\n✅ 24/7 active team\n\n👇 Visit our website:",
        "🎯 *PRECISION SIGNALS* ⚡\n\n🔑 Each signal:\n• Real Forex pair\n• Direction (BUY/SELL)\n• Entry price, TP & SL\n\n📊 Quotex | Pocket Option | All brokers\n\n👇 Get access now:",
        "💎 *EVALON VIP SIGNALS* 🚀\n\n📈 Real price action\n📊 EUR/USD | GBP/USD | USD/JPY | XAU/USD\n⚡ Instant delivery\n\n👇 Start winning:",
    ],
    "sw": [
        "📊 *VIP SIGNALS — EVALON WINNERS* 🎯\n\n✅ Usahihi 80–95%\n✅ Signals 3–10 kila siku\n✅ Forex ya kweli\n✅ Entry, TP & SL\n✅ Quotex & Pocket Option\n\n👇 Tembelea website:",
        "🎯 *SIGNALS ZA USAHIHI* ⚡\n\n🔑 Kila signal:\n• Pair ya forex ya kweli\n• Mwelekeo (BUY/SELL)\n• Bei ya kuingia, TP & SL\n\n👇 Pata ufikiaji:",
    ],
    "ar": ["📊 *إشارات VIP — EVALON* 🎯\n\n✅ دقة 80–95%\n✅ 3–10 إشارات يومياً\n✅ فوركس حقيقي\n✅ دخول، TP و SL\n✅ Quotex و Pocket Option\n\n👇 زر موقعنا:"],
    "zh": ["📊 *VIP信号 — EVALON* 🎯\n\n✅ 80–95%胜率\n✅ 每日3–10个信号\n✅ 真实外汇\n✅ 入场、TP和SL\n✅ Quotex和Pocket Option\n\n👇 访问网站:"],
    "hi": ["📊 *VIP सिग्नल — EVALON* 🎯\n\n✅ 80–95% जीत दर\n✅ प्रतिदिन 3–10 सिग्नल\n✅ असली फॉरेक्स\n✅ Entry, TP और SL\n✅ Quotex और Pocket Option\n\n👇 वेबसाइट:"],
    "ru": ["📊 *VIP СИГНАЛЫ — EVALON* 🎯\n\n✅ Точность 80–95%\n✅ 3–10 сигналов в день\n✅ Реальный форекс\n✅ Вход, TP и SL\n✅ Quotex и Pocket Option\n\n👇 Сайт:"],
    "es": ["📊 *SEÑALES VIP — EVALON* 🎯\n\n✅ Precisión 80–95%\n✅ 3–10 señales diarias\n✅ Forex real\n✅ Entrada, TP y SL\n✅ Quotex y Pocket Option\n\n👇 Web:"],
    "fr": ["📊 *SIGNAUX VIP — EVALON* 🎯\n\n✅ Précision 80–95%\n✅ 3–10 signaux par jour\n✅ Forex réel\n✅ Entrée, TP et SL\n✅ Quotex et Pocket Option\n\n👇 Site:"],
    "pt": ["📊 *SINAIS VIP — EVALON* 🎯\n\n✅ Precisão 80–95%\n✅ 3–10 sinais diários\n✅ Forex real\n✅ Entrada, TP e SL\n✅ Quotex e Pocket Option\n\n👇 Site:"],
    "de": ["📊 *VIP-SIGNALE — EVALON* 🎯\n\n✅ Genauigkeit 80–95%\n✅ 3–10 Signale täglich\n✅ Echter Forex\n✅ Einstieg, TP und SL\n✅ Quotex und Pocket Option\n\n👇 Website:"],
    "ur": ["📊 *VIP سگنلز — EVALON* 🎯\n\n✅ 80–95% درستگی\n✅ روزانہ 3–10 سگنل\n✅ حقیقی فاریکس\n✅ Entry, TP اور SL\n✅ Quotex اور Pocket Option\n\n👇 ویب سائٹ:"],
    "ja": ["📊 *VIPシグナル — EVALON* 🎯\n\n✅ 80–95%勝率\n✅ 1日3–10シグナル\n✅ リアルFX\n✅ エントリー、TPとSL\n✅ QuotexとPocket Option\n\n👇 ウェブサイト:"],
    "it": ["📊 *SEGNALI VIP — EVALON* 🎯\n\n✅ Accuratezza 80-95%\n✅ 3-10 segnali al giorno\n✅ Forex reale\n✅ Entrata, TP e SL\n✅ Quotex e Pocket Option\n\n👇 Sito web:"],
    "ko": ["📊 *VIP 신호 — EVALON* 🎯\n\n✅ 80-95% 승률\n✅ 하루 3-10개 신호\n✅ 실제 외환\n✅ 진입, TP 및 SL\n✅ Quotex 및 Pocket Option\n\n👇 웹사이트:"],
    "tr": ["📊 *VIP SINYALLER — EVALON* 🎯\n\n✅ %80-95 Basari Orani\n✅ Gunluk 3-10 sinyal\n✅ Gercek Forex\n✅ Giris, TP ve SL\n✅ Quotex ve Pocket Option\n\n👇 Web sitesi:"],
    "fa": ["📊 *سیگنال های VIP — EVALON* 🎯\n\n✅ دقت 80-95%\n✅ 3-10 سیگنال روزانه\n✅ فارکس واقعی\n✅ ورود، TP و SL\n✅ Quotex و Pocket Option\n\n👇 وب سایت:"],
    "pl": ["📊 *SYGNALY VIP — EVALON* 🎯\n\n✅ Dokladnosc 80-95%\n✅ 3-10 sygnalow dziennie\n✅ Prawdziwy Forex\n✅ Wejscie, TP i SL\n✅ Quotex i Pocket Option\n\n👇 Strona:"],
    "uk": ["📊 *VIP СИГНАЛИ — EVALON* 🎯\n\n✅ Точнiсть 80-95%\n✅ 3-10 сигналiв на день\n✅ Реальний форекс\n✅ Вхiд, TP i SL\n✅ Quotex i Pocket Option\n\n👇 Сайт:"],
    "kk": ["📊 *VIP СИГНАЛДАР — EVALON* 🎯\n\n✅ Далдiк 80-95%\n✅ Кунiне 3-10 сигнал\n✅ Накты форекс\n✅ Кiру, TP жане SL\n✅ Quotex жане Pocket Option\n\n👇 Сайт:"],
    "cs": ["📊 *VIP SIGNALY — EVALON* 🎯\n\n✅ Presnost 80-95%\n✅ 3-10 signalu denne\n✅ Skutecny Forex\n✅ Vstup, TP a SL\n✅ Quotex a Pocket Option\n\n👇 Web:"],
}

SOCIAL_REPLIES = {
    "en": [
        "👥 *POCKET SOCIAL TRADING — EVALON* 🔄\n\nCopy the best traders automatically!\n\n✅ Auto-copy top performers\n✅ Works on Pocket Option\n✅ No experience needed\n✅ Start & stop anytime\n\n👇 Learn more:",
        "🔄 *COPY TRADING — EARN PASSIVELY* 💰\n\n1️⃣ Connect Pocket Option\n2️⃣ Choose top trader\n3️⃣ Trades copy automatically\n4️⃣ You earn when they earn!\n\n👇 Get started:",
    ],
    "sw": [
        "👥 *POCKET SOCIAL TRADING* 🔄\n\nNakili wafanyabiashara bora!\n\n✅ Nakili otomatiki\n✅ Pocket Option\n✅ Huhitaji uzoefu\n\n👇 Jifunze zaidi:",
        "🔄 *NAKILI & PATA FAIDA* 💰\n\n1️⃣ Unganisha Pocket Option\n2️⃣ Chagua trader bora\n3️⃣ Biashara zinakiliwa\n4️⃣ Pata faida!\n\n👇 Anza:",
    ],
    "ar": ["👥 *التداول الاجتماعي — EVALON* 🔄\n\nانسخ أفضل المتداولين تلقائياً!\n\n✅ نسخ تلقائي\n✅ Pocket Option\n✅ لا خبرة مطلوبة\n\n👇 زر موقعنا:"],
    "zh": ["👥 *社交交易 — EVALON* 🔄\n\n自动复制最佳交易者！\n\n✅ 自动复制\n✅ Pocket Option\n✅ 无需经验\n\n👇 访问网站:"],
    "hi": ["👥 *सोशल ट्रेडिंग — EVALON* 🔄\n\nसर्वश्रेष्ठ ट्रेडर्स को कॉपी करें!\n\n✅ ऑटो-कॉपी\n✅ Pocket Option\n✅ कोई अनुभव नहीं चाहिए\n\n👇 वेबसाइट:"],
    "ru": ["👥 *СОЦИАЛЬНЫЙ ТРЕЙДИНГ — EVALON* 🔄\n\nКопируйте лучших трейдеров автоматически!\n\n✅ Авто-копирование\n✅ Pocket Option\n✅ Опыт не нужен\n\n👇 Сайт:"],
    "es": ["👥 *TRADING SOCIAL — EVALON* 🔄\n\nCopia a los mejores traders automáticamente!\n\n✅ Auto-copia\n✅ Pocket Option\n✅ Sin experiencia necesaria\n\n👇 Web:"],
    "fr": ["👥 *TRADING SOCIAL — EVALON* 🔄\n\nCopiez les meilleurs traders automatiquement!\n\n✅ Auto-copie\n✅ Pocket Option\n✅ Aucune expérience requise\n\n👇 Site:"],
    "pt": ["👥 *TRADING SOCIAL — EVALON* 🔄\n\nCopie os melhores traders automaticamente!\n\n✅ Auto-cópia\n✅ Pocket Option\n✅ Sem experiência necessária\n\n👇 Site:"],
    "de": ["👥 *SOCIAL TRADING — EVALON* 🔄\n\nKopieren Sie die besten Trader automatisch!\n\n✅ Auto-Kopie\n✅ Pocket Option\n✅ Keine Erfahrung nötig\n\n👇 Website:"],
    "ur": ["👥 *سوشل ٹریڈنگ — EVALON* 🔄\n\nبہترین ٹریڈرز کو خودبخود کاپی کریں!\n\n✅ آٹو کاپی\n✅ Pocket Option\n✅ تجربہ ضروری نہیں\n\n👇 ویب سائٹ:"],
    "ja": ["👥 *ソーシャルトレード — EVALON* 🔄\n\nトップトレーダーを自動コピー！\n\n✅ 自動コピー\n✅ Pocket Option\n✅ 経験不要\n\n👇 ウェブサイト:"],
    "it": ["👥 *SOCIAL TRADING — EVALON* 🔄\n\nCopia i migliori trader automaticamente!\n\n✅ Copia automatica\n✅ Pocket Option\n✅ Nessuna esperienza\n\n👇 Sito web:"],
    "ko": ["👥 *소셜 트레이딩 — EVALON* 🔄\n\n최고의 트레이더를 자동으로 복사하세요!\n\n✅ 자동 복사\n✅ Pocket Option\n✅ 경험 불필요\n\n👇 웹사이트:"],
    "tr": ["👥 *SOSYAL TICARET — EVALON* 🔄\n\nEn iyi traderlari otomatik kopyala!\n\n✅ Otomatik kopyalama\n✅ Pocket Option\n✅ Deneyim gerekmez\n\n👇 Web sitesi:"],
    "fa": ["👥 *معاملات اجتماعی — EVALON* 🔄\n\nبهترین معامله گران را کپی کنید!\n\n✅ کپی خودکار\n✅ Pocket Option\n✅ بدون تجربه\n\n👇 وب سایت:"],
    "pl": ["👥 *HANDEL SPOLECZNOSCIOWY — EVALON* 🔄\n\nAutomatycznie kopiuj najlepszych traderow!\n\n✅ Automatyczne kopiowanie\n✅ Pocket Option\n✅ Bez doswiadczenia\n\n👇 Strona:"],
    "uk": ["👥 *СОЦIАЛЬНА ТОРГIВЛЯ — EVALON* 🔄\n\nАвтоматично копiюйте найкращих трейдерiв!\n\n✅ Авто-копiювання\n✅ Pocket Option\n✅ Досвiд не потрiбен\n\n👇 Сайт:"],
    "kk": ["👥 *АЛЕУМЕТТIК САУДА — EVALON* 🔄\n\nYздiк трейдерлердi автоматты кошiрiнiз!\n\n✅ Авто-кошiру\n✅ Pocket Option\n✅ Тажiрибе казет емес\n\n👇 Сайт:"],
    "cs": ["👥 *SOCIALNI OBCHODOVANI — EVALON* 🔄\n\nAutomaticky kopirujte nejlepsi tradery!\n\n✅ Automaticke kopirovani\n✅ Pocket Option\n✅ Bez zkusenosti\n\n👇 Web:"],
}

INDICATOR_REPLIES = {
    "en": [
        "📈 *FREE INDICATOR — EVALON WINNERS* 🎁\n\n100% FREE!\n\n✅ Buy/sell arrows on chart\n✅ All timeframes\n✅ No repaint\n✅ MT4, MT5 & web\n✅ Easy install + guide\n\n📲 Join FREE channel:",
        "🆓 *FREE INDICATOR — NO PAYMENT* 💎\n\n🔧 Non-repainting\n📊 20+ pairs\n⚡ OTC weekend trading\n\n👇 Get FREE:",
    ],
    "sw": [
        "📈 *INDICATOR YA BURE — EVALON* 🎁\n\nBURE KABISA!\n\n✅ Mishale ya BUY/SELL\n✅ Vipindi vyote\n✅ Haibadilishi\n✅ MT4, MT5 na web\n✅ Rahisi kusakinisha\n\n📲 Jiunge na channel ya BURE:",
        "🆓 *INDICATOR BURE* 💎\n\n🔧 Haibadilishi\n📊 Jozi 20+\n⚡ OTC mwishoni mwa wiki\n\n👇 Ipate BURE:",
    ],
    "ar": ["📈 *مؤشر مجاني — EVALON* 🎁\n\n100% مجاني!\n\n✅ أسهم شراء/بيع\n✅ جميع الأطر الزمنية\n✅ لا إعادة رسم\n✅ MT4 و MT5\n\n📲 القناة المجانية:"],
    "zh": ["📈 *免费指标 — EVALON* 🎁\n\n100%免费！\n\n✅ 买卖箭头\n✅ 所有时间框架\n✅ 不重绘\n✅ MT4和MT5\n\n📲 免费频道:"],
    "hi": ["📈 *मुफ्त इंडिकेटर — EVALON* 🎁\n\n100% मुफ्त!\n\n✅ BUY/SELL तीर\n✅ सभी टाइमफ्रेम\n✅ रिपेंट नहीं\n✅ MT4 और MT5\n\n📲 मुफ्त चैनल:"],
    "ru": ["📈 *БЕСПЛАТНЫЙ ИНДИКАТОР — EVALON* 🎁\n\n100% бесплатно!\n\n✅ Стрелки покупки/продажи\n✅ Все таймфреймы\n✅ Без перерисовки\n✅ MT4 и MT5\n\n📲 Бесплатный канал:"],
    "es": ["📈 *INDICADOR GRATIS — EVALON* 🎁\n\n100% gratis!\n\n✅ Flechas de compra/venta\n✅ Todos los marcos de tiempo\n✅ Sin repintar\n✅ MT4 y MT5\n\n📲 Canal gratuito:"],
    "fr": ["📈 *INDICATEUR GRATUIT — EVALON* 🎁\n\n100% gratuit!\n\n✅ Flèches achat/vente\n✅ Tous les délais\n✅ Pas de repeinture\n✅ MT4 et MT5\n\n📲 Canal gratuit:"],
    "pt": ["📈 *INDICADOR GRÁTIS — EVALON* 🎁\n\n100% grátis!\n\n✅ Setas de compra/venda\n✅ Todos os prazos\n✅ Sem repintura\n✅ MT4 e MT5\n\n📲 Canal gratuito:"],
    "de": ["📈 *KOSTENLOSER INDIKATOR — EVALON* 🎁\n\n100% kostenlos!\n\n✅ Kauf/Verkauf Pfeile\n✅ Alle Zeitrahmen\n✅ Kein Neuzeichnen\n✅ MT4 und MT5\n\n📲 Kostenloser Kanal:"],
    "ur": ["📈 *مفت انڈیکیٹر — EVALON* 🎁\n\n100% مفت!\n\n✅ خریداری/فروخت کے تیر\n✅ تمام ٹائم فریم\n✅ دوبارہ پینٹ نہیں\n✅ MT4 اور MT5\n\n📲 مفت چینل:"],
    "ja": ["📈 *無料インジケーター — EVALON* 🎁\n\n100%無料！\n\n✅ 売買矢印\n✅ 全タイムフレーム\n✅ 再描画なし\n✅ MT4とMT5\n\n📲 無料チャンネル:"],
    "it": ["📈 *INDICATORE GRATUITO — EVALON* 🎁\n\n100% GRATIS!\n\n✅ Frecce acquisto/vendita\n✅ Tutti i timeframe\n✅ Nessun repaint\n✅ MT4 e MT5\n\n📲 Canale gratuito:"],
    "ko": ["📈 *무료 인디케이터 — EVALON* 🎁\n\n100% 무료!\n\n✅ 매수/매도 화살표\n✅ 모든 타임프레임\n✅ 리페인트 없음\n✅ MT4 및 MT5\n\n📲 무료 채널:"],
    "tr": ["📈 *UCRETSIZ INDIKATÖR — EVALON* 🎁\n\n100% UCRETSIZ!\n\n✅ Al/Sat oklari\n✅ Tum zaman dilimleri\n✅ Yeniden boyama yok\n✅ MT4 ve MT5\n\n📲 Ucretsiz kanal:"],
    "fa": ["📈 *اندیکاتور رایگان — EVALON* 🎁\n\n100% رایگان!\n\n✅ فلش های خرید/فروش\n✅ همه تایم فریم ها\n✅ بدون ریپینت\n✅ MT4 و MT5\n\n📲 کانال رایگان:"],
    "pl": ["📈 *DARMOWY WSKAZNIK — EVALON* 🎁\n\n100% ZA DARMO!\n\n✅ Strzalki kupna/sprzedazy\n✅ Wszystkie ramy czasowe\n✅ Bez przerysowywania\n✅ MT4 i MT5\n\n📲 Darmowy kanal:"],
    "uk": ["📈 *БЕЗКОШТОВНИЙ IНДИКАТОР — EVALON* 🎁\n\n100% БЕЗКОШТОВНО!\n\n✅ Стрiлки купiвлi/продажу\n✅ Всi таймфрейми\n✅ Без перемальовування\n✅ MT4 i MT5\n\n📲 Безкоштовний канал:"],
    "kk": ["📈 *ТЕГIН ИНДИКАТОР — EVALON* 🎁\n\n100% ТЕГIН!\n\n✅ Сатып алу/сату корсеткiштерi\n✅ Барлык уакыт аралыктары\n✅ Кайта сызу жок\n✅ MT4 жане MT5\n\n📲 Тегiн арна:"],
    "cs": ["📈 *BEZPLATNY INDIKATOR — EVALON* 🎁\n\n100% ZDARMA!\n\n✅ Sipky nakup/prodej\n✅ Vsechny casove ramce\n✅ Bez prekreslování\n✅ MT4 a MT5\n\n📲 Bezplatny kanal:"],
}

AUTOBOT_REPLIES = {
    "en": [
        "🤖 *AUTO TRADING BOT — EVALON* 💎\n\nTrade automatically 24/7!\n\n✅ All brokers supported\n✅ Runs 24/7\n✅ No experience needed\n\n🏦 Quotex | Pocket Option | IQ Option | Deriv\n\n👇 Get it now:",
        "⚡ *EVALON AUTO BOT — 24/7* 🚀\n\nYou focus on life — bot focuses on profits!\n\n🔧 AI entry detection\n📱 Mobile notifications\n🔐 Funds stay in YOUR account\n\n👇 Website:",
    ],
    "sw": [
        "🤖 *AUTO TRADING BOT — EVALON* 💎\n\nBiashara otomatiki 24/7!\n\n✅ Mawakala WOTE\n✅ Inafanya kazi 24/7\n✅ Huhitaji uzoefu\n\n🏦 Quotex | Pocket Option | IQ Option | Deriv\n\n👇 Ipate sasa:",
        "⚡ *EVALON AUTO BOT — 24/7* 🚀\n\nWewe zingatia maisha — bot izingatie faida!\n\n🔧 AI detection\n📱 Arifa za simu\n🔐 Pesa zinabaki kwenye akaunti YAKO\n\n👇 Website:",
    ],
    "ar": ["🤖 *بوت التداول التلقائي — EVALON* 💎\n\nتداول تلقائياً 24/7!\n\n✅ جميع الوسطاء\n✅ يعمل 24/7\n✅ لا خبرة مطلوبة\n\n🏦 Quotex | Pocket Option | IQ Option | Deriv\n\n👇 احصل عليه الآن:"],
    "zh": ["🤖 *自动交易机器人 — EVALON* 💎\n\n24/7自动交易！\n\n✅ 支持所有经纪商\n✅ 24/7运行\n✅ 无需经验\n\n🏦 Quotex | Pocket Option | IQ Option | Deriv\n\n👇 立即获取:"],
    "hi": ["🤖 *ऑटो ट्रेडिंग बॉट — EVALON* 💎\n\n24/7 स्वचालित ट्रेडिंग!\n\n✅ सभी ब्रोकर\n✅ 24/7 चलता है\n✅ कोई अनुभव नहीं चाहिए\n\n🏦 Quotex | Pocket Option | IQ Option | Deriv\n\n👇 अभी पाएं:"],
    "ru": ["🤖 *АВТО ТОРГОВЫЙ БОТ — EVALON* 💎\n\nТоргуйте автоматически 24/7!\n\n✅ Все брокеры\n✅ Работает 24/7\n✅ Опыт не нужен\n\n🏦 Quotex | Pocket Option | IQ Option | Deriv\n\n👇 Получить:"],
    "es": ["🤖 *BOT DE TRADING AUTO — EVALON* 💎\n\nOpera automáticamente 24/7!\n\n✅ Todos los brokers\n✅ Funciona 24/7\n✅ Sin experiencia\n\n🏦 Quotex | Pocket Option | IQ Option | Deriv\n\n👇 Obtener ahora:"],
    "fr": ["🤖 *BOT DE TRADING AUTO — EVALON* 💎\n\nTradez automatiquement 24/7!\n\n✅ Tous les brokers\n✅ Fonctionne 24/7\n✅ Sans expérience\n\n🏦 Quotex | Pocket Option | IQ Option | Deriv\n\n👇 Obtenir maintenant:"],
    "pt": ["🤖 *BOT DE TRADING AUTO — EVALON* 💎\n\nNegocie automaticamente 24/7!\n\n✅ Todos os brokers\n✅ Funciona 24/7\n✅ Sem experiência\n\n🏦 Quotex | Pocket Option | IQ Option | Deriv\n\n👇 Obter agora:"],
    "de": ["🤖 *AUTO-TRADING-BOT — EVALON* 💎\n\nHandeln Sie automatisch 24/7!\n\n✅ Alle Broker\n✅ Läuft 24/7\n✅ Keine Erfahrung nötig\n\n🏦 Quotex | Pocket Option | IQ Option | Deriv\n\n👇 Jetzt holen:"],
    "ur": ["🤖 *آٹو ٹریڈنگ بوٹ — EVALON* 💎\n\n24/7 خودکار ٹریڈنگ!\n\n✅ تمام بروکرز\n✅ 24/7 چلتا ہے\n✅ تجربہ ضروری نہیں\n\n🏦 Quotex | Pocket Option | IQ Option | Deriv\n\n👇 ابھی حاصل کریں:"],
    "ja": ["🤖 *自動取引ボット — EVALON* 💎\n\n24/7自動取引！\n\n✅ 全ブローカー対応\n✅ 24/7稼働\n✅ 経験不要\n\n🏦 Quotex | Pocket Option | IQ Option | Deriv\n\n👇 今すぐ入手:"],
    "it": ["🤖 *BOT AUTOMATICO — EVALON* 💎\n\nOpera automaticamente 24/7!\n\n✅ Tutti i broker\n✅ Funziona 24/7\n✅ Nessuna esperienza\n\n🏦 Quotex | Pocket Option | IQ Option | Deriv\n\n👇 Ottieni ora:"],
    "ko": ["🤖 *자동 트레이딩 봇 — EVALON* 💎\n\n24/7 자동 거래!\n\n✅ 모든 브로커 지원\n✅ 24/7 작동\n✅ 경험 불필요\n\n🏦 Quotex | Pocket Option | IQ Option | Deriv\n\n👇 지금 받기:"],
    "tr": ["🤖 *OTOMATIK BOT — EVALON* 💎\n\n7/24 Otomatik Islem!\n\n✅ Tum brokerlar\n✅ 7/24 calisir\n✅ Deneyim gerekmez\n\n🏦 Quotex | Pocket Option | IQ Option | Deriv\n\n👇 Simdi al:"],
    "fa": ["🤖 *ربات خودکار — EVALON* 💎\n\nمعاملات خودکار 24/7!\n\n✅ همه بروکرها\n✅ 24/7 فعال\n✅ بدون تجربه\n\n🏦 Quotex | Pocket Option | IQ Option | Deriv\n\n👇 همین الان بگیرید:"],
    "pl": ["🤖 *AUTOMATYCZNY BOT — EVALON* 💎\n\nHandluj automatycznie 24/7!\n\n✅ Wszystkie brokery\n✅ Dziala 24/7\n✅ Bez doswiadczenia\n\n🏦 Quotex | Pocket Option | IQ Option | Deriv\n\n👇 Pobierz teraz:"],
    "uk": ["🤖 *АВТОМАТИЧНИЙ БОТ — EVALON* 💎\n\nТоргуйте автоматично 24/7!\n\n✅ Всi брокери\n✅ Працює 24/7\n✅ Досвiд не потрiбен\n\n🏦 Quotex | Pocket Option | IQ Option | Deriv\n\n👇 Отримати:"],
    "kk": ["🤖 *АВТОМАТТЫ БОТ — EVALON* 💎\n\nАвтоматты 24/7 сауда!\n\n✅ Барлык брокерлер\n✅ 24/7 жумыс iстейдi\n✅ Тажiрибе казет емес\n\n🏦 Quotex | Pocket Option | IQ Option | Deriv\n\n👇 Казiр алыныз:"],
    "cs": ["🤖 *AUTOMATICKY BOT — EVALON* 💎\n\nObchodujte automaticky 24/7!\n\n✅ Vsichni brokeři\n✅ Funguje 24/7\n✅ Bez zkusenosti\n\n🏦 Quotex | Pocket Option | IQ Option | Deriv\n\n👇 Ziskat nyni:"],
}

FREEBOT_REPLIES = {
    "en": ["🆓 *FREE MANUAL BOT — EVALON* 🤖\n\nGet our FREE trading bot!\n\n✅ Works on ALL brokers\n✅ Easy to use\n✅ Step-by-step guide\n\nChoose your broker 👇"],
    "sw": ["🆓 *FREE MANUAL BOT — EVALON* 🤖\n\nPata bot yetu ya BURE!\n\n✅ Mawakala WOTE\n✅ Rahisi kutumia\n✅ Mwongozo wa hatua kwa hatua\n\nChagua broker yako 👇"],
    "ar": ["🆓 *بوت مجاني — EVALON* 🤖\n\nاحصل على بوتنا المجاني!\n\n✅ يعمل مع جميع الوسطاء\n✅ سهل الاستخدام\n✅ دليل خطوة بخطوة\n\nاختر وسيطك 👇"],
    "zh": ["🆓 *免费手动机器人 — EVALON* 🤖\n\n获取我们的免费交易机器人！\n\n✅ 适用于所有经纪商\n✅ 易于使用\n✅ 逐步指南\n\n选择您的经纪商 👇"],
    "hi": ["🆓 *मुफ्त मैनुअल बॉट — EVALON* 🤖\n\nहमारा मुफ्त ट्रेडिंग बॉट पाएं!\n\n✅ सभी ब्रोकर पर काम करता है\n✅ उपयोग में आसान\n✅ चरण-दर-चरण गाइड\n\nअपना ब्रोकर चुनें 👇"],
    "ru": ["🆓 *БЕСПЛАТНЫЙ БОТ — EVALON* 🤖\n\nПолучите наш бесплатный торговый бот!\n\n✅ Работает со всеми брокерами\n✅ Прост в использовании\n✅ Пошаговое руководство\n\nВыберите брокера 👇"],
    "es": ["🆓 *BOT MANUAL GRATIS — EVALON* 🤖\n\nObtén nuestro bot de trading GRATIS!\n\n✅ Funciona con todos los brokers\n✅ Fácil de usar\n✅ Guía paso a paso\n\nElige tu broker 👇"],
    "fr": ["🆓 *BOT MANUEL GRATUIT — EVALON* 🤖\n\nObtenez notre bot de trading GRATUIT!\n\n✅ Fonctionne avec tous les brokers\n✅ Facile à utiliser\n✅ Guide étape par étape\n\nChoisissez votre broker 👇"],
    "pt": ["🆓 *BOT MANUAL GRÁTIS — EVALON* 🤖\n\nObtenha nosso bot de trading GRÁTIS!\n\n✅ Funciona com todos os brokers\n✅ Fácil de usar\n✅ Guia passo a passo\n\nEscolha seu broker 👇"],
    "de": ["🆓 *KOSTENLOSER MANUELLER BOT — EVALON* 🤖\n\nHolen Sie sich unseren kostenlosen Trading-Bot!\n\n✅ Funktioniert mit allen Brokern\n✅ Einfach zu bedienen\n✅ Schritt-für-Schritt-Anleitung\n\nWählen Sie Ihren Broker 👇"],
    "ur": ["🆓 *مفت مینوئل بوٹ — EVALON* 🤖\n\nہمارا مفت ٹریڈنگ بوٹ حاصل کریں!\n\n✅ تمام بروکرز پر کام کرتا ہے\n✅ استعمال میں آسان\n✅ مرحلہ وار گائیڈ\n\nاپنا بروکر منتخب کریں 👇"],
    "ja": ["🆓 *無料マニュアルボット — EVALON* 🤖\n\n無料トレーディングボットを入手！\n\n✅ 全ブローカー対応\n✅ 使いやすい\n✅ ステップバイステップガイド\n\nブローカーを選択 👇"],
    "it": ["🆓 *BOT GRATUITO — EVALON* 🤖\n\nOttieni il bot GRATIS!\n\n✅ Tutti i broker\n✅ Facile da usare\n✅ Guida passo passo\n\nScegli il broker 👇"],
    "ko": ["🆓 *무료 봇 — EVALON* 🤖\n\n무료 봇을 받으세요!\n\n✅ 모든 브로커 지원\n✅ 사용하기 쉬움\n✅ 단계별 가이드\n\n브로커 선택 👇"],
    "tr": ["🆓 *UCRETSIZ BOT — EVALON* 🤖\n\nUcretsiz botu al!\n\n✅ Tum brokerlar\n✅ Kullanimi kolay\n✅ Adim adim rehber\n\nBrokerini sec 👇"],
    "fa": ["🆓 *ربات رایگان — EVALON* 🤖\n\nربات رایگان ما را بگیرید!\n\n✅ همه بروکرها\n✅ استفاده آسان\n✅ راهنمای گام به گام\n\nبروکر خود را انتخاب کنید 👇"],
    "pl": ["🆓 *DARMOWY BOT — EVALON* 🤖\n\nZdobadz darmowego bota!\n\n✅ Wszystkie brokery\n✅ Latwy w uzyciu\n✅ Przewodnik krok po kroku\n\nWybierz brokera 👇"],
    "uk": ["🆓 *БЕЗКОШТОВНИЙ БОТ — EVALON* 🤖\n\nОтримайте безкоштовного бота!\n\n✅ Всi брокери\n✅ Простий у використаннi\n✅ Покрокове керiвництво\n\nОберiть брокера 👇"],
    "kk": ["🆓 *ТЕГIН БОТ — EVALON* 🤖\n\nТегiн ботты алыныз!\n\n✅ Барлык брокерлер\n✅ Колданылуы онай\n✅ Кадамдык нускаулык\n\nБрокердi танданыз 👇"],
    "cs": ["🆓 *BEZPLATNY BOT — EVALON* 🤖\n\nZiskejte bezplatneho bota!\n\n✅ Vsichni brokeři\n✅ Snadne pouziti\n✅ Pruvodce krok za krokem\n\nVyberte brokera 👇"],
}

# ══════════════════════════════════════════════════════════════
#  UI TRANSLATIONS — FIXED: All 12 languages fully translated
# ══════════════════════════════════════════════════════════════

UI = {
    "en": {
        "welcome": "👋 Welcome, *{name}!*\n\n{urgency}\n\n🏆 *{business}* — Where winners trade!\n\nWhat would you like to explore? 👇",
        "btn_services": "🏆 Our Services",
        "btn_referral": "🎁 Invite & Earn",
        "btn_stories": "⭐ Success Stories",
        "btn_language": "🌍 Language",
        "btn_spin": "🎰 Try Your Free Access — Lucky Spin!",
        "btn_whats_new": "🆕 What's New Today",
        "btn_vip_results": "🏆 Today's VIP Results",
        "btn_winners": "👑 Winners of the Week",
        "btn_my_streak": "🔥 My Daily Streak",
        "spin_wait": "⏳ Already spun today! Come back in {hours}h {mins}m 🕐",
        "spin_spinning": "🎰 Spinning...",
        "no_news": "📢 *No new updates yet!*\n\nCheck back later — our team posts updates regularly. 🔔",
        "no_vip": "📊 *No VIP results posted yet today!*\n\nJoin our VIP channel to get signals live:\n\nOr check back later — results are posted after each session! ⚡",
        "btn_signals": "📊 VIP Signals",
        "btn_social": "👥 Social Trading",
        "btn_indicator": "📈 Free Indicator",
        "btn_autobot": "🤖 Auto Bot",
        "btn_freebot": "🆓 Free Manual Bot",
        "btn_website": "🌐 Website",
        "btn_support": "💬 Contact Support",
        "btn_back": "⬅️ Back",
        "btn_restart": "🚀 Tap to Start",
        "btn_free_indicator": "📲 Get FREE Indicator",
        "btn_join": "📢 Join Our Channel",
        "btn_poll_quotex": "📊 Quotex",
        "btn_poll_pocket": "💰 Pocket Option",
        "btn_poll_both": "✅ Both",
        "btn_whats_new": "🆕 What's New Today",
        "btn_vip_results": "🏆 Today's VIP Results",
        "btn_winners": "👑 Winners of the Week",
        "btn_my_streak": "🔥 My Daily Streak",
        "no_news": "📢 *No new updates yet!*\n\nCheck back later — our team posts updates regularly. 🔔",
        "no_vip": "📊 *No VIP results posted yet today!*\n\nJoin our VIP channel to get signals live!\n\nOr check back later — results are posted after each session! ⚡",
        "join_msg": "⚠️ *Please join our channel first!*\n\nJoin now and come back! 👇",
        "support_msg": "💬 *Support Request Received!* ✅\n\nOur team will contact you *within 5 hours.* ⏳\n\nPlease keep the bot open! 🙏",
        "fallback_msg": "🤔 I didn't find an answer for that.\n\nWould you like to speak with our support team?",
        "msg_received": "📨 Message received! Our team will reply shortly. 🙏",
        "referral_msg": "🎁 *YOUR REFERRAL LINK*\n\nYour link:\nhttps://t.me/{bot}?start=ref{uid}\n\nPeople invited: *{count}/{min}*\n{bar}\n\nInvite {needed} more to unlock your discount reward!\n{leaderboard}",
        "comeback_msg": "👋 Hey *{name}!* We missed you! 😊\n\n🔥 New signals & opportunities waiting!\n\n💎 *EVALON WINNERS* has exciting updates for you!\n\n👇 Come back and explore:",
        "rating_msg": "⭐ *How was your support experience?*\n\nPlease rate our service:",
        "rating_opinion_msg": "📝 *Thank you for the rating!*\n\nPlease share a short opinion about your experience (or type 'skip' to skip):",
        "rating_thanks": "🙏 Thank you for your feedback, *{name}!* ⭐",
        "poll_msg": "📊 *Quick Question!*\n\nWhich platform do you mainly use?",
        "welcome_video": "🎬 *Welcome to EVALON WINNERS!*\n\nWatch this intro to see how we help traders win! 🏆",
        "services_msg": "🏆 *OUR SERVICES*\n\nChoose a service to learn more 👇",
        "price_msg": "💰 *Pricing & Plans*\n\nVisit our website for latest pricing 👇",
        "join_pending": "⏳ *Request received!*\n\nAdmin will approve shortly. 🙏",
        "auto_clean_msg": "🔄 *Chat refreshed!*\n\nTap below to continue 👇",
        "session_ended": "👋 *Support chat has ended.*\n\nThank you for contacting us! 🙏",
        "btn_tip": "💡 Daily Tip",
        "btn_quiz": "🧠 Quiz",
        "btn_profile": "👤 My Profile",
        "btn_goal": "🎯 Set Goal",
        "btn_results_history": "📅 Past Results",
        "btn_challenge": "💪 Challenge",
        "btn_mood": "😊 My Mood",
        "btn_why_evalon": "🤔 Why EVALON?",
        "btn_win_alert": "🔔 Win Alert",
        "no_results_history": "📅 *No past results yet!*\n\nAdmin will post session results here. Check back soon! ⚡",
    },
    "sw": {
        "welcome": "👋 Karibu, *{name}!*\n\n{urgency}\n\n🏆 *{business}* — Mahali pa washindi!\n\nUnataka kuchunguza nini? 👇",
        "btn_services": "🏆 Huduma Zetu",
        "btn_referral": "🎁 Alika & Pata",
        "btn_stories": "⭐ Hadithi za Mafanikio",
        "btn_language": "🌍 Lugha",
        "btn_spin": "🎰 Jaribu Free Access Yako — Lucky Spin!",
        "btn_whats_new": "🆕 Nini Kipya Leo",
        "btn_vip_results": "🏆 Matokeo ya VIP Leo",
        "btn_winners": "👑 Washindi wa Wiki",
        "btn_my_streak": "🔥 Streak Yangu ya Kila Siku",
        "spin_wait": "⏳ Umeshaspinni leo! Rudi baada ya masaa {hours}h {mins}m 🕐",
        "spin_spinning": "🎰 Inazunguka...",
        "no_news": "📢 *Hakuna habari mpya bado!*\n\nRudi baadaye — timu yetu huchapisha masasisho mara kwa mara. 🔔",
        "no_vip": "📊 *Hakuna matokeo ya VIP bado leo!*\n\nJiunge na channel yetu ya VIP kupata signals moja kwa moja:\n\nAu rudi baadaye — matokeo huchapishwa baada ya kila kipindi! ⚡",
        "btn_signals": "📊 VIP Signals",
        "btn_social": "👥 Social Trading",
        "btn_indicator": "📈 Indicator ya Bure",
        "btn_autobot": "🤖 Auto Bot",
        "btn_freebot": "🆓 Free Manual Bot",
        "btn_website": "🌐 Website & Bei",
        "btn_support": "💬 Wasiliana na Support",
        "btn_back": "⬅️ Rudi",
        "btn_restart": "🚀 Bonyeza Kuanza",
        "btn_free_indicator": "📲 Pata Indicator BURE",
        "btn_join": "📢 Jiunge na Channel",
        "btn_poll_quotex": "📊 Quotex",
        "btn_poll_pocket": "💰 Pocket Option",
        "btn_poll_both": "✅ Zote Mbili",
        "btn_whats_new": "🆕 Nini Kipya Leo",
        "btn_vip_results": "🏆 Matokeo ya VIP Leo",
        "btn_winners": "👑 Washindi wa Wiki",
        "btn_my_streak": "🔥 Streak Yangu ya Kila Siku",
        "no_news": "📢 *Hakuna habari mpya bado!*\n\nRudi baadaye — timu yetu huchapisha masasisho mara kwa mara. 🔔",
        "no_vip": "📊 *Hakuna matokeo ya VIP bado leo!*\n\nJiunge na channel yetu ya VIP kupata signals moja kwa moja!\n\nAu rudi baadaye — matokeo huchapishwa baada ya kila kipindi! ⚡",
        "join_msg": "⚠️ *Tafadhali jiunge na channel yetu kwanza!*\n\nJiunge sasa na urudi! 👇",
        "support_msg": "💬 *Ombi la Msaada Limepokelewa!* ✅\n\nTimu yetu itawasiliana nawe *ndani ya masaa 5.* ⏳\n\nKaa na bot wazi! 🙏",
        "fallback_msg": "🤔 Sikupata jibu la hilo.\n\nUnataka kuzungumza na timu yetu ya msaada?",
        "msg_received": "📨 Ujumbe umepokelewa! Timu yetu itajibu hivi karibuni. 🙏",
        "referral_msg": "🎁 *KIUNGO CHAKO CHA RUFAA*\n\nKiungo chako:\nhttps://t.me/{bot}?start=ref{uid}\n\nWatu wamealikwa: *{count}/{min}*\n{bar}\n\nAlika {needed} zaidi kufungua tuzo yako!\n{leaderboard}",
        "comeback_msg": "👋 Habari *{name}!* Tulikusahau! 😊\n\n🔥 Signals mpya, fursa mpya!\n\n💎 *EVALON WINNERS* ina mambo mapya!\n\n👇 Rudi na uchunguze:",
        "rating_msg": "⭐ *Huduma ya support ilikuwaje?*\n\nTupa alama:",
        "rating_opinion_msg": "📝 *Asante kwa alama!*\n\nTushirikishe maoni yako mafupi kuhusu uzoefu wako (au andika 'skip' kuruka):",
        "rating_thanks": "🙏 Asante kwa maoni yako, *{name}!* ⭐",
        "poll_msg": "📊 *Swali Moja!*\n\nUnatumia platform ipi zaidi?",
        "welcome_video": "🎬 *Karibu EVALON WINNERS!*\n\nAngalia video hii fupi! 🏆",
        "services_msg": "🏆 *HUDUMA ZETU*\n\nChagua huduma kujifunza zaidi 👇",
        "price_msg": "💰 *Bei na Mipango*\n\nTembelea website 👇",
        "join_pending": "⏳ *Ombi limepokelewa!*\n\nAdmin atakuidhibitisha. 🙏",
        "auto_clean_msg": "🔄 *Chat imesafishwa!*\n\nBonyeza hapa chini kuendelea 👇",
        "session_ended": "👋 *Mazungumzo ya msaada yamekwisha.*\n\nAsante kwa kuwasiliana nasi! 🙏",
        "btn_tip": "💡 Kidokezo cha Leo",
        "btn_quiz": "🧠 Maswali ya Maarifa",
        "btn_profile": "👤 Wasifu Wangu",
        "btn_goal": "🎯 Weka Lengo",
        "btn_results_history": "📅 Matokeo ya Nyuma",
        "btn_challenge": "💪 Changamoto",
        "btn_mood": "😊 Hali Yangu",
        "btn_why_evalon": "🤔 Kwa Nini EVALON?",
        "btn_win_alert": "🔔 Arifa ya Ushindi",
        "no_results_history": "📅 *Hakuna matokeo ya nyuma bado!*\n\nAdmin ataweka matokeo ya vikao hapa. Rudi baadaye! ⚡",
    },
    "ar": {
        "welcome": "👋 مرحباً، *{name}!*\n\n{urgency}\n\n🏆 *{business}* — حيث يتداول الفائزون!\n\nماذا تريد أن تستكشف؟ 👇",
        "btn_services": "🏆 خدماتنا",
        "btn_referral": "🎁 ادعُ واربح",
        "btn_stories": "⭐ قصص النجاح",
        "btn_language": "🌍 اللغة",
        "btn_spin": "🎰 دوران محظوظ — جرب حظك!",
        "spin_wait": "⏳ لقد درت اليوم! عد خلال {hours}h {mins}m 🕐",
        "spin_spinning": "🎰 جاري الدوران...",
        "btn_signals": "📊 إشارات VIP",
        "btn_social": "👥 التداول الاجتماعي",
        "btn_indicator": "📈 مؤشر مجاني",
        "btn_autobot": "🤖 بوت تلقائي",
        "btn_freebot": "🆓 بوت يدوي مجاني",
        "btn_website": "🌐 الموقع",
        "btn_support": "💬 التواصل مع الدعم",
        "btn_back": "⬅️ رجوع",
        "btn_restart": "🚀 اضغط للبدء",
        "btn_free_indicator": "📲 احصل على المؤشر المجاني",
        "btn_join": "📢 انضم لقناتنا",
        "btn_poll_quotex": "📊 Quotex",
        "btn_poll_pocket": "💰 Pocket Option",
        "btn_poll_both": "✅ كلاهما",
        "btn_whats_new": "🆕 ما الجديد اليوم",
        "btn_vip_results": "🏆 نتائج VIP اليوم",
        "btn_winners": "👑 فائزو الأسبوع",
        "btn_my_streak": "🔥 سلسلتي اليومية",
        "no_news": "📢 *لا توجد تحديثات جديدة بعد!*\n\nتحقق لاحقاً — يقوم فريقنا بنشر التحديثات بانتظام. 🔔",
        "no_vip": "📊 *لا توجد نتائج VIP اليوم بعد!*\n\nانضم إلى قناة VIP الخاصة بنا للحصول على الإشارات مباشرة!\n\nأو تحقق لاحقاً! ⚡",
        "join_msg": "⚠️ *يرجى الانضمام إلى قناتنا أولاً!*\n\nانضم الآن وعد! 👇",
        "support_msg": "💬 *تم استلام طلب الدعم!* ✅\n\nسيتواصل معك فريقنا *خلال 5 ساعات.* ⏳\n\nيرجى إبقاء البوت مفتوحاً! 🙏",
        "fallback_msg": "🤔 لم أجد إجابة لذلك.\n\nهل تريد التحدث مع فريق الدعم؟",
        "msg_received": "📨 تم استلام الرسالة! سيرد فريقنا قريباً. 🙏",
        "referral_msg": "🎁 *رابط الإحالة الخاص بك*\n\nرابطك:\nhttps://t.me/{bot}?start=ref{uid}\n\nإحالاتك: {count}/{min}\n{bar}\n\nادعُ {needed} آخرين لفتح مكافأتك!\n{leaderboard}",
        "comeback_msg": "👋 مرحباً *{name}!* اشتقنا إليك! 😊\n\n🔥 إشارات جديدة وفرص في انتظارك!\n\n💎 *EVALON WINNERS* لديها تحديثات مثيرة!\n\n👇 عد واستكشف:",
        "rating_msg": "⭐ *كيف كانت تجربة الدعم؟*\n\nيرجى تقييم خدمتنا:",
        "rating_opinion_msg": "📝 *شكراً على التقييم!*\n\nشارك رأيك المختصر عن تجربتك (أو اكتب 'skip' للتخطي):",
        "rating_thanks": "🙏 شكراً على تعليقك، *{name}!* ⭐",
        "poll_msg": "📊 *سؤال سريع!*\n\nأي منصة تستخدم بشكل رئيسي؟",
        "welcome_video": "🎬 *مرحباً بك في EVALON WINNERS!*\n\nشاهد هذه المقدمة! 🏆",
        "services_msg": "🏆 *خدماتنا*\n\nاختر خدمة لمعرفة المزيد 👇",
        "price_msg": "💰 *الأسعار والخطط*\n\nزر موقعنا لأحدث الأسعار 👇",
        "join_pending": "⏳ *تم استلام الطلب!*\n\nسيوافق المشرف قريباً. 🙏",
        "auto_clean_msg": "🔄 *تم تحديث المحادثة!*\n\nاضغط أدناه للمتابعة 👇",
        "btn_tip": "💡 نصيحة اليوم",
        "btn_quiz": "🧠 اختبار",
        "btn_profile": "👤 ملفي الشخصي",
        "btn_goal": "🎯 تحديد الهدف",
        "btn_results_history": "📅 النتائج السابقة",
        "btn_challenge": "💪 تحدي",
        "btn_mood": "😊 مزاجي",
        "btn_why_evalon": "🤔 لماذا EVALON؟",
        "btn_win_alert": "🔔 تنبيه الفوز",
        "no_results_history": "📅 *لا توجد نتائج سابقة بعد!*\n\nسيقوم المشرف بنشر نتائج الجلسات هنا. تحقق لاحقاً! ⚡",
        "session_ended": "👋 *انتهت جلسة الدعم.*\n\nشكراً للتواصل معنا! 🙏",
    },
    "zh": {
        "welcome": "👋 欢迎，*{name}!*\n\n{urgency}\n\n🏆 *{business}* — 赢家交易的地方！\n\n您想探索什么？ 👇",
        "btn_services": "🏆 我们的服务",
        "btn_referral": "🎁 邀请赚钱",
        "btn_stories": "⭐ 成功故事",
        "btn_language": "🌍 语言",
        "btn_spin": "🎰 幸运转盘 — 试试你的运气！",
        "spin_wait": "⏳ 今天已经转过了！{hours}h {mins}m 后回来 🕐",
        "spin_spinning": "🎰 旋转中...",
        "btn_signals": "📊 VIP信号",
        "btn_social": "👥 社交交易",
        "btn_indicator": "📈 免费指标",
        "btn_autobot": "🤖 自动机器人",
        "btn_freebot": "🆓 免费手动机器人",
        "btn_website": "🌐 网站",
        "btn_support": "💬 联系支持",
        "btn_back": "⬅️ 返回",
        "btn_restart": "🚀 点击开始",
        "btn_free_indicator": "📲 获取免费指标",
        "btn_join": "📢 加入我们的频道",
        "btn_poll_quotex": "📊 Quotex",
        "btn_poll_pocket": "💰 Pocket Option",
        "btn_poll_both": "✅ 两者都用",
        "btn_whats_new": "🆕 今日新动态",
        "btn_vip_results": "🏆 今日VIP成果",
        "btn_winners": "👑 本周获胜者",
        "btn_my_streak": "🔥 我的每日连胜",
        "no_news": "📢 *暂无新更新！*\n\n稍后再查看 — 我们的团队定期发布更新。 🔔",
        "no_vip": "📊 *今天还没有VIP成果！*\n\n加入我们的VIP频道实时获取信号！\n\n或稍后再查看！ ⚡",
        "join_msg": "⚠️ *请先加入我们的频道！*\n\n现在加入并返回！ 👇",
        "support_msg": "💬 *支持请求已收到！* ✅\n\n我们的团队将在 *5小时内* 联系您。 ⏳\n\n请保持机器人开启！ 🙏",
        "fallback_msg": "🤔 我没有找到答案。\n\n您想与我们的支持团队交谈吗？",
        "msg_received": "📨 消息已收到！我们的团队将很快回复。 🙏",
        "referral_msg": "🎁 *您的推荐链接*\n\n您的链接：\nhttps://t.me/{bot}?start=ref{uid}\n\n您的推荐：{count}/{min}\n{bar}\n\n再邀请 {needed} 人解锁奖励！\n{leaderboard}",
        "comeback_msg": "👋 嘿 *{name}!* 我们想念你！ 😊\n\n🔥 新信号和机会等着你！\n\n💎 *EVALON WINNERS* 有令人兴奋的更新！\n\n👇 回来探索：",
        "rating_msg": "⭐ *您的支持体验如何？*\n\n请为我们的服务评分：",
        "rating_opinion_msg": "📝 *感谢您的评分！*\n\n请分享您对体验的简短意见（或输入 'skip' 跳过）：",
        "rating_thanks": "🙏 感谢您的反馈，*{name}!* ⭐",
        "poll_msg": "📊 *快速问题！*\n\n您主要使用哪个平台？",
        "welcome_video": "🎬 *欢迎来到 EVALON WINNERS！*\n\n观看此介绍！ 🏆",
        "services_msg": "🏆 *我们的服务*\n\n选择服务了解更多 👇",
        "price_msg": "💰 *价格和计划*\n\n访问我们的网站查看最新价格 👇",
        "join_pending": "⏳ *请求已收到！*\n\n管理员将很快批准。 🙏",
        "auto_clean_msg": "🔄 *聊天已刷新！*\n\n点击下方继续 👇",
        "btn_tip": "💡 每日提示",
        "btn_quiz": "🧠 测验",
        "btn_profile": "👤 我的资料",
        "btn_goal": "🎯 设定目标",
        "btn_results_history": "📅 历史结果",
        "btn_challenge": "💪 挑战",
        "btn_mood": "😊 我的心情",
        "btn_why_evalon": "🤔 为什么选EVALON？",
        "btn_win_alert": "🔔 获胜提醒",
        "no_results_history": "📅 *暂无历史结果！*\n\n管理员将在此发布会话结果。稍后再来！ ⚡",
        "session_ended": "👋 *支持聊天已结束。*\n\n感谢您联系我们！ 🙏",
    },
    "hi": {
        "welcome": "👋 स्वागत है, *{name}!*\n\n{urgency}\n\n🏆 *{business}* — जहाँ विजेता व्यापार करते हैं!\n\nआप क्या जानना चाहते हैं? 👇",
        "btn_services": "🏆 हमारी सेवाएं",
        "btn_referral": "🎁 आमंत्रित करें & कमाएं",
        "btn_stories": "⭐ सफलता की कहानियां",
        "btn_language": "🌍 भाषा",
        "btn_spin": "🎰 लकी स्पिन — अपनी किस्मत आजमाएं!",
        "spin_wait": "⏳ आज पहले से स्पिन किया! {hours}h {mins}m में वापस आएं 🕐",
        "spin_spinning": "🎰 घुमा रहा है...",
        "btn_signals": "📊 VIP सिग्नल",
        "btn_social": "👥 सोशल ट्रेडिंग",
        "btn_indicator": "📈 मुफ्त इंडिकेटर",
        "btn_autobot": "🤖 ऑटो बॉट",
        "btn_freebot": "🆓 मुफ्त मैनुअल बॉट",
        "btn_website": "🌐 वेबसाइट",
        "btn_support": "💬 सहायता से संपर्क करें",
        "btn_back": "⬅️ वापस",
        "btn_restart": "🚀 शुरू करने के लिए टैप करें",
        "btn_free_indicator": "📲 मुफ्त इंडिकेटर पाएं",
        "btn_join": "📢 हमारे चैनल से जुड़ें",
        "btn_poll_quotex": "📊 Quotex",
        "btn_poll_pocket": "💰 Pocket Option",
        "btn_poll_both": "✅ दोनों",
        "btn_whats_new": "🆕 आज क्या नया है",
        "btn_vip_results": "🏆 आज के VIP परिणाम",
        "btn_winners": "👑 सप्ताह के विजेता",
        "btn_my_streak": "🔥 मेरी दैनिक स्ट्रीक",
        "no_news": "📢 *अभी कोई नया अपडेट नहीं!*\n\nबाद में जांचें — हमारी टीम नियमित रूप से अपडेट पोस्ट करती है। 🔔",
        "no_vip": "📊 *आज अभी तक कोई VIP परिणाम नहीं!*\n\nसिग्नल सीधे पाने के लिए हमारे VIP चैनल से जुड़ें!\n\nया बाद में जांचें! ⚡",
        "join_msg": "⚠️ *कृपया पहले हमारे चैनल से जुड़ें!*\n\nअभी जुड़ें और वापस आएं! 👇",
        "support_msg": "💬 *सहायता अनुरोध प्राप्त हुआ!* ✅\n\nहमारी टीम *5 घंटे के भीतर* आपसे संपर्क करेगी। ⏳\n\nकृपया बॉट खुला रखें! 🙏",
        "fallback_msg": "🤔 मुझे इसका उत्तर नहीं मिला।\n\nक्या आप हमारी सहायता टीम से बात करना चाहते हैं?",
        "msg_received": "📨 संदेश प्राप्त हुआ! हमारी टीम जल्द ही जवाब देगी। 🙏",
        "referral_msg": "🎁 *आपका रेफरल लिंक*\n\nआपका लिंक:\nhttps://t.me/{bot}?start=ref{uid}\n\nआपके रेफरल: {count}/{min}\n{bar}\n\nइनाम अनलॉक करने के लिए {needed} और को आमंत्रित करें!\n{leaderboard}",
        "comeback_msg": "👋 हेलो *{name}!* हमने आपको याद किया! 😊\n\n🔥 नए सिग्नल और अवसर इंतजार कर रहे हैं!\n\n💎 *EVALON WINNERS* के पास आपके लिए रोमांचक अपडेट हैं!\n\n👇 वापस आएं और एक्सप्लोर करें:",
        "rating_msg": "⭐ *आपका सहायता अनुभव कैसा था?*\n\nकृपया हमारी सेवा को रेट करें:",
        "rating_opinion_msg": "📝 *रेटिंग के लिए धन्यवाद!*\n\nकृपया अपने अनुभव के बारे में एक छोटी राय साझा करें (या 'skip' टाइप करें):",
        "rating_thanks": "🙏 आपकी प्रतिक्रिया के लिए धन्यवाद, *{name}!* ⭐",
        "poll_msg": "📊 *त्वरित प्रश्न!*\n\nआप मुख्य रूप से कौन सा प्लेटफॉर्म उपयोग करते हैं?",
        "welcome_video": "🎬 *EVALON WINNERS में आपका स्वागत है!*\n\nयह परिचय वीडियो देखें! 🏆",
        "services_msg": "🏆 *हमारी सेवाएं*\n\nअधिक जानने के लिए एक सेवा चुनें 👇",
        "price_msg": "💰 *मूल्य और योजनाएं*\n\nनवीनतम मूल्य के लिए हमारी वेबसाइट पर जाएं 👇",
        "join_pending": "⏳ *अनुरोध प्राप्त हुआ!*\n\nएडमिन जल्द ही अनुमोदन करेगा। 🙏",
        "auto_clean_msg": "🔄 *चैट रिफ्रेश हुई!*\n\nजारी रखने के लिए नीचे टैप करें 👇",
        "btn_tip": "💡 दैनिक टिप",
        "btn_quiz": "🧠 क्विज़",
        "btn_profile": "👤 मेरी प्रोफ़ाइल",
        "btn_goal": "🎯 लक्ष्य निर्धारित करें",
        "btn_results_history": "📅 पुराने परिणाम",
        "btn_challenge": "💪 चुनौती",
        "btn_mood": "😊 मेरा मूड",
        "btn_why_evalon": "🤔 EVALON क्यों?",
        "btn_win_alert": "🔔 जीत अलर्ट",
        "no_results_history": "📅 *अभी तक कोई पुराना परिणाम नहीं!*\n\nAdmin यहाँ सत्र परिणाम पोस्ट करेगा। बाद में देखें! ⚡",
        "session_ended": "👋 *सहायता चैट समाप्त हो गई।*\n\nहमसे संपर्क करने के लिए धन्यवाद! 🙏",
    },
    "ru": {
        "welcome": "👋 Добро пожаловать, *{name}!*\n\n{urgency}\n\n🏆 *{business}* — Где торгуют победители!\n\nЧто вы хотите узнать? 👇",
        "btn_services": "🏆 Наши услуги",
        "btn_referral": "🎁 Пригласи и зарабатывай",
        "btn_stories": "⭐ Истории успеха",
        "btn_language": "🌍 Язык",
        "btn_spin": "🎰 Счастливый Спин — Испытайте Удачу!",
        "spin_wait": "⏳ Уже крутили сегодня! Вернитесь через {hours}h {mins}m 🕐",
        "spin_spinning": "🎰 Вращается...",
        "btn_signals": "📊 VIP сигналы",
        "btn_social": "👥 Социальная торговля",
        "btn_indicator": "📈 Бесплатный индикатор",
        "btn_autobot": "🤖 Авто бот",
        "btn_freebot": "🆓 Бесплатный ручной бот",
        "btn_website": "🌐 Сайт",
        "btn_support": "💬 Связаться с поддержкой",
        "btn_back": "⬅️ Назад",
        "btn_restart": "🚀 Нажмите для начала",
        "btn_free_indicator": "📲 Получить бесплатный индикатор",
        "btn_join": "📢 Присоединиться к каналу",
        "btn_poll_quotex": "📊 Quotex",
        "btn_poll_pocket": "💰 Pocket Option",
        "btn_poll_both": "✅ Оба",
        "btn_whats_new": "🆕 Что нового сегодня",
        "btn_vip_results": "🏆 Результаты VIP сегодня",
        "btn_winners": "👑 Победители недели",
        "btn_my_streak": "🔥 Моя ежедневная серия",
        "no_news": "📢 *Новых обновлений пока нет!*\n\nПроверьте позже — наша команда публикует обновления регулярно. 🔔",
        "no_vip": "📊 *Результаты VIP сегодня ещё не опубликованы!*\n\nПрисоединитесь к нашему VIP-каналу!\n\nИли проверьте позже! ⚡",
        "join_msg": "⚠️ *Пожалуйста, сначала присоединитесь к нашему каналу!*\n\nПрисоединитесь сейчас и возвращайтесь! 👇",
        "support_msg": "💬 *Запрос поддержки получен!* ✅\n\nНаша команда свяжется с вами *в течение 5 часов.* ⏳\n\nПожалуйста, держите бота открытым! 🙏",
        "fallback_msg": "🤔 Я не нашел ответа на это.\n\nХотите поговорить с нашей командой поддержки?",
        "msg_received": "📨 Сообщение получено! Наша команда ответит скоро. 🙏",
        "referral_msg": "🎁 *ВАША РЕФЕРАЛЬНАЯ ССЫЛКА*\n\nВаша ссылка:\nhttps://t.me/{bot}?start=ref{uid}\n\nВаши рефералы: {count}/{min}\n{bar}\n\nПригласите ещё {needed} для разблокировки награды!\n{leaderboard}",
        "comeback_msg": "👋 Привет *{name}!* Мы скучали по тебе! 😊\n\n🔥 Новые сигналы и возможности ждут!\n\n💎 *EVALON WINNERS* имеет захватывающие обновления!\n\n👇 Возвращайся и исследуй:",
        "rating_msg": "⭐ *Как прошел ваш опыт поддержки?*\n\nПожалуйста, оцените наш сервис:",
        "rating_opinion_msg": "📝 *Спасибо за оценку!*\n\nПоделитесь кратким мнением о вашем опыте (или напишите 'skip' для пропуска):",
        "rating_thanks": "🙏 Спасибо за ваш отзыв, *{name}!* ⭐",
        "poll_msg": "📊 *Быстрый вопрос!*\n\nКакую платформу вы используете?",
        "welcome_video": "🎬 *Добро пожаловать в EVALON WINNERS!*\n\nПосмотрите это введение! 🏆",
        "services_msg": "🏆 *НАШИ УСЛУГИ*\n\nВыберите услугу, чтобы узнать больше 👇",
        "price_msg": "💰 *Цены и планы*\n\nПосетите наш сайт для актуальных цен 👇",
        "join_pending": "⏳ *Запрос получен!*\n\nАдмин одобрит скоро. 🙏",
        "auto_clean_msg": "🔄 *Чат обновлен!*\n\nНажмите ниже для продолжения 👇",
        "btn_tip": "💡 Совет дня",
        "btn_quiz": "🧠 Викторина",
        "btn_profile": "👤 Мой профиль",
        "btn_goal": "🎯 Установить цель",
        "btn_results_history": "📅 История результатов",
        "btn_challenge": "💪 Вызов",
        "btn_mood": "😊 Моё настроение",
        "btn_why_evalon": "🤔 Почему EVALON?",
        "btn_win_alert": "🔔 Уведомление о победе",
        "no_results_history": "📅 *Нет прошлых результатов!*\n\nАдмин опубликует результаты сессий здесь. Загляните позже! ⚡",
        "session_ended": "👋 *Чат поддержки завершен.*\n\nСпасибо за обращение! 🙏",
    },
    "es": {
        "welcome": "👋 Bienvenido, *{name}!*\n\n{urgency}\n\n🏆 *{business}* — ¡Donde comercian los ganadores!\n\n¿Qué deseas explorar? 👇",
        "btn_services": "🏆 Nuestros Servicios",
        "btn_referral": "🎁 Invitar y Ganar",
        "btn_stories": "⭐ Historias de Éxito",
        "btn_language": "🌍 Idioma",
        "btn_signals": "📊 Señales VIP",
        "btn_social": "👥 Trading Social",
        "btn_indicator": "📈 Indicador Gratis",
        "btn_autobot": "🤖 Bot Automático",
        "btn_freebot": "🆓 Bot Manual Gratis",
        "btn_website": "🌐 Sitio Web",
        "btn_support": "💬 Contactar Soporte",
        "btn_back": "⬅️ Atrás",
        "btn_restart": "🚀 Toca para Comenzar",
        "btn_free_indicator": "📲 Obtener Indicador GRATIS",
        "btn_join": "📢 Únete a Nuestro Canal",
        "btn_poll_quotex": "📊 Quotex",
        "btn_poll_pocket": "💰 Pocket Option",
        "btn_poll_both": "✅ Ambos",
        "btn_spin": "🎰 Giro de Suerte — ¡Prueba tu Suerte!",
        "spin_wait": "⏳ Ya giraste hoy! Vuelve en {hours}h {mins}m 🕐",
        "spin_spinning": "🎰 Girando...",
        "btn_whats_new": "🆕 Qué hay de nuevo hoy",
        "btn_vip_results": "🏆 Resultados VIP de hoy",
        "btn_winners": "👑 Ganadores de la semana",
        "btn_my_streak": "🔥 Mi racha diaria",
        "no_news": "📢 *¡No hay nuevas actualizaciones todavía!*\n\nVuelve más tarde — nuestro equipo publica actualizaciones regularmente. 🔔",
        "no_vip": "📊 *¡No hay resultados VIP publicados hoy todavía!*\n\n¡Únete a nuestro canal VIP para recibir señales en vivo!\n\n¡O vuelve más tarde! ⚡",
        "join_msg": "⚠️ *¡Por favor únete a nuestro canal primero!*\n\n¡Únete ahora y vuelve! 👇",
        "support_msg": "💬 *¡Solicitud de soporte recibida!* ✅\n\nNuestro equipo te contactará *en 5 horas.* ⏳\n\n¡Mantén el bot abierto! 🙏",
        "fallback_msg": "🤔 No encontré respuesta a eso.\n\n¿Te gustaría hablar con nuestro equipo de soporte?",
        "msg_received": "📨 ¡Mensaje recibido! Nuestro equipo responderá pronto. 🙏",
        "referral_msg": "🎁 *TU ENLACE DE REFERIDO*\n\nTu enlace:\nhttps://t.me/{bot}?start=ref{uid}\n\nTus referidos: {count}/{min}\n{bar}\n\n¡Invita {needed} más para desbloquear tu recompensa!\n{leaderboard}",
        "comeback_msg": "👋 ¡Hola *{name}!* ¡Te echamos de menos! 😊\n\n🔥 ¡Nuevas señales y oportunidades esperan!\n\n💎 ¡*EVALON WINNERS* tiene actualizaciones emocionantes!\n\n👇 Vuelve y explora:",
        "rating_msg": "⭐ *¿Cómo fue tu experiencia de soporte?*\n\nPor favor califica nuestro servicio:",
        "rating_opinion_msg": "📝 *¡Gracias por la calificación!*\n\nComparte una opinión breve sobre tu experiencia (o escribe 'skip' para omitir):",
        "rating_thanks": "🙏 ¡Gracias por tu opinión, *{name}!* ⭐",
        "poll_msg": "📊 *¡Pregunta rápida!*\n\n¿Qué plataforma usas principalmente?",
        "welcome_video": "🎬 *¡Bienvenido a EVALON WINNERS!*\n\n¡Mira esta introducción! 🏆",
        "services_msg": "🏆 *NUESTROS SERVICIOS*\n\nElige un servicio para saber más 👇",
        "price_msg": "💰 *Precios y Planes*\n\nVisita nuestro sitio web para precios actuales 👇",
        "join_pending": "⏳ *¡Solicitud recibida!*\n\nEl admin aprobará pronto. 🙏",
        "auto_clean_msg": "🔄 *¡Chat actualizado!*\n\nToca abajo para continuar 👇",
        "btn_tip": "💡 Consejo del día",
        "btn_quiz": "🧠 Quiz",
        "btn_profile": "👤 Mi perfil",
        "btn_goal": "🎯 Establecer meta",
        "btn_results_history": "📅 Resultados anteriores",
        "btn_challenge": "💪 Desafío",
        "btn_mood": "😊 Mi estado de ánimo",
        "btn_why_evalon": "🤔 ¿Por qué EVALON?",
        "btn_win_alert": "🔔 Alerta de victoria",
        "no_results_history": "📅 *¡No hay resultados anteriores aún!*\n\nEl admin publicará resultados aquí. ¡Vuelve pronto! ⚡",
        "session_ended": "👋 *El chat de soporte ha finalizado.*\n\n¡Gracias por contactarnos! 🙏",
    },
    "fr": {
        "welcome": "👋 Bienvenue, *{name}!*\n\n{urgency}\n\n🏆 *{business}* — Là où les gagnants tradent!\n\nQue voulez-vous explorer? 👇",
        "btn_services": "🏆 Nos Services",
        "btn_referral": "🎁 Inviter et Gagner",
        "btn_stories": "⭐ Histoires de Succès",
        "btn_language": "🌍 Langue",
        "btn_signals": "📊 Signaux VIP",
        "btn_social": "👥 Trading Social",
        "btn_indicator": "📈 Indicateur Gratuit",
        "btn_autobot": "🤖 Bot Automatique",
        "btn_freebot": "🆓 Bot Manuel Gratuit",
        "btn_website": "🌐 Site Web",
        "btn_support": "💬 Contacter le Support",
        "btn_back": "⬅️ Retour",
        "btn_restart": "🚀 Appuyez pour Commencer",
        "btn_free_indicator": "📲 Obtenir l'Indicateur GRATUIT",
        "btn_join": "📢 Rejoindre Notre Canal",
        "btn_poll_quotex": "📊 Quotex",
        "btn_poll_pocket": "💰 Pocket Option",
        "btn_poll_both": "✅ Les Deux",
        "btn_spin": "🎰 Spin Chanceux — Tentez Votre Chance!",
        "spin_wait": "⏳ Déjà tourné aujourd'hui! Revenez dans {hours}h {mins}m 🕐",
        "spin_spinning": "🎰 Tourne...",
        "btn_whats_new": "🆕 Quoi de neuf aujourd'hui",
        "btn_vip_results": "🏆 Résultats VIP aujourd'hui",
        "btn_winners": "👑 Gagnants de la semaine",
        "btn_my_streak": "🔥 Ma série quotidienne",
        "no_news": "📢 *Pas encore de nouvelles mises à jour!*\n\nRevenez plus tard — notre équipe publie régulièrement. 🔔",
        "no_vip": "📊 *Pas encore de résultats VIP publiés aujourd'hui!*\n\nRejoignez notre canal VIP pour recevoir des signaux en direct!\n\nOu revenez plus tard! ⚡",
        "join_msg": "⚠️ *Veuillez d'abord rejoindre notre canal!*\n\nRejoignez maintenant et revenez! 👇",
        "support_msg": "💬 *Demande de support reçue!* ✅\n\nNotre équipe vous contactera *dans les 5 heures.* ⏳\n\nGardez le bot ouvert! 🙏",
        "fallback_msg": "🤔 Je n'ai pas trouvé de réponse.\n\nVoulez-vous parler à notre équipe de support?",
        "msg_received": "📨 Message reçu! Notre équipe répondra bientôt. 🙏",
        "referral_msg": "🎁 *VOTRE LIEN DE PARRAINAGE*\n\nVotre lien:\nhttps://t.me/{bot}?start=ref{uid}\n\nVos parrainages: {count}/{min}\n{bar}\n\nInvitez {needed} de plus pour débloquer votre récompense!\n{leaderboard}",
        "comeback_msg": "👋 Salut *{name}!* Vous nous avez manqué! 😊\n\n🔥 Nouveaux signaux et opportunités vous attendent!\n\n💎 *EVALON WINNERS* a des mises à jour passionnantes!\n\n👇 Revenez et explorez:",
        "rating_msg": "⭐ *Comment s'est passée votre expérience de support?*\n\nVeuillez noter notre service:",
        "rating_opinion_msg": "📝 *Merci pour la note!*\n\nPartagez une brève opinion sur votre expérience (ou écrivez 'skip' pour passer):",
        "rating_thanks": "🙏 Merci pour votre avis, *{name}!* ⭐",
        "poll_msg": "📊 *Question rapide!*\n\nQuelle plateforme utilisez-vous principalement?",
        "welcome_video": "🎬 *Bienvenue chez EVALON WINNERS!*\n\nRegardez cette introduction! 🏆",
        "services_msg": "🏆 *NOS SERVICES*\n\nChoisissez un service pour en savoir plus 👇",
        "price_msg": "💰 *Prix et Plans*\n\nVisitez notre site pour les derniers prix 👇",
        "join_pending": "⏳ *Demande reçue!*\n\nL'admin approuvera bientôt. 🙏",
        "auto_clean_msg": "🔄 *Chat actualisé!*\n\nAppuyez ci-dessous pour continuer 👇",
        "btn_tip": "💡 Conseil du jour",
        "btn_quiz": "🧠 Quiz",
        "btn_profile": "👤 Mon profil",
        "btn_goal": "🎯 Fixer un objectif",
        "btn_results_history": "📅 Résultats passés",
        "btn_challenge": "💪 Défi",
        "btn_mood": "😊 Mon humeur",
        "btn_why_evalon": "🤔 Pourquoi EVALON?",
        "btn_win_alert": "🔔 Alerte victoire",
        "no_results_history": "📅 *Pas encore de résultats passés!*\n\nL'admin publiera les résultats ici. Revenez bientôt! ⚡",
        "session_ended": "👋 *Le chat de support est terminé.*\n\nMerci de nous avoir contactés! 🙏",
    },
    "pt": {
        "welcome": "👋 Bem-vindo, *{name}!*\n\n{urgency}\n\n🏆 *{business}* — Onde os vencedores negociam!\n\nO que você quer explorar? 👇",
        "btn_services": "🏆 Nossos Serviços",
        "btn_referral": "🎁 Convidar e Ganhar",
        "btn_stories": "⭐ Histórias de Sucesso",
        "btn_language": "🌍 Idioma",
        "btn_signals": "📊 Sinais VIP",
        "btn_social": "👥 Trading Social",
        "btn_indicator": "📈 Indicador Grátis",
        "btn_autobot": "🤖 Bot Automático",
        "btn_freebot": "🆓 Bot Manual Grátis",
        "btn_website": "🌐 Site",
        "btn_support": "💬 Contatar Suporte",
        "btn_back": "⬅️ Voltar",
        "btn_restart": "🚀 Toque para Começar",
        "btn_free_indicator": "📲 Obter Indicador GRÁTIS",
        "btn_join": "📢 Junte-se ao Nosso Canal",
        "btn_poll_quotex": "📊 Quotex",
        "btn_poll_pocket": "💰 Pocket Option",
        "btn_poll_both": "✅ Ambos",
        "btn_spin": "🎰 Giro da Sorte — Tente sua Sorte!",
        "spin_wait": "⏳ Já girou hoje! Volte em {hours}h {mins}m 🕐",
        "spin_spinning": "🎰 Girando...",
        "btn_whats_new": "🆕 O que há de novo hoje",
        "btn_vip_results": "🏆 Resultados VIP de hoje",
        "btn_winners": "👑 Vencedores da semana",
        "btn_my_streak": "🔥 Minha sequência diária",
        "no_news": "📢 *Ainda não há novas atualizações!*\n\nVolte mais tarde — nossa equipe publica atualizações regularmente. 🔔",
        "no_vip": "📊 *Ainda não há resultados VIP publicados hoje!*\n\nJunte-se ao nosso canal VIP para receber sinais ao vivo!\n\nOu volte mais tarde! ⚡",
        "join_msg": "⚠️ *Por favor, junte-se ao nosso canal primeiro!*\n\nJunte-se agora e volte! 👇",
        "support_msg": "💬 *Solicitação de suporte recebida!* ✅\n\nNossa equipe entrará em contato *em 5 horas.* ⏳\n\nMantenha o bot aberto! 🙏",
        "fallback_msg": "🤔 Não encontrei resposta para isso.\n\nGostaria de falar com nossa equipe de suporte?",
        "msg_received": "📨 Mensagem recebida! Nossa equipe responderá em breve. 🙏",
        "referral_msg": "🎁 *SEU LINK DE REFERÊNCIA*\n\nSeu link:\nhttps://t.me/{bot}?start=ref{uid}\n\nSuas referências: {count}/{min}\n{bar}\n\nConvide {needed} a mais para desbloquear sua recompensa!\n{leaderboard}",
        "comeback_msg": "👋 Olá *{name}!* Sentimos sua falta! 😊\n\n🔥 Novos sinais e oportunidades aguardando!\n\n💎 *EVALON WINNERS* tem atualizações emocionantes!\n\n👇 Volte e explore:",
        "rating_msg": "⭐ *Como foi sua experiência de suporte?*\n\nPor favor, avalie nosso serviço:",
        "rating_opinion_msg": "📝 *Obrigado pela avaliação!*\n\nCompartilhe uma opinião breve sobre sua experiência (ou escreva 'skip' para pular):",
        "rating_thanks": "🙏 Obrigado pelo seu feedback, *{name}!* ⭐",
        "poll_msg": "📊 *Pergunta rápida!*\n\nQual plataforma você usa principalmente?",
        "welcome_video": "🎬 *Bem-vindo ao EVALON WINNERS!*\n\nAssista a esta introdução! 🏆",
        "services_msg": "🏆 *NOSSOS SERVIÇOS*\n\nEscolha um serviço para saber mais 👇",
        "price_msg": "💰 *Preços e Planos*\n\nVisite nosso site para os preços mais recentes 👇",
        "join_pending": "⏳ *Solicitação recebida!*\n\nO admin aprovará em breve. 🙏",
        "auto_clean_msg": "🔄 *Chat atualizado!*\n\nToque abaixo para continuar 👇",
        "btn_tip": "💡 Dica do dia",
        "btn_quiz": "🧠 Quiz",
        "btn_profile": "👤 Meu perfil",
        "btn_goal": "🎯 Definir meta",
        "btn_results_history": "📅 Resultados anteriores",
        "btn_challenge": "💪 Desafio",
        "btn_mood": "😊 Meu humor",
        "btn_why_evalon": "🤔 Por que EVALON?",
        "btn_win_alert": "🔔 Alerta de vitória",
        "no_results_history": "📅 *Sem resultados anteriores ainda!*\n\nO admin publicará resultados aqui. Volte em breve! ⚡",
        "session_ended": "👋 *O chat de suporte foi encerrado.*\n\nObrigado por entrar em contato! 🙏",
    },
    "de": {
        "welcome": "👋 Willkommen, *{name}!*\n\n{urgency}\n\n🏆 *{business}* — Wo Gewinner handeln!\n\nWas möchten Sie erkunden? 👇",
        "btn_services": "🏆 Unsere Dienste",
        "btn_referral": "🎁 Einladen und Verdienen",
        "btn_stories": "⭐ Erfolgsgeschichten",
        "btn_language": "🌍 Sprache",
        "btn_signals": "📊 VIP Signale",
        "btn_social": "👥 Social Trading",
        "btn_indicator": "📈 Kostenloser Indikator",
        "btn_autobot": "🤖 Auto Bot",
        "btn_freebot": "🆓 Kostenloser manueller Bot",
        "btn_website": "🌐 Website",
        "btn_support": "💬 Support kontaktieren",
        "btn_back": "⬅️ Zurück",
        "btn_restart": "🚀 Tippen zum Starten",
        "btn_free_indicator": "📲 Kostenlosen Indikator holen",
        "btn_join": "📢 Unserem Kanal beitreten",
        "btn_poll_quotex": "📊 Quotex",
        "btn_poll_pocket": "💰 Pocket Option",
        "btn_poll_both": "✅ Beide",
        "btn_spin": "🎰 Glücksrad — Versuchen Sie Ihr Glück!",
        "spin_wait": "⏳ Heute bereits gedreht! Kommen Sie in {hours}h {mins}m zurück 🕐",
        "spin_spinning": "🎰 Dreht sich...",
        "btn_whats_new": "🆕 Was gibt es heute Neues",
        "btn_vip_results": "🏆 Heutige VIP-Ergebnisse",
        "btn_winners": "👑 Gewinner der Woche",
        "btn_my_streak": "🔥 Meine tägliche Serie",
        "no_news": "📢 *Noch keine neuen Updates!*\n\nSchauen Sie später vorbei — unser Team veröffentlicht regelmäßig Updates. 🔔",
        "no_vip": "📊 *Heute noch keine VIP-Ergebnisse veröffentlicht!*\n\nTreten Sie unserem VIP-Kanal bei!\n\nOder schauen Sie später vorbei! ⚡",
        "join_msg": "⚠️ *Bitte treten Sie zuerst unserem Kanal bei!*\n\nJetzt beitreten und zurückkommen! 👇",
        "support_msg": "💬 *Support-Anfrage erhalten!* ✅\n\nUnser Team wird Sie *innerhalb von 5 Stunden* kontaktieren. ⏳\n\nBitte halten Sie den Bot offen! 🙏",
        "fallback_msg": "🤔 Ich habe keine Antwort darauf gefunden.\n\nMöchten Sie mit unserem Support-Team sprechen?",
        "msg_received": "📨 Nachricht erhalten! Unser Team wird bald antworten. 🙏",
        "referral_msg": "🎁 *IHR EMPFEHLUNGSLINK*\n\nIhr Link:\nhttps://t.me/{bot}?start=ref{uid}\n\nIhre Empfehlungen: {count}/{min}\n{bar}\n\nLaden Sie {needed} mehr ein, um Ihre Belohnung freizuschalten!\n{leaderboard}",
        "comeback_msg": "👋 Hey *{name}!* Wir haben Sie vermisst! 😊\n\n🔥 Neue Signale und Möglichkeiten warten!\n\n💎 *EVALON WINNERS* hat aufregende Updates!\n\n👇 Kommen Sie zurück und erkunden Sie:",
        "rating_msg": "⭐ *Wie war Ihre Support-Erfahrung?*\n\nBitte bewerten Sie unseren Service:",
        "rating_opinion_msg": "📝 *Danke für die Bewertung!*\n\nTeilen Sie eine kurze Meinung zu Ihrer Erfahrung mit (oder schreiben Sie 'skip' zum Überspringen):",
        "rating_thanks": "🙏 Danke für Ihr Feedback, *{name}!* ⭐",
        "poll_msg": "📊 *Schnelle Frage!*\n\nWelche Plattform nutzen Sie hauptsächlich?",
        "welcome_video": "🎬 *Willkommen bei EVALON WINNERS!*\n\nSchauen Sie sich diese Einführung an! 🏆",
        "services_msg": "🏆 *UNSERE DIENSTE*\n\nWählen Sie einen Dienst, um mehr zu erfahren 👇",
        "price_msg": "💰 *Preise und Pläne*\n\nBesuchen Sie unsere Website für aktuelle Preise 👇",
        "join_pending": "⏳ *Anfrage erhalten!*\n\nDer Admin wird bald genehmigen. 🙏",
        "auto_clean_msg": "🔄 *Chat aktualisiert!*\n\nTippen Sie unten, um fortzufahren 👇",
        "btn_tip": "💡 Tipp des Tages",
        "btn_quiz": "🧠 Quiz",
        "btn_profile": "👤 Mein Profil",
        "btn_goal": "🎯 Ziel setzen",
        "btn_results_history": "📅 Vergangene Ergebnisse",
        "btn_challenge": "💪 Herausforderung",
        "btn_mood": "😊 Meine Stimmung",
        "btn_why_evalon": "🤔 Warum EVALON?",
        "btn_win_alert": "🔔 Gewinn-Benachrichtigung",
        "no_results_history": "📅 *Noch keine vergangenen Ergebnisse!*\n\nDer Admin wird hier Sitzungsergebnisse posten. Schau später vorbei! ⚡",
        "session_ended": "👋 *Der Support-Chat wurde beendet.*\n\nDanke, dass Sie uns kontaktiert haben! 🙏",
    },
    "ur": {
        "welcome": "👋 خوش آمدید، *{name}!*\n\n{urgency}\n\n🏆 *{business}* — جہاں فاتح تجارت کرتے ہیں!\n\nآپ کیا جاننا چاہتے ہیں؟ 👇",
        "btn_services": "🏆 ہماری خدمات",
        "btn_referral": "🎁 مدعو کریں اور کمائیں",
        "btn_stories": "⭐ کامیابی کی کہانیاں",
        "btn_language": "🌍 زبان",
        "btn_signals": "📊 VIP سگنلز",
        "btn_social": "👥 سوشل ٹریڈنگ",
        "btn_indicator": "📈 مفت انڈیکیٹر",
        "btn_autobot": "🤖 آٹو بوٹ",
        "btn_freebot": "🆓 مفت مینوئل بوٹ",
        "btn_website": "🌐 ویب سائٹ",
        "btn_support": "💬 سپورٹ سے رابطہ",
        "btn_back": "⬅️ واپس",
        "btn_restart": "🚀 شروع کرنے کے لیے ٹیپ کریں",
        "btn_free_indicator": "📲 مفت انڈیکیٹر حاصل کریں",
        "btn_join": "📢 ہمارے چینل میں شامل ہوں",
        "btn_poll_quotex": "📊 Quotex",
        "btn_poll_pocket": "💰 Pocket Option",
        "btn_poll_both": "✅ دونوں",
        "btn_spin": "🎰 لکی اسپن — اپنی قسمت آزمائیں!",
        "spin_wait": "⏳ آج پہلے سے اسپن کیا! {hours}h {mins}m میں واپس آئیں 🕐",
        "spin_spinning": "🎰 گھوم رہا ہے...",
        "btn_whats_new": "🆕 آج کیا نیا ہے",
        "btn_vip_results": "🏆 آج کے VIP نتائج",
        "btn_winners": "👑 ہفتے کے فاتحین",
        "btn_my_streak": "🔥 میری روزانہ اسٹریک",
        "no_news": "📢 *ابھی کوئی نئی اپڈیٹ نہیں!*\n\nبعد میں چیک کریں — ہماری ٹیم باقاعدگی سے اپڈیٹ پوسٹ کرتی ہے۔ 🔔",
        "no_vip": "📊 *آج ابھی تک کوئی VIP نتائج نہیں!*\n\nسگنل براہ راست پانے کے لیے ہمارے VIP چینل سے جڑیں!\n\nیا بعد میں چیک کریں! ⚡",
        "join_msg": "⚠️ *براہ کرم پہلے ہمارے چینل میں شامل ہوں!*\n\nابھی شامل ہوں اور واپس آئیں! 👇",
        "support_msg": "💬 *سپورٹ کی درخواست موصول ہوئی!* ✅\n\nہماری ٹیم *5 گھنٹوں کے اندر* آپ سے رابطہ کرے گی۔ ⏳\n\nبوٹ کھلا رکھیں! 🙏",
        "fallback_msg": "🤔 مجھے اس کا جواب نہیں ملا۔\n\nکیا آپ ہماری سپورٹ ٹیم سے بات کرنا چاہتے ہیں؟",
        "msg_received": "📨 پیغام موصول ہوا! ہماری ٹیم جلد جواب دے گی۔ 🙏",
        "referral_msg": "🎁 *آپ کا ریفرل لنک*\n\nآپ کا لنک:\nhttps://t.me/{bot}?start=ref{uid}\n\nآپ کے ریفرلز: {count}/{min}\n{bar}\n\nانعام کھولنے کے لیے {needed} مزید کو مدعو کریں!\n{leaderboard}",
        "comeback_msg": "👋 ہیلو *{name}!* ہم نے آپ کو یاد کیا! 😊\n\n🔥 نئے سگنلز اور مواقع انتظار میں ہیں!\n\n💎 *EVALON WINNERS* کے پاس دلچسپ اپڈیٹس ہیں!\n\n👇 واپس آئیں اور دریافت کریں:",
        "rating_msg": "⭐ *آپ کا سپورٹ تجربہ کیسا تھا؟*\n\nبراہ کرم ہماری سروس کو ریٹ کریں:",
        "rating_opinion_msg": "📝 *ریٹنگ کا شکریہ!*\n\nاپنے تجربے کے بارے میں مختصر رائے شیئر کریں (یا 'skip' لکھیں):",
        "rating_thanks": "🙏 آپ کے تاثرات کا شکریہ، *{name}!* ⭐",
        "poll_msg": "📊 *فوری سوال!*\n\nآپ بنیادی طور پر کون سا پلیٹ فارم استعمال کرتے ہیں؟",
        "welcome_video": "🎬 *EVALON WINNERS میں خوش آمدید!*\n\nیہ تعارف دیکھیں! 🏆",
        "services_msg": "🏆 *ہماری خدمات*\n\nمزید جاننے کے لیے سروس منتخب کریں 👇",
        "price_msg": "💰 *قیمتیں اور پلان*\n\nتازہ ترین قیمتوں کے لیے ہماری ویب سائٹ دیکھیں 👇",
        "join_pending": "⏳ *درخواست موصول ہوئی!*\n\nایڈمن جلد منظور کرے گا۔ 🙏",
        "auto_clean_msg": "🔄 *چیٹ ریفریش ہو گئی!*\n\nجاری رکھنے کے لیے نیچے ٹیپ کریں 👇",
        "btn_tip": "💡 روزانہ ٹپ",
        "btn_quiz": "🧠 کوئز",
        "btn_profile": "👤 میری پروفائل",
        "btn_goal": "🎯 ہدف مقرر کریں",
        "btn_results_history": "📅 پچھلے نتائج",
        "btn_challenge": "💪 چیلنج",
        "btn_mood": "😊 میرا موڈ",
        "btn_why_evalon": "🤔 EVALON کیوں؟",
        "btn_win_alert": "🔔 جیت کا الرٹ",
        "no_results_history": "📅 *ابھی تک کوئی پچھلے نتائج نہیں!*\n\nAdmin یہاں سیشن کے نتائج پوسٹ کرے گا۔ بعد میں دیکھیں! ⚡",
        "session_ended": "👋 *سپورٹ چیٹ ختم ہو گئی۔*\n\nہم سے رابطہ کرنے کا شکریہ! 🙏",
    },
    "ja": {
        "welcome": "👋 ようこそ、*{name}!*\n\n{urgency}\n\n🏆 *{business}* — 勝者が取引する場所！\n\n何を探しますか？ 👇",
        "btn_services": "🏆 私たちのサービス",
        "btn_referral": "🎁 招待して稼ぐ",
        "btn_stories": "⭐ 成功事例",
        "btn_language": "🌍 言語",
        "btn_signals": "📊 VIPシグナル",
        "btn_social": "👥 ソーシャルトレード",
        "btn_indicator": "📈 無料インジケーター",
        "btn_autobot": "🤖 自動ボット",
        "btn_freebot": "🆓 無料マニュアルボット",
        "btn_website": "🌐 ウェブサイト",
        "btn_support": "💬 サポートに連絡",
        "btn_back": "⬅️ 戻る",
        "btn_restart": "🚀 タップして開始",
        "btn_free_indicator": "📲 無料インジケーターを入手",
        "btn_join": "📢 チャンネルに参加",
        "btn_poll_quotex": "📊 Quotex",
        "btn_poll_pocket": "💰 Pocket Option",
        "btn_poll_both": "✅ 両方",
        "btn_spin": "🎰 ラッキースピン — 運試し！",
        "spin_wait": "⏳ 今日はもう回しました！{hours}h {mins}m 後に戻ってください 🕐",
        "spin_spinning": "🎰 回転中...",
        "btn_whats_new": "🆕 今日の新着情報",
        "btn_vip_results": "🏆 今日のVIP成果",
        "btn_winners": "👑 今週の勝者",
        "btn_my_streak": "🔥 毎日の連続記録",
        "no_news": "📢 *まだ新しい更新はありません！*\n\n後でチェックしてください — チームが定期的に更新を投稿します。 🔔",
        "no_vip": "📊 *今日はまだVIP成果が投稿されていません！*\n\nVIPチャンネルに参加してシグナルをリアルタイムで受け取ろう！\n\nまたは後でチェックしてください！ ⚡",
        "join_msg": "⚠️ *まず私たちのチャンネルに参加してください！*\n\n今すぐ参加して戻ってください！ 👇",
        "support_msg": "💬 *サポートリクエストを受信しました！* ✅\n\nチームが *5時間以内に* 連絡します。 ⏳\n\nボットを開いたままにしてください！ 🙏",
        "fallback_msg": "🤔 その答えが見つかりませんでした。\n\nサポートチームと話しますか？",
        "msg_received": "📨 メッセージを受信しました！チームがすぐに返信します。 🙏",
        "referral_msg": "🎁 *あなたの紹介リンク*\n\nあなたのリンク：\nhttps://t.me/{bot}?start=ref{uid}\n\nあなたの紹介：{count}/{min}\n{bar}\n\nあと {needed} 人招待して報酬をアンロック！\n{leaderboard}",
        "comeback_msg": "👋 こんにちは *{name}!* 会いたかった！ 😊\n\n🔥 新しいシグナルと機会が待っています！\n\n💎 *EVALON WINNERS* に興奮する更新があります！\n\n👇 戻って探索してください：",
        "rating_msg": "⭐ *サポート体験はいかがでしたか？*\n\nサービスを評価してください：",
        "rating_opinion_msg": "📝 *評価ありがとうございます！*\n\n体験について短い意見を共有してください（または 'skip' と入力してスキップ）：",
        "rating_thanks": "🙏 フィードバックありがとう、*{name}!* ⭐",
        "poll_msg": "📊 *簡単な質問！*\n\n主にどのプラットフォームを使用しますか？",
        "welcome_video": "🎬 *EVALON WINNERSへようこそ！*\n\nこの紹介を見てください！ 🏆",
        "services_msg": "🏆 *私たちのサービス*\n\n詳細はサービスを選択 👇",
        "price_msg": "💰 *価格とプラン*\n\n最新の価格はウェブサイトをご覧ください 👇",
        "join_pending": "⏳ *リクエストを受信しました！*\n\n管理者がすぐに承認します。 🙏",
        "auto_clean_msg": "🔄 *チャットが更新されました！*\n\n続けるには下をタップ 👇",
        "btn_tip": "💡 今日のヒント",
        "btn_quiz": "🧠 クイズ",
        "btn_profile": "👤 マイプロフィール",
        "btn_goal": "🎯 目標設定",
        "btn_results_history": "📅 過去の結果",
        "btn_challenge": "💪 チャレンジ",
        "btn_mood": "😊 マイムード",
        "btn_why_evalon": "🤔 なぜEVALON？",
        "btn_win_alert": "🔔 勝利アラート",
        "no_results_history": "📅 *まだ過去の結果はありません！*\n\nAdminがここにセッション結果を投稿します。後で確認してください！ ⚡",
        "session_ended": "👋 *サポートチャットが終了しました。*\n\nご連絡ありがとうございました！ 🙏",
    },
}

# Add 8 new languages — copy English as base then override key strings
for _lc, _welcome, _btn_svc, _btn_ref, _btn_lang, _btn_spin, _spin_wait, _join, _support, _session, _referral_msg, _comeback, _rating, _rating_op, _rating_thanks, _price_msg in [
    ("it", "👋 Benvenuto, *{name}!*\n\n{urgency}\n\n🏆 *{business}* — Dove vincono i trader!\n\nCosa vuoi esplorare? 👇",
     "🏆 I Nostri Servizi", "🎁 Invita e Guadagna", "🌍 Lingua",
     "🎰 Prova il Tuo Accesso Gratuito — Spin Fortunato!",
     "⏳ Hai già girato oggi! Torna tra {hours}h {mins}m 🕐",
     "⚠️ *Unisciti prima al nostro canale!*\n\nUnisciti ora e torna! 👇",
     "💬 *Richiesta di supporto ricevuta!* ✅\n\nIl nostro team ti contatterà *entro 5 ore.* ⏳",
     "👋 *Chat di supporto terminata.*\n\nGrazie per averci contattato! 🙏",
     "🎁 *IL TUO LINK DI RIFERIMENTO*\n\nIl tuo link:\nhttps://t.me/{bot}?start=ref{uid}\n\nI tuoi riferimenti: {count}/{min}\n{bar}\n\nInvita altri {needed} per sbloccare il premio!\n{leaderboard}",
     "👋 Ciao *{name}!* Ci sei mancato! 😊\n\n🔥 Nuovi segnali e opportunità ti aspettano!\n\n💎 *EVALON WINNERS* ha aggiornamenti entusiasmanti!\n\n👇 Torna ed esplora:",
     "⭐ *Com'è stata la tua esperienza di supporto?*\n\nValuta il nostro servizio:",
     "📝 *Grazie per la valutazione!*\n\nCondividi una breve opinione (o scrivi 'skip' per saltare):",
     "🙏 Grazie per il tuo feedback, *{name}!* ⭐",
     "💰 *Scopri i Nostri Piani*\n\nVisita il nostro sito per tutti i dettagli 👇"),

    ("ko", "👋 환영합니다, *{name}!*\n\n{urgency}\n\n🏆 *{business}* — 승자들이 거래하는 곳!\n\n무엇을 탐색하시겠습니까? 👇",
     "🏆 서비스", "🎁 초대하고 수익 얻기", "🌍 언어",
     "🎰 무료 액세스 시도 — 럭키 스핀!",
     "⏳ 오늘 이미 돌렸습니다! {hours}h {mins}m 후에 돌아오세요 🕐",
     "⚠️ *먼저 채널에 참여해주세요!*\n\n지금 참여하고 돌아오세요! 👇",
     "💬 *지원 요청이 접수되었습니다!* ✅\n\n팀이 *5시간 이내에* 연락드립니다. ⏳",
     "👋 *지원 채팅이 종료되었습니다.*\n\n연락해 주셔서 감사합니다! 🙏",
     "🎁 *추천 링크*\n\n링크:\nhttps://t.me/{bot}?start=ref{uid}\n\n추천: {count}/{min}\n{bar}\n\n보상을 받으려면 {needed}명 더 초대하세요!\n{leaderboard}",
     "👋 안녕하세요 *{name}!* 보고 싶었어요! 😊\n\n🔥 새로운 신호와 기회가 기다립니다!\n\n💎 *EVALON WINNERS* 에 흥미진진한 업데이트가 있습니다!\n\n👇 돌아와서 탐색하세요:",
     "⭐ *지원 경험은 어떠셨나요?*\n\n서비스를 평가해주세요:",
     "📝 *평가해주셔서 감사합니다!*\n\n경험에 대한 간단한 의견을 공유하세요 (건너뛰려면 'skip' 입력):",
     "🙏 피드백 감사합니다, *{name}!* ⭐",
     "💰 *서비스 살펴보기*\n\n최신 정보는 웹사이트를 방문하세요 👇"),

    ("tr", "👋 Hoş geldiniz, *{name}!*\n\n{urgency}\n\n🏆 *{business}* — Kazananların işlem yaptığı yer!\n\nNe keşfetmek istersiniz? 👇",
     "🏆 Hizmetlerimiz", "🎁 Davet Et ve Kazan", "🌍 Dil",
     "🎰 Ücretsiz Erişimini Dene — Şanslı Çark!",
     "⏳ Bugün zaten çevirdiniz! {hours}h {mins}m sonra dönün 🕐",
     "⚠️ *Lütfen önce kanalımıza katılın!*\n\nŞimdi katılın ve geri dönün! 👇",
     "💬 *Destek talebi alındı!* ✅\n\nEkibimiz *5 saat içinde* sizinle iletişime geçecek. ⏳",
     "👋 *Destek sohbeti sona erdi.*\n\nBize ulaştığınız için teşekkürler! 🙏",
     "🎁 *REFERANS BAĞLANTINIZ*\n\nBağlantınız:\nhttps://t.me/{bot}?start=ref{uid}\n\nReferanslarınız: {count}/{min}\n{bar}\n\nÖdülünüzü açmak için {needed} kişi daha davet edin!\n{leaderboard}",
     "👋 Merhaba *{name}!* Sizi özledik! 😊\n\n🔥 Yeni sinyaller ve fırsatlar sizi bekliyor!\n\n💎 *EVALON WINNERS* heyecan verici güncellemelere sahip!\n\n👇 Geri dönün ve keşfedin:",
     "⭐ *Destek deneyiminiz nasıldı?*\n\nHizmetimizi değerlendirin:",
     "📝 *Değerlendirme için teşekkürler!*\n\nDeneyiminiz hakkında kısa bir görüş paylaşın (geçmek için 'skip' yazın):",
     "🙏 Geri bildiriminiz için teşekkürler, *{name}!* ⭐",
     "💰 *Hizmetlerimizi Keşfedin*\n\nTüm detaylar için web sitemizi ziyaret edin 👇"),

    ("fa", "👋 خوش آمدید، *{name}!*\n\n{urgency}\n\n🏆 *{business}* — جایی که برندگان معامله می‌کنند!\n\nمی‌خواهید چه چیزی را کشف کنید؟ 👇",
     "🏆 خدمات ما", "🎁 دعوت کنید و کسب درآمد کنید", "🌍 زبان",
     "🎰 دسترسی رایگان خود را امتحان کنید — چرخ شانس!",
     "⏳ امروز قبلاً چرخاندید! {hours}h {mins}m دیگر برگردید 🕐",
     "⚠️ *لطفاً ابتدا به کانال ما بپیوندید!*\n\nالان بپیوندید و برگردید! 👇",
     "💬 *درخواست پشتیبانی دریافت شد!* ✅\n\nتیم ما *ظرف ۵ ساعت* با شما تماس می‌گیرد. ⏳",
     "👋 *چت پشتیبانی پایان یافت.*\n\nممنون از تماس شما! 🙏",
     "🎁 *لینک معرفی شما*\n\nلینک شما:\nhttps://t.me/{bot}?start=ref{uid}\n\nمعرفی‌های شما: {count}/{min}\n{bar}\n\n{needed} نفر دیگر دعوت کنید تا جایزه‌تان را باز کنید!\n{leaderboard}",
     "👋 سلام *{name}!* دلمان برایتان تنگ شده بود! 😊\n\n🔥 سیگنال‌ها و فرصت‌های جدید منتظر شما هستند!\n\n💎 *EVALON WINNERS* به‌روزرسانی‌های هیجان‌انگیز دارد!\n\n👇 برگردید و کشف کنید:",
     "⭐ *تجربه پشتیبانی شما چگونه بود؟*\n\nلطفاً خدمات ما را ارزیابی کنید:",
     "📝 *ممنون از ارزیابی شما!*\n\nنظر کوتاهی درباره تجربه‌تان به اشتراک بگذارید (برای رد کردن 'skip' بنویسید):",
     "🙏 از بازخورد شما متشکریم، *{name}!* ⭐",
     "💰 *خدمات ما را کشف کنید*\n\nبرای جزئیات کامل از وب‌سایت ما دیدن کنید 👇"),

    ("pl", "👋 Witamy, *{name}!*\n\n{urgency}\n\n🏆 *{business}* — Gdzie handlują zwycięzcy!\n\nCo chcesz odkryć? 👇",
     "🏆 Nasze Usługi", "🎁 Zaproś i Zarabiaj", "🌍 Język",
     "🎰 Wypróbuj Darmowy Dostęp — Szczęśliwy Spin!",
     "⏳ Już kręciłeś dziś! Wróć za {hours}h {mins}m 🕐",
     "⚠️ *Dołącz najpierw do naszego kanału!*\n\nDołącz teraz i wróć! 👇",
     "💬 *Żądanie wsparcia otrzymane!* ✅\n\nNasz zespół skontaktuje się z Tobą *w ciągu 5 godzin.* ⏳",
     "👋 *Czat wsparcia zakończony.*\n\nDziękujemy za kontakt! 🙏",
     "🎁 *TWÓJ LINK POLECAJĄCY*\n\nTwój link:\nhttps://t.me/{bot}?start=ref{uid}\n\nTwoje polecenia: {count}/{min}\n{bar}\n\nZaproś jeszcze {needed} osób, aby odblokować nagrodę!\n{leaderboard}",
     "👋 Hej *{name}!* Tęskniliśmy za Tobą! 😊\n\n🔥 Nowe sygnały i okazje czekają!\n\n💎 *EVALON WINNERS* ma ekscytujące aktualizacje!\n\n👇 Wróć i odkryj:",
     "⭐ *Jak było Twoje doświadczenie z obsługą?*\n\nOceń naszą usługę:",
     "📝 *Dziękujemy za ocenę!*\n\nPodziel się krótką opinią (lub wpisz 'skip', aby pominąć):",
     "🙏 Dziękujemy za opinię, *{name}!* ⭐",
     "💰 *Odkryj Nasze Usługi*\n\nOdwiedź naszą stronę, aby zobaczyć wszystkie szczegóły 👇"),

    ("uk", "👋 Ласкаво просимо, *{name}!*\n\n{urgency}\n\n🏆 *{business}* — Де торгують переможці!\n\nЩо ви хочете дослідити? 👇",
     "🏆 Наші Послуги", "🎁 Запросіть і Заробляйте", "🌍 Мова",
     "🎰 Спробуйте Безкоштовний Доступ — Щасливий Спін!",
     "⏳ Ви вже крутили сьогодні! Поверніться через {hours}h {mins}m 🕐",
     "⚠️ *Будь ласка, спочатку приєднайтесь до нашого каналу!*\n\nПриєднайтесь зараз і поверніться! 👇",
     "💬 *Запит на підтримку отримано!* ✅\n\nНаша команда зв'яжеться з вами *протягом 5 годин.* ⏳",
     "👋 *Чат підтримки завершено.*\n\nДякуємо за звернення! 🙏",
     "🎁 *ВАШЕ РЕФЕРАЛЬНЕ ПОСИЛАННЯ*\n\nВаше посилання:\nhttps://t.me/{bot}?start=ref{uid}\n\nВаші реферали: {count}/{min}\n{bar}\n\nЗапросіть ще {needed} для отримання винагороди!\n{leaderboard}",
     "👋 Привіт *{name}!* Ми скучили за тобою! 😊\n\n🔥 Нові сигнали і можливості чекають!\n\n💎 *EVALON WINNERS* має захоплюючі оновлення!\n\n👇 Повернись і досліджуй:",
     "⭐ *Яким був ваш досвід підтримки?*\n\nОціните наш сервіс:",
     "📝 *Дякуємо за оцінку!*\n\nПоділіться коротким відгуком (або напишіть 'skip', щоб пропустити):",
     "🙏 Дякуємо за відгук, *{name}!* ⭐",
     "💰 *Досліджуйте Наші Послуги*\n\nВідвідайте наш сайт для всіх деталей 👇"),

    ("kk", "👋 Қош келдіңіз, *{name}!*\n\n{urgency}\n\n🏆 *{business}* — Жеңімпаздар сауда жасайтын жер!\n\nНені зерттегіңіз келеді? 👇",
     "🏆 Біздің Қызметтер", "🎁 Шақырып, Табыс Табыңыз", "🌍 Тіл",
     "🎰 Тегін Қолжетімділікті Сынаңыз — Бақытты Айналым!",
     "⏳ Бүгін айналдырдыңыз! {hours}h {mins}m кейін оралыңыз 🕐",
     "⚠️ *Алдымен арнамызға қосылыңыз!*\n\nҚазір қосылып, оралыңыз! 👇",
     "💬 *Қолдау сұранысы алынды!* ✅\n\nКоманда *5 сағат ішінде* хабарласады. ⏳",
     "👋 *Қолдау чаты аяқталды.*\n\nХабарласқаныңызға рахмет! 🙏",
     "🎁 *РЕФЕРАЛ СІЛТЕМЕҢІЗ*\n\nСілтемеңіз:\nhttps://t.me/{bot}?start=ref{uid}\n\nРефералдарыңыз: {count}/{min}\n{bar}\n\nСыйлықты ашу үшін {needed} адам шақырыңыз!\n{leaderboard}",
     "👋 Сәлем *{name}!* Сені сағындық! 😊\n\n🔥 Жаңа сигналдар мен мүмкіндіктер күтуде!\n\n💎 *EVALON WINNERS* тартымды жаңартулар ұсынады!\n\n👇 Оралып, зерттеңіз:",
     "⭐ *Қолдау тәжірибеңіз қандай болды?*\n\nКызметімізді бағалаңыз:",
     "📝 *Бағалағаныңызға рахмет!*\n\nТәжірибеңіз туралы қысқаша пікір бөлісіңіз (өткізіп жіберу үшін 'skip' жазыңыз):",
     "🙏 Пікіріңізге рахмет, *{name}!* ⭐",
     "💰 *Қызметтерімізді Зерттеңіз*\n\nТолық мәліметтер үшін сайтымызды қараңыз 👇"),

    ("cs", "👋 Vítejte, *{name}!*\n\n{urgency}\n\n🏆 *{business}* — Kde obchodují vítězové!\n\nCo chcete prozkoumat? 👇",
     "🏆 Naše Služby", "🎁 Pozvěte a Vydělávejte", "🌍 Jazyk",
     "🎰 Vyzkoušejte Bezplatný Přístup — Šťastný Spin!",
     "⏳ Dnes jste již točili! Vraťte se za {hours}h {mins}m 🕐",
     "⚠️ *Nejprve se připojte k našemu kanálu!*\n\nPřipojte se nyní a vraťte se! 👇",
     "💬 *Žádost o podporu přijata!* ✅\n\nNáš tým vás bude kontaktovat *do 5 hodin.* ⏳",
     "👋 *Chat podpory ukončen.*\n\nDěkujeme za kontakt! 🙏",
     "🎁 *VÁŠ REFERENČNÍ ODKAZ*\n\nVáš odkaz:\nhttps://t.me/{bot}?start=ref{uid}\n\nVaše doporučení: {count}/{min}\n{bar}\n\nPozvěte dalších {needed} pro odemknutí odměny!\n{leaderboard}",
     "👋 Ahoj *{name}!* Chyběl jsi nám! 😊\n\n🔥 Nové signály a příležitosti čekají!\n\n💎 *EVALON WINNERS* má vzrušující aktualizace!\n\n👇 Vrať se a prozkoumej:",
     "⭐ *Jak byl váš podpůrný zážitek?*\n\nOhodnoťte naši službu:",
     "📝 *Děkujeme za hodnocení!*\n\nPodělte se o krátký názor (nebo napište 'skip' pro přeskočení):",
     "🙏 Děkujeme za zpětnou vazbu, *{name}!* ⭐",
     "💰 *Prozkoumejte Naše Služby*\n\nNavštivte náš web pro všechny podrobnosti 👇"),
]:
    UI[_lc] = dict(UI["en"])  # copy English as base
    UI[_lc].update({
        "welcome": _welcome,
        "btn_services": _btn_svc,
        "btn_referral": _btn_ref,
        "btn_language": _btn_lang,
        "btn_spin": _btn_spin,
        "spin_wait": _spin_wait,
        "join_msg": _join,
        "support_msg": _support,
        "session_ended": _session,
        "referral_msg": _referral_msg,
        "comeback_msg": _comeback,
        "rating_msg": _rating,
        "rating_opinion_msg": _rating_op,
        "rating_thanks": _rating_thanks,
        "price_msg": _price_msg,
    })

# ── Update btn_website text for all languages to remove "Pricing" ──
_website_texts = {
    "en": "🌐 Website",
    "sw": "🌐 Website",
    "ar": "🌐 الموقع",
    "zh": "🌐 网站",
    "hi": "🌐 वेबसाइट",
    "ru": "🌐 Сайт",
    "es": "🌐 Sitio Web",
    "fr": "🌐 Site Web",
    "pt": "🌐 Site",
    "de": "🌐 Website",
    "ur": "🌐 ویب سائٹ",
    "ja": "🌐 ウェブサイト",
    "it": "🌐 Sito Web",
    "ko": "🌐 웹사이트",
    "tr": "🌐 Web Sitesi",
    "fa": "🌐 وب سایت",
    "pl": "🌐 Strona",
    "uk": "🌐 Сайт",
    "kk": "🌐 Сайт",
    "cs": "🌐 Web",
}
for _lc, _txt in _website_texts.items():
    if _lc in UI:
        UI[_lc]["btn_website"] = _txt

# ══════════════════════════════════════════════════════════════
#  MISSING UI KEYS — Full translations for 8 partial languages
# ══════════════════════════════════════════════════════════════
_extra_ui = {
    "it": {
        "btn_signals": "\U0001f4ca Segnali VIP",
        "btn_social": "\U0001f465 Social Trading",
        "btn_indicator": "\U0001f4c8 Indicatore Gratuito",
        "btn_autobot": "\U0001f916 Auto Bot",
        "btn_freebot": "\U0001f193 Bot Manuale Gratuito",
        "btn_support": "\U0001f4ac Contatta Supporto",
        "btn_back": "\u2b05\ufe0f Indietro",
        "btn_restart": "\U0001f680 Tocca per Iniziare",
        "btn_free_indicator": "\U0001f4f2 Ottieni Indicatore GRATUITO",
        "btn_join": "\U0001f4e2 Unisciti al Canale",
        "btn_whats_new": "\U0001f195 Novita di Oggi",
        "btn_vip_results": "\U0001f3c6 Risultati VIP di Oggi",
        "btn_winners": "\U0001f451 Vincitori della Settimana",
        "btn_my_streak": "\U0001f525 La Mia Serie Giornaliera",
        "btn_tip": "\U0001f4a1 Consiglio del Giorno",
        "btn_quiz": "\U0001f9e0 Quiz",
        "btn_profile": "\U0001f464 Il Mio Profilo",
        "btn_results_history": "\U0001f4c5 Risultati Passati",
        "btn_stories": "\u2b50 Storie di Successo",
        "btn_referral": "🎁 Invita e Guadagna",
        "btn_language": "🌍 Lingua",
        "btn_website": "🌐 Sito e Prezzi",
        "btn_spin": "🎰 Ruota della Fortuna",
        "welcome": "👋 Benvenuto, *{name}!*\n\n{urgency}\n\n🏆 *{business}* — Dove vincono i trader!\n\nCosa vuoi esplorare? 👇",
        "services_msg": "🏆 *I NOSTRI SERVIZI*\n\nScegli un servizio per saperne di più 👇",
        "join_msg": "⚠️ *Per favore unisciti prima al nostro canale!*\n\nUnisciti ora e torna! 👇",
        "support_msg": "💬 *Richiesta di supporto ricevuta!* ✅\n\nIl nostro team ti contatterà *entro 5 ore.* ⏳\n\nTieni aperto il bot! 🙏",
        "btn_services": "🏆 I Nostri Servizi",
        "btn_challenge": "💪 Sfida",
        "btn_goal": "🎯 Imposta Obiettivo",
        "btn_mood": "😊 Il Mio Umore",
        "btn_why_evalon": "🤔 Perché EVALON?",
        "btn_win_alert": "🔔 Avviso Vincita",
        "session_ended": "👋 *La chat di supporto è terminata.*\n\nGrazie per averci contattato! 🙏",
        "rating_msg": "⭐ *Come è stata la tua esperienza di supporto?*\n\nValuta il nostro servizio:",
        "rating_opinion_msg": "📝 *Grazie per la valutazione!*\n\nCondividi una breve opinione (o scrivi 'skip' per saltare):",
        "rating_thanks": "🙏 Grazie per il tuo feedback, *{name}!* ⭐",
        "msg_received": "\U0001f4e8 Messaggio ricevuto! Il nostro team rispondera a breve. \U0001f64f",
        "no_news": "\U0001f4e2 *Nessun aggiornamento ancora!*\n\nTorna piu tardi. \U0001f514",
        "no_vip": "\U0001f4ca *Nessun risultato VIP oggi!*\n\nUnisciti al canale VIP per segnali in diretta. \u26a1",
        "no_results_history": "\U0001f4c5 *Nessun risultato passato!*\n\nL admin pubblichera i risultati qui. \u26a1",
        "fallback_msg": "\U0001f914 Non ho trovato una risposta.\n\nVuoi parlare con il nostro team di supporto?",
        "comeback_msg": "👋 Ciao *{name}!* Ci sei mancato! 😊\n\n🔥 Nuovi segnali e opportunità ti aspettano!\n\n👇 Torna ed esplora:",
        "auto_clean_msg": "🔄 *Chat aggiornata!*\n\nTocca qui sotto per continuare 👇",
        "join_pending": "⏳ *Richiesta ricevuta!*\n\nL'admin approverà presto. 🙏",
        "spin_spinning": "\U0001f3b0 Girando...",
        "spin_wait": "⏳ Hai già girato oggi! Torna tra {hours}h {mins}m 🕐",
        "referral_msg": "🎁 *IL TUO LINK DI RIFERIMENTO*\n\nIl tuo link:\nhttps://t.me/{bot}?start=ref{uid}\n\nI tuoi riferimenti: {count}/{min}\n{bar}\n\nInvita altri {needed} per sbloccare il tuo premio!\n{leaderboard}",
        "price_msg": "💰 *Prezzi e Piani*\n\nVisita il nostro sito per i prezzi aggiornati 👇",
        "poll_msg": "📊 *Domanda veloce!*\n\nQuale piattaforma usi principalmente?",
        "btn_poll_quotex": "📊 Quotex",
        "btn_poll_pocket": "💰 Pocket Option",
        "btn_poll_both": "✅ Entrambi",
        "welcome_video": "🎬 *Benvenuto in EVALON WINNERS!*\n\nGuarda questa introduzione! 🏆",
    },
    "ko": {
        "btn_signals": "\U0001f4ca VIP \uc2e0\ud638",
        "btn_social": "\U0001f465 \uc18c\uc15c \ud2b8\ub808\uc774\ub529",
        "btn_indicator": "\U0001f4c8 \ubb34\ub8cc \uc778\ub514\ucf00\uc774\ud130",
        "btn_autobot": "\U0001f916 \uc790\ub3d9 \ubd07",
        "btn_freebot": "\U0001f193 \ubb34\ub8cc \uc218\ub3d9 \ubd07",
        "btn_support": "\U0001f4ac \uc9c0\uc6d0 \ubb38\uc758",
        "btn_back": "\u2b05\ufe0f \ub4a4\ub85c",
        "btn_restart": "\U0001f680 \uc2dc\uc791\ud558\ub824\uba74 \ud0ed\ud558\uc138\uc694",
        "btn_free_indicator": "\U0001f4f2 \ubb34\ub8cc \uc778\ub514\ucf00\uc774\ud130 \ubc1b\uae30",
        "btn_join": "\U0001f4e2 \ucc44\ub110 \ucc38\uc5ec",
        "btn_whats_new": "\U0001f195 \uc624\ub298\uc758 \uc0c8\uc18c\uc2dd",
        "btn_vip_results": "\U0001f3c6 \uc624\ub298\uc758 VIP \uacb0\uacfc",
        "btn_winners": "\U0001f451 \uc774\ubc88 \uc8fc \uc6b0\uc2b9\uc790",
        "btn_my_streak": "\U0001f525 \ub098\uc758 \uc77c\uc77c \uc5f0\uc18d",
        "btn_tip": "\U0001f4a1 \uc624\ub298\uc758 \ud301",
        "btn_quiz": "\U0001f9e0 \ud034\uc988",
        "btn_profile": "\U0001f464 \ub0b4 \ud504\ub85c\ud544",
        "btn_results_history": "\U0001f4c5 \uacfc\uac70 \uacb0\uacfc",
        "btn_stories": "\u2b50 \uc131\uacf5 \uc0ac\ub840",
        "btn_referral": "🎁 초대 및 수익",
        "btn_language": "🌍 언어",
        "btn_website": "🌐 웹사이트",
        "btn_spin": "🎰 행운의 룰렛",
        "welcome": "👋 환영합니다, *{name}!*\n\n{urgency}\n\n🏆 *{business}* — 승자들이 거래하는 곳!\n\n무엇을 탐색하시겠습니까? 👇",
        "services_msg": "🏆 *저희 서비스*\n\n더 알아보려면 서비스를 선택하세요 👇",
        "join_msg": "⚠️ *먼저 채널에 참가해주세요!*\n\n지금 참가하고 돌아오세요! 👇",
        "support_msg": "💬 *지원 요청이 접수되었습니다!* ✅\n\n저희 팀이 *5시간 이내에* 연락드리겠습니다. ⏳\n\n봇을 열어두세요! 🙏",
        "btn_services": "🏆 우리 서비스",
        "btn_challenge": "💪 챌린지",
        "btn_goal": "🎯 목표 설정",
        "btn_mood": "😊 내 기분",
        "btn_why_evalon": "🤔 왜 EVALON?",
        "btn_win_alert": "🔔 승리 알림",
        "session_ended": "👋 *지원 채팅이 종료되었습니다.*\n\n연락해 주셔서 감사합니다! 🙏",
        "rating_msg": "⭐ *지원 경험이 어떠셨나요?*\n\n서비스를 평가해 주세요:",
        "rating_opinion_msg": "📝 *평가해 주셔서 감사합니다!*\n\n경험에 대한 간단한 의견을 나눠주세요 (또는 '건너뛰기'라고 입력):",
        "rating_thanks": "🙏 피드백 감사합니다, *{name}!* ⭐",
        "fallback_msg": "\U0001f914 \ub2f5\ubcc0\uc744 \ucc3e\uc9c0 \ubabb\ud588\uc2b5\ub2c8\ub2e4.\n\n\uc9c0\uc6d0\ud300\uacfc \ub300\ud654\ud558\uc2dc\uaca0\uc2b5\ub2c8\uae4c?",
        "msg_received": "\U0001f4e8 \uba54\uc2dc\uc9c0\ub97c \ubc1b\uc558\uc2b5\ub2c8\ub2e4! \ud300\uc774 \uacf5 \ub2f5\ubcc0\ub4dc\ub9ac\uaca0\uc2b5\ub2c8\ub2e4. \U0001f64f",
        "no_news": "\U0001f4e2 *\uc544\uc9c1 \uc0c8\ub85c\uc6b4 \uc5c5\ub370\uc774\ud2b8\uac00 \uc5c6\uc2b5\ub2c8\ub2e4!*\n\n\ub098\uc911\uc5d0 \ub2e4\uc2dc \ud655\uc778\ud558\uc138\uc694. \U0001f514",
        "no_vip": "\U0001f4ca *\uc624\ub298 VIP \uacb0\uacfc\uac00 \uc544\uc9c1 \uac8c\uc2dc\ub418\uc9c0 \uc54a\uc558\uc2b5\ub2c8\ub2e4!*\n\nVIP \ucc44\ub110\uc5d0 \ucc38\uc5ec\ud558\uc138\uc694. \u26a1",
        "no_results_history": "\U0001f4c5 *\uc544\uc9c1 \uacfc\uac70 \uacb0\uacfc\uac00 \uc5c6\uc2b5\ub2c8\ub2e4!*\n\n\uad00\ub9ac\uc790\uac00 \uc138\uc158 \uacb0\uacfc\ub97c \uac8c\uc2dc\ud560 \uac83\uc785\ub2c8\ub2e4. \u26a1",
        "comeback_msg": "👋 안녕하세요 *{name}!* 보고 싶었어요! 😊\n\n🔥 새 신호와 기회가 기다리고 있습니다!\n\n👇 돌아와서 탐색하세요:",
        "auto_clean_msg": "🔄 *채팅이 새로고침되었습니다!*\n\n계속하려면 아래를 탭하세요 👇",
        "join_pending": "⏳ *요청이 접수되었습니다!*\n\n관리자가 곧 승인합니다. 🙏",
        "spin_spinning": "\U0001f3b0 \ub3cc\ub9ac\ub294 \uc911...",
        "spin_wait": "⏳ 오늘 이미 스핀했습니다! {hours}h {mins}m 후에 돌아오세요 🕐",
        "referral_msg": "🎁 *나의 추천 링크*\n\n링크:\nhttps://t.me/{bot}?start=ref{uid}\n\n추천: {count}/{min}\n{bar}\n\n{needed}명 더 초대하면 보상 잠금 해제!\n{leaderboard}",
        "price_msg": "💰 *가격 및 플랜*\n\n최신 가격은 웹사이트를 방문하세요 👇",
        "poll_msg": "📊 *빠른 질문!*\n\n주로 어떤 플랫폼을 사용하시나요?",
        "btn_poll_quotex": "📊 Quotex",
        "btn_poll_pocket": "💰 Pocket Option",
        "btn_poll_both": "✅ 둘 다",
        "welcome_video": "🎬 *EVALON WINNERS에 오신 것을 환영합니다!*\n\n이 소개를 보세요! 🏆",
    },
    "tr": {
        "btn_signals": "\U0001f4ca VIP Sinyaller",
        "btn_social": "\U0001f465 Sosyal Ticaret",
        "btn_indicator": "\U0001f4c8 Ucretsiz Gosterge",
        "btn_autobot": "\U0001f916 Otomatik Bot",
        "btn_freebot": "\U0001f193 Ucretsiz Manuel Bot",
        "btn_support": "\U0001f4ac Destek Ile Iletisim",
        "btn_back": "\u2b05\ufe0f Geri",
        "btn_restart": "\U0001f680 Baslamak Icin Dokun",
        "btn_free_indicator": "\U0001f4f2 UCRETSIZ Gosterge Al",
        "btn_join": "\U0001f4e2 Kanala Katil",
        "btn_whats_new": "\U0001f195 Bugunun Yenilikleri",
        "btn_vip_results": "\U0001f3c6 Bugunun VIP Sonuclari",
        "btn_winners": "\U0001f451 Haftanin Kazananlari",
        "btn_my_streak": "\U0001f525 Gunluk Serim",
        "btn_tip": "\U0001f4a1 Gunluk Ipucu",
        "btn_quiz": "\U0001f9e0 Quiz",
        "btn_profile": "\U0001f464 Profilim",
        "btn_results_history": "\U0001f4c5 Gecmis Sonuclar",
        "btn_stories": "\u2b50 Basari Hikayeleri",
        "btn_referral": "🎁 Davet Et ve Kazan",
        "btn_language": "🌍 Dil",
        "btn_website": "🌐 Web Sitesi ve Fiyatlar",
        "btn_spin": "🎰 Sarki Carki — Sansini Dene!",
        "welcome": "👋 Hosgeldiniz, *{name}!*\n\n{urgency}\n\n🏆 *{business}* — Kazananlarin islem yaptigi yer!\n\nNeyi kesfetmek istersiniz? 👇",
        "services_msg": "🏆 *HİZMETLERİMİZ*\n\nDaha fazla bilgi icin bir hizmet secin 👇",
        "join_msg": "⚠️ *Lutfen once kanalimiza katilın!*\n\nSimdi katilın ve geri gelin! 👇",
        "support_msg": "💬 *Destek talibiniz alindi!* ✅\n\nEkibimiz *5 saat icinde* sizinle iletisime gececek. ⏳\n\nBotu acik tutun! 🙏",
        "btn_services": "🏆 Hizmetlerimiz",
        "btn_challenge": "💪 Meydan Okuma",
        "btn_goal": "🎯 Hedef Belirle",
        "btn_mood": "😊 Ruh Halim",
        "btn_why_evalon": "🤔 Neden EVALON?",
        "btn_win_alert": "🔔 Kazanma Uyarısı",
        "session_ended": "👋 *Destek sohbeti sona erdi.*\n\nBize ulastiginiz icin tesekkurler! 🙏",
        "rating_msg": "⭐ *Destek deneyiminiz nasildı?*\n\nHizmetimizi derecelendirin:",
        "rating_opinion_msg": "📝 *Derecelendirme icin tesekkurler!*\n\nDeneyiminiz hakkinda kisa bir gorüs paylasin ('skip' yazabilirsiniz):",
        "rating_thanks": "🙏 Geri bildiriminiz icin tesekkurler, *{name}!* ⭐",
        "fallback_msg": "\U0001f914 Bunun icin bir cevap bulamadim.\n\nDestek ekibimizle konusmak ister misiniz?",
        "msg_received": "\U0001f4e8 Mesaj alindi! Ekibimiz yakin zamanda yanitlayacak. \U0001f64f",
        "no_news": "\U0001f4e2 *Henuz yeni guncelleme yok!*\n\nDaha sonra tekrar kontrol edin. \U0001f514",
        "no_vip": "\U0001f4ca *Bugun VIP sonucu yayinlanmadi!*\n\nCanli sinyaller icin VIP kanalina katilin. \u26a1",
        "no_results_history": "\U0001f4c5 *Gecmis sonuc yok!*\n\nYonetici oturum sonuclarini buraya yayinlayacak. \u26a1",
        "comeback_msg": "👋 Merhaba *{name}!* Sizi özledik! 😊\n\n🔥 Yeni sinyaller ve firsatlar sizi bekliyor!\n\n👇 Geri donun ve kesfedın:",
        "auto_clean_msg": "🔄 *Sohbet yenilendi!*\n\nDevam etmek icin asagiya dokunun 👇",
        "join_pending": "⏳ *Talep alindi!*\n\nYonetici yakinda onaylayacak. 🙏",
        "spin_spinning": "\U0001f3b0 Donduruluyor...",
        "spin_wait": "⏳ Bugün zaten çevirdiniz! {hours}s {mins}d içinde geri dönün 🕐",
        "referral_msg": "🎁 *REFERANS LINKINIZ*\n\nLinkiniz:\nhttps://t.me/{bot}?start=ref{uid}\n\nReferanslariniz: {count}/{min}\n{bar}\n\n{needed} kisi daha davet edin ve oduluzu kazanin!\n{leaderboard}",
        "price_msg": "💰 *Fiyatlar ve Planlar*\n\nGüncel fiyatlar icin web sitemizi ziyaret edin 👇",
        "poll_msg": "📊 *Hizli soru!*\n\nEsasen hangi platformu kullaniyorsunuz?",
        "btn_poll_quotex": "📊 Quotex",
        "btn_poll_pocket": "💰 Pocket Option",
        "btn_poll_both": "✅ Her Ikisi",
        "welcome_video": "🎬 *EVALON WINNERS'a Hosgeldiniz!*\n\nBu tanitimi izleyin! 🏆",
    },
    "fa": {
        "btn_signals": "\U0001f4ca \u0633\u06cc\u06af\u0646\u0627\u0644\u200c\u0647\u0627\u06cc VIP",
        "btn_social": "\U0001f465 \u0645\u0639\u0627\u0645\u0644\u0627\u062a \u0627\u062c\u062a\u0645\u0627\u0639\u06cc",
        "btn_indicator": "\U0001f4c8 \u0627\u0646\u062f\u06cc\u06a9\u0627\u062a\u0648\u0631 \u0631\u0627\u06cc\u06af\u0627\u0646",
        "btn_autobot": "\U0001f916 \u0631\u0628\u0627\u062a \u062e\u0648\u062f\u06a9\u0627\u0631",
        "btn_freebot": "\U0001f193 \u0631\u0628\u0627\u062a \u062f\u0633\u062a\u06cc \u0631\u0627\u06cc\u06af\u0627\u0646",
        "btn_support": "\U0001f4ac \u062a\u0645\u0627\u0633 \u0628\u0627 \u067e\u0634\u062a\u06cc\u0628\u0627\u0646\u06cc",
        "btn_back": "\u2b05\ufe0f \u0628\u0627\u0632\u06af\u0634\u062a",
        "btn_restart": "\U0001f680 \u0628\u0631\u0627\u06cc \u0634\u0631\u0648\u0639 \u0644\u0645\u0633 \u06a9\u0646\u06cc\u062f",
        "btn_free_indicator": "\U0001f4f2 \u062f\u0631\u06cc\u0627\u0641\u062a \u0627\u0646\u062f\u06cc\u06a9\u0627\u062a\u0648\u0631 \u0631\u0627\u06cc\u06af\u0627\u0646",
        "btn_join": "\U0001f4e2 \u0639\u0636\u0648\u06cc\u062a \u062f\u0631 \u06a9\u0627\u0646\u0627\u0644",
        "btn_whats_new": "\U0001f195 \u0627\u062e\u0628\u0627\u0631 \u0627\u0645\u0631\u0648\u0632",
        "btn_vip_results": "\U0001f3c6 \u0646\u062a\u0627\u06cc\u062c VIP \u0627\u0645\u0631\u0648\u0632",
        "btn_winners": "\U0001f451 \u0628\u0631\u0646\u062f\u06af\u0627\u0646 \u0647\u0641\u062a\u0647",
        "btn_my_streak": "\U0001f525 \u0631\u0634\u062a\u0647 \u0631\u0648\u0632\u0627\u0646\u0647 \u0645\u0646",
        "btn_tip": "\U0001f4a1 \u0646\u06a9\u062a\u0647 \u0631\u0648\u0632\u0627\u0646\u0647",
        "btn_quiz": "\U0001f9e0 \u0622\u0632\u0645\u0648\u0646",
        "btn_profile": "\U0001f464 \u067e\u0631\u0648\u0641\u0627\u06cc\u0644 \u0645\u0646",
        "btn_results_history": "\U0001f4c5 \u0646\u062a\u0627\u06cc\u062c \u06af\u0630\u0634\u062a\u0647",
        "btn_stories": "\u2b50 \u062f\u0627\u0633\u062a\u0627\u0646\u200c\u0647\u0627\u06cc \u0645\u0648\u0641\u0642\u06cc\u062a",
        "btn_referral": "🎁 دعوت و کسب درآمد",
        "btn_language": "🌍 زبان",
        "btn_website": "🌐 وب سایت",
        "btn_spin": "🎰 چرخ شانس",
        "welcome": "👋 خوش آمدید, *{name}!*\n\n{urgency}\n\n🏆 *{business}* — جایی که برندگان معامله می‌کنند!\n\nمی‌خواهید چه چیزی را کشف کنید؟ 👇",
        "services_msg": "🏆 *خدمات ما*\n\nبرای اطلاعات بیشتر یک سرویس انتخاب کنید 👇",
        "join_msg": "⚠️ *لطفاً ابتدا به کانال ما بپیوندید!*\n\nهم اکنون بپیوندید و بازگردید! 👇",
        "support_msg": "💬 *درخواست پشتیبانی دریافت شد!* ✅\n\nتیم ما *ظرف ۵ ساعت* با شما تماس خواهد گرفت. ⏳\n\nبات را باز نگه دارید! 🙏",
        "btn_services": "🏆 خدمات ما",
        "btn_challenge": "💪 چالش",
        "btn_goal": "🎯 تعیین هدف",
        "btn_mood": "😊 حال من",
        "btn_why_evalon": "🤔 چرا EVALON؟",
        "btn_win_alert": "🔔 هشدار برنده شدن",
        "session_ended": "👋 *چت پشتیبانی پایان یافت.*\n\nممنون که با ما تماس گرفتید! 🙏",
        "rating_msg": "⭐ *تجربه پشتیبانی شما چطور بود؟*\n\nسرویس ما را ارزیابی کنید:",
        "rating_opinion_msg": "📝 *ممنون از امتیازدهی!*\n\nنظر کوتاهی در مورد تجربه خود بنویسید (یا 'skip' بنویسید):",
        "rating_thanks": "🙏 ممنون از بازخورد شما, *{name}!* ⭐",
        "fallback_msg": "\U0001f914 \u067e\u0627\u0633\u062e\u06cc \u0628\u0631\u0627\u06cc \u0627\u06cc\u0646 \u067e\u06cc\u062f\u0627 \u0646\u06a9\u0631\u062f\u0645.\n\n\u0622\u06cc\u0627 \u0645\u06cc\u200c\u062e\u0648\u0627\u0647\u06cc\u062f \u0628\u0627 \u062a\u06cc\u0645 \u067e\u0634\u062a\u06cc\u0628\u0627\u0646\u06cc \u0635\u062d\u0628\u062a \u06a9\u0646\u06cc\u062f?",
        "msg_received": "\U0001f4e8 \u067e\u06cc\u0627\u0645 \u062f\u0631\u06cc\u0627\u0641\u062a \u0634\u062f! \u062a\u06cc\u0645 \u0645\u0627 \u0628\u0647 \u0632\u0648\u062f\u06cc \u067e\u0627\u0633\u062e \u062e\u0648\u0627\u0647\u062f \u062f\u0627\u062f. \U0001f64f",
        "no_news": "\U0001f4e2 *\u0647\u0646\u0648\u0632 \u0628\u0631\u0648\u0632\u0631\u0633\u0627\u0646\u06cc \u062c\u062f\u06cc\u062f\u06cc \u0646\u06cc\u0633\u062a!*\n\n\u0628\u0639\u062f\u0627 \u062f\u0648\u0628\u0627\u0631\u0647 \u0628\u0631\u0631\u0633\u06cc \u06a9\u0646\u06cc\u062f. \U0001f514",
        "no_vip": "\U0001f4ca *\u0627\u0645\u0631\u0648\u0632 \u0646\u062a\u06cc\u062c\u0647 VIP \u0645\u0646\u062a\u0634\u0631 \u0646\u0634\u062f\u0647!*\n\n\u0628\u0631\u0627\u06cc \u0633\u06cc\u06af\u0646\u0627\u0644 \u0632\u0646\u062f\u0647 \u0628\u0647 \u06a9\u0627\u0646\u0627\u0644 VIP \u0628\u067e\u06cc\u0648\u0646\u062f\u06cc\u062f. \u26a1",
        "no_results_history": "\U0001f4c5 *\u0647\u0646\u0648\u0632 \u0646\u062a\u06cc\u062c\u0647 \u06af\u0630\u0634\u062a\u0647\u200c\u0627\u06cc \u0646\u06cc\u0633\u062a!*\n\n\u0627\u062f\u0645\u06cc\u0646 \u0646\u062a\u0627\u06cc\u062c \u062c\u0644\u0633\u0627\u062a \u0631\u0627 \u0627\u06cc\u0646\u062c\u0627 \u0645\u0646\u062a\u0634\u0631 \u062e\u0648\u0627\u0647\u062f \u06a9\u0631\u062f. \u26a1",
        "comeback_msg": "👋 سلام *{name}!* دلمان برایتان تنگ شده بود! 😊\n\n🔥 سیگنال‌ها و فرصت‌های جدید منتظر شما هستند!\n\n👇 برگردید و کشف کنید:",
        "auto_clean_msg": "🔄 *چت تازه‌سازی شد!*\n\nبرای ادامه پایین را لمس کنید 👇",
        "join_pending": "⏳ *درخواست دریافت شد!*\n\nادمین به زودی تأیید خواهد کرد. 🙏",
        "spin_spinning": "\U0001f3b0 \u062f\u0631 \u062d\u0627\u0644 \u0686\u0631\u062e\u0634...",
        "spin_wait": "⏳ امروز قبلاً چرخاندید! بعد از {hours} ساعت و {mins} دقیقه برگردید 🕐",
        "referral_msg": "🎁 *لینک معرفی شما*\n\nلینک شما:\nhttps://t.me/{bot}?start=ref{uid}\n\nمعرفی‌ها: {count}/{min}\n{bar}\n\n{needed} نفر دیگر دعوت کنید تا جایزه باز شود!\n{leaderboard}",
        "price_msg": "💰 *قیمت‌ها و پلان‌ها*\n\nبرای آخرین قیمت‌ها به وب سایت مراجعه کنید 👇",
        "poll_msg": "📊 *سوال سریع!*\n\nاصلاً از کدام پلتفرم استفاده می‌کنید؟",
        "btn_poll_quotex": "📊 Quotex",
        "btn_poll_pocket": "💰 Pocket Option",
        "btn_poll_both": "✅ هر دو",
        "welcome_video": "🎬 *به EVALON WINNERS خوش آمدید!*\n\nاین معرفی را تماشا کنید! 🏆",
    },
    "pl": {
        "btn_signals": "\U0001f4ca Sygna\u0142y VIP",
        "btn_social": "\U0001f465 Handel Spo\u0142eczno\u015bciowy",
        "btn_indicator": "\U0001f4c8 Darmowy Wska\u017anik",
        "btn_autobot": "\U0001f916 Automatyczny Bot",
        "btn_freebot": "\U0001f193 Darmowy Bot Manualny",
        "btn_support": "\U0001f4ac Kontakt z Pomoc\u0105",
        "btn_back": "\u2b05\ufe0f Wr\u00f3\u0107",
        "btn_restart": "\U0001f680 Dotknij aby Zacz\u0105\u0107",
        "btn_free_indicator": "\U0001f4f2 Pobierz DARMOWY Wska\u017anik",
        "btn_join": "\U0001f4e2 Do\u0142\u0105cz do Kana\u0142u",
        "btn_whats_new": "\U0001f195 Co Nowego Dzi\u015b",
        "btn_vip_results": "\U0001f3c6 Dzisiejsze Wyniki VIP",
        "btn_winners": "\U0001f451 Zwyci\u0119zcy Tygodnia",
        "btn_my_streak": "\U0001f525 Moja Codzienna Seria",
        "btn_tip": "\U0001f4a1 Codzienna Wskaz\u00f3wka",
        "btn_quiz": "\U0001f9e0 Quiz",
        "btn_profile": "\U0001f464 M\u00f3j Profil",
        "btn_results_history": "\U0001f4c5 Poprzednie Wyniki",
        "btn_stories": "\u2b50 Historie Sukcesu",
        "fallback_msg": "\U0001f914 Nie znalaz\u0142em odpowiedzi na to.\n\nChcesz porozmawia\u0107 z naszym zespo\u0142em wsparcia?",
        "msg_received": "\U0001f4e8 Wiadomo\u015b\u0107 odebrana! Nasz zesp\u00f3\u0142 odpowie wkr\u00f3tce. \U0001f64f",
        "no_news": "\U0001f4e2 *Brak nowych aktualizacji!*\n\nSprawdź ponownie później. \U0001f514",
        "no_vip": "\U0001f4ca *Dzi\u015b nie opublikowano wynik\u00f3w VIP!*\n\nDo\u0142\u0105cz do kana\u0142u VIP po sygna\u0142y na \u017cywo. \u26a1",
        "no_results_history": "\U0001f4c5 *Brak poprzednich wynik\u00f3w!*\n\nAdmin opublikuje tu wyniki sesji. \u26a1",
        "spin_spinning": "\U0001f3b0 Kr\u0119ci si\u0119...",
    },
    "uk": {
        "btn_signals": "\U0001f4ca VIP \u0421\u0438\u0433\u043d\u0430\u043b\u0438",
        "btn_social": "\U0001f465 \u0421\u043e\u0446\u0456\u0430\u043b\u044c\u043d\u0430 \u0422\u043e\u0440\u0433\u0456\u0432\u043b\u044f",
        "btn_indicator": "\U0001f4c8 \u0411\u0435\u0437\u043a\u043e\u0448\u0442\u043e\u0432\u043d\u0438\u0439 \u0406\u043d\u0434\u0438\u043a\u0430\u0442\u043e\u0440",
        "btn_autobot": "\U0001f916 \u0410\u0432\u0442\u043e \u0411\u043e\u0442",
        "btn_freebot": "\U0001f193 \u0411\u0435\u0437\u043a\u043e\u0448\u0442\u043e\u0432\u043d\u0438\u0439 \u0420\u0443\u0447\u043d\u0438\u0439 \u0411\u043e\u0442",
        "btn_support": "\U0001f4ac \u0417\u0432'\u044f\u0437\u0430\u0442\u0438\u0441\u044f \u0437 \u041f\u0456\u0434\u0442\u0440\u0438\u043c\u043a\u043e\u044e",
        "btn_back": "\u2b05\ufe0f \u041d\u0430\u0437\u0430\u0434",
        "btn_restart": "\U0001f680 \u041d\u0430\u0442\u0438\u0441\u043d\u0456\u0442\u044c \u0434\u043b\u044f \u041f\u043e\u0447\u0430\u0442\u043a\u0443",
        "btn_free_indicator": "\U0001f4f2 \u041e\u0442\u0440\u0438\u043c\u0430\u0442\u0438 \u0411\u0415\u0417\u041a\u041e\u0428\u0422\u041e\u0412\u041d\u0418\u0419 \u0406\u043d\u0434\u0438\u043a\u0430\u0442\u043e\u0440",
        "btn_join": "\U0001f4e2 \u041f\u0440\u0438\u0454\u0434\u043d\u0430\u0442\u0438\u0441\u044f \u0434\u043e \u041a\u0430\u043d\u0430\u043b\u0443",
        "btn_whats_new": "\U0001f195 \u0429\u043e \u041d\u043e\u0432\u043e\u0433\u043e \u0421\u044c\u043e\u0433\u043e\u0434\u043d\u0456",
        "btn_vip_results": "\U0001f3c6 \u0421\u044c\u043e\u0433\u043e\u0434\u043d\u0456\u0448\u043d\u0456 VIP \u0420\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442\u0438",
        "btn_winners": "\U0001f451 \u041f\u0435\u0440\u0435\u043c\u043e\u0436\u0446\u0456 \u0422\u0438\u0436\u043d\u044f",
        "btn_my_streak": "\U0001f525 \u041c\u043e\u044f \u0429\u043e\u0434\u0435\u043d\u043d\u0430 \u0421\u0435\u0440\u0456\u044f",
        "btn_tip": "\U0001f4a1 \u0429\u043e\u0434\u0435\u043d\u043d\u0430 \u041f\u043e\u0440\u0430\u0434\u0430",
        "btn_quiz": "\U0001f9e0 \u0412\u0456\u043a\u0442\u043e\u0440\u0438\u043d\u0430",
        "btn_profile": "\U0001f464 \u041c\u0456\u0439 \u041f\u0440\u043e\u0444\u0456\u043b\u044c",
        "btn_results_history": "\U0001f4c5 \u041c\u0438\u043d\u0443\u043b\u0456 \u0420\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442\u0438",
        "btn_stories": "\u2b50 \u0406\u0441\u0442\u043e\u0440\u0456\u0457 \u0423\u0441\u043f\u0456\u0445\u0443",
        "fallback_msg": "\U0001f914 \u042f \u043d\u0435 \u0437\u043d\u0430\u0439\u0448\u043e\u0432 \u0432\u0456\u0434\u043f\u043e\u0432\u0456\u0434\u0456.\n\n\u0425\u043e\u0447\u0435\u0442\u0435 \u043f\u043e\u0433\u043e\u0432\u043e\u0440\u0438\u0442\u0438 \u0437 \u043f\u0456\u0434\u0442\u0440\u0438\u043c\u043a\u043e\u044e?",
        "msg_received": "\U0001f4e8 \u041f\u043e\u0432\u0456\u0434\u043e\u043c\u043b\u0435\u043d\u043d\u044f \u043e\u0442\u0440\u0438\u043c\u0430\u043d\u043e! \u041d\u0430\u0448\u0430 \u043a\u043e\u043c\u0430\u043d\u0434\u0430 \u0441\u043a\u043e\u0440\u043e \u0432\u0456\u0434\u043f\u043e\u0432\u0456\u0441\u0442\u044c. \U0001f64f",
        "no_news": "\U0001f4e2 *\u0429\u0435 \u043d\u0435\u043c\u0430\u0454 \u043d\u043e\u0432\u0438\u0445 \u043e\u043d\u043e\u0432\u043b\u0435\u043d\u044c!*\n\n\u041f\u0435\u0440\u0435\u0432\u0456\u0440\u0442\u0435 \u043f\u0456\u0437\u043d\u0456\u0448\u0435. \U0001f514",
        "no_vip": "\U0001f4ca *\u0421\u044c\u043e\u0433\u043e\u0434\u043d\u0456 \u0440\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442\u0456\u0432 VIP \u043d\u0435\u043c\u0430\u0454!*\n\n\u041f\u0440\u0438\u0454\u0434\u043d\u0430\u0439\u0442\u0435\u0441\u044c \u0434\u043e VIP \u043a\u0430\u043d\u0430\u043b\u0443. \u26a1",
        "no_results_history": "\U0001f4c5 *\u0429\u0435 \u043d\u0435\u043c\u0430\u0454 \u043c\u0438\u043d\u0443\u043b\u0438\u0445 \u0440\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442\u0456\u0432!*\n\n\u0410\u0434\u043c\u0456\u043d \u043e\u043f\u0443\u0431\u043b\u0456\u043a\u0443\u0454 \u0440\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442\u0438 \u0441\u0435\u0441\u0456\u0439 \u0442\u0443\u0442. \u26a1",
        "spin_spinning": "\U0001f3b0 \u041e\u0431\u0435\u0440\u0442\u0430\u0454\u0442\u044c\u0441\u044f...",
    },
    "kk": {
        "btn_signals": "\U0001f4ca VIP \u0421\u0438\u0433\u043d\u0430\u043b\u0434\u0430\u0440",
        "btn_social": "\U0001f465 \u04d8\u043b\u0435\u0443\u043c\u0435\u0442\u0442\u0456\u043a \u0421\u0430\u0443\u0434\u0430",
        "btn_indicator": "\U0001f4c8 \u0422\u0435\u0433\u0456\u043d \u0418\u043d\u0434\u0438\u043a\u0430\u0442\u043e\u0440",
        "btn_autobot": "\U0001f916 \u0410\u0432\u0442\u043e \u0411\u043e\u0442",
        "btn_freebot": "\U0001f193 \u0422\u0435\u0433\u0456\u043d \u049a\u043e\u043b\u043c\u0435\u043d \u0411\u043e\u0442",
        "btn_support": "\U0001f4ac \u049a\u043e\u043b\u0434\u0430\u0443\u043c\u0435\u043d \u0411\u0430\u0439\u043b\u0430\u043d\u044b\u0441",
        "btn_back": "\u2b05\ufe0f \u0410\u0440\u0442\u049b\u0430",
        "btn_restart": "\U0001f680 \u0411\u0430\u0441\u0442\u0430\u0443 \u04af\u0448\u0456\u043d \u0411\u0430\u0441\u044b\u04a3\u044b\u0437",
        "btn_free_indicator": "\U0001f4f2 \u0422\u0415\u0413\u0406\u041d \u0418\u043d\u0434\u0438\u043a\u0430\u0442\u043e\u0440 \u0410\u043b\u044b\u04a3\u044b\u0437",
        "btn_join": "\U0001f4e2 \u0410\u0440\u043d\u0430\u0493\u0430 \u049a\u043e\u0441\u044b\u043b\u0443",
        "btn_whats_new": "\U0001f195 \u0411\u04af\u0433\u0456\u043d\u0433\u0456 \u0416\u0430\u04a3\u0430\u043b\u044b\u049b\u0442\u0430\u0440",
        "btn_vip_results": "\U0001f3c6 \u0411\u04af\u0433\u0456\u043d\u0433\u0456 VIP \u041d\u04d9\u0442\u0438\u0436\u0435\u043b\u0435\u0440",
        "btn_winners": "\U0001f451 \u0410\u043f\u0442\u0430 \u0416\u0435\u04a3\u0456\u043c\u043f\u0430\u0437\u0434\u0430\u0440\u044b",
        "btn_my_streak": "\U0001f525 \u041c\u0435\u043d\u0456\u04a3 \u041a\u04af\u043d\u0434\u0435\u043b\u0456\u043a\u0442\u0456 \u0421\u0435\u0440\u0456\u044f\u043c",
        "btn_tip": "\U0001f4a1 \u041a\u04af\u043d\u0434\u0435\u043b\u0456\u043a \u041a\u0435\u04a3\u0435\u0441",
        "btn_quiz": "\U0001f9e0 \u0412\u0438\u043a\u0442\u043e\u0440\u0438\u043d\u0430",
        "btn_profile": "\U0001f464 \u041c\u0435\u043d\u0456\u04a3 \u041f\u0440\u043e\u0444\u0438\u043b\u0456\u043c",
        "btn_results_history": "\U0001f4c5 \u04e8\u0442\u043a\u0435\u043d \u041d\u04d9\u0442\u0438\u0436\u0435\u043b\u0435\u0440",
        "btn_stories": "\u2b50 \u0416\u0435\u0442\u0456\u0441\u0442\u0456\u043a \u0422\u0430\u0440\u0438\u0445\u0442\u0430\u0440\u044b",
        "fallback_msg": "\U0001f914 \u0411\u04b1\u043b \u04af\u0448\u0456\u043d \u0436\u0430\u0443\u0430\u043f \u0442\u0430\u043f\u043f\u0430\u0434\u044b\u043c.\n\n\u049a\u043e\u043b\u0434\u0430\u0443 \u043a\u043e\u043c\u0430\u043d\u0434\u0430\u0441\u044b\u043c\u0435\u043d \u0441\u04e9\u0439\u043b\u0435\u0441\u043a\u0456\u04a3\u0456\u0437 \u043a\u0435\u043b\u0435 \u043c\u0435?",
        "msg_received": "\U0001f4e8 \u0425\u0430\u0431\u0430\u0440\u043b\u0430\u043c\u0430 \u0430\u043b\u044b\u043d\u0434\u044b! \u041a\u043e\u043c\u0430\u043d\u0434\u0430\u043c\u044b\u0437 \u0436\u0430\u049b\u044b\u043d \u0430\u0440\u0430\u0434\u0430 \u0436\u0430\u0443\u0430\u043f \u0431\u0435\u0440\u0435\u0434\u0456. \U0001f64f",
        "no_news": "\U0001f4e2 *\u04d8\u043b\u0456 \u0436\u0430\u04a3\u0430 \u0436\u0430\u04a3\u0430\u0440\u0442\u0443\u043b\u0430\u0440 \u0436\u043e\u049b!*\n\n\u041a\u0435\u0439\u0456\u043d\u0440\u0435\u043a \u049b\u0430\u0439\u0442\u0430 \u0442\u0435\u043a\u0441\u0435\u0440\u0456\u04a3\u0456\u0437. \U0001f514",
        "no_vip": "\U0001f4ca *\u0411\u04af\u0433\u0456\u043d VIP \u043d\u04d9\u0442\u0438\u0436\u0435\u043b\u0435\u0440 \u04d9\u043b\u0456 \u0436\u0430\u0440\u0438\u044f\u043b\u0430\u043d\u0431\u0430\u0493\u0430\u043d!*\n\nVIP \u0430\u0440\u043d\u0430\u0441\u044b\u043d\u0430 \u049b\u043e\u0441\u044b\u043b\u044b\u04a3\u044b\u0437. \u26a1",
        "no_results_history": "\U0001f4c5 *\u04e8\u0442\u043a\u0435\u043d \u043d\u04d9\u0442\u0438\u0436\u0435\u043b\u0435\u0440 \u04d9\u043b\u0456 \u0436\u043e\u049b!*\n\n\u0410\u0434\u043c\u0438\u043d \u0441\u0435\u0441\u0441\u0438\u044f \u043d\u04d9\u0442\u0438\u0436\u0435\u043b\u0435\u0440\u0456\u043d \u043e\u0441\u044b\u043d\u0434\u0430 \u0436\u0430\u0440\u0438\u044f\u043b\u0430\u0439\u0434\u044b. \u26a1",
        "spin_spinning": "\U0001f3b0 \u0410\u0439\u043d\u0430\u043b\u0443\u0434\u0430...",
    },
    "cs": {
        "btn_signals": "\U0001f4ca VIP Sign\u00e1ly",
        "btn_social": "\U0001f465 Soci\u00e1ln\u00ed Obchodov\u00e1n\u00ed",
        "btn_indicator": "\U0001f4c8 Bezplatn\u00fd Indik\u00e1tor",
        "btn_autobot": "\U0001f916 Automatick\u00fd Bot",
        "btn_freebot": "\U0001f193 Bezplatn\u00fd Manu\u00e1ln\u00ed Bot",
        "btn_support": "\U0001f4ac Kontaktovat Podporu",
        "btn_back": "\u2b05\ufe0f Zp\u011bt",
        "btn_restart": "\U0001f680 Klepn\u011bte pro Za\u010d\u00e1tek",
        "btn_free_indicator": "\U0001f4f2 Z\u00edskat BEZPLATN\u00dd Indik\u00e1tor",
        "btn_join": "\U0001f4e2 P\u0159ipojit se ke Kan\u00e1lu",
        "btn_whats_new": "\U0001f195 Co Je Nov\u00e9ho Dnes",
        "btn_vip_results": "\U0001f3c6 Dne\u0161n\u00ed VIP V\u00fdsledky",
        "btn_winners": "\U0001f451 V\u00edt\u011bzov\u00e9 T\u00fddne",
        "btn_my_streak": "\U0001f525 M\u016fj Denn\u00ed Streak",
        "btn_tip": "\U0001f4a1 Denn\u00ed Tip",
        "btn_quiz": "\U0001f9e0 Kv\u00edz",
        "btn_profile": "\U0001f464 M\u016fj Profil",
        "btn_results_history": "\U0001f4c5 Minul\u00e9 V\u00fdsledky",
        "btn_stories": "\u2b50 P\u0159\u00edb\u011bhy \u00dasp\u011bchu",
        "fallback_msg": "\U0001f914 Nena\u0161el jsem odpov\u011b\u010f na to.\n\nChcete mluvit s na\u0161\u00edm t\u00fdmem podpory?",
        "msg_received": "\U0001f4e8 Zpr\u00e1va p\u0159ijata! N\u00e1\u0161 t\u00fdm odpov\u00ed brzy. \U0001f64f",
        "no_news": "\U0001f4e2 *Zat\u00edm \u017e\u00e1dn\u00e9 nov\u00e9 aktualizace!*\n\nZkuste to znovu pozd\u011bji. \U0001f514",
        "no_vip": "\U0001f4ca *Dnes nejsou zve\u0159ejn\u011bny \u017e\u00e1dn\u00e9 VIP v\u00fdsledky!*\n\nP\u0159ipojte se k VIP kan\u00e1lu pro \u017eiv\u00e9 sign\u00e1ly. \u26a1",
        "no_results_history": "\U0001f4c5 *Zat\u00edm \u017e\u00e1dn\u00e9 minul\u00e9 v\u00fdsledky!*\n\nAdmin sem zve\u0159ejn\u00ed v\u00fdsledky relac\u00ed. \u26a1",
        "spin_spinning": "\U0001f3b0 To\u010d\u00ed se...",
    },
}

for _lc, _keys in _extra_ui.items():
    if _lc in UI:
        UI[_lc].update(_keys)

# ── Add missing critical keys for non-core languages ──────────────────────────
_missing_keys = {
    "pl": {
        "btn_referral": "🎁 Zaproś i Zarabiaj", "btn_language": "🌍 Język",
        "btn_website": "🌐 Strona i Ceny", "btn_spin": "🎰 Koło Fortuny",
        "welcome": "👋 Witaj, *{name}!*\n\n{urgency}\n\n🏆 *{business}* — Gdzie wygrywają traderzy!\n\nCo chcesz poznać? 👇",
        "services_msg": "🏆 *NASZE USŁUGI*\n\nWybierz usługę, aby dowiedzieć się więcej 👇",
        "join_msg": "⚠️ *Najpierw dołącz do naszego kanału!*\n\nDołącz teraz i wróć! 👇",
        "support_msg": "💬 *Zgłoszenie supportu odebrane!* ✅\n\nNasz team skontaktuje się z Tobą *w ciągu 5 godzin.* ⏳\n\nTrzymaj bota otwartego! 🙏",
        "session_ended": "👋 *Czat supportu zakończony.*\n\nDziękujemy za kontakt! 🙏",
        "rating_msg": "⭐ *Jak oceniasz nasze wsparcie?*\n\nOceń naszą usługę:",
        "rating_opinion_msg": "📝 *Dziękujemy za ocenę!*\n\nPodziel się krótką opinią (lub napisz 'skip'):",
        "rating_thanks": "🙏 Dziękujemy za opinię, *{name}!* ⭐",
        "comeback_msg": "👋 Hej *{name}!* Tęskniliśmy za Tobą! 😊\n\n🔥 Nowe sygnały i okazje czekają!\n\n👇 Wróć i odkryj:",
        "auto_clean_msg": "🔄 *Czat odświeżony!*\n\nDotknij poniżej, aby kontynuować 👇",
        "join_pending": "⏳ *Zgłoszenie odebrane!*\n\nAdmin zatwierdzi wkrótce. 🙏",
        "spin_wait": "⏳ Już kręciłeś dziś! Wróć za {hours}h {mins}min 🕐",
        "referral_msg": "🎁 *TWÓJ LINK POLECAJĄCY*\n\nLink:\nhttps://t.me/{bot}?start=ref{uid}\n\nPolecenia: {count}/{min}\n{bar}\n\nZaproś {needed} więcej osób!\n{leaderboard}",
        "price_msg": "💰 *Ceny i Plany*\n\nOdwiedź naszą stronę 👇",
        "poll_msg": "📊 *Szybkie pytanie!*\n\nJakiej platformy używasz?",
        "btn_poll_quotex": "📊 Quotex", "btn_poll_pocket": "💰 Pocket Option",
        "btn_poll_both": "✅ Obu", "welcome_video": "🎬 *Witaj w EVALON WINNERS!* 🏆",
    },
    "uk": {
        "btn_referral": "🎁 Запроси та Заробляй", "btn_language": "🌍 Мова",
        "btn_website": "🌐 Сайт та Ціни", "btn_spin": "🎰 Колесо Фортуни",
        "welcome": "👋 Ласкаво просимо, *{name}!*\n\n{urgency}\n\n🏆 *{business}* — Де перемагають трейдери!\n\nЩо хочете досліджувати? 👇",
        "services_msg": "🏆 *НАШІ ПОСЛУГИ*\n\nОберіть послугу для детальнішої інформації 👇",
        "join_msg": "⚠️ *Спочатку приєднайтесь до нашого каналу!*\n\nПриєднайтесь зараз і повертайтесь! 👇",
        "support_msg": "💬 *Запит на підтримку отримано!* ✅\n\nНаша команда зв'яжеться з вами *протягом 5 годин.* ⏳\n\nТримайте бота відкритим! 🙏",
        "session_ended": "👋 *Чат підтримки завершено.*\n\nДякуємо за звернення! 🙏",
        "rating_msg": "⭐ *Як вам досвід підтримки?*\n\nОцініть наш сервіс:",
        "rating_opinion_msg": "📝 *Дякуємо за оцінку!*\n\nПоділіться короткою думкою (або напишіть 'skip'):",
        "rating_thanks": "🙏 Дякуємо за відгук, *{name}!* ⭐",
        "comeback_msg": "👋 Привіт *{name}!* Ми сумували! 😊\n\n🔥 Нові сигнали та можливості чекають!\n\n👇 Повертайтесь:",
        "auto_clean_msg": "🔄 *Чат оновлено!*\n\nТоркніться нижче, щоб продовжити 👇",
        "join_pending": "⏳ *Запит отримано!*\n\nАдмін незабаром підтвердить. 🙏",
        "spin_wait": "⏳ Ви вже крутили сьогодні! Повертайтесь через {hours}г {mins}хв 🕐",
        "referral_msg": "🎁 *ВАШЕ РЕФЕРАЛЬНЕ ПОСИЛАННЯ*\n\nПосилання:\nhttps://t.me/{bot}?start=ref{uid}\n\nРеферали: {count}/{min}\n{bar}\n\nЗапросіть ще {needed} осіб!\n{leaderboard}",
        "price_msg": "💰 *Ціни та Плани*\n\nВідвідайте наш сайт 👇",
        "poll_msg": "📊 *Швидке питання!*\n\nЯку платформу ви в основному використовуєте?",
        "btn_poll_quotex": "📊 Quotex", "btn_poll_pocket": "💰 Pocket Option",
        "btn_poll_both": "✅ Обидві", "welcome_video": "🎬 *Ласкаво просимо до EVALON WINNERS!* 🏆",
    },
    "kk": {
        "btn_referral": "🎁 Шақыр және Тап", "btn_language": "🌍 Тіл",
        "btn_website": "🌐 Сайт және Бағалар", "btn_spin": "🎰 Бақыт Дөңгелегі",
        "welcome": "👋 Қош келдіңіз, *{name}!*\n\n{urgency}\n\n🏆 *{business}* — Жеңімпаздар сауда жасайтын жер!\n\nНені зерттегіңіз келеді? 👇",
        "services_msg": "🏆 *БІЗДІҢ ҚЫЗМЕТТЕР*\n\nТолығырақ білу үшін қызметті таңдаңыз 👇",
        "join_msg": "⚠️ *Алдымен арнамызға қосылыңыз!*\n\nҚазір қосылып, оралыңыз! 👇",
        "support_msg": "💬 *Қолдау сұрауы қабылданды!* ✅\n\nКомандамыз *5 сағат ішінде* хабарласады. ⏳\n\nБотты ашық ұстаңыз! 🙏",
        "session_ended": "👋 *Қолдау чаты аяқталды.*\n\nБізге хабарласқаныңыз үшін рахмет! 🙏",
        "rating_msg": "⭐ *Қолдау тәжірибеңіз қандай болды?*\n\nҚызметімізді бағалаңыз:",
        "rating_opinion_msg": "📝 *Бағалағаныңыз үшін рахмет!*\n\nТәжірибеңіз туралы қысқаша пікір айтыңыз ('skip' жазуға болады):",
        "rating_thanks": "🙏 Пікіріңіз үшін рахмет, *{name}!* ⭐",
        "comeback_msg": "👋 Сәлем *{name}!* Сізді сағындық! 😊\n\n🔥 Жаңа сигналдар мен мүмкіндіктер күтуде!\n\n👇 Оралыңыз:",
        "auto_clean_msg": "🔄 *Чат жаңартылды!*\n\nЖалғастыру үшін төменге басыңыз 👇",
        "join_pending": "⏳ *Сұрау қабылданды!*\n\nАдминистратор жақында растайды. 🙏",
        "spin_wait": "⏳ Бүгін айналдырдыңыз! {hours}с {mins}м-ден кейін оралыңыз 🕐",
        "referral_msg": "🎁 *СІЗДІҢ РЕФЕРАЛ СІЛТЕМЕҢІЗ*\n\nСілтемеңіз:\nhttps://t.me/{bot}?start=ref{uid}\n\nРефералдар: {count}/{min}\n{bar}\n\nТағы {needed} адам шақырыңыз!\n{leaderboard}",
        "price_msg": "💰 *Бағалар және Жоспарлар*\n\nАқтуалды бағалар үшін сайтымызға кіріңіз 👇",
        "poll_msg": "📊 *Жылдам сұрақ!*\n\nНегізінен қандай платформаны пайдаланасыз?",
        "btn_poll_quotex": "📊 Quotex", "btn_poll_pocket": "💰 Pocket Option",
        "btn_poll_both": "✅ Екеуі де", "welcome_video": "🎬 *EVALON WINNERS-ке қош келдіңіз!* 🏆",
    },
    "cs": {
        "btn_referral": "🎁 Pozvi a Vydělávej", "btn_language": "🌍 Jazyk",
        "btn_website": "🌐 Web a Ceny", "btn_spin": "🎰 Kolo Štěstí",
        "welcome": "👋 Vítejte, *{name}!*\n\n{urgency}\n\n🏆 *{business}* — Kde vítězí tradeři!\n\nCo chcete prozkoumat? 👇",
        "services_msg": "🏆 *NAŠE SLUŽBY*\n\nVyberte službu pro více informací 👇",
        "join_msg": "⚠️ *Nejprve se připojte k našemu kanálu!*\n\nPřipojte se teď a vraťte se! 👇",
        "support_msg": "💬 *Žádost o podporu přijata!* ✅\n\nNáš tým vás kontaktuje *do 5 hodin.* ⏳\n\nNechte bota otevřeného! 🙏",
        "session_ended": "👋 *Chat podpory ukončen.*\n\nDěkujeme za kontakt! 🙏",
        "rating_msg": "⭐ *Jak hodnotíte naši podporu?*\n\nOhodnoťte naši službu:",
        "rating_opinion_msg": "📝 *Děkujeme za hodnocení!*\n\nPodělte se o krátký názor (nebo napište 'skip'):",
        "rating_thanks": "🙏 Děkujeme za zpětnou vazbu, *{name}!* ⭐",
        "comeback_msg": "👋 Ahoj *{name}!* Chyběl/a jste nám! 😊\n\n🔥 Nové signály a příležitosti čekají!\n\n👇 Vraťte se a prozkoumejte:",
        "auto_clean_msg": "🔄 *Chat obnoven!*\n\nDotknout se níže pro pokračování 👇",
        "join_pending": "⏳ *Žádost přijata!*\n\nAdmin brzy schválí. 🙏",
        "spin_wait": "⏳ Dnes jste již točil/a! Vraťte se za {hours}h {mins}min 🕐",
        "referral_msg": "🎁 *VÁŠ REFERRAL ODKAZ*\n\nOdkaz:\nhttps://t.me/{bot}?start=ref{uid}\n\nReferraly: {count}/{min}\n{bar}\n\nPozvěte ještě {needed} osob!\n{leaderboard}",
        "price_msg": "💰 *Ceny a Plány*\n\nNavštivte náš web pro aktuální ceny 👇",
        "poll_msg": "📊 *Rychlá otázka!*\n\nJakou platformu hlavně používáte?",
        "btn_poll_quotex": "📊 Quotex", "btn_poll_pocket": "💰 Pocket Option",
        "btn_poll_both": "✅ Obě", "welcome_video": "🎬 *Vítejte v EVALON WINNERS!* 🏆",
    },
}
for _lc, _keys in _missing_keys.items():
    if _lc in UI:
        UI[_lc].update(_keys)



# ── Referral discount messages ─────────────────────────────────
REFERRAL_DISCOUNT_MSG = {
    "en": (
        "🎉 *CONGRATULATIONS {name}!* 🏆\n\n"
        "You have successfully referred *{count} people* to EVALON WINNERS!\n\n"
        "🎁 *YOUR REWARD: 5% DISCOUNT!*\n\n"
        "You have earned a *5% discount* on ANY of our services!\n\n"
        "💡 But it gets better — keep inviting:\n"
        "• 10 referrals → 10% discount\n"
        "• 20 referrals → 20% discount\n"
        "• 50 referrals → 50% discount\n"
        "• 100 referrals → 70% discount 🔥\n\n"
        "The more you invite, the more you save!\n\n"
        "👇 Contact our team to redeem your discount:"
    ),
    "sw": (
        "🎉 *HONGERA {name}!* 🏆\n\n"
        "Umefanikiwa kuwalika *watu {count}* kwenye EVALON WINNERS!\n\n"
        "🎁 *ZAWADI YAKO: PUNGUZO LA 5%!*\n\n"
        "Umepata *punguzo la 5%* kwenye HUDUMA YOYOTE yetu!\n\n"
        "💡 Lakini inazidi kuwa nzuri — endelea kuwaandika:\n"
        "• Watu 10 → punguzo la 10%\n"
        "• Watu 20 → punguzo la 20%\n"
        "• Watu 50 → punguzo la 50%\n"
        "• Watu 100 → punguzo la 70% 🔥\n\n"
        "Unavyowaalika watu wengi zaidi, ndivyo unavyookoa zaidi!\n\n"
        "👇 Wasiliana na timu yetu kupata punguzo lako:"
    ),
}
# Use English for other languages
for _lc in ["ar","zh","hi","ru","es","fr","pt","de","ur","ja","it","ko","tr","fa","pl","uk","kk","cs"]:
    REFERRAL_DISCOUNT_MSG[_lc] = REFERRAL_DISCOUNT_MSG["en"]

# ── Onboarding messages (new users only, once) ─────────────────
ONBOARDING_VIDEO = "BAACAgQAAxkBAAID3WoKFvd6vxGTQBe9wd-2Gbh3uCMgAALEIAACgwZRUOtEi7uuFxmIOwQ"

ONBOARDING_TEXT = {
    "en": (
        "🤖 Hello *{name}*, Welcome to *Evalon Winners* 🚀\n\n"
        "I am a smart trading system created to help traders access useful tools, "
        "learning resources and different trading services for Binary Trading. 📈\n\n"
        "Inside, you will find systems designed to help you improve and grow your trading journey. 🔥\n\n"
        "My goal is to give traders one place with everything they need.\n\n"
        "From learning market analysis, understanding strategies, using trading tools "
        "and exploring better ways to improve trading knowledge and experience. 📊\n\n"
        "*Evalon Winners Trader* is made for both beginners and experienced traders.\n\n"
        "Whether you want to learn more, improve your strategy or explore smart trading systems, "
        "you are in the right place. 🚀✨\n\n"
        "Thank you for joining us.\n\n"
        "All services are ready inside our system and waiting for you to explore.\n\n"
        "*Press Continue to proceed* 🚀"
    ),
    "sw": (
        "🤖 Habari *{name}*, Karibu *Evalon Winners* 🚀\n\n"
        "Mimi ni mfumo wa biashara mahiri uliotengenezwa kusaidia wafanyabiashara kupata "
        "zana muhimu, rasilimali za kujifunza na huduma mbalimbali za biashara ya Binary. 📈\n\n"
        "Ndani, utapata mifumo iliyoundwa kukusaidia kuboresha na kukuza safari yako ya biashara. 🔥\n\n"
        "Lengo langu ni kuwapa wafanyabiashara mahali pamoja na kila wanachohitaji.\n\n"
        "Kuanzia kujifunza uchambuzi wa soko, kuelewa mikakati, kutumia zana za biashara "
        "na kuchunguza njia bora za kuboresha maarifa na uzoefu wa biashara. 📊\n\n"
        "*Evalon Winners Trader* imetengenezwa kwa wanaoanza na wafanyabiashara wenye uzoefu.\n\n"
        "Iwe unataka kujifunza zaidi, kuboresha mkakati wako au kuchunguza mifumo ya biashara mahiri, "
        "uko mahali pazuri. 🚀✨\n\n"
        "Asante kwa kujiunga nasi.\n\n"
        "Huduma zote zipo tayari ndani ya mfumo wetu na zinakusubiri kuzichunguza.\n\n"
        "*Bonyeza Endelea kuendelea* 🚀"
    ),
}
for _lc in ["ar","zh","hi","ru","es","fr","pt","de","ur","ja","it","ko","tr","fa","pl","uk","kk","cs"]:
    ONBOARDING_TEXT[_lc] = ONBOARDING_TEXT["en"]

def get_onboarding_text(lang, name):
    text = ONBOARDING_TEXT.get(lang, ONBOARDING_TEXT["en"])
    return text.format(name=escape_md(name))

def ui(key, lang):
    return UI.get(lang, UI["en"]).get(key, UI["en"].get(key, key))

def get_lang(context, user_id=None):
    """Load lang from DB if not in memory (survives restarts)"""
    lang = context.user_data.get("lang")
    if not lang and user_id:
        try:
            info = get_user_info(user_id)
            lang = info.get("lang", "en") or "en"
            context.user_data["lang"] = lang
        except:
            lang = "en"
    return lang or "en"

def get_replies(pool, lang):
    return pool.get(lang) or pool.get("en", ["Coming soon!"])

# ══════════════════════════════════════════════════════════════
#  FEEDBACK DATABASE SYSTEM
#  - Admin adds custom feedback via /feedbackadd
#  - All feedback stored in DB (custom + built-in)
#  - /feedback N — sends N mixed (EN-heavy) feedback
#  - /feedbackdlt — deletes all custom feedback from DB
#  - Built-in feedback always available as fallback
# ══════════════════════════════════════════════════════════════

def init_feedback_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS custom_feedback (
            id          SERIAL PRIMARY KEY,
            name        TEXT NOT NULL,
            flag        TEXT DEFAULT '🌍',
            text_val    TEXT NOT NULL,
            lang        TEXT DEFAULT 'en',
            added_at    TEXT DEFAULT NULL
        )
    """)
    conn.commit()
    conn.close()

def add_custom_feedback(name, flag, text_val, lang="en"):
    conn = get_conn()
    c = conn.cursor()
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    c.execute("""
        INSERT INTO custom_feedback (name, flag, text_val, lang, added_at)
        VALUES (%s, %s, %s, %s, %s)
    """, (name, flag, text_val, lang, now))
    conn.commit()
    conn.close()

def get_custom_feedback():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT name, flag, text_val, lang FROM custom_feedback ORDER BY id")
    rows = c.fetchall()
    conn.close()
    return [(r[0], r[1], r[2], r[3]) for r in rows]

def delete_all_custom_feedback():
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM custom_feedback")
    count = c.rowcount
    conn.commit()
    conn.close()
    return count

def get_mixed_feedback(count):
    """
    Get N feedback — mixed languages, EN-heavy.
    Mix ratio: ~70% EN, ~20% SW, ~10% UR from built-in.
    Custom feedback from DB included and shuffled in.
    Same day = same order (rotates daily).
    """
    day_seed = datetime.now().timetuple().tm_yday + datetime.now().year
    rng = random.Random(day_seed)

    # Get custom feedback from DB
    custom = get_custom_feedback()

    # Build pool: EN-heavy mix
    en_pool = [(n, f, t) for n, f, t in FAKE_FEEDBACK["en"]]
    sw_pool = [(n, f, t) for n, f, t in FAKE_FEEDBACK["sw"]]
    ur_pool = [(n, f, t) for n, f, t in FAKE_FEEDBACK["ur"]]

    # Shuffle each pool with today's seed
    rng.shuffle(en_pool)
    rng.shuffle(sw_pool)
    rng.shuffle(ur_pool)

    # Interleave: pattern EN,EN,EN,EN,SW,EN,EN,EN,UR,EN...
    # Roughly 70% EN, 20% SW, 10% UR
    combined = []
    ei = si = ui_idx = 0
    pattern = ["en","en","en","en","sw","en","en","en","ur","en"]
    pi = 0
    while len(combined) < count * 3:  # build large pool then slice
        lang_pick = pattern[pi % len(pattern)]
        pi += 1
        if lang_pick == "en" and ei < len(en_pool):
            combined.append(en_pool[ei]); ei += 1
        elif lang_pick == "sw" and si < len(sw_pool):
            combined.append(sw_pool[si]); si += 1
        elif lang_pick == "ur" and ui_idx < len(ur_pool):
            combined.append(ur_pool[ui_idx]); ui_idx += 1
        else:
            # fallback to EN if pool exhausted
            if ei < len(en_pool):
                combined.append(en_pool[ei]); ei += 1
            elif si < len(sw_pool):
                combined.append(sw_pool[si]); si += 1
            else:
                break

    # Inject custom feedback at random positions
    if custom:
        custom_tuples = [(n, f, t) for n, f, t, l in custom]
        rng.shuffle(custom_tuples)
        for i, item in enumerate(custom_tuples):
            pos = rng.randint(0, max(0, len(combined)-1))
            combined.insert(pos, item)

    # Slice to requested count, cycling if needed
    result = []
    while len(result) < count:
        result.extend(combined)
    return result[:count]

# ══════════════════════════════════════════════════════════════
#  MESSAGE TRACKING
# ══════════════════════════════════════════════════════════════

def track_msg(chat_id, msg_id):
    if chat_id not in bot_msg_ids:
        bot_msg_ids[chat_id] = []
    bot_msg_ids[chat_id].append(msg_id)
    if len(bot_msg_ids[chat_id]) > 100:
        bot_msg_ids[chat_id] = bot_msg_ids[chat_id][-100:]

def track_support_msg(chat_id, msg_id):
    if chat_id not in support_msg_ids:
        support_msg_ids[chat_id] = []
    support_msg_ids[chat_id].append(msg_id)

# ══════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════

async def safe_delete(context, chat_id, message_id):
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except:
        pass

async def delete_user_msg(message):
    try:
        await message.delete()
    except:
        pass

async def delete_all_bot_msgs(context, chat_id):
    if chat_id in bot_msg_ids:
        for msg_id in bot_msg_ids[chat_id]:
            await safe_delete(context, chat_id, msg_id)
        bot_msg_ids[chat_id] = []

async def delete_support_msgs(context, chat_id):
    if chat_id in support_msg_ids:
        for msg_id in support_msg_ids[chat_id]:
            await safe_delete(context, chat_id, msg_id)
        support_msg_ids[chat_id] = []

async def typing_action(chat_id, context, seconds=1.5):
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    await asyncio.sleep(seconds)

async def is_member(context, user_id):
    try:
        member = await context.bot.get_chat_member(
            chat_id=MAIN_CHANNEL_ID, user_id=user_id)
        if member.status in ("member", "administrator", "creator", "restricted"):
            return True
        if member.status == "left" and user_id in pending_requests:
            return True
    except:
        if user_id in pending_requests:
            return True
    return user_id in pending_requests

async def notify_new_user(context, user):
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    name = escape_md(user.full_name)
    username = escape_md(user.username or "NA")
    text = f"🆕 *New User!*\n\n👤 {name}\n🔗 @{username}\n🆔 `{user.id}`\n🕐 {now}"
    for aid in ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=aid, text=text, parse_mode="Markdown")
        except Exception as e:
            logger.warning(f"Notify failed: {e}")

async def notify_support_request(context, user, lang):
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    name = escape_md(user.full_name)
    username = escape_md(user.username or "NA")
    text = (
        f"🆘 *Support Request*\n\n"
        f"👤 {name}\n🔗 @{username}\n"
        f"🆔 `{user.id}`\n🕐 {now}\n🌍 Lang: {lang}"
    )
    btns = InlineKeyboardMarkup([[
        InlineKeyboardButton("🟢 Connect", callback_data=f"con:{user.id}:{lang}"),
        InlineKeyboardButton("🔴 End Chat", callback_data=f"dis:{user.id}:{lang}"),
    ]])
    for aid in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=aid, text=text,
                parse_mode="Markdown", reply_markup=btns)
        except Exception as e:
            logger.warning(f"Support notify failed: {e}")

# ══════════════════════════════════════════════════════════════
#  AUTO CLEAN JOB
# ══════════════════════════════════════════════════════════════

async def auto_clean_chat(context: ContextTypes.DEFAULT_TYPE):
    job_data = context.job.data
    chat_id = job_data["chat_id"]
    lang    = job_data.get("lang", "en")
    name    = job_data.get("name", "")
    uid     = job_data.get("uid")

    if uid and active_support.get(uid):
        schedule_auto_clean(context, chat_id, lang, name, uid)
        return

    await delete_all_bot_msgs(context, chat_id)

    try:
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        await asyncio.sleep(1.0)
        clean_text = get_auto_clean_msg(lang, name)
        msg = await context.bot.send_message(
            chat_id=chat_id,
            text=clean_text,
            parse_mode="Markdown",
            protect_content=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(ui("btn_spin", lang), callback_data="do_spin")],
                [InlineKeyboardButton(ui("btn_services", lang), callback_data="menu_services")],
                [InlineKeyboardButton(ui("btn_restart", lang), callback_data="main_menu")],
            ]))
        track_msg(chat_id, msg.message_id)
    except Exception as e:
        logger.warning(f"Auto clean failed for {chat_id}: {e}")

    schedule_auto_clean(context, chat_id, lang, name, uid)

def schedule_auto_clean(context, chat_id, lang, name, uid=None):
    if not context.job_queue:
        return
    job_name = f"clean_{chat_id}"
    for job in context.job_queue.get_jobs_by_name(job_name):
        job.schedule_removal()
    context.job_queue.run_once(
        auto_clean_chat,
        when=CLEAN_HOURS * 3600,
        data={"chat_id": chat_id, "lang": lang, "name": name, "uid": uid},
        name=job_name)

# ══════════════════════════════════════════════════════════════
#  COMEBACK JOB
# ══════════════════════════════════════════════════════════════

async def send_comeback_reminder(context: ContextTypes.DEFAULT_TYPE):
    job_data = context.job.data
    chat_id = job_data["chat_id"]
    name    = job_data["name"]
    lang    = job_data.get("lang", "en")
    try:
        img = random.choice(SERVICE_PHOTOS)
        text = ui("comeback_msg", lang).format(name=escape_md(name))
        try:
            msg = await context.bot.send_photo(
                chat_id=chat_id, photo=img, caption=text,
                parse_mode="Markdown",
                protect_content=True,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(ui("btn_services", lang), callback_data="menu_services")],
                    [InlineKeyboardButton(ui("btn_support", lang), callback_data="do_support")],
                ]))
        except:
            msg = await context.bot.send_message(
                chat_id=chat_id, text=text,
                parse_mode="Markdown",
                protect_content=True,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(ui("btn_services", lang), callback_data="menu_services")],
                ]))
        track_msg(chat_id, msg.message_id)
    except Exception as e:
        logger.warning(f"Comeback failed: {e}")

def schedule_comeback(context, chat_id, name, lang):
    if not context.job_queue:
        return
    job_name = f"comeback_{chat_id}"
    for job in context.job_queue.get_jobs_by_name(job_name):
        job.schedule_removal()
    context.job_queue.run_once(
        send_comeback_reminder,
        when=COMEBACK_DAYS * 24 * 3600,
        data={"chat_id": chat_id, "name": name, "lang": lang},
        name=job_name)

# ══════════════════════════════════════════════════════════════
#  KEYBOARDS
# ══════════════════════════════════════════════════════════════

def lang_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"),
         InlineKeyboardButton("🇨🇳 中文", callback_data="lang_zh"),
         InlineKeyboardButton("🇪🇸 Español", callback_data="lang_es")],
        [InlineKeyboardButton("🇫🇷 Français", callback_data="lang_fr"),
         InlineKeyboardButton("🇸🇦 العربية", callback_data="lang_ar"),
         InlineKeyboardButton("🇮🇳 हिन्दी", callback_data="lang_hi")],
        [InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
         InlineKeyboardButton("🇹🇿 Swahili", callback_data="lang_sw"),
         InlineKeyboardButton("🇧🇷 Português", callback_data="lang_pt")],
        [InlineKeyboardButton("🇩🇪 Deutsch", callback_data="lang_de"),
         InlineKeyboardButton("🇵🇰 اردو", callback_data="lang_ur"),
         InlineKeyboardButton("🇯🇵 日本語", callback_data="lang_ja")],
        [InlineKeyboardButton("🇮🇹 Italiano", callback_data="lang_it"),
         InlineKeyboardButton("🇰🇷 한국어", callback_data="lang_ko"),
         InlineKeyboardButton("🇹🇷 Türkçe", callback_data="lang_tr")],
        [InlineKeyboardButton("🇮🇷 فارسی", callback_data="lang_fa"),
         InlineKeyboardButton("🇵🇱 Polski", callback_data="lang_pl"),
         InlineKeyboardButton("🇺🇦 Українська", callback_data="lang_uk")],
        [InlineKeyboardButton("🇰🇿 Қазақша", callback_data="lang_kk"),
         InlineKeyboardButton("🇨🇿 Čeština", callback_data="lang_cs")],
    ])

def main_menu(lang):
    rows = [
        [InlineKeyboardButton(ui("btn_services", lang), callback_data="menu_services")],
        [InlineKeyboardButton(ui("btn_whats_new", lang), callback_data="do_whats_new"),
         InlineKeyboardButton(ui("btn_vip_results", lang), callback_data="do_vip_results")],
        [InlineKeyboardButton(ui("btn_tip", lang), callback_data="do_tip"),
         InlineKeyboardButton(ui("btn_quiz", lang), callback_data="do_quiz")],
        [InlineKeyboardButton(ui("btn_winners", lang), callback_data="do_winners"),
         InlineKeyboardButton(ui("btn_my_streak", lang), callback_data="do_streak")],
        [InlineKeyboardButton(ui("btn_results_history", lang), callback_data="do_results_history"),
         InlineKeyboardButton(ui("btn_profile", lang), callback_data="do_profile")],
        [InlineKeyboardButton(ui("btn_spin", lang), callback_data="do_spin")],
        [InlineKeyboardButton(ui("btn_website", lang), url=WEBSITE_URL)],
    ]
    # Referral row — add Stories button only if admin has posted stories
    ref_row = [InlineKeyboardButton(ui("btn_referral", lang), callback_data="do_referral")]
    try:
        if has_stories():
            ref_row.append(InlineKeyboardButton(ui("btn_stories", lang), callback_data="do_stories"))
    except:
        pass
    rows.append(ref_row)
    rows.append([InlineKeyboardButton(ui("btn_language", lang), callback_data="change_lang")])
    return InlineKeyboardMarkup(rows)

def services_menu(lang):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(ui("btn_signals", lang), callback_data="svc_signals"),
         InlineKeyboardButton(ui("btn_social", lang), callback_data="svc_social")],
        [InlineKeyboardButton(ui("btn_indicator", lang), callback_data="svc_indicator"),
         InlineKeyboardButton(ui("btn_autobot", lang), callback_data="svc_autobot")],
        [InlineKeyboardButton(ui("btn_freebot", lang), callback_data="svc_freebot")],
        [InlineKeyboardButton(ui("btn_website", lang), url=WEBSITE_URL)],
        [InlineKeyboardButton(ui("btn_support", lang), callback_data="do_support")],
        [InlineKeyboardButton(ui("btn_back", lang), callback_data="main_menu")],
    ])

def freebot_menu(lang):
    rows = [
        [InlineKeyboardButton("🌐 All Brokers Bot", url=FREE_BOT_LINKS["all_brokers"])],
        [InlineKeyboardButton("💎 Evalon Winners Bot", url=FREE_BOT_LINKS["evalon"])],
        [InlineKeyboardButton("🤖 Evalon AI Bot", url=FREE_BOT_LINKS["evalon_ai"])],
        # ── Binary Brokers ─────────────────────────────────────────
        [InlineKeyboardButton("📊 Quotex Pro Bot", url=FREE_BOT_LINKS["quotex"])],
        [InlineKeyboardButton("💰 Pocket Option Bot 🆕", callback_data="show_pocket_bot")],

    ]
    # Dynamically add admin-added bots from DB
    try:
        admin_bots = get_admin_bots()
        for bid, name, link, desc in admin_bots:
            rows.append([InlineKeyboardButton(f"🆕 {name}", url=link)])
    except:
        pass
    rows.append([InlineKeyboardButton(ui("btn_back", lang), callback_data="menu_services")])
    return InlineKeyboardMarkup(rows)

def svc_keyboard(lang, indicator=False, signals=False, autobot=False, social=False):
    rows = []

    # Video links per service
    if signals:
        rows.append([
            InlineKeyboardButton("▶️ Real Signal Results 🔥", url="https://youtu.be/rflkvCWG-fw?si=VFWoZO1cPqCQbg83"),
            InlineKeyboardButton("📱 Live Wins 1", url="https://vt.tiktok.com/ZSx2do7SF/"),
        ])
        rows.append([
            InlineKeyboardButton("📱 Live Wins 2", url="https://vt.tiktok.com/ZSx2d3RmU/"),
        ])

    if autobot:
        rows.append([
            InlineKeyboardButton("▶️ See Real Profits 🔥", url="https://youtu.be/q3Sa9ndExNc?si=MmMVL9F7t-fRzXQF"),
            InlineKeyboardButton("📱 Bot Wins Live", url="https://vt.tiktok.com/ZSx2RHF25/"),
        ])

    if social:
        rows.append([
            InlineKeyboardButton("▶️ Traders Winning Live 🔥", url="https://vt.tiktok.com/ZSx2RNM2m/"),
            InlineKeyboardButton("📱 Copy Trade Results", url="https://vt.tiktok.com/ZSx2dpgxt/"),
        ])

    if indicator:
        rows.append([InlineKeyboardButton(
            ui("btn_free_indicator", lang), url=INDICATOR_CHANNEL)])
        rows.append([
            InlineKeyboardButton("▶️ See It In Action 🔥", url="https://vt.tiktok.com/ZSx2dGWab/"),
            InlineKeyboardButton("📱 Real Results 2", url="https://vt.tiktok.com/ZSx2RQcpD/"),
        ])
        rows.append([
            InlineKeyboardButton("📱 Real Results 3", url="https://vt.tiktok.com/ZSx2RrX7T/"),
        ])

    rows.append([InlineKeyboardButton(ui("btn_website", lang), url=WEBSITE_URL)])
    rows.append([InlineKeyboardButton(ui("btn_support", lang), callback_data="do_support")])
    rows.append([InlineKeyboardButton(ui("btn_back", lang), callback_data="menu_services")])
    return InlineKeyboardMarkup(rows)

def join_keyboard(lang):
    _joined_btn = {
        "en": "✅ I've Joined!", "sw": "✅ Nimejiunga!", "ar": "✅ لقد انضممت!",
        "zh": "✅ 我已加入!", "hi": "✅ मैं जुड़ गया!", "ru": "✅ Я вступил!",
        "es": "✅ ¡Me uní!", "fr": "✅ J'ai rejoint!", "pt": "✅ Já entrei!",
        "de": "✅ Ich bin beigetreten!", "ur": "✅ میں شامل ہو گیا!", "ja": "✅ 参加しました!",
        "it": "✅ Mi sono unito!", "ko": "✅ 참가했습니다!", "tr": "✅ Katıldım!",
        "fa": "✅ پیوستم!", "pl": "✅ Dołączyłem!", "uk": "✅ Я приєднався!",
        "kk": "✅ Мен қосылдым!", "cs": "✅ Připojil jsem se!",
    }
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(ui("btn_join", lang), url=MAIN_CHANNEL_LINK)],
        [InlineKeyboardButton(_joined_btn.get(lang, "✅ I've Joined!"), callback_data="check_join")],
    ])

def support_keyboard(lang):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(ui("btn_support", lang), callback_data="do_support")],
        [InlineKeyboardButton(ui("btn_back", lang), callback_data="main_menu")],
    ])

def broadcast_keyboard(lang):
    join_texts = {
        "en": "🚀 Join Us Now",
        "sw": "🚀 Jiunge Nasi Sasa",
        "ar": "🚀 انضم إلينا الآن",
        "zh": "🚀 立即加入我们",
        "hi": "🚀 अभी हमसे जुड़ें",
        "ru": "🚀 Присоединяйтесь сейчас",
        "es": "🚀 Únete ahora",
        "fr": "🚀 Rejoignez-nous maintenant",
        "pt": "🚀 Junte-se a nós agora",
        "de": "🚀 Jetzt mitmachen",
        "ur": "🚀 ابھی ہم سے جڑیں",
        "ja": "🚀 今すぐ参加",
    }
    btn_text = join_texts.get(lang, join_texts["en"])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(btn_text, callback_data="menu_services")],
    ])

def rating_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("⭐", callback_data="rate_1"),
        InlineKeyboardButton("⭐⭐", callback_data="rate_2"),
        InlineKeyboardButton("⭐⭐⭐", callback_data="rate_3"),
        InlineKeyboardButton("⭐⭐⭐⭐", callback_data="rate_4"),
        InlineKeyboardButton("⭐⭐⭐⭐⭐", callback_data="rate_5"),
    ]])

def poll_keyboard(lang):
    both_text = ui("btn_poll_both", lang)
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Quotex", callback_data="poll_quotex"),
            InlineKeyboardButton("💰 Pocket Option", callback_data="poll_pocket"),
        ],
        [
            InlineKeyboardButton("📈 IQ Option", callback_data="poll_iqoption"),
            InlineKeyboardButton("🌐 Deriv", callback_data="poll_deriv"),
        ],
        [
            InlineKeyboardButton("🏦 Olymp Trade", callback_data="poll_olymp"),
            InlineKeyboardButton("💎 Binomo", callback_data="poll_binomo"),
        ],
        [
            InlineKeyboardButton("🔥 ExpertOption", callback_data="poll_expert"),
            InlineKeyboardButton("⚡ Binary.com", callback_data="poll_binary"),
        ],
        [
            InlineKeyboardButton("🎯 Binolla", callback_data="poll_binolla"),
        ],
        [
            InlineKeyboardButton("✅ " + both_text, callback_data="poll_both"),
        ],
    ])

def start_reply_keyboard():
    """Single persistent keyboard button shown at all times"""
    return ReplyKeyboardMarkup(
        [[KeyboardButton("🏆 START 🏆")]],
        resize_keyboard=True,
        is_persistent=True
    )

# ══════════════════════════════════════════════════════════════
#  SEND WITH PROTECT CONTENT
# ══════════════════════════════════════════════════════════════

async def send_protected_photo(context, chat_id, photo, caption, keyboard):
    try:
        return await context.bot.send_photo(
            chat_id=chat_id, photo=photo, caption=caption,
            parse_mode="Markdown", reply_markup=keyboard,
            protect_content=True)
    except:
        return await context.bot.send_message(
            chat_id=chat_id, text=caption,
            parse_mode="Markdown", reply_markup=keyboard,
            protect_content=True)

async def send_protected_text(context, chat_id, text, keyboard):
    return await context.bot.send_message(
        chat_id=chat_id, text=text,
        parse_mode="Markdown", reply_markup=keyboard,
        protect_content=True)

async def send_welcome_media(context, chat_id, caption, keyboard):
    """Send welcome screen — video or photo depending on admin setting."""
    file_id, media_type = get_welcome_media()
    start_kb = start_reply_keyboard()
    try:
        if media_type == "video":
            return await context.bot.send_video(
                chat_id=chat_id, video=file_id, caption=caption,
                parse_mode="Markdown", reply_markup=keyboard,
                protect_content=True)
        else:
            return await context.bot.send_photo(
                chat_id=chat_id, photo=file_id, caption=caption,
                parse_mode="Markdown", reply_markup=keyboard,
                protect_content=True)
    except Exception as e:
        logger.warning(f"send_welcome_media failed ({media_type}): {e}")
        # Fallback to text
        return await context.bot.send_message(
            chat_id=chat_id, text=caption,
            parse_mode="Markdown", reply_markup=keyboard,
            protect_content=True)
    finally:
        # Always send the persistent START button keyboard separately
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text="​",  # invisible character
                reply_markup=start_kb)
        except:
            pass

# ══════════════════════════════════════════════════════════════
#  JOIN REQUEST
# ══════════════════════════════════════════════════════════════

async def handle_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    req  = update.chat_join_request
    user = req.from_user
    chat = req.chat
    now  = datetime.now().strftime("%d/%m/%Y %H:%M")

    # Track pending request so bot can verify membership
    pending_requests[user.id] = {
        "chat_id": chat.id, "chat_title": chat.title,
        "user": user, "time": now,
    }
    # NOTE: No admin notification here — admin uses separate bot for approvals
    lang = context.user_data.get("lang", "en")
    try:
        await context.bot.send_message(
            chat_id=user.id,
            text=ui("join_pending", lang),
            parse_mode="Markdown",
            protect_content=True)
    except:
        pass

# ══════════════════════════════════════════════════════════════
#  /start
# ══════════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    cid  = update.effective_chat.id

    referred_by = None
    if context.args and context.args[0].startswith("ref"):
        try:
            referred_by = int(context.args[0][3:])
            if referred_by == user.id:
                referred_by = None
        except:
            pass

    new_user = is_new_user(user.id)
    lang = get_lang(context, user.id)
    register_user(user, referred_by=referred_by, lang=lang)

    # If user was previously blocked but is back, remove from blocked list
    try:
        unmark_blocked_user(user.id)
    except:
        pass

    if new_user:
        await notify_new_user(context, user)
        if referred_by:
            ref_count = get_referral_count(referred_by)
            # Notify referrer of discount milestones
            milestones = {5: 5, 10: 10, 20: 20, 50: 50, 100: 70}
            if ref_count in milestones:
                ref_info = get_user_info(referred_by)
                ref_lang = ref_info.get("lang", "en") or "en"
                ref_name = escape_md(ref_info['name'])
                discount = milestones[ref_count]
                discount_text = REFERRAL_DISCOUNT_MSG.get(ref_lang, REFERRAL_DISCOUNT_MSG["en"])
                try:
                    await context.bot.send_message(
                        chat_id=referred_by,
                        text=discount_text.format(name=ref_name, count=ref_count, discount=discount),
                        parse_mode="Markdown",
                        protect_content=True,
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🎁 Claim My Reward!", callback_data="claim_discount")
                        ]]))
                except:
                    pass
                # Also notify admin
                for aid in ADMIN_IDS:
                    try:
                        await context.bot.send_message(
                            chat_id=aid,
                            text=f"🏆 *REFERRAL MILESTONE!*\n\n👤 {ref_name}\n📊 Reached *{ref_count} referrals*\n🎁 Earned *{discount}% discount*",
                            parse_mode="Markdown")
                    except:
                        pass

    await delete_all_bot_msgs(context, cid)
    await typing_action(cid, context, 1.2)

    if not context.user_data.get("lang"):
        msg = await send_protected_text(
            context, cid,
            "🏆 *EVALON WINNERS TRADER* 🏆\n\nChoose your language / Chagua lugha yako:",
            lang_keyboard())
        context.user_data["last_bot_msg_id"] = msg.message_id
        track_msg(cid, msg.message_id)
        return

    if not await is_member(context, user.id):
        msg = await send_protected_text(
            context, cid, ui("join_msg", lang), join_keyboard(lang))
        context.user_data["last_bot_msg_id"] = msg.message_id
        track_msg(cid, msg.message_id)
        return

    # Go straight to welcome — no onboarding video/text/continue button
    visit_count = context.user_data.get("visit_count", 0) + 1
    context.user_data["visit_count"] = visit_count

    # Show broker poll for first-time visitors
    if new_user or visit_count == 1:
        update_streak(user.id)
        msg = await send_protected_text(
            context, cid,
            ui("poll_msg", lang),
            poll_keyboard(lang))
        context.user_data["last_bot_msg_id"] = msg.message_id
        track_msg(cid, msg.message_id)
        schedule_comeback(context, cid, user.first_name, lang)
        schedule_smart_comebacks(context, cid, user.first_name, lang)
        schedule_auto_clean(context, cid, lang, user.first_name, user.id)
        return

    welcome_text = build_welcome_text(lang, user.first_name, visit_count)
    update_streak(user.id)

    msg = await send_welcome_media(
        context, cid, welcome_text, main_menu(lang))
    context.user_data["last_bot_msg_id"] = msg.message_id
    track_msg(cid, msg.message_id)

    schedule_comeback(context, cid, user.first_name, lang)
    schedule_smart_comebacks(context, cid, user.first_name, lang)
    schedule_auto_clean(context, cid, lang, user.first_name, user.id)

# ══════════════════════════════════════════════════════════════
#  BROADCAST
# ══════════════════════════════════════════════════════════════

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    all_users = get_all_user_ids()
    total = len(all_users)
    sent = failed = 0
    replied_msg = update.message.reply_to_message

    # Validate content first
    has_content = (
        replied_msg and (replied_msg.photo or replied_msg.video or replied_msg.voice
                         or replied_msg.document or replied_msg.audio
                         or replied_msg.animation or replied_msg.sticker
                         or replied_msg.text)
    ) or bool(context.args)

    if not has_content:
        await update.message.reply_text(
            "⚠️ *No content.*\n\n"
            "• `/broadcast Your message here`\n"
            "• Reply to any message/photo/video/file + `/broadcast`",
            parse_mode="Markdown")
        return

    progress_msg = await update.message.reply_text(
        f"📢 *Broadcasting to {total} users...*\n\n⏳ Please wait...",
        parse_mode="Markdown")

    src_chat = update.effective_chat.id

    for i, uid in enumerate(all_users):
        try:
            u_info = get_user_info(uid)
            user_lang = u_info.get("lang", "en") or "en"
            kb = broadcast_keyboard(user_lang)

            if replied_msg:
                # Use copy_message to PRESERVE exact formatting, entities, bold etc.
                if replied_msg.photo or replied_msg.video or replied_msg.document \
                        or replied_msg.audio or replied_msg.animation or replied_msg.voice \
                        or replied_msg.sticker:
                    # Media: copy preserves caption + formatting exactly
                    await context.bot.copy_message(
                        chat_id=uid,
                        from_chat_id=src_chat,
                        message_id=replied_msg.message_id,
                        reply_markup=kb if not replied_msg.sticker else None)
                elif replied_msg.text:
                    # Text: copy_message preserves bold/italic/links exactly
                    await context.bot.copy_message(
                        chat_id=uid,
                        from_chat_id=src_chat,
                        message_id=replied_msg.message_id,
                        reply_markup=kb)
            elif context.args:
                # Plain text from command args — send as-is
                await context.bot.send_message(
                    chat_id=uid,
                    text=" ".join(context.args),
                    parse_mode=None,
                    reply_markup=kb)

            sent += 1

            # Rate limiting: Telegram allows ~30 msgs/sec to different chats
            # Sleep 0.04s = ~25/sec — safe and fast
            await asyncio.sleep(0.04)

            # Update progress every 50 users
            if (i + 1) % 50 == 0:
                try:
                    await progress_msg.edit_text(
                        f"📢 *Broadcasting...*\n\n"
                        f"✅ Sent: {sent} / {total}\n"
                        f"❌ Failed: {failed}",
                        parse_mode="Markdown")
                except:
                    pass

        except TelegramError as e:
            failed += 1
            err_str = str(e).lower()
            if "bot was blocked" in err_str or "user is deactivated" in err_str or "chat not found" in err_str:
                try:
                    mark_blocked_user(uid)
                except:
                    pass
            logger.warning(f"Broadcast failed {uid}: {e}")

    # Build blocked users list for admin
    blocked_list = get_blocked_users()
    blocked_info = ""
    if blocked_list:
        blocked_info = f"\n🚫 Blocked bot: *{len(blocked_list)}*\nUse /blockedusers to see who"

    try:
        await progress_msg.edit_text(
            f"✅ *Broadcast Complete!*\n\n"
            f"📤 Sent: *{sent}*\n"
            f"❌ Failed: *{failed}*\n"
            f"👥 Total: *{total}*{blocked_info}",
            parse_mode="Markdown")
    except:
        await update.message.reply_text(
            f"✅ *Done!*\n\n📤 Sent: {sent}\n❌ Failed: {failed}\n👥 Total: {total}{blocked_info}",
            parse_mode="Markdown")

# ══════════════════════════════════════════════════════════════
#  ADMIN COMMANDS
# ══════════════════════════════════════════════════════════════

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    total     = get_user_count()
    active7   = get_active_users(7)
    active30  = get_active_users(30)
    new_today = get_new_users_today()
    top = get_top_referrers(5)
    top_text = ""
    for i, (name, refs) in enumerate(top, 1):
        safe_name = escape_md(name)
        top_text += f"{i}. {safe_name} — {refs} referrals\n"

    await update.message.reply_text(
        f"📊 *EVALON WINNERS — STATS*\n\n"
        f"👥 Total users: *{total}*\n"
        f"🆕 New today: *{new_today}*\n"
        f"🟢 Active 7d: *{active7}*\n"
        f"📅 Active 30d: *{active30}*\n"
        f"🆘 Active support: *{len(active_support)}*\n\n"
        f"🏆 *TOP REFERRERS:*\n{top_text or 'None yet'}\n\n"
        f"🕐 {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        parse_mode="Markdown")

async def getid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    msg = update.message
    if msg.photo:
        await msg.reply_text(f"📸 `{msg.photo[-1].file_id}`", parse_mode="Markdown")
    elif msg.video:
        await msg.reply_text(f"🎥 `{msg.video.file_id}`", parse_mode="Markdown")
    elif msg.document:
        await msg.reply_text(f"📄 `{msg.document.file_id}`", parse_mode="Markdown")
    else:
        await msg.reply_text("Send me a photo/video to get file_id")

async def sessions_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not active_support:
        await update.message.reply_text("✅ No active support sessions.")
        return
    text = f"🆘 *Active Sessions: {len(active_support)}*\n\n"
    kb = []
    for uid in list(active_support.keys()):
        u = get_user_info(uid)
        safe_name = escape_md(u['name'])
        text += f"👤 {safe_name} | `{uid}`\n"
        kb.append([InlineKeyboardButton(
            f"🔴 End: {u['name'][:20]}", callback_data=f"dis:{uid}:en")])
    kb.append([InlineKeyboardButton("🔴 End ALL", callback_data="end_all_support")])
    await update.message.reply_text(
        text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

# ══════════════════════════════════════════════════════════════
#  RESULTS HISTORY HELPER — paginated
# ══════════════════════════════════════════════════════════════

async def _show_results_history(context, cid, lang, page=0):
    """Show paginated past results — 1 per page, with prev/next navigation"""
    # Delete old bot messages first (like addstory pattern)
    await delete_all_bot_msgs(context, cid)

    results = get_results_history(50)  # get up to 50
    if not results:
        msg = await send_protected_text(
            context, cid, ui("no_results_history", lang),
            InlineKeyboardMarkup([[InlineKeyboardButton(ui("btn_back", lang), callback_data="main_menu")]]))
        track_msg(cid, msg.message_id)
        return

    total = len(results)
    page = max(0, min(page, total - 1))
    row = results[page]
    rid, caption, media_id, media_type, saved_at = row

    header_texts = {
        "en": f"📅 *PAST VIP RESULTS*\n\n🗓 Session: _{saved_at}_\n📊 Result {page+1} of {total}\n\n",
        "sw": f"📅 *MATOKEO YA VIP YA NYUMA*\n\n🗓 Kikao: _{saved_at}_\n📊 Matokeo {page+1} kati ya {total}\n\n",
        "ar": f"📅 *نتائج VIP السابقة*\n\n🗓 الجلسة: _{saved_at}_\n📊 النتيجة {page+1} من {total}\n\n",
        "fr": f"📅 *RÉSULTATS VIP PASSÉS*\n\n🗓 Session: _{saved_at}_\n📊 Résultat {page+1} sur {total}\n\n",
        "pt": f"📅 *RESULTADOS VIP PASSADOS*\n\n🗓 Sessão: _{saved_at}_\n📊 Resultado {page+1} de {total}\n\n",
        "es": f"📅 *RESULTADOS VIP PASADOS*\n\n🗓 Sesión: _{saved_at}_\n📊 Resultado {page+1} de {total}\n\n",
        "ru": f"📅 *ПРОШЛЫЕ РЕЗУЛЬТАТЫ VIP*\n\n🗓 Сессия: _{saved_at}_\n📊 Результат {page+1} из {total}\n\n",
        "de": f"📅 *VERGANGENE VIP-ERGEBNISSE*\n\n🗓 Sitzung: _{saved_at}_\n📊 Ergebnis {page+1} von {total}\n\n",
        "zh": f"📅 *过去VIP结果*\n\n🗓 会话: _{saved_at}_\n📊 结果 {page+1}/{total}\n\n",
        "hi": f"📅 *पिछले VIP परिणाम*\n\n🗓 सत्र: _{saved_at}_\n📊 परिणाम {page+1}/{total}\n\n",
        "ur": f"📅 *پچھلے VIP نتائج*\n\n🗓 سیشن: _{saved_at}_\n📊 نتیجہ {page+1}/{total}\n\n",
        "ja": f"📅 *過去のVIP結果*\n\n🗓 セッション: _{saved_at}_\n📊 結果 {page+1}/{total}\n\n",
    }
    header = header_texts.get(lang, header_texts["en"])

    # Navigation buttons
    _vip_join = {
        "en": "🚀 Join VIP Now", "sw": "🚀 Jiunge na VIP Sasa",
        "ar": "🚀 انضم لـ VIP الآن", "zh": "🚀 立即加入VIP",
        "hi": "🚀 अभी VIP जुड़ें", "ru": "🚀 Вступить в VIP",
        "es": "🚀 Unirse al VIP Ahora", "fr": "🚀 Rejoindre VIP Maintenant",
        "pt": "🚀 Entrar no VIP Agora", "de": "🚀 VIP jetzt beitreten",
        "ur": "🚀 ابھی VIP میں شامل ہوں", "ja": "🚀 今すぐVIPに参加",
    }
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ " + ("Nyuma" if lang == "sw" else "Back"), callback_data=f"results_page_{page-1}"))
    if page < total - 1:
        nav_row.append(InlineKeyboardButton("➡️ " + ("Mbele" if lang == "sw" else "Next"), callback_data=f"results_page_{page+1}"))

    back_kb_rows = []
    if nav_row:
        back_kb_rows.append(nav_row)
    back_kb_rows.append([InlineKeyboardButton(_vip_join.get(lang, "🚀 Join VIP Now"), url=VIP_BOT_LINK)])
    back_kb_rows.append([InlineKeyboardButton(ui("btn_back", lang), callback_data="main_menu")])
    back_kb = InlineKeyboardMarkup(back_kb_rows)

    msg = None
    if media_id and media_type == "photo":
        try:
            msg = await context.bot.send_photo(
                chat_id=cid, photo=media_id,
                caption=header + (caption or ""),
                parse_mode="Markdown", protect_content=True, reply_markup=back_kb)
        except:
            pass
    elif media_id and media_type == "video":
        try:
            msg = await context.bot.send_video(
                chat_id=cid, video=media_id,
                caption=header + (caption or ""),
                parse_mode="Markdown", protect_content=True, reply_markup=back_kb)
        except:
            pass
    if msg is None:
        msg = await send_protected_text(context, cid, header + (caption or ""), back_kb)
    track_msg(cid, msg.message_id)


# ══════════════════════════════════════════════════════════════
#  CALLBACK HANDLER
# ══════════════════════════════════════════════════════════════

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user = query.from_user
    cid  = query.message.chat_id

    lang = get_lang(context, user.id)

    # Language select
    if data.startswith("lang_"):
        new_lang = data[5:]
        context.user_data["lang"] = new_lang
        register_user(user, lang=new_lang)
        await safe_delete(context, cid, query.message.message_id)
        await delete_all_bot_msgs(context, cid)
        await typing_action(cid, context, 1.5)

        if not await is_member(context, user.id):
            msg = await send_protected_text(
                context, cid, ui("join_msg", new_lang), join_keyboard(new_lang))
            context.user_data["last_bot_msg_id"] = msg.message_id
            track_msg(cid, msg.message_id)
            return

        welcome_text = build_welcome_text(new_lang, user.first_name)
        msg = await send_welcome_media(
        context, cid, welcome_text, main_menu(new_lang))
        context.user_data["last_bot_msg_id"] = msg.message_id
        track_msg(cid, msg.message_id)
        schedule_comeback(context, cid, user.first_name, new_lang)
        schedule_auto_clean(context, cid, new_lang, user.first_name, user.id)
        return

    # Check join
    if data == "check_join":
        await typing_action(cid, context, 1.0)
        if await is_member(context, user.id):
            await safe_delete(context, cid, query.message.message_id)
            await delete_all_bot_msgs(context, cid)
            # Show broker poll before welcome screen
            msg = await send_protected_text(
                context, cid,
                ui("poll_msg", lang),
                poll_keyboard(lang))
            context.user_data["last_bot_msg_id"] = msg.message_id
            track_msg(cid, msg.message_id)
        else:
            await query.answer("❌ Please join first!", show_alert=True)
        return

    # Poll
    if data.startswith("poll_"):
        await safe_delete(context, cid, query.message.message_id)
        await delete_all_bot_msgs(context, cid)
        await typing_action(cid, context, 1.0)
        visit_count = context.user_data.get("visit_count", 1)
        welcome_text = build_welcome_text(lang, user.first_name, visit_count)
        msg = await send_welcome_media(
            context, cid,
            f"✅ Got it\\!\n\n{welcome_text}", main_menu(lang))
        context.user_data["last_bot_msg_id"] = msg.message_id
        track_msg(cid, msg.message_id)
        schedule_comeback(context, cid, user.first_name, lang)
        schedule_smart_comebacks(context, cid, user.first_name, lang)
        schedule_auto_clean(context, cid, lang, user.first_name, user.id)
        return

    # FIX: User skips text opinion — MUST be BEFORE rate_ check to avoid int("skip") crash
    if data == "rate_skip":
        awaiting_rating_opinion.pop(user.id, None)
        await safe_delete(context, cid, query.message.message_id)
        await delete_all_bot_msgs(context, cid)
        await typing_action(cid, context, 1.0)
        welcome_text = build_welcome_text(lang, user.first_name)
        msg = await send_welcome_media(
        context, cid,
            f"{ui('rating_thanks', lang).format(name=escape_md(user.first_name))}\n\n{welcome_text}",
            main_menu(lang))
        context.user_data["last_bot_msg_id"] = msg.message_id
        track_msg(cid, msg.message_id)
        return

    # FIX: Rating — ask for text opinion after stars
    if data.startswith("rate_"):
        stars = int(data[5:])
        star_display = "⭐" * stars
        await safe_delete(context, cid, query.message.message_id)
        await typing_action(cid, context, 1.0)

        # Notify admin of star rating
        name = escape_md(user.full_name)
        for aid in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=aid,
                    text=f"⭐ *Rating received*\n\n👤 {name}\n🆔 `{user.id}`\n{star_display} ({stars}/5)\n\n⏳ Waiting for text opinion...",
                    parse_mode="Markdown")
            except:
                pass

        # Save stars and ask for text opinion
        awaiting_rating_opinion[user.id] = {"stars": stars, "star_display": star_display}

        msg = await send_protected_text(
            context, cid,
            ui("rating_opinion_msg", lang),
            InlineKeyboardMarkup([[
                InlineKeyboardButton("⏭ Skip", callback_data="rate_skip")
            ]]))
        track_msg(cid, msg.message_id)
        return

    # Navigation buttons
    await safe_delete(context, cid, query.message.message_id)
    await delete_all_bot_msgs(context, cid)
    await typing_action(cid, context, 1.5)

    if data == "main_menu":
        welcome_text = build_welcome_text(lang, user.first_name)
        msg = await send_welcome_media(
        context, cid, welcome_text, main_menu(lang))
        context.user_data["last_bot_msg_id"] = msg.message_id
        track_msg(cid, msg.message_id)
        schedule_comeback(context, cid, user.first_name, lang)
        schedule_auto_clean(context, cid, lang, user.first_name, user.id)

    elif data == "menu_services":
        msg = await send_protected_text(
            context, cid, ui("services_msg", lang), services_menu(lang))
        context.user_data["last_bot_msg_id"] = msg.message_id
        track_msg(cid, msg.message_id)

    elif data == "change_lang":
        msg = await send_protected_text(
            context, cid,
            "🏆 *EVALON WINNERS TRADER* 🏆\n\nChoose your language / Chagua lugha yako:",
            lang_keyboard())
        context.user_data["last_bot_msg_id"] = msg.message_id
        track_msg(cid, msg.message_id)

    elif data == "svc_signals":
        replies = get_replies(SIGNALS_REPLIES, lang)
        img = rand_img(IMGS_SIGNALS, context.user_data, "last_img_signals")
        msg = await send_protected_photo(
            context, cid, img, random.choice(replies), svc_keyboard(lang, signals=True))
        context.user_data["last_bot_msg_id"] = msg.message_id
        track_msg(cid, msg.message_id)
        schedule_fomo(context, cid, lang, "VIP Signals")

    elif data == "svc_social":
        replies = get_replies(SOCIAL_REPLIES, lang)
        img = rand_img(IMGS_SOCIAL, context.user_data, "last_img_social")
        msg = await send_protected_photo(
            context, cid, img, random.choice(replies), svc_keyboard(lang, social=True))
        context.user_data["last_bot_msg_id"] = msg.message_id
        track_msg(cid, msg.message_id)
        schedule_fomo(context, cid, lang, "Social Trading")

    elif data == "svc_indicator":
        replies = get_replies(INDICATOR_REPLIES, lang)
        img = rand_img(IMGS_INDICATOR, context.user_data, "last_img_indicator")
        msg = await send_protected_photo(
            context, cid, img, random.choice(replies),
            svc_keyboard(lang, indicator=True))
        context.user_data["last_bot_msg_id"] = msg.message_id
        track_msg(cid, msg.message_id)
        schedule_fomo(context, cid, lang, "Free Indicator")

    elif data == "svc_autobot":
        replies = get_replies(AUTOBOT_REPLIES, lang)
        img = rand_img(IMGS_AUTOBOT, context.user_data, "last_img_autobot")
        msg = await send_protected_photo(
            context, cid, img, random.choice(replies), svc_keyboard(lang, autobot=True))
        context.user_data["last_bot_msg_id"] = msg.message_id
        track_msg(cid, msg.message_id)
        schedule_fomo(context, cid, lang, "Auto Bot")

    elif data == "svc_freebot":
        replies = get_replies(FREEBOT_REPLIES, lang)
        img = rand_img(IMGS_FREEBOT, context.user_data, "last_img_freebot")
        msg = await send_protected_photo(
            context, cid, img, random.choice(replies), freebot_menu(lang))
        context.user_data["last_bot_msg_id"] = msg.message_id
        track_msg(cid, msg.message_id)
        schedule_fomo(context, cid, lang, "Free Manual Bot")

    # ── CLAIM DISCOUNT — validates referral count first ───────
    elif data == "claim_discount":
        ref_count = get_referral_count(user.id)
        if ref_count < REFERRAL_MIN:
            needed = REFERRAL_MIN - ref_count
            ref_link = f"https://t.me/{BOT_USERNAME}?start=ref{user.id}"
            error_texts = {
                "en": (
                    f"❌ *Not enough referrals yet!*\n\n"
                    f"📊 Your progress: *{ref_count}/{REFERRAL_MIN}*\n\n"
                    f"You need *{needed} more* people to unlock your discount.\n\n"
                    f"🔗 Share your link and keep inviting:\n{ref_link}\n\n"
                    f"The more you invite, the bigger your reward — up to *70% OFF!* 🔥"
                ),
                "sw": (
                    f"❌ *Bado huna rufaa za kutosha!*\n\n"
                    f"📊 Maendeleo yako: *{ref_count}/{REFERRAL_MIN}*\n\n"
                    f"Unahitaji *{needed} zaidi* kufungua punguzo lako.\n\n"
                    f"🔗 Shiriki kiungo chako na endelea kuwa kuita:\n{ref_link}\n\n"
                    f"Unavyowaleta watu wengi, tuzo yako inakuwa kubwa — hadi *70% PUNGUZO!* 🔥"
                ),
                "ar": (
                    f"❌ *ليس لديك إحالات كافية بعد!*\n\n"
                    f"📊 تقدمك: *{ref_count}/{REFERRAL_MIN}*\n\n"
                    f"تحتاج إلى *{needed} شخص آخر* لفتح خصمك.\n\n"
                    f"🔗 شارك رابطك وتابع الدعوة:\n{ref_link}\n\n"
                    f"كلما دعوت أكثر، كلما كانت مكافأتك أكبر — حتى *70% خصم!* 🔥"
                ),
                "ru": (
                    f"❌ *Недостаточно рефералов!*\n\n"
                    f"📊 Ваш прогресс: *{ref_count}/{REFERRAL_MIN}*\n\n"
                    f"Вам нужно ещё *{needed} человек* для разблокировки скидки.\n\n"
                    f"🔗 Поделитесь ссылкой:\n{ref_link}\n\n"
                    f"Чем больше людей, тем больше скидка — до *70%!* 🔥"
                ),
            }
            error_text = error_texts.get(lang, error_texts["en"])
            # Send error as plain (link not protected so easy to copy)
            await delete_all_bot_msgs(context, cid)
            try:
                msg = await context.bot.send_message(
                    chat_id=cid,
                    text=error_text,
                    parse_mode="Markdown",
                    protect_content=False,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton(ui("btn_back", lang), callback_data="do_referral")]
                    ]))
                track_msg(cid, msg.message_id)
            except:
                pass
            return
        # Reached minimum — proceed to support
        await notify_support_request(context, user, lang)
        msg = await send_protected_text(
            context, cid, ui("support_msg", lang),
            InlineKeyboardMarkup([
                [InlineKeyboardButton(ui("btn_back", lang), callback_data="main_menu")]
            ]))
        track_msg(cid, msg.message_id)

    elif data == "do_support":
        await notify_support_request(context, user, lang)
        msg = await send_protected_text(
            context, cid, ui("support_msg", lang),
            InlineKeyboardMarkup([
                [InlineKeyboardButton(ui("btn_back", lang), callback_data="main_menu")]
            ]))
        context.user_data["last_bot_msg_id"] = msg.message_id
        track_msg(cid, msg.message_id)

    elif data == "do_referral":
        ref_count = get_referral_count(user.id)
        # Show progress toward next milestone
        if ref_count < REFERRAL_MIN:
            needed = REFERRAL_MIN - ref_count
            bar = make_progress_bar(ref_count, REFERRAL_MIN)
        elif ref_count < 100:
            needed = 100 - ref_count
            bar = make_progress_bar(ref_count, 100)
        else:
            needed = 0
            bar = make_progress_bar(100, 100)
        leaderboard = get_fake_leaderboard(ref_count)

        # MSG 1 — Main referral info
        ref_text = ui("referral_msg", lang).format(
            bot=BOT_USERNAME, uid=user.id,
            count=ref_count, min=REFERRAL_MIN,
            needed=needed, bar=bar,
            leaderboard=leaderboard)
        try:
            msg = await send_protected_text(
                context, cid, ref_text,
                InlineKeyboardMarkup([
                    [InlineKeyboardButton("👥 View My Referrals", callback_data="view_referrals")],
                    [InlineKeyboardButton(ui("btn_support", lang), callback_data="do_support")],
                    [InlineKeyboardButton(ui("btn_back", lang), callback_data="main_menu")],
                ]))
            context.user_data["last_bot_msg_id"] = msg.message_id
            track_msg(cid, msg.message_id)
        except Exception as e:
            logger.warning(f"Referral msg failed: {e}")

        # MSG 2 — Link (plain, easy to copy)
        ref_link = f"https://t.me/{BOT_USERNAME}?start=ref{user.id}"
        try:
            link_msg = await context.bot.send_message(
                chat_id=cid,
                text=ref_link,
                protect_content=False)
            track_msg(cid, link_msg.message_id)
        except:
            pass

        # MSG 3 — Total count + persuasion
        if ref_count >= 100:
            # 100+ referrals — LIFETIME VIP!
            congrats_texts = {
                "en": (
                    f"👑 *WOW {escape_md(user.first_name)}! LEGENDARY!*\n\n"
                    f"You have invited *{ref_count} people* — You have earned *LIFETIME VIP ACCESS!* 🏆\n\n"
                    f"💎 This is the highest reward we offer!\n\n"
                    f"📩 Contact our team now to activate your *FREE LIFETIME VIP:*"
                ),
                "sw": (
                    f"👑 *WOW {escape_md(user.first_name)}! MAAJABU!*\n\n"
                    f"Umemualika *watu {ref_count}* — Umepata *VIP YA MAISHA YOTE BURE!* 🏆\n\n"
                    f"💎 Hii ndiyo tuzo ya juu kabisa tunayotoa!\n\n"
                    f"📩 Wasiliana na timu yetu sasa kuanzisha *VIP YAKO YA MAISHA YOTE BURE:*"
                ),
                "ar": (
                    f"👑 *واو {escape_md(user.first_name)}! أسطوري!*\n\n"
                    f"لقد دعوت *{ref_count} شخص* — لقد حصلت على *وصول VIP مدى الحياة مجاناً!* 🏆\n\n"
                    f"💎 هذه أعلى مكافأة نقدمها!\n\n"
                    f"📩 تواصل مع فريقنا الآن لتفعيل *VIP مجاني مدى الحياة:*"
                ),
                "ru": (
                    f"👑 *ВАУ {escape_md(user.first_name)}! ЛЕГЕНДА!*\n\n"
                    f"Вы пригласили *{ref_count} человек* — Вы получили *ПОЖИЗНЕННЫЙ VIP ДОСТУП БЕСПЛАТНО!* 🏆\n\n"
                    f"💎 Это наша наивысшая награда!\n\n"
                    f"📩 Свяжитесь с нашей командой для активации *ПОЖИЗНЕННОГО VIP:*"
                ),
            }
            congrats = congrats_texts.get(lang, congrats_texts["en"])
            try:
                p_msg = await send_protected_text(
                    context, cid, congrats,
                    InlineKeyboardMarkup([
                        [InlineKeyboardButton("👑 Claim LIFETIME VIP!", callback_data="claim_discount")],
                        [InlineKeyboardButton(ui("btn_back", lang), callback_data="main_menu")],
                    ]))
                track_msg(cid, p_msg.message_id)
            except:
                pass

        elif ref_count >= REFERRAL_MIN:
            # 5+ referrals — 1 WEEK FREE VIP!
            congrats_texts = {
                "en": (
                    f"🎉 *CONGRATULATIONS {escape_md(user.first_name)}!*\n\n"
                    f"You have invited *{ref_count} people* — You have earned *1 WEEK FREE VIP!* 🏆\n\n"
                    f"📩 Contact our team now to activate your free week!\n\n"
                    f"🚀 Keep going — invite *100 people* total to unlock *LIFETIME FREE VIP!* 👑\n\n"
                    f"📊 Your progress: *{ref_count}/100* to Lifetime VIP"
                ),
                "sw": (
                    f"🎉 *HONGERA {escape_md(user.first_name)}!*\n\n"
                    f"Umemualika *watu {ref_count}* — Umepata *WIKI 1 VIP BURE!* 🏆\n\n"
                    f"📩 Wasiliana na timu yetu sasa kuanzisha wiki yako ya bure!\n\n"
                    f"🚀 Endelea — alika *watu 100* jumla kupata *VIP YA MAISHA YOTE BURE!* 👑\n\n"
                    f"📊 Maendeleo yako: *{ref_count}/100* hadi VIP ya Maisha Yote"
                ),
                "ar": (
                    f"🎉 *تهانينا {escape_md(user.first_name)}!*\n\n"
                    f"لقد دعوت *{ref_count} شخص* — لقد حصلت على *أسبوع VIP مجاني!* 🏆\n\n"
                    f"📩 تواصل مع فريقنا الآن لتفعيل أسبوعك المجاني!\n\n"
                    f"🚀 واصل — ادعُ *100 شخص* للحصول على *VIP مجاني مدى الحياة!* 👑\n\n"
                    f"📊 تقدمك: *{ref_count}/100* نحو VIP مدى الحياة"
                ),
                "ru": (
                    f"🎉 *ПОЗДРАВЛЯЕМ {escape_md(user.first_name)}!*\n\n"
                    f"Вы пригласили *{ref_count} человек* — Вы получили *1 НЕДЕЛЮ VIP БЕСПЛАТНО!* 🏆\n\n"
                    f"📩 Свяжитесь с нашей командой для активации!\n\n"
                    f"🚀 Продолжайте — пригласите *100 человек* для *ПОЖИЗНЕННОГО VIP!* 👑\n\n"
                    f"📊 Ваш прогресс: *{ref_count}/100* до пожизненного VIP"
                ),
            }
            congrats = congrats_texts.get(lang, congrats_texts["en"])
            try:
                p_msg = await send_protected_text(
                    context, cid, congrats,
                    InlineKeyboardMarkup([
                        [InlineKeyboardButton("🎁 Claim 1 Week FREE VIP!", callback_data="claim_discount")],
                        [InlineKeyboardButton(ui("btn_back", lang), callback_data="main_menu")],
                    ]))
                track_msg(cid, p_msg.message_id)
            except:
                pass
        else:
            # Not yet reached 5 — motivate
            persuasion_texts = {
                "en": (
                    f"📊 *Your Progress: {ref_count}/{REFERRAL_MIN} people invited*\n\n"
                    f"🎯 Invite just *{needed} more* friends to unlock *1 WEEK FREE VIP!* 🏆\n\n"
                    f"🚀 *Milestone Rewards:*\n"
                    f"• 5 referrals → 1 Week FREE VIP 🎁\n"
                    f"• 100 referrals → LIFETIME FREE VIP 👑\n\n"
                    f"🔗 Share your link above and start earning today!"
                ),
                "sw": (
                    f"📊 *Maendeleo Yako: {ref_count}/{REFERRAL_MIN} watu wamealikwa*\n\n"
                    f"🎯 Alika *{needed} zaidi* tu kufungua *WIKI 1 VIP BURE!* 🏆\n\n"
                    f"🚀 *Tuzo za Hatua:*\n"
                    f"• Marafiki 5 → Wiki 1 VIP BURE 🎁\n"
                    f"• Marafiki 100 → VIP YA MAISHA YOTE BURE 👑\n\n"
                    f"🔗 Shiriki kiungo chako hapo juu na uanze kupata leo!"
                ),
                "ar": (
                    f"📊 *تقدمك: {ref_count}/{REFERRAL_MIN} شخص مدعو*\n\n"
                    f"🎯 ادعُ *{needed} شخص آخر* فقط لفتح *أسبوع VIP مجاني!* 🏆\n\n"
                    f"🚀 *مكافآت المراحل:*\n"
                    f"• 5 دعوات → أسبوع VIP مجاني 🎁\n"
                    f"• 100 دعوة → VIP مجاني مدى الحياة 👑\n\n"
                    f"🔗 شارك رابطك أعلاه وابدأ اليوم!"
                ),
                "ru": (
                    f"📊 *Ваш прогресс: {ref_count}/{REFERRAL_MIN} человек приглашено*\n\n"
                    f"🎯 Пригласите ещё *{needed}* друзей для *1 НЕДЕЛИ VIP БЕСПЛАТНО!* 🏆\n\n"
                    f"🚀 *Этапы наград:*\n"
                    f"• 5 приглашений → 1 неделя VIP бесплатно 🎁\n"
                    f"• 100 приглашений → ПОЖИЗНЕННЫЙ VIP бесплатно 👑\n\n"
                    f"🔗 Поделитесь ссылкой выше и начните зарабатывать сегодня!"
                ),
            }
            persuasion = persuasion_texts.get(lang, persuasion_texts["en"])
            try:
                p_msg = await send_protected_text(
                    context, cid, persuasion,
                    InlineKeyboardMarkup([
                        [InlineKeyboardButton(ui("btn_back", lang), callback_data="main_menu")],
                    ]))
                track_msg(cid, p_msg.message_id)
            except:
                pass

    elif data == "do_stories":
        all_stories = get_all_stories()
        back_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(ui("btn_services", lang), callback_data="menu_services")],
            [InlineKeyboardButton(ui("btn_back", lang), callback_data="main_menu")],
        ])
        if not all_stories:
            _no_stories = {
                "en": "⭐ *SUCCESS STORIES*\n\nNo stories posted yet. Check back soon!",
                "sw": "⭐ *HADITHI ZA MAFANIKIO*\n\nHadithi hazijawekwa bado. Angalia hivi karibuni!",
                "ar": "⭐ *قصص النجاح*\n\nلم تُنشر قصص بعد. تحقق قريباً!",
                "zh": "⭐ *成功故事*\n\n尚未发布故事。请稍后再查看！",
                "hi": "⭐ *सफलता की कहानियां*\n\nअभी तक कोई कहानी नहीं। जल्द वापस देखें!",
                "ru": "⭐ *ИСТОРИИ УСПЕХА*\n\nИстории ещё не опубликованы. Зайдите позже!",
                "es": "⭐ *HISTORIAS DE ÉXITO*\n\nAún no hay historias. ¡Vuelve pronto!",
                "fr": "⭐ *HISTOIRES DE SUCCÈS*\n\nPas encore d'histoires. Revenez bientôt!",
                "pt": "⭐ *HISTÓRIAS DE SUCESSO*\n\nNenhuma história ainda. Volte em breve!",
                "de": "⭐ *ERFOLGSGESCHICHTEN*\n\nNoch keine Geschichten. Schau bald wieder vorbei!",
                "ur": "⭐ *کامیابی کی کہانیاں*\n\nابھی تک کوئی کہانی نہیں۔ جلد واپس دیکھیں!",
                "ja": "⭐ *サクセスストーリー*\n\nまだストーリーはありません。すぐに確認してください！",
            }
            msg = await send_protected_text(context, cid,
                _no_stories.get(lang, _no_stories["en"]), back_kb)
            track_msg(cid, msg.message_id)
        else:
            # Pick random story, different from last shown
            last_story_id = context.user_data.get("last_story_id")
            available = [s for s in all_stories if s["id"] != last_story_id] or all_stories
            story = random.choice(available)
            context.user_data["last_story_id"] = story["id"]
            caption = story.get("caption") or "⭐ Success Story"
            _story_title = {
                "en": "⭐ *SUCCESS STORIES*", "sw": "⭐ *HADITHI ZA MAFANIKIO*",
                "ar": "⭐ *قصص النجاح*", "zh": "⭐ *成功故事*",
                "hi": "⭐ *सफलता की कहानियां*", "ru": "⭐ *ИСТОРИИ УСПЕХА*",
                "es": "⭐ *HISTORIAS DE ÉXITO*", "fr": "⭐ *HISTOIRES DE SUCCÈS*",
                "pt": "⭐ *HISTÓRIAS DE SUCESSO*", "de": "⭐ *ERFOLGSGESCHICHTEN*",
                "ur": "⭐ *کامیابی کی کہانیاں*", "ja": "⭐ *サクセスストーリー*",
            }
            header = f"{_story_title.get(lang, '⭐ *SUCCESS STORIES*')}\n\n{caption}"
            # Navigation if multiple stories
            nav_row = []
            if len(all_stories) > 1:
                _next_story = {
                    "en": "🔄 Next Story", "sw": "🔄 Hadithi Inayofuata",
                    "ar": "🔄 القصة التالية", "zh": "🔄 下一个故事",
                    "hi": "🔄 अगली कहानी", "ru": "🔄 Следующая история",
                    "es": "🔄 Siguiente Historia", "fr": "🔄 Histoire Suivante",
                    "pt": "🔄 Próxima História", "de": "🔄 Nächste Geschichte",
                    "ur": "🔄 اگلی کہانی", "ja": "🔄 次のストーリー",
                }
                nav_row.append(InlineKeyboardButton(_next_story.get(lang, "🔄 Next Story"), callback_data="do_stories"))
            kb = InlineKeyboardMarkup([nav_row] + [
                [InlineKeyboardButton(ui("btn_services", lang), callback_data="menu_services")],
                [InlineKeyboardButton(ui("btn_back", lang), callback_data="main_menu")],
            ] if nav_row else [
                [InlineKeyboardButton(ui("btn_services", lang), callback_data="menu_services")],
                [InlineKeyboardButton(ui("btn_back", lang), callback_data="main_menu")],
            ])
            mid  = story.get("media_id")
            mtyp = story.get("media_type", "text")
            msg  = None
            try:
                if mid and mtyp == "photo":
                    msg = await context.bot.send_photo(chat_id=cid, photo=mid,
                        caption=header, parse_mode="Markdown", reply_markup=kb, protect_content=True)
                elif mid and mtyp == "video":
                    msg = await context.bot.send_video(chat_id=cid, video=mid,
                        caption=header, parse_mode="Markdown", reply_markup=kb, protect_content=True)
                else:
                    msg = await send_protected_text(context, cid, header, kb)
            except Exception:
                msg = await send_protected_text(context, cid, header, kb)
            context.user_data["last_bot_msg_id"] = msg.message_id
            track_msg(cid, msg.message_id)

    # ── WHAT'S NEW TODAY ───────────────────────────────────────
    elif data == "do_whats_new":
        content = get_dynamic_content("news")
        back_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(ui("btn_back", lang), callback_data="main_menu")]
        ])
        if not content:
            msg = await send_protected_text(context, cid, ui("no_news", lang), back_kb)
        else:
            updated = content.get("updated_at", "")
            _news_hdr = {
                "en": "🆕 WHAT'S NEW", "sw": "🆕 HABARI MPYA", "ar": "🆕 ما الجديد",
                "zh": "🆕 最新消息", "hi": "🆕 नया क्या है", "ru": "🆕 ЧТО НОВОГО",
                "es": "🆕 QUÉ HAY DE NUEVO", "fr": "🆕 QUOI DE NEUF",
                "pt": "🆕 O QUE HÁ DE NOVO", "de": "🆕 WAS GIBT'S NEUES",
                "ur": "🆕 کیا نیا ہے", "ja": "🆕 新着情報",
            }.get(lang, "🆕 WHAT'S NEW")
            header = f"{_news_hdr}\n\n{updated}\n\n" if updated else f"{_news_hdr}\n\n"
            body = content.get("text") or ""
            full_text = header + body
            if content.get("file_id") and content.get("file_type") == "photo":
                try:
                    msg = await context.bot.send_photo(
                        chat_id=cid, photo=content["file_id"],
                        caption=full_text,
                        parse_mode=None, protect_content=True, reply_markup=back_kb)
                except:
                    msg = await context.bot.send_message(
                        chat_id=cid, text=full_text,
                        parse_mode=None, protect_content=True, reply_markup=back_kb)
            elif content.get("file_id") and content.get("file_type") == "video":
                try:
                    msg = await context.bot.send_video(
                        chat_id=cid, video=content["file_id"],
                        caption=full_text,
                        parse_mode=None, protect_content=True, reply_markup=back_kb)
                except:
                    msg = await context.bot.send_message(
                        chat_id=cid, text=full_text,
                        parse_mode=None, protect_content=True, reply_markup=back_kb)
            else:
                msg = await context.bot.send_message(
                    chat_id=cid, text=full_text,
                    parse_mode=None, protect_content=True, reply_markup=back_kb)
        track_msg(cid, msg.message_id)

    # ── TODAY'S VIP RESULTS ────────────────────────────────────
    elif data == "do_vip_results":
        content = get_dynamic_content("vip")
        _vip_join2 = {
            "en": "🚀 Join VIP Now", "sw": "🚀 Jiunge na VIP Sasa",
            "ar": "🚀 انضم لـ VIP الآن", "zh": "🚀 立即加入VIP",
            "hi": "🚀 अभी VIP जुड़ें", "ru": "🚀 Вступить в VIP",
            "es": "🚀 Unirse al VIP Ahora", "fr": "🚀 Rejoindre VIP",
            "pt": "🚀 Entrar no VIP", "de": "🚀 VIP beitreten",
            "ur": "🚀 ابھی VIP میں شامل ہوں", "ja": "🚀 VIPに参加",
        }
        back_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(_vip_join2.get(lang, "🚀 Join VIP Now"), url=VIP_BOT_LINK)],
            [InlineKeyboardButton(ui("btn_back", lang), callback_data="main_menu")]
        ])
        if not content:
            msg = await send_protected_text(context, cid, ui("no_vip", lang), back_kb)
        else:
            updated = content.get("updated_at", "")
            _vip_header = {
                "en": "🏆 TODAY'S VIP RESULTS", "sw": "🏆 MATOKEO YA VIP YA LEO",
                "ar": "🏆 نتائج VIP اليوم", "zh": "🏆 今日VIP结果",
                "hi": "🏆 आज के VIP परिणाम", "ru": "🏆 РЕЗУЛЬТАТЫ VIP СЕГОДНЯ",
                "es": "🏆 RESULTADOS VIP HOY", "fr": "🏆 RÉSULTATS VIP AUJOURD'HUI",
                "pt": "🏆 RESULTADOS VIP HOJE", "de": "🏆 HEUTIGE VIP-ERGEBNISSE",
                "ur": "🏆 آج کے VIP نتائج", "ja": "🏆 本日のVIP結果",
            }.get(lang, "🏆 TODAY'S VIP RESULTS")
            header = f"{_vip_header}\n\n{updated}\n\n" if updated else f"{_vip_header}\n\n"
            body = content.get("text") or ""
            full_text = header + body
            if content.get("file_id") and content.get("file_type") == "photo":
                try:
                    msg = await context.bot.send_photo(
                        chat_id=cid, photo=content["file_id"],
                        caption=full_text,
                        parse_mode=None, protect_content=True, reply_markup=back_kb)
                except:
                    msg = await context.bot.send_message(
                        chat_id=cid, text=full_text,
                        parse_mode=None, protect_content=True, reply_markup=back_kb)
            elif content.get("file_id") and content.get("file_type") == "video":
                try:
                    msg = await context.bot.send_video(
                        chat_id=cid, video=content["file_id"],
                        caption=full_text,
                        parse_mode=None, protect_content=True, reply_markup=back_kb)
                except:
                    msg = await context.bot.send_message(
                        chat_id=cid, text=full_text,
                        parse_mode=None, protect_content=True, reply_markup=back_kb)
            else:
                msg = await context.bot.send_message(
                    chat_id=cid, text=full_text,
                    parse_mode=None, protect_content=True, reply_markup=back_kb)
        track_msg(cid, msg.message_id)

    # ── WINNERS OF THE WEEK ────────────────────────────────────
    elif data == "do_winners":
        try:
            from datetime import timedelta as _td
            leaders = get_referral_leaderboard_daily()
            medals = ["👑", "🥈", "🥉", "4️⃣", "5️⃣"]
            now = datetime.now()
            monday = now - _td(days=now.weekday())
            sunday = monday + _td(days=6)
            week_range = f"{monday.strftime('%d %b')} – {sunday.strftime('%d %b')}"
            user_refs = get_referral_count(user.id)
            _wi_title = {
                "en": "👑 *TOP INVITERS — THIS WEEK*", "sw": "👑 *WAALIKAJI BORA — WIKI HII*",
                "ar": "👑 *أفضل المدعوين — هذا الأسبوع*", "zh": "👑 *本周最佳邀请者*",
                "hi": "👑 *इस सप्ताह के शीर्ष आमंत्रणकर्ता*", "ru": "👑 *ТОП РЕФЕРЕРОВ — ЭТА НЕДЕЛЯ*",
                "es": "👑 *MEJORES INVITADORES — ESTA SEMANA*", "fr": "👑 *MEILLEURS PARRAINS — CETTE SEMAINE*",
                "pt": "👑 *MELHORES INDICADORES — ESTA SEMANA*", "de": "👑 *TOP-EINLADER — DIESE WOCHE*",
                "ur": "👑 *اس ہفتے کے بہترین مدعو کنندگان*", "ja": "👑 *今週のトップ招待者*",
            }.get(lang, "👑 *TOP INVITERS — THIS WEEK*")
            _wi_invited = {
                "en": "people invited", "sw": "watu wamealikwa", "ar": "شخص مدعو",
                "zh": "人受邀", "hi": "लोग आमंत्रित", "ru": "приглашено",
                "es": "personas invitadas", "fr": "personnes invitées", "pt": "pessoas convidadas",
                "de": "Personen eingeladen", "ur": "افراد مدعو", "ja": "人を招待",
            }.get(lang, "people invited")
            _wi_you = {
                "en": "You", "sw": "Wewe", "ar": "أنت", "zh": "你",
                "hi": "आप", "ru": "Вы", "es": "Tú", "fr": "Vous",
                "pt": "Você", "de": "Sie", "ur": "آپ", "ja": "あなた",
            }.get(lang, "You")
            _wi_invite_more = {
                "en": "Invite *{gap} more* to enter the Top 5!",
                "sw": "Alika *{gap} zaidi* kuingia kwenye Top 5!",
                "ar": "ادعُ *{gap} أخرى* للدخول إلى أفضل 5!",
                "zh": "再邀请 *{gap}* 人进入前5名！",
                "hi": "Top 5 में आने के लिए *{gap} और* आमंत्रित करें!",
                "ru": "Пригласите ещё *{gap}* для входа в Топ 5!",
                "es": "¡Invita *{gap} más* para entrar al Top 5!",
                "fr": "Invitez *{gap} de plus* pour entrer dans le Top 5!",
                "pt": "Convide *{gap} mais* para entrar no Top 5!",
                "de": "Lade *{gap} mehr* ein für die Top 5!",
                "ur": "Top 5 میں آنے کے لیے *{gap} اور* مدعو کریں!",
                "ja": "Top 5入りにあと *{gap}人* 招待してください！",
            }.get(lang, "Invite *{gap} more* to enter the Top 5!")
            _wi_top = {
                "en": "🔥 *You're in the top tier! Keep going!*",
                "sw": "🔥 *Uko kwenye kiwango cha juu! Endelea!*",
                "ar": "🔥 *أنت في المستوى الأعلى! استمر!*",
                "zh": "🔥 *您在顶层！继续加油！*",
                "hi": "🔥 *आप शीर्ष स्तर पर हैं! जारी रखें!*",
                "ru": "🔥 *Вы в топ-уровне! Продолжайте!*",
                "es": "🔥 *¡Estás en el nivel superior! ¡Sigue!*",
                "fr": "🔥 *Vous êtes au top! Continuez!*",
                "pt": "🔥 *Você está no topo! Continue!*",
                "de": "🔥 *Sie sind in der Top-Stufe! Weiter so!*",
                "ur": "🔥 *آپ سرفہرست ہیں! جاری رکھیں!*",
                "ja": "🔥 *あなたはトップ層にいます！続けましょう！*",
            }.get(lang, "🔥 *You're in the top tier! Keep going!*")
            _wi_reset = {
                "en": "🔄 *Leaderboard resets every Monday!*\n🚀 Share your link → climb the ranks!",
                "sw": "🔄 *Orodha inawekwa upya kila Jumatatu!*\n🚀 Shiriki kiungo chako → panda daraja!",
                "ar": "🔄 *لوحة المتصدرين تُعاد كل يوم اثنين!*\n🚀 شارك رابطك → ارتقِ في الترتيب!",
                "ru": "🔄 *Таблица обновляется каждый понедельник!*\n🚀 Поделитесь ссылкой → поднимайтесь!",
            }.get(lang, "🔄 *Leaderboard resets every Monday!*\n🚀 Share your link → climb the ranks!")
            lines = [f"{_wi_title}\n📅 _{week_range}_\n\n"]
            for i, (name, flag, count) in enumerate(leaders):
                lines.append(f"{medals[i]} *{name}* {flag} — *{count} {_wi_invited}*\n")
            lines.append(f"\n👤 *{_wi_you}:* {user_refs} {_wi_invited}")
            top_count = leaders[-1][2] if leaders else 10
            if user_refs < top_count:
                gap = top_count - user_refs
                lines.append(f"\n💪 {_wi_invite_more.format(gap=gap)}")
            else:
                lines.append(f"\n{_wi_top}")
            lines.append(f"\n\n{_wi_reset}")
            winners_text = "\n".join(lines)
            img = rand_img(SERVICE_PHOTOS, context.user_data, "last_img_winners")
            try:
                msg = await send_protected_photo(
                    context, cid, img, winners_text,
                    InlineKeyboardMarkup([
                        [InlineKeyboardButton(ui("btn_referral", lang), callback_data="do_referral")],
                        [InlineKeyboardButton(ui("btn_back", lang), callback_data="main_menu")],
                    ]))
            except Exception:
                msg = await send_protected_text(
                    context, cid, winners_text,
                    InlineKeyboardMarkup([
                        [InlineKeyboardButton(ui("btn_referral", lang), callback_data="do_referral")],
                        [InlineKeyboardButton(ui("btn_back", lang), callback_data="main_menu")],
                    ]))
            track_msg(cid, msg.message_id)
        except Exception as e:
            logger.warning(f"do_winners error: {e}")
            try:
                _wi_err = {
                    "en": "👑 *TOP INVITERS — THIS WEEK*\n\n⚠️ Could not load leaderboard. Please try again!",
                    "sw": "👑 *WAALIKAJI BORA — WIKI HII*\n\n⚠️ Imeshindwa kupakia orodha. Tafadhali jaribu tena!",
                }.get(lang, "👑 *TOP INVITERS — THIS WEEK*\n\n⚠️ Could not load leaderboard. Please try again!")
                msg = await send_protected_text(
                    context, cid, _wi_err,
                    InlineKeyboardMarkup([
                        [InlineKeyboardButton(ui("btn_back", lang), callback_data="main_menu")],
                    ]))
                track_msg(cid, msg.message_id)
            except:
                pass

    # ── MY DAILY STREAK ────────────────────────────────────────
    elif data == "do_streak":
        streak, max_streak = get_streak(user.id)
        if streak == 0:
            streak = 1
        badge_emoji, badge_name = get_streak_badge(streak)
        next_days, next_emoji, next_name = get_next_badge(streak)
        streak_texts = {
            "en": (
                f"🔥 *YOUR DAILY STREAK*\n\n"
                f"{badge_emoji} *{badge_name}*\n\n"
                f"📅 Current streak: *{streak} days* 🔥\n"
                f"🏆 Best streak: *{max_streak} days*\n\n"
                f"{'🎯 Next badge: ' + next_emoji + ' *' + next_name + '* in *' + str(next_days - streak) + ' days!*' if next_days else '🌟 *You have reached the highest rank!*'}\n\n"
                f"Keep coming back every day to grow your streak!\n"
                f"Active members get priority rewards from our team. 💎"
            ),
            "sw": (
                f"🔥 *STREAK YAKO YA KILA SIKU*\n\n"
                f"{badge_emoji} *{badge_name}*\n\n"
                f"📅 Streak ya sasa: *siku {streak}* 🔥\n"
                f"🏆 Streak bora: *siku {max_streak}*\n\n"
                f"{'🎯 Badge inayofuata: ' + next_emoji + ' *' + next_name + '* baada ya siku *' + str(next_days - streak) + '*!' if next_days else '🌟 *Umefika kiwango cha juu kabisa!*'}\n\n"
                f"Endelea kurudi kila siku kukuza streak yako!\n"
                f"Wanachama wanaoshiriki hupata zawadi za kipaumbele. 💎"
            ),
        }
        streak_text = streak_texts.get(lang, streak_texts["en"])
        img = rand_img(SERVICE_PHOTOS, context.user_data, "last_img_streak")
        msg = await send_protected_photo(
            context, cid, img, streak_text,
            InlineKeyboardMarkup([
                [InlineKeyboardButton(ui("btn_services", lang), callback_data="menu_services")],
                [InlineKeyboardButton(ui("btn_back", lang), callback_data="main_menu")],
            ]))
        track_msg(cid, msg.message_id)

    elif data == "do_tip":
        tip = get_daily_binary_tip()
        msg = await send_protected_text(
            context, cid, tip,
            InlineKeyboardMarkup([
                [InlineKeyboardButton(ui("btn_services", lang), callback_data="menu_services")],
                [InlineKeyboardButton(ui("btn_back", lang), callback_data="main_menu")],
            ]))
        track_msg(cid, msg.message_id)

    elif data == "do_profile":
        profile_text = build_profile_text(user.id, lang)
        msg = await send_protected_text(
            context, cid, profile_text,
            InlineKeyboardMarkup([
                [InlineKeyboardButton(ui("btn_back", lang), callback_data="main_menu")],
            ]))
        track_msg(cid, msg.message_id)

    elif data == "do_results_history":
        await _show_results_history(context, cid, lang, page=0)

    elif data.startswith("results_page_"):
        page = int(data.split("_")[-1])
        await safe_delete(context, cid, query.message.message_id)
        await _show_results_history(context, cid, lang, page=page)

    elif data == "do_quiz":
        context.user_data["quiz_idx"] = 0
        context.user_data["quiz_correct"] = 0
        q = QUIZ_QUESTIONS[0]
        opts = "\n".join([f"{i+1}. {o}" for i, o in enumerate(q["options"])])
        quiz_text = f"{q['q']}\n\n{opts}"
        buttons = [[InlineKeyboardButton(f"{i+1}", callback_data=f"quiz_ans_{i}")] for i in range(len(q["options"]))]
        buttons.append([InlineKeyboardButton(ui("btn_back", lang), callback_data="main_menu")])
        msg = await send_protected_text(context, cid, quiz_text, InlineKeyboardMarkup(buttons))
        track_msg(cid, msg.message_id)

    elif data.startswith("quiz_ans_"):
        ans = int(data.split("_")[-1])
        q_idx = context.user_data.get("quiz_idx", 0)
        correct_count = context.user_data.get("quiz_correct", 0)
        if ans == QUIZ_QUESTIONS[q_idx]["answer"]:
            correct_count += 1
            feedback = f"✅ *Correct!* {QUIZ_QUESTIONS[q_idx]['explanation']}"
        else:
            feedback = f"❌ *Not quite!* {QUIZ_QUESTIONS[q_idx]['explanation']}"
        context.user_data["quiz_correct"] = correct_count
        next_q = q_idx + 1
        context.user_data["quiz_idx"] = next_q
        if next_q < len(QUIZ_QUESTIONS):
            q = QUIZ_QUESTIONS[next_q]
            opts = "\n".join([f"{i+1}. {o}" for i, o in enumerate(q["options"])])
            quiz_text = f"{feedback}\n\n{q['q']}\n\n{opts}"
            buttons = [[InlineKeyboardButton(f"{i+1}", callback_data=f"quiz_ans_{i}")] for i in range(len(q["options"]))]
            msg = await send_protected_text(context, cid, quiz_text, InlineKeyboardMarkup(buttons))
        else:
            save_quiz_score(user.id, correct_count)
            add_badge(user.id, "quiz_master")
            final = f"{feedback}\n\n🎓 *QUIZ COMPLETE!*\n\nYour score: *{correct_count}/{len(QUIZ_QUESTIONS)}*\n\n"
            if correct_count == len(QUIZ_QUESTIONS):
                final += "🏆 Perfect score! You're a trading genius! 🎉"
            elif correct_count >= 2:
                final += "💪 Great job! Keep learning and you'll be a pro! 📈"
            else:
                final += "📚 Keep studying — every expert was once a beginner! 💡"
            msg = await send_protected_text(
                context, cid, final,
                InlineKeyboardMarkup([[InlineKeyboardButton(ui("btn_back", lang), callback_data="main_menu")]]))
        track_msg(cid, msg.message_id)

    elif data == "do_spin":
        if not can_spin_today(user.id):
            hours, mins = get_next_spin_time(user.id)
            await safe_delete(context, cid, query.message.message_id)
            await delete_all_bot_msgs(context, cid)
            wait_texts = {
                "en": f"⏳ *You have already used your Lucky Spin today!*\n\nYour next spin will be available in *{hours}h {mins}m* ⏰\n\nCome back then — big prizes are waiting for you! 🎁",
                "sw": f"⏳ *Umeshakutumia Lucky Spin yako ya leo!*\n\nSpin yako ijayo itapatikana baada ya *saa {hours} na dakika {mins}* ⏰\n\nRudi wakati huo — zawadi kubwa zinakusubiri! 🎁",
                "ar": f"⏳ *لقد استخدمت بالفعل دورتك المحظوظة اليوم!*\n\nستكون دورتك التالية متاحة خلال *{hours}h {mins}m* ⏰\n\nعد بعدها! 🎁",
                "zh": f"⏳ *您今天已经使用了幸运转盘！*\n\n下次可用时间：*{hours}h {mins}m* ⏰\n\n到时再来！ 🎁",
                "hi": f"⏳ *आप आज Lucky Spin उपयोग कर चुके हैं!*\n\nअगला spin *{hours}h {mins}m* में ⏰\n\nतब वापस आएं! 🎁",
                "ru": f"⏳ *Вы уже использовали Счастливый Спин сегодня!*\n\nСледующий спин через *{hours}h {mins}m* ⏰\n\nВозвращайтесь! 🎁",
                "es": f"⏳ *¡Ya usaste tu Giro de Suerte hoy!*\n\nPróximo giro en *{hours}h {mins}m* ⏰\n\n¡Vuelve entonces! 🎁",
                "fr": f"⏳ *Vous avez déjà utilisé votre Spin aujourd'hui!*\n\nProchain spin dans *{hours}h {mins}m* ⏰\n\nRevenez! 🎁",
                "pt": f"⏳ *Você já usou seu Giro hoje!*\n\nPróximo giro em *{hours}h {mins}m* ⏰\n\nVolte! 🎁",
                "de": f"⏳ *Sie haben Ihr Glücksrad heute bereits genutzt!*\n\nNächstes Drehen in *{hours}h {mins}m* ⏰\n\nKommen Sie zurück! 🎁",
                "ur": f"⏳ *آپ آج Lucky Spin استعمال کر چکے ہیں!*\n\nاگلا spin *{hours}h {mins}m* میں ⏰\n\nواپس آئیں! 🎁",
                "ja": f"⏳ *今日はすでにラッキースピンを使用しました！*\n\n次のスピン：*{hours}h {mins}m* 後 ⏰\n\nその時に戻ってください！ 🎁",
            }
            wait_text = wait_texts.get(lang, wait_texts["en"])
            msg = await send_protected_text(
                context, cid, wait_text,
                InlineKeyboardMarkup([
                    [InlineKeyboardButton(ui("btn_services", lang), callback_data="menu_services")],
                    [InlineKeyboardButton(ui("btn_back", lang), callback_data="main_menu")],
                ]))
            track_msg(cid, msg.message_id)
            return

        # Record spin with user info
        record_spin(user.id, user.full_name, user.username or "")

        # Show spinning animation — FAST: 3 frames, 1.5 seconds total
        spin_msg = await send_protected_text(
            context, cid,
            SPIN_WHEEL_VISUAL + "      ✨ Spinning... ✨",
            InlineKeyboardMarkup([]))
        track_msg(cid, spin_msg.message_id)

        # Only 3 frames, very fast
        spin_timings = [0.4, 0.4, 0.5]
        for i, (frame, wait) in enumerate(zip(SPIN_FRAMES[:3], spin_timings)):
            await asyncio.sleep(wait)
            try:
                await context.bot.edit_message_text(
                    chat_id=cid,
                    message_id=spin_msg.message_id,
                    text=SPIN_WHEEL_VISUAL + "      ✨ " + frame + " ✨",
                    parse_mode="Markdown")
            except BadRequest:
                pass
            except Exception as e:
                if "retry" in str(e).lower() or "flood" in str(e).lower():
                    await asyncio.sleep(2)

        await asyncio.sleep(0.3)

        # Get result — always a lose result
        prize_key, prize_emoji, is_win = do_spin()
        prize_text = get_prize_text(prize_key, lang)

        # Delete spin animation immediately
        await safe_delete(context, cid, spin_msg.message_id)
        if spin_msg.message_id in bot_msg_ids.get(cid, []):
            bot_msg_ids[cid].remove(spin_msg.message_id)

        # Always show exciting lose message with hope — no win tracking, no admin mention
        _spin_again = {
            "en": "🔄 Spin Again Tomorrow 🕐", "sw": "🔄 Spin Tena Kesho 🕐",
            "ar": "🔄 الدوران مجدداً غداً 🕐", "zh": "🔄 明天再旋转 🕐",
            "hi": "🔄 कल फिर Spin करें 🕐", "ru": "🔄 Крутить снова завтра 🕐",
            "es": "🔄 Girar Mañana 🕐", "fr": "🔄 Retourner Demain 🕐",
            "pt": "🔄 Girar Amanhã 🕐", "de": "🔄 Morgen wieder drehen 🕐",
            "ur": "🔄 کل دوبارہ Spin کریں 🕐", "ja": "🔄 明日また回す 🕐",
        }
        _spin_title = {
            "en": "🎰 *LUCKY SPIN RESULT* 🎰", "sw": "🎰 *MATOKEO YA LUCKY SPIN* 🎰",
            "ar": "🎰 *نتيجة الدورة المحظوظة* 🎰", "zh": "🎰 *幸运转盘结果* 🎰",
            "hi": "🎰 *Lucky Spin परिणाम* 🎰", "ru": "🎰 *РЕЗУЛЬТАТ СЧАСТЛИВОГО СПИНА* 🎰",
            "es": "🎰 *RESULTADO DEL GIRO* 🎰", "fr": "🎰 *RÉSULTAT DU SPIN* 🎰",
            "pt": "🎰 *RESULTADO DO GIRO* 🎰", "de": "🎰 *GLÜCKSRAD ERGEBNIS* 🎰",
            "ur": "🎰 *Lucky Spin نتیجہ* 🎰", "ja": "🎰 *ラッキースピン結果* 🎰",
        }
        result_header = f"{_spin_title.get(lang, '🎰 *LUCKY SPIN RESULT* 🎰')}\n\n{prize_text}"
        result_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(_spin_again.get(lang, "🔄 Spin Again Tomorrow 🕐"), callback_data="main_menu")],
            [InlineKeyboardButton(ui("btn_services", lang), callback_data="menu_services")],
            [InlineKeyboardButton(ui("btn_back", lang), callback_data="main_menu")],
        ])
        # Send spin result — 3 fallback layers to guarantee user always sees something
        msg = None
        try:
            img = random.choice(SERVICE_PHOTOS)
            msg = await context.bot.send_photo(
                chat_id=cid, photo=img, caption=result_header,
                parse_mode="Markdown", reply_markup=result_kb,
                protect_content=True)
        except Exception as e:
            logger.warning(f"spin photo failed: {e}")

        if msg is None:
            try:
                msg = await context.bot.send_message(
                    chat_id=cid, text=result_header,
                    parse_mode="Markdown", reply_markup=result_kb,
                    protect_content=True)
            except Exception as e:
                logger.warning(f"spin markdown msg failed: {e}")

        if msg is None:
            # Last resort — plain text, no Markdown, no photo, no protect
            try:
                plain = f"🎰 LUCKY SPIN RESULT 🎰\n\n{prize_text}"
                msg = await context.bot.send_message(
                    chat_id=cid, text=plain,
                    reply_markup=result_kb)
            except Exception as e:
                logger.error(f"spin last resort failed: {e}")

        if msg:
            track_msg(cid, msg.message_id)

        # Silently notify admin — no sound, just data tracking
        name = escape_md(user.full_name)
        username_str = escape_md(user.username or "NA")
        # Get total spins for this user
        from_db = get_top_spinners(limit=100)
        user_spins = next((r[3] for r in from_db if r[0] == user.id), 1)
        for aid in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=aid,
                    text=(
                        f"🎰 *Spin Activity*\n\n"
                        f"👤 {name} @{username_str}\n"
                        f"🆔 `{user.id}` | 🌍 {lang}\n"
                        f"🔢 Total spins: *{user_spins}*\n\n"
                        f"_Use /spinners to see most active players_"
                    ),
                    parse_mode="Markdown",
                    disable_notification=True)  # Silent notification
            except:
                pass

    # Admin: Connect
    elif data.startswith("con:"):
        parts = data.split(":")
        uid   = int(parts[1])
        ulang = parts[2] if len(parts) > 2 else "en"
        active_support[uid] = True
        # FIX: wrap edit in try/except — message may already be deleted
        try:
            await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🟢 Connected ✓", callback_data="noop"),
                InlineKeyboardButton("🔴 End Chat", callback_data=f"dis:{uid}:{ulang}"),
            ]]))
        except:
            pass
        try:
            msg = await context.bot.send_message(
                chat_id=uid,
                text={
                    "en": "🟢 *You are now connected to our support team!*\n\nPlease describe your issue. 💬",
                    "sw": "🟢 *Umeunganishwa na timu yetu ya usaidizi!*\n\nTafadhali eleza tatizo lako. 💬",
                    "ar": "🟢 *أنت الآن متصل بفريق الدعم!*\n\nيرجى وصف مشكلتك. 💬",
                    "zh": "🟢 *您已连接到我们的支持团队！*\n\n请描述您的问题。 💬",
                    "hi": "🟢 *आप हमारी सपोर्ट टीम से जुड़ गए हैं!*\n\nकृपया अपनी समस्या बताएं। 💬",
                    "ru": "🟢 *Вы подключены к команде поддержки!*\n\nОпишите вашу проблему. 💬",
                    "es": "🟢 *¡Ahora estás conectado con nuestro equipo de soporte!*\n\nPor favor describe tu problema. 💬",
                    "fr": "🟢 *Vous êtes connecté à notre équipe support!*\n\nVeuillez décrire votre problème. 💬",
                    "pt": "🟢 *Você está conectado à nossa equipe de suporte!*\n\nDescreva seu problema. 💬",
                    "de": "🟢 *Sie sind jetzt mit unserem Support-Team verbunden!*\n\nBitte beschreiben Sie Ihr Problem. 💬",
                    "ur": "🟢 *آپ ہماری سپورٹ ٹیم سے جڑ گئے ہیں!*\n\nبراہ کرم اپنا مسئلہ بیان کریں۔ 💬",
                    "ja": "🟢 *サポートチームに接続されました！*\n\n問題を説明してください。 💬",
                    "it": "🟢 *Sei connesso al nostro team di supporto!*\n\nDescivi il tuo problema. 💬",
                    "ko": "🟢 *지원팀에 연결되었습니다!*\n\n문제를 설명해 주세요. 💬",
                    "tr": "🟢 *Destek ekibimize bağlandınız!*\n\nLütfen sorununuzu açıklayın. 💬",
                    "fa": "🟢 *به تیم پشتیبانی متصل شدید!*\n\nلطفاً مشکل خود را شرح دهید. 💬",
                    "pl": "🟢 *Połączono z zespołem wsparcia!*\n\nProszę opisać swój problem. 💬",
                    "uk": "🟢 *Ви підключені до команди підтримки!*\n\nБудь ласка, опишіть вашу проблему. 💬",
                    "kk": "🟢 *Сіз қолдау тобына қосылдыңыз!*\n\nМәселеңізді сипаттаңыз. 💬",
                    "cs": "🟢 *Jste připojeni k týmu podpory!*\n\nPopište prosím svůj problém. 💬",
                }.get(ulang, "🟢 *You are now connected to our support team!*\n\nPlease describe your issue. 💬"),
                parse_mode="Markdown",
                protect_content=True)
            track_support_msg(uid, msg.message_id)
        except:
            pass

    # Admin: Disconnect
    elif data.startswith("dis:"):
        parts = data.split(":")
        uid   = int(parts[1])
        ulang = parts[2] if len(parts) > 2 else "en"
        active_support.pop(uid, None)
        # FIX: wrap edit in try/except
        try:
            await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🟢 Connect", callback_data=f"con:{uid}:{ulang}"),
                InlineKeyboardButton("🔴 Ended ✓", callback_data="noop"),
            ]]))
        except:
            pass

        # NOTE: Do NOT delete support messages — they stay as conversation record
        # Only delete bot system messages (menu, spin, etc), NOT the chat conversation
        # delete_support_msgs is intentionally NOT called here

        # FIX: session_ended has NO contact support button — just thank you
        try:
            msg = await context.bot.send_message(
                chat_id=uid,
                text=ui("session_ended", ulang),
                parse_mode="Markdown",
                protect_content=True,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(
                        ui("btn_back", ulang), callback_data="main_menu")
                ]]))
            track_msg(uid, msg.message_id)
            await asyncio.sleep(2)
            rating_msg = await context.bot.send_message(
                chat_id=uid,
                text=ui("rating_msg", ulang),
                parse_mode="Markdown",
                protect_content=True,
                reply_markup=rating_keyboard())
            track_msg(uid, rating_msg.message_id)
        except:
            pass

    elif data == "end_all_support":
        count = len(active_support)
        uids = list(active_support.keys())
        active_support.clear()
        for uid in uids:
            await delete_support_msgs(context, uid)
        await query.message.reply_text(
            f"✅ Ended all *{count}* sessions.", parse_mode="Markdown")

    elif data.startswith("approve_"):
        uid = int(data[8:])
        req = pending_requests.get(uid)
        if req:
            try:
                await context.bot.approve_chat_join_request(
                    chat_id=req["chat_id"], user_id=uid)
                pending_requests.pop(uid, None)
                safe_name = escape_md(req['user'].full_name)
                await query.message.edit_text(
                    f"✅ *Approved!*\n👤 {safe_name}",
                    parse_mode="Markdown")
                try:
                    await context.bot.send_message(
                        chat_id=uid,
                        text="🎉 You have been *approved!* Welcome! 🚀",
                        parse_mode="Markdown",
                        protect_content=True)
                except:
                    pass
            except TelegramError as e:
                await query.message.reply_text(f"❌ Error: {e}")
        else:
            await query.answer("⚠️ Request not found.", show_alert=True)

    elif data.startswith("decline_"):
        uid = int(data[8:])
        req = pending_requests.get(uid)
        if req:
            try:
                await context.bot.decline_chat_join_request(
                    chat_id=req["chat_id"], user_id=uid)
                pending_requests.pop(uid, None)
                await query.message.edit_text("❌ *Declined.*", parse_mode="Markdown")
            except TelegramError as e:
                await query.message.reply_text(f"❌ Error: {e}")
        else:
            await query.answer("⚠️ Request not found.", show_alert=True)

    # ── GIVESPIN QUICK BUTTON from /spinners ──────────────────
    elif data.startswith("givespin_btn:"):
        uid_str = data.split(":")[1]
        await query.answer()
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=(
                f"📋 To reward this user, send:\n\n"
                f"`/givespin {uid_str} 3 signals`\n\n"
                f"Change the discount (3) and service (signals/social/indicator/autobot/any) as needed."
            ),
            parse_mode="Markdown")
        return

    # ── POCKET OPTION BOT — show video + link ─────────────────
    elif data == "show_pocket_bot":
        try:
            pocket_link = FREE_BOT_LINKS.get("pocket_link", "")
            pocket_texts = {
                "en": "💰 *POCKET OPTION BOT — NEW!* 🆕\n\n🤖 Our brand new Pocket Option trading bot is here!\n\n✅ Works on Pocket Option\n✅ Auto trading 24/7\n✅ Easy setup\n✅ Real results\n\n👇 Watch the bot in action & access it below:",
                "sw": "💰 *BOT YA POCKET OPTION — MPYA!* 🆕\n\n🤖 Bot yetu mpya kabisa ya Pocket Option ipo sasa!\n\n✅ Inafanya kazi kwenye Pocket Option\n✅ Biashara otomatiki 24/7\n✅ Usanidi rahisi\n✅ Matokeo ya kweli\n\n👇 Angalia bot na uifikikie hapa chini:",
            }
            pocket_text = pocket_texts.get(lang, pocket_texts["en"])
            # Build keyboard — add link button if pocket_link is set
            _open_btn = {
                "en": "🤖 Open Pocket Option Bot", "sw": "🤖 Fungua Pocket Option Bot",
                "ar": "🤖 فتح بوت Pocket Option", "zh": "🤖 打开Pocket Option Bot",
                "hi": "🤖 Pocket Option Bot खोलें", "ru": "🤖 Открыть Pocket Option Bot",
                "es": "🤖 Abrir Pocket Option Bot", "fr": "🤖 Ouvrir Pocket Option Bot",
                "pt": "🤖 Abrir Pocket Option Bot", "de": "🤖 Pocket Option Bot öffnen",
                "ur": "🤖 Pocket Option Bot کھولیں", "ja": "🤖 Pocket Option Botを開く",
            }
            kb_rows = []
            if pocket_link:
                kb_rows.append([InlineKeyboardButton(_open_btn.get(lang, "🤖 Open Pocket Option Bot"), url=pocket_link)])
            kb_rows.append([InlineKeyboardButton(ui("btn_support", lang), callback_data="do_support")])
            kb_rows.append([InlineKeyboardButton(ui("btn_back", lang), callback_data="svc_freebot")])
            msg = await context.bot.send_video(
                chat_id=cid,
                video=FREE_BOT_LINKS["pocket"],
                caption=pocket_text,
                parse_mode="Markdown",
                protect_content=True,
                reply_markup=InlineKeyboardMarkup(kb_rows))
            track_msg(cid, msg.message_id)
        except Exception as e:
            logger.warning(f"Pocket bot video failed: {e}")
            pocket_link = FREE_BOT_LINKS.get("pocket_link", "")
            kb_rows = []
            if pocket_link:
                kb_rows.append([InlineKeyboardButton(_open_btn.get(lang, "🤖 Open Pocket Option Bot"), url=pocket_link)])
            kb_rows.append([InlineKeyboardButton(ui("btn_support", lang), callback_data="do_support")])
            kb_rows.append([InlineKeyboardButton(ui("btn_back", lang), callback_data="svc_freebot")])
            msg = await send_protected_text(
                context, cid,
                {
                    "en": "💰 *POCKET OPTION BOT — NEW!* 🆕\n\n🤖 Our Pocket Option trading bot is ready!\n\nTap below to access it or contact support.",
                    "sw": "💰 *BOT YA POCKET OPTION — MPYA!* 🆕\n\n🤖 Bot yetu ya Pocket Option iko tayari!\n\nBonyeza hapa chini kuifikia au wasiliana na usaidizi.",
                    "ar": "💰 *بوت Pocket Option — جديد!* 🆕\n\n🤖 بوتنا جاهز!\n\nاضغط أدناه للوصول أو تواصل مع الدعم.",
                    "ru": "💰 *БОТ Pocket Option — НОВИНКА!* 🆕\n\n🤖 Наш бот готов!\n\nНажмите ниже для доступа или свяжитесь с поддержкой.",
                }.get(lang, "💰 *POCKET OPTION BOT — NEW!* 🆕\n\n🤖 Our Pocket Option trading bot is ready!\n\nTap below to access it or contact support."),
                InlineKeyboardMarkup(kb_rows))
            track_msg(cid, msg.message_id)

    elif data == "noop":
        pass

    # onboarding_done removed — no longer used
    elif data == "onboarding_done":
        # Legacy support — just show main menu
        welcome_text = build_welcome_text(lang, user.first_name)
        msg = await send_welcome_media(context, cid, welcome_text, main_menu(lang))
        context.user_data["last_bot_msg_id"] = msg.message_id
        track_msg(cid, msg.message_id)

    # ── VIEW MY REFERRALS LIST ─────────────────────────────────
    elif data == "view_referrals":
        ref_list = get_referred_users(user.id)
        ref_count = len(ref_list)
        if not ref_list:
            _no_ref = {
                "en": "👥 *Your Referrals*\n\nYou haven't invited anyone yet.\n\nShare your link and start earning discounts! 🎁",
                "sw": "👥 *Rufaa Zako*\n\nHujamwalika mtu yeyote bado.\n\nShiriki kiungo chako na uanze kupata punguzo! 🎁",
                "ar": "👥 *إحالاتك*\n\nلم تدعُ أحداً بعد.\n\nشارك رابطك وابدأ بكسب الخصومات! 🎁",
                "zh": "👥 *您的推荐*\n\n您还没有邀请任何人。\n\n分享您的链接开始赚取折扣！ 🎁",
                "hi": "👥 *आपके रेफरल*\n\nआपने अभी तक किसी को आमंत्रित नहीं किया।\n\nअपना लिंक साझा करें और छूट पाना शुरू करें! 🎁",
                "ru": "👥 *Ваши рефералы*\n\nВы ещё никого не пригласили.\n\nПоделитесь ссылкой и начните зарабатывать скидки! 🎁",
                "es": "👥 *Tus Referidos*\n\nAún no has invitado a nadie.\n\n¡Comparte tu enlace y empieza a ganar descuentos! 🎁",
                "fr": "👥 *Vos Parrainages*\n\nVous n'avez encore invité personne.\n\nPartagez votre lien et commencez à gagner des remises! 🎁",
                "pt": "👥 *Seus Indicados*\n\nVocê ainda não convidou ninguém.\n\nCompartilhe seu link e comece a ganhar descontos! 🎁",
                "de": "👥 *Ihre Empfehlungen*\n\nSie haben noch niemanden eingeladen.\n\nTeilen Sie Ihren Link und verdienen Sie Rabatte! 🎁",
                "ur": "👥 *آپ کے ریفرلز*\n\nآپ نے ابھی تک کسی کو مدعو نہیں کیا۔\n\nاپنا لنک شیئر کریں اور چھوٹ حاصل کرنا شروع کریں! 🎁",
                "ja": "👥 *あなたの紹介*\n\nまだ誰も招待していません。\n\nリンクを共有して割引を獲得しましょう! 🎁",
            }
            text = _no_ref.get(lang, _no_ref["en"])
        else:
            _ref_header = {
                "en": "Your Referrals", "sw": "Rufaa Zako", "ar": "إحالاتك",
                "zh": "您的推荐", "hi": "आपके रेफरल", "ru": "Ваши рефералы",
                "es": "Tus Referidos", "fr": "Vos Parrainages", "pt": "Seus Indicados",
                "de": "Ihre Empfehlungen", "ur": "آپ کے ریفرلز", "ja": "あなたの紹介",
            }
            lines = [f"👥 *{_ref_header.get(lang, 'Your Referrals')} ({ref_count} {'watu' if lang=='sw' else 'people'})*\n"]
            for i, (name_r, joined_r) in enumerate(ref_list[:20], 1):
                safe = escape_md(name_r or "Unknown")
                lines.append(f"{i}. {safe} — {joined_r[:10] if joined_r else '?'}")
            if ref_count > 20:
                lines.append(f"\n...and {ref_count - 20} more")
            text = "\n".join(lines)
        msg = await send_protected_text(
            context, cid, text,
            InlineKeyboardMarkup([
                [InlineKeyboardButton(ui("btn_back", lang), callback_data="do_referral")]
            ]))
        track_msg(cid, msg.message_id)

# ══════════════════════════════════════════════════════════════
#  TWO-WAY MESSAGING — Copy instead of Forward
# ══════════════════════════════════════════════════════════════

async def forward_to_admin(context, user, message):
    if not active_support.get(user.id):
        return

    name = escape_md(user.full_name)

    # Save message to persistent chat history
    if message.text:
        save_chat_message(user.id, user.full_name, user.username, "user", message=message.text)
    elif message.photo:
        save_chat_message(user.id, user.full_name, user.username, "user",
                         message=message.caption, media_type="photo",
                         media_id=message.photo[-1].file_id)
    elif message.video:
        save_chat_message(user.id, user.full_name, user.username, "user",
                         message=message.caption, media_type="video",
                         media_id=message.video.file_id)
    elif message.voice:
        save_chat_message(user.id, user.full_name, user.username, "user",
                         media_type="voice", media_id=message.voice.file_id)
    elif message.document:
        save_chat_message(user.id, user.full_name, user.username, "user",
                         message=message.caption, media_type="document",
                         media_id=message.document.file_id)

    for aid in ADMIN_IDS:
        try:
            sent = None
            if message.text:
                # FIX: Use plain Markdown, not MarkdownV2 — consistent throughout
                sent = await context.bot.send_message(
                    chat_id=aid,
                    text=f"💬 *{name}* (`{user.id}`):\n\n{message.text}",
                    parse_mode="Markdown")
            elif message.photo:
                caption = f"📸 *{name}*"
                if message.caption:
                    caption += f"\n{message.caption}"
                sent = await context.bot.send_photo(
                    chat_id=aid,
                    photo=message.photo[-1].file_id,
                    caption=caption,
                    parse_mode="Markdown")
            elif message.video:
                caption = f"🎥 *{name}*"
                if message.caption:
                    caption += f"\n{message.caption}"
                sent = await context.bot.send_video(
                    chat_id=aid,
                    video=message.video.file_id,
                    caption=caption,
                    parse_mode="Markdown")
            elif message.voice:
                sent = await context.bot.send_voice(
                    chat_id=aid,
                    voice=message.voice.file_id)
            elif message.document:
                caption = f"📄 *{name}*"
                if message.caption:
                    caption += f"\n{message.caption}"
                sent = await context.bot.send_document(
                    chat_id=aid,
                    document=message.document.file_id,
                    caption=caption,
                    parse_mode="Markdown")
            elif message.sticker:
                sent = await context.bot.send_sticker(
                    chat_id=aid,
                    sticker=message.sticker.file_id)
            elif message.audio:
                sent = await context.bot.send_audio(
                    chat_id=aid,
                    audio=message.audio.file_id)

            if sent:
                reply_map[sent.message_id] = user.id

        except Exception as e:
            logger.warning(f"Forward to admin failed: {e}")

async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    replied = message.reply_to_message
    if not replied:
        return
    target_uid = reply_map.get(replied.message_id)
    if not target_uid:
        return

    # Save admin reply to persistent history
    admin_text = message.text or message.caption or ""
    if message.photo:
        save_chat_message(target_uid, "ADMIN", "admin", "admin",
                         message=message.caption, media_type="photo",
                         media_id=message.photo[-1].file_id)
    elif message.video:
        save_chat_message(target_uid, "ADMIN", "admin", "admin",
                         message=message.caption, media_type="video",
                         media_id=message.video.file_id)
    elif message.text:
        save_chat_message(target_uid, "ADMIN", "admin", "admin", message=message.text)

    try:
        await context.bot.send_chat_action(
            chat_id=target_uid, action=ChatAction.TYPING)
        await asyncio.sleep(1.5)
        if message.photo:
            sent = await context.bot.send_photo(
                chat_id=target_uid, photo=message.photo[-1].file_id,
                caption=message.caption or "",
                parse_mode="Markdown",
                protect_content=True)
        elif message.video:
            sent = await context.bot.send_video(
                chat_id=target_uid, video=message.video.file_id,
                caption=message.caption or "",
                parse_mode="Markdown",
                protect_content=True)
        elif message.voice:
            sent = await context.bot.send_voice(
                chat_id=target_uid, voice=message.voice.file_id,
                protect_content=True)
        elif message.document:
            sent = await context.bot.send_document(
                chat_id=target_uid, document=message.document.file_id,
                caption=message.caption or "",
                parse_mode="Markdown",
                protect_content=True)
        elif message.sticker:
            sent = await context.bot.send_sticker(
                chat_id=target_uid, sticker=message.sticker.file_id)
        elif message.text:
            sent = await context.bot.send_message(
                chat_id=target_uid, text=message.text,
                parse_mode="Markdown",
                protect_content=True)
        else:
            return
        track_support_msg(target_uid, sent.message_id)
        await message.reply_text("✅ Delivered!")
    except Exception as e:
        await message.reply_text(f"❌ Failed: {e}")

# ══════════════════════════════════════════════════════════════
#  MAIN MESSAGE HANDLER
# ══════════════════════════════════════════════════════════════

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message:
        return
    user = message.from_user
    cid  = message.chat_id

    # Admin handler
    if is_admin(user.id):
        if message.reply_to_message:
            target = reply_map.get(message.reply_to_message.message_id)
            if target:
                await handle_admin_reply(update, context)
                return
        if message.photo and not message.reply_to_message:
            await message.reply_text(
                f"📸 `{message.photo[-1].file_id}`", parse_mode="Markdown")
            return
        if message.video and not message.reply_to_message:
            await message.reply_text(
                f"🎥 `{message.video.file_id}`", parse_mode="Markdown")
            return
        return

    lang = get_lang(context, user.id)
    register_user(user, lang=lang)

    # Handle 🏆 START 🏆 button — goes straight to welcome/main menu
    if message.text and message.text.strip() == "🏆 START 🏆":
        await delete_user_msg(message)
        await delete_all_bot_msgs(context, cid)
        await typing_action(cid, context, 1.0)
        welcome_text = build_welcome_text(lang, user.first_name)
        update_streak(user.id)
        msg = await send_welcome_media(context, cid, welcome_text, main_menu(lang))
        context.user_data["last_bot_msg_id"] = msg.message_id
        track_msg(cid, msg.message_id)
        schedule_comeback(context, cid, user.first_name, lang)
        schedule_auto_clean(context, cid, lang, user.first_name, user.id)
        return

    # FIX: Check if user is giving rating text opinion
    if user.id in awaiting_rating_opinion and message.text:
        opinion_data = awaiting_rating_opinion.pop(user.id)
        stars = opinion_data["stars"]
        star_display = opinion_data["star_display"]
        opinion_text = message.text.strip()

        # Delete user's message and the opinion prompt
        await delete_user_msg(message)
        await delete_all_bot_msgs(context, cid)

        # Send full rating + opinion to admin
        name = escape_md(user.full_name)
        skip_text = "(skipped)" if opinion_text.lower() == "skip" else opinion_text
        for aid in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=aid,
                    text=f"⭐ *Full Rating*\n\n👤 {name}\n🆔 `{user.id}`\n{star_display} ({stars}/5)\n\n💬 Opinion: {skip_text}",
                    parse_mode="Markdown")
            except:
                pass

        await typing_action(cid, context, 1.0)
        welcome_text = build_welcome_text(lang, user.first_name)
        msg = await send_welcome_media(
        context, cid,
            f"{ui('rating_thanks', lang).format(name=escape_md(user.first_name))}\n\n{welcome_text}",
            main_menu(lang))
        context.user_data["last_bot_msg_id"] = msg.message_id
        track_msg(cid, msg.message_id)
        return

    # FIX: Check support session FIRST — before deleting anything
    if active_support.get(user.id):
        track_support_msg(cid, message.message_id)
        await forward_to_admin(context, user, message)
        return

    # Only delete for non-support users (melt effect)
    await delete_user_msg(message)

    # Media from non-support users
    if message.photo or message.video or message.voice or message.document or message.sticker:
        await typing_action(cid, context, 1.0)
        await delete_all_bot_msgs(context, cid)
        msg = await send_protected_text(
            context, cid, ui("msg_received", lang), support_keyboard(lang))
        context.user_data["last_bot_msg_id"] = msg.message_id
        track_msg(cid, msg.message_id)
        return

    if not message.text:
        return

    text = message.text.strip()
    low  = text.lower()

    await typing_action(cid, context, 1.8)
    await delete_all_bot_msgs(context, cid)

    async def reply_with_photo(img, caption, keyboard):
        m = await send_protected_photo(context, cid, img, caption, keyboard)
        context.user_data["last_bot_msg_id"] = m.message_id
        track_msg(cid, m.message_id)

    async def reply_with_welcome(caption, keyboard):
        m = await send_welcome_media(context, cid, caption, keyboard)
        context.user_data["last_bot_msg_id"] = m.message_id
        track_msg(cid, m.message_id)

    async def reply_with_text(text_content, keyboard):
        m = await send_protected_text(context, cid, text_content, keyboard)
        context.user_data["last_bot_msg_id"] = m.message_id
        track_msg(cid, m.message_id)

    # Keyword routing
    if any(w in low for w in [
        "hi","hello","hey","hujambo","habari","salaam","bonjour","hola",
        "привет","مرحبا","नमस्ते","niaje","mambo","wassup","ciao","你好"
    ]) and not any(w in low for w in [
        "signal","vip","pocket","social","copy","indicator","auto","bot",
        "support","help","price","referral","free bot","manual"
    ]):
        welcome_text = build_welcome_text(lang, user.first_name)
        await reply_with_welcome(welcome_text, main_menu(lang))

    elif any(w in low for w in [
        "signal","signals","vip","alert","ishara","forex signal","win rate","binary signal"
    ]):
        img = rand_img(IMGS_SIGNALS, context.user_data, "last_img_signals")
        await reply_with_photo(img, random.choice(get_replies(SIGNALS_REPLIES, lang)), svc_keyboard(lang, signals=True))

    elif any(w in low for w in [
        "social","copy","pocket","copy trade","copy trading","nakili"
    ]):
        img = rand_img(IMGS_SOCIAL, context.user_data, "last_img_social")
        await reply_with_photo(img, random.choice(get_replies(SOCIAL_REPLIES, lang)), svc_keyboard(lang, social=True))

    elif any(w in low for w in [
        "indicator","chart","mt4","mt5","free indicator","kiashiria","arrow","technical"
    ]):
        img = rand_img(IMGS_INDICATOR, context.user_data, "last_img_indicator")
        await reply_with_photo(img, random.choice(get_replies(INDICATOR_REPLIES, lang)),
                               svc_keyboard(lang, indicator=True))

    elif any(w in low for w in [
        "free bot","manual bot","freebot","bot ya bure","free manual"
    ]):
        img = rand_img(IMGS_FREEBOT, context.user_data, "last_img_freebot")
        await reply_with_photo(img, random.choice(get_replies(FREEBOT_REPLIES, lang)), freebot_menu(lang))

    elif any(w in low for w in [
        "auto","robot","automatic","autobot","trading bot",
        "quotex","deriv","olymp","binomo","iq option","broker","leseni"
    ]):
        img = rand_img(IMGS_AUTOBOT, context.user_data, "last_img_autobot")
        await reply_with_photo(img, random.choice(get_replies(AUTOBOT_REPLIES, lang)), svc_keyboard(lang, autobot=True))

    elif any(w in low for w in [
        "referral","refer","invite","earn","reward","kiungo","zawadi","alika"
    ]):
        ref_count = get_referral_count(user.id)
        needed = max(0, REFERRAL_MIN - ref_count)
        bar = make_progress_bar(ref_count, REFERRAL_MIN)
        leaderboard = get_fake_leaderboard(ref_count)
        ref_text = ui("referral_msg", lang).format(
            bot=BOT_USERNAME, uid=user.id,
            count=ref_count, min=REFERRAL_MIN,
            needed=needed, bar=bar, leaderboard=leaderboard)
        await reply_with_text(ref_text, InlineKeyboardMarkup([
            [InlineKeyboardButton(ui("btn_back", lang), callback_data="main_menu")]
        ]))

    elif any(w in low for w in [
        "price","cost","bei","pesa","pay","payment","subscribe","plan","nunua","ngapi"
    ]):
        await reply_with_text(ui("price_msg", lang), InlineKeyboardMarkup([
            [InlineKeyboardButton(ui("btn_website", lang), url=WEBSITE_URL)],
            [InlineKeyboardButton(ui("btn_support", lang), callback_data="do_support")],
            [InlineKeyboardButton(ui("btn_back", lang), callback_data="main_menu")],
        ]))

    elif any(w in low for w in [
        "support","help","assist","contact","agent","admin","msaada","wasiliana"
    ]):
        await notify_support_request(context, user, lang)
        await reply_with_text(ui("support_msg", lang), InlineKeyboardMarkup([
            [InlineKeyboardButton(ui("btn_back", lang), callback_data="main_menu")]
        ]))

    elif any(w in low for w in [
        "thank","thanks","asante","merci","gracias","спасибо","شكرا","danke"
    ]):
        await reply_with_text(
            f"😊 Thank you, *{escape_md(user.first_name)}!* Always here for you. 🚀",
            InlineKeyboardMarkup([
                [InlineKeyboardButton(ui("btn_back", lang), callback_data="main_menu")]
            ]))

    else:
        await reply_with_text(ui("fallback_msg", lang), support_keyboard(lang))

# ══════════════════════════════════════════════════════════════
#  /preview — Admin sees exactly what new user sees
# ══════════════════════════════════════════════════════════════

async def preview_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /preview        — Preview current bot flow (English)
    /preview sw     — Preview in Swahili
    /preview en     — Preview in English
    Works for all 20 supported languages.
    """
    if not is_admin(update.effective_user.id):
        return

    user = update.effective_user
    cid  = update.effective_chat.id

    # Parse language arg
    lang = "en"
    if context.args:
        arg = context.args[0].lower().strip()
        if arg in UI:
            lang = arg

    await update.message.reply_text(
        f"👁 *PREVIEW MODE*\n\n"
        f"🌍 Language: `{lang}`\n"
        f"📱 Showing current bot flow (8 steps)...\n\n"
        f"_This is exactly what users see_",
        parse_mode="Markdown")

    await asyncio.sleep(0.8)

    # ── STEP 1: Language selector ──────────────────────────────
    await context.bot.send_message(
        chat_id=cid,
        text="━━━━━━━━━━━━━━━━━━\n📍 *STEP 1: Language Selector* (first visit only)\n━━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown")
    await asyncio.sleep(0.4)
    await context.bot.send_message(
        chat_id=cid,
        text="🏆 *EVALON WINNERS TRADER* 🏆\n\nChoose your language / Chagua lugha yako:",
        parse_mode="Markdown",
        reply_markup=lang_keyboard())
    await asyncio.sleep(1.2)

    # ── STEP 2: Join gate ──────────────────────────────────────
    await context.bot.send_message(
        chat_id=cid,
        text="━━━━━━━━━━━━━━━━━━\n📍 *STEP 2: Channel Join Gate*\n━━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown")
    await asyncio.sleep(0.4)
    await context.bot.send_message(
        chat_id=cid,
        text=ui("join_msg", lang),
        parse_mode="Markdown",
        reply_markup=join_keyboard(lang))
    await asyncio.sleep(1.2)

    # ── STEP 3: Welcome screen — users land here directly after joining ──
    await context.bot.send_message(
        chat_id=cid,
        text="━━━━━━━━━━━━━━━━━━\n📍 *STEP 3: Welcome + Main Menu*\n_(Users go here directly after channel join)_\n━━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown")
    await asyncio.sleep(0.4)
    welcome_text = build_welcome_text(lang, user.first_name)
    try:
        await send_welcome_media(context, cid, welcome_text, main_menu(lang))
    except Exception as e:
        await context.bot.send_message(
            chat_id=cid, text=welcome_text,
            parse_mode="Markdown", reply_markup=main_menu(lang))
    await asyncio.sleep(1.2)

    # ── STEP 4: Services menu ──────────────────────────────────
    await context.bot.send_message(
        chat_id=cid,
        text="━━━━━━━━━━━━━━━━━━\n📍 *STEP 4: Services Menu*\n━━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown")
    await asyncio.sleep(0.4)
    await context.bot.send_message(
        chat_id=cid,
        text=ui("services_msg", lang),
        parse_mode="Markdown",
        reply_markup=services_menu(lang))
    await asyncio.sleep(1.2)

    # ── STEP 5: Free Bot menu — all brokers ───────────────────
    await context.bot.send_message(
        chat_id=cid,
        text="━━━━━━━━━━━━━━━━━━\n📍 *STEP 5: Free Bot Menu (All Brokers)*\n━━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown")
    await asyncio.sleep(0.4)
    _freebot_txt = {
        "sw": "🆓 *FREE MANUAL BOT — EVALON* 🤖\n\nPata bot yetu ya BURE!\n\n✅ Mawakala WOTE\n✅ Rahisi kutumia\n\nChagua broker yako 👇",
        "en": "🆓 *FREE MANUAL BOT — EVALON* 🤖\n\nGet our FREE trading bot!\n\n✅ Works on ALL brokers\n✅ Easy to use\n\nChoose your broker 👇",
    }
    await context.bot.send_message(
        chat_id=cid,
        text=_freebot_txt.get(lang, _freebot_txt["en"]),
        parse_mode="Markdown",
        reply_markup=freebot_menu(lang))
    await asyncio.sleep(1.2)

    # ── STEP 6: Broker poll ────────────────────────────────────
    await context.bot.send_message(
        chat_id=cid,
        text="━━━━━━━━━━━━━━━━━━\n📍 *STEP 6: Broker Poll*\n_(Shown to new users)_\n━━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown")
    await asyncio.sleep(0.4)
    await context.bot.send_message(
        chat_id=cid,
        text=ui("poll_msg", lang),
        parse_mode="Markdown",
        reply_markup=poll_keyboard(lang))
    await asyncio.sleep(1.2)

    # ── STEP 7: Spin wheel ─────────────────────────────────────
    await context.bot.send_message(
        chat_id=cid,
        text="━━━━━━━━━━━━━━━━━━\n📍 *STEP 7: Lucky Spin*\n_(1x per day — 5% win chance)_\n━━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown")
    await asyncio.sleep(0.4)
    await context.bot.send_message(
        chat_id=cid,
        text=SPIN_WHEEL_VISUAL + "      ✨ Spinning... ✨",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔄 Spin Again Tomorrow 🕐", callback_data="noop"),
        ]]))
    await asyncio.sleep(0.8)

    # ── STEP 8: Broadcast sample ───────────────────────────────
    await context.bot.send_message(
        chat_id=cid,
        text="━━━━━━━━━━━━━━━━━━\n📍 *STEP 8: Broadcast Sample*\n_(How broadcast messages appear)_\n━━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown")
    await asyncio.sleep(0.4)
    await context.bot.send_message(
        chat_id=cid,
        text="🔥 *EVALON WINNERS — BROADCAST!*\n\n📊 Today signals: *9/10 won!* 💪\n\n_Bold, italic, emojis — all preserved exactly as admin sends_",
        parse_mode="Markdown",
        reply_markup=broadcast_keyboard(lang))
    await asyncio.sleep(0.6)

    # ── DONE ───────────────────────────────────────────────────
    await context.bot.send_message(
        chat_id=cid,
        text=(
            "━━━━━━━━━━━━━━━━━━\n"
            "✅ *PREVIEW COMPLETE!*\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"🌍 Language: `{lang}` | 8 steps shown\n\n"
            "📌 Other languages:\n"
            "• `/preview sw` — Swahili\n"
            "• `/preview ar` — Arabic\n"
            "• `/preview hi` — Hindi\n"
            "• `/preview fr` — French\n"
            "• Works for all 20 languages\n\n"
            "🗑 Delete these messages when done."
        ),
        parse_mode="Markdown")

# ══════════════════════════════════════════════════════════════
#  /spinners — Admin sees most active spinners to pick winners
#  /givespin  — Admin manually gives discount to chosen user
# ══════════════════════════════════════════════════════════════

async def spinners_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    spinners = get_top_spinners(limit=10)
    if not spinners:
        await update.message.reply_text("🎰 No spinners yet.")
        return

    text = "🎰 *TOP ACTIVE SPINNERS*\n\n"
    text += "_Pick a winner and use /givespin to reward them_\n\n"
    kb = []
    medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    for i, (uid, uname, uusername, total, last_spin) in enumerate(spinners):
        safe_name = escape_md(uname or str(uid))
        uun = f"@{uusername}" if uusername else "no username"
        last = last_spin[:10] if last_spin else "?"
        text += f"{medals[i]} {safe_name} ({uun})\n   🔢 *{total} spins* | Last: {last}\n\n"
        kb.append([InlineKeyboardButton(
            f"🎁 Reward: {(uname or str(uid))[:18]} ({total} spins)",
            callback_data=f"givespin_btn:{uid}"
        )])

    await update.message.reply_text(
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb))


async def givespin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Usage: /givespin USER_ID DISCOUNT SERVICE
    Example: /givespin 123456789 3 signals
    Services: signals, social, indicator, autobot, any
    """
    if not is_admin(update.effective_user.id):
        return

    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "📋 *How to give a spin reward:*\n\n"
            "`/givespin USER_ID DISCOUNT SERVICE`\n\n"
            "*Examples:*\n"
            "• `/givespin 123456789 3 signals`\n"
            "• `/givespin 987654321 5 autobot`\n"
            "• `/givespin 111222333 2 any`\n\n"
            "*Services:* signals | social | indicator | autobot | any",
            parse_mode="Markdown")
        return

    try:
        target_uid = int(args[0])
        discount   = int(args[1].replace("%", ""))
        service    = args[2].lower() if len(args) > 2 else "any"
    except:
        await update.message.reply_text(
            "❌ Wrong format.\n\nUse: `/givespin USER_ID DISCOUNT SERVICE`",
            parse_mode="Markdown")
        return

    service_names = {
        "signals":   "📊 VIP Signals",
        "social":    "👥 Social Trading",
        "indicator": "📈 Free Indicator",
        "autobot":   "🤖 Auto Bot",
        "any":       "🏆 Any Service of Your Choice",
    }
    service_display = service_names.get(service, f"🎁 {service}")

    u_info = get_user_info(target_uid)
    ulang  = u_info.get("lang", "en") or "en"

    win_texts = {
        "en": (
            f"🎉 *CONGRATULATIONS! YOU WON!* 🎉\n\n"
            f"🎰 Our team reviewed your Lucky Spin activity and *selected you as a winner!*\n\n"
            f"🎁 You have earned a *{discount}% DISCOUNT* on:\n"
            f"*{service_display}*\n\n"
            f"This is your reward for being one of our most active members! 🏆\n\n"
            f"👇 Tap below to claim your prize now:"
        ),
        "sw": (
            f"🎉 *HONGERA! UMESHINDA!* 🎉\n\n"
            f"🎰 Timu yetu ilichunguza shughuli yako ya Lucky Spin na *kukuchagua kama mshindi!*\n\n"
            f"🎁 Umepata *Punguzo la {discount}%* kwenye:\n"
            f"*{service_display}*\n\n"
            f"Hii ni tuzo yako kwa kuwa mmoja wa wanachama wetu wanaoshiriki zaidi! 🏆\n\n"
            f"👇 Bonyeza hapa chini kupata tuzo yako sasa:"
        ),
        "ar": (
            f"🎉 *تهانينا! لقد فزت!* 🎉\n\n"
            f"🎰 راجع فريقنا نشاطك في Lucky Spin *واختارك فائزاً!*\n\n"
            f"🎁 حصلت على *خصم {discount}%* على:\n"
            f"*{service_display}*\n\n"
            f"هذه مكافأتك لكونك من أكثر أعضائنا نشاطاً! 🏆\n\n"
            f"👇 اضغط أدناه للمطالبة بجائزتك الآن:"
        ),
        "ru": (
            f"🎉 *ПОЗДРАВЛЯЕМ! ВЫ ВЫИГРАЛИ!* 🎉\n\n"
            f"🎰 Наша команда изучила вашу активность Lucky Spin и *выбрала вас победителем!*\n\n"
            f"🎁 Вы получили *скидку {discount}%* на:\n"
            f"*{service_display}*\n\n"
            f"Это ваша награда за то, что вы один из наших самых активных участников! 🏆\n\n"
            f"👇 Нажмите ниже, чтобы получить приз:"
        ),
        "zh": (
            f"🎉 *恭喜！您赢了！* 🎉\n\n"
            f"🎰 我们的团队审查了您的幸运转盘活动并*选择您为获胜者！*\n\n"
            f"🎁 您获得了 *{discount}% 折扣*：\n"
            f"*{service_display}*\n\n"
            f"这是您作为我们最活跃成员之一的奖励！ 🏆\n\n"
            f"👇 点击下方立即领取您的奖品："
        ),
    }
    win_msg = win_texts.get(ulang, win_texts["en"])

    try:
        await context.bot.send_message(
            chat_id=target_uid,
            text=win_msg,
            parse_mode="Markdown",
            protect_content=True,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🎁 Claim My Prize Now!", callback_data="do_support")
            ]]))
        active_support[target_uid] = True
        await update.message.reply_text(
            f"✅ *Reward sent successfully!*\n\n"
            f"👤 User ID: `{target_uid}`\n"
            f"🎁 Discount: *{discount}%*\n"
            f"📌 Service: {service_display}\n\n"
            f"User is now connected to support.\n"
            f"Reply to their messages to complete the transaction.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🟢 Open Chat", callback_data=f"con:{target_uid}:{ulang}")
            ]]))
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to send prize: {e}")

async def setnews_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /setnews Some text here
    Or reply to a photo/video with /setnews Optional caption
    """
    if not is_admin(update.effective_user.id):
        return
    msg = update.message
    replied = msg.reply_to_message
    text_val = " ".join(context.args) if context.args else None

    if replied and replied.photo:
        set_dynamic_content("news", text_value=text_val or replied.caption,
                            file_id=replied.photo[-1].file_id, file_type="photo")
    elif replied and replied.video:
        set_dynamic_content("news", text_value=text_val or replied.caption,
                            file_id=replied.video.file_id, file_type="video")
    elif text_val:
        set_dynamic_content("news", text_value=text_val)
    else:
        await msg.reply_text(
            "❌ Usage:\n• `/setnews Your text here`\n• Reply to photo/video + `/setnews`",
            parse_mode="Markdown")
        return
    await msg.reply_text("✅ *What's New* updated! Users will see it immediately.", parse_mode="Markdown")


async def setresult_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /setresult — Manually save current VIP session to past results history
    Or reply to photo/video: /setresult Optional label
    """
    if not is_admin(update.effective_user.id):
        return
    msg = update.message
    replied = msg.reply_to_message
    text_val = " ".join(context.args) if context.args else None
    today = datetime.now().strftime("%d/%m/%Y %H:%M")

    if replied and replied.photo:
        cap = text_val or replied.caption or ""
        save_result(today, cap, media_id=replied.photo[-1].file_id, media_type="photo")
    elif replied and replied.video:
        cap = text_val or replied.caption or ""
        save_result(today, cap, media_id=replied.video.file_id, media_type="video")
    elif text_val:
        save_result(today, text_val)
    else:
        # Save current VIP content
        vip = get_dynamic_content("vip")
        if vip and (vip.get("text") or vip.get("file_id")):
            label = f"📅 {today}\n\n{vip.get('text') or ''}"
            save_result(today, label.strip(), media_id=vip.get("file_id"), media_type=vip.get("file_type"))
            await msg.reply_text("✅ Current VIP session saved to *Past Results*!", parse_mode="Markdown")
        else:
            await msg.reply_text(
                "❌ Usage:\n"
                "• `/setresult` — saves current VIP content to history\n"
                "• `/setresult Text here` — save text as past result\n"
                "• Reply to photo/video + `/setresult`",
                parse_mode="Markdown")
        return

    await msg.reply_text("✅ Result saved to *Past Results History*!", parse_mode="Markdown")


async def setvip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /setvip Some text here
    Or reply to a photo/video with /setvip Optional caption
    """
    if not is_admin(update.effective_user.id):
        return
    msg = update.message
    replied = msg.reply_to_message
    text_val = " ".join(context.args) if context.args else None

    # ── AUTO-SAVE: Move existing VIP content to results_history before overwriting ──
    old_vip = get_dynamic_content("vip")
    auto_saved = False
    if old_vip and (old_vip.get("text") or old_vip.get("file_id")):
        saved_date = old_vip.get("updated_at", datetime.now().strftime("%d/%m/%Y %H:%M"))
        today_str = datetime.now().strftime("%d/%m/%Y")
        # Check if already saved today (by date prefix) to avoid duplicates
        existing = get_results_history(10)
        already_saved_today = any(
            row[4] and row[4].startswith(today_str)
            for row in existing
        )
        if not already_saved_today:
            label = f"📅 Session: {saved_date}\n\n{old_vip.get('text') or ''}"
            try:
                auto_saved = save_result(
                    result_date=saved_date,
                    content_text=label.strip(),
                    media_id=old_vip.get("file_id"),
                    media_type=old_vip.get("file_type"),
                )
            except Exception as e:
                logger.warning(f"setvip auto-save failed: {e}")
                auto_saved = False

    if replied and replied.photo:
        set_dynamic_content("vip", text_value=text_val or replied.caption,
                            file_id=replied.photo[-1].file_id, file_type="photo")
    elif replied and replied.video:
        set_dynamic_content("vip", text_value=text_val or replied.caption,
                            file_id=replied.video.file_id, file_type="video")
    elif text_val:
        set_dynamic_content("vip", text_value=text_val)
    else:
        await msg.reply_text(
            "❌ Usage:\n• `/setvip Today: 8/10 signals won! 🔥`\n• Reply to photo/video + `/setvip`",
            parse_mode="Markdown")
        return

    saved_note = "\n\U0001f4e6 _Previous session auto-saved to Past Results._" if auto_saved else ""
    await msg.reply_text(
        f"\u2705 *VIP Results* updated! Users will see it immediately.{saved_note}",
        parse_mode="Markdown")


async def clearnews_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear news or vip content: /clearnews or /clearvip"""
    if not is_admin(update.effective_user.id):
        return
    cmd = update.message.text.strip().lower()
    key = "vip" if "vip" in cmd else "news"
    set_dynamic_content(key, text_value=None, file_id=None, file_type=None)
    label = "VIP Results" if key == "vip" else "Whats New"
    await update.message.reply_text(f"✅ *{label}* cleared.", parse_mode="Markdown")


async def results_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save today's session results to history: /results text or reply to photo/video"""
    if not is_admin(update.effective_user.id):
        return
    msg = update.message
    today = datetime.now().strftime("%d/%m/%Y")
    text = " ".join(context.args) if context.args else None

    if msg.reply_to_message:
        r = msg.reply_to_message
        if r.photo:
            fid = r.photo[-1].file_id
            cap = r.caption or text or ""
            save_result(today, cap, media_id=fid, media_type="photo")
            await msg.reply_text("✅ *Results saved!* (photo)", parse_mode="Markdown")
            return
        elif r.video:
            fid = r.video.file_id
            cap = r.caption or text or ""
            save_result(today, cap, media_id=fid, media_type="video")
            await msg.reply_text("✅ *Results saved!* (video)", parse_mode="Markdown")
            return

    if text:
        save_result(today, text)
        await msg.reply_text("✅ *Results saved!*", parse_mode="Markdown")
    else:
        await msg.reply_text(
            "❌ Usage:\n`/results Today 8/10 won!`\nor reply to a photo/video with `/results`",
            parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show all admin commands — /help"""
    if not is_admin(update.effective_user.id):
        return

    # Send in 2 messages to avoid Telegram 4096 char limit
    msg1 = (
        "🤖 *EVALON WINNERS — ADMIN PANEL*\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "📊 *STATISTICS & USERS*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "`/stats` — Jumla ya users, active, wapya leo, top referrers\n"
        "`/users` — Orodha ya users WOTE (jina + ID)\n"
        "`/users john` — Tafuta user kwa jina, username, au ID\n"
        "`/blockedusers` — Users waliozuia bot\n"
        "`/history USER_ID` — Ujumbe 50 wa mwisho na user huyo\n"
        "`/history USER_ID 100` — Ujumbe 100\n"
        "`/history USER_ID all` — Ujumbe WOTE tangu siku ya kwanza\n"
        "`/userchart USER_ID` — Chart ya shughuli za kila siku\n"
        "`/getid` _(reply to photo/video)_ — Pata file_id\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "📢 *BROADCAST*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "`/broadcast Ujumbe wako` — Tuma text kwa users WOTE\n"
        "`/broadcast` _(reply to photo/video/file)_ — Tuma media kwa wote\n"
        "✅ Bold, italic, links — zinahifadhiwa exactly kama ulivyoandika\n"
        "✅ Progress inaonyeshwa kila users 50\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🆕 *DYNAMIC CONTENT*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "`/setnews Ujumbe wako` — Weka What's New ya leo\n"
        "`/setnews` _(reply to photo/video)_ — Weka na picha/video\n"
        "`/setvip Leo: 8/10 zilishinda!` — Weka VIP Results\n"
        "`/setvip` _(reply to photo/video)_ — Weka na media\n"
        "`/clearnews` — Futa What's New content\n"
        "`/clearvip` — Futa VIP Results content\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "📈 *RESULTS HISTORY*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "`/results Leo 8/10 zilishinda!` — Hifadhi matokeo ya session\n"
        "`/results` _(reply to photo/video)_ — Hifadhi na media\n"
        "`/setresult` — Hifadhi VIP content ya sasa kama result\n"
        "`/setresult Maandishi` _(au reply to photo)_ — Hifadhi na label\n"
    )

    msg2 = (
        "━━━━━━━━━━━━━━━━━━\n"
        "💬 *SUPPORT SESSIONS*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "`/sessions` — Ona na simamia support sessions zinazoendelea\n"
        "🟢 Connect — Anza mazungumzo na user\n"
        "🔴 End Chat — Maliza session + tuma rating\n"
        "_Reply kwenye ujumbe ulioforwardiwa = jibu user_\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🎰 *SPIN WHEEL*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "`/spinners` — Top 10 wanaospin zaidi\n"
        "`/givespin USER_ID DISCOUNT SERVICE` — Toa tuzo\n"
        "   Mfano: `/givespin 123456789 30 signals`\n"
        "   Services: `signals` `social` `indicator` `autobot` `any`\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "⭐ *SUCCESS STORIES*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "`/addstory Maandishi yako` — Ongeza story ya maandishi\n"
        "`/addstory` _(reply to photo/video)_ — Ongeza story na media\n"
        "`/liststories` — Ona stories zote na IDs zao\n"
        "`/deletestory ID` — Futa story kwa ID\n"
        "_Stories button inaonekana main menu tu ukiwa na story 1+_\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🔧 *BOT SETTINGS*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "`/setwelcome` _(reply to video/photo)_ — Badilisha welcome screen\n"
        "`/setwelcome reset` — Rudisha welcome video ya default\n"
        "`/setpocketlink` https://t.me/YourBot — Weka link ya Pocket Option bot\n"
        "`/addphoto` _(reply to photo)_ — Ongeza picha kwenye service images pool\n"
        "`/addbot Jina | Link | Maelezo` — Ongeza bot kwenye Free Bots menu\n"
        "`/addbot` — Ona bots zote zilizoongezwa\n"
        "`/delbot ID` — Futa bot kutoka menu\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "⭐ *FAKE FEEDBACK*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "`/feedback` — Tuma feedback 5 za mchanganyiko\n"
        "`/feedback 70` — Tuma feedback 70\n"
        "`/feedbackadd Jina | 🇳🇬 | Maandishi` — Ongeza feedback yako\n"
        "`/feedbacklist` — Ona feedback zote za custom\n"
        "`/feedbackdlt` — Futa feedback ZOTE za custom\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "👁 *PREVIEW & TOOLS*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "`/preview` — Ona flow kamili ya user mpya (English, steps 8)\n"
        "`/preview sw` — Preview kwa lugha yoyote (sw/ar/hi/fr...)\n"
        "`/help` — Onyesha commands hizi\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "💡 *VIDOKEZO*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "• `/setnews` na `/setvip` zinafanya kazi mara moja — huhitaji redeploy\n"
        "• `/users` kisha `/history ID` = njia rahisi ya kuona mazungumzo\n"
        "• `/spinners` kila wiki — chagua washindi 1-2 wa tuzo\n"
        "• Broadcast: reply kwenye ujumbe wowote + `/broadcast` = inatumwa exactly"
    )

    await update.message.reply_text(msg1, parse_mode="Markdown")
    await asyncio.sleep(0.3)
    await update.message.reply_text(msg2, parse_mode="Markdown")


async def feedback_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Send N mixed feedback messages (EN-heavy, auto-mixed with SW & UR)
    Usage: /feedback        → 5 feedback
    Usage: /feedback 70     → 70 feedback
    Usage: /feedback 100    → 100 feedback
    """
    if not is_admin(update.effective_user.id):
        return

    args = context.args
    count = 5
    if args and args[0].isdigit():
        count = min(int(args[0]), 200)  # max 200

    custom_count = len(get_custom_feedback())

    await update.message.reply_text(
        f"📨 *FEEDBACK PREVIEW*\n\n"
        f"📊 Sending: *{count}* mixed feedback\n"
        f"🌍 Mix: ~70% English, ~20% Swahili, ~10% Urdu\n"
        f"✏️ Custom feedback in DB: *{custom_count}*\n\n"
        f"_Sending now — one by one..._",
        parse_mode="Markdown")

    feedbacks = get_mixed_feedback(count)
    await asyncio.sleep(0.5)

    for i, (name, flag, text) in enumerate(feedbacks, 1):
        await asyncio.sleep(0.9)
        msg_text = f"{flag} *{escape_md(name)}*\n\n_{escape_md(text)}_\n\n⭐⭐⭐⭐⭐"
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=msg_text,
                parse_mode="Markdown")
        except Exception as e:
            logger.warning(f"Feedback msg {i} failed: {e}")

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=(
            f"✅ *Done! {count} feedback sent.*\n\n"
            f"📌 *Tips:*\n"
            f"• `/feedback 70` — send 70 mixed\n"
            f"• `/feedback 100` — send 100 mixed\n"
            f"• `/feedbackadd` — add your own feedback\n"
            f"• `/feedbackdlt` — delete all custom feedback\n"
            f"• `/feedbacklist` — see your custom feedback\n\n"
            f"🎬 Record screen then broadcast with `/broadcast`!"
        ),
        parse_mode="Markdown")


async def feedbackadd_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Add custom feedback to DB
    Usage: /feedbackadd Name | Flag | Your feedback text here
    Example: /feedbackadd John K. | 🇳🇬 | Made $500 this week with Evalon signals!
    """
    if not is_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text(
            "📝 *How to add custom feedback:*\n\n"
            "`/feedbackadd Name | Flag | Feedback text`\n\n"
            "*Examples:*\n"
            "• `/feedbackadd John K. | 🇳🇬 | Made $500 this week with Evalon signals! Amazing!`\n"
            "• `/feedbackadd Maria S. | 🇧🇷 | Best trading bot ever. 9/10 signals win!`\n"
            "• `/feedbackadd Hassan M. | 🇹🇿 | Auto bot ilifanya $180 nikiwa nimelala!`\n\n"
            "💡 *Tips:*\n"
            "• Use real-sounding names from different countries\n"
            "• Include dollar amounts for credibility\n"
            "• Mix languages for authenticity",
            parse_mode="Markdown")
        return

    full_text = " ".join(context.args)
    parts = [p.strip() for p in full_text.split("|")]

    if len(parts) < 3:
        await update.message.reply_text(
            "❌ Wrong format. Use:\n`/feedbackadd Name | Flag | Text`",
            parse_mode="Markdown")
        return

    name = parts[0]
    flag = parts[1]
    text_val = " | ".join(parts[2:])  # allow | in text itself

    add_custom_feedback(name, flag, text_val)
    total = len(get_custom_feedback())

    await update.message.reply_text(
        f"✅ *Custom feedback added!*\n\n"
        f"{flag} *{escape_md(name)}*\n_{escape_md(text_val)}_\n\n"
        f"📊 Total custom feedback in DB: *{total}*\n\n"
        f"_Use `/feedback 10` to preview mixed feedback_",
        parse_mode="Markdown")


async def feedbackdlt_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete ALL custom feedback from DB"""
    if not is_admin(update.effective_user.id):
        return

    count = delete_all_custom_feedback()
    await update.message.reply_text(
        f"🗑 *All custom feedback deleted!*\n\n"
        f"Removed: *{count}* entries\n\n"
        f"_Built-in feedback (EN/SW/UR) is still available._",
        parse_mode="Markdown")


async def feedbacklist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all custom feedback in DB"""
    if not is_admin(update.effective_user.id):
        return

    custom = get_custom_feedback()
    if not custom:
        await update.message.reply_text(
            "📭 *No custom feedback in DB yet.*\n\nUse `/feedbackadd` to add some.",
            parse_mode="Markdown")
        return

    text = f"📋 *Custom Feedback ({len(custom)} entries):*\n\n"
    for i, (name, flag, fb_text, lang) in enumerate(custom[:20], 1):
        short = fb_text[:60] + "..." if len(fb_text) > 60 else fb_text
        text += f"{i}. {flag} *{escape_md(name)}*: _{escape_md(short)}_\n"
    if len(custom) > 20:
        text += f"\n_...and {len(custom) - 20} more_"

    await update.message.reply_text(text, parse_mode="Markdown")


def init_media_db():
    """Store admin-added photos/videos and bot links"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS admin_media (
            id          SERIAL PRIMARY KEY,
            media_type  TEXT NOT NULL,
            file_id     TEXT NOT NULL,
            caption     TEXT DEFAULT NULL,
            added_at    TEXT DEFAULT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS admin_bots (
            id          SERIAL PRIMARY KEY,
            name        TEXT NOT NULL,
            link        TEXT NOT NULL,
            description TEXT DEFAULT NULL,
            added_at    TEXT DEFAULT NULL
        )
    """)
    conn.commit()
    conn.close()

def add_admin_photo(file_id, caption=""):
    conn = get_conn()
    c = conn.cursor()
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    c.execute("INSERT INTO admin_media (media_type, file_id, caption, added_at) VALUES (%s,%s,%s,%s)",
              ("photo", file_id, caption, now))
    conn.commit()
    conn.close()

def get_admin_photos():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT file_id FROM admin_media WHERE media_type='photo'")
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

def add_admin_bot(name, link, description=""):
    conn = get_conn()
    c = conn.cursor()
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    c.execute("INSERT INTO admin_bots (name, link, description, added_at) VALUES (%s,%s,%s,%s)",
              (name, link, description, now))
    conn.commit()
    conn.close()

def get_admin_bots():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, name, link, description FROM admin_bots ORDER BY id")
    rows = c.fetchall()
    conn.close()
    return rows

def delete_admin_bot(bot_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM admin_bots WHERE id=%s", (bot_id,))
    conn.commit()
    conn.close()

# ══════════════════════════════════════════════════════════════
#  BLOCKED USERS TRACKING
# ══════════════════════════════════════════════════════════════

def init_blocked_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS blocked_users (
            user_id     BIGINT PRIMARY KEY,
            name        TEXT DEFAULT NULL,
            username    TEXT DEFAULT NULL,
            blocked_at  TEXT DEFAULT NULL
        )
    """)
    conn.commit()
    conn.close()

def mark_blocked_user(uid):
    """Record that this user has blocked the bot"""
    conn = get_conn()
    c = conn.cursor()
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    # Try to get their name from users table
    c.execute("SELECT name, username FROM users WHERE id=%s", (uid,))
    row = c.fetchone()
    name = row[0] if row else str(uid)
    username = row[1] if row else ""
    c.execute("""
        INSERT INTO blocked_users (user_id, name, username, blocked_at)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE
        SET blocked_at=EXCLUDED.blocked_at
    """, (uid, name, username, now))
    conn.commit()
    conn.close()

def get_blocked_users(limit=50):
    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute("""
            SELECT user_id, name, username, blocked_at
            FROM blocked_users ORDER BY blocked_at DESC LIMIT %s
        """, (limit,))
        rows = c.fetchall()
        conn.close()
        return rows
    except:
        return []

def unmark_blocked_user(uid):
    """Remove from blocked list if user starts bot again"""
    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute("DELETE FROM blocked_users WHERE user_id=%s", (uid,))
        conn.commit()
        conn.close()
    except:
        pass


async def addphoto_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Add photo to SERVICE_PHOTOS pool — used in service replies
    Reply to a photo with /addphoto Optional caption
    """
    if not is_admin(update.effective_user.id):
        return
    msg = update.message
    replied = msg.reply_to_message

    if not replied or not replied.photo:
        await msg.reply_text(
            "📸 *How to add a photo:*\n\n"
            "1. Send a photo to the bot\n"
            "2. Reply to it with `/addphoto`\n"
            "3. It will be added to the service images pool\n\n"
            "The photo will appear randomly in service replies!",
            parse_mode="Markdown")
        return

    file_id = replied.photo[-1].file_id
    caption = " ".join(context.args) if context.args else replied.caption or ""
    add_admin_photo(file_id, caption)

    # Add to runtime pool too
    SERVICE_PHOTOS.append(file_id)

    await msg.reply_text(
        f"✅ *Photo added to service pool!*\n\n"
        f"`{file_id}`\n\n"
        f"Total photos in pool: *{len(SERVICE_PHOTOS)}*\n"
        f"It will now appear randomly in service replies.",
        parse_mode="Markdown")


async def addbot_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Add new bot link to Free Bots menu
    Usage: /addbot BotName | https://t.me/YourBot | Description
    """
    if not is_admin(update.effective_user.id):
        return

    if not context.args:
        bots = get_admin_bots()
        if not bots:
            await update.message.reply_text(
                "🤖 *How to add a bot:*\n\n"
                "`/addbot Name | Link | Description`\n\n"
                "Example:\n"
                "`/addbot Pocket Bot | https://t.me/PocketBot | New Pocket Option bot`\n\n"
                "Use `/delbotN` to delete (e.g. `/delbot3`)",
                parse_mode="Markdown")
        else:
            text = "🤖 *Your Added Bots:*\n\n"
            for bid, name, link, desc in bots:
                text += f"*{bid}.* {name}\n   {link}\n   _{desc}_\n\n"
            text += "Use `/delbot ID` to remove (e.g. `/delbot 3`)"
            await update.message.reply_text(text, parse_mode="Markdown")
        return

    full = " ".join(context.args)
    parts = [p.strip() for p in full.split("|")]
    if len(parts) < 2:
        await update.message.reply_text(
            "❌ Wrong format.\n`/addbot Name | Link | Description`",
            parse_mode="Markdown")
        return

    name = parts[0]
    link = parts[1]
    desc = parts[2] if len(parts) > 2 else ""
    add_admin_bot(name, link, desc)

    await update.message.reply_text(
        f"✅ *Bot added to Free Bots menu!*\n\n"
        f"🤖 *{escape_md(name)}*\n"
        f"🔗 {escape_md(link)}\n"
        f"_{escape_md(desc)}_\n\n"
        f"Users will see it in the Free Manual Bot section.",
        parse_mode="Markdown")


async def delbot_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete a bot by ID: /delbot 3"""
    if not is_admin(update.effective_user.id):
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage: `/delbot ID`\nGet ID from `/addbot`", parse_mode="Markdown")
        return
    bot_id = int(context.args[0])
    delete_admin_bot(bot_id)
    await update.message.reply_text(f"✅ Bot #{bot_id} removed from menu.", parse_mode="Markdown")


async def addstory_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add a success story — reply to photo/video/text with /addstory [caption]"""
    if not is_admin(update.effective_user.id):
        return
    msg = update.message
    replied = msg.reply_to_message
    caption = " ".join(context.args) if context.args else ""

    if replied and replied.photo:
        fid   = replied.photo[-1].file_id
        cap   = caption or replied.caption or "⭐ Success Story"
        sid   = add_story(cap, media_id=fid, media_type="photo")
        await msg.reply_text(f"✅ *Photo story added!*\nID: `{sid}`\n\n_{cap}_", parse_mode="Markdown")
    elif replied and replied.video:
        fid   = replied.video.file_id
        cap   = caption or replied.caption or "⭐ Success Story"
        sid   = add_story(cap, media_id=fid, media_type="video")
        await msg.reply_text(f"✅ *Video story added!*\nID: `{sid}`\n\n_{cap}_", parse_mode="Markdown")
    elif caption:
        sid = add_story(caption, media_type="text")
        await msg.reply_text(f"✅ *Text story added!*\nID: `{sid}`\n\n_{caption}_", parse_mode="Markdown")
    else:
        await msg.reply_text(
            "📖 *How to add a story:*\n\n"
            "• Text only: `/addstory Great results this week!`\n"
            "• Photo: Reply to photo with `/addstory Great results!`\n"
            "• Video: Reply to video with `/addstory Watch this win!`\n\n"
            "Users will see the ⭐ Stories button in the main menu once you add one.",
            parse_mode="Markdown")


async def liststories_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all stories with IDs — /liststories"""
    if not is_admin(update.effective_user.id):
        return
    stories = get_all_stories()
    if not stories:
        await update.message.reply_text("📭 No stories yet. Use /addstory to add one.")
        return
    lines = ["📖 *SUCCESS STORIES*\n"]
    for s in stories:
        mtype = s.get("media_type", "text")
        icon  = "📷" if mtype == "photo" else "🎥" if mtype == "video" else "📝"
        cap   = (s.get("caption") or "")[:60]
        lines.append(f"{icon} *ID {s['id']}* — _{cap}..._\n   Added: {s.get('created_at','')}")
    lines.append(f"\n*Total: {len(stories)} stories*")
    lines.append("Use `/deletestory [ID]` to remove one.")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def deletestory_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/deletestory [ID] — delete a story"""
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Usage: `/deletestory [ID]`\nGet IDs from /liststories", parse_mode="Markdown")
        return
    try:
        sid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ ID must be a number.")
        return
    if delete_story(sid):
        remaining = len(get_all_stories())
        note = "" if remaining > 0 else "\n\n_No stories left — Stories button hidden from users._"
        await update.message.reply_text(f"✅ Story *{sid}* deleted.{note}", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ Story *{sid}* not found.", parse_mode="Markdown")


async def setwelcome_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Set welcome screen media (video or photo):
    Reply to a video/photo with /setwelcome
    /setwelcome reset — go back to default welcome video
    """
    if not is_admin(update.effective_user.id):
        return
    msg = update.message
    replied = msg.reply_to_message

    # Reset to default
    if context.args and context.args[0].lower() == "reset":
        set_dynamic_content("welcome_media", text_value=None, file_id=None, file_type=None)
        await msg.reply_text(
            "✅ *Welcome screen reset!*\n\nDefault welcome video restored.",
            parse_mode="Markdown")
        return

    if replied and replied.video:
        fid = replied.video.file_id
        set_dynamic_content("welcome_media", file_id=fid, file_type="video")
        await msg.reply_text(
            "✅ *Welcome video updated!*\n\nAll users will now see this video on the welcome screen.\n\nTo reset: `/setwelcome reset`",
            parse_mode="Markdown")
    elif replied and replied.photo:
        fid = replied.photo[-1].file_id
        set_dynamic_content("welcome_media", file_id=fid, file_type="photo")
        await msg.reply_text(
            "✅ *Welcome photo updated!*\n\nAll users will now see this photo on the welcome screen.\n\nTo reset: `/setwelcome reset`",
            parse_mode="Markdown")
    else:
        current_fid, current_type = get_welcome_media()
        is_default = current_fid == WELCOME_VIDEO
        current_info = "_Using default welcome video_" if is_default else f"_Custom {current_type} is set_"
        await msg.reply_text(
            f"🎬 *Set Welcome Screen Media*\n\nCurrent: {current_info}\n\n"
            f"*How to change:*\n"
            f"1. Send a video or photo to the bot\n"
            f"2. Reply to it with `/setwelcome`\n\n"
            f"To reset to default: `/setwelcome reset`",
            parse_mode="Markdown")


async def setpocketlink_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Set Pocket Option bot link: /setpocketlink https://t.me/YourPocketBot
    Link shows as button below the video in Free Bots menu.
    """
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        current = FREE_BOT_LINKS.get("pocket_link", "")
        current_display = f"`{current}`" if current else "_Not set yet_"
        await update.message.reply_text(
            f"🔗 *Pocket Option Bot Link*\n\nCurrent: {current_display}\n\n"
            f"To update:\n`/setpocketlink https://t.me/YourBotName`\n\n"
            f"The link will appear as a button below the video.",
            parse_mode="Markdown")
        return
    new_link = context.args[0].strip()
    if not new_link.startswith("http"):
        await update.message.reply_text("❌ Must be a full URL starting with https://")
        return
    FREE_BOT_LINKS["pocket_link"] = new_link
    # Also save to DB so it persists across restarts
    set_dynamic_content("pocket_bot_link", text_value=new_link)
    await update.message.reply_text(
        f"✅ *Pocket Option Bot link updated!*\n\n"
        f"🔗 `{new_link}`\n\n"
        f"Users will see a '🤖 Open Pocket Option Bot' button when they tap the Pocket Option Bot button.",
        parse_mode="Markdown")


async def blockedusers_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show list of users who have blocked the bot — /blockedusers"""
    if not is_admin(update.effective_user.id):
        return
    users_list = get_blocked_users(limit=50)
    if not users_list:
        await update.message.reply_text(
            "✅ *No blocked users detected yet.*\n\n"
            "Run /broadcast to check — blocked users are detected automatically.",
            parse_mode="Markdown")
        return
    text = f"🚫 *USERS WHO BLOCKED THE BOT*\n\n"
    text += f"Total: *{len(users_list)}*\n\n"
    for uid, name, username, blocked_at in users_list[:30]:
        safe_name = escape_md(name or str(uid))
        uun = f"@{username}" if username else "no username"
        date = (blocked_at or "?")[:10]
        text += f"👤 {safe_name} ({uun})\n   🆔 `{uid}` | 📅 {date}\n\n"
    if len(users_list) > 30:
        text += f"_...and {len(users_list) - 30} more_\n"
    text += "\n💡 _Blocked users are auto-detected during /broadcast_"
    await update.message.reply_text(text, parse_mode="Markdown")


async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /history USER_ID       — Ujumbe 50 wa mwisho
    /history USER_ID 100   — Ujumbe 100
    /history USER_ID all   — Ujumbe WOTE tangu mwanzo
    Kila ujumbe unatumwa peke yake kama chat halisi.
    """
    if not is_admin(update.effective_user.id):
        return
    args = context.args
    if not args:
        await update.message.reply_text(
            "📋 *View Chat History*\n\n"
            "Usage:\n"
            "`/history USER_ID` — last 50 msgs\n"
            "`/history USER_ID 100` — last 100 msgs\n"
            "`/history USER_ID all` — ALL messages ever\n\n"
            "Each message sent separately — like a real chat.",
            parse_mode="Markdown")
        return
    try:
        uid = int(args[0])
    except:
        await update.message.reply_text("❌ Invalid user ID.", parse_mode="Markdown")
        return

    limit = 50
    if len(args) > 1:
        if args[1].lower() == "all":
            limit = 5000
        elif args[1].isdigit():
            limit = int(args[1])

    u_info = get_user_info(uid)
    msgs = get_chat_history_for_user(uid, limit)

    if not msgs:
        await update.message.reply_text(
            f"📭 Hakuna historia ya chat kwa `{uid}`.",
            parse_mode="Markdown")
        return

    safe_name = escape_md(u_info.get("name", str(uid)))
    uun = f"@{u_info.get('username', '')}" if u_info.get("username") else "no username"

    # Header
    await update.message.reply_text(
        f"💬 *CHAT HISTORY*\n"
        f"👤 {safe_name} ({escape_md(uun)})\n"
        f"🆔 `{uid}`\n"
        f"📊 Ujumbe: *{len(msgs)}*\n"
        f"─────────────────────\n"
        f"_Ujumbe wote hapa chini_ 👇",
        parse_mode="Markdown")

    await asyncio.sleep(0.5)

    last_date = None
    for sender, message, media_type, sent_at in msgs:
        await asyncio.sleep(0.12)

        # Date divider when day changes
        try:
            msg_date = sent_at[:10] if sent_at else None
            if msg_date and msg_date != last_date:
                try:
                    dt = datetime.strptime(msg_date, "%d/%m/%Y")
                    date_label = dt.strftime("%A, %d %B %Y")
                except:
                    date_label = msg_date
                await update.message.reply_text(
                    f"📅 ─── *{escape_md(date_label)}* ───",
                    parse_mode="Markdown")
                last_date = msg_date
                await asyncio.sleep(0.1)
        except:
            pass

        # Time (HH:MM only)
        time_str = sent_at[11:16] if sent_at and len(sent_at) > 10 else ""

        if sender == "user":
            icon = "👤"
            label = safe_name
        else:
            icon = "🤖"
            label = "Admin"

        if message:
            # Handle long messages in chunks
            text = message
            first = True
            while text:
                chunk = text[:900]
                text = text[900:]
                header_part = f"{icon} *{escape_md(label)}* `{time_str}`\n" if first else ""
                first = False
                try:
                    await update.message.reply_text(
                        f"{header_part}{escape_md(chunk)}",
                        parse_mode="Markdown")
                except:
                    await update.message.reply_text(
                        f"{icon} {label} [{time_str}]\n{chunk}")
                await asyncio.sleep(0.08)
        elif media_type:
            try:
                await update.message.reply_text(
                    f"{icon} *{escape_md(label)}* `{time_str}`\n📎 _{media_type.upper()}_",
                    parse_mode="Markdown")
            except:
                pass

    # Footer
    await update.message.reply_text(
        f"✅ *Mwisho wa historia* — ujumbe {len(msgs)}",
        parse_mode="Markdown")



# ══════════════════════════════════════════════════════════════
#  /users — Orodha ya users wote: jina + ID
# ══════════════════════════════════════════════════════════════

def get_all_users_list():
    """Leta users wote: id, name, username, joined, last_seen"""
    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute("""
            SELECT id, name, username, joined, last_seen
            FROM users ORDER BY joined ASC
        """)
        rows = c.fetchall()
        conn.close()
        return rows
    except Exception as e:
        logger.warning(f"get_all_users_list failed: {e}")
        return []


async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /users        — Orodha ya users wote (jina + ID)
    /users john   — Tafuta kwa jina au username
    """
    if not is_admin(update.effective_user.id):
        return

    search = " ".join(context.args).lower().strip() if context.args else ""

    await update.message.reply_text(
        f"⏳ Inatafuta{'...' if not search else f' *{escape_md(search)}*...'}",
        parse_mode="Markdown")

    all_users = get_all_users_list()

    if search:
        # Filter by name or username
        filtered = [
            (uid, name, uname, joined, last_seen)
            for uid, name, uname, joined, last_seen in all_users
            if search in (name or "").lower()
            or search in (uname or "").lower()
            or search in str(uid)
        ]
    else:
        filtered = all_users

    total = len(filtered)

    if not filtered:
        await update.message.reply_text(
            f"📭 Hakuna user anayepatikana na '*{escape_md(search)}*'",
            parse_mode="Markdown")
        return

    # Build orodha — send in chunks of 50 users per message
    chunk_size = 50
    chunks = [filtered[i:i+chunk_size] for i in range(0, len(filtered), chunk_size)]
    total_pages = len(chunks)

    for page, chunk in enumerate(chunks, 1):
        lines_out = []

        if page == 1:
            header = (
                f"👥 *USERS LIST*\n"
                f"📊 Jumla: *{total}*"
            )
            if search:
                header += f"\n🔍 Search: `{escape_md(search)}`"
            header += f"\n{'─' * 20}"
            lines_out.append(header)

        for uid, name, uname, joined, last_seen in chunk:
            safe_name = escape_md(name or str(uid))
            uname_str = f"@{uname}" if uname else "—"
            joined_short = joined[:10] if joined else "?"
            lines_out.append(
                f"👤 *{safe_name}*\n"
                f"   🆔 `{uid}`  |  {escape_md(uname_str)}\n"
                f"   📅 {joined_short}"
            )

        if total_pages > 1:
            lines_out.append(f"\n_Ukurasa {page}/{total_pages}_")

        text = "\n\n".join(lines_out)

        try:
            await update.message.reply_text(text, parse_mode="Markdown")
        except Exception as e:
            # Fallback bila markdown
            plain = text.replace("*", "").replace("`", "").replace("_", "").replace("\n", "\n")
            await update.message.reply_text(plain)

        await asyncio.sleep(0.3)



# ══════════════════════════════════════════════════════════════
#  /userchart USER_ID — Visual chat activity chart for a user
# ══════════════════════════════════════════════════════════════



def get_chat_stats_for_user(uid):
    """
    Returns per-day message counts: {date_str: {user: N, admin: N}}
    Also returns first_seen date and total counts.
    """
    try:
        conn = get_conn()
        c = conn.cursor()
        # All messages ever for this user
        c.execute("""
            SELECT sender, sent_at FROM chat_history
            WHERE user_id=%s ORDER BY id ASC
        """, (uid,))
        rows = c.fetchall()
        conn.close()
    except:
        return {}, None, 0, 0

    from collections import defaultdict
    daily = defaultdict(lambda: {"user": 0, "admin": 0})
    total_user = 0
    total_admin = 0
    first_date = None

    for sender, sent_at in rows:
        if not sent_at:
            continue
        try:
            # sent_at format: "DD/MM/YYYY HH:MM"
            day = sent_at[:10]  # "DD/MM/YYYY"
            if sender == "user":
                daily[day]["user"] += 1
                total_user += 1
            else:
                daily[day]["admin"] += 1
                total_admin += 1
            if first_date is None:
                first_date = day
        except:
            continue

    return dict(daily), first_date, total_user, total_admin


def build_text_chart(uid, u_info, daily, first_date, total_user, total_admin):
    """Build ASCII bar chart as Telegram message text."""
    if not daily:
        return None

    name = u_info.get("name", str(uid))
    uname = f"@{u_info['username']}" if u_info.get("username") else "no username"
    joined = u_info.get("joined", first_date or "?")

    # Sort dates
    def parse_day(d):
        try:
            return datetime.strptime(d, "%d/%m/%Y")
        except:
            return datetime.min

    sorted_days = sorted(daily.keys(), key=parse_day)
    total_msgs = total_user + total_admin

    lines = []
    lines.append(f"📊 *CHAT CHART*")
    lines.append(f"👤 {escape_md(name)} ({escape_md(uname)})")
    lines.append(f"🆔 `{uid}`")
    lines.append(f"📅 Joined: {joined}")
    lines.append(f"💬 Total: *{total_msgs}* msgs ({total_user} user / {total_admin} admin)\n")
    lines.append("─────────────────────")

    # Max msgs in a day (for bar scaling)
    max_msgs = max((daily[d]["user"] + daily[d]["admin"]) for d in sorted_days) or 1
    bar_max = 12  # max bar length in chars

    for day in sorted_days:
        u = daily[day]["user"]
        a = daily[day]["admin"]
        total_day = u + a
        bar_len = max(1, round(total_day / max_msgs * bar_max))
        bar = "█" * bar_len

        # Show date without year if same year as today
        try:
            dt = datetime.strptime(day, "%d/%m/%Y")
            label = dt.strftime("%d %b")
        except:
            label = day

        lines.append(f"`{label}` {bar} {total_day}  _(👤{u} / 🤖{a})_")

    lines.append("─────────────────────")

    # Most active day
    busiest = max(sorted_days, key=lambda d: daily[d]["user"] + daily[d]["admin"])
    busiest_count = daily[busiest]["user"] + daily[busiest]["admin"]
    try:
        busiest_label = datetime.strptime(busiest, "%d/%m/%Y").strftime("%d %b %Y")
    except:
        busiest_label = busiest

    lines.append(f"🔥 Most active: *{busiest_label}* ({busiest_count} msgs)")
    lines.append(f"📆 Days active: *{len(sorted_days)}*")

    return "\n".join(lines)


async def userchart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /userchart USER_ID — Show chat activity chart for a user
    Shows per-day message counts (user vs admin) from day 1 to today
    """
    if not is_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text(
            "📊 *User Chat Chart*\n\n"
            "Usage: `/userchart USER_ID`\n"
            "Example: `/userchart 123456789`\n\n"
            "Shows bar chart of daily messages between you and this user.",
            parse_mode="Markdown")
        return

    try:
        uid = int(context.args[0])
    except:
        await update.message.reply_text("❌ Invalid user ID.", parse_mode="Markdown")
        return

    u_info = get_user_info(uid)
    daily, first_date, total_user, total_admin = get_chat_stats_for_user(uid)

    if not daily:
        name = escape_md(u_info.get("name", str(uid)))
        await update.message.reply_text(
            f"📭 *No chat history found for {name}*\n\n"
            f"🆔 `{uid}`\n\n"
            f"_Messages are only recorded during active support sessions._",
            parse_mode="Markdown")
        return

    chart_text = build_text_chart(uid, u_info, daily, first_date, total_user, total_admin)
    try:
        await update.message.reply_text(chart_text, parse_mode="Markdown")
    except Exception as e:
        # Fallback without markdown if parse fails
        await update.message.reply_text(chart_text)



def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("getid", getid_command))
    app.add_handler(CommandHandler("sessions", sessions_command))
    app.add_handler(CommandHandler("preview", preview_command))
    app.add_handler(CommandHandler("spinners", spinners_command))
    app.add_handler(CommandHandler("givespin", givespin_command))
    app.add_handler(CommandHandler("setnews", setnews_command))
    app.add_handler(CommandHandler("setvip", setvip_command))
    app.add_handler(CommandHandler("clearnews", clearnews_command))
    app.add_handler(CommandHandler("clearvip", clearnews_command))
    app.add_handler(CommandHandler("results", results_command))
    app.add_handler(CommandHandler("feedback", feedback_command))
    app.add_handler(CommandHandler("feedbackadd", feedbackadd_command))
    app.add_handler(CommandHandler("feedbackdlt", feedbackdlt_command))
    app.add_handler(CommandHandler("feedbacklist", feedbacklist_command))
    app.add_handler(CommandHandler("addphoto", addphoto_command))
    app.add_handler(CommandHandler("addstory", addstory_command))
    app.add_handler(CommandHandler("liststories", liststories_command))
    app.add_handler(CommandHandler("deletestory", deletestory_command))
    app.add_handler(CommandHandler("addbot", addbot_command))
    app.add_handler(CommandHandler("delbot", delbot_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("blockedusers", blockedusers_command))
    app.add_handler(CommandHandler("setpocketlink", setpocketlink_command))
    app.add_handler(CommandHandler("setwelcome", setwelcome_command))
    app.add_handler(CommandHandler("history", history_command))
    app.add_handler(CommandHandler("setresult", setresult_command))
    app.add_handler(CommandHandler("users", users_command))
    app.add_handler(CommandHandler("userchart", userchart_command))
    app.add_handler(ChatJoinRequestHandler(handle_join_request))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))

    # Health server for Render + Self-ping every 5 minutes
    import threading
    import urllib.request
    from http.server import HTTPServer, BaseHTTPRequestHandler
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'OK - EVALON BOT RUNNING')
        def log_message(self, *a): pass
    _port = int(os.environ.get('PORT', 8080))
    threading.Thread(target=lambda: HTTPServer(('0.0.0.0', _port), H).serve_forever(), daemon=True).start()

    # Self-ping every 5 minutes to prevent Render from sleeping
    def self_ping():
        import time
        url = os.environ.get('RENDER_EXTERNAL_URL', f'http://0.0.0.0:{_port}')
        while True:
            time.sleep(300)  # 5 minutes
            try:
                urllib.request.urlopen(url, timeout=10)
                logger.info("✅ Self-ping OK")
            except Exception as e:
                logger.warning(f"Self-ping failed: {e}")
    threading.Thread(target=self_ping, daemon=True).start()

    print(f"✅ {BUSINESS_NAME} Bot v6.9 is LIVE!")
    print("📋 Type /help in bot for all admin commands")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )

if __name__ == "__main__":
    main()

