import discord
import requests
import os
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

# 1. Giữ bot sống dai trên Koyeb
app = Flask('')
@app.route('/')
def home():
    return "Gemidờm OpenRouter - Đang 'bú' DeepSeek Free cực mạnh! 🥀"

def run():
    app.run(host='0.0.0.0', port=8000)

def keep_alive():
    t = Thread(target=run)
    t.start()

# 2. Cấu hình
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')

# Model DeepSeek bản FREE trên OpenRouter
CURRENT_MODEL = "deepseek/deepseek-chat:free" 
user_memory = {}

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'Bot {client.user} đã lên sàn OpenRouter! (⌐■_■)')

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
                if len(user_memory[user_id]) > 8:
                    user_memory[user_id] = user_memory[user_id][-8:]

                url = "https://openrouter.ai/api/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://localhost:3000", # OpenRouter bắt buộc có cái này
                    "X-Title": "Gemidom Discord Bot"
                }

                system_prompt = { 
                    "role": "system", 
                    "content": """M là Gemidờm - báo thủ Discord. Xưng m(mày) - t(tao). 
                    - CẤM nói đạo lý, CẤM xưng 'tôi/bạn'. 
                    - BẮT BUỘC dùng teen code: 'không'->'ko', 'gì'->'j', 'vậy'->'v', 'rồi'->'r', 'được'->'đc', 'biết'->'bt'.
                    - Nết: Cục súc, hay khịa, rep cực ngắn. 
                    - Icon: 🥀, 🐧, 💀, 😇, 💔.
                    - NGOẠI LỆ: Nếu bảo viết code hoặc giải toán thì phải viết cực pro trong block code."""
                }

                payload = {
                    "model": CURRENT_MODEL,
                    "messages": [system_prompt] + user_memory[user_id],
                    "temperature": 1.1,
                    "max_tokens": 1500
                }

                res = requests.post(url, json=payload, headers=headers)
                
                if res.status_code == 200:
                    data = res.json()
                    # OpenRouter đôi khi trả về list rỗng nếu model free quá tải
                    if 'choices' in data and len(data['choices']) > 0:
                        reply = data['choices'][0]['message']['content']
                        user_memory[user_id].append({"role": "assistant", "content": reply})
                        await message.reply(reply)
                    else:
                        await message.reply("Hàng free đang nghẽn r, đợi tí m 🥀")
                else:
                    print(f"Lỗi OpenRouter: {res.text}")
                    await message.reply(f"OpenRouter tát lỗi {res.status_code} vô mặt t r 🥀💔")
            
            except Exception as e:
                print(f"Lỗi: {e}")
                await message.reply(f"T chịu chết🥀💔 (o^▽^o)")

keep_alive()
client.run(DISCORD_TOKEN)
