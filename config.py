import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "8225457730:AAEM9tw99r3mx5X2Of0iiUHqyxQUo6gDtQM")
ADMIN_ID = int(os.getenv("ADMIN_ID", "6239727148"))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
