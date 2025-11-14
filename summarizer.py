"""OpenRouter API integration for generating summaries."""
import requests
from typing import List, Dict
from config import OPENROUTER_API_KEY, OPENROUTER_MODEL


class Summarizer:
    """Generate summaries of channel messages using OpenRouter API."""

    def __init__(self):
        self.api_key = OPENROUTER_API_KEY
        self.model = OPENROUTER_MODEL
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"

    def generate_summary(self, messages: List[Dict[str, str]], channel_name: str) -> str:
        """
        Generate a summary of messages from a channel.

        Args:
            messages: List of dicts with 'date', 'text', 'views' keys
            channel_name: Name of the channel

        Returns:
            Generated summary text
        """
        if not messages:
            return f"Нет новых сообщений в канале {channel_name}."

        # Prepare messages text
        messages_text = self._format_messages(messages)

        # Create prompt for LLM
        prompt = f"""Создай краткое саммари (summary) сообщений из Telegram канала "{channel_name}".

Сообщения за период:
{messages_text}

Требования к саммари:
1. Выдели основные темы и важные новости
2. Группируй похожие сообщения вместе
3. Указывай конкретные факты, цифры, даты если они есть
4. Пиши кратко и по существу
5. Используй bullet points для структуры
6. Если есть особо важные/популярные сообщения (по просмотрам), отметь это
7. Пиши на русском языке

Саммари:"""

        try:
            response = requests.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/aleksander/telegram-summary-bot",
                    "X-Title": "Telegram Summary Bot"
                },
                json={
                    "model": self.model,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "max_tokens": 2000,
                    "temperature": 0.7,
                },
                timeout=60
            )

            # Debug: print response details if error
            if response.status_code != 200:
                print(f"OpenRouter API Error: Status {response.status_code}")
                print(f"Response: {response.text}")

            response.raise_for_status()

            result = response.json()
            summary = result['choices'][0]['message']['content']

            # Add links to messages
            summary_with_links = self._add_message_links(summary.strip(), messages, channel_name)
            return summary_with_links

        except requests.exceptions.RequestException as e:
            return f"❌ Ошибка при генерации саммари для {channel_name}: {str(e)}"

    def generate_multi_channel_summary(self, channels_messages: Dict[str, List[Dict[str, str]]]) -> str:
        """
        Generate a combined summary for multiple channels.

        Args:
            channels_messages: Dict mapping channel names to their message lists

        Returns:
            Combined summary text
        """
        if not channels_messages:
            return "Нет новых сообщений ни в одном из отслеживаемых каналов."

        summaries = []
        for channel_name, messages in channels_messages.items():
            # Escape HTML in channel name
            safe_channel_name = channel_name.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            if messages:
                summary = self.generate_summary(messages, channel_name)
                summaries.append(f"📢 <b>{safe_channel_name}</b>\n\n{summary}")
            else:
                summaries.append(f"📢 <b>{safe_channel_name}</b>\n\nНет новых сообщений.")

        return "\n\n" + "─" * 50 + "\n\n".join(summaries)

    def _format_messages(self, messages: List[Dict[str, str]], include_links: bool = False) -> str:
        """Format messages for the prompt."""
        formatted = []
        for i, msg in enumerate(messages, 1):
            date = msg.get('date', 'N/A')
            text = msg.get('text', '')
            views = msg.get('views', 0)
            message_id = msg.get('message_id', '')
            channel_username = msg.get('channel_username', '')

            # Truncate very long messages
            if len(text) > 2000:
                text = text[:2000] + "..."

            # Create message link if available
            link_text = ""
            if include_links and message_id and channel_username:
                # Clean channel_username from any prefixes/domains
                clean_username = channel_username.replace('https://t.me/', '').replace('http://t.me/', '').replace('@', '').strip('/')
                link = f"https://t.me/{clean_username}/{message_id}"
                link_text = f" [ссылка]({link})"

            formatted.append(f"{i}. [{date}] (👁 {views} просмотров){link_text}\n{text}")

        return "\n\n".join(formatted)

    def _add_message_links(self, summary: str, messages: List[Dict[str, str]], channel_name: str) -> str:
        """Add links to original messages at the end of summary."""
        if not messages:
            return summary

        # Sort messages by views (most viewed first)
        sorted_messages = sorted(messages, key=lambda x: x.get('views', 0), reverse=True)

        # Take top 5 most viewed messages
        top_messages = sorted_messages[:5]

        # Build links section
        links_section = "\n\n📎 <b>Ссылки на посты:</b>\n"
        for msg in top_messages:
            message_id = msg.get('message_id')
            channel_username = msg.get('channel_username')
            views = msg.get('views', 0)
            date = msg.get('date', 'N/A')

            if message_id and channel_username:
                # Clean channel_username from any prefixes/domains
                clean_username = channel_username.replace('https://t.me/', '').replace('http://t.me/', '').replace('@', '').strip('/')
                link = f"https://t.me/{clean_username}/{message_id}"

                # Get preview of message (first 100 chars)
                text_preview = msg.get('text', '')[:100]
                # Escape HTML in preview
                text_preview = text_preview.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                if len(msg.get('text', '')) > 100:
                    text_preview += "..."

                links_section += f"• [{date}] <a href='{link}'>{text_preview}</a> (👁 {views})\n"

        # Add links section to summary if we have any links
        if len(top_messages) > 0 and top_messages[0].get('message_id'):
            return summary + links_section
        else:
            return summary
