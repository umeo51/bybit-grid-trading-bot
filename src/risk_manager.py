"""
リスク管理モジュール
損失限界チェック、ポジションサイズ制御、自動損切り
"""

from typing import Dict, Tuple, Optional
from datetime import datetime, timedelta


class RiskManager:
    """リスク管理クラス"""
    
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
        
        # 状態管理
        self.start_balance = 0.0
        self.start_date = None
        self.daily_start_balance = 0.0
        self.peak_balance = 0.0
        self.total_trades = 0
        self.winning_trades = 0
        self.total_pnl = 0.0
        self.trading_stopped = False
        self.stop_reason = None
    
    def initialize(self) -> bool:
        """
        リスク管理を初期化
        
        Returns:
            成功したかどうか
        """
        try:
            balance = self.client.get_balance()
            if not balance:
                self.logger.error("Failed to get balance for risk manager initialization")
                return False
            
            self.start_balance = balance['total']
            self.daily_start_balance = balance['total']
            self.peak_balance = balance['total']
            self.start_date = datetime.now()
            
            self.logger.info(f"Risk manager initialized with balance: {self.start_balance:.2f} USDT")
            return True
            
        except Exception as e:
            self.logger.error(f"Error initializing risk manager: {e}")
            return False
    
    def check_daily_loss(self, current_balance: float) -> Tuple[bool, Optional[str]]:
        """
        日次損失限界をチェック
        
        Args:
            current_balance: 現在残高
            
        Returns:
            (限界到達, 理由)
        """
        # 日付が変わったら日次残高をリセット
        if datetime.now().date() > self.start_date.date():
            self.daily_start_balance = current_balance
            self.start_date = datetime.now()
            self.logger.info(f"Daily balance reset: {current_balance:.2f} USDT")
        
        # 損失率を計算
        loss = self.daily_start_balance - current_balance
        loss_percent = loss / self.daily_start_balance if self.daily_start_balance > 0 else 0
        
        if loss_percent >= self.config.daily_loss_limit:
            reason = (
                f"Daily loss limit reached: {loss_percent * 100:.2f}% "
                f"(limit: {self.config.daily_loss_limit * 100:.2f}%)"
            )
            self.logger.log_risk_alert("DAILY_LOSS", reason)
            return True, reason
        
        return False, None
    
    def check_drawdown(self, current_balance: float) -> Tuple[bool, Optional[str]]:
        """
        最大ドローダウンをチェック
        
        Args:
            current_balance: 現在残高
            
        Returns:
            (限界到達, 理由)
        """
        # ピーク残高を更新
        if current_balance > self.peak_balance:
            self.peak_balance = current_balance
        
        # ドローダウンを計算
        drawdown = (self.peak_balance - current_balance) / self.peak_balance
        
        if drawdown >= self.config.max_drawdown:
            reason = (
                f"Max drawdown reached: {drawdown * 100:.2f}% "
                f"(limit: {self.config.max_drawdown * 100:.2f}%)"
            )
            self.logger.log_risk_alert("MAX_DRAWDOWN", reason)
            return True, reason
        
        return False, None
    
    def check_position_size(self, position_value: float, total_balance: float) -> Tuple[bool, Optional[str]]:
        """
        ポジションサイズをチェック
        
        Args:
            position_value: ポジション価値
            total_balance: 総残高
            
        Returns:
            (許容範囲内, 理由)
        """
        if total_balance <= 0:
            return False, "Total balance is zero or negative"
        
        position_ratio = position_value / total_balance
        
        if position_ratio > self.config.max_position_ratio:
            reason = (
                f"Position size exceeds limit: {position_ratio * 100:.2f}% "
                f"(limit: {self.config.max_position_ratio * 100:.2f}%)"
            )
            self.logger.log_risk_alert("POSITION_SIZE", reason)
            return False, reason
        
        return True, None
    
    def check_daily_profit_target(self, current_balance: float) -> bool:
        """
        日次利益目標に到達したかチェック
        
        Args:
            current_balance: 現在残高
            
        Returns:
            目標到達したかどうか
        """
        profit = current_balance - self.daily_start_balance
        profit_percent = profit / self.daily_start_balance if self.daily_start_balance > 0 else 0
        
        if profit_percent >= self.config.daily_profit_target:
            self.logger.info(
                f"Daily profit target reached: {profit_percent * 100:.2f}% "
                f"(target: {self.config.daily_profit_target * 100:.2f}%)"
            )
            return True
        
        return False
    
    def should_stop_trading(self, current_balance: float) -> Tuple[bool, Optional[str]]:
        """
        取引を停止すべきかどうかを判定
        
        Args:
            current_balance: 現在残高
            
        Returns:
            (停止すべき, 理由)
        """
        # 既に停止している場合
        if self.trading_stopped:
            return True, self.stop_reason
        
        # 日次損失チェック
        should_stop, reason = self.check_daily_loss(current_balance)
        if should_stop:
            self.trading_stopped = True
            self.stop_reason = reason
            return True, reason
        
        # ドローダウンチェック
        should_stop, reason = self.check_drawdown(current_balance)
        if should_stop:
            self.trading_stopped = True
            self.stop_reason = reason
            return True, reason
        
        # 残高が初期値の50%を下回った場合
        if current_balance < self.start_balance * 0.5:
            reason = f"Balance dropped below 50% of initial: {current_balance:.2f} USDT"
            self.logger.log_risk_alert("LOW_BALANCE", reason)
            self.trading_stopped = True
            self.stop_reason = reason
            return True, reason
        
        return False, None
    
    def calculate_stop_loss_price(self, 
                                  entry_price: float,
                                  side: str) -> float:
        """
        損切り価格を計算
        
        Args:
            entry_price: エントリー価格
            side: ポジション方向 ("Buy" or "Sell")
            
        Returns:
            損切り価格
        """
        if side == "Buy":
            # ロングポジションの損切り
            stop_loss = entry_price * (1 - self.config.stop_loss_percent)
        else:
            # ショートポジションの損切り
            stop_loss = entry_price * (1 + self.config.stop_loss_percent)
        
        return stop_loss
    
    def record_trade(self, pnl: float, is_win: bool):
        """
        取引を記録
        
        Args:
            pnl: 損益
            is_win: 勝ちトレードかどうか
        """
        self.total_trades += 1
        self.total_pnl += pnl
        
        if is_win:
            self.winning_trades += 1
    
    def get_win_rate(self) -> float:
        """
        勝率を取得
        
        Returns:
            勝率（%）
        """
        if self.total_trades == 0:
            return 0.0
        
        return (self.winning_trades / self.total_trades) * 100
    
    def get_daily_return(self, current_balance: float) -> float:
        """
        日次リターンを取得
        
        Args:
            current_balance: 現在残高
            
        Returns:
            日次リターン（%）
        """
        if self.daily_start_balance == 0:
            return 0.0
        
        return ((current_balance - self.daily_start_balance) / self.daily_start_balance) * 100
    
    def get_total_return(self, current_balance: float) -> float:
        """
        総リターンを取得
        
        Args:
            current_balance: 現在残高
            
        Returns:
            総リターン（%）
        """
        if self.start_balance == 0:
            return 0.0
        
        return ((current_balance - self.start_balance) / self.start_balance) * 100
    
    def get_risk_metrics(self, current_balance: float) -> Dict:
        """
        リスクメトリクスを取得
        
        Args:
            current_balance: 現在残高
            
        Returns:
            リスクメトリクス
        """
        drawdown = 0.0
        if self.peak_balance > 0:
            drawdown = ((self.peak_balance - current_balance) / self.peak_balance) * 100
        
        daily_loss = 0.0
        if self.daily_start_balance > 0:
            daily_loss = ((self.daily_start_balance - current_balance) / self.daily_start_balance) * 100
        
        return {
            'start_balance': self.start_balance,
            'current_balance': current_balance,
            'peak_balance': self.peak_balance,
            'daily_start_balance': self.daily_start_balance,
            'total_return': self.get_total_return(current_balance),
            'daily_return': self.get_daily_return(current_balance),
            'drawdown': drawdown,
            'daily_loss': daily_loss,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'win_rate': self.get_win_rate(),
            'total_pnl': self.total_pnl,
            'trading_stopped': self.trading_stopped,
            'stop_reason': self.stop_reason
        }
    
    def reset_daily_stats(self):
        """日次統計をリセット"""
        balance = self.client.get_balance()
        if balance:
            self.daily_start_balance = balance['total']
            self.start_date = datetime.now()
            self.logger.info("Daily stats reset")


if __name__ == "__main__":
    # テスト
    from config import Config
    from logger import BotLogger
    from bybit_client import BybitClient
    
    config = Config()
    logger = BotLogger(config)
    client = BybitClient(config, logger)
    risk_manager = RiskManager(config, logger, client)
    
    # 初期化
    if risk_manager.initialize():
        print("\n=== Risk Manager Initialized ===")
        
        # メトリクス取得
        balance = client.get_balance()
        metrics = risk_manager.get_risk_metrics(balance['total'])
        
        print(f"Start Balance: {metrics['start_balance']:.2f} USDT")
        print(f"Current Balance: {metrics['current_balance']:.2f} USDT")
        print(f"Total Return: {metrics['total_return']:.2f}%")
