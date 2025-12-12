"""
残高取得のデバッグスクリプト
"""

import os
import time
import hmac
import hashlib
import requests
import json
from dotenv import load_dotenv
from pathlib import Path

# .envファイルを読み込み
env_path = Path(__file__).parent / 'config' / '.env'
load_dotenv(env_path)

# 環境変数から取得
api_key = os.getenv('BYBIT_API_KEY', '').strip()
api_secret = os.getenv('BYBIT_API_SECRET', '').strip()

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
    params = {'accountType': 'UNIFIED'}
    
    query_string = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
    param_str = f"{timestamp}{api_key}{RECV_WINDOW}{query_string}"
    signature = generate_signature(param_str, api_secret)
    
    headers = {
        'X-BAPI-API-KEY': api_key,
        'X-BAPI-SIGN': signature,
        'X-BAPI-TIMESTAMP': timestamp,
        'X-BAPI-RECV-WINDOW': RECV_WINDOW,
        'Content-Type': 'application/json'
    }
    
    url = f"{BASE_URL}/v5/account/wallet-balance"
    response = requests.get(url, params=params, headers=headers)
    
    return response.json()

# テスト実行
print("=" * 80)
print("Balance Debug Information")
print("=" * 80)

result = get_wallet_balance()

if result.get('retCode') == 0:
    print("\n✓ API call successful\n")
    
    # 完全なレスポンスを表示
    print("Full Response:")
    print(json.dumps(result, indent=2))
    
    print("\n" + "=" * 80)
    print("Coin Details:")
    print("=" * 80)
    
    coins = result['result']['list'][0]['coin']
    for coin in coins:
        if coin['coin'] == 'USDT':
            print(f"\nUSDT Details:")
            print(f"  coin: {coin['coin']}")
            print(f"  walletBalance: '{coin['walletBalance']}' (type: {type(coin['walletBalance'])})")
            print(f"  availableToWithdraw: '{coin['availableToWithdraw']}' (type: {type(coin['availableToWithdraw'])})")
            print(f"  equity: '{coin.get('equity', 'N/A')}'")
            print(f"  availableToBorrow: '{coin.get('availableToBorrow', 'N/A')}'")
            print(f"  borrowAmount: '{coin.get('borrowAmount', 'N/A')}'")
            print(f"  accruedInterest: '{coin.get('accruedInterest', 'N/A')}'")
            print(f"  totalOrderIM: '{coin.get('totalOrderIM', 'N/A')}'")
            print(f"  totalPositionIM: '{coin.get('totalPositionIM', 'N/A')}'")
            print(f"  totalPositionMM: '{coin.get('totalPositionMM', 'N/A')}'")
            print(f"  unrealisedPnl: '{coin.get('unrealisedPnl', 'N/A')}'")
            print(f"  cumRealisedPnl: '{coin.get('cumRealisedPnl', 'N/A')}'")
            
            # 計算
            wallet_balance = float(coin['walletBalance']) if coin['walletBalance'] else 0.0
            available_to_withdraw = float(coin['availableToWithdraw']) if coin['availableToWithdraw'] else 0.0
            
            print(f"\nCalculated Values:")
            print(f"  wallet_balance (float): {wallet_balance}")
            print(f"  available_to_withdraw (float): {available_to_withdraw}")
            print(f"  used: {wallet_balance - available_to_withdraw}")
            
else:
    print(f"\n✗ Error: {result.get('retMsg')}")
    print(f"Error Code: {result.get('retCode')}")

print("\n" + "=" * 80)
