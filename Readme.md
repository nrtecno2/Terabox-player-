TeraBox Downloader Telegram Bot
Features
✅ TeraBox video/file download without API
✅ Channel join verification (@nrtecno2)
✅ Referral system (2 referrals = unlimited)
✅ Files uploaded to private Telegram channel
✅ Webhook + Flask + pyTelegramBotAPI
✅ Deploy on Render
Environment Variables (Render Dashboard)
Variable
Description
Example
BOT_TOKEN
Your BotFather token
123456:ABC-DEF...
CHANNEL_USERNAME
Channel username without @
nrtecno2
CHANNEL_ID
Channel ID (must be admin)
-1001234567890
PRIVATE_CHANNEL_ID
Private channel for uploads
-1009876543210
WEBHOOK_URL
Your Render app URL
https://your-app.onrender.com
PORT
Render port
10000
Setup Steps
1. Create Telegram Bot
Go to @BotFather
Create new bot, copy token
Set bot privacy: DISABLE (so it can read messages)
2. Create Channels
Create public channel: @nrtecno2 (force join)
Create private channel for file storage
Add bot as ADMIN in BOTH channels
3. Get Channel IDs
Forward a message from channel to @userinfobot
Or use: @RawDataBot to get ID
Format: -1001234567890
4. Deploy on Render
Connect GitHub repo
Deploy!
5. Set Webhook
Bot auto-sets webhook on startup
Or manually: https://api.telegram.org/bot<TOKEN>/setWebhook?url=<URL>/<TOKEN>
Important Notes
⚠️ TeraBox Download Limitation: Since we don't use official API, the download method uses web scraping. Some links may not work if TeraBox changes their website structure.
⚠️ File Size: Telegram bot limit is 2GB per file.
⚠️ Data Persistence: Bot uses JSON file for storage. On Render free tier, the filesystem resets on restart. For production, use Redis/PostgreSQL.
File Structure
├── bot.py              # Main bot code
├── requirements.txt    # Dependencies
├── render.yaml         # Render config
└── bot_data.json       # User data (auto-created)
Commands
/start - Start bot and verify channel
Send any TeraBox link - Download file
Referral System
User gets 3 free downloads
After 3rd download, bot asks for 2 referrals
Unique referral link generated per user
2 successful referrals = unlimited downloads
