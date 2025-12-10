"""
設定管理モジュール
YAMLファイルと環境変数から設定を読み込む
"""

import os
import yaml
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, Any


class Config:
    """設定クラス"""
    
    def __init__(self, config_path: str = None):
        """
        初期化
        
        Args:
            config_path: 設定ファイルのパス（デフォルト: config/config.yaml）
        """
        # プロジェクトルートディレクトリを取得
        self.project_root = Path(__file__).parent.parent
        
        # 環境変数を読み込み
        env_path = self.project_root / "config" / ".env"
        load_dotenv(env_path)
        
        # 設定ファイルを読み込み
        if config_path is None:
            config_path = self.project_root / "config" / "config.yaml"
        
        with open(config_path, 'r', encoding='utf-8') as f:
            self._config = yaml.safe_load(f)
        
        # API認証情報を環境変数から取得
        self.api_key = os.getenv('BYBIT_API_KEY')
        self.api_secret = os.getenv('BYBIT_API_SECRET')
        
        if not self.api_key or not self.api_secret:
            raise ValueError(
                "API credentials not found. "
                "Please set BYBIT_API_KEY and BYBIT_API_SECRET in .env file"
            )
        
        # 設定を属性として展開
        self._load_config()
    
    def _load_config(self):
        """設定をクラス属性として読み込む"""
        
        # API設定
        api_config = self._config.get('api', {})
        self.testnet = api_config.get('testnet', True)
        
        # 取引設定
        trading_config = self._config.get('trading', {})
        self.symbol = trading_config.get('symbol', 'BTCUSDT')
        self.leverage = trading_config.get('leverage', 2)
        self.position_mode = trading_config.get('position_mode', 'MergedSingle')
        
        # グリッド設定
        grid_config = self._config.get('grid', {})
        self.grid_count = grid_config.get('count', 20)
        self.grid_range_percent = grid_config.get('range_percent', 0.05)
        self.min_range_percent = grid_config.get('min_range_percent', 0.02)
        self.max_range_percent = grid_config.get('max_range_percent', 0.08)
        self.use_dynamic_range = grid_config.get('use_dynamic_range', True)
        self.atr_multiplier = grid_config.get('atr_multiplier', 2.0)
        self.atr_period = grid_config.get('atr_period', 14)
        
        # 注文設定
        order_config = self._config.get('order', {})
        self.min_profit_percent = order_config.get('min_profit_percent', 0.003)
        self.order_offset_percent = order_config.get('order_offset_percent', 0.0001)
        self.retry_count = order_config.get('retry_count', 3)
        self.retry_delay = order_config.get('retry_delay', 5)
        
        # リスク管理設定
        risk_config = self._config.get('risk', {})
        self.max_position_ratio = risk_config.get('max_position_ratio', 0.6)
        self.daily_loss_limit = risk_config.get('daily_loss_limit', 0.05)
        self.stop_loss_percent = risk_config.get('stop_loss_percent', 0.10)
        self.max_drawdown = risk_config.get('max_drawdown', 0.15)
        self.daily_profit_target = risk_config.get('daily_profit_target', 0.02)
        
        # 手数料設定
        fees_config = self._config.get('fees', {})
        self.maker_fee = fees_config.get('maker', 0.0002)
        self.taker_fee = fees_config.get('taker', 0.0055)
        
        # ログ設定
        logging_config = self._config.get('logging', {})
        self.log_level = logging_config.get('level', 'INFO')
        self.log_console = logging_config.get('console', True)
        self.log_file = logging_config.get('file', True)
        self.log_dir = self.project_root / logging_config.get('log_dir', 'logs')
        self.trade_history = logging_config.get('trade_history', True)
        
        # 実行設定
        execution_config = self._config.get('execution', {})
        self.check_interval = execution_config.get('check_interval', 60)
        self.grid_update_interval = execution_config.get('grid_update_interval', 3600)
        self.position_check_interval = execution_config.get('position_check_interval', 30)
        
        # 通知設定
        notification_config = self._config.get('notification', {})
        self.notification_enabled = notification_config.get('enabled', False)
        self.notification_email = notification_config.get('email', '')
        self.notification_webhook = notification_config.get('webhook_url', '')
    
    def get_bybit_endpoint(self) -> str:
        """Bybit APIエンドポイントを取得"""
        if self.testnet:
            return "https://api-testnet.bybit.com"
        else:
            return "https://api.bybit.com"
    
    def validate(self) -> bool:
        """設定の妥当性をチェック"""
        errors = []
        
        # グリッド数のチェック
        if self.grid_count < 5 or self.grid_count > 100:
            errors.append("Grid count must be between 5 and 100")
        
        # レバレッジのチェック
        if self.leverage < 1 or self.leverage > 10:
            errors.append("Leverage must be between 1 and 10")
        
        # 価格範囲のチェック
        if self.grid_range_percent < 0.01 or self.grid_range_percent > 0.20:
            errors.append("Grid range percent must be between 0.01 and 0.20")
        
        # リスク設定のチェック
        if self.max_position_ratio < 0.1 or self.max_position_ratio > 1.0:
            errors.append("Max position ratio must be between 0.1 and 1.0")
        
        if self.daily_loss_limit < 0.01 or self.daily_loss_limit > 0.20:
            errors.append("Daily loss limit must be between 0.01 and 0.20")
        
        if errors:
            for error in errors:
                print(f"Configuration Error: {error}")
            return False
        
        return True
    
    def __str__(self) -> str:
        """設定の文字列表現"""
        return f"""
Bybit Grid Trading Bot Configuration
=====================================
API:
  Testnet: {self.testnet}
  
Trading:
  Symbol: {self.symbol}
  Leverage: {self.leverage}x
  
Grid:
  Count: {self.grid_count}
  Range: ±{self.grid_range_percent * 100}%
  Dynamic Range: {self.use_dynamic_range}
  
Risk Management:
  Max Position: {self.max_position_ratio * 100}%
  Daily Loss Limit: {self.daily_loss_limit * 100}%
  Stop Loss: {self.stop_loss_percent * 100}%
  
Fees:
  Maker: {self.maker_fee * 100}%
  Taker: {self.taker_fee * 100}%
"""


if __name__ == "__main__":
    # テスト
    config = Config()
    print(config)
    print(f"Configuration valid: {config.validate()}")
