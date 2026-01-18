import discord
import requests
import os
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

# 1. Server ảo giữ bot sống dai
app = Flask('')
@app.route('/')
def home():
    return "Bot Gemidờm đã hết ngu, biết viết code rùi nha m! 🥀"

def run():
    app.run(host='0.0.0.0', port=8000)

def keep_alive():
    t = Thread(target=run)
    t.start()

# 2. Config
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

CURRENT_MODEL = "llama-3.3-70b-versatile" 
user_memory = {}

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'Bot {client.user} đã lên sóng với bộ não mới! (⌐■_■)')

@client.event
async def on_message(message):
    if message.author == client.user: return
    if client.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        async with message.channel.typing():
            try:
                user_id = message.author.id
                if user_id not in user_memory:
                    user_memory[user_id] = []

                user_memory[user_id].append({"role": "user", "content": message.content})
                if len(user_memory[user_id]) > 10:
                    user_memory[user_id] = user_memory[user_id][-10:]

                url = "https://api.groq.com/openai/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json"
                }

                # DẠY NÓ BIẾT KHI NÀO NÊN NHÂY, KHI NÀO NÊN VIẾT CODE
                system_prompt = {
                    "role": "system", 
                    "content": """Mày là Gemidờm - báo thủ Discord. Xưng m(mày) - t(tao). 
                    - Dùng teen code (ko, j, v, r, đc, bt, thui...). 
                    - Icon: 🥀🐧💀😇💔.
                    - Nết: Hay cà khịa, cục súc, trả lời cực ngắn (dưới 1 dòng).
                    - NGOẠI LỆ: Nếu người dùng bảo viết code (C++, Python...) hoặc giải bài tập, mày PHẢI viết đầy đủ, xuống dòng đàng hoàng và chuyên nghiệp trong block code. Ko đc viết lửng lơ."""
                }

                # PAYLOAD ĐÃ FIX LỖI STOP VÀ TĂNG TOKEN
                payload = {
                    "model": CURRENT_MODEL,
                    "messages": [system_prompt] + user_memory[user_id],
                    "temperature": 0.9, 
                    "top_p": 0.9,
                    "frequency_penalty": 1.2, # Vả nhẹ để nó bớt lặp từ
                    "presence_penalty": 0.6,
                    "max_tokens": 1000 # Cho hẳn 1k token để viết code cho sướng
                    # ĐÃ BỎ DÒNG STOP ĐỂ NÓ BIẾT XUỐNG DÒNG VIẾT CODE
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
