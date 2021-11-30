import json
from os import execv
import time
import krakenex
import sys
import numpy as np
import pandas as pd
from pandas.core import api
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
    
    Pitää tehdä metodi myynnin tarkastelulle, samalla positiolle ei voi liattaa tarpeeski myyntikriteerejä
    """
    def __init__(self, ):

        # DEFINING API
        self.api_key, self.private_key = self.load_keys()
        self.api = krakenex.API(self.api_key, self.private_key)

        # TRADING VARIABLES
        self.currency = "XXBTZEUR"
        self.currency_private = "XBTEUR"
        self.fund_currency = "ZEUR"
        self.uptrend = False #uptrend
        self.downtrend = False #Down
        self.trend_change = False
        self.win_target = 1.006
        self.stop_loss_value = 0
        self.available_funds = None
        self.long_buy_price = 0
        self.target_price = 0
        self.available_btc = 0
        self.last_bought_price = 0

        # TESTING VARIABLES
        self.testing = False
        self.data_index = 0
        self.test_data_length = 6433
        self.current_day = 0
        self.current_value = 0
        self.test_data_period = 65

    def run(self):
        while True:
            # Get data and indicators
            data = self.get_history_data()
            print("Fetched new data!")
            averages = self.make_averages(data)
            one_older_time = averages[1]["time"]
            self.available_funds = self.get_available_funds()
            one_before_newest = data[len(data) -2]

            # Prints shown when running
            print(f"Available funds : {self.available_funds}")
            this_time = data[len(data)-1][0]
            this_time = averages[0]["time"]
            st1 = datetime.datetime.fromtimestamp(this_time).strftime('%Y-%m-%d %H:%M:%S')
            st2 = datetime.datetime.fromtimestamp(one_older_time).strftime('%Y-%m-%d %H:%M:%S')
            print(st1)
            print(averages[0])
            print(st2)
            print(averages[1])
            one_before_newest_date = one_before_newest[0]
            one_before_newest_date = datetime.datetime.fromtimestamp(one_before_newest_date).strftime('%Y-%m-%d %H:%M:%S')
            print(one_before_newest_date)
            print(one_before_newest)

            # Get last closed order
            open_position = self.get_latest_order() #Last closed order from api
            # CHECK FOR OPEN ORDERS
            open_orders = self.get_open_order() # Boolean. True if open orders exists.
            self.available_btc = self.get_available_btc()
            print("LAST CLOSED ORDER")
            print(open_position)
            print(f"open_orders :  {open_orders}")
            print(f"stop_loss value = {self.stop_loss_value}")
            print(f"buy price set on {self.long_buy_price}")
            print(f"target price set on {self.target_price}")
            #open_position = self.get_trades()

            if averages[1]["ema9"] > averages[1]["wma30"]:
                if self.uptrend:
                    print("CONTINUING UPTREND")
                    if open_position["descr"]["type"] == "sell" and open_orders == False:
                        print("Checking if should buy!1")
                        self.check_if_should_buy(averages, one_before_newest, data)
                    elif open_position["descr"]["type"] == "buy" and open_orders == False:
                        print("Checking if should sell!1")
                        self.check_if_should_sell(data)
                else:
                    #TREND CHANGE!!
                    print("TREND CHANGES! UPTREND!")
                    self.uptrend = True
                    self.downtrend = False
                    if open_position["descr"]["type"] == "sell" and open_orders != True:
                        print("Checking if should buy!11")
                        self.check_if_should_buy(averages, one_before_newest, data)
                    elif open_position["descr"]["type"] == "buy" and open_orders == False:
                        print("Checking if should sell!11")
                        self.check_if_should_sell(data)

            elif averages[1]["ema9"] < averages[1]["wma30"]:
                if self.downtrend:
                    print("CONTINUING DOWNTREND")
                    #CHECK IF OWNING ALREADY IF NOT 
                    #CHECK IF OPEN IN BETWEEN EMA AND WMA
                    if open_position["descr"]["type"] == "buy":
                        print("Checking if should sell!111")
                        self.check_if_should_sell(data)
                else:
                    #TREND CHANGE!!
                    print("TREND CHANGE! DOWNTREND!")
                    if open_position["descr"]["type"] == "buy":
                        print("Checking if should sell!1111")
                        self.check_if_should_sell(data)
                    self.long_buy_price = 0
                    self.stop_loss_value = 0
                    self.downtrend = True
                    self.uptrend = False
            
            print("\n\n")            
            time.sleep(5)

    """
    ############## SELLING #####################
    """
    def check_if_should_sell(self, data):
        current_price = float(self.get_current_value(data))
        if current_price >= self.target_price:
            self.set_sell_order(self.target_price)
        elif current_price < self.stop_loss_value:
            self.set_sell_order(self.target_price)

    def set_sell_order(self, price):
        while True:        
            try:
                api_call_data= {"pair" : self.currency, 
                            "ordertype" : "limit", 
                            "type" : "sell", 
                            "volume" : self.available_btc, 
                            "price" : price
                            }
                api_callback_sell = self.api.query_private("AddOrder", api_call_data) # SETTING SELL
                if len(api_callback_sell["error"]) != 0:
                    while len(api_callback_sell["error"]) != 0:
                        time.sleep(5)
                        print("TRYING TO SELL")
                        print(api_callback_sell["error"])
                        api_callback_sell = self.api.query_private("AddOrder", api_call_data)
                else:
                    print("SELL WAS MADE, WAITING!")
                    self.stop_loss_value = 0
                    self.long_buy_price = 0
                    time.sleep(5)
                    break
            except Exception as e:
                time.sleep(5)
                print(f"{e}")
                pass
            
    """
    ############## BUYING #####################
    """
    def check_if_should_buy(self, averages, data_from_latest_candle, data):
        if float(data_from_latest_candle[4]) > averages[1]["wma30"] and float(data_from_latest_candle[4]) < averages[1]["ema9"] and float(data_from_latest_candle[4]) < float(data_from_latest_candle[1]):
            self.long_buy_price = float(data_from_latest_candle[2])
            self.stop_loss_value = float(data_from_latest_candle[3])
            print("Last complete candle closed in between indicators")
            time.sleep(1)
            current_price = float(self.get_current_value(data))
            time.sleep(1)
            if current_price >= self.long_buy_price:
                print(f"Setting buy on {data_from_latest_candle[2]}")
                print(f"With STOP LOSS of {data_from_latest_candle[3]}")
                volume = self.available_funds * (1 / float(data_from_latest_candle[2]))
                self.set_buy_order(float(data_from_latest_candle[2]), volume)
        # IF INSPECTING DATA NOT DIRECTLY AFTER TREND CHANGE
        elif self.stop_loss_value != 0 and self.long_buy_price != 0 and self.uptrend:
            time.sleep(1)
            current_price = float(self.get_current_value(data))
            time.sleep(1)
            if current_price >= self.long_buy_price:
                print(f"Setting buy on {current_price}")
                print(f"With STOP LOSS of {self.stop_loss_value}")
                volume = self.available_funds * (1 / current_price)
                self.set_buy_order(current_price, volume)

    def set_buy_order(self, buy_price, volume):
        bought = False
        """trades = {}
        with open("trades.json", "r", encoding="utf-8") as f:
            trades = json.loads(f.read())"""
        while True:        
            try:
                if bought == False:
                    api_call_data= {"pair" : self.currency, 
                                "ordertype" : "limit", 
                                "type" : "buy", 
                                "volume" : volume, 
                                "price" : buy_price
                                }

                    api_callback_buy = self.api.query_private("AddOrder", api_call_data) # SETTING BUY
                    time.sleep(1)
                    if len(api_callback_buy["error"]) != 0 and bought == False:
                        while len(api_callback_buy["error"]) != 0:
                            time.sleep(1)
                            api_callback_buy = self.api.query_private("AddOrder", api_call_data)
                    else:
                        bought = True
                while True:
                    open_order = self.get_open_order()
                    if open_order == True:
                        time.sleep(2)
                    else:
                        break
                time.sleep(5)
                open_position = self.get_latest_order() #Last closed order from api 
                self.long_buy_price = 0
                self.available_btc = self.get_available_btc()
                self.last_bought_price = float(open_position["descr"]["price"])
                self.target_price =  self.last_bought_price * self.win_target
                print("set_buy_orderPrint")
                return
            except Exception as e:
                time.sleep(5)
                print(f"{e}")
                pass
    """
    ############## API CALLS #####################
    """

    def get_available_btc(self):
        time.sleep(1)
        api_callback = self.api.query_private("Balance")
        print(api_callback)
        if len(api_callback["error"]) == 0:
            funds = float(api_callback["result"]["XXBT"])
        else:
            while len(api_callback["error"]) != 0:
                time.sleep(5)
                print("GET_AVAILABLE_BTC ERROR!")
                print(api_callback["error"])
                print("TRYING AGAIN AFTER 10 SECS")
                time.sleep(10)
                api_callback = self.api.query_private("Balance")
                if len(api_callback["error"]) == 0:
                    funds = float(api_callback["result"]["XXBT"])

        return funds

    def get_available_funds(self):
        time.sleep(1)
        api_callback = self.api.query_private("Balance")
        print(api_callback)
        if len(api_callback["error"]) == 0:
            funds = float(api_callback["result"][self.fund_currency])
        else:
            while len(api_callback["error"]) != 0:
                time.sleep(5)
                print("GET_AVAILABLE_FUNDS ERROR!") 
                print(api_callback["error"])
                print("TRYING AGAIN AFTER 10 SECS")
                time.sleep(10)
                api_callback = self.api.query_private("Balance")
                if len(api_callback["error"]) == 0:
                    funds = float(api_callback["result"][self.fund_currency])

        return funds

    def get_history_data(self):
        time.sleep(1)
        # OHLC = open, high, low, close
        data = None
        
        # Data viimeisin 90 tunnin ajalta -> 60 * 60 * 90 = 324000
        while True:
            data = self.api.query_public(
                'OHLC', {"pair" : self.currency, "since" : str(int(time.time() - 324000,)), "interval" : 60
                })

            if len(data["error"]) != 0:
                while len(data["error"]) != 0:
                    time.sleep(1)
                    data = self.api.query_public(
                    'OHLC', {"pair" : self.currency, "since" : str(int(time.time() - 324000,)), "interval" : 60
                    })
            else:
                break
        if self.testing == True:
            data = self.get_test_data()
            with open("data.json", "w") as file:
                file.write(json.dumps(data, indent=4))
        else:
            data = data["result"][self.currency]
            with open("data.json", "w") as file:
                    file.write(json.dumps(data, indent=4))
        return data

    def get_current_value(self, data_test):
        while True:
            try:
                time.sleep(1)
                data = self.api.query_public('Ticker', {"pair" : self.currency}) 
                data = data["result"][self.currency]["a"][0]
                return data
            except Exception as e:
                print(e)
                print("TRYING AGAIN TO FETCH DATA")
                time.sleep(1)

    def get_open_order(self):
        time.sleep(1)
        while True:
            try:
                api_callback = self.api.query_private("OpenOrders")
                if len(api_callback["error"]) == 0:
                    if api_callback["result"]["open"] != {}:
                        open_orders = True
                        return open_orders
                    else:
                        open_orders = False
                        return open_orders
                else:
                    while len(api_callback["error"]) != 0:
                        print(api_callback["error"])
                        time.sleep(1)
                        api_callback = self.api.query_private("OpenOrders")
                        if len(api_callback["error"]) == 0:
                            if api_callback["result"]["open"] != {}:
                                open_orders = True
                                return open_orders
                            else:
                                open_orders = False
                                return open_orders
            except Exception:
                time.sleep(5)
                pass

    def get_latest_order(self):
        time.sleep(1)
        while True:
            try:
                time.sleep(1)
                api_callback = self.api.query_private("ClosedOrders")
                latest_order_for_current_pair = None
                if len(api_callback["error"]) == 0:
                    for order_key in api_callback["result"]["closed"]:
                        if api_callback["result"]["closed"][order_key]["descr"]["pair"] == self.currency_private:
                            latest_order_for_current_pair = api_callback["result"]["closed"][order_key]
                            return latest_order_for_current_pair
            except Exception:
                time.sleep(5)
                pass
    """
    ################ JSON HANDLING ########################
    """
    def load_keys(self):
        with open("keys.json", "r") as file:
            keys = json.loads(file.read())
            return (keys["api_key"], keys["private_key"])
    """
    ################ PRODUCE AVERAGES ########################
    """    
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
        #self.save_averages(averages_to_save)
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