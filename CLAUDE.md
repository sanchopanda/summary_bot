# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Telegram bot that monitors Telegram channels and automatically generates summaries using AI (via OpenRouter API). It supports both public and private channels, stores channel subscriptions in SQLite, and sends periodic summaries based on user-configured schedules.

## Key Architecture Concepts

### Dual Telegram Integration
The bot uses **two separate Telegram connections**:
1. **python-telegram-bot** - Standard bot API for bot commands and user interactions
2. **Telethon** - Full Telegram client for reading channel messages (necessary for private channels)

This dual approach is required because bot API cannot read channel messages directly. The Telethon client needs user account authorization (phone + code) on first run.

### Async Architecture
All major components (bot, database, Telegram client) use Python asyncio. When modifying code:
- Use `async def` for new functions that interact with these components
- Use `await` for all database, bot, and client operations
- Be careful with blocking operations in async context

### Data Flow
1. User adds channel via bot command (`/add`)
2. Bot validates channel access via Telethon client
3. Channel saved to SQLite database
4. Scheduler periodically checks for users needing summaries
5. Bot reads messages via Telethon client
6. Messages sent to OpenRouter API for summarization
7. Summary delivered to user via bot

## Development Commands

### Setup and Installation
```bash
./setup.sh                    # Initial setup: creates venv and installs dependencies
source venv/bin/activate      # Activate virtual environment
pip install -r requirements.txt  # Install/update dependencies
```

### Running the Bot
```bash
./run.sh                      # Standard run (checks .env and venv)
python main.py                # Direct run (requires manual venv activation)
python check_config.py        # Validate configuration without starting bot
```

### First Run Authorization
On first run, Telethon requires user account authorization:
1. Enter phone number in international format (e.g., +1234567890)
2. Enter verification code sent to your Telegram
3. (If 2FA enabled) Enter 2FA password
4. Session saved to `telegram_session.session` for future runs

**Important**: Use a Telegram account subscribed to all private channels you want to monitor.

No automated tests are currently implemented.

## Configuration Requirements

The `.env` file must contain:
- **BOT_TOKEN** - From @BotFather
- **API_ID** and **API_HASH** - From https://my.telegram.org/apps (for Telethon)
- **OPENROUTER_API_KEY** - From https://openrouter.ai/
- **OPENROUTER_MODEL** - Model identifier (default: anthropic/claude-3.5-sonnet)
- **DATABASE_PATH** - SQLite database file path
- **SESSION_NAME** - Telethon session file name

Use `.env.example` as template.

## Important Implementation Details

### Database Schema
SQLite with two main tables:
- **users**: `user_id`, `username`, `first_name`, `summary_period` (in days: 1, 3, or 7), `last_summary`
- **channels**: `user_id`, `channel_username`, `channel_id`, `channel_title`, `added_at`, `last_message_date`

The database uses aiosqlite for async operations. When modifying schema in `database.py:init_db()`, existing databases won't auto-migrate.

### Scheduler Behavior
`scheduler.py` uses APScheduler with CronTrigger to run `send_scheduled_summaries()` every hour. It checks each user's `last_summary_time` and `summary_period` to determine if summary is due. This is NOT real-time - users may receive summaries up to 1 hour late.

### Channel Username Handling
Channels can be referenced with or without `@` prefix. The code normalizes this by stripping `@` when storing in database (`database.py`) and when making Telethon calls (`client.py`).

### Message Collection Period
When generating summaries, the bot collects messages from the period specified by user's `summary_period` setting (24h, 72h, or 168h). This is calculated from current time backwards, NOT from last summary time. If scheduler is down for days, users won't get a "catch-up" summary covering missed periods.

### OpenRouter Integration
`summarizer.py` sends messages to OpenRouter API with streaming disabled. The prompt instructs the model to create a structured summary organized by channel. For multi-channel summaries, all messages are sent in one request with channel separators.

Important details:
- Messages longer than 2000 characters are truncated in `_format_messages()`
- Summaries use `max_tokens=2000` and `temperature=0.7`
- The bot automatically splits responses longer than 4096 characters (Telegram limit) in `_send_long_message()`
- After each summary, bot adds links to top 5 most viewed posts via `_add_message_links()`
- Links format: `https://t.me/{channel_username}/{message_id}` with message preview (first 100 chars)

### Connection Retry Logic
`main.py` implements retry logic for bot initialization:
- Up to 3 connection attempts with 5-second delays
- Custom HTTP timeouts: 30 seconds for all operations (connect, read, write, pool)
- Helpful error messages suggesting VPN/proxy if Telegram is blocked

### Timezone Handling
All message date comparisons use UTC timezone (`datetime.now(timezone.utc)`) to match Telegram's message timestamps. This prevents timezone-related bugs when collecting messages for summaries.

## Common Modification Patterns

### Adding New Bot Command
1. Define handler method in `bot.py` (e.g., `async def cmd_newcommand()`)
2. Register in `build_application()`: `self.application.add_handler(CommandHandler("newcommand", self.cmd_newcommand))`
3. Add description to `/help` and `/start` commands
4. Update README.md

### Changing Summary Periods
Summary periods are defined in `cmd_set_period()` in `bot.py`. To add/modify periods:
1. Update inline keyboard options in `cmd_set_period()`
2. Update callback handler in `handle_callback()` for "period:" callbacks
3. Update help text in relevant commands

### Modifying Summary Format
Summary generation logic is in `summarizer.py`:
- `_format_messages()` - Controls how messages are formatted for the LLM
- `generate_summary()` - Contains the system prompt for single channel
- `generate_multi_channel_summary()` - Contains prompt for multiple channels

### Changing Scheduler Frequency
Modify the CronTrigger in `scheduler.py:start()`. Current: `CronTrigger(minute=0)` (every hour). For testing, use `IntervalTrigger(minutes=X)` instead.

### Error Handling Patterns
When modifying code, follow these error handling patterns:
- **Telethon operations**: Catch `ChannelPrivateError`, `ChannelInvalidError`, `UsernameInvalidError`, `UsernameNotOccupiedError` (see `client.py`)
- **Database operations**: Catch `aiosqlite.IntegrityError` for constraint violations
- **OpenRouter API**: Catch `requests.exceptions.RequestException` with timeouts
- **Scheduler errors**: Individual user summary failures are caught and logged but don't stop the scheduler (see `bot.py:send_scheduled_summaries()` line 355)

## File Organization

**Core modules** (all Python, no subdirectories):
- `main.py` - Entry point, initialization, graceful shutdown
- `bot.py` - Bot commands, callback handlers, summary delivery
- `client.py` - Telethon client wrapper for channel reading
- `database.py` - SQLite operations
- `summarizer.py` - OpenRouter API integration
- `scheduler.py` - APScheduler wrapper
- `config.py` - Environment variable loading and validation

**Helper scripts**:
- `setup.sh` - Automated setup
- `run.sh` - Run with validation
- `check_config.py` - Configuration validation utility

**Generated at runtime** (not in git):
- `bot_data.db` - SQLite database
- `telegram_session.session` - Telethon session (sensitive!)
- `.env` - Configuration (sensitive!)

## Systemd Deployment

For production deployment, use the included `telegram-summary-bot.service` file:
```bash
sudo cp telegram-summary-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable telegram-summary-bot
sudo systemctl start telegram-summary-bot
```

Service runs as the `aleksander` user and uses absolute paths. Modify `User` and `WorkingDirectory` for different setups.
