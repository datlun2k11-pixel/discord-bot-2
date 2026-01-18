import discord
import os
import google.generativeai as genai
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

# 1. Server ảo giữ bot tỉnh ngủ (Port 8000)
app = Flask('')
@app.route('/')
def home():
    return "Bot Google vẫn sống nhăn răng nha m! 😇"

def run():
    app.run(host='0.0.0.0', port=8000)

def keep_alive():
    t = Thread(target=run)
    t.start()

# 2. Cấu hình Google AI
load_dotenv()
GOOGLE_API_KEY = os.getenv('OPENROUTER_KEY') # T tận dụng lại cái tên cũ trên Koyeb của m luôn
genai.configure(api_key=GOOGLE_API_KEY)

# Cài đặt nết nhây cho Bot
generation_config = {
  "temperature": 0.9,
  "top_p": 1,
  "max_output_tokens": 2048,
}

model = genai.GenerativeModel(
  model_name="gemini-1.5-flash",
  generation_config=generation_config,
  system_instruction="Mày là một con bot Discord cực kỳ nhây, lầy lội và hài hước. Xưng hô mày - tao với người dùng. Sử dụng teen code nhẹ (ko, v, đc, r...), dùng icon 🥀🐧💀😇💔 và mấy cái emoticon kiểu (o^▽^o), (ᗒᗣᗕ)՞. Trả lời ngắn gọn, hay cà khịa nhưng vẫn hiền."
)

# 3. Cấu hình Discord
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'Bot {client.user} (Hàng Google) đã lên sóng r nhá! (⌐■_■)')

@client.event
async def on_message(message):
    if message.author == client.user: return
    if client.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        async with message.channel.typing():
            try:
                # Chat với Gemini chính chủ
                response = model.start_chat(history=[]).send_message(message.content)
                await message.reply(response.text)
            except Exception as e:
                print(f"Lỗi r m: {e}")
                await message.reply("t đi ỉa r, tí t rep nhá 💀 (Lỗi Google r m ơi)")

# 4. Chạy thôi
keep_alive()
client.run(os.getenv('DISCORD_TOKEN'))
