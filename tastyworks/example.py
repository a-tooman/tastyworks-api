import asyncio
import calendar
import logging
from os import environ
from datetime import date, timedelta
from decimal import Decimal, getcontext
from collections import deque
import numpy as np

from tastyworks.models import option_chain, underlying
from tastyworks.models.option import Option, OptionType
from tastyworks.models.order import (Order, OrderDetails, OrderPriceEffect,
                                     OrderType)
from tastyworks.models.session import TastyAPISession
from tastyworks.models.trading_account import TradingAccount
from tastyworks.models.underlying import UnderlyingType
from tastyworks.streamer import DataStreamer
from tastyworks.tastyworks_api import tasty_session

LOGGER = logging.getLogger(__name__)

# test github

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
    _ticker = 'QQQ'
    #_ticker = '/ESM1 (EW3)'
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


def getrsi(_quotes, _obs=14):
    """
    Desc. calculate relative strength index
    RSI = 100.0 – 100.0 / ( 1.0 + RS )
    RS = Average Gain / Average Loss

    Average Gain = [(previous Average Gain) x 13 + current Gain] / 14
    Average Loss = [(previous Average Loss) x 13 + current Loss] / 14

    current Gain = Sum of Gains over the past 14 periods
    current Loss = Sum of Losses over the past 14 periods

    current Average Gain = Sum of Gains over the past 14 periods / 14
    current Average Loss = Sum of Losses over the past 14 periods / 14
    """
    return


def updatersi(_quotearray, _quote):
    _rsilen = 15
    return np.append(_quotearray[1:_rsilen],_quote)

class rsihandler(object):
    def __init__(self, _prd=14):
        self.prd = _prd
        self.set()
        return

    def set(self):
        self.quotes = np.zeros(self.prd+1)
        self.quotesdiff = np.zeros(self.prd)
        return self

    def get(self):
        return {'quotes':self.quotes, 'quotesdiff':self.quotesdiff}

    def update(self, _quote):
        print(_quote)
        print(self.quotes[-1])
        print(self.quotes[-1]-_quote)
        self.quotesdiff = np.append(self.quotesdiff[1:self.prd-1],self.quotes[-1]-_quote)
        self.quotes = np.append(self.quotes[1:self.prd],_quote)
        return

    def getrsi():
        """
        Desc. calculate relative strength index
        RSI = 100.0 – 100.0 / ( 1.0 + RS )
        RS = Average Gain / Average Loss

        Average Gain = [(previous Average Gain) x 13 + current Gain] / 14
        Average Loss = [(previous Average Loss) x 13 + current Loss] / 14

        current Gain = Sum of Gains over the past 14 periods
        current Loss = Sum of Losses over the past 14 periods

        current Average Gain = Sum of Gains over the past 14 periods / 14
        current Average Loss = Sum of Losses over the past 14 periods / 14
        """
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


async def getquote(session:TastyAPISession, streamer:DataStreamer, _ticker="/ESM21:XCME"): #"/ESM21:XCME"
    """
    Desc. display ticker quote
    tickers. /ESM21:XCME (current futures contract), SPY (S&P500 mini), QQQ (NASDAQ100 mini)
    """
    # get account details
    accounts = await TradingAccount.get_remote_accounts(session)
    acct = accounts[0]
    LOGGER.info('Accounts available: %s', accounts)

    # get quote details
    sub_values = {"Quote":[_ticker]}

    await streamer.add_data_sub(sub_values)
    quotehdlr = quotehandler()
    rsihdlr = rsihandler()
    #quotearray = np.zeros(15)
    async for item in streamer.listen():
        quotehdlr.update(item.data[0])
        rsihdlr.update(quotehdlr.mid)
        #quotearray = updatersi(quotearray, quotehdlr.mid)

        LOGGER.info([quotehdlr.get(),rsihdlr.get()])
    return


def main():
    tasty_client = tasty_session.create_new_session(environ.get('TW_USER', ""), environ.get('TW_PASSWORD', ""))

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
        pending_tasks = [
            task for task in asyncio.all_tasks() if not task.done()
        ]
        loop.run_until_complete(asyncio.gather(*pending_tasks))
        loop.close()


if __name__ == '__main__':
    main()
