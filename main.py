import requests
import sqlite3
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, types, executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Command
from aiogram.dispatcher.filters.state import State, StatesGroup
from dotenv import load_dotenv

load_dotenv()

api_token = os.getenv('API_TOKEN')

bot = Bot(token=api_token)

storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

class User:
    def __init__(self, telegram_id):
        self.telegram_id = telegram_id

    def check_user_data(self):
        conn = sqlite3.connect('./app_data/database.db')
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        result = cursor.fetchone()
        if result is None:
            conn.close()
            return None
        cursor.execute('SELECT * FROM users WHERE telegram_id = ?', (self.telegram_id,))
        result = cursor.fetchone()
        conn.close()
        return result

    def create_user_record(self):
        inserted_id = None
        if not self.check_user_data():
            conn = sqlite3.connect('./app_data/database.db')
            cursor = conn.cursor()
            cursor.execute('''CREATE TABLE IF NOT EXISTS users (telegram_id INTEGER PRIMARY KEY)''')
            cursor.execute('INSERT INTO users (telegram_id) VALUES (?)', (self.telegram_id,))
            inserted_id = cursor.lastrowid
            conn.commit()
            conn.close()   
        return inserted_id

class Stock:
    def __init__(self, owner_id, stock_id, quantity, unit_price, purchase_date):
        self.owner_id = owner_id
        self.stock_id = stock_id
        self.quantity = quantity
        self.unit_price = unit_price
        self.purchase_date = purchase_date
    
    def __eq__(self, other):
        if isinstance(other, Stock):
            return (
                self.owner_id == other.owner_id
                and self.stock_id == other.stock_id
                and self.quantity == other.quantity
                and self.unit_price == other.unit_price
                and self.purchase_date == other.purchase_date
            )
        return False

    def add_stock(self):
        conn = sqlite3.connect('./app_data/database.db')
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS stocks
                          (owner_id INTEGER, stock_id TEXT, quantity INTEGER, unit_price REAL, purchase_date TIMESTAMP, FOREIGN KEY (owner_id) REFERENCES users(telegram_id) ON DELETE CASCADE)''')
        values = (self.owner_id, self.stock_id, self.quantity, self.unit_price, self.purchase_date)
        cursor.execute('INSERT INTO stocks VALUES (?, ?, ?, ?, ?)', values)
        inserted_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return inserted_id

    def get_user_stocks(owner_id):
        stocks = []
        conn = sqlite3.connect('./app_data/database.db')
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='stocks'")
        result = cursor.fetchone()
        if result is None:
            conn.close()
            return stocks
        cursor.execute('SELECT * FROM stocks WHERE owner_id = ?', (owner_id,))
        result = cursor.fetchall()
        conn.close()

        for row in result:
            owner_id, stock_id, quantity, unit_price, purchase_date = row
            stock = Stock(owner_id, stock_id, quantity, unit_price, purchase_date)
            stocks.append(stock)

        return stocks

class CheckStockStates(StatesGroup):
    StockID = State()

class AddStockStates(StatesGroup):
    StockID = State()
    StockPrice = State()
    StockQuantity = State()

def check_stock_existance(stock_id: str) -> bool:
    url = f"https://iss.moex.com/iss/securities/{stock_id}.json"
    
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        exists = data.get("boards", {}).get("data", [])
        return bool(exists)
    else:
        return False

def get_stock_price(stock_id: str) -> float:
    url = f"https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR/securities/{stock_id}.json?iss.only=securities&securities.columns=PREVPRICE,CURRENCYID"

    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if len(data.get("securities", {}).get("data", [[]])) > 0:
            stock_currency = data.get("securities", {}).get("data", [[]])[0][1]
            if stock_currency == 'SUR':
                stock_currency = 'RUB'
            stock_price = data.get("securities", {}).get("data", [[]])[0][0]
            stock_result = str(stock_price) + ' ' + str(stock_currency)
            return stock_result
        else:
            return None
    else:
        return None

@dp.message_handler(Command('start'))
async def reg_user(message: types.Message):
    new_user = User(message.from_user.id)
    new_user.create_user_record()
    await message.reply('Добро пожаловать!')

@dp.message_handler(Command('checkStock'))
async def check_stock_start(message: types.Message):
    await message.reply('Введите идентификатор ценной бумаги')
    await CheckStockStates.StockID.set()

@dp.message_handler(state=CheckStockStates.StockID)
async def check_stock_id(message: types.Message, state: FSMContext):
    stock_id = message.text.upper()

    stock_exists = check_stock_existance(stock_id)
    if stock_exists is not False:
        stock_price = get_stock_price(stock_id)
        if stock_price is not None:
            await message.reply(f"Ценная бумага с идентификатором {stock_id} существует на Московской бирже. Текущий курс: {stock_price}")
        else:
            await message.reply(f"Ценная бумага с идентификатором {stock_id} не найдена на Московской бирже.")
    else:
        await message.reply(f"Ценная бумага с идентификатором {stock_id} не найдена на Московской бирже.")

    await state.finish()

@dp.message_handler(Command('addStock'))
async def check_stock_start(message: types.Message):
    await message.reply('Преступим к добавлению ценной бумаги')
    await bot.send_message(message.chat.id, 'Введите идентификатор приобретенного инструмента')
    await AddStockStates.StockID.set()

@dp.message_handler(state=AddStockStates.StockID)
async def add_stock_id(message: types.Message, state: FSMContext):
    if message.text != "/stop" and message.text != "/STOP":
        stock_exists = check_stock_existance(message.text)
        if stock_exists is not False:
            await bot.send_message(message.chat.id, 'Введите стоимость единицы ценной бумаги')
            async with state.proxy() as data:
                data['StockID'] = message.text
            await AddStockStates.StockPrice.set()
        else:
            await message.reply('Указанный иденификатор ценной бумаги не найден на Московской бирже')
            await bot.send_message(message.chat.id, 'Введите корректный идентификатор приобретенного инструмента или введите /stop для отмены')
    else:
        await state.finish()
        await message.reply('Добавление информации о приобретенной ценной бумаге отменено')

@dp.message_handler(state=AddStockStates.StockPrice)
async def add_stock_id(message: types.Message, state: FSMContext):
    if message.text != '/stop' and message.text != '/STOP':
        try:
            float(message.text.replace(',', '.'))
            await bot.send_message(message.chat.id, 'Введите количество приобретенных единиц инструмента')
            async with state.proxy() as data:
                data['StockPrice'] = message.text.replace(',', '.')
            await AddStockStates.StockQuantity.set()
        except:
             await message.reply('Вы некорректно указали стоимость одной ценной бумаги.')
             await bot.send_message(message.chat.id, 'Введите стоимость приобретения в числовом формате или введите /stop для отмены"')
        
    else:
        await state.finish()
        await message.reply('Добавление информации о приобретенной ценной бумаге отменено')

@dp.message_handler(state=AddStockStates.StockQuantity)
async def add_stock_id(message: types.Message, state: FSMContext):
    if message.text != "/stop" and message.text != "/STOP":
        try:
            int(message.text)
            async with state.proxy() as data:
                data['StockQuantity'] = message.text
                data['StockOwnerID'] = message.from_user.id
                data['StockPurchaseDate'] = datetime.now()
            StockRecord = Stock(data['StockOwnerID'], data['StockID'], data['StockPrice'], data['StockQuantity'], data['StockPurchaseDate'])
            StockRecord.add_stock()
            await state.finish()
            await bot.send_message(message.chat.id, 'Информация о приобретенной ценной бумаге успешно сохранена!')
        except:
             await message.reply('Вы некорректно указали количество приобретенных единиц ценной бумаги.')
             await bot.send_message(message.chat.id, 'Введите количество в виде целого числа или введите /stop для отмены"')
    
    else:
        await state.finish()
        await message.reply('Добавление информации о приобретенной ценной бумаге отменено')

@dp.message_handler(Command('checkPortfolioSummary'))
async def check_portfolio(message: types.Message):
    user_stocks = Stock.get_user_stocks(message.from_user.id)
    portfolio_price = 0
    portfolio_stocks_count = 0
    for stock in user_stocks:
        stock_price = int(stock.quantity) * float(stock.unit_price)
        portfolio_price += stock_price
        portfolio_stocks_count += 1
    await message.reply(f'Вы приобрели {portfolio_stocks_count} раз, на общую сумму {portfolio_price} RUB')

@dp.message_handler(Command('test'))
async def test(message: types.Message):
    return_message = User(message.from_user.id).check_user_data()
    await message.reply(return_message)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)

