"""
動的設定調整モジュール
資産額に応じてグリッド数や設定を自動調整
"""

import logging
from typing import Dict, Any


class DynamicConfigManager:
    """資産額に応じた動的設定管理"""
    
    # 資産額別の推奨設定
    BALANCE_TIERS = [
        {
            'min_balance': 300,
            'max_balance': 500,
            'grid_count': 6,
            'range_percent': 0.03,
            'max_position_ratio': 0.85,
            'leverage': 2,
            'description': '300-500 USDT: 保守的運用'
        },
        {
            'min_balance': 500,
            'max_balance': 800,
            'grid_count': 10,
            'range_percent': 0.035,
            'max_position_ratio': 0.75,
            'leverage': 2,
            'description': '500-800 USDT: バランス運用'
        },
        {
            'min_balance': 800,
            'max_balance': 1200,
            'grid_count': 15,
            'range_percent': 0.04,
            'max_position_ratio': 0.70,
            'leverage': 2,
            'description': '800-1200 USDT: 標準運用'
        },
        {
            'min_balance': 1200,
            'max_balance': 2000,
            'grid_count': 20,
            'range_percent': 0.045,
            'max_position_ratio': 0.65,
            'leverage': 2,
            'description': '1200-2000 USDT: 積極運用'
        },
        {
            'min_balance': 2000,
            'max_balance': 5000,
            'grid_count': 30,
            'range_percent': 0.05,
            'max_position_ratio': 0.60,
            'leverage': 2,
            'description': '2000-5000 USDT: 高頻度運用'
        },
        {
            'min_balance': 5000,
            'max_balance': float('inf'),
            'grid_count': 40,
            'range_percent': 0.05,
            'max_position_ratio': 0.55,
            'leverage': 2,
            'description': '5000+ USDT: 最大効率運用'
        }
    ]
    
    def __init__(self, logger: logging.Logger):
        """
        初期化
        
        Args:
            logger: ロガーオブジェクト
        """
        self.logger = logger
        self.current_tier = None
        self.current_balance = 0.0
    
    def get_optimal_settings(self, balance: float) -> Dict[str, Any]:
        """
        資産額に応じた最適設定を取得
        
        Args:
            balance: 現在の資産額（USDT）
            
        Returns:
            最適設定の辞書
        """
        self.current_balance = balance
        
        # 最小残高チェック
        if balance < 300:
            self.logger.error(f"Balance too low: {balance:.2f} USDT (minimum: 300 USDT)")
            return None
        
        # 該当するティアを検索
        for tier in self.BALANCE_TIERS:
            if tier['min_balance'] <= balance < tier['max_balance']:
                self.current_tier = tier
                break
        
        if not self.current_tier:
            # デフォルト設定（最後のティア）
            self.current_tier = self.BALANCE_TIERS[-1]
        
        self.logger.info(f"Balance tier: {self.current_tier['description']}")
        self.logger.info(f"Optimal grid count: {self.current_tier['grid_count']}")
        self.logger.info(f"Price range: ±{self.current_tier['range_percent']*100:.1f}%")
        self.logger.info(f"Max position ratio: {self.current_tier['max_position_ratio']*100:.0f}%")
        
        return {
            'grid_count': self.current_tier['grid_count'],
            'range_percent': self.current_tier['range_percent'],
            'max_position_ratio': self.current_tier['max_position_ratio'],
            'leverage': self.current_tier['leverage'],
            'tier_description': self.current_tier['description']
        }
    
    def calculate_order_size(self, balance: float, current_price: float, settings: Dict[str, Any]) -> float:
        """
        1グリッドあたりの注文サイズを計算
        
        Args:
            balance: 現在の資産額（USDT）
            current_price: 現在のBTC価格（USDT）
            settings: 設定辞書
            
        Returns:
            1グリッドあたりの注文サイズ（BTC）
        """
        grid_count = settings['grid_count']
        max_position_ratio = settings['max_position_ratio']
        leverage = settings['leverage']
        
        # 1グリッドあたりのUSDT額
        usdt_per_grid = (balance * leverage * max_position_ratio) / grid_count
        
        # BTC換算
        btc_per_grid = usdt_per_grid / current_price
        
        self.logger.debug(f"Order size calculation:")
        self.logger.debug(f"  Balance: {balance:.2f} USDT")
        self.logger.debug(f"  Leverage: {leverage}x")
        self.logger.debug(f"  Max position ratio: {max_position_ratio*100:.0f}%")
        self.logger.debug(f"  Grid count: {grid_count}")
        self.logger.debug(f"  USDT per grid: {usdt_per_grid:.2f}")
        self.logger.debug(f"  BTC per grid: {btc_per_grid:.6f}")
        
        # Bybitの最小注文サイズチェック（0.001 BTC）
        min_order_size = 0.001
        if btc_per_grid < min_order_size:
            self.logger.warning(f"Calculated order size ({btc_per_grid:.6f} BTC) is below minimum ({min_order_size} BTC)")
            self.logger.warning(f"Consider increasing balance or reducing grid count")
        
        return btc_per_grid
    
    def should_rebalance(self, new_balance: float) -> bool:
        """
        設定を再調整すべきかチェック
        
        Args:
            new_balance: 新しい資産額（USDT）
            
        Returns:
            再調整が必要な場合True
        """
        if not self.current_tier:
            return True
        
        # 現在のティアの範囲外になった場合
        if new_balance < self.current_tier['min_balance'] or new_balance >= self.current_tier['max_balance']:
            self.logger.info(f"Balance changed significantly: {self.current_balance:.2f} → {new_balance:.2f} USDT")
            self.logger.info("Rebalancing required")
            return True
        
        return False
    
    def get_tier_info(self) -> str:
        """
        現在のティア情報を取得
        
        Returns:
            ティア情報の文字列
        """
        if not self.current_tier:
            return "No tier selected"
        
        return (
            f"\n{'='*60}\n"
            f"Current Tier: {self.current_tier['description']}\n"
            f"Balance Range: {self.current_tier['min_balance']}-{self.current_tier['max_balance']} USDT\n"
            f"Grid Count: {self.current_tier['grid_count']}\n"
            f"Price Range: ±{self.current_tier['range_percent']*100:.1f}%\n"
            f"Max Position: {self.current_tier['max_position_ratio']*100:.0f}%\n"
            f"Leverage: {self.current_tier['leverage']}x\n"
            f"{'='*60}"
        )
