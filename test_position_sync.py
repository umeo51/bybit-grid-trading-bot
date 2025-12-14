#!/usr/bin/env python3
"""
既存ポジション同期機能のテストスクリプト
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent / 'src'))

from config import Config
from logger import BotLogger
from bybit_client import BybitClient

def test_position_sync():
    """ポジション情報取得のテスト"""
    
    # 設定とロガーを初期化
    config = Config()
    logger = BotLogger(config)
    
    # Bybitクライアントを初期化
    client = BybitClient(config, logger)
    
    print("\n" + "="*60)
    print("ポジション情報取得テスト")
    print("="*60)
    
    # ポジション情報を取得
    position = client.get_position()
    
    if position:
        print(f"\nポジション情報:")
        print(f"  Symbol: {position.get('symbol', 'N/A')}")
        print(f"  Side: {position.get('side', 'N/A')}")
        print(f"  Size: {position.get('size', 0):.6f} BTC")
        print(f"  Entry Price: {position.get('entry_price', 0):.2f} USDT")
        print(f"  Unrealized PnL: {position.get('unrealized_pnl', 0):.2f} USDT")
        print(f"  Leverage: {position.get('leverage', 0)}x")
        
        # ポジションサイズが0より大きい場合
        if abs(float(position.get('size', 0))) > 0:
            print("\n✅ アクティブなポジションが検出されました")
            
            # entry_priceが正しく取得できているか確認
            entry_price = float(position.get('entry_price', 0))
            if entry_price > 0:
                print(f"✅ 平均価格が正しく取得されました: {entry_price:.2f} USDT")
            else:
                print("❌ 平均価格の取得に失敗しました（0.00）")
        else:
            print("\nℹ️  現在ポジションはありません")
    else:
        print("❌ ポジション情報の取得に失敗しました")
    
    print("\n" + "="*60)

if __name__ == "__main__":
    test_position_sync()
