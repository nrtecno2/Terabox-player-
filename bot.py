import os
import re
import json
import requests
import hashlib
from flask import Flask, request
from telebot import TeleBot, types

# ========== CONFIGURATION ==========
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")  # e.g., -1001234567890
PRIVATE_CHANNEL_ID = os.environ.get("PRIVATE_CHANNEL_ID")  # e.g., -1009876543210
CHANNEL_USERNAME = os.environ.get("CHANNEL_USERNAME", "nrtecno2")  # without @
ADMIN_ID = os.environ.get("ADMIN_ID")

bot = TeleBot(BOT_TOKEN)
app = Flask(__name__)

# In-memory storage (use Redis/DB for production)
users_data = {}
referrals_data = {}

# ========== FILE STORAGE ==========
DATA_FILE = "bot_data.json"

def load_data():
    global users_data, referrals_data
    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            users_data = data.get("users", {})
            referrals_data = data.get("referrals", {})
    except FileNotFoundError:
        pass

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump({"users": users_data, "referrals": referrals_data}, f)

load_data()

# ========== TERABOX DOWNLOADER ==========
def get_terabox_download_url(terabox_url):
    """
    TeraBox direct download without API
    Uses web scraping approach
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.0'
        }

        # Extract short URL or file ID
        if "teraboxapp.com" in terabox_url or "terabox.com" in terabox_url or "1024terabox" in terabox_url:
            # Get the page content
            session = requests.Session()
            response = session.get(terabox_url, headers=headers, timeout=30, allow_redirects=True)

            # Try to extract direct download link from page
            # Look for video/audio direct links
            patterns = [
                r'"dlink":"([^"]+)"',
                r'"download_url":"([^"]+)"',
                r'https://[^"\s]+terabox[^"\s]*\.(mp4|mkv|avi|mov)',
                r'https://[^"\s]+d\.terabox[^"\s]*',
                r'"url":"(https://[^"]+terabox[^"]+)"',
                r'"play_url":"([^"]+)"',
                r'"link":"(https://[^"]+)"'
            ]

            for pattern in patterns:
                matches = re.findall(pattern, response.text)
                if matches:
                    url = matches[0].replace('\\/', '/').replace('\/', '/')
                    if url.startswith('http'):
                        return url

            # Alternative: Extract file metadata and construct download
            shareid = re.search(r'"shareid":(\d+)', response.text)
            uk = re.search(r'"uk":(\d+)', response.text)
            sign = re.search(r'"sign":"([^"]+)"', response.text)

            if shareid and uk:
                shareid_val = shareid.group(1)
                uk_val = uk.group(1)

                # Try to get download link via public endpoints
                shorturl = terabox_url.split('/')[-1].split('?')[0]
                meta_url = f"https://www.terabox.com/share/list?app_id=250528&shorturl={shorturl}&root=1"
                meta_resp = session.get(meta_url, headers=headers, timeout=10)

                if meta_resp.status_code == 200:
                    try:
                        meta_data = meta_resp.json()
                        if meta_data.get('list'):
                            file_info = meta_data['list'][0]
                            dlink = file_info.get('dlink')
                            if dlink:
                                return dlink
                    except:
                        pass

            # Try to find any media URL in the page
            media_pattern = r'(https://[^"\s<>]+\.(?:mp4|mkv|avi|mov|webm)[^"\s<>]*)'
            media_matches = re.findall(media_pattern, response.text)
            if media_matches:
                return media_matches[0].replace('\/', '/')

            return None
    except Exception as e:
        print(f"Error getting TeraBox link: {e}")
        return None

# ========== KEYBOARD MARKUPS ==========
def get_join_channel_markup():
    markup = types.InlineKeyboardMarkup()
    join_btn = types.InlineKeyboardButton("📢 Channel Join Karein", url=f"https://t.me/{CHANNEL_USERNAME}")
    verify_btn = types.InlineKeyboardButton("✅ Verify Karein", callback_data="verify_channel")
    markup.add(join_btn)
    markup.add(verify_btn)
    return markup

def get_main_markup():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📎 TeraBox Link Bhejein", callback_data="send_link"))
    return markup

def get_referral_markup(user_id):
    markup = types.InlineKeyboardMarkup()
    ref_link = users_data.get(str(user_id), {}).get("referral_link", "")
    if ref_link:
        markup.add(types.InlineKeyboardButton("🔗 Referral Link Copy Karein", url=ref_link))
    return markup

# ========== BOT HANDLERS ==========
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = str(message.from_user.id)
    user_name = message.from_user.first_name or "User"
    args = message.text.split()

    # Check if user came via referral
    if len(args) > 1 and args[1].startswith('ref'):
        referrer_id = args[1].replace('ref', '')
        if referrer_id != user_id and user_id not in referrals_data.get(referrer_id, []):
            if referrer_id not in referrals_data:
                referrals_data[referrer_id] = []
            referrals_data[referrer_id].append(user_id)
            save_data()

            # Notify referrer
            ref_count = len(referrals_data.get(referrer_id, []))
            try:
                bot.send_message(int(referrer_id), f"🎉 Naya referral mila! Total: {ref_count}/2")

                if ref_count >= 2:
                    users_data[referrer_id]["unlimited"] = True
                    save_data()
                    bot.send_message(int(referrer_id), 
                        "🎊 Badhai ho! Aapko ab UNLIMITED downloads ki suvidha mil gayi hai!\n\n"
                        "Aap ab jitni chahein utni files download kar sakte hain!"
                    )
            except:
                pass

    # Initialize user
    if user_id not in users_data:
        users_data[user_id] = {
            "joined": False,
            "downloads": 0,
            "unlimited": False,
            "referral_link": f"https://t.me/{bot.get_me().username}?start=ref{user_id}",
            "user_name": user_name
        }
        save_data()

    # Check if already joined
    if users_data[user_id].get("joined", False):
        welcome_msg = (
            f"👋 Welcome back {user_name}!\n\n"
            "📥 Mujhe TeraBox link bhejein, main aapko file download karke dunga."
        )
        if users_data[user_id].get("unlimited", False):
            welcome_msg += "\n\n✨ Aapke paas UNLIMITED access hai!"
        else:
            remaining = 3 - users_data[user_id].get("downloads", 0)
            welcome_msg += f"\n\n📊 Bachi hui downloads: {remaining}/3"

        bot.send_message(user_id, welcome_msg, reply_markup=get_main_markup())
        return

    # Ask to join channel
    welcome_text = (
        f"👋 Namaste {user_name}!\n\n"
        f"🤖 Main TeraBox Video Downloader Bot hoon.\n\n"
        f"📢 Bot use karne ke liye, kripaya pehle hamare channel join karein:\n"
        f"👉 @{CHANNEL_USERNAME}\n\n"
        f"✅ Channel join karne ke baad 'Verify' button dabayein."
    )
    bot.send_message(user_id, welcome_text, reply_markup=get_join_channel_markup())

@bot.callback_query_handler(func=lambda call: call.data == "verify_channel")
def verify_channel(call):
    user_id = str(call.from_user.id)

    try:
        # Check if user is member of channel
        member = bot.get_chat_member(f"@{CHANNEL_USERNAME}", call.from_user.id)

        if member.status in ['member', 'administrator', 'creator']:
            users_data[user_id]["joined"] = True
            save_data()

            bot.edit_message_text(
                "✅ Verification successful!\n\n"
                "📥 Ab aap TeraBox link bhej sakte hain. Main usse download karke aapko bhej dunga.",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=get_main_markup()
            )
        else:
            bot.answer_callback_query(call.id, "❌ Aapne abhi tak channel join nahi kiya hai!")
    except Exception as e:
        bot.answer_callback_query(call.id, "❌ Verification mein error. Dobara try karein.")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = str(message.from_user.id)

    # Check if user exists
    if user_id not in users_data:
        start_command(message)
        return

    # Check if joined
    if not users_data[user_id].get("joined", False):
        bot.send_message(
            user_id,
            "⚠️ Kripaya pehle channel join karein!",
            reply_markup=get_join_channel_markup()
        )
        return

    # Check download limit
    downloads = users_data[user_id].get("downloads", 0)
    unlimited = users_data[user_id].get("unlimited", False)

    if downloads >= 3 and not unlimited:
        ref_link = users_data[user_id].get("referral_link", "")
        ref_count = len(referrals_data.get(user_id, []))

        msg = (
            f"⚠️ Aapki 3 free downloads khatam ho gayi hain!\n\n"
            f"🎁 UNLIMITED access ke liye 2 users ko refer karein.\n\n"
            f"📊 Abhi tak ke referrals: {ref_count}/2\n\n"
            f"🔗 Aapka referral link:\n`{ref_link}`"
        )
        bot.send_message(user_id, msg, parse_mode="Markdown", reply_markup=get_referral_markup(user_id))
        return

    # Check if message is TeraBox link
    text = message.text.strip()
    terabox_pattern = r'(https?://(?:www\.)?(?:terabox|1024terabox|freeterabox|teraboxapp)\.[^\s]+)'

    if re.match(terabox_pattern, text, re.IGNORECASE):
        # Process TeraBox link
        process_terabox_link(message, text)
    else:
        bot.send_message(
            user_id,
            "❌ Kripaya valid TeraBox link bhejein.\n\n"
            "Example: https://teraboxapp.com/s/xxxxx\n"
            "Ya: https://1024terabox.com/s/xxxxx"
        )

def process_terabox_link(message, url):
    user_id = str(message.from_user.id)

    # Send processing message
    processing_msg = bot.send_message(user_id, "⏳ Aapka link process ho raha hai...")

    try:
        # Get download URL
        download_url = get_terabox_download_url(url)

        if not download_url:
            bot.edit_message_text(
                "❌ Download link generate nahi ho paya.\n"
                "Kripaya check karein ki link valid hai ya nahi, ya phir link expire to nahi hua.",
                chat_id=user_id,
                message_id=processing_msg.message_id
            )
            return

        # Download file
        bot.edit_message_text(
            "⬇️ TeraBox se file download ho rahi hai...",
            chat_id=user_id,
            message_id=processing_msg.message_id
        )

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

        session = requests.Session()
        response = session.get(download_url, headers=headers, stream=True, timeout=300)
        file_size = int(response.headers.get('content-length', 0))

        # Check file size (Telegram limit ~2GB for bots)
        if file_size > 2 * 1024 * 1024 * 1024:
            bot.edit_message_text(
                "❌ File bahut badi hai (max 2GB supported).",
                chat_id=user_id,
                message_id=processing_msg.message_id
            )
            return

        # Save temporarily
        filename = url.split('/')[-1].split('?')[0] or "terabox_file"
        if '.' not in filename:
            filename += ".mp4"

        temp_path = f"/tmp/terabox_{user_id}_{filename}"

        downloaded = 0
        with open(temp_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)

        # Upload to private channel
        bot.edit_message_text(
            "📤 Private channel par upload ho raha hai...",
            chat_id=user_id,
            message_id=processing_msg.message_id
        )

        # Send to private channel
        with open(temp_path, 'rb') as f:
            if filename.endswith(('.mp4', '.avi', '.mkv', '.mov', '.webm')):
                sent_msg = bot.send_video(
                    PRIVATE_CHANNEL_ID, 
                    f, 
                    caption=f"📥 From: {users_data[user_id].get('user_name', 'Unknown')}\n🆔 User ID: {user_id}",
                    supports_streaming=True
                )
            else:
                sent_msg = bot.send_document(
                    PRIVATE_CHANNEL_ID, 
                    f, 
                    caption=f"📥 From: {users_data[user_id].get('user_name', 'Unknown')}\n🆔 User ID: {user_id}",
                    filename=filename
                )

        # Forward to user from private channel
        bot.edit_message_text(
            "📤 Aapko file bheji ja rahi hai...",
            chat_id=user_id,
            message_id=processing_msg.message_id
        )

        bot.forward_message(user_id, PRIVATE_CHANNEL_ID, sent_msg.message_id)

        # Update download count
        users_data[user_id]["downloads"] = users_data[user_id].get("downloads", 0) + 1
        save_data()

        # Check if limit reached
        new_count = users_data[user_id]["downloads"]
        if new_count >= 3 and not users_data[user_id].get("unlimited", False):
            ref_link = users_data[user_id].get("referral_link", "")
            bot.send_message(
                user_id,
                f"⚠️ Yeh aapki 3rd free download thi!\n\n"
                f"🎁 UNLIMITED access ke liye 2 users ko refer karein!\n\n"
                f"🔗 Aapka referral link:\n`{ref_link}`",
                parse_mode="Markdown",
                reply_markup=get_referral_markup(user_id)
            )
        else:
            remaining = "Unlimited" if users_data[user_id].get("unlimited", False) else 3 - new_count
            bot.send_message(
                user_id,
                f"✅ Download complete!\n\n"
                f"📊 Bachi hui downloads: {remaining}\n\n"
                f"📥 Aur links bhejne ke liye ready hain!",
                reply_markup=get_main_markup()
            )

        # Cleanup
        if os.path.exists(temp_path):
            os.remove(temp_path)

    except Exception as e:
        print(f"Error: {e}")
        bot.edit_message_text(
            f"❌ Error aa gaya: {str(e)}\n\nKripaya baad mein try karein.",
            chat_id=user_id,
            message_id=processing_msg.message_id
        )
        # Cleanup on error
        temp_path = f"/tmp/terabox_{user_id}_"
        for f in os.listdir('/tmp'):
            if f.startswith(f"terabox_{user_id}_"):
                try:
                    os.remove(f'/tmp/{f}')
                except:
                    pass

# ========== FLASK WEBHOOK ==========
@app.route('/' + BOT_TOKEN, methods=['POST'])
def webhook():
    json_string = request.get_data().decode('utf-8')
    update = types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return 'OK', 200

@app.route('/')
def index():
    return 'Bot is running!'

@app.route('/health')
def health():
    return 'OK', 200

# Set webhook (run once)
def set_webhook():
    webhook_url = os.environ.get("WEBHOOK_URL")  # e.g., https://your-app.onrender.com
    if webhook_url:
        try:
            bot.remove_webhook()
            bot.set_webhook(url=webhook_url + '/' + BOT_TOKEN)
            print(f"Webhook set: {webhook_url + '/' + BOT_TOKEN}")
        except Exception as e:
            print(f"Webhook error: {e}")

if __name__ == '__main__':
    set_webhook()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
