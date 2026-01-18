import discord
import requests
import os
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

# 1. Server ảo giữ bot sống
app = Flask('')
@app.route('/')
def home():
    return "Bot đã chuyển hộ khẩu sang Groq, chạy nhanh như chó đuổi! 🐶💨"

def run():
    app.run(host='0.0.0.0', port=8000)

def keep_alive():
    t = Thread(target=run)
    t.start()

# 2. Config
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GROQ_API_KEY = os.getenv('GROQ_API_KEY') # Nhớ đổi tên biến trong Koyeb nha m

# Dùng con Llama 3 mới nhất, bao ngon, bao nhây
# Hoặc m có thể đổi thành 'llama3-8b-8192' nếu muốn tiết kiệm hơn nữa
CURRENT_MODEL = "llama-3.3-70b-versatile" 

# Bộ nhớ chat (RAM)
user_memory = {}

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'Bot {client.user} đã tái sinh bên Groq! Model: {CURRENT_MODEL} (⌐■_■)')

@client.event
async def on_message(message):
    if message.author == client.user: return
    if client.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        async with message.channel.typing():
            try:
                user_id = message.author.id
                
                # 1. Khởi tạo bộ nhớ nếu chưa có
                if user_id not in user_memory:
                    user_memory[user_id] = []

                # 2. Thêm tin nhắn mới của m vào
                # Lưu ý: Groq dùng format "role": "user", "content": "text" (khác Google xíu)
                user_memory[user_id].append({"role": "user", "content": message.content})

                # 3. Giới hạn bộ nhớ 10 câu gần nhất
                if len(user_memory[user_id]) > 10:
                    user_memory[user_id] = user_memory[user_id][-10:]

                # 4. Chuẩn bị gửi sang Groq
                url = "https://api.groq.com/openai/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json"
                }
                
                # System Prompt: Cái nết của bot nằm ở đây
                system_prompt = {
                    "role": "system", 
                    "content": "Mày là một con bot Discord cực kỳ nhây, lầy lội, xéo sắc. Xưng hô mày (m) - tao (t). Sử dụng teen code, viết tắt (ko, đc, r...), dùng nhiều icon 🥀🐧💀😇💔 và emoticon (o^▽^o). Trả lời ngắn gọn, súc tích, hay cà khịa nhưng vẫn vui vẻ. Nếu bị chửi thì chửi lại nhẹ nhàng thâm thúy."
                }
                
                # Ghép System Prompt + Lịch sử chat
                messages_to_send = [system_prompt] + user_memory[user_id]

                payload = {
                    "model": CURRENT_MODEL,
                    "messages": messages_to_send,
                    "temperature": 0.8, # Độ sáng tạo (càng cao càng ngáo)
                    "max_tokens": 1024
                }

                # 5. Bắn tin đi
                res = requests.post(url, json=payload, headers=headers)
                
                if res.status_code == 200:
                    data = res.json()
                    reply = data['choices'][0]['message']['content']
                    
                    # Lưu câu trả lời của bot vào bộ nhớ
                    user_memory[user_id].append({"role": "assistant", "content": reply})
                    
                    await message.reply(reply)
                else:
                    # Nếu lỗi thì in ra xem nó bị gì
                    print(f"Lỗi Groq: {res.text}")
                    await message.reply(f"Groq nó cũng chặn cửa r hay sao á 💀. Lỗi: {res.status_code}")
            
            except Exception as e:
                print(f"Lỗi code: {e}")
                await message.reply(f"Bot đột tử r m ơi: {e} 🥀")

keep_alive()
client.run(DISCORD_TOKEN)
