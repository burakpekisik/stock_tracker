import asyncio
from datetime import datetime, time
from telegram import Bot
from telegram.constants import ParseMode
import mysql.connector
from tabulate import tabulate
import yfinance as yf
import logging
import userInfo

# Telegram bot token
TOKEN = userInfo.TOKEN

logger = logging.getLogger(__name__)

mydb = mysql.connector.connect(
    host=userInfo.HOST,
    user=userInfo.USERNAME,
    password=userInfo.PASSWORD,
    database=userInfo.DATABASE
)

# Function to fetch stocks for a user from the database
async def get_user_stocks(user_id):
    mycursor = mydb.cursor()
    table_name = f"user_{user_id}"
    mycursor.execute(f"SELECT stock_code, stock_cost, stock_quantity FROM {table_name}")
    return mycursor.fetchall()

# Function to format stocks data into a table
async def format_stocks_data(stocks):
    headers = ["Hisse Kodu", "Günlük Değişim (%)"]
    stock_data = []
    for stock in stocks:
        stock_code, stock_cost, stock_quantity = stock
        daily_change_percentage = await calculate_daily_change_percentage(stock_code, stock_cost)
        stock_data.append([stock_code, daily_change_percentage])
    return tabulate(stock_data, headers=headers, tablefmt="pipe")

# Function to send stocks table to a user
async def send_stocks_table(bot, user_id, stocks_table):
    user = await bot.get_chat(user_id)
    await bot.send_message(chat_id=user_id, text=f"<pre>{stocks_table}</pre>", parse_mode=ParseMode.HTML)
    print(f"Message Was Sent to {user.first_name}")

# Function to send stocks table to all users
async def send_stocks_tables_to_all_users(bot):  # Bot parametresi eklendi
    # Connect to MySQL database
    mycursor = mydb.cursor()

    # Get all user IDs from the database
    mycursor.execute("SHOW TABLES")
    tables = mycursor.fetchall()

    # Loop through each user table and send stocks table
    for table in tables:
        if table[0].startswith("user_"):  # Kullanıcı tablolarını kontrol et
            user_id = int(table[0][5:])  # User ID'yi çıkar
            stocks = await get_user_stocks(user_id)
            if stocks:
                stocks_table = await format_stocks_data(stocks)
                await send_stocks_table(bot, user_id, stocks_table)

# Function to check if current time is within the specified time range
def is_within_time_range(start_time, end_time):
    now = datetime.now().time()
    return start_time <= now <= end_time

# Function to calculate the daily change percentage for a stock
async def calculate_daily_change_percentage(stock_code: str, stock_cost: float) -> str:
    """Calculates the daily change percentage for a given stock."""
    try:
        # Get stock data from Yahoo Finance
        stock_data = yf.Ticker(stock_code)
        hist = stock_data.history(period="2d")

        # Get yesterday's closing price
        yesterday_close = hist.iloc[0]["Close"]

        # Get today's latest price
        latest_price = hist.iloc[1]["Close"]

        # Calculate daily change percentage
        change_percentage = ((latest_price - yesterday_close) / yesterday_close) * 100

        # Format the change percentage string
        change_percentage_str = f"{change_percentage:.2f}%"

        return change_percentage_str
    except Exception as e:
        logger.error(f"Error calculating daily change percentage for {stock_code}: {e}")
        return "N/A"


# Main function
async def main():
    # Initialize Telegram Bot
    bot = Bot(token=TOKEN)

    # Define the time range for sending messages (10:30 to 19:00)
    start_time = time(10, 30)
    end_time = time(23, 0)

    # Run the loop indefinitely
    while True:
        # Check if current time is within the specified time range
        if is_within_time_range(start_time, end_time):
            # Send stocks tables to all users
            await send_stocks_tables_to_all_users(bot)  # Bot parametresi eklendi

        # Wait for an hour before checking the time again
        await asyncio.sleep(3600)  # Sleep for 1 hour

# Run the main function
asyncio.run(main())
