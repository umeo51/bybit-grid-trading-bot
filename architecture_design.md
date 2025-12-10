# Bybit自動取引BOT アーキテクチャ設計

## システム構成図

```
┌─────────────────────────────────────────────────────────┐
│                    Main Controller                       │
│  - 全体の制御とスケジューリング                            │
│  - エラーハンドリング                                      │
└────────────┬────────────────────────────────────────────┘
             │
    ┌────────┴────────┐
    │                 │
┌───▼────┐      ┌────▼─────┐
│ Config │      │  Logger  │
│ Manager│      │          │
└────────┘      └──────────┘
    │
    ├─────────────┬─────────────┬──────────────┬───────────────┐
    │             │             │              │               │
┌───▼────┐  ┌────▼─────┐  ┌───▼──────┐  ┌───▼──────┐  ┌────▼──────┐
│ Bybit  │  │ Market   │  │  Grid    │  │  Risk    │  │ Position  │
│ API    │  │ Data     │  │ Strategy │  │ Manager  │  │ Manager   │
│ Client │  │ Analyzer │  │          │  │          │  │           │
└────────┘  └──────────┘  └──────────┘  └──────────┘  └───────────┘
```

## モジュール設計

### 1. Config Manager (config.py)
**責務**: 設定の管理と検証

```python
class Config:
    # API設定
    API_KEY: str
    API_SECRET: str
    TESTNET: bool = True
    
    # 取引設定
    SYMBOL: str = "BTCUSDT"
    LEVERAGE: int = 2
    GRID_COUNT: int = 20
    GRID_RANGE_PERCENT: float = 0.05  # ±5%
    
    # リスク管理
    MAX_POSITION_SIZE: float = 0.6  # 総資金の60%
    DAILY_LOSS_LIMIT: float = 0.05  # 5%
    STOP_LOSS_PERCENT: float = 0.10  # 10%
    
    # 手数料
    MAKER_FEE: float = 0.0002  # 0.02%
    TAKER_FEE: float = 0.0055  # 0.055%
```

### 2. Bybit API Client (bybit_client.py)
**責務**: Bybit APIとの通信

**主要メソッド**:
- `get_balance()`: 残高取得
- `get_ticker(symbol)`: 現在価格取得
- `get_klines(symbol, interval, limit)`: ローソク足データ取得
- `place_limit_order(symbol, side, qty, price)`: 指値注文
- `cancel_order(symbol, order_id)`: 注文キャンセル
- `get_open_orders(symbol)`: 未約定注文取得
- `get_position(symbol)`: ポジション情報取得
- `set_leverage(symbol, leverage)`: レバレッジ設定

### 3. Market Data Analyzer (market_analyzer.py)
**責務**: 市場データの分析

**主要メソッド**:
- `calculate_atr(period=14)`: ATR計算
- `get_current_price()`: 現在価格取得
- `calculate_volatility()`: ボラティリティ計算
- `is_range_market()`: レンジ相場判定
- `get_optimal_grid_range()`: 最適なグリッド範囲計算

### 4. Grid Strategy (grid_strategy.py)
**責務**: グリッド戦略の実装

**主要メソッド**:
- `calculate_grid_levels(current_price, range_percent, grid_count)`: グリッドレベル計算
- `generate_grid_orders()`: グリッド注文生成
- `adjust_grid_range()`: グリッド範囲の動的調整
- `calculate_order_size(total_capital, grid_count)`: 注文サイズ計算

**グリッド計算ロジック**:
```python
def calculate_grid_levels(current_price, range_percent, grid_count):
    upper_price = current_price * (1 + range_percent)
    lower_price = current_price * (1 - range_percent)
    grid_step = (upper_price - lower_price) / grid_count
    
    buy_levels = []
    sell_levels = []
    
    for i in range(grid_count // 2):
        buy_price = current_price - (grid_step * (i + 1))
        sell_price = current_price + (grid_step * (i + 1))
        buy_levels.append(buy_price)
        sell_levels.append(sell_price)
    
    return buy_levels, sell_levels
```

### 5. Risk Manager (risk_manager.py)
**責務**: リスク管理とポジション制御

**主要メソッド**:
- `check_daily_loss()`: 日次損失チェック
- `check_position_size()`: ポジションサイズチェック
- `should_stop_trading()`: 取引停止判定
- `calculate_stop_loss_price()`: 損切り価格計算
- `check_drawdown()`: ドローダウンチェック

**リスク管理ルール**:
```python
class RiskManager:
    def check_daily_loss(self, current_balance, start_balance):
        loss_percent = (start_balance - current_balance) / start_balance
        if loss_percent >= self.config.DAILY_LOSS_LIMIT:
            return True, "Daily loss limit reached"
        return False, None
    
    def check_position_size(self, position_value, total_balance):
        position_ratio = position_value / total_balance
        if position_ratio > self.config.MAX_POSITION_SIZE:
            return False, "Position size exceeds limit"
        return True, None
```

### 6. Position Manager (position_manager.py)
**責務**: ポジションとオーダーの管理

**主要メソッド**:
- `track_orders()`: 注文追跡
- `handle_filled_order(order)`: 約定処理
- `rebalance_grid()`: グリッドのリバランス
- `calculate_pnl()`: 損益計算
- `get_active_positions()`: アクティブポジション取得

### 7. Logger (logger.py)
**責務**: ログ記録と通知

**ログレベル**:
- INFO: 通常の取引情報
- WARNING: 警告（リスク限界接近など）
- ERROR: エラー情報
- CRITICAL: 重大なエラー（取引停止など）

**ログ出力**:
- コンソール出力
- ファイル出力 (logs/bot_{date}.log)
- 取引履歴CSV (logs/trades_{date}.csv)

### 8. Main Controller (main.py)
**責務**: 全体の制御とスケジューリング

**メインループ**:
```python
def main_loop():
    while True:
        try:
            # 1. 市場データ取得
            current_price = market_analyzer.get_current_price()
            
            # 2. リスクチェック
            if risk_manager.should_stop_trading():
                logger.warning("Trading stopped due to risk limits")
                break
            
            # 3. グリッド更新チェック
            if should_update_grid():
                grid_strategy.adjust_grid_range()
                position_manager.rebalance_grid()
            
            # 4. 注文管理
            position_manager.track_orders()
            
            # 5. パフォーマンス記録
            log_performance()
            
            # 6. 待機
            time.sleep(60)  # 1分ごとに実行
            
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            time.sleep(300)  # エラー時は5分待機
```

## データフロー

1. **起動時**:
   ```
   Config読み込み → API接続確認 → 初期残高取得 → グリッド生成 → 注文配置
   ```

2. **メインループ**:
   ```
   市場データ取得 → リスクチェック → 注文状態確認 → 約定処理 → グリッド調整 → ログ記録
   ```

3. **注文約定時**:
   ```
   約定通知受信 → ポジション更新 → 対向注文生成 → 損益計算 → ログ記録
   ```

## エラーハンドリング戦略

### レベル1: リトライ可能なエラー
- ネットワークエラー
- API Rate Limit
- 一時的なサーバーエラー

**対応**: 指数バックオフでリトライ（最大3回）

### レベル2: 警告レベルのエラー
- 注文失敗（残高不足など）
- 価格範囲外

**対応**: ログ記録、アラート送信、処理続行

### レベル3: 致命的なエラー
- API認証エラー
- 日次損失限界到達
- システムエラー

**対応**: 全ポジション決済、取引停止、管理者通知

## セキュリティ設計

1. **APIキー管理**:
   - 環境変数または暗号化ファイルで管理
   - 出金権限は付与しない
   - IP制限を設定

2. **データ保護**:
   - 機密情報はログに出力しない
   - 取引履歴は暗号化して保存

3. **アクセス制御**:
   - 設定ファイルのパーミッション制限
   - ログファイルのアクセス制限

## パフォーマンス最適化

1. **API呼び出し最小化**:
   - WebSocket使用（価格データ）
   - バッチ処理（複数注文）
   - キャッシング（設定データ）

2. **メモリ管理**:
   - 古いログの定期削除
   - データ構造の最適化

3. **並行処理**:
   - 非同期I/O (asyncio)
   - マルチスレッド（データ取得と注文処理）

## ディレクトリ構造

```
bybit_grid_bot/
├── config/
│   ├── config.yaml          # 設定ファイル
│   └── secrets.env          # APIキー（.gitignore）
├── src/
│   ├── __init__.py
│   ├── main.py              # メインコントローラー
│   ├── config.py            # 設定管理
│   ├── bybit_client.py      # API クライアント
│   ├── market_analyzer.py   # 市場分析
│   ├── grid_strategy.py     # グリッド戦略
│   ├── risk_manager.py      # リスク管理
│   ├── position_manager.py  # ポジション管理
│   └── logger.py            # ログ管理
├── logs/
│   ├── bot_2025-12-04.log
│   └── trades_2025-12-04.csv
├── tests/
│   ├── test_grid_strategy.py
│   └── test_risk_manager.py
├── requirements.txt
├── README.md
└── run.sh                   # 起動スクリプト
```

## 次のステップ

Phase 3で各モジュールの実装を開始します。
