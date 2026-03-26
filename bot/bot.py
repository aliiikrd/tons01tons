"""
===============================================================================
  Telegram Media Downloader Bot  -  @AllSocialSaversbot
  Developed by @whykurds
===============================================================================

  OVERVIEW:
  ---------
  This bot receives a video or image URL from the user, stores it in memory
  (no database required), and prompts the user to watch a Monetag ad via a
  Telegram Mini App.  Once the ad is completed the Mini App sends an
  "ad_completed" signal back to the bot, which then downloads the media with
  yt-dlp and sends it to the user.

  ARCHITECTURE:
  -------------
  1.  User sends a link  ->  stored in an in-memory Python dictionary.
  2.  Bot replies with an inline button that opens the Mini App.
  3.  Mini App shows a Monetag Rewarded Interstitial ad.
  4.  On ad completion the Mini App calls Telegram.WebApp.sendData("ad_completed").
  5.  Bot receives the web_app_data event, downloads the media, and sends it.

  WHY IN-MEMORY STORAGE?
  ----------------------
  We use a plain Python dict  { user_id: url_string }  instead of a database
  because:
  -  The bot is lightweight and meant for free hosting (PythonAnywhere, etc.).
  -  Each user can only have ONE pending link at a time (last link wins).
  -  If the bot restarts the dictionary is cleared, which is acceptable for
     this use-case (the user simply re-sends their link).

  WHY asyncio.run_in_executor?
  ----------------------------
  yt-dlp's download process is CPU-bound and blocking.  Running it directly
  inside an async handler would freeze the entire event loop, preventing the
  bot from answering other users.  By using run_in_executor we offload the
  blocking work to a thread-pool so the event loop stays responsive.

  DEPENDENCIES  (see requirements.txt):
  -  python-telegram-bot >= 20.0   (async Telegram Bot API wrapper)
  -  yt-dlp                        (media downloader supporting 1000+ sites)

===============================================================================
"""

# ──────────────────────────────────────────────────────────────────────────────
#  IMPORTS
# ──────────────────────────────────────────────────────────────────────────────

import os               # Access environment variables (BOT_TOKEN, MINI_APP_URL)
import re               # Regular expressions - used to detect URLs in messages
import glob as _glob    # File pattern matching - find downloaded files
import asyncio          # Async primitives, specifically run_in_executor
import logging          # Structured logging for debugging in production
import tempfile         # Create temporary directories for downloads
import shutil           # Remove temporary directories after sending files
from functools import partial  # Bind arguments to blocking functions for executor

import yt_dlp           # The powerful media downloader (supports 1000+ sites)

from telegram import (
    Update,             # Represents an incoming update from Telegram
    WebAppInfo,         # Describes a Mini App to be opened via an inline button
    InlineKeyboardButton,   # A single button in an inline keyboard
    InlineKeyboardMarkup,   # Container for rows of inline buttons
)
from telegram.ext import (
    Application,        # The main entry point for building and running the bot
    CommandHandler,     # Handles /commands (like /start)
    MessageHandler,     # Handles regular text messages and web_app_data
    ContextTypes,       # Type hints for callback context
    filters,            # Pre-built message filters (text, web_app_data, etc.)
)
from telegram.constants import ParseMode  # For HTML-formatted messages

# ──────────────────────────────────────────────────────────────────────────────
#  CONFIGURATION
# ──────────────────────────────────────────────────────────────────────────────

# Your Telegram Bot API token, obtained from @BotFather.
# SECURITY: Never hard-code tokens in production - use environment variables.
# For quick testing you can paste it here, but switch to env vars before deploy.
BOT_TOKEN = os.environ.get(
    "BOT_TOKEN",
    "8643154105:AAHGczQKF_IpzxSORNK5SbkEZgt-g_WCyWs"  # Fallback for testing
)

# The HTTPS URL where your Mini App is deployed (Vercel).
# This URL is passed to Telegram so it can open the Mini App in WebView.
# Replace "YOUR_VERCEL_URL" with your actual Vercel deployment URL.
MINI_APP_URL = os.environ.get(
    "MINI_APP_URL",
    "https://tons01tons-njgo.vercel.app"  # <-- Replace after deploying mini_app/ to Vercel
)

# ──────────────────────────────────────────────────────────────────────────────
#  LOGGING  -  helps diagnose issues on free hosting platforms
# ──────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
#  IN-MEMORY STORAGE
# ──────────────────────────────────────────────────────────────────────────────
#
#  This dictionary maps each Telegram user_id (int) to the URL (str) they
#  most recently submitted.  Only the latest link is kept per user.
#
#  Pros:  Zero setup, no external services, instant read/write.
#  Cons:  Data is lost when the process restarts.
#         Not suitable for multi-process deployments (use Redis in that case).
#
#  Structure example:
#      {
#          123456789: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
#          987654321: "https://www.instagram.com/reel/ABC123/",
#      }

user_links: dict[int, str] = {}

# ──────────────────────────────────────────────────────────────────────────────
#  HELPER  -  Build the inline keyboard with the Mini App button
# ──────────────────────────────────────────────────────────────────────────────

def get_webapp_keyboard() -> InlineKeyboardMarkup:
    """
    Creates and returns an InlineKeyboardMarkup containing a single button
    that opens the Telegram Mini App.

    How it works:
    -  WebAppInfo(url=...) tells Telegram to open the given URL inside the
       built-in WebView (the Mini App environment).
    -  When the user taps the button Telegram opens the Mini App.
    -  The Mini App can later call Telegram.WebApp.sendData() to send data
       back to the bot, which arrives as a web_app_data message.
    """
    button = InlineKeyboardButton(
        text="Watch Ad & Download",           # Button label shown to the user
        web_app=WebAppInfo(url=MINI_APP_URL),  # Opens the Mini App on tap
    )
    # InlineKeyboardMarkup expects a list of rows; each row is a list of buttons.
    return InlineKeyboardMarkup([[button]])

# ──────────────────────────────────────────────────────────────────────────────
#  HANDLER  -  /start command
# ──────────────────────────────────────────────────────────────────────────────

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Triggered when the user sends /start.

    Sends a welcome message explaining how the bot works and shows the
    inline button (disabled until the user sends a link, but shown for UX).
    """
    welcome_text = (
        "<b>Welcome to All Social Saver Bot!</b>\n\n"

        "Send me any video or image link from:\n"
        "  YouTube / Instagram / TikTok / Twitter(X)\n"
        "  Facebook / Reddit / Pinterest / and 1000+ more sites\n\n"

        "<b>How it works:</b>\n"
        "1. Send me a link\n"
        "2. Tap <i>\"Watch Ad & Download\"</i>\n"
        "3. Watch a short ad in the Mini App\n"
        "4. Your media is downloaded and sent here!\n\n"

        "Developed by @whykurds"
    )
    await update.message.reply_text(
        text=welcome_text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_webapp_keyboard(),
    )

# ──────────────────────────────────────────────────────────────────────────────
#  HELPER  -  Simple URL validation using regex
# ──────────────────────────────────────────────────────────────────────────────

# This regex matches most http/https URLs.
# It is intentionally broad - yt-dlp will do the real validation later.
URL_PATTERN = re.compile(
    r"https?://"                     # Must start with http:// or https://
    r"[^\s<>\"']+",                  # Followed by non-whitespace characters
    re.IGNORECASE,
)

# ──────────────────────────────────────────────────────────────────────────────
#  HANDLER  -  User sends a text message (assumed to be a link)
# ──────────────────────────────────────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Triggered when the user sends any text message (that isn't a command).

    Logic:
    1.  Extract the first URL found in the message text.
    2.  If a valid URL is found, store it in the user_links dictionary
        keyed by the user's Telegram ID.
    3.  Reply with a confirmation and the Mini App button.
    4.  If no URL is found, ask the user to send a valid link.
    """
    text = update.message.text.strip()
    user_id = update.effective_user.id

    # Try to find a URL in the message
    match = URL_PATTERN.search(text)

    if match:
        url = match.group(0)

        # ── Store the URL in our in-memory dictionary ──
        # If the user already had a link stored it gets overwritten.
        user_links[user_id] = url
        logger.info("User %s saved link: %s", user_id, url)

        await update.message.reply_text(
            text=(
                "Link saved! Please tap the button below to watch a short ad "
                "- then your media will be downloaded and sent to you.\n\n"
                f"<b>Your link:</b> <code>{url}</code>"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=get_webapp_keyboard(),
        )
    else:
        # No URL detected - inform the user
        await update.message.reply_text(
            text=(
                "I couldn't find a valid link in your message.\n"
                "Please send a URL starting with <code>http://</code> or "
                "<code>https://</code>."
            ),
            parse_mode=ParseMode.HTML,
        )

# ──────────────────────────────────────────────────────────────────────────────
#  BLOCKING DOWNLOAD FUNCTION  (runs in a thread via executor)
# ──────────────────────────────────────────────────────────────────────────────

def download_media(url: str, download_dir: str) -> str | None:
    """
    Downloads media from *url* into *download_dir* using yt-dlp.

    Returns the path to the downloaded file, or None if download failed.

    yt-dlp Configuration Explained:
    --------------------------------
    - outtmpl:  Output filename template.  We use the video title + extension.
                The file is saved inside download_dir.
    - format:   "best[filesize<50M]/best" tries to get the best quality that
                is under 50 MB (Telegram's upload limit for bots).  If no
                format is under 50 MB it falls back to the absolute best and
                we'll handle the size error later.
    - merge_output_format:  When separate video+audio streams are merged,
                            output as mp4 for broad compatibility.
    - noplaylist:  Download only the single video, not the entire playlist.
    - quiet:    Suppress yt-dlp's verbose console output.
    - no_warnings:  Suppress non-critical warnings.
    - socket_timeout:  Network timeout in seconds to avoid hanging forever.
    - retries:  Number of retry attempts for transient network errors.
    - http_headers:  A realistic User-Agent to avoid being blocked by sites
                     that reject bot-like requests.
    """
    # yt-dlp options dictionary
    ydl_opts = {
        "outtmpl": os.path.join(download_dir, "%(title).80s.%(ext)s"),
        "format": "best[filesize<50M]/best",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 30,
        "retries": 3,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        },
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # extract_info downloads the file when download=True
            info = ydl.extract_info(url, download=True)

            # yt-dlp may return the prepared filename via 'requested_downloads'
            if info and "requested_downloads" in info:
                return info["requested_downloads"][0]["filepath"]

            # Fallback: search the download directory for any file
            files = _glob.glob(os.path.join(download_dir, "*"))
            if files:
                return files[0]

    except Exception as exc:
        logger.error("yt-dlp download failed for %s: %s", url, exc)

    return None  # Download failed

# ──────────────────────────────────────────────────────────────────────────────
#  HELPER  -  Determine if a file is an image based on extension
# ──────────────────────────────────────────────────────────────────────────────

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff"}

def is_image(filepath: str) -> bool:
    """Check whether *filepath* has a common image file extension."""
    _, ext = os.path.splitext(filepath)
    return ext.lower() in IMAGE_EXTENSIONS

# ──────────────────────────────────────────────────────────────────────────────
#  HANDLER  -  web_app_data (Mini App sends data back to the bot)
# ──────────────────────────────────────────────────────────────────────────────

async def handle_webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Triggered when the Telegram Mini App calls:
        Telegram.WebApp.sendData("ad_completed")

    The data arrives in update.effective_message.web_app_data.data.

    Flow:
    1.  Verify the data is "ad_completed".
    2.  Look up the user's stored URL.
    3.  Send a "downloading..." status message.
    4.  Download the media in a background thread (run_in_executor).
    5.  Send the file to the user (as video or photo depending on extension).
    6.  Clean up the temporary directory.
    7.  Remove the URL from the dictionary.
    """
    user_id = update.effective_user.id
    data = update.effective_message.web_app_data.data  # The string from sendData()

    logger.info("Received web_app_data from user %s: %s", user_id, data)

    # ── Step 1: Verify the signal ──
    if data != "ad_completed":
        await update.effective_message.reply_text(
            "Unexpected data received from Mini App. Please try again."
        )
        return

    # ── Step 2: Retrieve the stored URL ──
    url = user_links.get(user_id)
    if not url:
        await update.effective_message.reply_text(
            "No link found! Please send me a link first, then watch the ad."
        )
        return

    # ── Step 3: Notify the user that download is starting ──
    status_msg = await update.effective_message.reply_text(
        "Downloading your media... Please wait."
    )

    # ── Step 4: Download in a background thread ──
    # Create a temporary directory that will be cleaned up after sending.
    tmp_dir = tempfile.mkdtemp(prefix="tg_dl_")
    loop = asyncio.get_event_loop()

    try:
        # run_in_executor runs the blocking function in a ThreadPoolExecutor
        # so the async event loop is NOT blocked.
        filepath = await loop.run_in_executor(
            None,                               # Use default executor
            partial(download_media, url, tmp_dir),  # Callable with args
        )
    except Exception as exc:
        logger.error("Executor error for user %s: %s", user_id, exc)
        filepath = None

    # ── Step 5: Send the file or report failure ──
    if filepath and os.path.exists(filepath):
        file_size = os.path.getsize(filepath)

        # Telegram bot file upload limit is ~50 MB
        if file_size > 50 * 1024 * 1024:
            await status_msg.edit_text(
                "The file is too large (>50 MB) for Telegram. "
                "Please try a lower-quality link or a shorter video."
            )
        else:
            try:
                if is_image(filepath):
                    # Send as a photo (Telegram compresses it for preview)
                    await update.effective_message.reply_photo(
                        photo=open(filepath, "rb"),
                        caption="Here is your image! | @AllSocialSaversbot",
                    )
                else:
                    # Send as a video (Telegram shows a video player)
                    await update.effective_message.reply_video(
                        video=open(filepath, "rb"),
                        caption="Here is your video! | @AllSocialSaversbot",
                        supports_streaming=True,  # Allow streaming playback
                    )
                # Edit the status message to indicate success
                await status_msg.edit_text("Download complete!")
            except Exception as send_err:
                logger.error("Failed to send file to user %s: %s", user_id, send_err)
                await status_msg.edit_text(
                    "Failed to send the file. It may be too large or in an "
                    "unsupported format. Please try a different link."
                )
    else:
        # Download failed - inform the user
        await status_msg.edit_text(
            "Download failed. Possible reasons:\n"
            "- The link is invalid or unsupported\n"
            "- The site requires login\n"
            "- Network error\n\n"
            "Please check your link and try again."
        )

    # ── Step 6: Cleanup temporary files ──
    try:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        logger.info("Cleaned up temp dir: %s", tmp_dir)
    except Exception:
        pass  # Non-critical - OS will clean /tmp eventually

    # ── Step 7: Remove the URL from storage ──
    # This prevents the user from accidentally re-downloading the same file.
    user_links.pop(user_id, None)

# ──────────────────────────────────────────────────────────────────────────────
#  ERROR HANDLER  -  Catch-all for unhandled exceptions
# ──────────────────────────────────────────────────────────────────────────────

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Logs errors caused by Updates.
    This prevents the bot from crashing on unexpected exceptions.
    """
    logger.error("Exception while handling an update:", exc_info=context.error)

# ──────────────────────────────────────────────────────────────────────────────
#  MAIN  -  Build and run the bot application
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    """
    Entry point.  Builds the Application, registers handlers, and starts
    long-polling.

    Handler registration order matters:
    1.  CommandHandler for /start  -  highest priority for the /start command.
    2.  MessageHandler for web_app_data  -  catches Mini App responses.
    3.  MessageHandler for text  -  catches all other text (assumed to be links).

    The bot uses long-polling (run_polling) which is ideal for free hosting
    platforms that don't support webhooks easily.
    """
    # ── Validate configuration ──
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        raise ValueError(
            "BOT_TOKEN is not set!  "
            "Set it as an environment variable or edit the default in this file."
        )

    if not MINI_APP_URL or "YOUR_VERCEL_URL" in MINI_APP_URL:
        logger.warning(
            "MINI_APP_URL is not configured!  "
            "The 'Watch Ad & Download' button will not work until you set it."
        )

    # ── Build the bot application ──
    app = Application.builder().token(BOT_TOKEN).build()

    # ── Register handlers ──

    # 1. /start command
    app.add_handler(CommandHandler("start", start_command))

    # 2. Web App data handler - triggered when Mini App calls sendData()
    #    filters.StatusUpdate.WEB_APP_DATA matches messages that contain
    #    web_app_data (i.e., data sent from a Mini App).
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp_data))

    # 3. Text message handler - catches URLs sent by users
    #    filters.TEXT filters for plain text messages.
    #    ~filters.COMMAND excludes messages starting with / (commands).
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # 4. Global error handler
    app.add_error_handler(error_handler)

    # ── Start the bot ──
    logger.info("Bot @AllSocialSaversbot is starting... (developed by @whykurds)")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,  # Receive all update types
        drop_pending_updates=True,          # Ignore old messages on startup
    )

# ──────────────────────────────────────────────────────────────────────────────
#  SCRIPT ENTRY POINT
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    main()
