#!/bin/bash

# Telegram Bot Runner for PSQLI

echo "🚀 PSQLI Telegram Bot"
echo "======================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 is not installed!"
    echo "Please install Python3 first."
    exit 1
fi

# Check dependencies
echo "📦 Installing dependencies..."
pip3 install -r requirements.txt --quiet

# Check config
if ! grep -q "YOUR_BOT_TOKEN_HERE" config.py; then
    echo "⚠️ Please set your BOT_TOKEN in config.py"
    echo "Get token from @BotFather on Telegram"
    exit 1
fi

# Make psqli.sh executable
chmod +x psqli.sh

# Run bot
echo "🤖 Starting bot..."
python3 bot.py
