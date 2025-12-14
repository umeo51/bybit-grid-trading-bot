"""
グリッド戦略モジュール（OrderLinkedID修正版）
"""

import time
import logging
from typing import List, Dict, Tuple, Optional
from datetime import datetime


class GridStrategy:
    """グリッド取引戦略"""
    
    def __init__(self, client, config, analyzer, logger: logging.Logger):
        """
        初期化
        
        Args:
            client: Bybitクライアント
            config: 設定オブジェクト
            analyzer: 市場分析オブジェクト
            logger: ロガーオブジェクト
        """
        self.client = client
        self.config = config
        self.analyzer = analyzer
        self.logger = logger
        
        self.buy_levels = []
        self.sell_levels = []
        self.current_price = 0.0
        self.grid_range = (0.0, 0.0)
        
        # セッションIDを生成（BOT起動時のタイムスタンプ）
        self.session_id = int(time.time())
        self.logger.info(f"Grid strategy initialized with session ID: {self.session_id}")
    
    def calculate_grid_levels(self, current_price: float, grid_range: Tuple[float, float], 
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
        
        # 買いレベル（現在価格より下）
        buy_levels = []
        for i in range(grid_count // 2):
            price = current_price - (i + 1) * grid_step
            if price >= lower_price:
                buy_levels.append(price)
        
        # 売りレベル（現在価格より上）
        sell_levels = []
        for i in range(grid_count // 2):
            price = current_price + (i + 1) * grid_step
            if price <= upper_price:
                sell_levels.append(price)
        
        return buy_levels, sell_levels
    
    def initialize_grid(self) -> bool:
        """
        グリッドを初期化
        
        Returns:
            成功した場合True
        """
        try:
            # 市場情報を取得
            summary = self.analyzer.get_market_summary()
            self.current_price = summary['current_price']
            self.grid_range = summary['grid_range']
            
            # グリッドレベルを計算
            self.buy_levels, self.sell_levels = self.calculate_grid_levels(
                self.current_price,
                self.grid_range,
                self.config.grid_count
            )
            
            # ログ出力
            self.logger.info("=" * 60)
            self.logger.info("Grid Configuration")
            self.logger.info(f"Current Price: {self.current_price:.2f}")
            self.logger.info(f"Grid Range: {self.grid_range[0]:.2f} - {self.grid_range[1]:.2f}")
            self.logger.info(f"Grid Count: {self.config.grid_count}")
            
            if len(self.buy_levels) > 0 and len(self.sell_levels) > 0:
                grid_step = abs(self.sell_levels[0] - self.current_price)
                self.logger.info(f"Grid Step: {grid_step:.2f}")
                range_percent = ((self.grid_range[1] - self.grid_range[0]) / 
                               (2 * self.current_price)) * 100
                self.logger.info(f"Range: ±{range_percent:.2f}%")
            
            self.logger.info("=" * 60)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize grid: {e}")
            return False
    
    def place_grid_orders(self, order_size: float) -> Dict:
        """
        グリッド注文を配置
        
        Args:
            order_size: 1注文あたりのサイズ（BTC）
            
        Returns:
            配置された注文の辞書
        """
        placed_orders = {
            'buy_orders': [],
            'sell_orders': []
        }
        
        # 既存の注文をキャンセル
        self.client.cancel_all_orders()
        time.sleep(1)
        
        # タイムスタンプを生成（ミリ秒単位）
        timestamp = int(time.time() * 1000)
        
        # 買い注文を配置
        for i, price in enumerate(self.buy_levels):
            try:
                # 価格をわずかにオフセット（メイカー注文を確実にする）
                adjusted_price = price * (1 - self.config.order_offset_percent)
                
                # 一意のorderLinkIdを生成（セッションID + タイムスタンプ + インデックス）
                order_link_id = f"grid_buy_{self.session_id}_{timestamp}_{i}"
                
                order = self.client.place_limit_order(
                    side="Buy",
                    qty=order_size,
                    price=adjusted_price,
                    order_link_id=order_link_id
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
                
                # 一意のorderLinkIdを生成
                order_link_id = f"grid_sell_{self.session_id}_{timestamp}_{i}"
                
                order = self.client.place_limit_order(
                    side="Sell",
                    qty=order_size,
                    price=adjusted_price,
                    order_link_id=order_link_id
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
    
    def update_grid(self, order_size: float) -> bool:
        """
        グリッドを更新
        
        Args:
            order_size: 1注文あたりのサイズ
            
        Returns:
            成功した場合True
        """
        try:
            # グリッドを再初期化
            if not self.initialize_grid():
                return False
            
            # 注文を再配置
            orders = self.place_grid_orders(order_size)
            
            return len(orders['buy_orders']) > 0 or len(orders['sell_orders']) > 0
            
        except Exception as e:
            self.logger.error(f"Failed to update grid: {e}")
            return False
