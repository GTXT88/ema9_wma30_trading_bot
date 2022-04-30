import json
import time

class Buying():
    """
    This class is inhereted by TradingBot.
    This class contains all functions for buying in uptrend.
    """

    def __init__(self) -> None:
        pass

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