"""
ログ管理モジュール
取引ログ、エラーログ、パフォーマンスログを記録
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional
import colorlog


class BotLogger:
    """ボット用ロガークラス"""
    
    def __init__(self, config, name: str = "GridBot"):
        """
        初期化
        
        Args:
            config: 設定オブジェクト
            name: ロガー名
        """
        self.config = config
        self.name = name
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, config.log_level))
        
        # ログディレクトリを作成
        self.log_dir = Path(config.log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # ハンドラーを設定
        self._setup_handlers()
        
        # 取引履歴ファイル
        if config.trade_history:
            self.trade_file = self._get_trade_file()
            self._init_trade_file()
    
    def _setup_handlers(self):
        """ログハンドラーを設定"""
        
        # フォーマッター
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        date_format = '%Y-%m-%d %H:%M:%S'
        
        # コンソールハンドラー（カラー付き）
        if self.config.log_console:
            console_handler = colorlog.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.DEBUG)
            
            color_formatter = colorlog.ColoredFormatter(
                '%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt=date_format,
                log_colors={
                    'DEBUG': 'cyan',
                    'INFO': 'green',
                    'WARNING': 'yellow',
                    'ERROR': 'red',
                    'CRITICAL': 'red,bg_white',
                }
            )
            console_handler.setFormatter(color_formatter)
            self.logger.addHandler(console_handler)
        
        # ファイルハンドラー
        if self.config.log_file:
            log_file = self._get_log_file()
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            
            file_formatter = logging.Formatter(log_format, datefmt=date_format)
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)
    
    def _get_log_file(self) -> Path:
        """ログファイルパスを取得"""
        today = datetime.now().strftime('%Y-%m-%d')
        return self.log_dir / f"bot_{today}.log"
    
    def _get_trade_file(self) -> Path:
        """取引履歴ファイルパスを取得"""
        today = datetime.now().strftime('%Y-%m-%d')
        return self.log_dir / f"trades_{today}.csv"
    
    def _init_trade_file(self):
        """取引履歴ファイルを初期化"""
        if not self.trade_file.exists():
            header = "timestamp,symbol,side,price,qty,order_id,status,pnl,fee,note\n"
            with open(self.trade_file, 'w', encoding='utf-8') as f:
                f.write(header)
    
    def debug(self, message: str):
        """DEBUGレベルのログ"""
        self.logger.debug(message)
    
    def info(self, message: str):
        """INFOレベルのログ"""
        self.logger.info(message)
    
    def warning(self, message: str):
        """WARNINGレベルのログ"""
        self.logger.warning(message)
    
    def error(self, message: str):
        """ERRORレベルのログ"""
        self.logger.error(message)
    
    def critical(self, message: str):
        """CRITICALレベルのログ"""
        self.logger.critical(message)
    
    def log_trade(self, 
                  symbol: str,
                  side: str,
                  price: float,
                  qty: float,
                  order_id: str,
                  status: str,
                  pnl: float = 0.0,
                  fee: float = 0.0,
                  note: str = ""):
        """
        取引をログに記録
        
        Args:
            symbol: 取引ペア
            side: 売買方向 (Buy/Sell)
            price: 価格
            qty: 数量
            order_id: 注文ID
            status: ステータス
            pnl: 損益
            fee: 手数料
            note: 備考
        """
        if not self.config.trade_history:
            return
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        line = f"{timestamp},{symbol},{side},{price},{qty},{order_id},{status},{pnl},{fee},{note}\n"
        
        with open(self.trade_file, 'a', encoding='utf-8') as f:
            f.write(line)
        
        self.info(f"Trade: {side} {qty} {symbol} @ {price} | PnL: {pnl:.4f} | Fee: {fee:.4f}")
    
    def log_performance(self,
                       total_balance: float,
                       unrealized_pnl: float,
                       realized_pnl: float,
                       total_trades: int,
                       win_rate: float,
                       daily_return: float):
        """
        パフォーマンスをログに記録
        
        Args:
            total_balance: 総残高
            unrealized_pnl: 未実現損益
            realized_pnl: 実現損益
            total_trades: 総取引数
            win_rate: 勝率
            daily_return: 日次リターン
        """
        self.info("=" * 60)
        self.info("Performance Summary")
        self.info(f"Total Balance: {total_balance:.2f} USDT")
        self.info(f"Unrealized PnL: {unrealized_pnl:.4f} USDT")
        self.info(f"Realized PnL: {realized_pnl:.4f} USDT")
        self.info(f"Total Trades: {total_trades}")
        self.info(f"Win Rate: {win_rate:.2f}%")
        self.info(f"Daily Return: {daily_return:.2f}%")
        self.info("=" * 60)
    
    def log_grid_info(self,
                     current_price: float,
                     grid_range: tuple,
                     grid_count: int,
                     grid_step: float):
        """
        グリッド情報をログに記録
        
        Args:
            current_price: 現在価格
            grid_range: グリッド範囲 (lower, upper)
            grid_count: グリッド数
            grid_step: グリッド間隔
        """
        lower, upper = grid_range
        self.info("=" * 60)
        self.info("Grid Configuration")
        self.info(f"Current Price: {current_price:.2f}")
        self.info(f"Grid Range: {lower:.2f} - {upper:.2f}")
        self.info(f"Grid Count: {grid_count}")
        self.info(f"Grid Step: {grid_step:.2f}")
        self.info(f"Range: ±{((upper - lower) / (2 * current_price)) * 100:.2f}%")
        self.info("=" * 60)
    
    def log_risk_alert(self, alert_type: str, message: str):
        """
        リスクアラートをログに記録
        
        Args:
            alert_type: アラートタイプ
            message: メッセージ
        """
        self.warning(f"RISK ALERT [{alert_type}]: {message}")
    
    def log_error_with_context(self, error: Exception, context: str):
        """
        コンテキスト付きでエラーをログに記録
        
        Args:
            error: 例外オブジェクト
            context: コンテキスト情報
        """
        self.error(f"Error in {context}: {type(error).__name__}: {str(error)}")


if __name__ == "__main__":
    # テスト
    from config import Config
    
    config = Config()
    logger = BotLogger(config)
    
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    
    logger.log_trade(
        symbol="BTCUSDT",
        side="Buy",
        price=95000.0,
        qty=0.01,
        order_id="test123",
        status="Filled",
        pnl=5.0,
        fee=0.19,
        note="Test trade"
    )
