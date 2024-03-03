from telegrambot import TelegramBot

with open("assets/gem.txt", "r") as f:
    gemma_api_key = f.read()

with open("assets/telegram_token.txt", "r") as f:
    telegram_bot_token = f.read()

with open("assets/user_id.txt", "r") as f:
    user_id = int(f.read())

with open("assets/google_maps_api.txt", "r") as f:
    google_api_key = f.read()

with open("assets/huggingface_token.txt", "r") as f:
    huggingface_token = f.read()

with open("assets/OPENWEATHERMAP_API_KEY.txt", "r") as f:
    openweathermap_api_key = f.read()
    
with open("assets/hackmd_api.txt", "r") as f:
    hackmd_api = f.read()

if __name__ == "__main__":
    telegram_bot = TelegramBot(gemma_api_key, telegram_bot_token, user_id, google_api_key, huggingface_token, openweathermap_api_key)
    telegram_bot.updater.idle()
    