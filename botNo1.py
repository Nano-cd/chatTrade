import json
import ccxt
import pandas as pd
import numpy as np
from datetime import datetime
import time
from sklearn.model_selection import GridSearchCV
from sklearn.metrics import make_scorer


def get_data(symbol, timeframe, limit):
    try:

        with open('config.json', 'r') as f:
            config = json.load(f)

        exchange = ccxt.okx({
            'apiKey': config['okx']['apiKey'],
            'secret': config['okx']['secret'],
            'password': config['okx']['password'],
        })

        exchange.httpProxy = 'http://127.0.0.1:33210'
        # exchange.load_markets()
        # symbols = exchange.symbols
        # print(symbols)

        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.to_excel('output.xlsx', index=False)  # 保存为 Excel 文件
        return df

    except Exception as e:
        print(f"获取数据错误: {str(e)}")
        return None


def strategy(df, rsi_period=14, ma_period=20, rsi_oversold=30, rsi_overbought=70):
    def calculate_rsi(data, periods=14):
        delta = data.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=periods).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=periods).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    df['MA'] = df['close'].rolling(window=ma_period).mean()
    df['RSI'] = calculate_rsi(df['close'], rsi_period)

    signals = pd.Series(index=df.index, data=0)
    buy_condition = (df['RSI'] < rsi_oversold) & (df['close'] > df['MA'])
    signals[buy_condition] = 1
    sell_condition = (df['RSI'] > rsi_overbought) & (df['close'] < df['MA'])
    signals[sell_condition] = -1

    return signals


def optimize_strategy(historical_data):
    """
    优化策略参数
    """

    def evaluate_strategy(data, params):
        rsi_period, ma_period, rsi_oversold, rsi_overbought = params
        signals = strategy(data, rsi_period, ma_period, rsi_oversold, rsi_overbought)
        returns = data['close'].pct_change() * signals.shift(1)
        return returns.sum()

    param_grid = {
        'rsi_period': range(10, 30, 2),
        'ma_period': range(10, 50, 5),
        'rsi_oversold': range(20, 40, 5),
        'rsi_overbought': range(60, 80, 5)
    }

    best_params = None
    best_return = float('-inf')

    for rsi_p in param_grid['rsi_period']:
        for ma_p in param_grid['ma_period']:
            for rsi_os in param_grid['rsi_oversold']:
                for rsi_ob in param_grid['rsi_overbought']:
                    params = (rsi_p, ma_p, rsi_os, rsi_ob)
                    returns = evaluate_strategy(historical_data, params)
                    if returns > best_return:
                        best_return = returns
                        best_params = params

    return best_params


def main():
    # 读取配置
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
    except Exception as e:
        print(f"读取配置文件错误: {str(e)}")
        return

    symbol = 'DOGE/USDT'
    timeframe = '1h'

    while True:
        try:

            historical_data = get_data(symbol, timeframe, 1000)
            if historical_data is None:
                continue

            best_params = optimize_strategy(historical_data)

            latest_data = get_data(symbol, timeframe, 100)
            if latest_data is None:
                continue

            signals = strategy(latest_data, *best_params)

            latest_signal = signals.iloc[-1]

            exchange = ccxt.okx({
                'apiKey': config['okx']['apiKey'],
                'secret': config['okx']['secret'],
                'password': config['okx']['password']
            })

            if latest_signal == 1:
                amount = 3
                exchange.create_market_buy_order(symbol, amount)
            elif latest_signal == -1:
                amount = 3
                exchange.create_market_sell_order(symbol, amount)

            time.sleep(3600)

        except Exception as e:
            print(f"执行错误: {str(e)}")
            time.sleep(60)
            continue


if __name__ == "__main__":
    print(ccxt.exchanges)
    main()
