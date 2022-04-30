import json
import time

class Shorting():
    """
    This class is inhereted by TradingBot.
    This class contains all functions for shorting.
    """
    def __init__(self) -> None:
        pass

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
                    "quantity" : self.truncate(volume, 5),
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