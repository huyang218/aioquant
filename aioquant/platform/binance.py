# -*- coding:utf-8 -*-

"""
Binance Trade module.
https://github.com/binance-exchange/binance-official-api-docs/blob/master/rest-api.md

Author: HuangTao
Date:   2018/08/09
Email:  huangtao@ifclover.com
"""

import json
import copy
import hmac
import hashlib

from urllib.parse import urljoin

from aioquant.error import Error
from aioquant.utils import tools
from aioquant.utils import logger
from aioquant.order import Order
from aioquant.tasks import SingleTask, LoopRunTask
from aioquant.utils.decorator import async_method_locker
from aioquant.utils.web import Websocket, AsyncHttpRequests
from aioquant.order import ORDER_ACTION_SELL, ORDER_ACTION_BUY, ORDER_TYPE_LIMIT, ORDER_TYPE_MARKET
from aioquant.order import ORDER_STATUS_SUBMITTED, ORDER_STATUS_PARTIAL_FILLED, ORDER_STATUS_FILLED, \
    ORDER_STATUS_CANCELED, ORDER_STATUS_FAILED

__all__ = ("BinanceRestAPI", "BinanceTrade", )


class BinanceRestAPI:
    """Binance REST API client.

    Attributes:
        host: HTTP request host.
        access_key: Account's ACCESS KEY.
        secret_key: Account's SECRET KEY.
    """

    def __init__(self, access_key, secret_key, host="https://api.binance.com"):
        """Initialize REST API client."""
        self._host = host
        self._access_key = access_key
        self._secret_key = secret_key

    async def get_user_account(self):
        """Get user account information.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/api/v3/account"
        ts = tools.get_cur_timestamp_ms()
        params = {
            "timestamp": str(ts)
        }
        success, error = await self.request("GET", uri, params, auth=True)
        return success, error

    async def get_server_time(self):
        """Get server time.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/api/v1/time"
        success, error = await self.request("GET", uri)
        return success, error

    async def get_exchange_info(self):
        """Get exchange information.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/api/v1/exchangeInfo"
        success, error = await self.request("GET", uri)
        return success, error

    async def get_latest_ticker(self, symbol):
        """Get latest ticker.

        Args:
            symbol: Symbol name, e.g. `BTCUSDT`.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/api/v1/ticker/24hr"
        params = {
            "symbol": symbol
        }
        success, error = await self.request("GET", uri, params=params)
        return success, error

    async def get_orderbook(self, symbol, limit=10):
        """Get orderbook.

        Args:
            symbol: Symbol name, e.g. `BTCUSDT`.
            limit: Number of results per request. (default 10)

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/api/v1/depth"
        params = {
            "symbol": symbol,
            "limit": limit
        }
        success, error = await self.request("GET", uri, params=params)
        return success, error

    async def create_order(self, action, symbol, price, quantity, client_order_id=None):
        """Create an order.
        Args:
            action: Trade direction, `BUY` or `SELL`.
            symbol: Symbol name, e.g. `BTCUSDT`.
            price: Price of each contract.
            quantity: The buying or selling quantity.
            client_order_id: Client order id.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/api/v3/order"
        data = {
            "symbol": symbol,
            "side": action,
            "type": "LIMIT",
            "timeInForce": "GTC",
            "quantity": quantity,
            "price": price,
            "recvWindow": "5000",
            "newOrderRespType": "FULL",
            "timestamp": tools.get_cur_timestamp_ms()
        }
        if client_order_id:
            data["newClientOrderId"] = client_order_id
        success, error = await self.request("POST", uri, body=data, auth=True)
        return success, error

    async def revoke_order(self, symbol, order_id, client_order_id=None):
        """Cancelling an unfilled order.
        Args:
            symbol: Symbol name, e.g. `BTCUSDT`.
            order_id: Order id.
            client_order_id: Client order id.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/api/v3/order"
        params = {
            "symbol": symbol,
            "orderId": order_id,
            "timestamp": tools.get_cur_timestamp_ms()
        }
        if client_order_id:
            params["origClientOrderId"] = client_order_id
        success, error = await self.request("DELETE", uri, params=params, auth=True)
        return success, error

    async def get_order_status(self, symbol, order_id, client_order_id):
        """Get order details by order id.

        Args:
            symbol: Symbol name, e.g. `BTCUSDT`.
            order_id: Order id.
            client_order_id: Client order id.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/api/v3/order"
        params = {
            "symbol": symbol,
            "orderId": str(order_id),
            "origClientOrderId": client_order_id,
            "timestamp": tools.get_cur_timestamp_ms()
        }
        success, error = await self.request("GET", uri, params=params, auth=True)
        return success, error

    async def get_all_orders(self, symbol):
        """Get all account orders; active, canceled, or filled.
        Args:
            symbol: Symbol name, e.g. `BTCUSDT`.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/api/v3/allOrders"
        params = {
            "symbol": symbol,
            "timestamp": tools.get_cur_timestamp_ms()
        }
        success, error = await self.request("GET", uri, params=params, auth=True)
        return success, error

    async def get_open_orders(self, symbol):
        """Get all open order information.
        Args:
            symbol: Symbol name, e.g. `BTCUSDT`.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/api/v3/openOrders"
        params = {
            "symbol": symbol,
            "timestamp": tools.get_cur_timestamp_ms()
        }
        success, error = await self.request("GET", uri, params=params, auth=True)
        return success, error

    async def get_listen_key(self):
        """Get listen key, start a new user data stream.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/api/v1/userDataStream"
        success, error = await self.request("POST", uri)
        return success, error

    async def put_listen_key(self, listen_key):
        """Keepalive a user data stream to prevent a time out.

        Args:
            listen_key: Listen key.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/api/v1/userDataStream"
        params = {
            "listenKey": listen_key
        }
        success, error = await self.request("PUT", uri, params=params)
        return success, error

    async def delete_listen_key(self, listen_key):
        """Delete a listen key.

        Args:
            listen_key: Listen key.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/api/v1/userDataStream"
        params = {
            "listenKey": listen_key
        }
        success, error = await self.request("DELETE", uri, params=params)
        return success, error

    async def get_klines(self, symbol, start_time=None, end_time=None, interval="1m",  limit=500):
        """Get kilnes list"""
        uri = "/api/v3/klines"

        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }
        if(start_time is not None):
            params.startTime = start_time
        if(end_time is not None):
            params.endTime = end_time
        success, error = await self.request("GET", uri, params=params)
        return success, error

    async def get_futures_transfer(self, start_time, end_time=None, current=1, size=10):
        """
        获取合约资金划转历史
        {
            "rows": [
                {
                "asset": "USDT",          // 资产
                "tranId": 100000001,      // 划转ID         
                "amount": "40.84624400",  // 数量
                "type": "1",              // 划转方向: 1( 现货向USDT本位合约), 2( USDT本位合约向现货), 3( 现货向币本位合约), and 4( 币本位合约向现货)
                "timestamp": 1555056425000,   // 时间戳
                "status": "CONFIRMED"         // PENDING (等待执行), CONFIRMED (成功划转), FAILED (执行失败);
                }
            ],
            "total": 1
        }

        """
        uri = "/sapi/v1/futures/transfer"
        params = {
            "asset": "USDT",
            "startTime": start_time,
            "current": current,
            "size": size,
            "timestamp": tools.get_cur_timestamp_ms()
        }
        if(end_time is not None):
            params["endTime"] = end_time
        success, error = await self.request("GET", uri, params=params, auth=True)
        return success, error

    async def futures_transfer(self, amount, t):
        """
        执行现货账户与合约账户之间的划转
        amount	The amount to be transferred
        type	1: 现货账户向USDT合约账户划转
                2: USDT合约账户向现货账户划转
                3: 现货账户向币本位合约账户划转
                4: 币本位合约账户向现货账户划转

        {
            "tranId": 100000001    // 划转 ID 
        }
        """
        uri = "/sapi/v1/futures/transfer"
        params = {
            "asset": "USDT",
            "amount": amount,
            "type": t,
            "timestamp": tools.get_cur_timestamp_ms()
        }
        success, error = await self.request("POST", uri, params=params, auth=True)
        return success, error

    async def request(self, method, uri, params=None, body=None, headers=None, auth=False):
        """Do HTTP request.

        Args:
            method: HTTP request method. `GET` / `POST` / `DELETE` / `PUT`.
            uri: HTTP request uri.
            params: HTTP query params.
            body:   HTTP request body.
            headers: HTTP request headers.
            auth: If this request requires authentication.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        url = urljoin(self._host, uri)
        data = {}
        if params:
            data.update(params)
        if body:
            data.update(body)

        if data:
            query = "&".join(["=".join([str(k), str(v)])
                              for k, v in data.items()])
        else:
            query = ""
        if auth and query:
            signature = hmac.new(self._secret_key.encode(
            ), query.encode(), hashlib.sha256).hexdigest()
            query += "&signature={s}".format(s=signature)
        if query:
            url += ("?" + query)

        if not headers:
            headers = {}
        headers["X-MBX-APIKEY"] = self._access_key
        _, success, error = await AsyncHttpRequests.fetch(method, url, headers=headers, timeout=10, verify_ssl=False)
        return success, error


class BinanceMarginAPI:
    """
    币安杠杆交易API
    """
    def __init__(self, access_key, secret_key, host="https://api.binance.com"):
        """Initialize REST API client."""
        self._host = host
        self._access_key = access_key
        self._secret_key = secret_key

    async def get_user_account(self,symbols=None):
        """
        查询杠杆逐仓账户信息
        {
            "assets":[
                {
                    "baseAsset": 
                    {
                    "asset": "BTC",
                    "borrowEnabled": true,
                    "borrowed": "0.00000000",
                    "free": "0.00000000",
                    "interest": "0.00000000",
                    "locked": "0.00000000",
                    "netAsset": "0.00000000",
                    "netAssetOfBtc": "0.00000000",
                    "repayEnabled": true,
                    "totalAsset": "0.00000000"
                    },
                    "quoteAsset": 
                    {
                    "asset": "USDT",
                    "borrowEnabled": true,
                    "borrowed": "0.00000000",
                    "free": "0.00000000",
                    "interest": "0.00000000",
                    "locked": "0.00000000",
                    "netAsset": "0.00000000",
                    "netAssetOfBtc": "0.00000000",
                    "repayEnabled": true,
                    "totalAsset": "0.00000000"
                    },
                    "symbol": "BTCUSDT"
                    "isolatedCreated": true, 
                    "marginLevel": "0.00000000", 
                    "marginLevelStatus": "EXCESSIVE", // "EXCESSIVE", "NORMAL", "MARGIN_CALL", "PRE_LIQUIDATION", "FORCE_LIQUIDATION"
                    "marginRatio": "0.00000000",
                    "indexPrice": "10000.00000000"
                    "liquidatePrice": "1000.00000000",
                    "liquidateRate": "1.00000000"
                    "tradeEnabled": true
                }
                ],
                "totalAssetOfBtc": "0.00000000",
                "totalLiabilityOfBtc": "0.00000000",
                "totalNetAssetOfBtc": "0.00000000" 
            }
        """
        uri = "/sapi/v1/margin/isolated/account"
        params = {
            "timestamp": tools.get_cur_timestamp_ms()
        }
        if(symbols is not None):
            params["symbols"] = symbols
        
        success, error = await self.request("GET", uri, params=params, auth=True)
        return success, error

    async def request(self, method, uri, params=None, body=None, headers=None, auth=False):
        """Do HTTP request.

        Args:
            method: HTTP request method. `GET` / `POST` / `DELETE` / `PUT`.
            uri: HTTP request uri.
            params: HTTP query params.
            body:   HTTP request body.
            headers: HTTP request headers.
            auth: If this request requires authentication.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        url = urljoin(self._host, uri)
        data = {}
        if params:
            data.update(params)
        if body:
            data.update(body)

        if data:
            query = "&".join(["=".join([str(k), str(v)])
                              for k, v in data.items()])
        else:
            query = ""
        if auth and query:
            signature = hmac.new(self._secret_key.encode(
            ), query.encode(), hashlib.sha256).hexdigest()
            query += "&signature={s}".format(s=signature)
        if query:
            url += ("?" + query)

        if not headers:
            headers = {}
        headers["X-MBX-APIKEY"] = self._access_key
        _, success, error = await AsyncHttpRequests.fetch(method, url, headers=headers, timeout=10, verify_ssl=False)
        return success, error


class BinanceUFutureAPI:
    """
    币安合约交易API，U本位交易模型
    """

    def __init__(self, access_key, secret_key, host="https://fapi.binance.com"):
        """Initialize REST API client."""
        self._host = host
        self._access_key = access_key
        self._secret_key = secret_key

    async def get_position_side(self):
        """
        查询用户目前在 所有symbol 合约上的持仓模式：双向持仓或单向持仓。
        {
            "dualSidePosition": true // "true": 双向持仓模式；"false": 单向持仓模式
        }
        """
        uri = "/fapi/v1/positionSide/dual"
        params = {
            "timestamp": tools.get_cur_timestamp_ms()
        }
        success, error = await self.request("GET", uri, params=params, auth=True)
        return success, error

    async def get_order(self, symbol, order_id=None):
        """
        查询订单状态

        请注意，如果订单满足如下条件，不会被查询到：
            订单的最终状态为 CANCELED 或者 EXPIRED, 并且
            订单没有任何的成交记录, 并且
            订单生成时间 + 7天 < 当前时间
        """
        uri = "/fapi/v1/order"
        params = {
            "symbol": symbol,
            "timestamp": tools.get_cur_timestamp_ms()
        }
        if(order_id is not None):
            params["orderId"] = order_id
        success, error = await self.request("GET", uri, params=params, auth=True)
        return success, error

    async def get_all_orders(self, symbol, order_id=None, start_time=None, end_time=None, limit=500):
        """Get all account orders; active, canceled, or filled.
        These orders will not be found:
        order status is CANCELED or EXPIRED, AND
        order has NO filled trade, AND
        created time + 7 days < current time 

        If orderId is set, it will get orders >= that orderId. Otherwise most recent orders are returned.
        The query time period must be less then 7 days( default as the recent 7 days).
         """
        uri = "/fapi/v1/allOrders"

        params = {
            "symbol": symbol,
            "timestamp": tools.get_cur_timestamp_ms()
        }
        if(order_id is not None):
            params.orderId = order_id
        if(start_time is not None):
            params["startTime"] = start_time
        if(end_time is not None):
            params["endTime"] = end_time

        success, error = await self.request("GET", uri, params=params, auth=True)
        return success, error

    async def get_open_order(self,symbol,order_id=None):
        """
        查询当前挂单
        {
            "avgPrice": "0.00000",              // 平均成交价
            "clientOrderId": "abc",             // 用户自定义的订单号
            "cumQuote": "0",                        // 成交金额
            "executedQty": "0",                 // 成交量
            "orderId": 1917641,                 // 系统订单号
            "origQty": "0.40",                  // 原始委托数量
            "origType": "TRAILING_STOP_MARKET", // 触发前订单类型
            "price": "0",                   // 委托价格
            "reduceOnly": false,                // 是否仅减仓
            "side": "BUY",                      // 买卖方向
            "status": "NEW",                    // 订单状态
            "positionSide": "SHORT", // 持仓方向
            "stopPrice": "9300",                    // 触发价，对`TRAILING_STOP_MARKET`无效
            "closePosition": false,   // 是否条件全平仓
            "symbol": "BTCUSDT",                // 交易对
            "time": 1579276756075,              // 订单时间
            "timeInForce": "GTC",               // 有效方法
            "type": "TRAILING_STOP_MARKET",     // 订单类型
            "activatePrice": "9020", // 跟踪止损激活价格, 仅`TRAILING_STOP_MARKET` 订单返回此字段
            "priceRate": "0.3", // 跟踪止损回调比例, 仅`TRAILING_STOP_MARKET` 订单返回此字段
            "updateTime": 1579276756075,        // 更新时间
            "workingType": "CONTRACT_PRICE", // 条件价格触发类型
            "priceProtect": false            // 是否开启条件单触发保护
        }
        """
        uri = "/fapi/v1/openOrder"

        params = {
            "symbol": symbol,
            "timestamp": tools.get_cur_timestamp_ms()
        }

        if(order_id is not None):
            params["orderId"] = order_id
        
        success, error = await self.request("GET", uri, params=params, auth=True)
        return success, error

    async def get_balance(self):
        """
        账户余额V2

        [
            {
                "accountAlias": "SgsR",    // 账户唯一识别码
                "asset": "USDT",        // 资产
                "balance": "122607.35137903",   // 总余额
                "crossWalletBalance": "23.72469206", // 全仓余额
                "crossUnPnl": "0.00000000"  // 全仓持仓未实现盈亏
                "availableBalance": "23.72469206",       // 下单可用余额
                "maxWithdrawAmount": "23.72469206",     // 最大可转出余额
                "marginAvailable": true,    // 是否可用作联合保证金
                "updateTime": 1617939110373
            }
        ]
        """
        uri = "/fapi/v2/balance"

        params = {
            "timestamp": tools.get_cur_timestamp_ms()
        }
        
        success, error = await self.request("GET", uri, params=params, auth=True)
        return success, error

    async def get_user_account(self):
        """
        账户信息V2

        {
            "feeTier": 0,  // 手续费等级
            "canTrade": true,  // 是否可以交易
            "canDeposit": true,  // 是否可以入金
            "canWithdraw": true, // 是否可以出金
            "updateTime": 0,
            "totalInitialMargin": "0.00000000",  // 但前所需起始保证金总额(存在逐仓请忽略), 仅计算usdt资产
            "totalMaintMargin": "0.00000000",  // 维持保证金总额, 仅计算usdt资产
            "totalWalletBalance": "23.72469206",   // 账户总余额, 仅计算usdt资产
            "totalUnrealizedProfit": "0.00000000",  // 持仓未实现盈亏总额, 仅计算usdt资产
            "totalMarginBalance": "23.72469206",  // 保证金总余额, 仅计算usdt资产
            "totalPositionInitialMargin": "0.00000000",  // 持仓所需起始保证金(基于最新标记价格), 仅计算usdt资产
            "totalOpenOrderInitialMargin": "0.00000000",  // 当前挂单所需起始保证金(基于最新标记价格), 仅计算usdt资产
            "totalCrossWalletBalance": "23.72469206",  // 全仓账户余额, 仅计算usdt资产
            "totalCrossUnPnl": "0.00000000",    // 全仓持仓未实现盈亏总额, 仅计算usdt资产
            "availableBalance": "23.72469206",       // 可用余额, 仅计算usdt资产
            "maxWithdrawAmount": "23.72469206"     // 最大可转出余额, 仅计算usdt资产
            "assets": [
                {
                    "asset": "USDT",        //资产
                    "walletBalance": "23.72469206",  //余额
                    "unrealizedProfit": "0.00000000",  // 未实现盈亏
                    "marginBalance": "23.72469206",  // 保证金余额
                    "maintMargin": "0.00000000",    // 维持保证金
                    "initialMargin": "0.00000000",  // 当前所需起始保证金
                    "positionInitialMargin": "0.00000000",  // 持仓所需起始保证金(基于最新标记价格)
                    "openOrderInitialMargin": "0.00000000", // 当前挂单所需起始保证金(基于最新标记价格)
                    "crossWalletBalance": "23.72469206",  //全仓账户余额
                    "crossUnPnl": "0.00000000" // 全仓持仓未实现盈亏
                    "availableBalance": "23.72469206",       // 可用余额
                    "maxWithdrawAmount": "23.72469206",     // 最大可转出余额
                    "marginAvailable": true    // 是否可用作联合保证金
                },
                {
                    "asset": "BUSD",        //资产
                    "walletBalance": "103.12345678",  //余额
                    "unrealizedProfit": "0.00000000",  // 未实现盈亏
                    "marginBalance": "103.12345678",  // 保证金余额
                    "maintMargin": "0.00000000",    // 维持保证金
                    "initialMargin": "0.00000000",  // 当前所需起始保证金
                    "positionInitialMargin": "0.00000000",  // 持仓所需起始保证金(基于最新标记价格)
                    "openOrderInitialMargin": "0.00000000", // 当前挂单所需起始保证金(基于最新标记价格)
                    "crossWalletBalance": "103.12345678",  //全仓账户余额
                    "crossUnPnl": "0.00000000" // 全仓持仓未实现盈亏
                    "availableBalance": "103.12345678",       // 可用余额
                    "maxWithdrawAmount": "103.12345678",     // 最大可转出余额
                    "marginAvailable": true    // 否可用作联合保证金
                }
            ],
            "positions": [  // 头寸，将返回所有市场symbol。
                //根据用户持仓模式展示持仓方向，即双向模式下只返回BOTH持仓情况，单向模式下只返回 LONG 和 SHORT 持仓情况
                {
                    "symbol": "BTCUSDT",  // 交易对
                    "initialMargin": "0",   // 当前所需起始保证金(基于最新标记价格)
                    "maintMargin": "0", //维持保证金
                    "unrealizedProfit": "0.00000000",  // 持仓未实现盈亏
                    "positionInitialMargin": "0",  // 持仓所需起始保证金(基于最新标记价格)
                    "openOrderInitialMargin": "0",  // 当前挂单所需起始保证金(基于最新标记价格)
                    "leverage": "100",  // 杠杆倍率
                    "isolated": true,  // 是否是逐仓模式
                    "entryPrice": "0.00000",  // 持仓成本价
                    "maxNotional": "250000",  // 当前杠杆下用户可用的最大名义价值
                    "positionSide": "BOTH",  // 持仓方向
                    "positionAmt": "0"      // 持仓数量
                }
            ]
        }
        """
        uri = "/fapi/v2/account"

        params = {
            "timestamp": tools.get_cur_timestamp_ms()
        }
        
        success, error = await self.request("GET", uri, params=params, auth=True)
        return success, error

    async def request(self, method, uri, params=None, body=None, headers=None, auth=False):
        """Do HTTP request.

        Args:
            method: HTTP request method. `GET` / `POST` / `DELETE` / `PUT`.
            uri: HTTP request uri.
            params: HTTP query params.
            body:   HTTP request body.
            headers: HTTP request headers.
            auth: If this request requires authentication.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        url = urljoin(self._host, uri)
        data = {}
        if params:
            data.update(params)
        if body:
            data.update(body)

        if data:
            query = "&".join(["=".join([str(k), str(v)])
                              for k, v in data.items()])
        else:
            query = ""
        if auth and query:
            signature = hmac.new(self._secret_key.encode(
            ), query.encode(), hashlib.sha256).hexdigest()
            query += "&signature={s}".format(s=signature)
        if query:
            url += ("?" + query)

        if not headers:
            headers = {}
        headers["X-MBX-APIKEY"] = self._access_key
        _, success, error = await AsyncHttpRequests.fetch(method, url, headers=headers, timeout=10, verify_ssl=False)
        return success, error


class BinanceTrade:
    """Binance Trade module. You can initialize trade object with some attributes in kwargs.

    Attributes:
        account: Account name for this trade exchange.
        strategy: What's name would you want to created for your strategy.
        symbol: Symbol name for your trade.
        host: HTTP request host. (default "https://api.binance.com")
        wss: Websocket address. (default "wss://stream.binance.com:9443")
        access_key: Account's ACCESS KEY.
        secret_key Account's SECRET KEY.
        order_update_callback: You can use this param to specify a async callback function when you initializing Trade
            module. `order_update_callback` is like `async def on_order_update_callback(order: Order): pass` and this
            callback function will be executed asynchronous when some order state updated.
        init_callback: You can use this param to specify a async callback function when you initializing Trade
            module. `init_callback` is like `async def on_init_callback(success: bool, **kwargs): pass`
            and this callback function will be executed asynchronous after Trade module object initialized done.
        error_callback: You can use this param to specify a async callback function when you initializing Trade
            module. `error_callback` is like `async def on_error_callback(error: Error, **kwargs): pass`
            and this callback function will be executed asynchronous when some error occur while trade module is running.
    """

    def __init__(self, **kwargs):
        """Initialize Trade module."""
        e = None
        if not kwargs.get("account"):
            e = Error("param account miss")
        if not kwargs.get("strategy"):
            e = Error("param strategy miss")
        if not kwargs.get("symbol"):
            e = Error("param symbol miss")
        if not kwargs.get("host"):
            kwargs["host"] = "https://api.binance.com"
        if not kwargs.get("wss"):
            kwargs["wss"] = "wss://stream.binance.com:9443"
        if not kwargs.get("access_key"):
            e = Error("param access_key miss")
        if not kwargs.get("secret_key"):
            e = Error("param secret_key miss")
        if e:
            logger.error(e, caller=self)
            SingleTask.run(kwargs["error_callback"], e)
            SingleTask.run(kwargs["init_callback"], False)

        self._account = kwargs["account"]
        self._strategy = kwargs["strategy"]
        self._platform = kwargs["platform"]
        self._symbol = kwargs["symbol"]
        self._host = kwargs["host"]
        self._wss = kwargs["wss"]
        self._access_key = kwargs["access_key"]
        self._secret_key = kwargs["secret_key"]
        self._order_update_callback = kwargs.get("order_update_callback")
        self._init_callback = kwargs.get("init_callback")
        self._error_callback = kwargs.get("error_callback")

        # Row symbol name, same as Binance Exchange.
        self._raw_symbol = self._symbol.replace("/", "")
        self._listen_key = None  # Listen key for Websocket authentication.
        # Asset data. e.g. {"BTC": {"free": "1.1", "locked": "2.2", "total": "3.3"}, ... }
        self._assets = {}
        self._orders = {}  # Order data. e.g. {order_no: order, ... }

        # Initialize our REST API client.
        self._rest_api = BinanceRestAPI(
            self._host, self._access_key, self._secret_key)

        # Create a loop run task to reset listen key every 30 minutes.
        LoopRunTask.register(self._reset_listen_key, 60 * 30)

        # Create a coroutine to initialize Websocket connection.
        SingleTask.run(self._init_websocket)

        LoopRunTask.register(self._send_heartbeat_msg, 10)

    async def _send_heartbeat_msg(self, *args, **kwargs):
        await self._ws.ping()

    @property
    def assets(self):
        return copy.copy(self._assets)

    @property
    def orders(self):
        return copy.copy(self._orders)

    @property
    def rest_api(self):
        return self._rest_api

    async def _init_websocket(self):
        """Initialize Websocket connection.
        """
        # Get listen key first.
        success, error = await self._rest_api.get_listen_key()
        if error:
            e = Error("get listen key failed: {}".format(error))
            logger.error(e, caller=self)
            SingleTask.run(self._error_callback, e)
            SingleTask.run(self._init_callback, False)
            return
        self._listen_key = success["listenKey"]
        uri = "/ws/" + self._listen_key
        url = urljoin(self._wss, uri)
        self._ws = Websocket(url, self.connected_callback,
                             process_callback=self.process)

    async def _reset_listen_key(self, *args, **kwargs):
        """Reset listen key."""
        if not self._listen_key:
            logger.error("listen key not initialized!", caller=self)
            return
        await self._rest_api.put_listen_key(self._listen_key)
        logger.info("reset listen key success!", caller=self)

    async def connected_callback(self):
        """After websocket connection created successfully, pull back all open order information."""
        logger.info(
            "Websocket connection authorized successfully.", caller=self)
        order_infos, error = await self._rest_api.get_open_orders(self._raw_symbol)
        if error:
            e = Error("get open orders error: {}".format(error))
            SingleTask.run(self._error_callback, e)
            SingleTask.run(self._init_callback, False)
            return
        for order_info in order_infos:
            if order_info["status"] == "NEW":
                status = ORDER_STATUS_SUBMITTED
            elif order_info["status"] == "PARTIALLY_FILLED":
                status = ORDER_STATUS_PARTIAL_FILLED
            elif order_info["status"] == "FILLED":
                status = ORDER_STATUS_FILLED
            elif order_info["status"] == "CANCELED":
                status = ORDER_STATUS_CANCELED
            elif order_info["status"] == "REJECTED":
                status = ORDER_STATUS_FAILED
            elif order_info["status"] == "EXPIRED":
                status = ORDER_STATUS_FAILED
            else:
                logger.warn("unknown status:", order_info, caller=self)
                SingleTask.run(self._error_callback, "order status error.")
                continue

            order_id = str(order_info["orderId"])
            info = {
                "platform": self._platform,
                "account": self._account,
                "strategy": self._strategy,
                "order_id": order_id,
                "client_order_id": order_info["clientOrderId"],
                "action": ORDER_ACTION_BUY if order_info["side"] == "BUY" else ORDER_ACTION_SELL,
                "order_type": ORDER_TYPE_LIMIT if order_info["type"] == "LIMIT" else ORDER_TYPE_MARKET,
                "symbol": self._symbol,
                "price": order_info["price"],
                "quantity": order_info["origQty"],
                "remain": float(order_info["origQty"]) - float(order_info["executedQty"]),
                "status": status,
                "ctime": order_info["time"],
                "utime": order_info["updateTime"]
            }
            order = Order(**info)
            self._orders[order_id] = order
            SingleTask.run(self._order_update_callback, copy.copy(order))

        SingleTask.run(self._init_callback, True, None)

    async def create_order(self, action, price, quantity, *args, **kwargs):
        """Create an order.

        Args:
            action: Trade direction, `BUY` or `SELL`.
            price: Price of each order.
            quantity: The buying or selling quantity.

        Returns:
            order_id: Order id if created successfully, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        client_order_id = kwargs["client_order_id"]
        result, error = await self._rest_api.create_order(action, self._raw_symbol, price, quantity, client_order_id)
        if error:
            SingleTask.run(self._error_callback, error)
            return None, error
        order_id = str(result["orderId"])
        return order_id, None

    async def revoke_order(self, *order_ids):
        """Revoke (an) order(s).

        Args:
            order_ids: Order id list, you can set this param to 0 or multiple items. If you set 0 param, you can cancel
                all orders for this symbol(initialized in Trade object). If you set 1 param, you can cancel an order.
                If you set multiple param, you can cancel multiple orders. Do not set param length more than 100.

        Returns:
            Success or error, see bellow.
        """
        # If len(order_nos) == 0, you will cancel all orders for this symbol(initialized in Trade object).
        if len(order_ids) == 0:
            order_infos, error = await self._rest_api.get_open_orders(self._raw_symbol)
            if error:
                SingleTask.run(self._error_callback, error)
                return False, error
            for order_info in order_infos:
                _, error = await self._rest_api.revoke_order(self._raw_symbol, order_info["orderId"])
                if error:
                    SingleTask.run(self._error_callback, error)
                    return False, error
            return True, None

        # If len(order_nos) == 1, you will cancel an order.
        if len(order_ids) == 1:
            success, error = await self._rest_api.revoke_order(self._raw_symbol, order_ids[0])
            if error:
                SingleTask.run(self._error_callback, error)
                return order_ids[0], error
            else:
                return order_ids[0], None

        # If len(order_nos) > 1, you will cancel multiple orders.
        if len(order_ids) > 1:
            success, error = [], []
            for order_id in order_ids:
                _, e = await self._rest_api.revoke_order(self._raw_symbol, order_id)
                if e:
                    SingleTask.run(self._error_callback, e)
                    error.append((order_id, e))
                else:
                    success.append(order_id)
            return success, error

    async def get_open_order_ids(self):
        """Get open order id list.
        """
        success, error = await self._rest_api.get_open_orders(self._raw_symbol)
        if error:
            SingleTask.run(self._error_callback, error)
            return None, error
        else:
            order_ids = []
            for order_info in success:
                order_id = str(order_info["orderId"])
                order_ids.append(order_id)
            return order_ids, None

    @async_method_locker("BinanceTrade.process.locker")
    async def process(self, msg):
        """Process message that received from Websocket connection.

        Args:
            msg: message received from Websocket connection.
        """
        logger.debug("msg:", json.dumps(msg), caller=self)
        e = msg.get("e")
        if e == "executionReport":  # Order update.
            if msg["s"] != self._raw_symbol:
                return
            order_id = str(msg["i"])
            if msg["X"] == "NEW":
                status = ORDER_STATUS_SUBMITTED
            elif msg["X"] == "PARTIALLY_FILLED":
                status = ORDER_STATUS_PARTIAL_FILLED
            elif msg["X"] == "FILLED":
                status = ORDER_STATUS_FILLED
            elif msg["X"] == "CANCELED":
                status = ORDER_STATUS_CANCELED
            elif msg["X"] == "REJECTED":
                status = ORDER_STATUS_FAILED
            elif msg["X"] == "EXPIRED":
                status = ORDER_STATUS_FAILED
            else:
                logger.warn("unknown status:", msg, caller=self)
                SingleTask.run(self._error_callback, "order status error.")
                return
            order = self._orders.get(order_id)
            if not order:
                info = {
                    "platform": self._platform,
                    "account": self._account,
                    "strategy": self._strategy,
                    "order_id": order_id,
                    "client_order_id": msg["c"],
                    "action": ORDER_ACTION_BUY if msg["S"] == "BUY" else ORDER_ACTION_SELL,
                    "order_type": ORDER_TYPE_LIMIT if msg["o"] == "LIMIT" else ORDER_TYPE_MARKET,
                    "symbol": self._symbol,
                    "price": msg["p"],
                    "quantity": msg["q"],
                    "ctime": msg["O"]
                }
                order = Order(**info)
                self._orders[order_id] = order
            order.remain = float(msg["q"]) - float(msg["z"])
            order.status = status
            order.utime = msg["T"]
            SingleTask.run(self._order_update_callback, copy.copy(order))

            if status in [ORDER_STATUS_FAILED, ORDER_STATUS_CANCELED, ORDER_STATUS_FILLED]:
                self._orders.pop(order_id)
