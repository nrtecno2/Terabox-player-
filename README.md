# Terabox Telegram Downloader Bot

Force-join + referral system wala Terabox video downloader bot.
Flask webhook + pyTelegramBotAPI, GitHub se Render par deploy karne ke liye ready.

## ⚠️ Zaroori disclaimer

Ye bot Terabox ki **website jo public endpoint use karti hai** wahi call karta hai (koi paid/private
API nahi), isliye Terabox jab chahe apna structure change kar sakta hai aur extraction tab tak toot
sakta hai jab tak `terabox.py` update na kiya jaaye. Sirf apne khud ke ya share-permission wale
content ke liye use karein — Terabox ke Terms of Service ka dhyan rakhein.

## Features

- `/start` par force channel join check
- "Verify" button se membership confirm
- Terabox link se video/file fetch karke user ko bhejta hai
- Har file private log channel me bhi save hoti hai
- Referral system: 3 free files, uske baad 2 successful referrals se unlimited

## Files

- `app.py` – Flask webhook + bot logic
- `terabox.py` – Terabox se file/dlink extraction
- `db.py` – SQLite storage (users, referral, usage count)
- `requirements.txt`, `Procfile`

## Setup steps

### 1. Telegram taraf se

1. [@BotFather](https://t.me/BotFather) se bot banayein → `BOT_TOKEN` milega.
2. Apna public channel (`nrtecno2`) me bot ko **admin** banayein (member check karne ke liye zaroori hai).
3. Ek private channel banayein jahan saari downloaded files log hongi. Bot ko is channel me bhi admin banayein.
4. Private channel ki **chat id** nikalne ke liye: channel me koi message forward karke
   [@JsonDumpBot](https://t.me/JsonDumpBot) ko bhejein, ya `getUpdates` API se `chat.id` nikalein
   (usually `-100` se start hoti hai).

### 2. GitHub par push karein

Is poore folder ko apne GitHub repo me push kar dein.

### 3. Render par deploy

1. [render.com](https://render.com) par **New → Web Service** banayein, apna GitHub repo connect karein.
2. **Build Command:** `pip install -r requirements.txt`
3. **Start Command:** `gunicorn app:app --bind 0.0.0.0:$PORT --timeout 120`
4. **Environment Variables** (Render dashboard → Environment):

   | Key | Value / Example |
   |---|---|
   | `BOT_TOKEN` | BotFather se mila token |
   | `CHANNEL_USERNAME` | `nrtecno2` (bina @ ke) |
   | `PRIVATE_CHANNEL_ID` | `-1001234567890` |
   | `WEBHOOK_HOST` | `https://your-app-name.onrender.com` (deploy ke baad Render jo URL de) |
   | `FREE_LIMIT` | `3` |
   | `REQUIRED_REFERRALS` | `2` |
   | `MAX_FILE_MB` | `1900` |

5. Deploy hone ke baad, ek baar browser me ye URL open karein taaki webhook set ho jaaye:

   ```
   https://your-app-name.onrender.com/set_webhook
   ```

   Response me `"webhook_set": true` aana chahiye.

### 4. Test

Apne bot ko Telegram par `/start` bhejein, join-verify flow follow karein, phir koi Terabox share link bhejein.

## Referral flow

- Naya user jab kisi ke referral link (`?start=ref_<id>`) se aakar **channel verify** karta hai,
  tabhi referrer ko 1 count milta hai (fake/bina-join count nahi hota).
- 3 free files ke baad, agar referral count `REQUIRED_REFERRALS` se kam hai, bot user ko uska
  unique referral link bhejta hai.
- 2 verified referrals ke baad us user ke liye limit hat jaati hai (unlimited).

## Limitations / aage improve kar sakte hain

- Render free tier ka disk ephemeral hai — restart/redeploy par SQLite data reset ho sakta hai.
  Zyada reliability ke liye Render ka free Postgres add-on use kar sakte hain.
- Standard Telegram Bot API cloud server ki upload limit ~50MB hoti hai; bade video ke liye
  aapko apna local Bot API server (`telegram-bot-api`) self-host karna padega (limit ~2GB tak).
- Terabox scraping endpoint kabhi bhi change ho sakta hai — agar extraction fail ho,
  `terabox.py` me endpoint/params update karne honge.
  
