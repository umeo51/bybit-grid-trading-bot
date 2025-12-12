"""
メインコントローラー
BOT全体の制御とスケジューリング
"""

import time
import signal
import sys
from pathlib import Path

# 親ディレクトリをパスに追加
sys.path.append(str(Path(__file__).parent))

from config import Config
from logger import BotLogger
from bybit_client import BybitClient
from market_analyzer import MarketAnalyzer
from grid_strategy import GridStrategy
from risk_manager import RiskManager
from position_manager import PositionManager


class GridTradingBot:
    """グリッドトレーディングBOT"""
    
    def __init__(self, config_path: str = None):
        """
        初期化
        
        Args:
            config_path: 設定ファイルのパス
        """
        # 設定読み込み
        self.config = Config(config_path)
        
        # ロガー初期化
        self.logger = BotLogger(self.config)
        
        # 各モジュール初期化
        self.client = BybitClient(self.config, self.logger)
        self.analyzer = MarketAnalyzer(self.config, self.logger, self.client)
        self.strategy = GridStrategy(self.config, self.logger, self.client, self.analyzer)
        self.risk_manager = RiskManager(self.config, self.logger, self.client)
        self.position_manager = PositionManager(
            self.config, self.logger, self.client, self.strategy, self.risk_manager
        )
        
        # 状態管理
        self.running = False
        self.order_size = 0.0
        self.last_position_check = 0
        
        # シグナルハンドラー設定
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        """シグナルハンドラー（Ctrl+C対応）"""
        self.logger.warning("Shutdown signal received, stopping bot...")
        self.running = False
    
    def initialize(self) -> bool:
        """
        BOTを初期化
        
        Returns:
            成功したかどうか
        """
        try:
            self.logger.info("=" * 60)
            self.logger.info("Bybit Grid Trading Bot - Initializing")
            self.logger.info("=" * 60)
            
            # 設定の検証
            if not self.config.validate():
                self.logger.error("Configuration validation failed")
                return False
            
            self.logger.info(str(self.config))
            
            # 既存の未約定注文をキャンセル
            self.logger.info("既存の未約定注文をキャンセル中...")
            if self.client.cancel_all_orders():
                self.logger.info("既存の注文をキャンセルしました")
                # キャンセル後、残高が更新されるまで少し待機
                import time
                time.sleep(2)
            else:
                self.logger.warning("注文のキャンセルに失敗しました（注文がない可能性があります）")
            
            # 残高確認
            balance = self.client.get_balance()
            if not balance:
                self.logger.error("Failed to get balance")
                return False
            
            self.logger.info(f"Available balance: {balance['available']:.2f} USDT")
            
            # 最小残高チェック
            if balance['available'] < 10:
                self.logger.error("Insufficient balance (minimum 10 USDT required)")
                return False
            
            # リスク管理初期化
            if not self.risk_manager.initialize():
                self.logger.error("Failed to initialize risk manager")
                return False
            
            # グリッド初期化
            if not self.strategy.initialize_grid():
                self.logger.error("Failed to initialize grid")
                return False
            
            # 注文サイズ計算
            current_price = self.analyzer.get_current_price()
            if not current_price:
                self.logger.error("Failed to get current price")
                return False
            
            self.order_size = self.strategy.calculate_order_size(
                balance['available'],
                current_price,
                self.config.grid_count
            )
            
            self.logger.info(f"Order size: {self.order_size:.4f} BTC per grid")
            
            # グリッド注文を配置
            placed_orders = self.strategy.place_grid_orders(self.order_size)
            
            if not placed_orders['buy_orders'] and not placed_orders['sell_orders']:
                self.logger.error("Failed to place grid orders")
                return False
            
            # アクティブ注文として記録
            for order in placed_orders['buy_orders'] + placed_orders['sell_orders']:
                self.position_manager.active_orders[order['order_id']] = order
            
            self.logger.info("=" * 60)
            self.logger.info("Bot initialized successfully")
            self.logger.info("=" * 60)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error during initialization: {e}")
            return False
    
    def main_loop(self):
        """メインループ"""
        self.running = True
        loop_count = 0
        
        while self.running:
            try:
                loop_count += 1
                self.logger.debug(f"Main loop iteration: {loop_count}")
                
                # 1. 残高取得
                balance = self.client.get_balance()
                if not balance:
                    self.logger.error("Failed to get balance")
                    time.sleep(60)
                    continue
                
                current_balance = balance['total']
                
                # 2. リスクチェック
                should_stop, reason = self.risk_manager.should_stop_trading(current_balance)
                if should_stop:
                    self.logger.critical(f"Trading stopped: {reason}")
                    self.emergency_shutdown()
                    break
                
                # 3. 現在価格取得
                current_price = self.analyzer.get_current_price()
                if not current_price:
                    self.logger.error("Failed to get current price")
                    time.sleep(60)
                    continue
                
                # 4. グリッド更新チェック
                if self.strategy.should_update_grid(current_price):
                    self.logger.info("Grid update required")
                    self.position_manager.rebalance_grid(self.order_size)
                
                # 5. 注文追跡と約定処理
                filled_orders = self.position_manager.track_orders()
                
                if filled_orders['buy_filled'] or filled_orders['sell_filled']:
                    self.logger.info(
                        f"Orders filled: {len(filled_orders['buy_filled'])} buy, "
                        f"{len(filled_orders['sell_filled'])} sell"
                    )
                
                # 6. ポジション情報更新（定期的に）
                if time.time() - self.last_position_check > self.config.position_check_interval:
                    self.position_manager.update_position_info()
                    self.last_position_check = time.time()
                
                # 7. パフォーマンスログ（10分ごと）
                if loop_count % 10 == 0:
                    self.log_performance(current_balance)
                
                # 8. 日次利益目標チェック
                if self.risk_manager.check_daily_profit_target(current_balance):
                    self.logger.info("Daily profit target reached, reducing risk...")
                    # 新規注文を停止（既存注文は継続）
                    # 実装は省略（オプション機能）
                
                # 9. 待機
                time.sleep(self.config.check_interval)
                
            except KeyboardInterrupt:
                self.logger.warning("Keyboard interrupt received")
                break
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}")
                time.sleep(300)  # エラー時は5分待機
        
        self.logger.info("Main loop ended")
    
    def log_performance(self, current_balance: float):
        """
        パフォーマンスをログ出力
        
        Args:
            current_balance: 現在残高
        """
        try:
            # ポジション情報
            position = self.client.get_position()
            unrealized_pnl = position['unrealized_pnl'] if position else 0.0
            
            # リスクメトリクス
            metrics = self.risk_manager.get_risk_metrics(current_balance)
            
            # ポジション統計
            pos_stats = self.position_manager.get_statistics()
            
            # ログ出力
            self.logger.log_performance(
                total_balance=current_balance,
                unrealized_pnl=unrealized_pnl,
                realized_pnl=metrics['total_pnl'],
                total_trades=metrics['total_trades'],
                win_rate=metrics['win_rate'],
                daily_return=metrics['daily_return']
            )
            
            self.logger.info(f"Active Orders: {pos_stats['active_orders']}")
            self.logger.info(f"Filled Orders: {pos_stats['filled_orders']}")
            
        except Exception as e:
            self.logger.error(f"Error logging performance: {e}")
    
    def emergency_shutdown(self):
        """緊急停止処理"""
        try:
            self.logger.critical("Executing emergency shutdown...")
            
            # 全注文をキャンセル
            self.client.cancel_all_orders()
            self.logger.info("All orders cancelled")
            
            # ポジションを決済（オプション）
            # position = self.client.get_position()
            # if position and position['size'] > 0:
            #     # ポジション決済ロジック
            #     pass
            
            # 最終パフォーマンスログ
            balance = self.client.get_balance()
            if balance:
                self.log_performance(balance['total'])
            
            self.logger.critical("Emergency shutdown completed")
            
        except Exception as e:
            self.logger.error(f"Error during emergency shutdown: {e}")
    
    def run(self):
        """BOTを実行"""
        try:
            # 初期化
            if not self.initialize():
                self.logger.error("Initialization failed, exiting...")
                return
            
            # メインループ開始
            self.logger.info("Starting main loop...")
            self.main_loop()
            
            # 正常終了処理
            self.logger.info("Bot stopped normally")
            
        except Exception as e:
            self.logger.critical(f"Fatal error: {e}")
        finally:
            # クリーンアップ
            self.logger.info("Cleaning up...")
            balance = self.client.get_balance()
            if balance:
                self.log_performance(balance['total'])


def main():
    """エントリーポイント"""
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║          Bybit Grid Trading Bot v1.0                      ║
    ║          Target: 5% Monthly Return                        ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    """)
    
    # BOT起動
    bot = GridTradingBot()
    bot.run()


if __name__ == "__main__":
    main()
