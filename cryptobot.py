from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
from itertools import count
import time
import MetaTrader5 as mt5

load_dotenv()

CRYPTO = 'BTCUSD!'

# Price threshold (percentage)
PRICE_THRESHOLD = 3
# Stop loss (percentage)
STOP_LOSS = 5
# Take profit (percentage)
TAKE_PROFIT = 8

# Replace in line 113 to choose between a BUY or SELL order
BUY = mt5.ORDER_TYPE_BUY
SELL = mt5.ORDER_TYPE_SELL
ORDER_TYPE = BUY

# connect to the trade account without specifying a password and a server
if not mt5.initialize():
    print("initialize() failed, error code =", mt5.last_error())
    quit()

# account number in the top left corner of the MT5 terminal window
# the terminal database password is applied if connection data is set to be remembered
account_number = 2121944313
password = os.getenv("MT5_PASSWORD")  # Get password from environment variable
authorized = mt5.login(account_number, password=password, server="XBTFX-MetaTrader5")

if authorized:
    print(f'connected to account #{account_number}')
else:
    print(f'failed to connect at account #{account_number}, error code: {mt5.last_error()}')

# store the equity of your account
account_info = mt5.account_info()
if account_info is None:
    raise RuntimeError('Could not load the account equity level.')
else:
    equity = float(account_info[10])

print(equity)


# This function is used to get the dates for our dataset - so one day's worth of data in our case as we only care about the last two 10 minute candles
def get_dates():
    """Use dates to define the range of our dataset in the `get_data() function"""
    utc_from = datetime.today() - timedelta(days=1)
    return utc_from, datetime.now()

def get_data():
    """Download one day of 10 minute candles, along with the buy and sell prices for bitcoin."""
    utc_from, utc_to = get_dates()
    return mt5.copy_rates_range('BTCUSD!', mt5.TIMEFRAME_M10, utc_from, utc_to)

def get_current_prices():
    """Return current buy and sell prices."""
    print(mt5.symbol_info_tick("BTCUSD!"))
    current_buy_price = mt5.symbol_info_tick("BTCUSD!")[2]
    current_sell_price = mt5.symbol_info_tick("BTCUSD!")[1]
    return current_buy_price, current_sell_price

def trade():
    """Determine if we should trade and if so, send requests to MT5."""
    utc_from, utc_to = get_dates()
    candles = get_data()
    current_buy_price, current_sell_price = get_current_prices()

    # now, we calculate the percent difference between the current price and the close price of the previous candle
    difference = (candles['close'][-1] - candles['close'][-2] / candles['close'][-2] * 100)

    # check if the position has already been placed
    positions = mt5.positions_get(symbol=CRYPTO)
    orders = mt5.orders_get(symbol=CRYPTO)
    symbol_info = mt5.symbol_info(CRYPTO)

    # now, we perform our logic checks
    if difference > PRICE_THRESHOLD:
        print(f'dif 1: {CRYPTO}, {difference}')
        # Pause for 8 seconds to make sure the increase is sustained
        time.sleep(8)

        # Update utc_from and utc_to to reflect the new time range
        utc_from, utc_to = get_dates()  # Call get_dates() again to refresh the timestamps

        # calculate the difference once again 
        candles = mt5.copy_rates_range(CRYPTO, mt5.TIMEFRAME_M10, utc_from, utc_to)
        difference = (candles['close'][-1] - candles['close'][-2]) / candles['close'][-2] * 100

        if difference > PRICE_THRESHOLD:
            print(f'dif 2: {CRYPTO}, {difference}')
            price = mt5.symbol_info_tick(CRYPTO).bid
            print(f'{CRYPTO} is up {str(difference)}% in the last 5 minutes, opening BUY position.')

            # prepare the trade request
            if not mt5.intialize():
                raise RuntimeError(f'MT5 initialize() failed with error code {mt5.last_error()}')
            
            # check that there are no open positions or orders
            if len(positions) == 0 and len(orders) < 1:
                if symbol_info is None:
                    print(f'{CRYPTO} not found, can not call order_check()')
                    mt5.shutdown()
                    
                # if the symbol is not available in MarketWatch, add it
                if not symbol_info.visible:
                    print(f'{CRYPTO} is not visible, trying to switch on')
                    if not mt5.symbol_select(CRYPTO, True):
                        print('symbol_select() failed, exit', CRYPTO)
                
                # this represents 5% equity. the minimum order is 0.01 BTC. Increase equity share if retcode = 10014
                lot = float(round(((equity / 20) / current_buy_price), 2))

                if ORDER_TYPE == BUY:
                    sl = price - (price * STOP_LOSS) / 100
                    tp = price + (price * TAKE_PROFIT) / 100
                else:
                    sl = price + (price * STOP_LOSS) / 100
                    tp = price - (price * TAKE_PROFIT) / 100

                request = {
                    'action': mt5.TRADE_ACTION_DEAL,
                    'symbol': CRYPTO,
                    'volume': lot,
                    'type': ORDER_TYPE,
                    'price': price,
                    'sl': sl,
                    'tp': tp,
                    'magic': 66,
                    'comment': 'python-buy',
                    'type_time': mt5.ORDER_TIME_GTC,
                    'type_filling': mt5.ORDER_FILLING_IOC,
                }

                # send a trading request
                result = mt5.order_send(request)

                # check the execution result
                print(f'1. order_send(): by {CRYPTO} {lot} lots at {price}')

                if result.retcode != mt5.TRADE_RETCODE_DONE:
                    print(f'2. order_send() failed, retcode={result.retcode}')

                # print the order result - anything else than retcode=10009 is an error in the trading request
                print(f'2. order_send done, {result}')
                print(f'    opened position with POSITION_TICKET={result.order}')

            else:
                print(f'BUY signal detected, but {CRYPTO} has {len(positions)} active trade')
        else:
            pass

    else:
        if orders or positions:
            print('Buying signal detected but there is an already an active trade')
        else: 
            print(f'difference is only: {str(difference)}% trying again...')

if __name__ == '__main__':
    print('Press Ctrl-C to stop.')
    try:
        for i in count():
            trade()
            print(f'Iteration {i}')
    except KeyboardInterrupt:
        print("Shutting down...")
        mt5.shutdown()
