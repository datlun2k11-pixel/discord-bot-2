import discord
import requests
import os
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

# 1. Server ảo bất tử
app = Flask('')
@app.route('/')
def home():
    return "Bot đang tự dò sóng Google nha m! 😇"

def run():
    app.run(host='0.0.0.0', port=8000)

def keep_alive():
    t = Thread(target=run)
    t.start()

# 2. Config & Biến toàn cục
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY') # Nhớ là Key lấy từ Google AI Studio nha m

CURRENT_MODEL = None # Để bot tự điền

# Hàm tự dò tìm model "sống"
def get_working_model():
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GOOGLE_API_KEY}"
        res = requests.get(url)
        data = res.json()
        
        # Lọc tìm model ngon (Flash hoặc Pro)
        if 'models' in data:
            for model in data['models']:
                name = model['name'] # Nó sẽ có dạng 'models/gemini-1.5-flash'
                if 'generateContent' in model['supportedGenerationMethods']:
                    if 'flash' in name or 'pro' in name:
                        print(f"✅ Đã tìm thấy hàng ngon: {name}")
                        return name
            # Nếu ko thấy cái nào quen thì lấy cái đầu tiên tìm được
            if len(data['models']) > 0:
                return data['models'][0]['name']
                
        print(f"❌ Ko tìm thấy model nào: {data}")
        return None
    except Exception as e:
        print(f"❌ Lỗi khi dò model: {e}")
        return None

# Tìm model ngay khi khởi động code
CURRENT_MODEL = get_working_model()

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'Bot {client.user} đã lên sóng với model: {CURRENT_MODEL} (⌐■_■)')

@client.event
async def on_message(message):
    if message.author == client.user: return
    if client.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        async with message.channel.typing():
            try:
                # Nếu lúc đầu chưa tìm đc model thì giờ tìm lại
                global CURRENT_MODEL
                if not CURRENT_MODEL:
                    CURRENT_MODEL = get_working_model()
                    
                if not CURRENT_MODEL:
                    await message.reply("Google chặn cửa r m ơi, check lại Key đi 💀")
                    return

                # Gọi thẳng vào cái model vừa tìm được
                # Lưu ý: CURRENT_MODEL đã có sẵn chữ 'models/' rồi nên ko thêm nữa
                url = f"https://generativelanguage.googleapis.com/v1beta/{CURRENT_MODEL}:generateContent?key={GOOGLE_API_KEY}"
                
                payload = {
                    "contents": [{
                        "parts": [{
                            "text": f"Mày là một con bot Discord cực kỳ nhây, lầy lội và hài hước. Xưng hô mày - tao với người dùng. Sử dụng teen code nhẹ (ko, v, đc, r...), dùng icon 🥀🐧💀😇💔 và mấy cái emoticon kiểu (o^▽^o). Trả lời ngắn gọn, hay cà khịa nhưng vẫn hiền. Câu hỏi: {message.content}"
                        }]
                    }]
                }
                res = requests.post(url, json=payload)
                data = res.json()
                
                if 'candidates' in data:
                    reply = data['candidates'][0]['content']['parts'][0]['text']
                    await message.reply(reply)
                else:
                    print(f"Lỗi API: {data}")
                    error_msg = data.get('error', {}).get('message', 'Lỗi ko xác định')
                    await message.reply(f"t đi ỉa r, Google bảo: {error_msg} 💀")
            except Exception as e:
                await message.reply(f"Lỗi r m ơi: {e} 💀")

keep_alive()
client.run(DISCORD_TOKEN)
