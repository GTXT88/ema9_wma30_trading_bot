import json
from os import execv
import time
import krakenex
import sys
import numpy as np
import pandas as pd
from pandas.core.indexes.base import Index
import pandas_datareader
import matplotlib
from pandas import DataFrame
import pickle
import datetime
import logging
import csv
import logging
from websocket import create_connection

class trading_bot():
    """
    Trading bot. Strategy is to use EMA9 as a short indicator and WMA30 as a long indicator. 
    LONG: 
        BUY : Buy when uptrend but CLOSE < EMA9. 
        SELL : Not sure if should use price target or ema9/wma30 crossover or something else
    
    """
    def __init__(self):

        # DEFINING API
        self.api_key, self.private_key = self.load_keys()
        self.api = krakenex.API(self.api_key, self.private_key)

        # TRADING VARIABLES
        self.currency = "XXBTZUSD"
        self.uptrend = False #uptrend
        self.downtrend = False #Down
        self.trend_change = False
        self.win_target = 1.01
        self.stop_loss_max = 0.998
        self.stop_loss_value = 0
        self.available_funds = 100000

        # TESTING VARIABLES
        self.data_index = 0
        self.testing = False
        self.test_data_length = 6433
        self.current_day = 0
        self.current_value = 0
        self.test_data_period = 65

    def run(self):
        while True:
            data = self.get_history_data()
            print("Fetched new data!")

            this_time = data[len(data)-1][0]
            averages = self.get_averages(data)
            this_time = averages[0]["time"]

            st1 = datetime.datetime.fromtimestamp(this_time).strftime('%Y-%m-%d %H:%M:%S')
            one_older_time = averages[1]["time"]
            st2 = datetime.datetime.fromtimestamp(one_older_time).strftime('%Y-%m-%d %H:%M:%S')
            print(st1)
            print(averages[0])
            print(st2)
            print(averages[1])
            one_before_newest = data[len(data) -2]
            one_before_newest_date = one_before_newest[0]
            one_before_newest_date = datetime.datetime.fromtimestamp(one_before_newest_date).strftime('%Y-%m-%d %H:%M:%S')
            print(one_before_newest_date)
            print(one_before_newest)


            #trades = self.get_latest_order() <- trade data from api
            open_position = self.get_trades()            
            if averages[1]["ema9"] > averages[1]["wma30"]:
                if self.uptrend:
                    print("CONTINUING UPTREND")
                    if open_position == None:
                        self.check_if_should_buy(averages, one_before_newest)
                else:
                    #TREND CHANGE!!
                    print("TREND CHANGES! UPTREND!")
                    self.uptrend = True
                    self.downtrend = False

            elif averages[1]["ema9"] < averages[1]["wma30"]:
                if self.downtrend:
                    print("CONTINUING DOWNTREND")
                    #CHECK IF OWNING ALREADY IF NOT 
                    #CHECK IF OPEN IN BETWEEN EMA AND WMA

                else:
                    #TREND CHANGE!!
                    print("TREND CHANGE! DOWNTREND!")
                    self.downtrend = True
                    self.uptrend = False

            if open_position != None:
                if open_position["status"] == "closed":
                    self.check_if_should_sell(open_position, data)
                elif open_position["status"] == "open":
                    self.check_if_trade_completed(open_position, data)
            print("\n\n")            
            time.sleep(20)

    """
    ############## CHECKS FOR SELLING AND BUYING #####################
    """

    def check_if_trade_completed(self, trade, data):
        current_price = self.get_current_value(data)
        if float(current_price) >= trade["price"]:
            print("Trade closed!")
            trade["status"] = "closed"
            self.close_trade(trade)
        elif float(current_price) < float(self.stop_loss_value):
            print("Deleting open position.")
            self.stop_loss_value = 0
            self.available_funds = self.available_funds + (float(trade["price"]) * float(trade["volume"]))
            self.delete_position()

    def check_if_should_buy(self, averages, data_from_latest_candle):
        if float(data_from_latest_candle[4]) > averages[1]["wma30"] and float(data_from_latest_candle[4]) < averages[1]["ema9"]:
            print("Last complete candle closed in between indicators")
            print(f"Setting buy on {data_from_latest_candle[2]}")
            print(f"With STOP LOSS of {data_from_latest_candle[3]}")
            volume = self.available_funds * (1 / float(data_from_latest_candle[2]))
            self.update_balance(float(data_from_latest_candle[2]) * volume)
            self.set_buy_order(float(data_from_latest_candle[2]), volume)
            self.stop_loss_value = data_from_latest_candle[3]

    def check_if_should_sell(self, trade, data):
        # CHECK IF SHOULD SELL
        current_price = self.get_current_value(data)
        print(f"CURRENT PRICE : {current_price}")

        """if self.testing:
            price_bought = trade["price"]
            volume = trade["volume"]
        else:
            price_bought = trade["descr"]["price"]
            volume = trade["descr"]["volume"]"""

        price_bought = trade["price"]
        volume = trade["volume"]

        if  float(current_price) / price_bought >= self.win_target:
            print(f"Selling with win at {current_price}")
            self.set_sell_order(float(current_price), float(current_price) * 1.001,volume)
            self.available_funds = self.available_funds + (float(current_price) * volume)
            self.delete_position()
        elif float(current_price) <= float(self.stop_loss_value):
            print(f"Selling with loss at {current_price}")
            self.set_sell_order(float(current_price),float(current_price) * 0.993,volume)
            self.available_funds = self.available_funds + (float(current_price) * volume)
            self.delete_position()


    """
    ############## API CALLS #####################
    """

    def get_test_data(self):
        data = []
        df = pd.read_csv("testidata/testidata1.csv", encoding='UTF-8')

        # DATA REVERSED TO first cell is oldest
        all_days_lists = list(reversed(df.values.tolist()))
        lists = []
        until_index = self.current_day + self.test_data_period
        if until_index >= self.test_data_length:
            sys.exit(1)
        print(f"DAYS FROM {self.current_day} TO {until_index}")
        for i in range(self.current_day, until_index):
            #print(i)
            lists.append(all_days_lists[i])

        #DAILY DATA CLEANING
        """for i in lists:
            date = i[0].replace(",", "")
            epoch = datetime.datetime.strptime(date, "%b %d %Y").timestamp()
            i[0] = epoch
            i.pop()
            i.pop()
            close = i[1]
            i.pop(1)
            i.append(close)
            i[0] = float(i[0])
            i[1] = float(i[1].replace(",", ""))
            i[2] = float(i[2].replace(",", ""))
            i[3] = float(i[3].replace(",", ""))
            i[4] = float(i[4].replace(",", ""))
            data.append(i)"""

        #HOURLY DATA CLEANING
        for i in lists:
            #date = i[0].replace(",", "")
            #epoch = datetime.datetime.strptime(date, "%b %d %Y").timestamp()
            #i[0] = epoch
            i.pop(1)
            i.pop(1)
            i.pop()
            i.pop()
            i[0] = i[0]
            i[1] = i[1]
            i[2] = i[2]
            i[3] = i[3]
            i[4] = i[4]
            data.append(i)
        
        #for day in data:
            #print(day)

        self.current_day += 1
        return data

    def get_history_data(self):
        # OHLC = open, high, low, close
        data = None
        """data = self.api.query_public(
            'OHLC', {"pair" : self.currency, "since" : str(int(time.time() - 180000,)), "interval" : 30
            })"""

        # Data viimeisin 2 tunnin ajalta -> 60 * 60 * 2 = 7200
        """data = self.api.query_public(
            'OHLC', {"pair" : self.currency, "since" : str(int(time.time() - 7200,))})"""
        
        # Data viimeisin 90 tunnin ajalta -> 60 * 60 * 90 = 324000
        data = self.api.query_public(
            'OHLC', {"pair" : self.currency, "since" : str(int(time.time() - 324000,)), "interval" : 60
            })

        if len(data["error"]) != 0:
            while len(data["error"]) != 0:
                time.sleep(10)
                data = self.api.query_public(
                'OHLC', {"pair" : self.currency, "since" : str(int(time.time() - 324000,)), "interval" : 60
                })


        if self.testing == True:
            data = self.get_test_data()

            with open("data.json", "w") as file:
                file.write(json.dumps(data, indent=4))
        
        else:
            data = data["result"][self.currency]
            with open("data.json", "w") as file:
                    file.write(json.dumps(data, indent=4))
    
        #print("Fetched data successfully")
        return data


    def get_current_value(self, data_test):
        data = None
        if self.testing:
            data = data_test[len(data_test)-1][4]
        else:
            data = self.api.query_public('Ticker', {"pair" : self.currency}) 
            data = data["result"][self.currency]["a"][0]
        return data


    def set_buy_order(self, buy_price, volume):
        """api_call_data= {"pair" : self.currency, 
                    "ordertype" : "limit", 
                    "type" : "buy", 
                    "volume" : volume, 
                    "price" : buy_price}"""

        #api_callback = self.api.query_private("AddOrder", api_call_data)
        """############# TESTING ############"""
        api_call_data= {"pair" : self.currency, 
                    "ordertype" : "limit", 
                    "type" : "buy", 
                    "volume" : volume, 
                    "price" : buy_price,
                    "status" : "open"}
        self.save_trade(api_call_data)


    def set_sell_order(self, sell_price, stop_loss_price,volume):
        api_call_data= {"pair" : self.currency, 
                    "ordertype" : "limit", 
                    "type" : "sell", 
                    "volume" : volume, 
                    "price" : sell_price, 
                    #"close[ordertpye]" : "stop-loss-limit", 
                    #"close[price]" : stop_loss_price
                    }

        #api_callback = self.api.query_private("AddOrder" ,api_call_data)
        self.save_trade(api_call_data)

    def get_latest_order(self):
        api_callback = self.api.query_public("ClosedOrders")
        latest_order_for_current_pair = {}
        for order in api_callback["results"]["closed"]:
            if order["descr"]["pair"] == self.currency:
                latest_order_for_current_pair = order
                break
        
        return latest_order_for_current_pair


    """
    ################ JSON HANDLING ########################
    """

    def close_trade(self, trade):
        with open("trades.json", "w+") as file:
            data = {"XXBTZUSD": [trade]}
            file.write(json.dumps(data, indent=4))
            file.close()

    def delete_position(self):
        with open("trades.json", "w+") as file:
            data = {"XXBTZUSD": []}
            file.write(json.dumps(data, indent=4))
            file.close()

    def update_balance(self, trade_value):
        self.available_funds = self.available_funds - trade_value

    def get_available_funds(self):
        with open("funds.json", "r") as file:
            data = json.load(file)
            funds = data["funds"]
            file.close()

        return funds


    def load_keys(self):
        with open("keys.json", "r") as file:
            keys = json.loads(file.read())
            return (keys["api_key"], keys["private_key"])


    def save_averages(self, averages_json):
        file = open("averages.json", "w+")
            
        file.write(json.dumps(averages_json, indent=4))
        file.close()
    

    def get_trades(self):
        with open("trades.json", "r") as file:
            try:
                trades = json.load(file)
                if trades[self.currency] != []:
                    return trades[self.currency][0]
                else:
                    return None
            except:
                trades = None


    def save_trade(self, trade_dict):
        # File for latest trade
        file = open("trades.json", "w+")
        trade_data = { self.currency : []}
        trade_data[self.currency].append(trade_dict)

        file.write(json.dumps(trade_data, indent=4))
        file.close()

        # File for all trades
        file = open("all_trades.json", "r")
        trade_data = json.loads(file.read())
        trade_data[self.currency].append(trade_dict)
        file.close()

        file = open("all_trades.json", "w+")
        file.write(json.dumps(trade_data, indent=4))
        file.close()


    """
    ################ PRODUCE AVERAGES ########################
    """

    def get_averages(self, data):
        averages = []
        averages = self.make_averages(data)
        return averages


    def make_averages(self, data):
        averages = []
        wma30s = self.calculate_wma30(data) # Return list of wma30s from most recent(this minute) to 30 minutes ago
        ema9s = self.calculate_ema9(data) # Return list of ema9s from 9 minutes ago to most recent
        
        averages.append({
            "time" : data[len(data)-1][0],
            "wma30" : round(wma30s[0], 2),
            "ema9" : round(ema9s[0], 2)
        })
        averages.append({
            "time" : data[len(data)-2][0],
            "wma30" : round(wma30s[1], 2),
            "ema9" : round(ema9s[1], 2)
        })

        averages_to_save = []
        averages_to_save.append(wma30s)
        averages_to_save.append(ema9s)
        #print(averages_to_save)
        self.save_averages(averages_to_save)
        return averages
    

    def calculate_wma30(self, data):
        reversed_data_temp = reversed(data)
        reversed_data = []
        for j in reversed_data_temp:
            reversed_data.append(j)

        wma30s = []
        for i in range(0,30): # Values from 0 to 30
            wma30_values = 0
            y=i+31
            wma_weight = 30
            #print(f"Calculating wma for {i}")
            for n in range(i,y):# Values from i + 30 to 1
                wma30_values += float(reversed_data[n][4]) * wma_weight
                wma_weight -= 1
                #print(n)
                
            denominator = 30 * 31 / 2
            wma30 = wma30_values / denominator
            wma30s.append(wma30)
        return wma30s
    

    def calculate_ema9(self, data):
        period = 9
        needed_prices_list = []
        index = 0

        for i in list(reversed(data)):
            if index <= 29:
                needed_prices_list.append( float(i[4]) )
                index += 1
            else:
                break
        
        values = DataFrame(list(reversed(needed_prices_list)))
        ema9s = values.ewm(span=period, adjust=False).mean()
        all_ema9 = list(reversed(ema9s.values.tolist()))
        ema9 = []
        for i in range(0, period):
            ema9.append(all_ema9[i][0])

        return ema9


if __name__ == "__main__":
    bot = trading_bot()
    bot.run()
    # Connect to WebSocket API and subscribe to trade feed for XBT/USD and XRP/USD
    """ ws = create_connection("wss://ws.kraken.com/")
        ws.send('{"event":"subscribe", "subscription":{"name":"ohlc", "interval" : 30}, "pair":["XBT/USD"], "since" : ' + str(int(time.time() - 7200,)) +'}')

        # Infinite loop waiting for WebSocket data
        while True:
            print(ws.recv())"""