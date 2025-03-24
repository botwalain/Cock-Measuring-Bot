from typing import Final
import json
import random
from datetime import datetime, timedelta
from uuid import uuid4

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# Constants
TOKEN: Final = 'Bot Token Goes Here'
BOT_USERNAME: Final = '@Bot UserName (make sure to add the @ infront of the username)'
DATABASE_FILE: Final = r"The database path , JSON file will be saved here"

# Load persistent data from file
try:
    with open(DATABASE_FILE, 'r') as file:
        database = json.load(file)
except FileNotFoundError:
    database = {}

def save_database():
    with open(DATABASE_FILE, 'w') as file:
        json.dump(database, file)

# Global dictionary to hold ongoing PvP battles.
# Battle structure:
# {
#   "battle_id": {
#       "initiator": user_id (str),
#       "challenger": user_id (str) or None,
#       "bid": int,
#       "chat_id": int,
#       "message_id": int,
#       "initiator_move": None or "rock"/"paper"/"scissors",
#       "challenger_move": None or "rock"/"paper"/"scissors",
#       "state": "waiting_challenger" | "awaiting_initiator_move" | "awaiting_challenger_move"
#   }
# }
pvp_battles = {}

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello, I am Solid Snake. Let's start the game of measuring your cock size!")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "Available commands:\n"
        "/grow - Grow your cock by a random amount (1-20 cm) every 12 hours.\n"
        "/size - Check your current cock size.\n"
        "/topcocks - Show the top 10 cock sizes.\n"
        "/pvp <bid> - Challenge someone for a bid of your cock size (rock, paper, scissors based).\n"
        "/start - Welcome message."
    )
    await update.message.reply_text(help_text)

async def grow_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    user_id = str(user.id)
    now = datetime.now()

    # Initialize new user data (store display name)
    if user_id not in database:
        display_name = user.username if user.username else user.first_name
        database[user_id] = {"size": 0, "last_grow": None, "name": display_name}

    last_grow_str = database[user_id]["last_grow"]
    if last_grow_str:
        last_grow = datetime.strptime(last_grow_str, '%Y-%m-%d %H:%M:%S')
        if now - last_grow < timedelta(hours=12):
            remaining = timedelta(hours=12) - (now - last_grow)
            hours, rem = divmod(remaining.seconds, 3600)
            minutes, seconds = divmod(rem, 60)
            await update.message.reply_text(
                f"Please wait {hours} hours, {minutes} minutes, and {seconds} seconds before growing again."
            )
            return

    growth = random.randint(1, 20)
    database[user_id]["size"] += growth
    database[user_id]["last_grow"] = now.strftime('%Y-%m-%d %H:%M:%S')
    save_database()
    await update.message.reply_text(
        f"Your cock has grown by {growth} cm. New size: {database[user_id]['size']} cm!"
    )

async def size_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    if user_id in database:
        current_size = database[user_id]["size"]
        await update.message.reply_text(f"Your cock size is {current_size} cm.")
    else:
        await update.message.reply_text("You haven't grown your cock yet. Use /grow to start!")

async def topcocks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Sort users by size in descending order
    sorted_users = sorted(database.items(), key=lambda item: item[1]["size"], reverse=True)
    if not sorted_users:
        await update.message.reply_text("No players yet. Use /grow to start growing!")
        return

    leaderboard_text = "🏆 Top Cock Sizes:\n"
    for rank, (user_id, data) in enumerate(sorted_users[:10], start=1):
        name = data.get("name", user_id)
        leaderboard_text += f"{rank}. {name} - {data['size']} cm\n"
    await update.message.reply_text(leaderboard_text)

# PvP Command: /pvp <bid>
async def pvp_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    user_id = str(user.id)
    chat_id = update.message.chat.id

    if not context.args:
        await update.message.reply_text("Usage: /pvp <bid>")
        return

    try:
        bid = int(context.args[0])
        if bid <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Bid must be a positive integer.")
        return

    if user_id not in database or database[user_id]["size"] < bid:
        await update.message.reply_text("You don't have enough penis to bid that amount.")
        return

    battle_id = str(uuid4())
    pvp_battles[battle_id] = {
        "initiator": user_id,
        "challenger": None,
        "bid": bid,
        "chat_id": chat_id,
        "message_id": None,
        "initiator_move": None,
        "challenger_move": None,
        "state": "waiting_challenger"
    }

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Attack!", callback_data=f"pvp|{battle_id}|attack")]
    ])
    sent_message = await update.message.reply_text(
        f"User {database[user_id]['name']} has challenged the group for a bid of {bid} cm. Click 'Attack!' to accept.",
        reply_markup=keyboard
    )
    pvp_battles[battle_id]["message_id"] = sent_message.message_id

# Callback handler for PvP events (includes rock-paper-scissors game flow)
async def pvp_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Acknowledge callback

    data = query.data.split('|')
    if len(data) < 3:
        return

    action, battle_id, detail = data
    if battle_id not in pvp_battles:
        await query.answer("This battle no longer exists.", show_alert=True)
        return

    battle = pvp_battles[battle_id]
    user_id = str(query.from_user.id)

    # When a challenger clicks Attack!
    if detail == "attack":
        if user_id == battle["initiator"]:
            await query.answer("You cannot attack your own challenge.", show_alert=True)
            return
        if user_id not in database or database[user_id]["size"] < battle["bid"]:
            await query.answer("You don't have enough penis.", show_alert=True)
            return
        battle["challenger"] = user_id
        battle["state"] = "awaiting_initiator_move"
        # Ask initiator to choose a move
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("Rock", callback_data=f"pvp|{battle_id}|initiator_rock"),
            InlineKeyboardButton("Paper", callback_data=f"pvp|{battle_id}|initiator_paper"),
            InlineKeyboardButton("Scissors", callback_data=f"pvp|{battle_id}|initiator_scissors")
        ]])
        await context.bot.edit_message_text(
            chat_id=battle["chat_id"],
            message_id=battle["message_id"],
            text=f"PvP started! Initiator {database[battle['initiator']]['name']} – please choose your move:",
            reply_markup=keyboard
        )
        await query.answer("Challenge accepted!")
        return

    # Initiator chooses a move
    if detail.startswith("initiator_") and battle["state"] == "awaiting_initiator_move":
        if user_id != battle["initiator"]:
            await query.answer("Only the challenge initiator can make that move.", show_alert=True)
            return
        move = detail.split("_")[1]  # rock, paper, or scissors
        battle["initiator_move"] = move
        battle["state"] = "awaiting_challenger_move"
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("Rock", callback_data=f"pvp|{battle_id}|challenger_rock"),
            InlineKeyboardButton("Paper", callback_data=f"pvp|{battle_id}|challenger_paper"),
            InlineKeyboardButton("Scissors", callback_data=f"pvp|{battle_id}|challenger_scissors")
        ]])
        await context.bot.edit_message_text(
            chat_id=battle["chat_id"],
            message_id=battle["message_id"],
            text=f"Now challenger {database[battle['challenger']]['name']}, please choose your move:",
            reply_markup=keyboard
        )
        await query.answer("Move recorded.")
        return

    # Challenger chooses a move
    if detail.startswith("challenger_") and battle["state"] == "awaiting_challenger_move":
        if user_id != battle["challenger"]:
            await query.answer("Only the challenger can make that move.", show_alert=True)
            return
        move = detail.split("_")[1]
        battle["challenger_move"] = move

        def decide(a: str, b: str) -> int:
            outcomes = {
                ('rock', 'scissors'): 1,
                ('scissors', 'paper'): 1,
                ('paper', 'rock'): 1
            }
            if a == b:
                return 0
            return 1 if outcomes.get((a, b)) else -1

        result = decide(battle["initiator_move"], battle["challenger_move"])
        if result == 0:
            # Tie: Reset moves and ask initiator to choose again
            battle["initiator_move"] = None
            battle["challenger_move"] = None
            battle["state"] = "awaiting_initiator_move"
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("Rock", callback_data=f"pvp|{battle_id}|initiator_rock"),
                InlineKeyboardButton("Paper", callback_data=f"pvp|{battle_id}|initiator_paper"),
                InlineKeyboardButton("Scissors", callback_data=f"pvp|{battle_id}|initiator_scissors")
            ]])
            await context.bot.edit_message_text(
                chat_id=battle["chat_id"],
                message_id=battle["message_id"],
                text=(f"Both players chose {move} (Tie!).\nTie! Initiator, please choose again:"),
                reply_markup=keyboard
            )
            await query.answer("Tie! Choose again.")
            return

        # Determine winner
        if result == 1:
            winner = battle["initiator"]
            loser = battle["challenger"]
        else:
            winner = battle["challenger"]
            loser = battle["initiator"]

        bid = battle["bid"]
        if database[loser]["size"] < bid:
            bid = database[loser]["size"]
        database[winner]["size"] += bid
        database[loser]["size"] -= bid
        save_database()

        await context.bot.edit_message_text(
            chat_id=battle["chat_id"],
            message_id=battle["message_id"],
            text=(f"Result:\n"
                  f"Initiator chose: {battle['initiator_move']}\n"
                  f"Challenger chose: {battle['challenger_move']}\n"
                  f"{database[winner]['name']} wins and takes {bid} cm from {database[loser]['name']}!")
        )
        await query.answer("Battle complete!")
        del pvp_battles[battle_id]
        return

    await query.answer()

# Error handler
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print(f"Update {update} caused error {context.error}")

if __name__ == '__main__':
    print("Starting Bot...")
    app = Application.builder().token(TOKEN).build()

    # Command handlers
    app.add_handler(CommandHandler('start', start_command))
    app.add_handler(CommandHandler('help', help_command))
    app.add_handler(CommandHandler('grow', grow_command))
    app.add_handler(CommandHandler('size', size_command))
    app.add_handler(CommandHandler('topcocks', topcocks_command))
    app.add_handler(CommandHandler('pvp', pvp_command))
    
    # Callback query handler for PvP events
    app.add_handler(CallbackQueryHandler(pvp_callback, pattern=r"^pvp\|"))
    
    # Global error handler
    app.add_error_handler(error_handler)

    print("Polling...")
    app.run_polling(poll_interval=3)
