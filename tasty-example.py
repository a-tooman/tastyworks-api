import asyncio
import calendar
import logging
from os import environ
from datetime import date, datetime, timedelta
from decimal import Decimal, getcontext
from collections import deque
import numpy as np
import talib

from tastyworks.models import option_chain, underlying
from tastyworks.models.option import Option, OptionType
from tastyworks.models.order import Order, OrderDetails, OrderPriceEffect, OrderType
from tastyworks.models.session import TastyAPISession
from tastyworks.models.trading_account import TradingAccount
from tastyworks.models.underlying import UnderlyingType

from tastyworks.streamer import DataStreamer
from tastyworks.tastyworks_api import tasty_session

LOGGER = logging.getLogger(__name__)

def get_third_friday(d):
    s = date(d.year, d.month, 15)
    candidate = s + timedelta(days=(calendar.FRIDAY - s.weekday()) % 7)

    # This month's third friday passed
    if candidate < d:
        candidate += timedelta(weeks=4)
        if candidate.day < 15:
            candidate += timedelta(weeks=1)

    return candidate

def getoptchain():
    #_ticker = 'QQQ'
    _ticker = '/ESZ1'
    _strike = 400.0
    _price = 0.0
    """
    orders = await Order.get_remote_orders(session, acct)
    LOGGER.info('Number of active orders: %s', len(orders))

    # create order (short leg)
    details = OrderDetails(
        type=OrderType.LIMIT,
        price=Decimal(_price),
        price_effect=OrderPriceEffect.DEBIT)
    new_order = Order(details)

    opt = Option(
        ticker=_ticker,
        quantity=1,
        expiry=get_third_friday(date.today()),
        strike=Decimal(_strike),
        option_type=OptionType.CALL,
        underlying_type=UnderlyingType.EQUITY
    )
    new_order.add_leg(opt)

    res = await acct.execute_order(new_order, session, dry_run=True)
    LOGGER.info('Order executed successfully: %s', res)

    # get options chain
    undl = underlying.Underlying(_ticker)

    chain = await option_chain.get_option_chain(session, undl)
    LOGGER.info('Chain strikes: %s', chain.get_all_strikes())
    """
    return

async def getaccinfo(session: TastyAPISession):
    # account details
    accounts = await TradingAccount.get_remote_accounts(session)
    acct = accounts[0]
    LOGGER.info('Accounts available: %s', accounts)
    return

class rsihandler(object):
    dplaces = 4
    def __init__(self, _prd=14):
        self.prd = _prd
        self.set()
        return

    def set(self):
        """
        Desc. quotes will be length of self.prd
        """
        self.quotes = np.zeros(self.prd+2)
        return

    def update(self, _quote):
        """
        Desc. append quote to the end
        """
        self.quotes = np.append(self.quotes[1:self.prd+1],_quote)
        return

    def get(self):
        """
        Desc. get the quotes
        """
        return {'quotes':self.quotes}

    def getrsi(self):
        """
        Desc. calculate relative strength index
        """
        return {'rsi':talib.RSI(self.quotes, timeperiod=self.prd)}

class tradehandler(object):
    dplaces = 4
    def __init__(self, _keep=10*60, _tdelta=5):
        self.keep = _keep
        self.tdelta = timedelta(seconds=_tdelta)
        self.set()
        return

    def set(self):
        """
        Desc. set trade
        """
        import math
        self.sym = ""
        self.price = 0.0
        self.prices = np.zeros(self.keep+1)
        self.pricessize = 0
        self.tlast = datetime.now()
        return

    def get(self):
        """
        Desc. get prices
        """
        return {'sym':self.sym,'prices':self.prices[-1], 'pricessize':self.pricessize, 'timedelta':self.tdelta}

    def update(self,_quote):
        """
        Desc. update trade
        """
        if (_quote['time'] - self.tlast) > self.tdelta:
            self.tlast = _quote['time']
            self.sym = _quote['eventSymbol']
            self.price = _quote['price']
            self.change = _quote['change']
            self.prices = np.append(self.prices[1:self.keep],self.price)
            self.pricessize = min(self.keep,self.pricessize+1)
        return

class quotehandler(object):
    dplaces = 4
    def __init__(self):
        self.set()
        return

    def set(self):
        """
        Desc. set quote
        """
        import math
        self.sym = ""

        self.midmin = math.exp(10)
        self.mid = 0.0
        self.midmax = 0.0

        self.ratiomin = math.exp(10)
        self.ratio = 0.0
        self.ratiomax = 0.0
        return

    def get(self):
        """
        Desc. get quote
        """
        return {'mid':self.mid, 'midrank':self.midrank, 'bid/ask':self.ratio}

    def update(self,_quote):
        """
        Desc. update quote
        """
        self.sym = _quote['eventSymbol']

        bsize = _quote['bidSize']
        asize = _quote['askSize']
        self.ratio = round(bsize/asize,self.dplaces)
        if self.ratio < self.ratiomin: self.ratiomin = self.ratio
        if self.ratio > self.ratiomax: self.ratiomax = self.ratio

        bprice = _quote['bidPrice']
        aprice = _quote['askPrice']
        self.mid = round(0.5*bprice+0.5*aprice,self.dplaces)
        if self.mid < self.midmin: self.midmin = self.mid
        if self.mid > self.midmax: self.midmax = self.mid

        try:
            self.midrank = round((self.mid - self.midmin)/(self.midmax - self.midmin),self.dplaces)
        except ZeroDivisionError:
            self.midrank = None
        return

async def getquote(session, streamer, _ticker="BTC/USD:CXTALP"): #"BTC/USD:CXTALP"
    """
    Desc. display ticker quote
    tickers. "BTC/USD:CXTALP" (bitcoin v usd)
    """
    # get account details
    accounts = await TradingAccount.get_remote_accounts(session)

    #acct = accounts[0]
    LOGGER.info('Accounts available: %s', accounts)

    # reset data subscriptions
    await streamer.reset_data_subs()

    # get and handle trades
    sub_values = {'Trade':[_ticker]}
    await streamer.add_data_sub(sub_values)
    tradehdlr = tradehandler()

    # get handle quotes
    #sub_values = {'Quote':[_ticker]}
    #await streamer.add_data_sub(sub_values)
    #quotehdlr = quotehandler()

    #rsihdlr = rsihandler()

    async for item in streamer.listen():
        #LOGGER.info(item.data[0])
        tradehdlr.update(item.data[0])
        LOGGER.info(tradehdlr.get())
    return

def main():
    """
    desc: initialize a session
    """
    tasty_client = tasty_session.create_new_session(
        environ.get('TW_USER', "")
        , environ.get('TW_PASSWORD', ""))

    streamer = DataStreamer(tasty_client)
    LOGGER.info('Streamer token: %s' % streamer.get_streamer_token())
    loop = asyncio.get_event_loop()

    try:
        #loop.run_until_complete(main_loop(tasty_client, streamer))
        loop.run_until_complete(getquote(tasty_client, streamer))
    except Exception:
        LOGGER.exception('Exception in main loop')
    finally:
        # find all futures/tasks still running and wait for them to finish
        pending_tasks = [task for task in asyncio.all_tasks() if not task.done()]
        loop.run_until_complete(asyncio.gather(*pending_tasks))
        loop.close()

if __name__ == '__main__':
    main()
