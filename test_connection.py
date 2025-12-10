"""
Bybit API接続テスト（本番環境）
"""

import os
import time
import hmac
import hashlib
import requests
from dotenv import load_dotenv
from pathlib import Path

# .envファイルを読み込み
env_path = Path(__file__).parent / 'config' / '.env'
load_dotenv(env_path)

# 環境変数から取得
api_key = os.getenv('BYBIT_API_KEY', '').strip()
api_secret = os.getenv('BYBIT_API_SECRET', '').strip()

print("=" * 60)
print("Bybit API Connection Test (Production)")
print("=" * 60)
print(f"API Key: {api_key[:10]}... (length: {len(api_key)})")
print(f"API Secret: {'*' * 10}... (length: {len(api_secret)})")
print("=" * 60)

# Bybit V5 API設定（本番環境）
BASE_URL = "https://api.bybit.com"
RECV_WINDOW = "5000"

def generate_signature(params: str, api_secret: str) -> str:
    """署名を生成"""
    return hmac.new(
        api_secret.encode('utf-8'),
        params.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

def get_wallet_balance():
    """残高を取得"""
    timestamp = str(int(time.time() * 1000))
    
    # パラメータ
    params = {
        'accountType': 'UNIFIED'
    }
    
    # クエリ文字列を作成
    query_string = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
    
    # 署名用の文字列を作成
    param_str = f"{timestamp}{api_key}{RECV_WINDOW}{query_string}"
    
    # 署名を生成
    signature = generate_signature(param_str, api_secret)
    
    # ヘッダーを設定
    headers = {
        'X-BAPI-API-KEY': api_key,
        'X-BAPI-SIGN': signature,
        'X-BAPI-TIMESTAMP': timestamp,
        'X-BAPI-RECV-WINDOW': RECV_WINDOW,
        'Content-Type': 'application/json'
    }
    
    # リクエストを送信
    url = f"{BASE_URL}/v5/account/wallet-balance"
    
    print(f"\nRequest URL: {url}")
    print(f"Sending request...")
    
    response = requests.get(url, params=params, headers=headers)
    
    print(f"Response Status: {response.status_code}")
    
    return response.json()

# テスト実行
try:
    print("\n" + "=" * 60)
    print("Testing Wallet Balance API")
    print("=" * 60)
    
    result = get_wallet_balance()
    
    if result.get('retCode') == 0:
        print("\n✓✓✓ SUCCESS! ✓✓✓")
        
        # 残高を表示
        coins = result['result']['list'][0]['coin']
        print("\nAccount Balance:")
        print("-" * 60)
        for coin in coins:
            if float(coin['walletBalance']) > 0:
                print(f"{coin['coin']}: {coin['walletBalance']} (Available: {coin['availableToWithdraw']})")
    else:
        print(f"\n✗ Error: {result.get('retMsg')}")
        print(f"Error Code: {result.get('retCode')}")
        print(f"\nFull response: {result}")
        
except Exception as e:
    print(f"\n✗ Exception: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("Test completed")
print("=" * 60)
