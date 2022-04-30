import json
import time
from typing import Optional
import numpy as np
import pandas as pd
from pandas import DataFrame
import datetime
from binance import Client
from math import floor
from produce_indicators import ProduceIndicators
from api_calls import ApiCalls
from shorting import Shorting
from buying import Buying

class TradingBot(ProduceIndicators, ApiCalls, Shorting, Buying):
    """
    Trading bot. Strategy is to use EMA9 as a short indicator and WMA30 as a long indicator. 
    https://tradingstrategyguides.com/9-30-trading-strategy/ If interested in implemented strategy.

    """
    def __init__(self, ):

        # DEFINING API
        self.api_key, self.private_key = self.load_keys()
        self.api = Client(self.api_key, self.private_key)

        # TRADING VARIABLES
        self.currency = "BTCBUSD" # This is used in public queries
        self.currency_private = "BUSD" # This is used in private queries
        self.fund_currency = "BUSD" # This is used in currency queries
        self.uptrend = False
        self.downtrend = False
        self.trend_change = False
        self.loan_open = False # If short position is open
        self.win_target = 1.01
        self.short_win_target = 0.99
        self.stop_loss_value = 0
        self.available_funds_spot = None
        self.available_funds_margin = None
        self.long_buy_price = 0
        self.short_buy_price = 0
        self.target_price = 0
        self.available_btc = 0
        self.last_bought_price = 0
        self.shorted_amount = 0

    def run(self):
        """
        This method is the running method for the trading bot.
        It starts a never ending loop and follow logic shown in logic.png
        """
        while True:
            # Get data and indicators
            data = self.get_history_data()
            print("Fetched new data!")
            averages = []
            while True:
                try:
                    averages = self.make_averages(data)
                    break
                except Exception as e:
                    print(e)
                    pass
            one_older_time = averages[1]["time"] / 1000
            self.available_funds = self.get_available_funds_spot()
            self.available_funds_margin = self.get_available_funds_margin()
            one_before_newest = data[len(data) -2]
    
            # Parsing printable strings from timedata
            this_time = data[len(data)-1][0]
            this_time = averages[0]["time"] / 1000
            st1 = datetime.datetime.fromtimestamp(this_time).strftime('%Y-%m-%d %H:%M:%S')
            st2 = datetime.datetime.fromtimestamp(one_older_time).strftime('%Y-%m-%d %H:%M:%S')
            one_before_newest_date = one_before_newest[0] / 1000
            one_before_newest_date = datetime.datetime.fromtimestamp(
                    one_before_newest_date).strftime('%Y-%m-%d %H:%M:%S')

            last_closed_order = self.get_latest_closed_order_spot()
            self.available_btc = self.get_available_btc_spot()
            last_closed_margin_order = self.get_latest_margin_without_id()
            self.shorted_amount = self.truncate(self.get_borrowed_btc_margin(), 5)

            self.produce_prints(last_closed_order,
                                st1, 
                                st2, 
                                averages[0], 
                                averages[1],
                                last_closed_margin_order)
            print(f"Win target percentage is {self.win_target}")

            # Checking if in uptrend
            if averages[1]["ema9"] > averages[1]["wma30"]:
                if self.uptrend:
                    print("CONTINUING UPTREND")
                    self.check_latest_order_in_uptrend(averages, one_before_newest, data, 
                                        last_closed_order, last_closed_margin_order)
                else:
                    print("TREND CHANGES! UPTREND!")
                    self.uptrend = True
                    self.downtrend = False
                    self.long_buy_price = 0
                    self.short_buy_price = 0
                    self.check_latest_order_in_uptrend(averages, one_before_newest, data, 
                                        last_closed_order, last_closed_margin_order)

            # Checking if in downtrend
            elif averages[1]["ema9"] < averages[1]["wma30"]:
                if self.downtrend:
                    print("CONTINUING DOWNTREND")
                    self.check_latest_order_in_downtrend(averages, one_before_newest, data, 
                                        last_closed_order, last_closed_margin_order)
                else:
                    print("TREND CHANGE! DOWNTREND!")
                    self.long_buy_price = 0
                    self.short_buy_price = 0
                    self.check_latest_order_in_downtrend(averages, one_before_newest, data, 
                                        last_closed_order, last_closed_margin_order)
                    self.downtrend = True
                    self.uptrend = False
            print("\n\n")            
            time.sleep(5)

    def check_latest_order_in_uptrend(self, averages, one_before_newest, data, last_closed_order, last_closed_margin_order):
        """
        Checking latest order in uptrend. 
        """
        if last_closed_order == None or last_closed_order["side"] == "SELL":
            #if self.traded_this_trend == False:
            print("Checking if should buy!")
            self.check_if_should_buy(averages, one_before_newest, data)
        elif last_closed_order["side"] == "BUY":
            self.stop_loss_value =  round(averages[1]["wma30"] * 0.995, 1) # Moving stop loss value
            print("Checking if should sell!")
            self.check_if_should_sell(data)

    def check_latest_order_in_downtrend(self, averages, one_before_newest, data, last_closed_order, last_closed_margin_order):
        """
        Checking lastest order in downtrend.
        Position is saved to loan_open boolean variable because binance handles margin position differently than regular orders.
        """
        if self.loan_open == False:
            # and self.traded_this_trend == False:
            print("Checking if should short!")
            self.check_if_should_short(averages, one_before_newest, data)
        elif self.loan_open == True:
            self.stop_loss_value =  round(averages[1]["wma30"] * 1.005, 1) # Moving stop loss value
            print("Checking if should sell short position!")
            self.check_if_should_sell_short()

    """
    ################ JSON HANDLING ########################
    """
    def load_keys(self):
        """
        Method for getting API-keys
        """
        with open("keys.json", "r") as file:
            keys = json.loads(file.read())
            return (keys["api_key"], keys["secret_key"])

    """
    ################ PRINTS ########################
    """
    def produce_prints(self, last_order, st1, st2, averages0, averages1, last_close_margin):
        """
        This method is run every 5 seconds. Contains prints about the current market and bot situation.
        """
        print(st1)
        print(averages0)
        print(st2)
        print(averages1)
        if last_order == None:
            print(f"No previous orders!")
        else:
            print("Last closed Order:")
            print(last_order)
        if last_close_margin == None:
            print(f"No previous margin orders!")
        else:
            print("Last closed margin order:")
            print(last_close_margin)
        print(f"Stop loss value = {self.stop_loss_value}")
        print(f"Buy price set on {self.long_buy_price}")
        print(f"Target price set on {self.target_price}")
        print(f"Short buy price set on {self.short_buy_price}")
        print(f"Available funds : {self.available_funds}")
        print(f"Available funds margin : {self.available_funds_margin}")
        print(f"Shorted amount plus interest: {self.shorted_amount}")

if __name__ == "__main__":
    bot = TradingBot()
    bot.run()