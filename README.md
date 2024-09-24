# Stock Tracker

This project is a Python-based Telegram bot for tracking users' stocks. It retrieves stock data and saves current statistics to a MySQL database for later use.

## Features

- **Stock Tracking**: Monitors stocks and their price changes.
- **Telegram Integration**: Notifies users about stock updates via Telegram bot.
- **Database Storage**: Saves stock data in a MySQL database for analytics and history tracking.

## Prerequisites

- Python 3.x
- MySQL Database
- Telegram Bot API token

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/burakpekisik/stock_tracker.git
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure your MySQL credentials and Telegram Bot API key in the userInfo.py file.

## Running the Bot

Run the bot with:
```bash
python main.py
```

## Folder Structure

```plaintext
├── daily_stock_table.py   # Script for managing daily stock data
├── main.py                # Entry point for the bot
├── stock_status.py        # Handles stock status and notifications
└── requirements.txt       # Python dependencies
```

## License

This project is licensed under the MIT License.
