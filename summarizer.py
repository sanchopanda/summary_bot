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
            response.raise_for_status()

            result = response.json()
            summary = result['choices'][0]['message']['content']
            return summary.strip()

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
            if messages:
                summary = self.generate_summary(messages, channel_name)
                summaries.append(f"📢 **{channel_name}**\n\n{summary}")
            else:
                summaries.append(f"📢 **{channel_name}**\n\nНет новых сообщений.")

        return "\n\n" + "─" * 50 + "\n\n".join(summaries)

    def _format_messages(self, messages: List[Dict[str, str]]) -> str:
        """Format messages for the prompt."""
        formatted = []
        for i, msg in enumerate(messages, 1):
            date = msg.get('date', 'N/A')
            text = msg.get('text', '')
            views = msg.get('views', 0)

            # Truncate very long messages
            if len(text) > 500:
                text = text[:500] + "..."

            formatted.append(f"{i}. [{date}] (👁 {views} просмотров)\n{text}")

        return "\n\n".join(formatted)
