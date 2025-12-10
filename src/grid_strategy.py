"""
グリッド戦略モジュール
グリッドレベルの計算、注文生成、グリッド調整
"""

from typing import List, Dict, Tuple
import time


class GridStrategy:
    """グリッド戦略クラス"""
    
    def __init__(self, config, logger, bybit_client, market_analyzer):
        """
        初期化
        
        Args:
            config: 設定オブジェクト
            logger: ロガーオブジェクト
            bybit_client: Bybitクライアント
            market_analyzer: 市場アナライザー
        """
        self.config = config
        self.logger = logger
        self.client = bybit_client
        self.analyzer = market_analyzer
        
        # グリッド状態
        self.grid_levels = []
        self.buy_levels = []
        self.sell_levels = []
        self.grid_range = (0.0, 0.0)
        self.grid_step = 0.0
        self.last_update_time = 0
    
    def calculate_grid_levels(self, 
                             current_price: float,
                             grid_range: Tuple[float, float],
                             grid_count: int) -> Tuple[List[float], List[float]]:
        """
        グリッドレベルを計算
        
        Args:
            current_price: 現在価格
            grid_range: (下限価格, 上限価格)
            grid_count: グリッド数
            
        Returns:
            (買いレベルのリスト, 売りレベルのリスト)
        """
        lower_price, upper_price = grid_range
        
        # グリッド間隔を計算
        grid_step = (upper_price - lower_price) / grid_count
        
        buy_levels = []
        sell_levels = []
        
        # 現在価格を基準にグリッドを配置
        # 現在価格より下に買い注文、上に売り注文
        for i in range(grid_count // 2):
            # 買いレベル（現在価格より下）
            buy_price = current_price - (grid_step * (i + 1))
            if buy_price >= lower_price:
                buy_levels.append(buy_price)
            
            # 売りレベル（現在価格より上）
            sell_price = current_price + (grid_step * (i + 1))
            if sell_price <= upper_price:
                sell_levels.append(sell_price)
        
        # 価格順にソート
        buy_levels.sort(reverse=True)  # 高い順
        sell_levels.sort()  # 低い順
        
        self.logger.debug(f"Grid levels calculated: {len(buy_levels)} buy, {len(sell_levels)} sell")
        
        return buy_levels, sell_levels
    
    def calculate_order_size(self, 
                           total_capital: float,
                           current_price: float,
                           grid_count: int) -> float:
        """
        1グリッドあたりの注文サイズを計算
        
        Args:
            total_capital: 総資金
            current_price: 現在価格
            grid_count: グリッド数
            
        Returns:
            注文サイズ（USDT）
        """
        # 使用可能資金（総資金の60%）
        available_capital = total_capital * self.config.max_position_ratio
        
        # レバレッジを考慮
        leveraged_capital = available_capital * self.config.leverage
        
        # グリッド数で分割
        order_size_usdt = leveraged_capital / grid_count
        
        # BTC数量に変換
        order_size_btc = order_size_usdt / current_price
        
        self.logger.debug(
            f"Order size calculated: {order_size_btc:.4f} BTC "
            f"({order_size_usdt:.2f} USDT per grid)"
        )
        
        return order_size_btc
    
    def initialize_grid(self) -> bool:
        """
        グリッドを初期化
        
        Returns:
            成功したかどうか
        """
        try:
            # 市場情報を取得
            summary = self.analyzer.get_market_summary()
            if not summary:
                self.logger.error("Failed to get market summary")
                return False
            
            current_price = summary['current_price']
            grid_range = summary['grid_range']
            
            # グリッドレベルを計算
            buy_levels, sell_levels = self.calculate_grid_levels(
                current_price,
                grid_range,
                self.config.grid_count
            )
            
            # 状態を保存
            self.buy_levels = buy_levels
            self.sell_levels = sell_levels
            self.grid_range = grid_range
            self.grid_step = (grid_range[1] - grid_range[0]) / self.config.grid_count
            self.last_update_time = time.time()
            
            # ログ出力
            self.logger.log_grid_info(
                current_price=current_price,
                grid_range=grid_range,
                grid_count=self.config.grid_count,
                grid_step=self.grid_step
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error initializing grid: {e}")
            return False
    
    def place_grid_orders(self, order_size: float) -> Dict[str, List]:
        """
        グリッド注文を配置
        
        Args:
            order_size: 注文サイズ（BTC）
            
        Returns:
            配置された注文のリスト
        """
        placed_orders = {
            'buy_orders': [],
            'sell_orders': []
        }
        
        # 既存の注文をキャンセル
        self.client.cancel_all_orders()
        time.sleep(1)
        
        # 買い注文を配置
        for i, price in enumerate(self.buy_levels):
            try:
                # 価格をわずかにオフセット（メイカー注文を確実にする）
                adjusted_price = price * (1 - self.config.order_offset_percent)
                
                order = self.client.place_limit_order(
                    side="Buy",
                    qty=order_size,
                    price=adjusted_price,
                    order_link_id=f"grid_buy_{i}"
                )
                
                if order:
                    placed_orders['buy_orders'].append(order)
                
                time.sleep(0.2)  # API制限対策
                
            except Exception as e:
                self.logger.error(f"Error placing buy order at {price}: {e}")
        
        # 売り注文を配置
        for i, price in enumerate(self.sell_levels):
            try:
                # 価格をわずかにオフセット
                adjusted_price = price * (1 + self.config.order_offset_percent)
                
                order = self.client.place_limit_order(
                    side="Sell",
                    qty=order_size,
                    price=adjusted_price,
                    order_link_id=f"grid_sell_{i}"
                )
                
                if order:
                    placed_orders['sell_orders'].append(order)
                
                time.sleep(0.2)
                
            except Exception as e:
                self.logger.error(f"Error placing sell order at {price}: {e}")
        
        self.logger.info(
            f"Grid orders placed: {len(placed_orders['buy_orders'])} buy, "
            f"{len(placed_orders['sell_orders'])} sell"
        )
        
        return placed_orders
    
    def should_update_grid(self, current_price: float) -> bool:
        """
        グリッドを更新すべきかどうかを判定
        
        Args:
            current_price: 現在価格
            
        Returns:
            更新すべきならTrue
        """
        # 時間チェック（最低1時間は待つ）
        time_since_update = time.time() - self.last_update_time
        if time_since_update < self.config.grid_update_interval:
            return False
        
        # 価格がレンジ外に出たかチェック
        lower, upper = self.grid_range
        
        # レンジの10%外に出たら更新
        range_buffer = (upper - lower) * 0.1
        
        if current_price < (lower - range_buffer):
            self.logger.warning(f"Price {current_price} below grid range, updating grid")
            return True
        
        if current_price > (upper + range_buffer):
            self.logger.warning(f"Price {current_price} above grid range, updating grid")
            return True
        
        return False
    
    def update_grid(self, order_size: float) -> bool:
        """
        グリッドを更新
        
        Args:
            order_size: 注文サイズ
            
        Returns:
            成功したかどうか
        """
        try:
            self.logger.info("Updating grid...")
            
            # グリッドを再初期化
            if not self.initialize_grid():
                return False
            
            # 注文を再配置
            self.place_grid_orders(order_size)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating grid: {e}")
            return False
    
    def calculate_grid_profit(self, fill_price: float, side: str) -> float:
        """
        グリッド1回転あたりの利益を計算
        
        Args:
            fill_price: 約定価格
            side: 売買方向
            
        Returns:
            予想利益（USDT）
        """
        # グリッド間隔に基づく利益
        profit_percent = (self.grid_step / fill_price) - (self.config.maker_fee * 2)
        
        return profit_percent
    
    def get_grid_status(self) -> Dict:
        """
        グリッドの状態を取得
        
        Returns:
            グリッド状態情報
        """
        return {
            'grid_range': self.grid_range,
            'grid_step': self.grid_step,
            'buy_levels_count': len(self.buy_levels),
            'sell_levels_count': len(self.sell_levels),
            'last_update_time': self.last_update_time
        }


if __name__ == "__main__":
    # テスト
    from config import Config
    from logger import BotLogger
    from bybit_client import BybitClient
    from market_analyzer import MarketAnalyzer
    
    config = Config()
    logger = BotLogger(config)
    client = BybitClient(config, logger)
    analyzer = MarketAnalyzer(config, logger, client)
    strategy = GridStrategy(config, logger, client, analyzer)
    
    # グリッド初期化
    if strategy.initialize_grid():
        print("\n=== Grid Status ===")
        status = strategy.get_grid_status()
        print(f"Grid Range: {status['grid_range'][0]:.2f} - {status['grid_range'][1]:.2f}")
        print(f"Grid Step: {status['grid_step']:.2f}")
        print(f"Buy Levels: {status['buy_levels_count']}")
        print(f"Sell Levels: {status['sell_levels_count']}")
