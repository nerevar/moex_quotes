from datetime import datetime


class GraphBuilder(object):
    def market_filter(self):
        return {
            'engine': 'stock',
            'market': 'index'
        }

    def quote_filter(self):
        return {
            'BOARDID': 'SNDX',
            'SECID': 'IMOEX' # TODO: массив значений для индекса
        }

    def get_date(self, df):
        quote = df.iloc[0]
        dt = datetime.strptime(quote.get('TRADEDATE'), '%Y-%m-%d')
        return int(dt.timestamp()) * 1000

    def get_value(self, df):
        # TODO: на вход принимать df с одним или несколькими рядами
        quote = df.iloc[0]
        return float(quote.get('CLOSE'))