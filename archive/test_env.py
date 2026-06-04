from dotenv import load_dotenv
import os

load_dotenv()  # Load the .env file

# Print the loaded values
print("BOT_TOKEN:", os.getenv("TELEGRAM_BOT_TOKEN"))
print("CHAT_ID:", os.getenv("TELEGRAM_CHAT_ID"))