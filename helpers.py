import json
from parking_bot import is_spot_available, save_data
from telegram.ext import ConversationHandler


with open('config.json', 'r') as f:
    config = json.load(f)

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

async def select_spot(update, context):
    query = update.callback_query
    await query.answer()
    selected_spot = query.data.replace('spot_', '')
    context.user_data['selected_spot'] = selected_spot

    # Prepare date selection keyboard (next 7 days)
    from datetime import datetime, timedelta
    keyboard = []
    for i in range(7):
        day = datetime.now() + timedelta(days=i)
        day_str = day.strftime('%Y-%m-%d')
        keyboard.append([{'text': day.strftime('%a %b %d'), 'callback_data': f'date_{day_str}'}])

    await query.edit_message_text(
        text=f"Selected spot: {selected_spot}\nPlease select a date for your reservation:",
        reply_markup=keyboard
    )
    return 1  # Next state: SELECTING_DATE


async def select_date(update, context):
    query = update.callback_query
    await query.answer()
    selected_date = query.data.replace('date_', '')
    context.user_data['selected_date'] = selected_date

    # Prepare time selection keyboard (e.g., 1-hour slots from 8 AM to 8 PM)
    keyboard = []
    for hour in range(8, 20):
        time_str = f"{hour:02d}:00"
        keyboard.append([{'text': time_str, 'callback_data': f'time_{time_str}'}])

    await query.edit_message_text(
        text=f"Selected date: {selected_date}\nPlease select a start time for your reservation:",
        reply_markup=keyboard
    )
    return 2  # Next state: SELECTING_TIME


async def select_time(update, context):
    query = update.callback_query
    await query.answer()
    selected_time = query.data.replace('time_', '')
    context.user_data['selected_time'] = selected_time

    selected_spot = context.user_data.get('selected_spot')
    selected_date = context.user_data.get('selected_date')

    confirmation_text = (
        f"Please confirm your booking:\n"
        f"Spot: {selected_spot}\n"
        f"Date: {selected_date}\n"
        f"Start Time: {selected_time}\n"
        f"Duration: 1 hour"
    )
    keyboard = [
        [{'text': 'Confirm', 'callback_data': 'confirm_yes'}],
        [{'text': 'Cancel', 'callback_data': 'confirm_no'}]
    ]

    await query.edit_message_text(
        text=confirmation_text,
        reply_markup=keyboard
    )
    return 3  # Next state: CONFIRMING

async def confirm_booking(update, context):
    query = update.callback_query
    await query.answer()
    response = query.data.replace('confirm_', '')

    if response == 'yes':
        from datetime import datetime, timedelta
        selected_spot = context.user_data.get('selected_spot')
        selected_date = context.user_data.get('selected_date')
        selected_time = context.user_data.get('selected_time')
        user_id = update.effective_user.id

        start_time_str = f"{selected_date}T{selected_time}:00"
        start_time = datetime.fromisoformat(start_time_str)
        end_time = start_time + timedelta(hours=1)

        if not is_spot_available(selected_spot):
            await query.edit_message_text("Sorry, the spot is no longer available.")
            return ConversationHandler.END

        reservation = {
            "user_id": user_id,
            "spot": selected_spot,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "status": "reserved"
        }
        data['reservations'].append(reservation)
        save_data()

        await query.edit_message_text("Your reservation has been confirmed!")
    else:
        await query.edit_message_text("Booking cancelled.")

    return ConversationHandler.END


async def cancel_booking(update, context):
    await update.message.reply_text("Booking process cancelled.")
    return ConversationHandler.END


async def cancel_reservation(update, context):
    user_id = update.effective_user.id
    # Find active reservation for user
    active_reservations = [r for r in data['reservations'] if r['user_id'] == user_id and r['status'] == 'reserved']

    if not active_reservations:
        await update.message.reply_text("You have no active reservations to cancel.")
        return

    # Cancel the first active reservation
    reservation = active_reservations[0]
    reservation['status'] = 'cancelled'
    save_data()

    await update.message.reply_text(
        f"Your reservation for spot {reservation['spot']} on {reservation['start_time']} has been cancelled."
    )


async def view_reservations(update, context):
    user_id = update.effective_user.id
    user_reservations = [r for r in data['reservations'] if r['user_id'] == user_id and r['status'] != 'cancelled']

    if not user_reservations:
        await update.message.reply_text("You have no reservations.")
        return

    message_lines = ["Your reservations:"]
    for r in user_reservations:
        message_lines.append(
            f"Spot: {r['spot']}, Start: {r['start_time']}, End: {r['end_time']}, Status: {r['status']}"
        )

    await update.message.reply_text('\n'.join(message_lines))


async def check_status(update, context):
    status_lines = []
    for spot in config['parking_places']:
        available = is_spot_available(spot)
        status = 'Available' if available else 'Occupied or Reserved'
        status_lines.append(f"{spot}: {status}")

    await update.message.reply_text("Current parking spot status:\n" + "\n".join(status_lines))
