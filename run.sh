#!/bin/bash

# Bybit Grid Trading Bot 起動スクリプト

echo "=================================="
echo "Bybit Grid Trading Bot"
echo "=================================="

# 仮想環境の確認
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# 仮想環境をアクティベート
source venv/bin/activate

# 依存関係のインストール
echo "Installing dependencies..."
pip install -q -r requirements.txt

# .envファイルの確認
if [ ! -f "config/.env" ]; then
    echo "ERROR: config/.env file not found!"
    echo "Please copy config/.env.example to config/.env and set your API keys."
    exit 1
fi

# ログディレクトリの作成
mkdir -p logs

# BOTを起動
echo "Starting bot..."
python3 src/main.py

# 仮想環境を終了
deactivate
