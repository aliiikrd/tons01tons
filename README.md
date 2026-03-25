# Telegram Media Downloader Bot

### @AllSocialSaversbot | Developed by [@whykurds](https://t.me/whykurds)

A Telegram bot that downloads videos and images from **1000+ websites** (YouTube, Instagram, TikTok, Twitter/X, Facebook, Reddit, Pinterest, and more) and sends them directly to the user -- after watching a short **Monetag** ad via a Telegram Mini App.

---

## Table of Contents

- [How It Works](#how-it-works)
- [Architecture](#architecture)
- [Repository Structure](#repository-structure)
- [Prerequisites](#prerequisites)
- [Setup Guide](#setup-guide)
  - [Step 1: Clone the Repository](#step-1-clone-the-repository)
  - [Step 2: Get Your Monetag Zone ID](#step-2-get-your-monetag-zone-id)
  - [Step 3: Deploy the Mini App to Vercel](#step-3-deploy-the-mini-app-to-vercel)
  - [Step 4: Configure & Run the Bot Locally](#step-4-configure--run-the-bot-locally)
  - [Step 5: Deploy the Bot to a Free Platform](#step-5-deploy-the-bot-to-a-free-platform)
  - [Step 6: Set the Mini App URL in BotFather](#step-6-set-the-mini-app-url-in-botfather)
- [Configuration Reference](#configuration-reference)
- [Monetag Integration Guide](#monetag-integration-guide)
- [Supported Sites](#supported-sites)
- [Troubleshooting](#troubleshooting)
- [Notes & Limitations](#notes--limitations)
- [Credits](#credits)

---

## How It Works

```
User sends link  -->  Bot saves link in memory  -->  Bot shows "Watch Ad" button
       |
       v
User taps button  -->  Mini App opens in Telegram WebView
       |
       v
Mini App shows Monetag Rewarded Interstitial ad
       |
       v
Ad completes  -->  Mini App sends "ad_completed" to bot  -->  Mini App closes
       |
       v
Bot receives signal  -->  Downloads media with yt-dlp  -->  Sends file to user
```

## Architecture

| Component | Technology | Hosting |
|-----------|-----------|---------|
| **Bot** | Python + python-telegram-bot + yt-dlp | PythonAnywhere / TeleBotHost / any VPS |
| **Mini App** | HTML + CSS + JS + Telegram WebApp SDK + Monetag SDK | Vercel (free) |
| **Storage** | In-memory Python dictionary | No database needed |

---

## Repository Structure

```
telegram-downloader-bot/
├── bot/
│   ├── bot.py              # Main bot logic (extensively commented)
│   └── requirements.txt    # Python dependencies
├── mini_app/
│   ├── index.html          # Mini App HTML (Telegram WebApp + Monetag SDK)
│   ├── style.css           # Modern CSS (glassmorphism, animations, responsive)
│   ├── script.js           # Ad logic (preload, show, sendData, close)
│   └── vercel.json         # Vercel static deployment config
└── README.md               # This file - deployment guide
```

---

## Prerequisites

Before you begin, make sure you have:

| Requirement | Where to Get It |
|-------------|----------------|
| **Python 3.9+** | [python.org](https://www.python.org/downloads/) |
| **Telegram Bot Token** | Create a bot via [@BotFather](https://t.me/BotFather) on Telegram |
| **Monetag Account & Zone ID** | Register at [publishers.monetag.com](https://publishers.monetag.com/signUp) |
| **Vercel Account** | Sign up at [vercel.com](https://vercel.com) (free tier) |
| **GitHub Account** | For connecting repo to Vercel: [github.com](https://github.com) |
| **Git** | [git-scm.com](https://git-scm.com/downloads) |

---

## Setup Guide

### Step 1: Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/telegram-downloader-bot.git
cd telegram-downloader-bot
```

### Step 2: Get Your Monetag Zone ID

1. **Register** at [publishers.monetag.com](https://publishers.monetag.com/signUp) (or sign in if you have an account).

2. Go to the **"Telegram Mini Apps"** tab in your dashboard.

3. Click **"+ Create new"** and add your Mini App:
   - Name: `AllSocialSaver` (or any name)
   - URL: You'll update this after deploying to Vercel (Step 3)

4. Click **"< > Get SDK"** to generate your ad tags.

5. **Copy the SDK script tag**. It will look like:
   ```html
   <script src="https://poweredby.jads.co/js/sdk.js" data-zone="987654" data-sdk="show_987654"></script>
   ```

6. **Note your Zone ID** (the number in `data-zone` -- e.g., `987654`).

7. **Update the Mini App files** with your Zone ID:

   **In `mini_app/index.html`** -- replace the Monetag `<script>` tag (around line 75):
   ```html
   <!-- REPLACE the entire <script> block with your actual Monetag SDK tag -->
   <script
       src="https://poweredby.jads.co/js/sdk.js"
       data-zone="987654"
       data-sdk="show_987654"
   ></script>
   ```

   **In `mini_app/script.js`** -- replace the ZONE_ID (line ~70):
   ```javascript
   const ZONE_ID = "987654";  // <-- Your actual Monetag zone ID
   ```

   > **IMPORTANT:** The zone ID must be identical in BOTH files!

### Step 3: Deploy the Mini App to Vercel

1. **Push your code to GitHub:**
   ```bash
   git add .
   git commit -m "Initial commit"
   git push origin main
   ```

2. **Go to [vercel.com](https://vercel.com)** and sign in.

3. Click **"Add New Project"** and import your GitHub repository.

4. **Configure the project:**
   | Setting | Value |
   |---------|-------|
   | **Root Directory** | `mini_app` |
   | **Framework Preset** | `Other` |
   | **Build Command** | _(leave empty)_ |
   | **Output Directory** | `.` |

5. Click **"Deploy"**.

6. After deployment, Vercel gives you a URL like:
   ```
   https://your-project-name.vercel.app
   ```
   **Copy this URL** -- you'll need it for the bot configuration.

7. **(Optional)** Go back to your Monetag dashboard and update the Mini App URL to your Vercel URL.

### Step 4: Configure & Run the Bot Locally

1. **Navigate to the bot directory:**
   ```bash
   cd bot
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set environment variables:**

   **Linux / macOS:**
   ```bash
   export BOT_TOKEN="8643154105:AAHGczQKF_IpzxSORNK5SbkEZgt-g_WCyWs"
   export MINI_APP_URL="https://your-project-name.vercel.app"
   ```

   **Windows (PowerShell):**
   ```powershell
   $env:BOT_TOKEN = "8643154105:AAHGczQKF_IpzxSORNK5SbkEZgt-g_WCyWs"
   $env:MINI_APP_URL = "https://your-project-name.vercel.app"
   ```

   **Windows (CMD):**
   ```cmd
   set BOT_TOKEN=8643154105:AAHGczQKF_IpzxSORNK5SbkEZgt-g_WCyWs
   set MINI_APP_URL=https://your-project-name.vercel.app
   ```

   > **Note:** Replace `https://your-project-name.vercel.app` with your actual Vercel URL from Step 3.

4. **Run the bot:**
   ```bash
   python bot.py
   ```

   You should see:
   ```
   Bot @AllSocialSaversbot is starting... (developed by @whykurds)
   ```

5. **Test it!** Open [@AllSocialSaversbot](https://t.me/AllSocialSaversbot) in Telegram, send `/start`, then send a video link.

### Step 5: Deploy the Bot to a Free Platform

The bot only needs the `bot/` folder. Choose one of these free platforms:

#### Option A: PythonAnywhere (Recommended)

1. Sign up at [pythonanywhere.com](https://www.pythonanywhere.com/) (free tier).

2. Open a **Bash console** and clone your repo:
   ```bash
   git clone https://github.com/YOUR_USERNAME/telegram-downloader-bot.git
   cd telegram-downloader-bot/bot
   pip install --user -r requirements.txt
   ```

3. Set environment variables in `~/.bashrc`:
   ```bash
   echo 'export BOT_TOKEN="8643154105:AAHGczQKF_IpzxSORNK5SbkEZgt-g_WCyWs"' >> ~/.bashrc
   echo 'export MINI_APP_URL="https://your-project-name.vercel.app"' >> ~/.bashrc
   source ~/.bashrc
   ```

4. Go to **"Tasks"** tab and set up an **Always-on task** (paid feature) or use **Scheduled tasks**:
   ```
   cd ~/telegram-downloader-bot/bot && python bot.py
   ```

   > **Free tier limitation:** PythonAnywhere free tier doesn't have always-on tasks. You can use scheduled tasks to restart the bot, or upgrade to the Hacker plan ($5/month).

#### Option B: TeleBotHost (Free Bot Hosting)

1. Go to [telebothost.com](https://telebothost.com) and sign up.
2. Upload only the `bot/` folder.
3. Set environment variables in their dashboard.
4. Start the bot from their control panel.

#### Option C: Railway.app

1. Go to [railway.app](https://railway.app) and sign in with GitHub.
2. Create a new project from your GitHub repo.
3. Set the root directory to `bot/`.
4. Add environment variables: `BOT_TOKEN` and `MINI_APP_URL`.
5. Railway will auto-detect Python and deploy.

#### Option D: Render.com

1. Go to [render.com](https://render.com) and sign up.
2. Create a new **Background Worker**.
3. Connect your GitHub repo.
4. Set root directory to `bot/`.
5. Build command: `pip install -r requirements.txt`
6. Start command: `python bot.py`
7. Add environment variables.

### Step 6: Set the Mini App URL in BotFather

This step is **optional** but recommended for a polished experience:

1. Open [@BotFather](https://t.me/BotFather) in Telegram.
2. Send `/mybots` and select `@AllSocialSaversbot`.
3. Click **"Bot Settings"** > **"Menu Button"** > **"Configure menu button"**.
4. Send your Vercel Mini App URL.
5. Set the button text (e.g., "Open App").

---

## Configuration Reference

| Variable | Where to Set | Description |
|----------|-------------|-------------|
| `BOT_TOKEN` | Environment variable or `bot.py` | Your Telegram bot API token from @BotFather |
| `MINI_APP_URL` | Environment variable or `bot.py` | Your Vercel deployment URL (https://...) |
| `ZONE_ID` | `mini_app/script.js` | Your Monetag zone ID (numeric) |
| Monetag SDK tag | `mini_app/index.html` | Full `<script>` tag from Monetag dashboard |

---

## Monetag Integration Guide

### How Monetag Works in This Project

1. **SDK Loading:** The Monetag SDK is loaded in `index.html` via a `<script>` tag. It creates a global function `show_XXXXX()` (where XXXXX is your zone ID).

2. **Ad Preloading:** When the Mini App opens, `script.js` calls `show_XXXXX({ type: 'preload' })` to download ad content in the background. This makes the ad appear instantly when the user taps the button.

3. **Ad Display:** When the user taps "Watch Ad & Download", we call `show_XXXXX()` which returns a Promise:
   - `.then()` -- User watched the ad successfully (proceed with download).
   - `.catch()` -- Ad failed or was unavailable (show error, let user retry).

4. **Ad Format:** We use **Rewarded Interstitial** -- a full-screen ad that the user watches in exchange for a reward (their download).

### Monetag Best Practices (From Official Docs)

- Always preload ads to avoid delays.
- Always use `.catch()` to handle ad failures gracefully.
- Pass `ymid` (user ID) for postback tracking.
- Use `requestVar` to track different placements.
- Test inside Telegram, not just in a browser.
- Don't include multiple SDK tags on the same page.

### Testing Monetag Ads

- Create a **test zone** in your Monetag dashboard for development.
- Ads may not always be available (depends on user's region/device).
- Some ad networks don't serve ads in testing environments -- always test on a real device inside Telegram.

---

## Supported Sites

Thanks to [yt-dlp](https://github.com/yt-dlp/yt-dlp), the bot supports **1000+ websites** including:

| Platform | Supported |
|----------|-----------|
| YouTube | Yes |
| Instagram (Reels, Posts) | Yes |
| TikTok | Yes |
| Twitter / X | Yes |
| Facebook | Yes |
| Reddit | Yes |
| Pinterest | Yes |
| Vimeo | Yes |
| Dailymotion | Yes |
| SoundCloud | Yes |
| Twitch Clips | Yes |
| And 1000+ more... | Yes |

Full list: [yt-dlp Supported Sites](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md)

---

## Troubleshooting

### Bot Issues

| Problem | Solution |
|---------|----------|
| Bot doesn't respond | Check `BOT_TOKEN` is correct. Ensure bot is running. |
| "Watch Ad" button doesn't open Mini App | Check `MINI_APP_URL` is a valid HTTPS URL. |
| Download fails | The link may be unsupported, require login, or the file is too large (>50MB). |
| Bot crashes on download | Ensure `yt-dlp` is installed: `pip install yt-dlp`. |
| "No link found" after watching ad | The bot may have restarted (in-memory storage cleared). Re-send the link. |

### Mini App Issues

| Problem | Solution |
|---------|----------|
| Mini App shows blank page | Check Vercel deployment. Ensure `index.html` is in the root of the deployed folder. |
| "Ad system not ready" error | Monetag SDK didn't load. Check your zone ID in both `index.html` and `script.js`. |
| Ad never shows | Monetag may have no fill for your region. Try from a different network/device. |
| sendData doesn't reach bot | Ensure the Mini App is opened via the bot's inline button (not a direct URL). |
| CSS looks broken | Clear Telegram's WebView cache (close and reopen the Mini App). |

### Monetag Issues

| Problem | Solution |
|---------|----------|
| `show_XXXXX is not a function` | Zone ID mismatch between `index.html` and `script.js`. Or SDK hasn't loaded yet. |
| Ad preload fails | Non-critical. The ad will still work when triggered, just with a delay. |
| No revenue showing | Wait 24-48 hours for Monetag reporting to update. Ensure ads are actually being watched. |
| SDK script URL returns 404 | Copy the exact URL from your Monetag dashboard. Don't modify it. |

---

## Notes & Limitations

### In-Memory Storage
- All user links are stored in a Python dictionary (`{user_id: url}`).
- **Data is lost** when the bot process restarts.
- Each user can only have **one pending link** at a time (last link wins).
- This is by design -- keeps the bot simple and database-free.
- For production with high traffic, consider switching to Redis.

### Telegram File Limits
- Bots can upload files up to **50 MB**.
- If a video is larger, the bot will inform the user.
- yt-dlp is configured to prefer formats under 50 MB when available.

### Free Hosting Limitations
- **PythonAnywhere free tier:** No always-on tasks. Bot may stop after some time.
- **Vercel free tier:** Generous limits (100 GB bandwidth/month) -- more than enough for a Mini App.
- **Railway.app free tier:** Limited hours per month.

### Monetag Revenue
- Revenue depends on user geography, ad availability, and engagement.
- Not all ad requests result in a paid impression.
- Use `ymid` tracking for accurate user-level reporting.

---

## Credits

- **Bot Developer:** [@whykurds](https://t.me/whykurds)
- **Bot Username:** [@AllSocialSaversbot](https://t.me/AllSocialSaversbot)
- **Powered by:**
  - [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
  - [yt-dlp](https://github.com/yt-dlp/yt-dlp)
  - [Monetag](https://monetag.com)
  - [Vercel](https://vercel.com)
  - [Telegram Mini Apps](https://core.telegram.org/bots/webapps)

---

**Made with by @whykurds**
