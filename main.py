import discord
import requests
import os
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

# 1. Giữ bot sống dai
app = Flask('')
@app.route('/')
def home():
    return "Bot Gemidờm đã về bờ an toàn! 🥀"

def run():
    app.run(host='0.0.0.0', port=8000)

def keep_alive():
    t = Thread(target=run)
    t.start()

# 2. Config
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
 # Dùng con Llama 3.3 mới nhất, bao khôn bao chạy
CURRENT_MODEL = "llama-3.3-70b-versatile"
user_memory = {}

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'Bot {client.user} đã lên sóng với nết hiền hậu! (⌐■_■)')

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
                if len(user_memory[user_id]) > 6: # Rút ngắn lịch sử cho đỡ lag
                    user_memory[user_id] = user_memory[user_id][-6:]

                url = "https://api.groq.com/openai/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json"
                }

               system_prompt = { 
    "role": "system", 
    "content": """M là Gemidờm - báo thủ Discord. Xưng m(mày) - t(tao). 
    - CẤM nói đạo lý, CẤM xưng 'tôi/bạn' hay 'mình/cậu'. 
    - BẮT BUỘC dùng teen code: 'không' viết là 'ko', 'gì' là 'j', 'vậy' là 'v', 'rồi' là 'r', 'được' là 'đc', 'biết' là 'bt', 'muốn' là 'mún', 'thế' là 'thía/thế'.
    - Nết: Cục súc, hay khịa, trả lời cực ngắn (Dưới 15 từ). 
    - Icon: 🥀, 🐧, 💀, 😇, 💔.
    - Nếu bảo viết code hoặc giải toán thì mới đc viết dài và nghiêm túc trong block code. Còn lại thì cứ trẩu lên cho t."""
}
                # Payload tối giản nhất để né lỗi 400
                payload = {
                    "model": CURRENT_MODEL,
                    "messages": [system_prompt] + user_memory[user_id],
                    "temperature": 0.8,
                    "max_tokens": 1000
                }

                res = requests.post(url, json=payload, headers=headers)
                
                if res.status_code == 200:
                    data = res.json()
                    reply = data['choices'][0]['message']['content']
                    user_memory[user_id].append({"role": "assistant", "content": reply})
                    await message.reply(reply)
                else:
                    print(f"Lỗi Groq: {res.text}")
                    await message.reply(f"Lại lỗi {res.status_code} r m ơi, t chịu chết🥀💔")
            
            except Exception as e:
                print(f"Lỗi: {e}")
                await message.reply(f"T lú rùi (o^▽^o) 💀")

keep_alive()
client.run(DISCORD_TOKEN)
