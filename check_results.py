import json
from os import execv
from pandas import DataFrame

if __name__ == "__main__":
    data = None
    funds = 100000
    win_loss = 0.0
    with open("all_trades.json", "r") as file:
        data = json.load(file)

    index = 0
    trade_index = 0
    for trade in data["XXBTZUSD"]:
        if trade["type"] == "sell":
            buy = data["XXBTZUSD"][trade_index-1]
            buy_worth = buy["price"] * buy["volume"]
            funds = funds - buy_worth
            worth_of_trade = trade["volume"] * trade["price"]
            funds = funds + worth_of_trade
            index +=1
            print(f"Funds after {index} bit  and sell: {funds}")
        trade_index += 1

    print("AFTER TRADES WE HAVE...................")
    print(f"{funds} COINS")