# BOT更新手順 v1.1

## 🔧 修正内容

### 1. 構文エラーの修正
**問題:** `src/position_manager.py` の100行目に型ヒントの構文エラー
```python
# 修正前（エラー）
def track_orders(self) -> Dict:str, List]:

# 修正後（正常）
def track_orders(self) -> Dict[str, List]:
```

### 2. 既存ポジション平均価格取得エラーの修正
**問題:** 既存ポジションの平均価格が0.00と取得され、カウンター注文の配置に失敗
```python
# 修正前（エラー）
avg_price = float(position.get('avgPrice', 0))

# 修正後（正常）
avg_price = float(position.get('entry_price', 0))
```

**原因:** `get_position()`メソッドは`entry_price`というキーで平均価格を返しているが、`sync_initial_state()`メソッドでは存在しない`avgPrice`キーで取得しようとしていた。

---

## 🚀 更新手順

### ステップ1: 最新版をダウンロード

PowerShellで以下のコマンドを実行してください:

```powershell
cd "C:\Users\umeda ryotaro\bybit-grid-trading-bot"
git pull
```

**成功すると以下のように表示されます:**
```
Updating c03c543..f95a5ca
Fast-forward
 src/position_manager.py  | 2 +-
 test_position_sync.py    | 58 ++++++++++++++++++++++++++++++++++++++
 2 files changed, 59 insertions(+), 1 deletion(-)
 create mode 100644 test_position_sync.py
```

### ステップ2: （オプション）ポジション情報取得テスト

BOTを起動する前に、ポジション情報が正しく取得できるか確認できます:

```powershell
python test_position_sync.py
```

**期待される出力例:**
```
============================================================
ポジション情報取得テスト
============================================================

ポジション情報:
  Symbol: BTCUSDT
  Side: Buy
  Size: 0.002000 BTC
  Entry Price: 89445.35 USDT
  Unrealized PnL: -3.04 USDT
  Leverage: 2x

✅ アクティブなポジションが検出されました
✅ 平均価格が正しく取得されました: 89445.35 USDT

============================================================
```

### ステップ3: BOTを起動

```powershell
python src/main.py
```

---

## ✅ 確認ポイント

BOT起動時のログで以下を確認してください:

### 1. 既存ポジションの検出
```
2025-12-15 XX:XX:XX - GridBot - WARNING - Existing position detected: 0.002 BTC (Buy) @ 89445.35
```
- ✅ 平均価格が正しく表示されている（0.00ではない）

### 2. カウンター注文の配置成功
```
2025-12-15 XX:XX:XX - GridBot - INFO - Counter order placed: Sell 0.002 BTC @ 90067.83
```
- ✅ エラーなくカウンター注文が配置されている
- ✅ 価格が平均価格より高い（利益確定価格）

### 3. 初期状態の同期完了
```
2025-12-15 XX:XX:XX - GridBot - INFO - Initial state synced: 11 open orders, position size: 0.002 BTC
```
- ✅ 既存ポジションサイズが正しく表示されている

---

## 🐛 トラブルシューティング

### エラー: "Failed to place order: price is invalid"

**原因:** 平均価格が0.00のまま取得されている

**対処法:**
1. `git pull`が正しく実行されたか確認
2. `src/position_manager.py`の53行目を確認:
   ```python
   avg_price = float(position.get('entry_price', 0))  # entry_priceになっているか？
   ```
3. それでも解決しない場合は、Bybit APIの応答を確認:
   ```powershell
   python test_position_sync.py
   ```

### エラー: "SyntaxError: invalid syntax"

**原因:** 構文エラーが残っている

**対処法:**
1. `git pull`を再実行
2. `src/position_manager.py`の100行目を確認:
   ```python
   def track_orders(self) -> Dict[str, List]:  # コロンではなく角括弧になっているか？
   ```

---

## 📊 動作確認

BOTが正常に動作している場合、以下のような状態になります:

1. **既存ポジション検出**: 起動時に0.002 BTC (Buy)のポジションを検出
2. **カウンター注文配置**: ポジションに対して利益確定の売り注文を自動配置
3. **グリッド注文配置**: 新規のグリッド注文（買い5件、売り5件）を配置
4. **合計注文数**: 11件の未約定注文（グリッド10件 + カウンター1件）

---

## 📝 次のステップ

BOTが正常に起動したら:

1. **約定監視**: 注文が約定したら自動的にカウンター注文が配置されることを確認
2. **利益確定**: 既存ポジションの売り注文が約定して利益が確定することを確認
3. **グリッド継続**: 新しい買い注文が約定したら、自動的に売り注文が配置されることを確認

何か問題があれば、ログ全体を共有してください！
