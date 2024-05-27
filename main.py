#!/usr/bin/env python
# pylint: disable=unused-argument
# This program is dedicated to the public domain under the CC0 license.

"""
Basic example for a bot that uses inline keyboards. For an in-depth explanation, check out
 https://github.com/python-telegram-bot/python-telegram-bot/wiki/InlineKeyboard-Example.
"""

import asyncio
import logging
from datetime import datetime
import yfinance as yf
import mysql.connector
from tabulate import tabulate
from telegram.constants import ParseMode
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ConversationHandler, MessageHandler, filters, CallbackContext
import userInfo

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

mydb = mysql.connector.connect(
    host=userInfo.HOST,
    user=userInfo.USERNAME,
    password=userInfo.PASSWORD,
    database=userInfo.DATABASE
)

SELECTING_OPTION, ADDING_STOCK, DELETING_STOCK, UPDATING_STOCK, EDITING_STOCK, VIEWING_STOCKS, END = range(7)

async def start(update: Update, context: CallbackContext) -> int:
    """Sends a message with three inline buttons attached."""
    keyboard = [
        [
            InlineKeyboardButton("Hisse Ekle", callback_data=str(ADDING_STOCK)),
            InlineKeyboardButton("Hisseleri Düzenle", callback_data=str(EDITING_STOCK)),
            InlineKeyboardButton("Hisse Sil", callback_data=str(DELETING_STOCK)),
        ],
        [InlineKeyboardButton("Hisseleri Görüntüle", callback_data=str(VIEWING_STOCKS))],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("Lütfen bir seçenek seçin:", reply_markup=reply_markup)

    return SELECTING_OPTION

async def view_stocks(update: Update, context: CallbackContext) -> int:
    """Displays the user's stocks with current prices and profit/loss in a table."""
    user_id = update.effective_user.id

    # Connect to MySQL database
    mycursor = mydb.cursor()

    # Check if table exists for the user
    table_name = f"user_{user_id}"
    mycursor.execute(f"SHOW TABLES LIKE '{table_name}'")
    table_exists = mycursor.fetchone()

    if table_exists:
        # Select the stocks of the user
        mycursor.execute(f"SELECT stock_code, stock_cost, stock_quantity FROM {table_name}")
        stocks = mycursor.fetchall()

        if stocks:
            # Prepare data for tabulate
            headers = ["Hisse Kodu", "Maliyet", "Adet", "Mevcut Fiyat", "Kar/Zarar", "Günlük Kar/Zarar", "Günlük Değişim"]
            stock_data = []

            for stock in stocks:
                stock_code = stock[0]
                stock_cost = stock[1]
                stock_quantity = stock[2]

                # Get current price from Yahoo Finance
                stock_info = yf.Ticker(stock_code)
                current_price = stock_info.history(period="1d")["Close"].iloc[-1]

                # Get previous day's closing price
                previous_close = stock_info.history(period="2d")["Close"].iloc[-2]

                # Calculate profit/loss
                profit_loss = (current_price - stock_cost) * stock_quantity

                # Calculate daily profit/loss and percentage change
                daily_change = ((current_price - previous_close) / previous_close) * 100
                daily_profit_loss = profit_loss * daily_change / 100

                # Format daily change
                if daily_change > 0:
                    daily_change_str = f"+%{daily_change:.2f}"
                elif daily_change < 0:
                    daily_change = abs(daily_change)
                    daily_change_str = f"-%{daily_change:.2f}"
                else:
                    daily_change_str = "%0.00"

                stock_data.append([stock_code, stock_cost, stock_quantity, current_price, profit_loss, daily_profit_loss, daily_change_str])

            # Format data as a table
            table = tabulate(stock_data, headers=headers, tablefmt="pipe")
            total_portfolio_value, profit_percentage = await calculate_portfolio(str(table_name))

            if float(profit_percentage) > 0:
                profit_percentage_str = f"+%{profit_percentage:.2f}"
            elif profit_percentage < 0:
                profit_percentage = abs(profit_percentage)
                profit_percentage_str = f"-%{profit_percentage:.2f}"
            else:
                profit_percentage_str = "%0.00"
            print(profit_percentage_str)

            # Send the table to the user
            await update.callback_query.message.reply_text(f"Toplam portföy değeriniz: {total_portfolio_value}\nGünlük portföy büyümeniz: {profit_percentage_str}")
            await update.callback_query.message.reply_text(f"<pre>{table}</pre>", parse_mode=ParseMode.HTML)
        else:
            await update.callback_query.message.reply_text("Henüz hisse bulunmamaktadır.")
    else:
        await update.callback_query.message.reply_text("Hisse bulunmamaktadır.")

    return END

#TODO: Her gün akşam 6.30'da bu işlem gerçekleşsin 
async def calculate_portfolio(is_daily_table: bool) -> float:
    """Calculates total value of all portfolios."""

    # MySQL veritabanı bağlantısı
    mycursor = mydb.cursor()

    # Kullanıcı tablolarını al
    mycursor.execute("SHOW TABLES LIKE 'user_%'")
    user_tables = mycursor.fetchall()

    # Her bir kullanıcının portföy değerini hesapla
    for user_table in user_tables:
        user_id = user_table[0].split('_')[1]  # Kullanıcı ID'si
        mycursor.execute(f"SELECT stock_code, stock_quantity FROM {user_table[0]}")
        print(user_table[0])
        print("Sorgu gönderilen tablo:", user_table[0])
        user_stocks = mycursor.fetchall()
        print(user_stocks)

        total_portfolio_value = 0
        previous_portfolio_value = 0

        for stock in user_stocks:
            stock_code = stock[0]
            stock_quantity = stock[1]

            # Hisse senedinin güncel fiyatını al
            stock_data = yf.Ticker(stock_code)
            current_price = stock_data.history(period="1d")["Close"].iloc[-1]
            # Önceki günün fiyatını al
            previous_price = stock_data.history(period="2d")["Close"].iloc[-2]

            # Portföy değerini güncelle
            total_portfolio_value += current_price * stock_quantity
            previous_portfolio_value += previous_price * stock_quantity

        # Portföy değerlerini yuvarla
        total_portfolio_value = round(total_portfolio_value, 2)
        previous_portfolio_value = round(previous_portfolio_value, 2)

        # Kar oranını hesapla
        if previous_portfolio_value != 0:
            profit_percentage = ((total_portfolio_value - previous_portfolio_value) / previous_portfolio_value) * 100
        else:
            profit_percentage = 0

        if (is_daily_table):
            create_daily_table(user_id, float(total_portfolio_value), str(profit_percentage))  # total_portfolio_value'yi float'a dönüştür

        print(f"Kullanıcı {user_id} portföy değeri: {total_portfolio_value}")
        print(f"Önceki gün portföy değeri: {previous_portfolio_value}")
        print(f"Kullanıcı {user_id} kar oranı: {profit_percentage:.2f}%")

        # Veritabanı bağlantısını kapat
        mycursor.close()
        return total_portfolio_value, profit_percentage
    
async def calculate_portfolio(user_id: str) -> float:
    """Calculates total value of desired portfolio."""
    # MySQL veritabanı bağlantısı
    mycursor = mydb.cursor()

    mycursor.execute(f"SELECT stock_code, stock_quantity FROM {user_id}")
    print(user_id)
    print("Sorgu gönderilen tablo:", user_id)
    user_stocks = mycursor.fetchall()
    print(user_stocks)

    total_portfolio_value = 0
    previous_portfolio_value = 0

    for stock in user_stocks:
        stock_code = stock[0]
        stock_quantity = stock[1]

        # Hisse senedinin güncel fiyatını al
        stock_data = yf.Ticker(stock_code)
        current_price = stock_data.history(period="1d")["Close"].iloc[-1]
        # Önceki günün fiyatını al
        previous_price = stock_data.history(period="2d")["Close"].iloc[-2]

        # Portföy değerini güncelle
        total_portfolio_value += current_price * stock_quantity
        previous_portfolio_value += previous_price * stock_quantity

    # Portföy değerlerini yuvarla
    total_portfolio_value = round(total_portfolio_value, 2)
    previous_portfolio_value = round(previous_portfolio_value, 2)

    # Kar oranını hesapla
    if previous_portfolio_value != 0:
        profit_percentage = ((total_portfolio_value - previous_portfolio_value) / previous_portfolio_value) * 100
    else:
        profit_percentage = 0

    print(f"Kullanıcı {user_id} portföy değeri: {total_portfolio_value}")
    print(f"Önceki gün portföy değeri: {previous_portfolio_value}")
    print(f"Kullanıcı {user_id} kar oranı: {profit_percentage:.2f}%")

    # Veritabanı bağlantısını kapat
    mycursor.close()
    return total_portfolio_value, profit_percentage

async def create_daily_table(usr_id: str, total_portfolio_value: float, profit_percentage: str) -> None:
    """Creates daily track table for profits."""
    usr_id = "user_" + usr_id

    todays_date = str(datetime.now().strftime("%d/%m/%Y"))

    # Veritabanı cursor oluştur
    mycursor = mydb.cursor()

    # user_profits tablosunu oluştur
    mycursor.execute("CREATE TABLE IF NOT EXISTS profits_user ( \
                        id INT AUTO_INCREMENT PRIMARY KEY, \
                        user_id VARCHAR(255), \
                        date VARCHAR(255), \
                        profit VARCHAR(255), \
                        portfolio_value FLOAT \
                    )")
    
    # Profiti belirli bir formatta kaydet
    profit_percentage_formatted = "{:.2f}".format(float(profit_percentage))

    sql = "INSERT INTO profits_user (user_id, date, profit, portfolio_value) VALUES (%s, %s, %s, %s)"
    val = (usr_id, todays_date, profit_percentage_formatted, total_portfolio_value)  # profit_percentage'yi formatla
    mycursor.execute(sql, val)

    # Değişiklikleri onayla
    mydb.commit()

    # Bağlantıyı kapat
    mycursor.close()

async def add_stock(update: Update, context: CallbackContext) -> int:
    """Asks for the stock details and adds it to the database."""
    await update.callback_query.message.edit_text("Lütfen hissenin kodunu girin:")
    return ADDING_STOCK

async def add_stock_details(update: Update, context: CallbackContext) -> int:
    """Adds the stock details to the database."""
    user_id = update.effective_user.id
    stock_code = update.message.text
    context.user_data["stock_code"] = stock_code

    await update.message.reply_text("Lütfen hissenin maliyetini girin:")
    return UPDATING_STOCK  # Bu satırı ekleyin


async def update_stock(update: Update, context: CallbackContext) -> int:
    """Updates the stock details in the database."""
    context.user_data["stock_cost"] = update.message.text

    await update.message.reply_text("Lütfen hissenin adetini girin:")
    return EDITING_STOCK

async def edit_stock(update: Update, context: CallbackContext) -> int:
    """Edits the stock details in the database."""
    context.user_data["stock_quantity"] = update.message.text

    user_id = update.effective_user.id
    stock_code = context.user_data["stock_code"]
    stock_cost = context.user_data["stock_cost"]
    stock_quantity = context.user_data["stock_quantity"]

    mycursor = mydb.cursor()

    # Check if table exists for the user, if not create one
    table_name = f"user_{user_id}"
    mycursor.execute(f"CREATE TABLE IF NOT EXISTS {table_name} (id INT AUTO_INCREMENT PRIMARY KEY, stock_code VARCHAR(255), stock_cost FLOAT, stock_quantity INT)")

    # Insert the stock details into the user's table
    sql = "INSERT INTO {} (stock_code, stock_cost, stock_quantity) VALUES (%s, %s, %s)".format(table_name)
    val = (stock_code, stock_cost, stock_quantity)
    mycursor.execute(sql, val)

    mydb.commit()

    await update.message.reply_text("Hisse başarıyla eklendi.")

    return END

async def delete_stock(update: Update, context: CallbackContext) -> int:
    """Displays the user's stocks in a table and asks for the stock code to delete from the database."""
    user_id = update.effective_user.id

    mycursor = mydb.cursor()

    # Check if table exists for the user
    table_name = f"user_{user_id}"
    mycursor.execute(f"SHOW TABLES LIKE '{table_name}'")
    table_exists = mycursor.fetchone()

    if table_exists:
        # Select the stocks of the user
        mycursor.execute(f"SELECT stock_code, stock_cost, stock_quantity FROM {table_name}")
        stocks = mycursor.fetchall()

        if stocks:
            # Prepare data for tabulate
            headers = ["Hisse Kodu", "Maliyet", "Adet"]
            stock_data = [[stock[0], stock[1], stock[2]] for stock in stocks]

            # Format data as a table
            table = tabulate(stock_data, headers=headers, tablefmt="pipe")

            # Send the table to the user
            await update.callback_query.message.reply_text(f"<pre>{table}</pre>", parse_mode=ParseMode.HTML)
            await update.callback_query.message.reply_text("Lütfen silmek istediğiniz hissenin kodunu girin:")

            # Transition to the DELETING_STOCK state
            return DELETING_STOCK
        else:
            await update.callback_query.message.reply_text("Henüz hisse bulunmamaktadır.")
    else:
        await update.callback_query.message.reply_text("Hisse bulunmamaktadır.")

    return END

async def delete_stock_confirm(update: Update, context: CallbackContext) -> int:
    """Deletes the stock from the database."""
    user_id = update.effective_user.id
    stock_code = update.message.text

    mycursor = mydb.cursor()

    # Check if table exists for the user
    table_name = f"user_{user_id}"
    mycursor.execute(f"SHOW TABLES LIKE '{table_name}'")
    table_exists = mycursor.fetchone()

    if table_exists:
        # Delete the stock from the user's table
        sql = "DELETE FROM {} WHERE stock_code = %s".format(table_name)
        val = (stock_code,)
        mycursor.execute(sql, val)

        mydb.commit()

        await update.message.reply_text("Hisse başarıyla silindi.")
    else:
        await update.message.reply_text("Hisse silinemedi, tablo bulunamadı.")

    return END

async def edit_stocks(update: Update, context: CallbackContext) -> int:
    """Asks for the stock code to edit its details."""
    await update.callback_query.message.edit_text("Lütfen düzenlemek istediğiniz hissenin kodunu girin:")
    return EDITING_STOCK

async def cancel(update: Update, context: CallbackContext) -> int:
    """Cancels the conversation."""
    await update.message.reply_text("İşlem iptal edildi.")
    return END

def main() -> None:
    """Run the bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(userInfo.TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            SELECTING_OPTION: [
                CallbackQueryHandler(add_stock, pattern='^' + str(ADDING_STOCK) + '$'),
                CallbackQueryHandler(delete_stock, pattern='^' + str(DELETING_STOCK) + '$'),
                CallbackQueryHandler(edit_stocks, pattern='^' + str(EDITING_STOCK) + '$'),
                CallbackQueryHandler(view_stocks, pattern='^' + str(VIEWING_STOCKS) + '$')
            ],
            ADDING_STOCK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_stock_details)
            ],
            UPDATING_STOCK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, update_stock)
            ],
            EDITING_STOCK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_stock)
            ],
            DELETING_STOCK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, delete_stock_confirm)
            ],
            VIEWING_STOCKS: [
                CallbackQueryHandler(view_stocks, pattern='^' + str(VIEWING_STOCKS) + '$')
            ],
            END: []
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(add_stock, pattern='^' + str(ADDING_STOCK) + '$'))
    application.add_handler(CallbackQueryHandler(delete_stock, pattern='^' + str(DELETING_STOCK) + '$'))
    application.add_handler(CallbackQueryHandler(edit_stocks, pattern='^' + str(EDITING_STOCK) + '$'))

    # Add the /start command handler outside of the conversation handler
    application.add_handler(CommandHandler('start', start))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
