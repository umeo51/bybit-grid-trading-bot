"""
市場データ分析モジュール
ATR計算、ボラティリティ分析、レンジ相場判定など
"""

import numpy as np
from typing import List, Dict, Tuple, Optional


class MarketAnalyzer:
    """市場データアナライザー"""
    
    def __init__(self, config, logger, bybit_client):
        """
        初期化
        
        Args:
            config: 設定オブジェクト
            logger: ロガーオブジェクト
            bybit_client: Bybitクライアント
        """
        self.config = config
        self.logger = logger
        self.client = bybit_client
    
    def get_current_price(self) -> Optional[float]:
        """
        現在価格を取得
        
        Returns:
            現在価格
        """
        ticker = self.client.get_ticker()
        if ticker:
            return ticker['last_price']
        return None
    
    def calculate_atr(self, period: int = None) -> Optional[float]:
        """
        ATR (Average True Range) を計算
        
        Args:
            period: 計算期間（デフォルトは設定値）
            
        Returns:
            ATR値
        """
        if period is None:
            period = self.config.atr_period
        
        # ローソク足データを取得（期間+1本）
        klines = self.client.get_klines(interval="60", limit=period + 1)
        
        if not klines or len(klines) < period + 1:
            self.logger.error("Insufficient kline data for ATR calculation")
            return None
        
        try:
            true_ranges = []
            
            for i in range(1, len(klines)):
                high = klines[i]['high']
                low = klines[i]['low']
                prev_close = klines[i-1]['close']
                
                # True Range = max(high-low, |high-prev_close|, |low-prev_close|)
                tr = max(
                    high - low,
                    abs(high - prev_close),
                    abs(low - prev_close)
                )
                true_ranges.append(tr)
            
            # ATR = 移動平均
            atr = np.mean(true_ranges[-period:])
            
            self.logger.debug(f"ATR({period}): {atr:.2f}")
            return atr
            
        except Exception as e:
            self.logger.error(f"Error calculating ATR: {e}")
            return None
    
    def calculate_volatility(self, period: int = 24) -> Optional[float]:
        """
        ボラティリティを計算（標準偏差）
        
        Args:
            period: 計算期間
            
        Returns:
            ボラティリティ（%）
        """
        klines = self.client.get_klines(interval="60", limit=period)
        
        if not klines or len(klines) < period:
            self.logger.error("Insufficient kline data for volatility calculation")
            return None
        
        try:
            # 終値の変化率を計算
            returns = []
            for i in range(1, len(klines)):
                ret = (klines[i]['close'] - klines[i-1]['close']) / klines[i-1]['close']
                returns.append(ret)
            
            # 標準偏差を計算
            volatility = np.std(returns) * 100  # パーセント表示
            
            self.logger.debug(f"Volatility({period}h): {volatility:.2f}%")
            return volatility
            
        except Exception as e:
            self.logger.error(f"Error calculating volatility: {e}")
            return None
    
    def is_range_market(self, threshold: float = 0.7) -> bool:
        """
        レンジ相場かどうかを判定
        
        Args:
            threshold: 判定閾値（0-1）
            
        Returns:
            レンジ相場ならTrue
        """
        # 過去24時間のローソク足を取得
        klines = self.client.get_klines(interval="60", limit=24)
        
        if not klines or len(klines) < 24:
            self.logger.warning("Insufficient data for range market detection")
            return True  # デフォルトはレンジ相場として扱う
        
        try:
            # 高値と安値の範囲を計算
            highs = [k['high'] for k in klines]
            lows = [k['low'] for k in klines]
            
            max_high = max(highs)
            min_low = min(lows)
            price_range = max_high - min_low
            
            # 現在価格
            current_price = klines[-1]['close']
            
            # レンジの中心からの乖離率
            range_center = (max_high + min_low) / 2
            deviation = abs(current_price - range_center) / (price_range / 2)
            
            # レンジ相場の判定
            # deviation が小さいほどレンジ相場
            is_range = deviation < threshold
            
            self.logger.debug(
                f"Range market check: deviation={deviation:.2f}, "
                f"threshold={threshold}, is_range={is_range}"
            )
            
            return is_range
            
        except Exception as e:
            self.logger.error(f"Error in range market detection: {e}")
            return True
    
    def get_optimal_grid_range(self, current_price: float) -> Tuple[float, float]:
        """
        最適なグリッド範囲を計算
        
        Args:
            current_price: 現在価格
            
        Returns:
            (下限価格, 上限価格)
        """
        if self.config.use_dynamic_range:
            # ATRベースの動的範囲
            atr = self.calculate_atr()
            
            if atr:
                # ATR × 倍数を範囲とする
                range_value = atr * self.config.atr_multiplier
                range_percent = range_value / current_price
                
                # 最小・最大範囲でクリップ
                range_percent = max(
                    self.config.min_range_percent,
                    min(range_percent, self.config.max_range_percent)
                )
                
                self.logger.info(f"Dynamic range calculated: ±{range_percent * 100:.2f}%")
            else:
                # ATR取得失敗時はデフォルト値
                range_percent = self.config.grid_range_percent
                self.logger.warning("Using default range due to ATR calculation failure")
        else:
            # 固定範囲
            range_percent = self.config.grid_range_percent
        
        lower_price = current_price * (1 - range_percent)
        upper_price = current_price * (1 + range_percent)
        
        return (lower_price, upper_price)
    
    def get_market_summary(self) -> Dict:
        """
        市場サマリーを取得
        
        Returns:
            市場サマリー情報
        """
        ticker = self.client.get_ticker()
        
        if not ticker:
            return None
        
        current_price = ticker['last_price']
        atr = self.calculate_atr()
        volatility = self.calculate_volatility()
        is_range = self.is_range_market()
        grid_range = self.get_optimal_grid_range(current_price)
        
        summary = {
            'current_price': current_price,
            'bid': ticker['bid'],
            'ask': ticker['ask'],
            'volume_24h': ticker['volume_24h'],
            'price_change_24h': ticker['price_change_24h'],
            'atr': atr,
            'volatility': volatility,
            'is_range_market': is_range,
            'grid_range': grid_range,
            'range_percent': ((grid_range[1] - grid_range[0]) / (2 * current_price)) * 100
        }
        
        return summary


if __name__ == "__main__":
    # テスト
    from config import Config
    from logger import BotLogger
    from bybit_client import BybitClient
    
    config = Config()
    logger = BotLogger(config)
    client = BybitClient(config, logger)
    analyzer = MarketAnalyzer(config, logger, client)
    
    # 市場サマリー取得
    summary = analyzer.get_market_summary()
    
    if summary:
        print("\n=== Market Summary ===")
        print(f"Current Price: {summary['current_price']:.2f}")
        print(f"24h Change: {summary['price_change_24h']:.2f}%")
        print(f"ATR: {summary['atr']:.2f}")
        print(f"Volatility: {summary['volatility']:.2f}%")
        print(f"Is Range Market: {summary['is_range_market']}")
        print(f"Grid Range: {summary['grid_range'][0]:.2f} - {summary['grid_range'][1]:.2f}")
        print(f"Range: ±{summary['range_percent']:.2f}%")
