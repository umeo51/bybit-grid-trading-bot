"""
ポジション管理モジュール
注文追跡、約定処理、グリッドリバランス
"""

import time
from typing import Dict, List, Optional
from collections import defaultdict


class PositionManager:
    """ポジション管理クラス"""
    
    def __init__(self, config, logger, bybit_client, grid_strategy, risk_manager):
        """
        初期化
        
        Args:
            config: 設定オブジェクト
            logger: ロガーオブジェクト
            bybit_client: Bybitクライアント
            grid_strategy: グリッド戦略
            risk_manager: リスク管理
        """
        self.config = config
        self.logger = logger
        self.client = bybit_client
        self.strategy = grid_strategy
        self.risk_manager = risk_manager
        
        # 注文追跡
        self.active_orders = {}  # order_id -> order_info
        self.filled_orders = []
        self.order_pairs = defaultdict(list)  # 対になる注文を追跡
        
        # ポジション情報
        self.current_position = None
        self.position_entry_price = 0.0
        self.position_size = 0.0
    
    def track_orders(self) -> Dict[str, List]:
        """
        注文を追跡し、約定を確認
        
        Returns:
            約定した注文のリスト
        """
        filled_orders = {
            'buy_filled': [],
            'sell_filled': []
        }
        
        try:
            # 未約定注文を取得
            open_orders = self.client.get_open_orders()
            
            # アクティブな注文IDのセット
            open_order_ids = {order['order_id'] for order in open_orders}
            
            # 以前アクティブだった注文で、今は存在しない注文を確認
            for order_id, order_info in list(self.active_orders.items()):
                if order_id not in open_order_ids:
                    # 注文履歴から実際のステータスを確認
                    order_history = self.client.get_order_history(limit=100)
                    order_status = None
                    
                    for hist_order in order_history:
                        if hist_order['order_id'] == order_id:
                            order_status = hist_order['status']
                            break
                    
                    # Filledステータスの場合のみ約定処理
                    if order_status == 'Filled':
                        self.logger.info(f"Order filled: {order_info['side']} @ {order_info['price']:.2f}")
                        
                        # 約定処理
                        self.handle_filled_order(order_info)
                        
                        # リストに追加
                        if order_info['side'] == 'Buy':
                            filled_orders['buy_filled'].append(order_info)
                        else:
                            filled_orders['sell_filled'].append(order_info)
                    elif order_status == 'Cancelled':
                        self.logger.debug(f"Order cancelled: {order_info['side']} @ {order_info['price']:.2f}")
                    elif order_status == 'Rejected':
                        self.logger.warning(f"Order rejected: {order_info['side']} @ {order_info['price']:.2f}")
                    else:
                        self.logger.debug(f"Order removed (status: {order_status}): {order_info['side']} @ {order_info['price']:.2f}")
                    
                    # アクティブリストから削除
                    del self.active_orders[order_id]
            
            # 現在の未約定注文を更新
            for order in open_orders:
                if order['order_id'] not in self.active_orders:
                    self.active_orders[order['order_id']] = order
            
            return filled_orders
            
        except Exception as e:
            self.logger.error(f"Error tracking orders: {e}")
            return filled_orders
    
    def handle_filled_order(self, order: Dict):
        """
        約定した注文を処理
        
        Args:
            order: 約定した注文情報
        """
        try:
            side = order['side']
            price = order['price']
            qty = order['qty']
            
            # 手数料計算
            fee = price * qty * self.config.maker_fee
            
            # 対向注文を生成
            self.place_counter_order(order)
            
            # 損益計算（ペアが完成した場合）
            pnl = self.calculate_pnl(order)
            
            # 取引を記録
            self.client.logger.log_trade(
                symbol=self.config.symbol,
                side=side,
                price=price,
                qty=qty,
                order_id=order['order_id'],
                status='Filled',
                pnl=pnl,
                fee=fee,
                note='Grid trade'
            )
            
            # リスク管理に記録
            if pnl != 0:
                is_win = pnl > 0
                self.risk_manager.record_trade(pnl, is_win)
            
            # 約定履歴に追加
            self.filled_orders.append(order)
            
        except Exception as e:
            self.logger.error(f"Error handling filled order: {e}")
    
    def place_counter_order(self, filled_order: Dict):
        """
        約定した注文の対向注文を配置
        
        Args:
            filled_order: 約定した注文
        """
        try:
            side = filled_order['side']
            price = filled_order['price']
            qty = filled_order['qty']
            
            # グリッド間隔を取得
            grid_step = self.strategy.grid_step
            
            # 対向注文の価格を計算
            if side == 'Buy':
                # 買いが約定したら、上に売り注文
                counter_price = price + grid_step
                counter_side = 'Sell'
            else:
                # 売りが約定したら、下に買い注文
                counter_price = price - grid_step
                counter_side = 'Buy'
            
            # 価格がグリッド範囲内かチェック
            lower, upper = self.strategy.grid_range
            if counter_price < lower or counter_price > upper:
                self.logger.debug(f"Counter order price {counter_price:.2f} out of range")
                return
            
            # 対向注文を配置
            order = self.client.place_limit_order(
                side=counter_side,
                qty=qty,
                price=counter_price
            )
            
            if order:
                # アクティブ注文に追加
                self.active_orders[order['order_id']] = order
                
                # ペアを記録
                self.order_pairs[filled_order['order_id']].append(order['order_id'])
                
                self.logger.debug(f"Counter order placed: {counter_side} @ {counter_price:.2f}")
            
        except Exception as e:
            self.logger.error(f"Error placing counter order: {e}")
    
    def calculate_pnl(self, order: Dict) -> float:
        """
        損益を計算
        
        Args:
            order: 注文情報
            
        Returns:
            損益（USDT）
        """
        try:
            # ペアになる注文を探す
            order_id = order['order_id']
            
            # この注文がペアの一部かチェック
            for pair_id, counter_ids in self.order_pairs.items():
                if order_id in counter_ids:
                    # ペアが見つかった
                    # 元の注文を探す
                    original_order = None
                    for filled in self.filled_orders:
                        if filled['order_id'] == pair_id:
                            original_order = filled
                            break
                    
                    if original_order:
                        # 損益計算
                        if original_order['side'] == 'Buy':
                            # 買い→売りのペア
                            buy_price = original_order['price']
                            sell_price = order['price']
                            qty = order['qty']
                            
                            gross_pnl = (sell_price - buy_price) * qty
                            fees = (buy_price + sell_price) * qty * self.config.maker_fee
                            net_pnl = gross_pnl - fees
                            
                            return net_pnl
                        else:
                            # 売り→買いのペア
                            sell_price = original_order['price']
                            buy_price = order['price']
                            qty = order['qty']
                            
                            gross_pnl = (sell_price - buy_price) * qty
                            fees = (buy_price + sell_price) * qty * self.config.maker_fee
                            net_pnl = gross_pnl - fees
                            
                            return net_pnl
            
            return 0.0
            
        except Exception as e:
            self.logger.error(f"Error calculating PnL: {e}")
            return 0.0
    
    def update_position_info(self):
        """ポジション情報を更新"""
        try:
            position = self.client.get_position()
            
            if position:
                self.current_position = position
                self.position_size = position['size']
                self.position_entry_price = position['entry_price']
                
                self.logger.debug(
                    f"Position: {position['side']} {position['size']} @ {position['entry_price']:.2f}"
                )
            
        except Exception as e:
            self.logger.error(f"Error updating position info: {e}")
    
    def get_total_position_value(self, current_price: float) -> float:
        """
        総ポジション価値を取得
        
        Args:
            current_price: 現在価格
            
        Returns:
            ポジション価値（USDT）
        """
        if not self.current_position:
            return 0.0
        
        position_value = self.position_size * current_price
        return position_value
    
    def rebalance_grid(self, order_size: float) -> bool:
        """
        グリッドをリバランス
        
        Args:
            order_size: 注文サイズ
            
        Returns:
            成功したかどうか
        """
        try:
            self.logger.info("Rebalancing grid...")
            
            # 既存の注文をキャンセル
            self.client.cancel_all_orders()
            time.sleep(1)
            
            # アクティブ注文をクリア
            self.active_orders.clear()
            
            # グリッドを更新
            if not self.strategy.update_grid(order_size):
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error rebalancing grid: {e}")
            return False
    
    def get_statistics(self) -> Dict:
        """
        統計情報を取得
        
        Returns:
            統計情報
        """
        return {
            'active_orders': len(self.active_orders),
            'filled_orders': len(self.filled_orders),
            'position_size': self.position_size,
            'position_entry_price': self.position_entry_price
        }


if __name__ == "__main__":
    # テスト
    from config import Config
    from logger import BotLogger
    from bybit_client import BybitClient
    from market_analyzer import MarketAnalyzer
    from grid_strategy import GridStrategy
    from risk_manager import RiskManager
    
    config = Config()
    logger = BotLogger(config)
    client = BybitClient(config, logger)
    analyzer = MarketAnalyzer(config, logger, client)
    strategy = GridStrategy(config, logger, client, analyzer)
    risk_manager = RiskManager(config, logger, client)
    
    position_manager = PositionManager(config, logger, client, strategy, risk_manager)
    
    print("\n=== Position Manager Initialized ===")
    stats = position_manager.get_statistics()
    print(f"Active Orders: {stats['active_orders']}")
    print(f"Filled Orders: {stats['filled_orders']}")
