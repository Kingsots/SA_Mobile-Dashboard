#!/bin/bash
# Test Telegram API connectivity and token validity

# Load .env (clean CRLF) - source directly without subshell
if [ -f /home/ubuntu/SilentAnalyst/.env ]; then
  eval "$(sed -e 's/\r$//' /home/ubuntu/SilentAnalyst/.env | grep -E '^(TELEGRAM|FINNHUB|ALPHA|TWELVE)' | sed 's/^/export /')"
fi

if [ -z "$TELEGRAM_BOT_TOKEN" ] || [ -z "$TELEGRAM_CHAT_ID" ]; then
  echo "ERROR: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set"
  echo "  TELEGRAM_BOT_TOKEN='$TELEGRAM_BOT_TOKEN'"
  echo "  TELEGRAM_CHAT_ID='$TELEGRAM_CHAT_ID'"
  exit 1
fi

echo "Testing Telegram API:"
echo "  Token (first 10 chars): ${TELEGRAM_BOT_TOKEN:0:10}..."
echo "  Chat ID: $TELEGRAM_CHAT_ID"
echo ""
echo "Sending test message..."

response=$(curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "chat_id=${TELEGRAM_CHAT_ID}&text=Test from EC2 at $(date -u +%Y-%m-%d\ %H:%M:%S\ UTC)")

echo "Response:"
echo "$response"

if echo "$response" | grep -q '"ok":true'; then
  echo ""
  echo "✅ Telegram API test PASSED - message sent successfully"
  exit 0
else
  echo ""
  echo "❌ Telegram API test FAILED"
  exit 1
fi
