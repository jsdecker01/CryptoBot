import krakenex
from pykrakenapi import KrakenAPI
import time
import decimal
import json

def now():
    return decimal.Decimal(time.time())

def get_balance():
    with open('balance.json','r') as f:
        try:
            return json.load(f)
        except:
    #change this for the actual query to the database once the script is working
            #return {'USD' : '1000.0', 'EUR.HOLD': '0.0000'}
            balance = k.query_private('Balance')['result']
            for pair in pairs:
                if not pair[:-len(pairdict[pair])] in balance:
                    balance[pair[:-len(pairdict[pair])]] = "0.00"
            return balance

def update_balance(amount, name, price, sold):
    balance = get_balance()
    if sold:
        balance.pop(name[:-len(pairdict[name])], None)
        balance['ZUSD'] = str(float(balance['ZUSD']) + amount*price)
    else:
        balance['ZUSD'] = str(float(balance['ZUSD']) - amount*price)
        balance[name[:-len(pairdict[name])]] = str(amount)
    save_balance(balance)
    return balance

def save_balance(data):
    with open('balance.json', 'w') as f:
        json.dump(data, f, indent=4)

#get the price data for the crypto
def get_crypto_data(pair, since):
    ret = k.query_public('OHLC', data = {'pair': pair, 'since': since})
    #print(pair)
    return ret['result'][pair]

def get_purchasing_price(name):
    trades = load_trades()
    return trades[name][-1]['price_usd']

def load_trades():
    trades = {}
    with open('trades.json', 'r') as f:
        try:
            trades = json.load(f)
        except:
            for crypto in pairs:
                trades[crypto] = []
    return trades

def load_crypto_data_from_file():
    data = {}
    with open('data.json', 'r') as f:
        try:
            data = json.load(f)
        except:
            data = make_crypto_data(data)
            save_crypto_data(data)
    return data

def make_crypto_data(data):
    for name in pairs:
        data[name] = {
                    'high' : [],
                    'low' : [],
                    'close' : [],
                    'prices' : []
                    }
    return data

def save_crypto_data(data):
    with open('data.json', 'w') as f:
        json.dump(data, f, indent=4)

def save_trade(close, name, bought, sold, amount):
    #saves trades to json file
    balance = get_balance()
    try:
        coin = balance[name[:-len(pairdict[name])]]
    except:
        coin = 0.000
    trade = {
            'time_stamp' : str(int(time.time())),
            'price_usd' : close,
            'bought' : bought,
            'sold' : sold,
            'amount' : amount,
            'new balance' : coin
            }
    print('TRADE: ' + name)
    print(json.dumps(trade, indent=4))
    trades = load_trades()
    trades[name].append(trade)
    with open('trades.json', 'w') as f:
        json.dump(trades, f, indent=4)

def buy_crypto(crypto_data, name):
#executes trade
    analysis_data = clear_crypto_data(name)
    #find what we can buy for
    price = float(crypto_data[-1][4])
    funds = get_available_funds()
    amount = funds * (1/ price)
    balance = update_balance(amount, name, price, False)
    add_order('buy',name,amount)
    save_trade(price, name, True, False, amount)
    print('buy')

def sell_crypto(crypto_data, name):
    balance = get_balance()
    analysis_data = clear_crypto_data(name)
    price = float(crypto_data[-1][4])
    amount = float(balance[name[:-len(pairdict[name])]])
    balance = update_balance(amount, name, price, True)
    add_order('sell',name,amount)
    save_trade(price, name, False, True, amount)
    print('sell')

#implements trade
def add_order(type, name, amount):
    data = {
            'type' : type,
            'trading_agreement' : 'agree',
            'pair' : name,
            'ordertype' : 'market',
            'volume' : amount
            }
    print(type, name, amount)
    res_add_order = k.query_private("AddOrder", data = data)

def clear_crypto_data(name):
    data = load_crypto_data_from_file()
    for key in data[name]:
        data[name][key] = delete_entries(data[name], key)
    save_crypto_data(data)
    return data

def delete_entries(data, key):
    clean_array = []
    for entry in data[key][-10:]:
        clean_array.append(entry)
    return clean_array

def get_available_funds():
    balance = get_balance()
    money = float(balance['ZUSD'])
    cryptos_owned = 0
    for crypto in balance:
        if float(balance[crypto]) > 0:
            cryptos_owned += 1
    cryptos_not_owned = len(balance) - cryptos_owned
    funds = money / cryptos_not_owned
    return funds

def bot(k, pairs):
    while True:
        #comment out to track the same "since"
        since = str(int(time.time() - 300))
        for pair in pairs:
            trades = load_trades()

            if len(trades[pair]) > 0:
                crypto_data = get_crypto_data(pair, since)
                if trades[pair][-1]['sold'] or trades[pair][-1] == None:
                    #check if we should buy
                    check_data(pair, crypto_data, True)
                if trades[pair][-1]['bought']:
                    #check if we should sell
                    check_data(pair, crypto_data, False)
            else:
                crypto_data = get_crypto_data(pair, since)
                check_data(pair, crypto_data, True)

        time.sleep(30)

def check_data(name, crypto_data, should_buy):
    high = 0
    low = 0
    close = 0
    for b in crypto_data[-5:]:
        if b not in historical_data[name]['prices']:
            historical_data[name]['prices'].append(b)

        high += float(b[2])
        low += float(b[3])
        close += float(b[4])
    #adds every moving average into data set
    historical_data[name]['high'].append(high / 5)
    historical_data[name]['low'].append(low / 5)
    historical_data[name]['close'].append(close / 5)
    save_crypto_data(historical_data)
    if should_buy:
        try_buy(historical_data[name], name, crypto_data)
    else:
        try_sell(historical_data[name],name, crypto_data)

def try_buy(data, name, crypto_data):
    #analyze the data to see if it is a good opportunity to buy
    make_trade = check_opportunity(data, name, False, True)
    if make_trade:
        buy_crypto(crypto_data, name)

def try_sell(data, name, crypto_data):
    #analyse the data to see if it is a good opportunity to sell
    make_trade = check_opportunity(data, name, True, False)
    if make_trade:
        sell_crypto(crypto_data, name)

def check_opportunity(data, name, sell, buy):
    #calculate percentage increase of each point
    count = 0
    previous_value = 0
    trends = []
    #for data in data['close'][-60:]:
    #    if previous_value == 0:
    #        previous_value = data
    #    else:
    #        if data/previous_value > 1:
    #            #uptrend
    #            if count < 1:
    #                count = 1
    #            else:
    #                count += 1
    #            trends.append('UPTREND')
    #        elif data/previous_value < 1:
    #            trends.append('DOWNTREND')
    #            if count > 0:
    #                count -= 1
    #        else:
    #            trends.append('NOTREND')
    #        previous_value = data

    #check if under 5 data points exist, and use earliest data point if so.
    if len(data['close']) > 5:
        first_data_point = -5
    else:
        first_data_point = 0
    print(name, 'Previous Moving Average: ' + str(data['close'][first_data_point]), 'Current Moving Average: ' + str(data['close'][-1]))
    #check trends
    if data['close'][-1] > data['close'][first_data_point]:
        trends.append('UPTREND')
    elif data['close'][-1] < data['close'][first_data_point]:
        trends.append('DOWNTREND')
    else:
        trends.append('NOTREND')
    print(name + ': ' + str(trends))

    if trends[-1] == 'UPTREND':
        price = float(data['prices'][-1][4])
        print('Current Price: ' + str(price), 'Current Moving Average: ' + str(data['close'][-1]))
        #only buy if price is at least 0.1% higher than current moving average
        if buy:
            print(price/(data['close'][-1] * 1.001))
            if price >= data['close'][-1] * 1.001:
                return True
        #only sell if price is at least 0.1% lower than current moving average
        if sell:
            if price < data['close'][-1] * 0.999:
                purchase_price = float(get_purchasing_price(name))
                print('Current Price: ' + str(price), 'Purchase Price: ' + str(purchase_price))
                if price > purchase_price:
                    print('Selling at a profit :)')
                elif price < purchase_price:
                    print('Selling at a loss :(')
                return True
    #areas = []
    #for data in reversed(data['close'][-5:]):
    #    area = 0
    #    price = float(data['prices'][-1][3])
    #    if sell:
    #        purchase_price = float(get_purchasing_price(name))
    #        if price > purchase_price:
    #            print('Selling at a profit')
    #            return True
    #        if price < purchase_price:
    #            print('Selling at a loss')
    #            return True
    #    areas.append(data/price)

    #if buy:
    #    counter = 0
    #    if count >= 5:
    #        for area in areas:
    #            counter += area
    #        if counter / 3 >= 1.05:
    #            return True
    return False

def get_pairs():
    return {
            'XETHZUSD' : 'ZUSD',
            'XXBTZUSD' : 'ZUSD',
            #'MANAUSD' : 'USD',
            #'GRTUSD' : 'USD',
            'LSKUSD' : 'USD',
            'XDGUSD' : 'USD',
            'XXRPZUSD' : 'ZUSD',
            'XLTCZUSD' : 'ZUSD'
            }

if __name__ == '__main__':
    k = krakenex.API()
    k.load_key('kraken.key')
    pairdict = get_pairs()
    pairs = list(pairdict.keys())
    historical_data = load_crypto_data_from_file()
    balance = get_balance()
    #rename XXDG to XDG
    if "XXDG" in balance:
        balance["XDG"] = balance.pop("XXDG")
    save_balance(balance)
    #check for existing balances and save them to trades as 'buy' in order for next trade to be 'sell'
    for pair in pairs:
        if float(balance[pair[:-len(pairdict[pair])]]) > 0:
            save_trade(float(balance[pair[:-len(pairdict[pair])]]), pair, True, False, 1.0)
    bot(k, pairs)
