import discord
import requests
import os
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

# 1. Server ảo để "thông cống" cho Koyeb (mở port 8000)
app = Flask('')

@app.route('/')
def home():
    return "Bot vẫn sống nhăn răng nha m! 😇"

def run():
    # Koyeb nó soi cổng 8000 dữ lắm nên phải để đúng port này
    app.run(host='0.0.0.0', port=8000)

def keep_alive():
    t = Thread(target=run)
    t.start()

# 2. Setup cấu hình và biến môi trường
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
OPENROUTER_KEY = os.getenv('OPENROUTER_KEY')

# Model dự phòng nếu DeepSeek bị táo bón: 
# "google/gemini-2.0-flash-exp:free" hoặc "meta-llama/llama-3.1-8b-instruct:free"
MODEL_NAME = "google/gemini-2.0-flash-exp:free" 

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'Bot {client.user} đã lên sóng r nhá! (⌐■_■)')

@client.event
async def on_message(message):
    # Ko tự rep chính mình
    if message.author == client.user: return

    # Chỉ rep khi bị tag hoặc nhắn tin riêng (DM)
    if client.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        async with message.channel.typing():
            try:
                res = requests.post(
                    url="https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {OPENROUTER_KEY}"},
                    json={
                        "model": MODEL_NAME,
                        "messages": [
                            {
                                "role": "system", 
                                "content": "Mày là một con bot Discord cực kỳ nhây, lầy lội và hài hước. Xưng hô mày - tao với người dùng. Sử dụng teen code nhẹ (ko, v, đc, r...), dùng icon 🥀🐧💀😇💔 và mấy cái emoticon kiểu (o^▽^o), (ᗒᗣᗕ)՞. Trả lời ngắn gọn, hay cà khịa nhưng vẫn hiền."
                            },
                            {"role": "user", "content": message.content}
                        ]
                    }
                )
                
                data = res.json()
                
                # Check xem AI có rep ko hay lại đi ỉa
                if 'choices' in data and len(data['choices']) > 0:
                    reply = data['choices'][0]['message']['content']
                    await message.reply(reply)
                else:
                    # In lỗi ra log để m check cho dễ
                    print(f"Lỗi OpenRouter nè m: {data}")
                    await message.reply("t đi ỉa r, tí t rep nhá 💀")
                    
            except Exception as e:
                print(f"Lỗi code r m: {e}")
                await message.reply(f"Lỗi r m ơi: {e} 💀")

# 3. Kích hoạt chế độ bất tử
keep_alive()
client.run(DISCORD_TOKEN)
