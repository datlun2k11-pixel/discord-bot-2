import discord
import requests
import os
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

# 1. Server ảo giữ bot ko bị ngủm
app = Flask('')
@app.route('/')
def home():
    return "Bot Gemidờm đang quẩy bên Groq nha m! 🥀🐧"

def run():
    app.run(host='0.0.0.0', port=8000)

def keep_alive():
    t = Thread(target=run)
    t.start()

# 2. Config & Biến toàn cục
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

# Dùng model Llama 3.3 70b cho nó khôn, ko bị ngáo "lô dzô"
CURRENT_MODEL = "llama-3.3-70b-versatile" 

# Bộ nhớ chat để bot ko bị mất trí nhớ
user_memory = {}

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'Bot {client.user} đã lên sóng (⌐■_■)')

@client.event
async def on_message(message):
    if message.author == client.user: return
    
    # Chỉ trả lời khi được tag hoặc nhắn tin riêng
    if client.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        async with message.channel.typing():
            try:
                user_id = message.author.id
                if user_id not in user_memory:
                    user_memory[user_id] = []

                # Lưu lịch sử chat
                user_memory[user_id].append({"role": "user", "content": message.content})
                if len(user_memory[user_id]) > 8: # Giữ 8 câu cho nhẹ não
                    user_memory[user_id] = user_memory[user_id][-8:]

                url = "https://api.groq.com/openai/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json"
                }

                # Cái "nết" của bot t chỉnh lại cho mặn hơn nè 🥀🐧
                system_prompt = {
                    "role": "system", 
                    "content": "Mày là Gemidờm, bot Discord lầy lội. Xưng m-t. Teen code (ko, j, v, r...). Nết: hay cà khịa, hài hước, trả lời cực ngắn (dưới 1 dòng). CẤM lặp từ 'lô', 'dzô'. Nếu nó nhắn 'lô' thì khịa lại kiểu 'lô cl' hoặc 'nói j nói lẹ'. Dùng icon 🥀🐧💀😇💔."
                }

                # ĐOẠN PAYLOAD THẦN THÁNH CHỮA BỆNH ĐẦN NÈ:
                payload = {
                    "model": CURRENT_MODEL,
                    "messages": [system_prompt] + user_memory[user_id],
                    "temperature": 1.0, # Tăng độ nhây
                    "top_p": 0.9,
                    "frequency_penalty": 1.5, # Vả cực mạnh nếu nó dám lặp từ "lô dzô"
                    "presence_penalty": 1.0, # Khuyến khích nó nói chuyện mới
                    "max_tokens": 100, # Ngắn gọn súc tích
                    "stop": ["\n", "User:", "Assistant:"] # Chặn đứng việc nó tự biên tự diễn
                }

                res = requests.post(url, json=payload, headers=headers)
                
                if res.status_code == 200:
                    data = res.json()
                    reply = data['choices'][0]['message']['content']
                    user_memory[user_id].append({"role": "assistant", "content": reply})
                    await message.reply(reply)
                else:
                    print(f"Lỗi Groq: {res.text}")
                    await message.reply(f"Groq báo lỗi {res.status_code} r m ơi 💀")
            
            except Exception as e:
                print(f"Lỗi: {e}")
                await message.reply(f"T chịu chết🥀💔 (o^▽^o)")

keep_alive()
client.run(DISCORD_TOKEN)
