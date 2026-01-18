import discord
import requests
import os
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

# 1. Server ảo
app = Flask('')
@app.route('/')
def home():
    return "Bot đã có bộ nhớ, ko còn ngáo ngơ nha m! 😇"

def run():
    app.run(host='0.0.0.0', port=8000)

def keep_alive():
    t = Thread(target=run)
    t.start()

# 2. Config
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

MODEL_POOL = []
CURRENT_MODEL_INDEX = 0
# TỪ ĐIỂN LƯU LỊCH SỬ CHAT (Bộ nhớ nè m)
user_memory = {} 

def refresh_model_pool():
    global MODEL_POOL
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GOOGLE_API_KEY}"
        res = requests.get(url)
        data = res.json()
        if 'models' in data:
            priority_list = ['2.5-flash-lite', '2.5-flash', '2.0-flash', '1.5-flash']
            new_pool = []
            all_models = [m['name'] for m in data['models'] if 'generateContent' in m['supportedGenerationMethods']]
            for p in priority_list:
                for m_name in all_models:
                    if p in m_name and m_name not in new_pool:
                        new_pool.append(m_name)
            MODEL_POOL = new_pool
            print(f"✅ Pool model: {MODEL_POOL}")
    except: pass

refresh_model_pool()

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'Bot {client.user} đã sẵn sàng khịa có bài bản! 🥀')

@client.event
async def on_message(message):
    global CURRENT_MODEL_INDEX
    if message.author == client.user: return
    if client.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        async with message.channel.typing():
            user_id = message.author.id
            # Khởi tạo bộ nhớ nếu chưa có
            if user_id not in user_memory:
                user_memory[user_id] = []

            # Thêm câu hỏi của m vào bộ nhớ
            user_memory[user_id].append({"role": "user", "parts": [{"text": message.content}]})
            
            # Chỉ giữ lại 10 câu gần nhất cho đỡ nặng (và đỡ tốn tiền/quota)
            if len(user_memory[user_id]) > 10:
                user_memory[user_id] = user_memory[user_id][-10:]

            for _ in range(len(MODEL_POOL)):
                model_name = MODEL_POOL[CURRENT_MODEL_INDEX]
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={GOOGLE_API_KEY}"
                    
                    # GỬI NGUYÊN CÁI LỊCH SỬ CHAT ĐI NÈ
                    payload = {
                        "contents": user_memory[user_id],
                        "system_instruction": {
                            "parts": [{"text": "Mày là bot Discord nhây, lầy. Xưng m - t. Teen code, icon 🥀🐧💀😇💔. Trả lời cực ngắn gọn."}]
                        }
                    }
                    
                    res = requests.post(url, json=payload)
                    data = res.json()

                    if 'candidates' in data:
                        reply = data['candidates'][0]['content']['parts'][0]['text']
                        # Lưu câu trả lời của bot vào bộ nhớ để lần sau nó nhớ nó đã nói gì
                        user_memory[user_id].append({"role": "model", "parts": [{"text": reply}]})
                        await message.reply(reply)
                        return
                    
                    if data.get('error', {}).get('code') in [429, 404, 400]:
                        CURRENT_MODEL_INDEX = (CURRENT_MODEL_INDEX + 1) % len(MODEL_POOL)
                        continue
                except:
                    CURRENT_MODEL_INDEX = (CURRENT_MODEL_INDEX + 1) % len(MODEL_POOL)

            await message.reply("T lú r, đợi tí t hồi não nhé 💀💔")

keep_alive()
client.run(DISCORD_TOKEN)

