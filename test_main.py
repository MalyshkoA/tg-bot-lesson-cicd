import sqlite3
import unittest
from unittest import mock
import requests
import main as bot

class UserTestCase(unittest.TestCase):

    check_telegram_id = 999999999999
    create_telegram_id = 999999999998


    def setUp(self) -> None:
        conn = sqlite3.connect('./app_data/database.db')
        cursor = conn.cursor()
        cursor.execute('CREATE TABLE IF NOT EXISTS users (telegram_id INTEGER PRIMARY KEY)')
        cursor.execute('INSERT INTO users (telegram_id) VALUES (?)', (self.check_telegram_id,))
        conn.commit()
        conn.close

    def tearDown(self) -> None:
        conn = sqlite3.connect('./app_data/database.db')
        cursor = conn.cursor()
        cursor.execute('DELETE FROM users WHERE telegram_id = ?', (self.check_telegram_id,))
        cursor.execute('DELETE FROM users WHERE telegram_id = ?', (self.create_telegram_id,))
        conn.commit()
        conn.close

    def test_check_user_data(self):
        user = bot.User(self.check_telegram_id)
        result = user.check_user_data()
        self.assertEqual(result, (self.check_telegram_id,))

    def test_create_user_record(self):
        user = bot.User(self.create_telegram_id)
        result = user.create_user_record()
        self.assertEqual(result, self.create_telegram_id)

class StockTestCase(unittest.TestCase):

    check_telegram_id = 999999999999
    create_telegram_id = 999999999998

    create_stock = bot.Stock(create_telegram_id, 'SBER', 100, 10, '2024-10-10 03:09:21.123454')

    test_stock_values = (check_telegram_id, 'SBER', 100, 10, '2024-10-10 03:09:21.123454')

    def setUp(self) -> None:
        conn = sqlite3.connect('./app_data/database.db')
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (telegram_id INTEGER PRIMARY KEY)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS stocks
                          (owner_id INTEGER, stock_id TEXT, quantity INTEGER, unit_price REAL, purchase_date TIMESTAMP, FOREIGN KEY (owner_id) REFERENCES users(telegram_id) ON DELETE CASCADE)''')
        cursor.execute('INSERT INTO users (telegram_id) VALUES (?)', (self.check_telegram_id,))
        cursor.execute('INSERT INTO stocks VALUES (?, ?, ?, ?, ?)', self.test_stock_values)
        conn.commit()
        conn.close()

    def tearDown(self) -> None:
        conn = sqlite3.connect('./app_data/database.db')
        cursor = conn.cursor()
        cursor.execute('DELETE FROM users WHERE telegram_id = ?', (self.check_telegram_id,))
        cursor.execute('DELETE FROM stocks WHERE owner_id = ?', (self.check_telegram_id,))
        cursor.execute('DELETE FROM users WHERE telegram_id = ?', (self.create_telegram_id,))
        cursor.execute('DELETE FROM stocks WHERE owner_id = ?', (self.create_telegram_id,))
        conn.commit()
        conn.close()

    def test_add_stock(self):
        result = []
        bot.Stock.add_stock(self.create_stock)
        conn = sqlite3.connect('./app_data/database.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM stocks WHERE owner_id = ?', (self.create_telegram_id,))
        result = cursor.fetchall()
        conn.close()
        self.assertNotEqual(result, [])

    def test_get_user_stocks(self):
        result = bot.Stock.get_user_stocks(self.check_telegram_id)
        self.assertIsNotNone(result)

class CheckStockExistance(unittest.TestCase):

    test_stock_id = 'SBER'
    test_url = f'https://iss.moex.com/iss/securities/{test_stock_id}.json'
    test_reponse = {'boards': {'data': [['SBER']]}}

    def test_check_stock_existance(self):

        with mock.patch('requests.get') as mock_get:

            mock_response_success = mock.Mock()
            mock_response_success.status_code = 200
            mock_response_success.json.return_value = self.test_reponse

            mock_response_fail = mock.Mock()
            mock_response_fail.status_code = 404
            mock_response_fail.json.return_value = None

            mock_get.return_value = mock_response_success
            result_success = bot.check_stock_existance(self.test_stock_id)
            self.assertTrue(result_success)
            mock_get.assert_called_once_with(self.test_url)

            mock_get.return_value = mock_response_fail
            result_fail = bot.check_stock_existance(self.test_stock_id)
            self.assertFalse(result_fail)
            mock_get.assert_called_with(self.test_url)

if __name__ == '__main__':
    unittest.main()
