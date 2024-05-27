import asyncio
from datetime import datetime
import mysql.connector
import yfinance as yf
from tabulate import tabulate
from telegram.constants import ParseMode
from telegram.ext import Updater, CommandHandler, Application
import userInfo

# Global variable to keep track of last run date
last_run_date = None

# MySQL database connection
mydb = mysql.connector.connect(
    host=userInfo.HOST,
    user=userInfo.USERNAME,
    password=userInfo.PASSWORD,
    database=userInfo.DATABASE
)

async def start_command(update, context):
    await update.message.reply_text('Bot started!')

# Function to schedule and view stocks
async def schedule_view_stocks(application):
    global last_run_date
    now = datetime.now()
    if last_run_date is None or (now - last_run_date).days >= 1:
        if now.weekday() < 5 and (now.hour < 23 or (now.hour == 23 and now.minute < 30)):
            print("Sending Stock Table")
            await send_stock_table(application)
            last_run_date = now
        else:
            today = datetime.now().strftime("%A")
            print(f"Not the right time to send stock table. Waiting for the next suitable day. Day: {today}, Time: {now.hour}:{now.minute}")
    else:
        print("Daily stock table has already been sent today.")
# Function to send stock table to users
async def send_stock_table(application):
    mycursor = mydb.cursor()

    mycursor.execute("SHOW TABLES LIKE 'user_%'")
    user_tables = mycursor.fetchall()

    for user_table in user_tables:
        user_id = user_table[0].split('_')[1]
        print("Sorgu gönderilen tablo:", user_table[0])
        table_name = f"user_{user_id}"
        mycursor.execute(f"SHOW TABLES LIKE '{table_name}'")
        table_exists = mycursor.fetchone()

        if table_exists:
            mycursor.execute(f"SELECT stock_code, stock_cost, stock_quantity FROM {table_name}")
            stocks = mycursor.fetchall()

            if stocks:
                headers = ["Hisse Kodu", "Maliyet", "Adet", "Mevcut Fiyat", "Kar/Zarar", "Günlük Kar/Zarar", "Günlük Değişim"]
                stock_data = []

                for stock in stocks:
                    stock_code = stock[0]
                    stock_cost = stock[1]
                    stock_quantity = stock[2]

                    stock_info = yf.Ticker(stock_code)
                    current_price = stock_info.history(period="1d")["Close"].iloc[-1]
                    previous_close = stock_info.history(period="2d")["Close"].iloc[-2]
                    profit_loss = (current_price - stock_cost) * stock_quantity
                    daily_change = ((current_price - previous_close) / previous_close) * 100
                    daily_profit_loss = profit_loss * daily_change / 100

                    if daily_change > 0:
                        daily_change_str = f"+%{daily_change:.2f}"
                    elif daily_change < 0:
                        daily_change = abs(daily_change)
                        daily_change_str = f"-%{daily_change:.2f}"
                    else:
                        daily_change_str = "%0.00"

                    stock_data.append([stock_code, stock_cost, stock_quantity, current_price, profit_loss, daily_profit_loss, daily_change_str])

                table = tabulate(stock_data, headers=headers, tablefmt="pipe")
                total_portfolio_value, profit_percentage = await calculate_portfolio(str(table_name))

                if float(profit_percentage) > 0:
                    profit_percentage_str = f"+%{profit_percentage:.2f}"
                elif profit_percentage < 0:
                    profit_percentage = abs(profit_percentage)
                    profit_percentage_str = f"-%{profit_percentage:.2f}"
                else:
                    profit_percentage_str = "%0.00"

                await application.bot.send_message(user_id, f"Toplam portföy değeriniz: {total_portfolio_value}\nGünlük portföy büyümeniz: {profit_percentage_str}")
                await application.bot.send_message(user_id, f"<pre>{table}</pre>", parse_mode=ParseMode.HTML)
                print(f"Stock Table Sent to User {user_id}")
            else:
                await application.bot.send_message(user_id, f"{user_id} kullanıcısının hissesi bulunmamaktadır.")
        else:
            await application.bot.send_message(user_id, "Hisse bulunmamaktadır.")

    mycursor.close()

# Function to calculate portfolio
async def calculate_portfolio(user_id):
    mycursor = mydb.cursor()

    mycursor.execute(f"SELECT stock_code, stock_quantity FROM {user_id}")
    user_stocks = mycursor.fetchall()

    total_portfolio_value = 0
    previous_portfolio_value = 0

    for stock in user_stocks:
        stock_code = stock[0]
        stock_quantity = stock[1]

        stock_data = yf.Ticker(stock_code)
        current_price = stock_data.history(period="1d")["Close"].iloc[-1]
        previous_price = stock_data.history(period="2d")["Close"].iloc[-2]

        total_portfolio_value += current_price * stock_quantity
        previous_portfolio_value += previous_price * stock_quantity

    total_portfolio_value = round(total_portfolio_value, 2)
    previous_portfolio_value = round(previous_portfolio_value, 2)

    if previous_portfolio_value != 0:
        profit_percentage = ((total_portfolio_value - previous_portfolio_value) / previous_portfolio_value) * 100
    else:
        profit_percentage = 0

    mycursor.close()
    return total_portfolio_value, profit_percentage

# Function for the scheduled task
async def scheduled_task(application):
    while True:
        print("Scheduled Task Called")
        await schedule_view_stocks(application)
        await asyncio.sleep(60)

# Main function
def main():
    application = Application.builder().token(userInfo.TOKEN).build()

    # Commands
    application.add_handler(CommandHandler('start', start_command))

    # Run bot
    asyncio.get_event_loop().run_until_complete(scheduled_task(application))

if __name__ == '__main__':
    main()
