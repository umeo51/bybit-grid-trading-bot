"""
Bybit API クライアントモジュール（直接API呼び出し版）
本番環境対応
"""

import time
import hmac
import hashlib
import requests
from typing import Dict, List, Optional, Any
from decimal import Decimal, ROUND_DOWN


class BybitClient:
    """Bybit APIクライアント"""
    
    def __init__(self, config, logger):
        """初期化"""
        self.config = config
        self.logger = logger
        
        # API設定
        self.api_key = config.api_key
        self.api_secret = config.api_secret
        self.base_url = "https://api-testnet.bybit.com" if config.testnet else "https://api.bybit.com"
        self.recv_window = "5000"
        
        self.logger.info(f"Bybit client initialized (Testnet: {config.testnet}, URL: {self.base_url})")
        
        # レバレッジを設定
        self._set_leverage()
    
    def _generate_signature(self, params: str) -> str:
        """署名を生成"""
        return hmac.new(
            self.api_secret.encode('utf-8'),
            params.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    def _set_leverage(self):
        """レバレッジを設定"""
        try:
            import json
            timestamp = str(int(time.time() * 1000))
            params = {
                'category': 'linear',
                'symbol': self.config.symbol,
                'buyLeverage': str(self.config.leverage),
                'sellLeverage': str(self.config.leverage)
            }
            
            # POSTリクエストの場合はJSONボディを使用
            json_body = json.dumps(params)
            param_str = f"{timestamp}{self.api_key}{self.recv_window}{json_body}"
            signature = self._generate_signature(param_str)
            
            headers = {
                'X-BAPI-API-KEY': self.api_key,
                'X-BAPI-SIGN': signature,
                'X-BAPI-TIMESTAMP': timestamp,
                'X-BAPI-RECV-WINDOW': self.recv_window,
                'Content-Type': 'application/json'
            }
            
            url = f"{self.base_url}/v5/position/set-leverage"
            response = requests.post(url, json=params, headers=headers)
            result = response.json()
            
            if result['retCode'] == 0:
                self.logger.info(f"Leverage set to {self.config.leverage}x")
            else:
                self.logger.warning(f"Failed to set leverage: {result['retMsg']}")
                
        except Exception as e:
            self.logger.warning(f"Failed to set leverage: {e}")
    
    def get_balance(self) -> Dict[str, Any]:
        """残高を取得"""
        try:
            timestamp = str(int(time.time() * 1000))
            params = {'accountType': 'UNIFIED'}
            
            query_string = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
            param_str = f"{timestamp}{self.api_key}{self.recv_window}{query_string}"
            signature = self._generate_signature(param_str)
            
            headers = {
                'X-BAPI-API-KEY': self.api_key,
                'X-BAPI-SIGN': signature,
                'X-BAPI-TIMESTAMP': timestamp,
                'X-BAPI-RECV-WINDOW': self.recv_window,
                'Content-Type': 'application/json'
            }
            
            url = f"{self.base_url}/v5/account/wallet-balance"
            response = requests.get(url, params=params, headers=headers)
            result = response.json()
            
            if result['retCode'] == 0:
                coins = result['result']['list'][0]['coin']
                for coin in coins:
                    if coin['coin'] == 'USDT':
                        wallet_balance = float(coin['walletBalance']) if coin['walletBalance'] else 0.0
                        # availableToWithdrawが空の場合はwalletBalanceを使用
                        available_balance = float(coin['availableToWithdraw']) if coin['availableToWithdraw'] else wallet_balance
                        balance = {
                            'total': wallet_balance,
                            'available': available_balance,
                            'used': wallet_balance - available_balance
                        }
                        return balance
                return {'total': 0.0, 'available': 0.0, 'used': 0.0}
            else:
                self.logger.error(f"Failed to get balance: {result['retMsg']}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting balance: {e}")
            return None
    
    def get_ticker(self, symbol: str = None) -> Optional[Dict[str, Any]]:
        """ティッカー情報を取得"""
        if symbol is None:
            symbol = self.config.symbol
        
        try:
            timestamp = str(int(time.time() * 1000))
            params = {'category': 'linear', 'symbol': symbol}
            
            query_string = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
            param_str = f"{timestamp}{self.api_key}{self.recv_window}{query_string}"
            signature = self._generate_signature(param_str)
            
            headers = {
                'X-BAPI-API-KEY': self.api_key,
                'X-BAPI-SIGN': signature,
                'X-BAPI-TIMESTAMP': timestamp,
                'X-BAPI-RECV-WINDOW': self.recv_window,
                'Content-Type': 'application/json'
            }
            
            url = f"{self.base_url}/v5/market/tickers"
            response = requests.get(url, params=params, headers=headers)
            result = response.json()
            
            if result['retCode'] == 0:
                ticker_data = result['result']['list'][0]
                return {
                    'symbol': ticker_data['symbol'],
                    'last_price': float(ticker_data['lastPrice']),
                    'bid': float(ticker_data['bid1Price']),
                    'ask': float(ticker_data['ask1Price']),
                    'volume_24h': float(ticker_data['volume24h']),
                    'price_change_24h': float(ticker_data['price24hPcnt']) * 100
                }
            return None
                
        except Exception as e:
            self.logger.error(f"Error getting ticker: {e}")
            return None
    
    def get_klines(self, symbol: str = None, interval: str = "60", limit: int = 200) -> Optional[List[Dict]]:
        """ローソク足データを取得"""
        if symbol is None:
            symbol = self.config.symbol
        
        try:
            timestamp = str(int(time.time() * 1000))
            params = {'category': 'linear', 'symbol': symbol, 'interval': interval, 'limit': str(limit)}
            
            query_string = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
            param_str = f"{timestamp}{self.api_key}{self.recv_window}{query_string}"
            signature = self._generate_signature(param_str)
            
            headers = {
                'X-BAPI-API-KEY': self.api_key,
                'X-BAPI-SIGN': signature,
                'X-BAPI-TIMESTAMP': timestamp,
                'X-BAPI-RECV-WINDOW': self.recv_window,
                'Content-Type': 'application/json'
            }
            
            url = f"{self.base_url}/v5/market/kline"
            response = requests.get(url, params=params, headers=headers)
            result = response.json()
            
            if result['retCode'] == 0:
                klines = []
                for k in result['result']['list']:
                    klines.append({
                        'timestamp': int(k[0]),
                        'open': float(k[1]),
                        'high': float(k[2]),
                        'low': float(k[3]),
                        'close': float(k[4]),
                        'volume': float(k[5])
                    })
                klines.reverse()
                return klines
            return None
                
        except Exception as e:
            self.logger.error(f"Error getting klines: {e}")
            return None
    
    def place_limit_order(self, side: str, qty: float, price: float, symbol: str = None, order_link_id: str = None) -> Optional[Dict]:
        """指値注文を発注"""
        if symbol is None:
            symbol = self.config.symbol
        
        try:
            qty_str = self._format_quantity(qty)
            price_str = self._format_price(price)
            
            timestamp = str(int(time.time() * 1000))
            params = {
                'category': 'linear',
                'symbol': symbol,
                'side': side,
                'orderType': 'Limit',
                'qty': qty_str,
                'price': price_str,
                'timeInForce': 'PostOnly'
            }
            
            if order_link_id:
                params['orderLinkId'] = order_link_id
            
            # POSTリクエストの場合はJSONボディを使用
            import json
            json_body = json.dumps(params)
            param_str = f"{timestamp}{self.api_key}{self.recv_window}{json_body}"
            signature = self._generate_signature(param_str)
            
            headers = {
                'X-BAPI-API-KEY': self.api_key,
                'X-BAPI-SIGN': signature,
                'X-BAPI-TIMESTAMP': timestamp,
                'X-BAPI-RECV-WINDOW': self.recv_window,
                'Content-Type': 'application/json'
            }
            
            url = f"{self.base_url}/v5/order/create"
            response = requests.post(url, json=params, headers=headers)
            result = response.json()
            
            if result['retCode'] == 0:
                order_id = result['result']['orderId']
                self.logger.info(f"Order placed: {side} {qty_str} @ {price_str} (ID: {order_id})")
                return {
                    'order_id': order_id,
                    'order_link_id': result['result'].get('orderLinkId'),
                    'symbol': symbol,
                    'side': side,
                    'qty': float(qty_str),
                    'price': float(price_str)
                }
            else:
                self.logger.error(f"Failed to place order: {result['retMsg']}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error placing order: {e}")
            return None
    
    def cancel_order(self, order_id: str = None, order_link_id: str = None, symbol: str = None) -> bool:
        """注文をキャンセル"""
        if symbol is None:
            symbol = self.config.symbol
        
        try:
            timestamp = str(int(time.time() * 1000))
            params = {'category': 'linear', 'symbol': symbol}
            
            if order_id:
                params['orderId'] = order_id
            elif order_link_id:
                params['orderLinkId'] = order_link_id
            else:
                return False
            
            # POSTリクエストの場合はJSONボディを使用
            import json
            json_body = json.dumps(params)
            param_str = f"{timestamp}{self.api_key}{self.recv_window}{json_body}"
            signature = self._generate_signature(param_str)
            
            headers = {
                'X-BAPI-API-KEY': self.api_key,
                'X-BAPI-SIGN': signature,
                'X-BAPI-TIMESTAMP': timestamp,
                'X-BAPI-RECV-WINDOW': self.recv_window,
                'Content-Type': 'application/json'
            }
            
            url = f"{self.base_url}/v5/order/cancel"
            response = requests.post(url, json=params, headers=headers)
            result = response.json()
            
            if result['retCode'] == 0:
                self.logger.info(f"Order cancelled: {order_id or order_link_id}")
                return True
            return False
                
        except Exception as e:
            self.logger.error(f"Error cancelling order: {e}")
            return False
    
    def cancel_all_orders(self, symbol: str = None) -> bool:
        """全ての注文をキャンセル"""
        if symbol is None:
            symbol = self.config.symbol
        
        try:
            timestamp = str(int(time.time() * 1000))
            params = {'category': 'linear', 'symbol': symbol}
            
            # POSTリクエストの場合はJSONボディを使用
            import json
            json_body = json.dumps(params)
            param_str = f"{timestamp}{self.api_key}{self.recv_window}{json_body}"
            signature = self._generate_signature(param_str)
            
            headers = {
                'X-BAPI-API-KEY': self.api_key,
                'X-BAPI-SIGN': signature,
                'X-BAPI-TIMESTAMP': timestamp,
                'X-BAPI-RECV-WINDOW': self.recv_window,
                'Content-Type': 'application/json'
            }
            
            url = f"{self.base_url}/v5/order/cancel-all"
            response = requests.post(url, json=params, headers=headers)
            result = response.json()
            
            if result['retCode'] == 0:
                self.logger.info(f"All orders cancelled for {symbol}")
                return True
            return False
                
        except Exception as e:
            self.logger.error(f"Error cancelling all orders: {e}")
            return False
    
    def get_open_orders(self, symbol: str = None) -> List[Dict]:
        """未約定注文を取得"""
        if symbol is None:
            symbol = self.config.symbol
        
        try:
            timestamp = str(int(time.time() * 1000))
            params = {'category': 'linear', 'symbol': symbol}
            
            query_string = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
            param_str = f"{timestamp}{self.api_key}{self.recv_window}{query_string}"
            signature = self._generate_signature(param_str)
            
            headers = {
                'X-BAPI-API-KEY': self.api_key,
                'X-BAPI-SIGN': signature,
                'X-BAPI-TIMESTAMP': timestamp,
                'X-BAPI-RECV-WINDOW': self.recv_window,
                'Content-Type': 'application/json'
            }
            
            url = f"{self.base_url}/v5/order/realtime"
            response = requests.get(url, params=params, headers=headers)
            result = response.json()
            
            if result['retCode'] == 0:
                orders = []
                for order in result['result']['list']:
                    orders.append({
                        'order_id': order['orderId'],
                        'order_link_id': order.get('orderLinkId'),
                        'symbol': order['symbol'],
                        'side': order['side'],
                        'price': float(order['price']),
                        'qty': float(order['qty']),
                        'filled_qty': float(order.get('cumExecQty', 0)),
                        'status': order['orderStatus'],
                        'created_time': order['createdTime']
                    })
                return orders
            return []
                
        except Exception as e:
            self.logger.error(f"Error getting open orders: {e}")
            return []
    
    def get_order_history(self, symbol: str = None, limit: int = 50) -> List[Dict]:
        """注文履歴を取得（最近の約定/キャンセル済み注文）"""
        if symbol is None:
            symbol = self.config.symbol
        
        try:
            timestamp = str(int(time.time() * 1000))
            params = {'category': 'linear', 'symbol': symbol, 'limit': str(limit)}
            
            query_string = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
            param_str = f"{timestamp}{self.api_key}{self.recv_window}{query_string}"
            signature = self._generate_signature(param_str)
            
            headers = {
                'X-BAPI-API-KEY': self.api_key,
                'X-BAPI-SIGN': signature,
                'X-BAPI-TIMESTAMP': timestamp,
                'X-BAPI-RECV-WINDOW': self.recv_window,
                'Content-Type': 'application/json'
            }
            
            url = f"{self.base_url}/v5/order/history"
            response = requests.get(url, params=params, headers=headers)
            result = response.json()
            
            if result['retCode'] == 0:
                orders = []
                for order in result['result']['list']:
                    orders.append({
                        'order_id': order['orderId'],
                        'order_link_id': order.get('orderLinkId'),
                        'symbol': order['symbol'],
                        'side': order['side'],
                        'price': float(order['price']),
                        'qty': float(order['qty']),
                        'filled_qty': float(order.get('cumExecQty', 0)),
                        'status': order['orderStatus'],
                        'reject_reason': order.get('rejectReason', ''),
                        'created_time': order['createdTime'],
                        'updated_time': order['updatedTime']
                    })
                return orders
            return []
                
        except Exception as e:
            self.logger.error(f"Error getting order history: {e}")
            return []
    
    def get_position(self, symbol: str = None) -> Optional[Dict]:
        """ポジション情報を取得"""
        if symbol is None:
            symbol = self.config.symbol
        
        try:
            timestamp = str(int(time.time() * 1000))
            params = {'category': 'linear', 'symbol': symbol}
            
            query_string = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
            param_str = f"{timestamp}{self.api_key}{self.recv_window}{query_string}"
            signature = self._generate_signature(param_str)
            
            headers = {
                'X-BAPI-API-KEY': self.api_key,
                'X-BAPI-SIGN': signature,
                'X-BAPI-TIMESTAMP': timestamp,
                'X-BAPI-RECV-WINDOW': self.recv_window,
                'Content-Type': 'application/json'
            }
            
            url = f"{self.base_url}/v5/position/list"
            response = requests.get(url, params=params, headers=headers)
            result = response.json()
            
            if result['retCode'] == 0 and result['result']['list']:
                pos = result['result']['list'][0]
                return {
                    'symbol': pos['symbol'],
                    'side': pos['side'],
                    'size': float(pos['size']) if pos['size'] else 0.0,
                    'entry_price': float(pos['avgPrice']) if pos['avgPrice'] else 0.0,
                    'unrealized_pnl': float(pos['unrealisedPnl']) if pos['unrealisedPnl'] else 0.0,
                    'leverage': float(pos['leverage']) if pos['leverage'] else self.config.leverage
                }
            return {
                'symbol': symbol,
                'side': 'None',
                'size': 0.0,
                'entry_price': 0.0,
                'unrealized_pnl': 0.0,
                'leverage': self.config.leverage
            }
                
        except Exception as e:
            self.logger.error(f"Error getting position: {e}")
            return None
    
    def _format_quantity(self, qty: float) -> str:
        """数量を適切な精度にフォーマット"""
        decimal_qty = Decimal(str(qty))
        formatted = decimal_qty.quantize(Decimal('0.001'), rounding=ROUND_DOWN)
        return str(formatted)
    
    def _format_price(self, price: float) -> str:
        """価格を適切な精度にフォーマット"""
        decimal_price = Decimal(str(price))
        formatted = decimal_price.quantize(Decimal('0.1'), rounding=ROUND_DOWN)
        return str(formatted)
