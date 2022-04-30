import json
import time
class Selling():
    """
    This class is inhereted by TradingBot.
    This class contains all functions for selling in uptrend.
    """

    def __init__(self) -> None:
        pass
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