import json
import logging
import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler
)

# States for conversation handler
SELECTING_SPOT, SELECTING_DATE, SELECTING_TIME, CONFIRMING = range(4)

# Load configuration
with open('config.json', 'r') as f:
    config = json.load(f)

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=getattr(logging, config['logging']['log_level']),
    filename=config['logging']['log_file']
)
logger = logging.getLogger(__name__)

# Load or initialize data
try:
    with open(config['data_file'], 'r') as f:
        data = json.load(f)
except FileNotFoundError:
    data = {
        "reservations": [],
        "stats": {
            "usage_by_user": {},
            "usage_by_spot": {},
            "usage_by_day": {}
        }
    }

def save_data():
    """Save current data to file"""
    with open(config['data_file'], 'w') as f:
        json.dump(data, f, indent=2)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a welcome message when the command /start is issued."""
    user_id = update.effective_user.id
    if user_id not in config['authorized_users']:
        await update.message.reply_text(
            "Sorry, you are not authorized to use this bot."
        )
        return
    
    await update.message.reply_text(
        f"Welcome to the Parking Share Bot!\n\n"
        f"We manage {len(config['parking_places'])} parking spots "
        f"shared between {len(config['authorized_users'])} people.\n\n"
        f"Use /book to reserve a spot\n"
        f"Use /view to see current reservations\n"
        f"Use /cancel to cancel your reservation\n"
        f"Use /status to check spot availability\n"
        f"Use /stats to see usage statistics"
    )

async def book_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the booking process"""
    user_id = update.effective_user.id
    if user_id not in config['authorized_users']:
        await update.message.reply_text("Sorry, you are not authorized to use this bot.")
        return ConversationHandler.END
    
    # Check availability of spots
    available_spots = []
    for spot in config['parking_places']:
        if is_spot_available(spot):
            available_spots.append(spot)
    
    if not available_spots:
        await update.message.reply_text(
            "Sorry, all spots are currently reserved. Use /view to see when they'll be available."
        )
        return ConversationHandler.END
    
    keyboard = []
    for spot in available_spots:
        keyboard.append([InlineKeyboardButton(spot, callback_data=f"spot_{spot}")])
    
    await update.message.reply_text(
        "Which parking spot would you like to reserve?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SELECTING_SPOT

# Add more handler functions for the conversation flow
# ...

def is_spot_available(spot_name):
    """Check if a spot is available now"""
    now = datetime.datetime.now()
    for reservation in data['reservations']:
        if (reservation['spot'] == spot_name and 
            reservation['status'] in ['reserved', 'occupied'] and
            datetime.datetime.fromisoformat(reservation['start_time']) <= now and
            datetime.datetime.fromisoformat(reservation['end_time']) >= now):
            return False
    return True


def main():
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(config['token']).build()

    # Add conversation handler for booking
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('book', book_start)],
        states={
            SELECTING_SPOT: [CallbackQueryHandler(select_spot, pattern=r'^spot_')],
            SELECTING_DATE: [CallbackQueryHandler(select_date, pattern=r'^date_')],
            SELECTING_TIME: [CallbackQueryHandler(select_time, pattern=r'^time_')],
            CONFIRMING: [CallbackQueryHandler(confirm_booking, pattern=r'^confirm_')]
        },
        fallbacks=[CommandHandler('cancel', cancel_booking)]
    )
    
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", start))
    application.add_handler(CommandHandler("view", view_reservations))
    application.add_handler(CommandHandler("status", check_status))
    application.add_handler(CommandHandler("stats", show_stats))
    application.add_handler(CommandHandler("cancel", cancel_reservation))

    # Start the Bot
    application.run_polling()

if __name__ == '__main__':
    main()
