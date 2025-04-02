import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.dispatcher.router import Router
from aiogram.types.input_file import FSInputFile
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext

# Enable logging for debugging
logging.basicConfig(level=logging.DEBUG)

# Bot token
TOKEN = "8091945944:AAGvf90keCy7KJEwt5Z1MbtuVikp7lay9E8"
ADMIN_ID = -1002537722873  # Ensure this is an integer

# Initialize bot and dispatcher
bot = Bot(token=TOKEN)
storage = MemoryStorage()

dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

PRICES = {
    "package_1": {1: 15, 3: 30, 6: 45, 12: 75},
    "package_2": {12: 105},
    "package_3": {12: 40},
    "vpn": 5  # Example price for VPN
}

# Define states for conversation
class FormState:
    email = "email"
    renewal = "renewal"
    duration = "duration"
    connections = "connections"
    internet_provider = "internet_provider"
    device = "device"
    payment = "payment"

# Command handler for /start
@router.message(Command(commands=["start"]))
async def start_command(message: types.Message):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="View Packages", callback_data="view_packages")]
        ]
    )

    # Send multiple images as a media group
    media_group = [
        InputMediaPhoto(media=FSInputFile("images/price_list1.jpg"), caption=f"Welcome, {message.from_user.first_name}! Here are our packages."),
        InputMediaPhoto(media=FSInputFile("images/price_list2.jpg"), caption="Here is another image of our packages.")
    ]
    await message.answer_media_group(media=media_group)
    await message.answer("Click the button below to view packages:", reply_markup=keyboard)

# Callback query handler for viewing packages
@router.callback_query(lambda c: c.data == "view_packages")
async def view_packages(callback_query: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Bronze", callback_data="package_1")],
            [InlineKeyboardButton(text="Silver", callback_data="package_2")],
            [InlineKeyboardButton(text="Super VOD", callback_data="package_3")]
        ]
    )
    await bot.send_message(callback_query.from_user.id, "Select a package:", reply_markup=keyboard)
    await callback_query.answer()

@router.callback_query(lambda c: c.data.startswith("package_"))
async def select_package(callback_query: types.CallbackQuery, state: FSMContext):
    logging.info(f"Package selected: {callback_query.data}")
    package = f"package_{callback_query.data.split('_')[1]}"  # Ensure valid key format
    
    # Save package info in user state
    await state.set_state(FormState.email)  # Set the next state to email
    await state.update_data(package=package)
    
    # Ask for email address after selecting the package
    await bot.send_message(callback_query.from_user.id, "Please provide your email address:")

    # Answer the callback to remove the loading state
    await callback_query.answer()

# Handle email input
@router.message(StateFilter(FormState.email))
async def handle_email(message: types.Message, state: FSMContext):
    logging.info(f"Email received: {message.text}")
    email = message.text
    
    # Save the email in the user's state
    await state.update_data(email=email)
    
    # Ask if it's a renewal or a new subscription
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[ 
            [InlineKeyboardButton(text="It's a renewal", callback_data="renewal_yes")],
            [InlineKeyboardButton(text="No, it's a new subscription", callback_data="renewal_no")]
        ]
    )
    await bot.send_message(message.from_user.id, "Is this a renewal or a new subscription?", reply_markup=keyboard)
    await state.set_state(FormState.renewal)

@router.callback_query(StateFilter(FormState.renewal))
async def renewal_check(callback_query: types.CallbackQuery, state: FSMContext):
    logging.info(f"Renewal check received: {callback_query.data}")
    renewal = callback_query.data.split("_")[1]

    if renewal == "yes":
        await bot.send_message(callback_query.from_user.id, "Please enter the usernames associated with the renewal (comma separated):")
        await state.set_state(FormState.renewal)  # Wait for usernames input
    else:
        await state.set_state(FormState.duration)  # ✅ Set correct state before asking for duration
        await ask_duration(callback_query)  # Proceed to duration selection

    await callback_query.answer()

@router.message(StateFilter(FormState.renewal))
async def handle_usernames_for_renewal(message: types.Message, state: FSMContext):
    usernames = message.text.split(",")  # Split usernames
    logging.info(f"Usernames for renewal: {usernames}")

    await state.update_data(usernames=usernames)  # Save usernames
    await state.set_state(FormState.duration)  # ✅ Move to duration selection

    await ask_duration(message)  # ✅ Ask duration only once

# Ask duration after renewal status
async def ask_duration(callback_query: types.CallbackQuery):
    logging.info("Asking for duration.")
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[ 
            [InlineKeyboardButton(text="1 Month", callback_data="duration_1")],
            [InlineKeyboardButton(text="3 Months", callback_data="duration_3")],
            [InlineKeyboardButton(text="6 Months", callback_data="duration_6")],
            [InlineKeyboardButton(text="12 Months", callback_data="duration_12")]
        ]
    )
    await bot.send_message(callback_query.from_user.id, "How long would you like the subscription for?", reply_markup=keyboard)

# Duration selection handler
@router.callback_query(StateFilter(FormState.duration))
async def select_duration(callback_query: types.CallbackQuery, state: FSMContext):
    logging.info(f"Received callback data: {callback_query.data}")

    try:
        user_data = await state.get_data()
        package = user_data.get("package")  # Retrieve selected package
        logging.info(f"User selected package: {package}")

        if callback_query.data.startswith("duration_"):
            duration = int(callback_query.data.split("_")[1])
            logging.info(f"Parsed duration: {duration}")

            # Restrict durations based on package selection
            if package in ["package_2", "package_3"] and duration != 12:
                logging.warning("Invalid duration selected for Package 2 or 3.")
                await bot.send_message(callback_query.from_user.id, "Only 12 months is available for this package.")
                return  # Stop execution if duration is not allowed

            # Save the duration in the FSM context
            await state.update_data(duration=duration)
            logging.info(f"Duration saved to state: {duration}")

            # Verify current state
            current_state = await state.get_state()
            logging.info(f"Current FSM state before transition: {current_state}")

            if current_state == FormState.duration:
                # Ask for the number of connections (1-5)
                await bot.send_message(callback_query.from_user.id, "How many connections would you like? (1-5)")

                # Update the state to move to the 'connections' step
                await state.set_state(FormState.connections)
                logging.info("State transitioned to FormState.connections.")

            await callback_query.answer()
            logging.info(f"Callback query answered for {callback_query.from_user.id}")

        else:
            logging.warning(f"Unexpected callback data format: {callback_query.data}")

    except Exception as e:
        logging.error(f"Error in select_duration handler: {e}")
        await bot.send_message(callback_query.from_user.id, "An error occurred while processing your request. Please try again.")

# Handle number of connections
@router.message(StateFilter(FormState.connections))
async def handle_connections(message: types.Message, state: FSMContext):
    logging.info(f"Connections received: {message.text}")
    try:
        connections = int(message.text)
    except ValueError:
        await message.answer("Please enter a valid number for connections (1-5).")
        return
    
    if not (1 <= connections <= 5):
        await message.answer("Please select a number of connections between 1 and 5.")
        return
    
    await state.update_data(connections=connections)
    
    # Ask for the internet provider
    await message.answer(f"Got it, {connections} connection(s) selected. Now, what internet provider do you use?")
    await state.set_state(FormState.internet_provider)

# Handle internet provider
@router.message(StateFilter(FormState.internet_provider))
async def handle_internet_provider(message: types.Message, state: FSMContext):
    logging.info(f"Internet provider received: {message.text}")
    internet_provider = message.text
    
    await state.update_data(internet_provider=internet_provider)
    
    # Ask for the device they are using
    await message.answer("Thank you! Now, what device are you using? (e.g., Firestick, Shield, Android Box, Smart Tv, IOS, Windows?)")
    await state.set_state(FormState.device)

# Handle device
@router.message(StateFilter(FormState.device))
async def handle_device(message: types.Message, state: FSMContext):
    logging.info(f"Device received: {message.text}")
    device = message.text
    
    await state.update_data(device=device)
    
    # Ask for the payment method
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[ 
            [InlineKeyboardButton(text="PayPal", callback_data="payment_paypal")],
            [InlineKeyboardButton(text="Bank Transfer", callback_data="payment_bank")],
            [InlineKeyboardButton(text="Bitcoin", callback_data="payment_bitcoin")]
        ]
    )
    await message.answer("What payment method would you like to use?", reply_markup=keyboard)
    await state.set_state(FormState.payment)

@router.callback_query(StateFilter(FormState.payment))
async def select_payment(callback_query: types.CallbackQuery, state: FSMContext):
    logging.info(f"Payment selected: {callback_query.data}")
    
    # Extract payment method
    payment_method = callback_query.data.split("_")[1]

    # Get user data from FSM context
    user_data = await state.get_data()
    package = user_data.get('package')
    duration = user_data.get('duration')
    connections = user_data.get('connections', 1)  # Default to 1 if not set
    email = user_data.get('email')
    renewal_usernames = user_data.get('usernames', [])
    internet_provider = user_data.get('internet_provider')
    device = user_data.get('device')

    # Check if package exists in pricing dictionary
    if package not in PRICES:
        await bot.send_message(callback_query.from_user.id, "Invalid package selected. Please restart the process.")
        return

    # Check if duration is valid for selected package
    if isinstance(PRICES[package], dict) and duration not in PRICES[package]:
        await bot.send_message(callback_query.from_user.id, "Invalid duration selected. Please restart the process.")
        return

    # Get base price
    base_price = PRICES[package][int(duration)]  

    # Connection pricing rules based on package and duration
    extra_connections_cost = 0
    max_connections = 1

    if package == "package_1":  # Bronze (Max 5 connections)
        max_connections = 5
        connection_prices = {
            1: 0,  # 1 connection is free
            2: {1: 10, 3: 15, 6: 20, 12: 25},
            3: {1: 20, 3: 30, 6: 40, 12: 50},
            4: {1: 30, 3: 45, 6: 60, 12: 75},
            5: {1: 40, 3: 60, 6: 80, 12: 100},
        }
        # Handle 1 connection separately to avoid AttributeError
        if connections == 1:
            extra_connections_cost = 0
        elif isinstance(connection_prices.get(connections), dict):  # For 2-5 connections
            extra_connections_cost = connection_prices.get(connections, {}).get(duration, 0)

    elif package == "package_2":  # Silver (Max 3 connections)
        max_connections = 5
        connection_prices = {2: 35, 3: 70, 4: 105, 5: 140}
        extra_connections_cost = connection_prices.get(connections, 0)

    elif package == "package_3":  # Gold (Max 3 connections)
        max_connections = 5
        connection_prices = {2: 20, 3: 40, 4: 60, 5: 80}
        extra_connections_cost = connection_prices.get(connections, 0)

    # Ensure user does not exceed max connections for their package
    if connections > max_connections:
        await bot.send_message(callback_query.from_user.id, f"⚠️ This package only allows up to {max_connections} connections.")
        return

    # Calculate total price
    total_price = base_price + extra_connections_cost

    # Send confirmation message to the user
    await bot.send_message(callback_query.from_user.id, f"Your order details:\n"
                                                       f"Package: {package}\n"
                                                       f"Duration: {duration} months\n"
                                                       f"Connections: {connections} (+£{extra_connections_cost} for extra connections)\n"
                                                       f"Payment Method: {payment_method.capitalize()}\n"
                                                       f"Total Price: £{total_price}\n"
                                                       f"Thank you for your order an admin will contact you shortly !")
    
    # Send order details to the admin
    user = callback_query.from_user
    info_message = (f"New Order Received:\n"
                    f"User: {user.first_name} (@{user.username})\n"
                    f"Package: {package}\n"
                    f"Duration: {duration} months\n"
                    f"Connections: {connections} (+£{extra_connections_cost} for extra connections)\n"
                    f"Payment Method: {payment_method.capitalize()}\n"
                    f"Total Price: £{total_price}\n"
                    f"Email: {email}\n"
                    f"Renewal Usernames: {', '.join(renewal_usernames) if renewal_usernames else 'N/A'}\n"
                    f"Internet Provider: {internet_provider}\n"
                    f"Device: {device}")
    
    # Send the information to the admin
    await bot.send_message(ADMIN_ID, info_message)

    # End the conversation
    await callback_query.answer()
    await state.finish()  # End FSM

# Run the bot
async def main():
    logging.info("Bot is running...")  # Debugging statement
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
