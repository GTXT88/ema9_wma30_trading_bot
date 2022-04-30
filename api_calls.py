import time
class ApiCalls():
    """
    This class is inhereted by TradingBot.
    Contains methods for Binance API integration.
    """
    def __init__(self) -> None:
        pass

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