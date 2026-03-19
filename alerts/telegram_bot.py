"""
Telegram Bot
Send trading alerts via Telegram with rich formatting.
"""

import requests
from typing import Dict
from datetime import datetime
from core.config import Config
from utils.logger import setup_logger
from .formatter import AlertFormatter

logger = setup_logger('TelegramBot')


class TelegramBot:
    """
    Send trading alerts to Telegram using Bot API.
    
    Requires:
    - TELEGRAM_BOT_TOKEN in .env
    - TELEGRAM_CHAT_ID in .env
    """
    
    def __init__(self, token: str = None, chat_id: str = None):
        """
        Initialize Telegram bot
        
        Args:
            token: Telegram bot token (default: from config)
            chat_id: Telegram chat ID (default: from config)
        """
        self.token = token or Config.TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or Config.TELEGRAM_CHAT_ID
        
        if not self.token or not self.chat_id:
            logger.error("Telegram credentials not configured!")
            logger.error("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env file")
            self.enabled = False
        else:
            self.enabled = True
            logger.info("Telegram bot initialized")
    
    def send_message(self, message: str, parse_mode: str = 'Markdown') -> bool:
        """
        Send a message to Telegram
        
        Args:
            message: Message text (supports Markdown formatting)
            parse_mode: Parse mode ('Markdown' or 'HTML')
        
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.enabled:
            logger.warning("Telegram bot not enabled. Check credentials.")
            return False
        
        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            
            payload = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': parse_mode,
                'disable_web_page_preview': True
            }
            
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                logger.info("✅ Telegram message sent successfully")
                return True
            else:
                logger.error(f"❌ Telegram API error: {response.status_code} - {response.text}")
                return False
                
        except requests.exceptions.Timeout:
            logger.error("❌ Telegram request timeout")
            return False
        except Exception as e:
            logger.error(f"❌ Error sending Telegram message: {e}")
            return False
    
    def send_alert(self, alert_data: Dict) -> bool:
        """
        Send formatted trading alert
        
        Args:
            alert_data: Dictionary with alert information
                       {symbol, signal, timeframe, confidence, price, etc.}
        
        Returns:
            True if sent successfully
        """
        if not self.enabled:
            return False
        
        try:
            message = self._format_alert_message(alert_data)
            return self.send_message(message)
            
        except Exception as e:
            logger.error(f"Error sending alert: {e}")
            return False
    
    def _format_alert_message(self, alert_data: Dict) -> str:
        """
        Format alert data into Telegram message
        
        Args:
            alert_data: Alert dictionary
        
        Returns:
            Formatted message string
        """
        formatter = AlertFormatter.format_signal_alert if Config.VERBOSE_ALERTS else AlertFormatter.format_compact_alert
        return formatter(alert_data)
    
    def send_test_message(self) -> bool:
        """
        Send a test message to verify Telegram setup
        
        Returns:
            True if successful
        """
        test_message = f"""
🤖 *OptiCore Trading Bot - Test Message*

✅ Telegram connection successful!

Bot is ready to send trading alerts.

🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        return self.send_message(test_message.strip())
    
    def send_startup_notification(self) -> bool:
        """
        Send bot startup notification
        
        Returns:
            True if successful
        """
        message = AlertFormatter.format_startup_message()
        return self.send_message(message)
    
    def send_error_notification(self, error_message: str) -> bool:
        """
        Send error notification
        
        Args:
            error_message: Error description
        
        Returns:
            True if successful
        """
        message = AlertFormatter.format_error(error_message)
        return self.send_message(message)
    
    def send_summary(self, summary_data: Dict) -> bool:
        """
        Send daily/periodic summary
        
        Args:
            summary_data: Summary statistics
        
        Returns:
            True if successful
        """
        message = AlertFormatter.format_summary(summary_data)
        return self.send_message(message)
    
    def send_to_observation_channel(self, message: str, parse_mode: str = 'HTML') -> bool:
        """
        Send message to observation/debug channel
        
        Args:
            message: Message text
            parse_mode: Parse mode ('HTML' or 'Markdown')
        
        Returns:
            True if sent successfully, False otherwise
        """
        obs_channel_id = getattr(Config, 'OBSERVATION_CHANNEL_ID', None)
        
        if not obs_channel_id:
            logger.debug("Observation channel not configured, skipping")
            return False
        
        if not self.enabled:
            logger.warning("Telegram bot not enabled")
            return False
        
        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            
            payload = {
                'chat_id': obs_channel_id,
                'text': message,
                'parse_mode': parse_mode,
                'disable_web_page_preview': True
            }
            
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                logger.info("OK - Observation channel sent")
                return True
            else:
                logger.error(f"Observation channel error: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send to observation channel: {e}")
            return False
