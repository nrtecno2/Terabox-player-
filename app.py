"""
app.py
Telegram Terabox Downloader Bot
- Flask webhook (Render par deploy karne ke liye)
- pyTelegramBotAPI (telebot)
- Force channel-join gate
- Referral system: 3 free files, uske baad 2 referrals se unlimited
- Har download private log channel me bhi save hota hai
"""

import os
import re
import logging

import telebot
from telebot import types
from flask import Flask, request

import db
import terabox

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("teraboxbot")

# telebot apni background threads me jo bhi error deta hai wo iske bina
# console/Render logs me nazar nahi aata - isliye explicitly enable kar rahe hain.
telebot.logger.setLevel(logging.DEBUG)

# ---------------- Environment variables (Render me set karein) ----------------
BOT_TOKEN = os.environ["BOT_TOKEN"]                     # BotFather se mila token
CHANNEL_USERNAME = os.environ.get("CHANNEL_USERNAME", "nrtecno2")  # bina @ ke
PRIVATE_CHANNEL_ID = int(os.environ["PRIVATE_CHANNEL_ID"])  # e.g. -1001234567890

# WEBHOOK_HOST manually set karne ki zaroorat nahi hai.
# Render har service ke liye khud RENDER_EXTERNAL_URL environment variable
# set karta hai (e.g. https://your-app.onrender.com) - hum wahi use karenge.
# Agar kisi wajah se wo na mile, to manually WEBHOOK_HOST set kar sakte hain (optional).
WEBHOOK_HOST = os.environ.get("WEBHOOK_HOST") or os.environ.get("RENDER_EXTERNAL_URL")
FREE_LIMIT = int(os.environ.get("FREE_LIMIT", "3"))
REQUIRED_REFERRALS = int(os.environ.get("REQUIRED_REFERRALS", "2"))
MAX_FILE_MB = int(os.environ.get("MAX_FILE_MB", "1900"))  # Telegram bot upload limit ~2GB (self-hosted API) / 50MB (cloud API default)

CHANNEL_LINK = f"https://t.me/{CHANNEL_USERNAME}"
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
app = Flask(__name__)

db.init_db()


def auto_set_webhook():
    """App start hote hi khud webhook set kar deta hai - manual step ki zaroorat nahi."""
    if not WEBHOOK_HOST:
        log.warning(
            "WEBHOOK_HOST na RENDER_EXTERNAL_URL mila na WEBHOOK_HOST env var - "
            "webhook set nahi ho paayega. /set_webhook route se manually try kar sakte hain."
        )
        return
    try:
        bot.remove_webhook()
        url = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
        ok = bot.set_webhook(url=url)
        log.info(f"Webhook auto-set: {ok} -> {url}")
    except Exception as e:
        log.error(f"Webhook auto-set fail hua: {e}")


auto_set_webhook()


# ---------------------------- Helper functions ----------------------------

def is_member(user_id: int) -> bool:
    try:
        member = bot.get_chat_member(f"@{CHANNEL_USERNAME}", user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception as e:
        log.warning(f"get_chat_member failed: {e}")
        return False


def join_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK))
    kb.add(types.InlineKeyboardButton("✅ Verify", callback_data="verify"))
    return kb


def referral_link(user_id: int) -> str:
    bot_username = bot.get_me().username
    return f"https://t.me/{bot_username}?start=ref_{user_id}"


def send_join_prompt(chat_id):
    bot.send_message(
        chat_id,
        f"Is bot ko use karne ke liye pehle hamara channel @{CHANNEL_USERNAME} join karein, "
        f"phir neeche diye gaye *Verify* button par click karein.",
        parse_mode="Markdown",
        reply_markup=join_keyboard(),
    )


def send_ask_link(chat_id):
    bot.send_message(
        chat_id,
        "Ab mujhe apna *Terabox* share link bhejein, main us se file nikal kar aapko bhej dunga.",
        parse_mode="Markdown",
    )


# ------------------------------- Handlers -------------------------------

@bot.message_handler(commands=["start"])
def handle_start(message):
    try:
        user_id = message.from_user.id
        username = message.from_user.username or ""

        referred_by = None
        parts = message.text.split(maxsplit=1)
        if len(parts) > 1 and parts[1].startswith("ref_"):
            try:
                ref_id = int(parts[1].replace("ref_", ""))
                if ref_id != user_id:
                    referred_by = ref_id
            except ValueError:
                pass

        is_new = db.create_user_if_not_exists(user_id, username, referred_by)
        log.info(f"/start from user_id={user_id} username={username} is_new={is_new}")

        if not is_member(user_id):
            send_join_prompt(message.chat.id)
            return

        db.set_joined(user_id)

        bot.send_message(
            message.chat.id,
            "🎉 Welcome! Aap already channel member hain.\n\n"
            "Ab mujhe apna Terabox link bhejein.",
        )
    except Exception:
        log.exception(f"handle_start me error aayi, message: {message}")
        try:
            bot.send_message(message.chat.id, "⚠️ Kuch error aayi, thodi der baad dobara try karein.")
        except Exception:
            pass


@bot.callback_query_handler(func=lambda c: c.data == "verify")
def handle_verify(call):
    try:
        user_id = call.from_user.id
        log.info(f"verify clicked by user_id={user_id}")
        if is_member(user_id):
            user = db.get_user(user_id)
            was_joined = user["joined_channel"] if user else 0

            db.set_joined(user_id)

            # Referral credit sirf ek baar, jab user pehli baar verify hota hai
            if user and not was_joined and user.get("referred_by"):
                db.increment_referral(user["referred_by"])
                try:
                    bot.send_message(
                        user["referred_by"],
                        "🎉 Aapke referral link se ek naya user verify hua hai!",
                    )
                except Exception:
                    pass

            bot.answer_callback_query(call.id, "✅ Verified!")
            bot.edit_message_text(
                "✅ Verification successful! Ab mujhe apna Terabox link bhejein.",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
            )
        else:
            bot.answer_callback_query(call.id, "❌ Aapne abhi channel join nahi kiya hai.", show_alert=True)
    except Exception:
        log.exception(f"handle_verify me error aayi, call: {call}")
        try:
            bot.answer_callback_query(call.id, "⚠️ Kuch error aayi, dobara try karein.", show_alert=True)
        except Exception:
            pass


@bot.message_handler(func=lambda m: m.text and terabox.is_terabox_link(m.text))
def handle_terabox_link(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    if not is_member(user_id):
        send_join_prompt(chat_id)
        return

    user = db.get_user(user_id)
    if not user:
        db.create_user_if_not_exists(user_id, message.from_user.username or "")
        user = db.get_user(user_id)

    if not db.can_use(user_id, FREE_LIMIT, REQUIRED_REFERRALS):
        link = referral_link(user_id)
        bot.send_message(
            chat_id,
            "🚫 Aapki *3 free files* khatam ho chuki hain।\n\n"
            f"👉 Unlimited use ke liye *{REQUIRED_REFERRALS} users* ko refer karein.\n\n"
            f"Aapka referral link:\n{link}\n\n"
            "Jaise hi 2 log is link se bot start aur verify karte hain, aapko unlimited access mil jaayega.",
            parse_mode="Markdown",
        )
        return

    processing = bot.send_message(chat_id, "⏳ Link check ho raha hai, please wait...")

    try:
        files = terabox.get_terabox_files(message.text.strip())
    except Exception as e:
        bot.edit_message_text(f"❌ {e}", chat_id, processing.message_id)
        return

    for f in files:
        size_mb = f["size"] / (1024 * 1024)
        if size_mb > MAX_FILE_MB:
            bot.send_message(chat_id, f"⚠️ {f['name']} size limit se bada hai, skip kiya gaya.")
            continue

        local_path = f"/tmp/{f['fs_id']}_{re.sub(r'[^A-Za-z0-9_.-]', '_', f['name'])}"
        try:
            bot.edit_message_text(f"⬇️ Downloading: {f['name']} ...", chat_id, processing.message_id)
            terabox.download_file(f["dlink"], local_path, max_bytes=MAX_FILE_MB * 1024 * 1024)

            bot.edit_message_text(f"⬆️ Uploading: {f['name']} ...", chat_id, processing.message_id)
            with open(local_path, "rb") as vid:
                sent = bot.send_video(
                    PRIVATE_CHANNEL_ID,
                    vid,
                    caption=f"{f['name']}\nRequested by: {message.from_user.first_name} ({user_id})",
                    supports_streaming=True,
                )
            # Private channel se user ko copy karo (forward tag nahi dikhega)
            bot.copy_message(chat_id, PRIVATE_CHANNEL_ID, sent.message_id)

            db.increment_files_used(user_id)
        except Exception as e:
            bot.send_message(chat_id, f"❌ {f['name']} process karte waqt error aayi: {e}")
        finally:
            if os.path.exists(local_path):
                os.remove(local_path)

    try:
        bot.delete_message(chat_id, processing.message_id)
    except Exception:
        pass

    user = db.get_user(user_id)
    remaining = max(0, FREE_LIMIT - user["files_used"])
    if user["files_used"] >= FREE_LIMIT and user["referral_count"] < REQUIRED_REFERRALS:
        link = referral_link(user_id)
        bot.send_message(
            chat_id,
            "✅ Aapki 3 free files khatam ho gayi hain।\n\n"
            f"Unlimited use ke liye {REQUIRED_REFERRALS} users ko refer karein:\n{link}",
        )
    elif remaining > 0:
        bot.send_message(chat_id, f"✅ Done! Aapke paas abhi {remaining} free files bachi hain.")


@bot.message_handler(func=lambda m: True, content_types=["text"])
def handle_other_text(message):
    if not is_member(message.from_user.id):
        send_join_prompt(message.chat.id)
        return
    send_ask_link(message.chat.id)


# ------------------------------- Flask routes -------------------------------

@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    json_str = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200


@app.route("/", methods=["GET"])
def index():
    return "Terabox Telegram Bot is running.", 200


@app.route("/set_webhook", methods=["GET"])
def set_webhook():
    if not WEBHOOK_HOST:
        return {"error": "WEBHOOK_HOST/RENDER_EXTERNAL_URL nahi mila"}, 400
    bot.remove_webhook()
    ok = bot.set_webhook(url=f"{WEBHOOK_HOST}{WEBHOOK_PATH}")
    return {"webhook_set": ok, "url": f"{WEBHOOK_HOST}{WEBHOOK_PATH}"}, 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
