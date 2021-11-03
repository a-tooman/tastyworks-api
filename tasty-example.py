import asyncio
import copy
import calendar
import logging
from os import environ
from datetime import date, datetime, timedelta
from decimal import Decimal, getcontext
from collections import deque
from math import exp

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

    def getrsi(self, _obs):
        """
        Desc. calculate relative strength index
        """
        return {'rsi':talib.RSI(_obs, timeperiod=self.prd)}

class tradehandler(object):
    """
    Desc. handles a trade subscription
    sym = instrument symbol.
    tdel = time delta (seconds).
    tobs = time of observations (seconds).
    iobs = indicator observations.
    obs = (iobs+1)*(tobs/tdel)
    """
    dplaces = 4
    def __init__(self, _sym="BTC/USD:CXTALP", _tdel=10, _tobs=1*60, _iobs=14+1):
        self.sym = _sym
        self.tdel = _tdel
        self.tobs = _tobs
        self.iobs = _iobs
        self.obs = int((self.tobs)*(self.tobs/self.tdel))
        self.set()
        return

    def set(self):
        """
        Desc. set trade
        OHLC: prcsopen, prcshigh, prcslow, prcsclose
        """
        self.prcsize = 0
        self.count = 0
        # ohlc
        self.prcopen = 0.0
        self.prchigh = 0.0
        self.prclow = pow(10,6)

        self.prcsopen = deque(maxlen=self.obs+1)
        self.prcshigh = deque(maxlen=self.obs+1)
        self.prcslow = deque(maxlen=self.obs+1)
        self.prcsclose = deque(maxlen=self.obs+1)

        self.prct = deque(maxlen=self.obs+1)
        self.tnext = datetime.now() + timedelta(seconds=self.tdel)
        self.tnext.replace(microsecond=0)
        return

    def get(self):
        """
        Desc. get trades
        """
        if self.prcsize < 1:
            return {'sym':self.sym, 'prcsize':self.prcsize,'prc':self.prcclose}
        else:
            return {'sym':self.sym
                , 'count':self.count
                , 'prcsize':self.prcsize
                , 'prcs':np.vstack(
                    [np.array(self.prct)[-self.prcsize:]
                    ,np.array(self.prcsopen)[-self.prcsize:]
                    ,np.array(self.prcshigh)[-self.prcsize:]
                    ,np.array(self.prcslow)[-self.prcsize:]
                    ,np.array(self.prcsclose)[-self.prcsize:]]).T
                }

    def getclose(self):
        """
        Desc. get prices
        """
        return np.append(self.prcs[1:self.obs],self.prc/self.prccount)

    def update(self,_trade):
        """
        Desc. update OHLC
        """
        self.count+=1
        self.prcclose = _trade['price']
        if self.prchigh < _trade['price']: self.prchigh = _trade['price']
        if _trade['price'] < self.prclow: self.prclow = _trade['price']
        if _trade['time'] > self.tnext:
            # append OHLC
            self.prcsopen.append(self.prcopen)
            self.prcshigh.append(self.prchigh)
            self.prcslow.append(self.prclow)
            self.prcsclose.append(self.prcclose)

            self.prcopen = _trade['price']
            self.prchigh = 0.0
            self.prclow = pow(10,6)
            # append time
            self.prct.append(self.tnext)
            self.prcsize = min(self.obs,self.prcsize+1)
            self.tnext = self.tnext + timedelta(seconds=self.tdel)
            self.tnext.replace(microsecond=0)
            self.count=0
        return

    def getslicer(self, _iobs):
        """
        Desc. get the slice for rsi
        """
        return np.linspace(start=self.obs-self.prcesize, stop=self.obs, num=_iobs+1, dtype=int)

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
    rsihdlr = rsihandler()

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

def testdt():
    _obs = np.array([63173.2065942, 63165.60865079, 63139.27961538,
               63124.31290323, 63131.55138462, 63122.32398437,
               63104.58233871, 63138.50757813, 63139.05274194,
               63146.16126984, 63134.81223077, 63137.99401515,
               63173.2065942 , 63165.60865079, 63139.27961538,
               63124.31290323, 63131.55138462, 63122.32398437,
               63104.58233871, 63138.50757813, 63139.05274194,
               63146.16126984, 63134.81223077, 63137.99401515,
               63173.2065942 , 63165.60865079, 63139.27961538,
               63124.31290323, 63131.55138462, 63122.32398437,
               63104.58233871, 63138.50757813, 63139.05274194,
               63146.16126984, 63134.81223077, 63137.99401515,
               63127.88171642, 63103.0808871 , 63138.74286885,
               63138.74286885, 63103.0808871, 63173.2065942,
               63165.60865079], dtype=float)

    prcesize = 42
    print(prcesize)
    tobs = int(3*60)
    tdel = int(1*60)
    iobs = int(14)
    obs = iobs*tobs/tdel
    steps = int(prcesize/iobs)
    print(steps)
    start = obs+1-steps*iobs
    print(obs)

    lin = np.linspace(start=obs-prcesize, stop=obs, num=iobs+1, dtype=int)
    print(lin)
    print(_obs[lin])
    """
    obs=1*60*(14+1)
    prct = np.ndarray(shape=(obs,), dtype=datetime)
    print(prct)
    print(prct.shape)

    prct = np.append(prct[1:obs],[dt], axis=0)
    print(prct)
    print(prct.shape)
    """

if __name__ == '__main__':
    #main()
    #testnp()
    #testdeque()
    testdt()
