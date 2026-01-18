import discord
import requests
import os
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

# 1. Server ảo giữ bot sống dai trên Koyeb
app = Flask('')
@app.route('/')
def home():
    return "Bot Gemidờm - Phiên bản Mixtral 'thiếu văn hoá nhm khôn' đã sẵn sàng! 🥀"

def run():
    app.run(host='0.0.0.0', port=8000)

def keep_alive():
    t = Thread(target=run)
    t.start()

# 2. Cấu hình
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

# Đổi sang con Mixtral để bớt đần tiếng Việt
CURRENT_MODEL = "mixtral-8x7b-32768" 
user_memory = {}

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'Bot {client.user} đã lên sóng (⌐■_■) - Model: {CURRENT_MODEL}')

@client.event
async def on_message(message):
    if message.author == client.user: return
    
    # Check nếu bot được tag hoặc nhắn tin riêng
    if client.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        async with message.channel.typing():
            try:
                user_id = message.author.id
                if user_id not in user_memory:
                    user_memory[user_id] = []

                # Lưu lịch sử chat (tầm 10 câu cho khôn)
                user_memory[user_id].append({"role": "user", "content": message.content})
                if len(user_memory[user_id]) > 10:
                    user_memory[user_id] = user_memory[user_id][-10:]

                url = "https://api.groq.com/openai/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json"
                }

                # Nết của con Mixtral t đã "độ" lại cực gắt
                system_prompt = { 
                    "role": "system", 
                    "content": """Mày là Gemidờm - báo thủ Discord. Xưng m(mày) - t(tao). 
                    - Tính cách: Thiếu văn hoá nhẹ, cục súc, hay khịa nhm cực khôn và giỏi code.
                    - Teencode: 'không'->'ko', 'gì'->'j', 'vậy'->'v', 'rồi'->'r', 'được'->'đc', 'biết'->'bt'.
                    - Icon: 🥀, 🐧, 💀, 😇, 💔.
                    - Quy tắc: Bình thường rep cực ngắn (dưới 1 dòng). 
                    - Ngoại lệ: Nếu bảo viết code hoặc giải toán, phải viết cực chi tiết, xuống dòng chuẩn trong block code. Cấm viết lửng lơ."""
                }

                # Payload fix lỗi 400 và tăng độ nhây
                payload = {
                    "model": CURRENT_MODEL,
                    "messages": [system_prompt] + user_memory[user_id],
                    "temperature": 1.1, # Tăng độ mặn mòi
                    "top_p": 0.9,
                    "frequency_penalty": 1.0, 
                    "presence_penalty": 0.5,
                    "max_tokens": 1500 # Cho nó viết code thoải mái
                }

                res = requests.post(url, json=payload, headers=headers)
                
                if res.status_code == 200:
                    data = res.json()
                    reply = data['choices'][0]['message']['content']
                    user_memory[user_id].append({"role": "assistant", "content": reply})
                    await message.reply(reply)
                else:
                    print(f"Lỗi Groq {res.status_code}: {res.text}")
                    await message.reply(f"Groq nó chặn cửa r hay sao á 💀. Lỗi: {res.status_code}")
            
            except Exception as e:
                print(f"Lỗi: {e}")
                await message.reply(f"T lú r, đợi tí t hồi não nhé 💀💔")

keep_alive()
client.run(DISCORD_TOKEN)
