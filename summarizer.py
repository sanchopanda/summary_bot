"""OpenRouter API integration for generating summaries."""
import re
import requests
import logging
import time
from typing import List, Dict, Optional
from config import OPENROUTER_API_KEY, OPENROUTER_MODEL


logger = logging.getLogger(__name__)


class Summarizer:
    """Generate summaries of channel messages using OpenRouter API."""

    def __init__(self):
        self.api_key = OPENROUTER_API_KEY
        self.model = OPENROUTER_MODEL
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"

    def generate_summary(self, messages: List[Dict[str, str]], channel_name: str, user_id: Optional[int] = None) -> str:
        """
        Generate a summary of messages from a channel.

        Args:
            messages: List of dicts with 'date', 'text', 'views' keys
            channel_name: Name of the channel
            user_id: Optional user ID for logging

        Returns:
            Generated summary text
        """
        if not messages:
            logger.info(f"No messages for channel {channel_name}")
            return f"Нет новых сообщений в канале {channel_name}."

        logger.info(f"Generating summary for channel {channel_name}: {len(messages)} messages" + (f" (user_id: {user_id})" if user_id else ""))

        # Use hierarchical selection to pick the most interesting posts
        # This handles any number of messages by recursively selecting top posts
        selected_messages = self._hierarchical_selection(messages, channel_name)
        logger.info(f"Hierarchical selection completed: {len(selected_messages)} posts selected for final summary")

        # Prepare messages text (with links for LLM to use)
        messages_text = self._format_messages(selected_messages, include_links=True)

        # Create prompt for LLM
        prompt = f"""Создай краткое саммари (summary) для самых интересных постов из Telegram канала "{channel_name}".
Все представленные ниже посты уже отобраны как наиболее важные.

Сообщения за период (каждое сообщение имеет [ССЫЛКА НА ПОСТ: URL]):
{messages_text}

⚠️ КРИТИЧЕСКИ ВАЖНО!
- Для КАЖДОГО поста в саммари ОБЯЗАТЕЛЬНО добавь HTML-ссылку в конце описания
- Используй ТОЛЬКО HTML формат: <a href='URL'>Ссылка на пост</a>
- НЕ используй Markdown формат [текст](url) - это ЗАПРЕЩЕНО!

ФОРМАТ (строго соблюдай):
Номер. Краткое описание поста <a href='URL_ПОСТА'>Ссылка на пост</a>

ПРИМЕРЫ правильного вывода с HTML-ссылками:
1. Компания X привлекла $100 млн инвестиций при оценке $500 млн <a href='https://t.me/channel/123'>Ссылка на пост</a>
2. Если бы дистрибутивы были автомобилями - интересное сравнение дистрибутивов Linux <a href='https://t.me/linuxos_tg/569'>Ссылка на пост</a>
3. Минцифры обновило список сайтов, которые будут работать при отключениях мобильного интернета <a href='https://t.me/vcnews/58098'>Ссылка на пост</a>
4. Стоимость биткоина опустилась ниже $95 тысяч впервые с мая 2025 года <a href='https://t.me/vcnews/58096'>Ссылка на пост</a>

НЕПРАВИЛЬНЫЙ формат (НЕ ДЕЛАЙ ТАК):
❌ 1. Текст поста [Ссылка на пост](https://t.me/channel/123)
❌ 2. Текст поста (https://t.me/channel/456)

ПРАВИЛЬНЫЙ формат (ДЕЛАЙ ТОЛЬКО ТАК):
✅ 1. Текст поста <a href='https://t.me/channel/123'>Ссылка на пост</a>

Требования:
1. Используй нумерованный список (1. 2. 3. и т.д.)
2. КАЖДАЯ строка должна заканчиваться на <a href='URL'>Ссылка на пост</a>
3. Указывай конкретные факты, цифры, даты
4. Пиши кратко и по существу
5. Группируй похожие темы вместе

Саммари:"""

        try:
            start_time = time.time()
            logger.info(f"Sending request to OpenRouter API: model={self.model}, channel={channel_name}")
            logger.info(f"OpenRouter prompt for {channel_name}:\n{'-'*80}\n{prompt}\n{'-'*80}")

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
                    "temperature": 0.7,
                },
                timeout=120  # 2 minutes for longer responses without token limit
            )

            elapsed_time = time.time() - start_time

            # Log response details
            if response.status_code != 200:
                logger.error(f"OpenRouter API Error: Status {response.status_code}, Response: {response.text}")

            response.raise_for_status()

            result = response.json()
            summary = result['choices'][0]['message']['content']

            # Log API usage
            usage = result.get('usage', {})
            prompt_tokens = usage.get('prompt_tokens', 0)
            completion_tokens = usage.get('completion_tokens', 0)
            total_tokens = usage.get('total_tokens', 0)

            logger.info(f"OpenRouter API success: channel={channel_name}, "
                       f"tokens={prompt_tokens}/{completion_tokens} (total: {total_tokens}), "
                       f"time={elapsed_time:.2f}s")
            logger.info(f"OpenRouter response for {channel_name}:\n{'-'*80}\n{summary}\n{'-'*80}")

            # Links are now added by LLM in the summary itself
            return summary.strip()

        except requests.exceptions.RequestException as e:
            logger.error(f"OpenRouter API request failed for channel {channel_name}: {str(e)}", exc_info=True)
            return f"❌ Ошибка при генерации саммари для {channel_name}: {str(e)}"

    def generate_multi_channel_summary(self, channels_messages: Dict[str, List[Dict[str, str]]], user_id: Optional[int] = None) -> str:
        """
        Generate a combined summary for multiple channels.

        Args:
            channels_messages: Dict mapping channel names to their message lists
            user_id: Optional user ID for logging

        Returns:
            Combined summary text
        """
        if not channels_messages:
            logger.info(f"No messages in any channels" + (f" (user_id: {user_id})" if user_id else ""))
            return "Нет новых сообщений ни в одном из отслеживаемых каналов."

        channel_list = list(channels_messages.keys())
        total_messages = sum(len(msgs) for msgs in channels_messages.values())
        logger.info(f"Generating multi-channel summary: {len(channel_list)} channels, {total_messages} total messages" +
                   (f" (user_id: {user_id})" if user_id else ""))
        logger.info(f"Channels: {', '.join(channel_list)}")

        summaries = []
        for channel_name, messages in channels_messages.items():
            # Escape HTML in channel name
            safe_channel_name = channel_name.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            if messages:
                summary = self.generate_summary(messages, channel_name, user_id=user_id)
                summaries.append(f"📢 <b>{safe_channel_name}</b>\n\n{summary}")
            else:
                summaries.append(f"📢 <b>{safe_channel_name}</b>\n\nНет новых сообщений.")

        return ("\n\n" + "─" * 50 + "\n\n").join(summaries)

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
                link_text = f"\n[ССЫЛКА НА ПОСТ: {link}]"

            formatted.append(f"{i}. [{date}] (👁 {views} просмотров)\n{text}{link_text}")

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

    def _select_top_posts(self, messages: List[Dict[str, str]], channel_name: str, max_count: int = 10) -> List[Dict[str, str]]:
        """
        Use LLM to select the most interesting posts from the given messages.

        Args:
            messages: List of message dicts
            channel_name: Name of the channel
            max_count: Maximum number of posts to select

        Returns:
            List of selected message dicts (with all metadata preserved)
        """
        if len(messages) <= max_count:
            return messages

        logger.info(f"Selecting top {max_count} posts from {len(messages)} messages for {channel_name}")

        # Format messages for LLM
        messages_text = self._format_messages(messages, include_links=False)

        # Prompt for selection
        prompt = f"""Проанализируй {len(messages)} сообщений из Telegram канала "{channel_name}".
Выбери {max_count} САМЫХ ИНТЕРЕСНЫХ и важных постов.

Сообщения:
{messages_text}

ВАЖНО: Верни ТОЛЬКО список номеров выбранных постов через запятую (например: 1, 5, 7, 12, 15, 18, 22, 25, 28, 30).
НЕ пиши никакого дополнительного текста, ТОЛЬКО номера через запятую.

Номера выбранных постов:"""

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
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,  # Lower temperature for more focused selection
                },
                timeout=60
            )

            response.raise_for_status()
            result = response.json()
            selection_text = result['choices'][0]['message']['content'].strip()

            logger.info(f"LLM selection response: {selection_text}")

            # Parse numbers from response
            numbers = re.findall(r'\d+', selection_text)
            selected_indices = [int(n) - 1 for n in numbers if 1 <= int(n) <= len(messages)][:max_count]

            if not selected_indices:
                logger.warning(f"Failed to parse selection, using first {max_count} messages")
                selected_indices = list(range(min(max_count, len(messages))))

            # Extract selected messages (preserving all metadata)
            selected_messages = [messages[i] for i in selected_indices if i < len(messages)]
            logger.info(f"Selected {len(selected_messages)} posts from {len(messages)}")

            return selected_messages

        except Exception as e:
            logger.error(f"Error in post selection: {e}", exc_info=True)
            # Fallback: return first max_count messages
            return messages[:max_count]

    def _hierarchical_selection(self, messages: List[Dict[str, str]], channel_name: str, depth: int = 0) -> List[Dict[str, str]]:
        """
        Recursively select the most interesting posts using hierarchical approach.

        Args:
            messages: List of message dicts
            channel_name: Name of the channel
            depth: Current recursion depth (for logging)

        Returns:
            List of selected message dicts (up to 10 most interesting)
        """
        indent = "  " * depth
        logger.info(f"{indent}Hierarchical selection: {len(messages)} messages at depth {depth}")

        # Base case: if messages <= 30, select top 10 directly
        if len(messages) <= 30:
            logger.info(f"{indent}Base case reached: selecting final top 10 from {len(messages)} messages")
            return self._select_top_posts(messages, channel_name, max_count=10)

        # Recursive case: split into chunks and select from each
        chunk_size = 30
        chunks = [messages[i:i + chunk_size] for i in range(0, len(messages), chunk_size)]
        logger.info(f"{indent}Splitting {len(messages)} messages into {len(chunks)} chunks of ~{chunk_size}")

        # Select top 10 from each chunk
        selected_from_chunks = []
        for i, chunk in enumerate(chunks, 1):
            logger.info(f"{indent}Processing chunk {i}/{len(chunks)} ({len(chunk)} messages)")
            selected = self._select_top_posts(chunk, channel_name, max_count=10)
            selected_from_chunks.extend(selected)
            logger.info(f"{indent}Chunk {i}: selected {len(selected)} posts")

        logger.info(f"{indent}Total selected from all chunks: {len(selected_from_chunks)} posts")

        # Recursively process the collected posts
        return self._hierarchical_selection(selected_from_chunks, channel_name, depth + 1)
