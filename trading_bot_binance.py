import json
import time
from typing import Optional
import numpy as np
import pandas as pd
from pandas import DataFrame
import datetime
from binance import Client
from math import floor

class trading_bot():
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
    ############## SELLING UPTREND #####################
    """
    def check_if_should_sell(self, data):
        """
        Checking if current value is higher than win target or lowet than stop loss value
        """
        current_price = float(self.get_current_value())
        if current_price >= self.target_price:
            # Profit
            self.set_sell_order(current_price, "limit")
        elif current_price < self.stop_loss_value:
            # Loss
            self.set_sell_order(current_price, "market")

    def set_sell_order(self, price, ordertype):
        """
        Creating data for api call and reseting variables used in trading.
        """
        while True:        
            try:
                api_call_data= {
                            "symbol" : self.currency,
                            "quantity" : self.truncate(self.available_btc, 5), 
                            "price" : float(round(price, 5))
                            }
                data = None
                with open("trades.json", "r", encoding="utf-8") as f:
                    data = json.loads(f.read())
                data["trades"].append(api_call_data)
                with open("trades.json", "w", encoding="utf-8") as f:
                    f.write(json.dumps(data, indent=4))
                self.sell_order_api_call(api_call_data)
                print("SELL WAS MADE!")
                self.stop_loss_value = 0
                self.target_price = 0
                time.sleep(1)
                break
            except Exception as e:
                time.sleep(1)
                print(f"{e}")
                pass

    def sell_order_api_call(self, data):
        """
        This is a separate method for handling non-margin selling via the api.
        """
        api_callback_sell = None
        while True:
            try:
                api_callback_sell = self.api.order_limit_sell(**data)
                open_order = self.get_open_order(api_callback_sell["clientOrderId"])
                if open_order == True:
                    # If trade was accepted we have to wait for it to close
                    while True:
                        open_order = self.get_open_order(api_callback_sell["clientOrderId"])
                        if open_order == True:
                            print("waiting for trade to finish4")
                            time.sleep(1)
                        else:
                            break
                if open_order == False:
                    print("Sell order was made!!")
                    return
            except Exception as e:
                time.sleep(1)
                print(f"{api_callback_sell}")
                print(f"{e}")
                pass

    """
    ############## BUYING UPTREND #####################
    """
    def check_if_should_buy(self, averages, data_from_latest_candle, data):
        """
        Method for checking price data in uptrend.
        """
        trend_strength = round(averages[0]["ema9"] / averages[0]["wma30"], 4)
        trend_is_strong = False
        if trend_strength >= 1.003:
            trend_is_strong = True
        
        # Checking if last candle opened an possibility for buying 
        if float(data_from_latest_candle[4]) > averages[1]["wma30"] and float(data_from_latest_candle[4]) < averages[1]["ema9"]:
            self.long_buy_price = float(data_from_latest_candle[2])
            self.stop_loss_value = round(averages[1]["wma30"] * 0.995, 1)
            print("Last complete candle closed in between indicators")
            time.sleep(1)
            current_price = float(self.get_current_value())
            time.sleep(1)
            if current_price >= self.long_buy_price and trend_is_strong:
                print(f"Setting buy on {data_from_latest_candle[2]}")
                print(f"With STOP LOSS of {data_from_latest_candle[3]}")
                volume = self.available_funds * (1 / current_price)
                self.set_buy_order(current_price, volume)
            else:
                print(f"current price {current_price}")
                print(f"trend is strong = {trend_is_strong} strength =  {trend_strength}")
        # Checking buying variables if set
        elif self.stop_loss_value != 0 and self.long_buy_price != 0 and trend_is_strong: 
            time.sleep(1)
            current_price = float(self.get_current_value())
            time.sleep(1)
            if current_price >= self.long_buy_price:
                print(f"Setting buy on {current_price}")
                print(f"With STOP LOSS of {self.stop_loss_value}")
                volume = self.available_funds * (1 / current_price)
                self.set_buy_order(current_price, volume)
            else:
                print(f"current price {current_price}")
                print(f"trend is strong = {trend_is_strong} strength =  {trend_strength}")
        else:
            print(f"trend is strong = {trend_is_strong} strength =  {trend_strength}")
    
    def set_buy_order(self, buy_price, volume):
        """
        Creating api call data and resetting variables after buying
        """
        while True:        
            try:
                print("Trying to buy 1")
                api_call_data= {
                            "symbol" : self.currency, 
                            "quantity" : self.truncate(volume, 5), 
                            "price" : float(round(buy_price, 5))
                            }
                self.buy_order_api_call(api_call_data)
                data = None
                with open("trades.json", "r", encoding="utf-8") as f:
                    data = json.loads(f.read())
                data["trades"].append(api_call_data)
                with open("trades.json", "w", encoding="utf-8") as f:
                    f.write(json.dumps(data, indent=4))
                open_position = self.get_latest_closed_order_spot() #Last closed order from api 
                self.long_buy_price = 0
                self.last_bought_price = float(open_position["price"])
                self.target_price =  round(self.last_bought_price * self.win_target, 1)
                #self.traded_this_trend = True
                print("set_buy_orderPrint")
                return
            except Exception as e:
                time.sleep(1)
                print(f"{e}")
                pass

    def buy_order_api_call(self, data):
        """
        This is a separate method for handling non-margin buying via the api.
        """
        while True:
            try:
                api_callback_buy = self.api.order_limit_buy(**data)
                open_order = self.get_open_order(api_callback_buy["clientOrderId"])
                if open_order == True:
                    # If trade was accepted we have to wait for it to close
                    while True:
                        open_order = self.get_open_order(api_callback_buy["clientOrderId"])
                        if open_order == True:
                            print("waiting for trade to finish4")
                            time.sleep(1)
                        else:
                            break
                if open_order == False:
                    print("Buy order was made!!")
                    return
            except Exception as e:
                time.sleep(1)
                print(f"{e}")
                pass

    """
    ############## SHORTING #####################
    """
    def check_if_should_sell_short(self):
        """
        Method for checking if short position should be closed
        """
        current_price = float(self.get_current_value())
        if current_price <= self.target_price:
            self.set_sell_short_order(current_price)
        elif current_price >= self.stop_loss_value:
            self.set_sell_short_order(current_price)
    
    def set_sell_short_order(self, price):
        """
        Method for creating api call data and resetting shorting variables.
        """
        while True:        
            try:
                volume = self.shorted_amount
                api_call_data= {
                    "symbol" : "BTCBUSD", 
                    "side" : "BUY",
                    "type" : "LIMIT",
                    "quantity" : bot.truncate(volume, 5),
                    "price" : price,
                    "sideEffectType" : "AUTO_REPAY",
                    "timeInForce" : "GTC"
                    }
                self.short_sell_order_api_call(api_call_data)
                data = None
                with open("trades.json", "r", encoding="utf-8") as f:
                    data = json.loads(f.read())
                data["trades"].append(api_call_data)
                with open("trades.json", "w", encoding="utf-8") as f:
                    f.write(json.dumps(data, indent=4))
                print("SELL WAS MADE!")
                self.stop_loss_value = 0
                self.target_price = 0
                self.shorted_amount = 0
                self.loan_open = False
                time.sleep(1)
                break
            except Exception as e:
                time.sleep(1)
                print(f"{e}")
                pass

    def short_sell_order_api_call(self, data):
        """
        This is a separate method for handling closing of short position via the api.
        """
        api_callback_sell = None
        while True:
            try:
                api_callback_sell = self.api.create_margin_order(**data)
                closed_order = self.wait_for_order_to_be_filled(api_callback_sell["clientOrderId"])
                if closed_order == True:
                    return closed_order
            except Exception as e:
                print(data)
                time.sleep(1)
                print(f"{e}")
                pass

    def check_if_should_short(self, averages, data_from_latest_candle, data):
        """
        Method for checking price data in downtrend and searching for possible short openings.
        """
        trend_strength = round(averages[0]["ema9"] / averages[0]["wma30"], 4)
        trend_is_strong = False
        if trend_strength <= 0.997:
            trend_is_strong = True
        current_price = 0
        if float(data_from_latest_candle[4]) < averages[1]["wma30"] and float(data_from_latest_candle[4]) > averages[1]["ema9"]:
            self.short_buy_price = float(data_from_latest_candle[3])
            self.stop_loss_value = round(averages[0]["wma30"] * 1.005, 1)
            print("Last complete candle closed in between indicators SHORT")
            current_price = float(self.get_current_value())
            if current_price <= self.short_buy_price and trend_is_strong:
                print(f"Setting short on {data_from_latest_candle[3]}")
                print(f"With STOP LOSS of {averages[0]['wma30']}")
                volume = 0
                while True:
                    try:
                        max_loan = self.api.get_max_margin_loan(asset='BTC')
                        volume = self.truncate(float(max_loan["amount"]) * 0.5, 5)
                        break
                    except Exception:
                        time.sleep(1)
                        pass
                self.set_short_order(current_price, volume)
            else:
                print(f"current price {current_price}")
                print(f"trend is strong = {trend_is_strong} strength =  {trend_strength}")
        elif self.stop_loss_value != 0 and self.short_buy_price != 0 and trend_is_strong: 
            current_price = float(self.get_current_value())
            if current_price <= self.short_buy_price:
                print(f"Setting short on {current_price}")
                print(f"With STOP LOSS of {self.stop_loss_value}")
                volume = 0
                while True:
                    try:
                        max_loan = self.api.get_max_margin_loan(asset='BTC')
                        volume = self.truncate(float(max_loan["amount"]) * 0.5, 5)
                        break
                    except Exception:
                        time.sleep(1)
                        pass
                self.set_short_order(current_price, volume)
        else:
            print(f"current price was not set")
            print(f"trend is strong = {trend_is_strong} strength =  {trend_strength}")

    def set_short_order(self, price, volume):
        while True:        
            try:
                print("Trying to short 1")
                api_call_data= {
                    "symbol" : "BTCBUSD", 
                    "side" : "SELL",
                    "type" : "LIMIT",
                    "quantity" : volume,
                    "price" : price,
                    "sideEffectType" : "MARGIN_BUY",
                    "timeInForce" : "GTC"
                    }
                data = None
                with open("trades.json", "r", encoding="utf-8") as f:
                    data = json.loads(f.read())
                data["trades"].append(api_call_data)
                with open("trades.json", "w", encoding="utf-8") as f:
                    f.write(json.dumps(data, indent=4))
                self.short_order_api_call(api_call_data)
                self.target_price = round(price * self.short_win_target, 1)
                self.shorted_amount = self.get_borrowed_btc_margin()
                self.loan_open = True
                print(f"Short order set. Target price : {self.target_price}")
                return
            except Exception as e:
                time.sleep(1)
                print(f"{e}")
                pass

    def short_order_api_call(self, data):
        """
        This is a separate method for handling buying via the api.
        """
        while True:
            try:
                api_callback_buy = self.api.create_margin_order(**data)
                print("API CALL BACK WAS RECEIVED")
                closed_order = self.wait_for_order_to_be_filled(api_callback_buy["clientOrderId"])
                if closed_order == True:
                    return closed_order
            except Exception as e:
                time.sleep(1)
                print(f"{e}")
                pass

    """
    ############## API CALLS GENERAL #####################
    """

    def get_history_data(self):
        """
        Get price data for BTCBUSD
        """
        time.sleep(1)
        data = None
        time_to_get = round(time.time() * 1000) - 324000000
        while True:
            try:
                data = self.api.get_historical_klines("BTCBUSD", "1h", start_str=time_to_get)
                return data
            except Exception as e:
                print(data)
                print(e)
                time.sleep(1)

    def get_current_value(self):
        """
        Get current value for BTCUSD ticker
        """
        data = None
        while True:
            try:
                time.sleep(1)
                data = self.api.get_symbol_ticker(symbol="BTCBUSD") 
                data = float(data["price"])
                return data
            except Exception as e:
                print(e)
                print(data)
                print("TRYING AGAIN TO FETCH DATA")
                time.sleep(1)

    """
    ############## API CALLS SPOT #####################
    """

    def get_available_btc_spot(self):
        """
        Get available BTC from spot (non-margin) account
        """
        api_callback = None
        time.sleep(1)
        while True:
            try:
                api_callback = self.api.get_asset_balance(asset="BTC")
                funds = float(api_callback["free"])
                return funds
            except Exception as e:
                print(api_callback)
                print(e)
                time.sleep(1)
                pass

    def get_available_funds_spot(self):
        """
        Get available BUSD from spot (non-margin) account
        """
        time.sleep(1)
        api_callback = None
        while True:
            try:
                api_callback = self.api.get_asset_balance(asset="BUSD")
                funds = float(api_callback["free"])
                return funds
            except Exception as e:
                print(api_callback)
                print(e)
                time.sleep(1)
                pass

    def get_open_order(self, order_id):
        """
        Method for checking if order closed when selling or buying.
        """
        api_callback = None
        time.sleep(1)
        while True:
            try:
                print(order_id)
                api_callback = self.api.get_order(symbol="BTCBUSD", origClientOrderId=order_id)
                if api_callback["status"] == "FILLED":
                    open_orders = False
                    return open_orders
                elif api_callback["status"] == "NEW":
                    open_orders = True
                    return open_orders
            except Exception as e:
                print(api_callback)
                print(e)
                time.sleep(1)
                pass

    def get_latest_closed_order_spot(self):
        """
        Method for getting last closed order.
        """
        time.sleep(1)
        api_callback = None
        while True:
            try:
                api_callback = self.api.get_all_orders(symbol="BTCBUSD")
                if len(api_callback) != 0:
                    if api_callback[len(api_callback)-1]["status"] == "FILLED":
                        return api_callback[len(api_callback)-1]
                return None
            except Exception as e:
                print(api_callback)
                print(e)
                time.sleep(1)
                pass

    """
    ############## API CALLS MARGIN #####################
    """

    def get_latest_margin_without_id(self):
        """
        Get latest margin account order
        """
        api_callback = None
        time.sleep(1)
        while True:
            try:
                api_callback = self.api.get_all_margin_orders(symbol="BTCBUSD")
                if len(api_callback) == 0:
                    return None
                else:
                    return api_callback[len(api_callback)-1]
            except Exception as e:
                print(api_callback)
                print(e)
                time.sleep(1)
                pass

    def wait_for_order_to_be_filled(self, id):
        """
        Method for waiting for margin order to be filled.
        """
        time.sleep(1)
        api_callback = None
        while True:
            try:
                api_callback = self.api.get_margin_order(symbol="BTCBUSD",  origClientOrderId=id)
                if api_callback["status"] == "FILLED":
                    closed_order = True
                    return closed_order
            except Exception as e:
                print(api_callback)
                print(e)
                time.sleep(1)
                pass

    def get_latest_repay_data(self, id):
        """
        Get data from latest repayment AKA closing of short position
        """
        time.sleep(1)
        api_callback = None
        while True:
            try:
                api_callback = self.api.get_margin_repay_details(asset="BTC", txId=id)
                return api_callback["rows"][0]
            except Exception as e:
                print(api_callback)
                print(e)
                time.sleep(1)
                pass
    
    def get_available_funds_margin(self):
        """
        Get available BUSD from margin account
        """
        time.sleep(1)
        api_callback = None
        while True:
            try:
                api_callback = self.api.get_margin_account()
                for asset in api_callback["userAssets"]:
                    if asset["asset"] == "BUSD":
                        funds = float(asset["free"])
                        return funds
            except Exception as e:
                print(api_callback)
                print(e)
                time.sleep(1)
                pass
    
    def get_borrowed_btc_margin(self):
        """
        Method for getting the amount of open margin position including interest
        """
        time.sleep(1)
        api_callback = None
        while True:
            try:
                api_callback = self.api.get_margin_account()
                for asset in api_callback["userAssets"]:
                    if asset["asset"] == "BTC":
                        funds = float(asset["borrowed"]) + float(asset["interest"])
                        return funds
            except Exception as e:
                print(api_callback)
                print(e)
                time.sleep(1)
                pass

    def get_available_btc_margin(self):
        """
        Method for getting available BTC on margin account
        """
        time.sleep(1)
        api_callback = None
        while True:
            try:
                api_callback = self.api.get_margin_account()
                for asset in api_callback["userAssets"]:
                    if asset["asset"] == "BTC":
                        funds = float(asset["free"])
                        return funds
            except Exception as e:
                print(api_callback)
                print(e)
                time.sleep(1)
                pass

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
    ################ PRODUCE AVERAGES ########################
    """    

    def make_averages(self, data):
        """
        Method for handling history data and constructing needed data for the bot.
        """
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
        """
        Calculating WMA30 indicator
        """
        reversed_data = list(reversed(data))
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
        """
        Calculating EMA9 indicator
        """
        period = 9
        needed_prices_list = []
        index = 0

        for i in list(reversed(data)):
            if index <= 29:
                needed_prices_list.append(float(i[4]))
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


    def truncate(self, f, n):
        return floor(f * 10 ** n) / 10 ** n

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
    bot = trading_bot()
    bot.run()