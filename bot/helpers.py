"""Helper functions for the bot."""
import re
import logging
from telegram import Update

logger = logging.getLogger(__name__)


def escape_html(text: str) -> str:
    """Escape special HTML characters in text."""
    if not text:
        return text
    # Escape special characters for Telegram HTML
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    return text


async def send_long_message(update: Update, text: str):
    """Send a long message, splitting it if necessary."""
    max_length = 4096

    if len(text) <= max_length:
        await update.message.reply_text(text, parse_mode='HTML')
    else:
        # Split by channel separators
        parts = text.split("─" * 50)
        current_part = ""

        for part in parts:
            if len(current_part) + len(part) + 50 < max_length:
                current_part += part + "\n" + "─" * 50 + "\n"
            else:
                if current_part:
                    await update.message.reply_text(current_part, parse_mode='HTML')
                current_part = part + "\n" + "─" * 50 + "\n"

        if current_part:
            await update.message.reply_text(current_part, parse_mode='HTML')


def fix_html_tags(text: str) -> str:
    """
    Fix unclosed HTML <a> tags in text.
    If fixing fails, falls back to plain text without HTML tags.

    Args:
        text: Text with potentially unclosed HTML tags

    Returns:
        Fixed HTML text or plain text if fixing failed
    """
    if not text:
        return text

    try:
        # Count opening and closing <a> tags
        opening_tags = re.findall(r'<a\s+href=["\']([^"\']+)["\']>', text)
        closing_tags = re.findall(r'</a>', text)

        # If we have more opening tags than closing tags, we need to fix
        unclosed_count = len(opening_tags) - len(closing_tags)

        if unclosed_count > 0:
            logger.warning(f"Found {unclosed_count} unclosed <a> tags, attempting to fix")
            # Add missing closing tags at the end
            text = text + ('</a>' * unclosed_count)

        # Validate: check that all tags are properly paired
        # Simple validation: count should match now
        opening_after = len(re.findall(r'<a\s+href=["\']([^"\']+)["\']>', text))
        closing_after = len(re.findall(r'</a>', text))

        if opening_after != closing_after:
            logger.error(f"HTML validation failed: {opening_after} opening tags vs {closing_after} closing tags")
            # Fall back to plain text
            return _strip_html_tags(text)

        logger.info(f"HTML tags fixed successfully: {unclosed_count} tags closed")
        return text

    except Exception as e:
        logger.error(f"Error fixing HTML tags: {e}", exc_info=True)
        # Fall back to plain text
        return _strip_html_tags(text)


def _strip_html_tags(text: str) -> str:
    """
    Remove all HTML <a> tags from text, keeping URLs in plain format.

    Args:
        text: Text with HTML tags

    Returns:
        Plain text with URLs exposed
    """
    logger.warning("Falling back to plain text format (stripping HTML tags)")

    # Replace <a href='URL'>text</a> with just "text (URL)"
    # Handle both single and double quotes
    text = re.sub(r'<a\s+href=["\']([^"\']+)["\']>([^<]*)', r'\2 (\1)', text)

    # Remove any remaining closing </a> tags
    text = re.sub(r'</a>', '', text)

    # Add a warning note at the beginning
    text = "⚠️ Ссылки предоставлены в текстовом формате\n\n" + text

    return text
