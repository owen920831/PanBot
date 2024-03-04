from urllib import response
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import requests
from bs4 import BeautifulSoup
import googlemaps
import datetime
import pytz
from gradio_client import Client
import tempfile
import google.generativeai as genai
import PIL.Image
import re
import nltk
from nltk.tokenize import sent_tokenize

# 下载需要的 NLTK 数据
nltk.download('punkt')
# 定义状态

class TelegramBot:
    def __init__(self, gemma_api_key, token, user_id, google_api_key, huggingface_token, openweathermap_api_key,):
        self.gemma_api_key = gemma_api_key
        self.token = token
        self.user_id = user_id
        self.openweathermap_api_key = openweathermap_api_key
        self.google_api_key = google_api_key
        self.huggingface_token = huggingface_token

        # Initialize the updater and dispatcher
        self.updater = Updater(self.token)
        self.dispatcher = self.updater.dispatcher
        # Initialize other attributes
        self.user_location = None
        self.gmaps = googlemaps.Client(key=self.google_api_key)
        self.tz = pytz.timezone('Asia/Taipei')
        genai.configure(api_key=gemma_api_key, )
        self.text_model = genai.GenerativeModel(model_name="gemini-pro")
        self.img_model = genai.GenerativeModel('gemini-pro-vision')
        self.text_client = self.text_model.start_chat(history=[])
        self.whisper_client = Client("https://sanchit-gandhi-whisper-jax.hf.space/")
        
        self.CHOOSING = 1
        
        # Initialize JobQueue
        self.job_queue = self.updater.job_queue

        # Setup commands and webhook
        self.setup_commands()
        self.setup_webhook()

    def setup_commands(self):
        self.dispatcher.add_handler(CommandHandler('start', self.start))
        self.dispatcher.add_handler(CommandHandler('novel', self.novel_updated))
        self.job_queue.run_daily(self.morning_greeting, datetime.time(7, 0, 0, tzinfo=self.tz))
        self.job_queue.run_daily(self.night_greeting, datetime.time(23, 0, 0, tzinfo=self.tz))
        self.dispatcher.add_handler(CommandHandler('restaurants', self.top5restaurants, pass_args=True))
        self.dispatcher.add_handler(MessageHandler(Filters.location, self.get_user_location))
        self.dispatcher.add_handler(CommandHandler('weather', self.weather))
        self.dispatcher.add_handler(CommandHandler('help', self.help))
        self.dispatcher.add_handler(MessageHandler(Filters.text & (~Filters.command), self.respond))
        self.dispatcher.add_handler(MessageHandler(Filters.photo & (~Filters.command), self.handle_image))
        self.dispatcher.add_handler(MessageHandler(Filters.voice, self.handle_audio_message))


    def start(self, update, context):
        context.bot.send_message(chat_id=update.message.from_user.id, text=f"Hello! use /help to see the available commands.")

    def handle_audio_message(self, update, context):
        update.message.reply_text('Translating audio...')
        voice = update.message.voice
        file = voice.get_file()

        # 创建一个临时文件
        with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as temp_file:
            temp_path = temp_file.name

            # 下载文件到临时文件
            file.download(temp_path)

            # 调用 transcribe_audio 函数进行转录
            text = self.trans_audio(temp_path, task="translate")

        # 回复用户
        update.message.reply_text(f'Translation: {text}')

        # 临时文件会在这里被自动删除
            

    def trans_audio(self, audio, task="transcribe", return_timestamps=False):
        """Function to transcribe an audio file using our endpoint"""
        text, runtime = self.whisper_client.predict(
            audio,
            task,
            return_timestamps,
            api_name="/predict_1",
        )
        return text


    def novel_updated(self, update, context):
        try:
            response = requests.get("https://m.zongheng.com/book?bookId=672340")
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            update_div = soup.find('div', class_='de-update-chapter flex')

            if update_div:
                chapter_title = update_div.a['title']
                update_time = update_div.find('span', class_='time JupdateTime').text.strip()
                print(chapter_title, update_time)
                update.message.reply_text(f"最新章節：{chapter_title}\n更新時間：{update_time}")

            else:
                update.message.reply_text("沒有找到更新信息")

        except Exception as e:
            update.message.reply_text(f"出錯了：{e}")

    def morning_greeting(self, context):
        text = "早安, 現在是台灣時間 " + datetime.datetime.now(pytz.timezone('Asia/Taipei')).strftime("%H:%M") + "☀️"
        context.bot.send_message(chat_id=self.user_id, text=text)

    def night_greeting(self, context):
        text = "晚安, 現在是台灣時間 " + datetime.datetime.now(pytz.timezone('Asia/Taipei')).strftime("%H:%M") + "🌙"
        context.bot.send_message(chat_id=self.user_id, text=text)

    def top5restaurants(self, update, context):
        user_id = update.message.from_user.id
        print("location address", self.current_address(self.user_location))
        num_restaurants = int(context.args[0]) if context.args else 5
        # Check if the user has shared their location
        if self.user_location:
            location = self.user_location
            print("location", location)
            # Get nearby places
            places_result = self.gmaps.places_nearby(
                location=(location.latitude, location.longitude),
                radius=1000,  # You can adjust the radius as needed
                type='restaurant'
            )

            # Display top num_restaurants places and their ratings
            if places_result.get('results'):
                places = places_result['results'][:num_restaurants]
                message = f"Top {num_restaurants} Restaurants Nearby:\n"
                for place in places:
                    name = place['name']
                    rating = place.get('rating', 'N/A')
                    message += f"{name}, Rating: {rating}\n"
            else:
                message = "No restaurants found nearby."

            context.bot.send_message(chat_id=user_id, text=message)
        else:
            context.bot.send_message(chat_id=user_id, text="Please share your location using the 'Location' option.")

    def get_user_location(self, update, context):
        user_id = update.message.from_user.id
        self.user_location = update.message.location
        print("user_location", self.user_location)
        context.bot.send_message(chat_id=user_id, text=f"你的位置：{self.current_address(self.user_location)}")

    def current_address(self, location):
        # Reverse geocode an address
        reverse_geocode_result = self.gmaps.reverse_geocode((location.latitude, location.longitude))

        # Filter out the postal code if it exists
        formatted_address = reverse_geocode_result[0]['formatted_address']
        components = reverse_geocode_result[0]['address_components']

        # Check if 'postal_code' is in the types of any address component
        for component in components:
            if 'postal_code' in component['types']:
                formatted_address = formatted_address.replace(component['long_name'], '').strip()

        return formatted_address

    def weather(self, update, context) -> None:
        user_id = update.message.from_user.id

        # Check if the message contains a location
        if self.user_location:
            location = self.user_location
            context.bot.send_message(chat_id=user_id, text=f"你的位置：{self.current_address(location)}")

            # Get current weather information from OpenWeatherMap API
            url_current = f"http://api.openweathermap.org/data/2.5/weather?lat={location.latitude}&lon={location.longitude}&appid={self.openweathermap_api_key}&units=metric"
            response_current = requests.get(url_current)
            data_current = response_current.json()

            # Display current weather information
            if data_current.get('main') and data_current.get('weather'):
                temperature_current = data_current['main']['temp']
                rain_probability_current = data_current.get('pop', 0)

                message_current = f"Current Weather:\nTemperature: {temperature_current} °C\n Rain Probability: {rain_probability_current}%"
            else:
                message_current = "Failed to fetch current weather information."

            context.bot.send_message(chat_id=user_id, text=message_current)

            # Fetch today's hourly forecast
            url_hourly = f"http://api.openweathermap.org/data/2.5/forecast?lat={location.latitude}&lon={location.longitude}&appid={self.openweathermap_api_key}&units=metric"
            response_hourly = requests.get(url_hourly)
            data_hourly = response_hourly.json()

            if data_hourly.get('list'):
                hourly_forecast = data_hourly['list']

                # Filter hourly forecast for today
                today_forecast = [entry for entry in hourly_forecast if
                                  entry['dt_txt'].startswith(datetime.datetime.now(self.tz).strftime("%Y-%m-%d"))]

                # Create a message with today's hourly forecast
                if today_forecast:
                    message_hourly = "Today's Hourly Forecast:\n"
                    for entry in today_forecast:
                        time = entry['dt_txt'].split()[1]  # Extract time from dt_txt
                        temperature = entry['main']['temp']
                        rain_probability = entry.get('pop', 0)
                        message_hourly += f"{time}: Temperature: {temperature} °C, Rain Probability: {rain_probability}%\n"

                    # Send the hourly forecast message to the user
                    context.bot.send_message(chat_id=user_id, text=message_hourly)
                else:
                    context.bot.send_message(chat_id=user_id, text="No hourly forecast data available for today.")
        else:
            context.bot.send_message(chat_id=user_id,
                                      text="Please share your location using the 'Location' option before using the /weather command.")

    def help(self, update, context):
        update.message.reply_text("""
        The following commands are available:
            
        /start -> Welcome Message
        /help -> This Message
        /novel -> Check if novel updated
        /weather -> Get current weather information and hourly forecast
        /restaurants + num(defalut 5) -> Get top num restaurants nearby
            """)

    def respond(self, update, context):
        user_input = update.message.text
        response_buffer = ""  # Holds accumulated response chunks

        for chunk in self.text_client.send_message(user_input, stream=True):
            response_buffer += chunk.text

            # Split buffer on sentence boundaries (implement sentence detection logic)
            sentences = self.split_into_sentences(response_buffer)
            for sentence in sentences:
                update.message.reply_text(sentence)

            # Clear buffer after sending sentences
            response_buffer = response_buffer[len(sentence):]  # Keep any remaining text


    def split_into_sentences(self, text):
        # 使用 NLTK 的 sent_tokenize 函数进行句子分割
        sentences = sent_tokenize(text)
        return sentences


    def handle_image(self, update, context):
        photo = update.message.photo[-1]
        photo_file = photo.get_file()
            # 创建一个临时文件
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as temp_file:
            temp_path = temp_file.name

            # 下载文件到临时文件
            photo_file.download(temp_path)
            image = PIL.Image.open(temp_path)
        
            if (update.message.caption) is None:
                caption = ""
            else:
                caption = update.message.caption
            print(caption)
            self.respond_image(update, caption, image)

    def respond_image(self, update, caption, photo_file):
        response = self.img_model.generate_content([caption, photo_file], stream=True)
        response_buffer = ""  # Holds accumulated response chunks
        for chunk in response:
            response_buffer += chunk.text

            # Split buffer on sentence boundaries (implement sentence detection logic)
            sentences = self.split_into_sentences(response_buffer)
            for sentence in sentences:
                update.message.reply_text(sentence)

            # Clear buffer after sending sentences
            response_buffer = response_buffer[len(sentence):]  # Keep any remaining text
    
    def setup_webhook(self):
        self.updater.bot.setWebhook(url="https://trianglesnake.nckuctf.org/owen/{}".format(self.token))
        self.updater.start_webhook( listen='127.0.0.1',
                                    port=5000,
                                    url_path=self.token)
