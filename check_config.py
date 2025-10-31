"""Configuration checker for Telegram Summary Bot."""
import os
import sys
from dotenv import load_dotenv


def check_config():
    """Check if all required configuration is present and valid."""
    print("🔍 Checking configuration...\n")

    # Load .env file
    if not os.path.exists('.env'):
        print("❌ .env file not found!")
        print("   Please copy .env.example to .env and fill in your credentials:")
        print("   cp .env.example .env")
        return False

    load_dotenv()

    all_ok = True

    # Check BOT_TOKEN
    bot_token = os.getenv('BOT_TOKEN')
    if not bot_token or bot_token == 'your_bot_token_here':
        print("❌ BOT_TOKEN not configured")
        print("   Get it from @BotFather in Telegram")
        all_ok = False
    else:
        print(f"✅ BOT_TOKEN: {bot_token[:10]}...{bot_token[-5:]}")

    # Check API_ID
    api_id = os.getenv('API_ID')
    if not api_id or api_id == 'your_api_id_here':
        print("❌ API_ID not configured")
        print("   Get it from https://my.telegram.org/apps")
        all_ok = False
    else:
        try:
            int(api_id)
            print(f"✅ API_ID: {api_id}")
        except ValueError:
            print("❌ API_ID must be a number")
            all_ok = False

    # Check API_HASH
    api_hash = os.getenv('API_HASH')
    if not api_hash or api_hash == 'your_api_hash_here':
        print("❌ API_HASH not configured")
        print("   Get it from https://my.telegram.org/apps")
        all_ok = False
    else:
        print(f"✅ API_HASH: {api_hash[:8]}...{api_hash[-4:]}")

    # Check OPENROUTER_API_KEY
    openrouter_key = os.getenv('OPENROUTER_API_KEY')
    if not openrouter_key or openrouter_key == 'your_openrouter_api_key_here':
        print("❌ OPENROUTER_API_KEY not configured")
        print("   Get it from https://openrouter.ai/")
        all_ok = False
    else:
        print(f"✅ OPENROUTER_API_KEY: {openrouter_key[:10]}...{openrouter_key[-5:]}")

    # Check OPENROUTER_MODEL
    model = os.getenv('OPENROUTER_MODEL', 'anthropic/claude-3.5-sonnet')
    print(f"✅ OPENROUTER_MODEL: {model}")

    print()

    if all_ok:
        print("✅ All configuration parameters are set!")
        print("\nYou can now run the bot with: ./run.sh")
        print("or: python main.py")
        return True
    else:
        print("❌ Some configuration parameters are missing or invalid")
        print("\nPlease edit .env file and fill in all required values")
        return False


if __name__ == "__main__":
    success = check_config()
    sys.exit(0 if success else 1)
