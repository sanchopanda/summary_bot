#!/bin/bash

# Deploy script for Telegram Summary Bot (tmux version)
# This script is executed on the server after git pull

set -e  # Exit on any error

TMUX_SESSION="br"
BOT_DIR="$HOME/summary_bot"

echo "🚀 Starting deployment..."

# Check if we're in the right directory
if [ ! -f "main.py" ]; then
    echo "❌ main.py not found. Are you in the bot directory?"
    exit 1
fi

# Activate virtual environment
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    echo "✅ Virtual environment activated"
else
    echo "❌ Virtual environment not found. Run ./setup.sh first"
    exit 1
fi

# Update dependencies
echo "📦 Updating dependencies..."
pip install -r requirements.txt --quiet

# Check configuration
echo "🔍 Validating configuration..."
python check_config.py

# Check if tmux session exists
if tmux has-session -t "$TMUX_SESSION" 2>/dev/null; then
    echo "🔄 Restarting bot in tmux session '$TMUX_SESSION'..."

    # Send Ctrl+C to stop the current process
    tmux send-keys -t "$TMUX_SESSION" C-c
    sleep 2

    # Clear the terminal
    tmux send-keys -t "$TMUX_SESSION" "clear" Enter
    sleep 1

    # Start the bot
    tmux send-keys -t "$TMUX_SESSION" "cd $BOT_DIR && ./run.sh" Enter

    echo "✅ Bot restarted in existing tmux session"
else
    echo "📺 Creating new tmux session '$TMUX_SESSION'..."

    # Create new detached session and start the bot
    tmux new-session -d -s "$TMUX_SESSION" -c "$BOT_DIR"
    sleep 1
    tmux send-keys -t "$TMUX_SESSION" "./run.sh" Enter

    echo "✅ Bot started in new tmux session"
fi

# Wait a bit for the bot to start
echo "⏳ Waiting for bot to start..."
sleep 5

# Show the last few lines from tmux
echo "📊 Recent output:"
tmux capture-pane -t "$TMUX_SESSION" -p | tail -15

echo ""
echo "🎉 Deployment completed successfully!"
echo ""
echo "💡 Useful commands:"
echo "   tmux attach -t $TMUX_SESSION    # Attach to the session"
echo "   tmux capture-pane -t $TMUX_SESSION -p | tail -20  # View recent output"
echo "   tmux send-keys -t $TMUX_SESSION C-c  # Stop the bot"
