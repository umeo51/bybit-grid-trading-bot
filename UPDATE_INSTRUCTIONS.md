# BOT更新手順（動的設定調整機能の追加）

## 更新内容

資産額に応じて自動的にグリッド数や設定を最適化する機能を追加しました。

**主な変更点:**
- 300 USDT → 6グリッド（保守的運用）
- 500 USDT → 10グリッド（バランス運用）
- 1000 USDT → 15グリッド（標準運用）
- 2000 USDT → 20グリッド（積極運用）
- 5000 USDT → 40グリッド（最大効率運用）

資産が増えるにつれて、自動的により効率的な設定に切り替わります。

## 更新手順

### 1. 現在のBOTを停止

Visual Studio Codeのターミナルで `Ctrl+C` を押してBOTを停止してください。

### 2. 最新版をダウンロード

Visual Studio Codeのターミナルで以下のコマンドを実行してください:

```bash
git pull
```

### 3. 新しいファイルの確認

以下のファイルが追加されているはずです:

- `src/dynamic_config.py` - 動的設定調整機能
- `DYNAMIC_CONFIG.md` - 機能の詳細説明
- `UPDATE_INSTRUCTIONS.md` - この手順書

### 4. BOTを再起動

```bash
python src/main.py
```

## 動作確認

BOT起動時に以下のようなログが表示されれば成功です:

```
2025-12-11 19:30:00 - GridBot - INFO - Available balance: 350.00 USDT
2025-12-11 19:30:00 - GridBot - INFO - ============================================================
2025-12-11 19:30:00 - GridBot - INFO - Applying dynamic configuration based on balance...
2025-12-11 19:30:00 - GridBot - INFO - ============================================================
2025-12-11 19:30:00 - GridBot - INFO - Balance tier: 300-500 USDT: 保守的運用
2025-12-11 19:30:00 - GridBot - INFO - Optimal grid count: 6
```

## 設定の自動調整について

### 資産が増えた場合

例: 350 USDT → 550 USDT

BOTが自動的に検知し、以下のようなログが表示されます:

```
============================================================
Balance tier changed - Rebalancing configuration...
============================================================
Balance tier: 500-800 USDT: バランス運用
Optimal grid count: 10
Price range: ±3.5%
Max position ratio: 75%
グリッドを再初期化します...
```

既存の注文はすべてキャンセルされ、新しい設定でグリッドが再構築されます。

### 資産が減った場合

例: 1500 USDT → 750 USDT

同様に自動的に検知し、より保守的な設定に切り替わります（リスク軽減）。

## トラブルシューティング

### Q1: `git pull` でエラーが出る

**エラー例:**
```
error: Your local changes to the following files would be overwritten by merge
```

**解決方法:**
```bash
git stash
git pull
git stash pop
```

### Q2: BOTが起動しない

**確認事項:**
1. Python環境が正しいか確認
2. 必要なパッケージがインストールされているか確認
   ```bash
   pip install -r requirements.txt
   ```

### Q3: 動的設定調整を無効にしたい

`src/main.py` の194-221行目をコメントアウトしてください:

```python
# # 1.5. 資産額に応じた再調整チェック
# if self.dynamic_config.should_rebalance(available_balance):
#     ...（以下すべてコメントアウト）
```

## 詳細情報

動的設定調整機能の詳細については、`DYNAMIC_CONFIG.md` をご覧ください。

## サポート

問題が発生した場合は、以下の情報を添えてお知らせください:

1. エラーメッセージ
2. `logs/` フォルダ内の最新ログファイル
3. 現在の資産額
4. 実行環境（Windows/Mac/Linux）

---

**更新日: 2025年12月13日**
