"""Telegram client for reading channel messages using Telethon."""
from telethon import TelegramClient
from telethon.tl.types import Channel
from telethon.errors import (
    ChannelPrivateError, ChannelInvalidError,
    UsernameInvalidError, UsernameNotOccupiedError
)
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import config


class ChannelReader:
    """Read messages from Telegram channels using user account."""

    def __init__(self):
        self.client = None
        self.api_id = int(config.API_ID)
        self.api_hash = config.API_HASH
        self.session_name = config.SESSION_NAME

    async def start(self):
        """Start the Telegram client."""
        if not self.client:
            self.client = TelegramClient(
                self.session_name,
                self.api_id,
                self.api_hash
            )
            await self.client.start()

    async def stop(self):
        """Stop the Telegram client."""
        if self.client:
            await self.client.disconnect()

    async def get_channel_info(self, channel_username: str) -> Optional[Tuple[int, str]]:
        """
        Get channel ID and title.

        Args:
            channel_username: Channel username (with or without @)

        Returns:
            Tuple of (channel_id, channel_title) or None if not found
        """
        try:
            channel_username = channel_username.lstrip('@')
            entity = await self.client.get_entity(channel_username)

            if isinstance(entity, Channel):
                return (entity.id, entity.title)
            else:
                return None

        except (ChannelPrivateError, ChannelInvalidError,
                UsernameInvalidError, UsernameNotOccupiedError):
            return None
        except Exception as e:
            print(f"Error getting channel info for {channel_username}: {e}")
            return None

    async def read_channel_messages(
        self,
        channel_username: str,
        days: int = 1,
        limit: int = 100
    ) -> Tuple[bool, str, List[Dict[str, str]]]:
        """
        Read messages from a channel for the specified period.

        Args:
            channel_username: Channel username (with or without @)
            days: Number of days to look back
            limit: Maximum number of messages to retrieve

        Returns:
            Tuple of (success, error_message, messages_list)
            messages_list contains dicts with 'date', 'text', 'views' keys
        """
        try:
            channel_username = channel_username.lstrip('@')
            entity = await self.client.get_entity(channel_username)

            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            # Fetch messages
            messages = []
            async for message in self.client.iter_messages(
                entity,
                offset_date=end_date,
                limit=limit
            ):
                # Check if message is within date range
                if message.date < start_date:
                    break

                # Skip messages without text
                if not message.text:
                    continue

                messages.append({
                    'date': message.date.strftime('%Y-%m-%d %H:%M'),
                    'text': message.text,
                    'views': message.views or 0,
                    'message_id': message.id,
                })

            return (True, "", messages)

        except ChannelPrivateError:
            return (False, "❌ Канал приватный. Убедитесь, что вы подписаны на него.", [])

        except (ChannelInvalidError, UsernameInvalidError, UsernameNotOccupiedError):
            return (False, "❌ Канал не найден. Проверьте правильность username.", [])

        except Exception as e:
            return (False, f"❌ Ошибка при чтении канала: {str(e)}", [])

    async def read_multiple_channels(
        self,
        channel_usernames: List[str],
        days: int = 1
    ) -> Dict[str, List[Dict[str, str]]]:
        """
        Read messages from multiple channels.

        Args:
            channel_usernames: List of channel usernames
            days: Number of days to look back

        Returns:
            Dict mapping channel names to their message lists
        """
        results = {}

        for channel_username in channel_usernames:
            success, error, messages = await self.read_channel_messages(
                channel_username,
                days=days
            )

            if success:
                results[channel_username] = messages
            else:
                # Store error as a special message
                results[channel_username] = []
                print(f"Error reading {channel_username}: {error}")

        return results

    async def check_channel_access(self, channel_username: str) -> Tuple[bool, str]:
        """
        Check if we can access a channel.

        Args:
            channel_username: Channel username

        Returns:
            Tuple of (can_access, message)
        """
        try:
            channel_username = channel_username.lstrip('@')
            entity = await self.client.get_entity(channel_username)

            if not isinstance(entity, Channel):
                return (False, "❌ Это не канал.")

            # Try to fetch one message to verify access
            async for _ in self.client.iter_messages(entity, limit=1):
                break

            return (True, f"✅ Доступ к каналу @{channel_username} подтвержден.")

        except ChannelPrivateError:
            return (False, f"❌ Канал @{channel_username} приватный и недоступен. Подпишитесь на него через свой аккаунт Telegram.")

        except (ChannelInvalidError, UsernameInvalidError, UsernameNotOccupiedError):
            return (False, f"❌ Канал @{channel_username} не найден.")

        except Exception as e:
            return (False, f"❌ Ошибка проверки доступа: {str(e)}")
