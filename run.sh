#!/bin/bash
# Run script for Telegram Summary Bot

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ .env file not found!"
    echo "Please copy .env.example to .env and fill in your credentials:"
    echo "  cp .env.example .env"
    echo "  nano .env"
    exit 1
fi

# Activate virtual environment
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "Please run ./setup.sh first"
    exit 1
fi

echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Run the bot
echo "🤖 Starting Telegram Summary Bot..."
echo "Press Ctrl+C to stop"
echo ""
python main.py
