import os
import random
import requests
import logging
import time
from dotenv import load_dotenv, find_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackQueryHandler,
    ConversationHandler,
    CallbackContext,
)

# Debug: Print current working directory
print("Current Working Directory:", os.getcwd())

# Load environment variables from .env file
env_path = find_dotenv()
print("Found .env file at:", env_path)
load_dotenv(env_path)

# Get credentials from environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
IMGFLIP_USERNAME = os.getenv("IMGFLIP_USERNAME")
IMGFLIP_PASSWORD = os.getenv("IMGFLIP_PASSWORD")

print("Loaded BOT_TOKEN:", BOT_TOKEN)

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found. Please set it in your .env file or environment variables.")

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Meme templates configuration
MEME_TEMPLATES = {
    "dark humor": "181913649",
    "wholesome": "8072285",
    "sarcastic": "61579",
    "nerdy": "61532",
    "trending": "93895088",
    "absurd": "222403160",
    "distracted": "112126428",
    "drake": "181913649",
    "gru": "124822590",
    "change my mind": "129242436"
}
ALL_CATEGORIES = list(MEME_TEMPLATES.keys())
# For video memes, only allow these two categories
VIDEO_CATEGORIES = ["dark humor", "distracted"]

# Reddit request headers
REDDIT_HEADERS = {
    'User-Agent': 'MemeBot/1.0 (by Safe_Individual_592)'
}

# Conversation states
OPTION, CATEGORY, TOP_TEXT, BOTTOM_TEXT = range(4)

def generate_custom_meme(category: str, top_text: str, bottom_text: str) -> str:
    """Generate custom meme using the Imgflip API."""
    template_id = MEME_TEMPLATES.get(category.lower())
    if not template_id:
        return "Invalid category selected"
    try:
        response = requests.post(
            "https://api.imgflip.com/caption_image",
            data={
                "template_id": template_id,
                "username": IMGFLIP_USERNAME,
                "password": IMGFLIP_PASSWORD,
                "text0": top_text,
                "text1": bottom_text
            },
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        return data['data']['url'] if data.get('success') else f"API Error: {data.get('error_message', 'Unknown error')}"
    except Exception as e:
        logger.error(f"Meme generation failed: {str(e)}")
        return "Failed to create meme. Please try again later."

def fetch_random_reddit_image_meme() -> str:
    """Fetch a random image meme from r/memes using the Reddit API."""
    try:
        response = requests.get(
            "https://www.reddit.com/r/memes/hot.json?limit=50&t=week",
            headers=REDDIT_HEADERS,
            timeout=15
        )
        response.raise_for_status()
        posts = response.json().get('data', {}).get('children', [])
        valid_posts = []
        for post in posts:
            data = post.get('data', {})
            url = data.get('url', '')
            if any(url.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif']):
                valid_posts.append(url)
        if valid_posts:
            return random.choice(valid_posts)
    except Exception as e:
        logger.error(f"Failed to fetch random image meme: {str(e)}")
    return None

def fetch_reddit_video(category: str) -> str:
    """Fetch a random video meme from relevant subreddits for video mode."""
    subreddit_map = {
        "dark humor": ["dankvideos", "DarkHumorAndMemes"],
        "distracted": ["DistractedVideos", "FunnyVideos"]
    }
    for subreddit in subreddit_map.get(category, []):
        try:
            url = f"https://www.reddit.com/r/{subreddit}/top.json?limit=50&t=week"
            response = requests.get(url, headers=REDDIT_HEADERS, timeout=15)
            response.raise_for_status()
            posts = response.json().get('data', {}).get('children', [])
            valid_posts = []
            for post in posts:
                data = post.get('data', {})
                if data.get('is_video', False) and data.get('url', '').endswith('.mp4'):
                    valid_posts.append(data['url'])
                elif 'media' in data and 'reddit_video' in data['media']:
                    valid_posts.append(data['media']['reddit_video']['fallback_url'])
            if valid_posts:
                return random.choice(valid_posts)
        except Exception as e:
            logger.error(f"Failed to fetch from r/{subreddit}: {str(e)}")
    return None

def fetch_random_meme(mode: str, category: str = None) -> str:
    """Fetch a random meme using the Reddit API.
       For 'random' mode, fetch an image meme from r/memes.
       For 'video' mode, use fetch_reddit_video()."""
    if mode == "random":
        return fetch_random_reddit_image_meme()
    elif mode == "video":
        return fetch_reddit_video(category)
    return None

def start_command(update: Update, context: CallbackContext) -> int:
    """Start conversation and display mode selection."""
    update.message.reply_photo(
        photo="https://i.imgur.com/ExdKOOz.png",
        caption=("🎉 Welcome to Meme Bot on Telegram! 🎉\n"
                 "Developed by Jatin (Reg No: 12323852)\n"
                 "What would you like to do?")
    )
    keyboard = [
        [InlineKeyboardButton("Edit Meme ✏️", callback_data="edit"),
         InlineKeyboardButton("Random Meme 🎲", callback_data="random")],
        [InlineKeyboardButton("Video Meme 🎥", callback_data="video")]
    ]
    update.message.reply_text("Select mode:", reply_markup=InlineKeyboardMarkup(keyboard))
    return OPTION

def handle_option(update: Update, context: CallbackContext) -> int:
    """Handle mode selection."""
    query = update.callback_query
    query.answer()
    mode = query.data
    context.user_data["mode"] = mode
    try:
        query.edit_message_text(f"Selected {mode} mode!")
    except Exception as e:
        logger.error(f"Error editing message: {str(e)}")
        query.message.reply_text(f"Selected {mode} mode!")
    
    categories = VIDEO_CATEGORIES if mode == "video" else ALL_CATEGORIES
    keyboard = [[InlineKeyboardButton(cat.title(), callback_data=cat)] for cat in categories]
    query.message.reply_text("Choose category:", reply_markup=InlineKeyboardMarkup(keyboard))
    return CATEGORY

def handle_category(update: Update, context: CallbackContext) -> int:
    """Handle category selection."""
    query = update.callback_query
    query.answer()
    category = query.data
    context.user_data["category"] = category
    mode = context.user_data.get("mode", "edit")
    
    if mode == "edit":
        query.edit_message_text(f"Selected {category} category!")
        query.message.reply_text("Send TOP TEXT (max 50 characters):")
        return TOP_TEXT
    else:
        meme_url = fetch_random_meme(mode, category)
        if not meme_url:
            query.message.reply_text(
                f"⚠️ Couldn't find a {mode} meme for {category}.\nTry another category!"
            )
            return ConversationHandler.END
        try:
            if mode == "video":
                query.message.reply_video(
                    video=meme_url,
                    caption=f"Here's your {category} video meme! 🎬"
                )
            else:
                query.message.reply_photo(
                    photo=meme_url,
                    caption=f"Here's your {category} random meme! 🎲"
                )
            query.message.reply_text("Type /start to make more memes!")
        except Exception as e:
            logger.error(f"Failed to send {mode} meme: {str(e)}")
            query.message.reply_text(f"❌ Error: {str(e)}. Try another category!")
        return ConversationHandler.END

def handle_top_text(update: Update, context: CallbackContext) -> int:
    """Receive top text for custom memes."""
    context.user_data["top_text"] = update.message.text[:50]
    update.message.reply_text("Now send BOTTOM TEXT (max 50 characters):")
    return BOTTOM_TEXT

def handle_bottom_text(update: Update, context: CallbackContext) -> int:
    """Generate and send the final custom meme."""
    bottom_text = update.message.text[:50]
    context.user_data["bottom_text"] = bottom_text
    category = context.user_data["category"]
    meme_url = generate_custom_meme(category, context.user_data["top_text"], bottom_text)
    if meme_url.startswith("http"):
        update.message.reply_photo(photo=meme_url, caption="Here's your custom meme! 🎨")
    else:
        update.message.reply_text(meme_url)
    update.message.reply_text("Type /start to create another!")
    return ConversationHandler.END

def cancel(update: Update, context: CallbackContext) -> int:
    """Cancel the current operation."""
    update.message.reply_text("Operation cancelled. Type /start to begin again!")
    context.user_data.clear()
    return ConversationHandler.END

def error_handler(update: Update, context: CallbackContext):
    """Global error handler."""
    logger.error("Exception while handling update:", exc_info=context.error)
    if update.message:
        update.message.reply_text("⚠️ An error occurred. Please try again!")
    elif update.callback_query:
        update.callback_query.message.reply_text("⚠️ An error occurred. Please try again!")

def main():
    while True:
        try:
            updater = Updater(BOT_TOKEN, use_context=True)
            dp = updater.dispatcher
            conv_handler = ConversationHandler(
                entry_points=[CommandHandler("start", start_command)],
                states={
                    OPTION: [CallbackQueryHandler(handle_option)],
                    CATEGORY: [CallbackQueryHandler(handle_category)],
                    TOP_TEXT: [MessageHandler(Filters.text & ~Filters.command, handle_top_text)],
                    BOTTOM_TEXT: [MessageHandler(Filters.text & ~Filters.command, handle_bottom_text)]
                },
                fallbacks=[CommandHandler("cancel", cancel)],
                allow_reentry=True,
            )
            dp.add_handler(conv_handler)
            dp.add_error_handler(error_handler)
            updater.start_polling()
            logger.info("Bot started and polling...")
            updater.idle()
        except Exception as e:
            logger.error(f"Bot crashed: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
