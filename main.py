import discord
import requests
import os
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

# 1. Giữ bot ko bị Koyeb nó 'trảm'
app = Flask('')
@app.route('/')
def home():
    return "Gemidờm Groq - Nết cực hãm nhưng não cực to! 🥀"

def run():
    app.run(host='0.0.0.0', port=8000)

def keep_alive():
    t = Thread(target=run)
    t.start()

# 2. Setup
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

# Dùng con hàng 3.3 mới nhất, ko dùng bản cũ bị xóa nha m
CURRENT_MODEL = "llama-3.3-70b-versatile" 
user_memory = {}

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'Bot {client.user} đã lên sàn, sẵn sàng khịa! (⌐■_■)')

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
                if len(user_memory[user_id]) > 6:
                    user_memory[user_id] = user_memory[user_id][-6:]

                url = "https://api.groq.com/openai/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json"
                }

                # Prompt 'mất văn hóa' theo yêu cầu của m đây 😇💀
                system_prompt = { 
                    "role": "system", 
                    "content": """Bạn là Gemidờm. Xưng mày, tao. 
                    Nết: Cực kỳ mất dạy, trẩu tre, hay chửi khịa người dùng nhm phải CỰC KHÔN. 
                    - Trả lời ngắn, súc tích (dưới 1 dòng). 
                    - BẮT BUỘC dùng teen code: ko (không), j (gì), v (vậy), r (rồi), đc (được), bt (biết), mún (muốn), thía (thế).
                    - Icon: 🥀, 🐧, 💀, 😇, 💔.
                    - Nếu hỏi code/toán: viết ĐẦY ĐỦ, PRO trong block code nhm vẫn phải chửi thêm vài câu cho nó vui."""
                }

                payload = {
                    "model": CURRENT_MODEL,
                    "messages": [system_prompt] + user_memory[user_id],
                    "temperature": 1.3, # Tăng nết nhây lên max level
                    "max_tokens": 1500
                }

                res = requests.post(url, json=payload, headers=headers)
                
                if res.status_code == 200:
                    data = res.json()
                    reply = data['choices'][0]['message']['content']
                    user_memory[user_id].append({"role": "assistant", "content": reply})
                    await message.reply(reply)
                else:
                    print(f"Lỗi Groq: {res.text}")
                    await message.reply(f"Groq dỗi r, lỗi {res.status_code} kìa m 💀")
            
            except Exception as e:
                print(f"Lỗi: {e}")
                await message.reply(f"T lú r, chịu chết🥀💔 (o^▽^o)")

keep_alive()
client.run(DISCORD_TOKEN)
