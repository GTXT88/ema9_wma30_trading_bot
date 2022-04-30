from pandas import DataFrame
from math import floor
class ProduceIndicators():
    """
    This class is inhereted by TradingBot.
    Contains methods for producing indicators from data
    """
    def __init__(self):
        pass    
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