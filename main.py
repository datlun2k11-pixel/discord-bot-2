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
    return "Bot đang dùng hệ thống dự phòng đa model nha m! (⌐■_■)"

def run():
    app.run(host='0.0.0.0', port=8000)

def keep_alive():
    t = Thread(target=run)
    t.start()

# 2. Config
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

# List model dự phòng
MODEL_POOL = []
CURRENT_MODEL_INDEX = 0

def refresh_model_pool():
    global MODEL_POOL
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GOOGLE_API_KEY}"
        res = requests.get(url)
        data = res.json()
        
        if 'models' in data:
            # Ưu tiên lấy mấy con Lite và Flash mới nhất của m
            priority_list = ['2.5-flash-lite', '2.5-flash', '2.0-flash', '1.5-flash']
            new_pool = []
            
            all_models = [m['name'] for m in data['models'] if 'generateContent' in m['supportedGenerationMethods']]
            
            # Sắp xếp theo độ ưu tiên của m
            for p in priority_list:
                for m_name in all_models:
                    if p in m_name and m_name not in new_pool:
                        new_pool.append(m_name)
            
            # Thêm nốt mấy con còn lại vào cuối list cho chắc
            for m_name in all_models:
                if m_name not in new_pool:
                    new_pool.append(m_name)
                    
            MODEL_POOL = new_pool
            print(f"✅ Pool model đã sẵn sàng: {MODEL_POOL}")
    except Exception as e:
        print(f"❌ Lỗi quét model: {e}")

refresh_model_pool()

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'Bot {client.user} đã lên sóng! Đang dùng: {MODEL_POOL[0] if MODEL_POOL else "None"}')

@client.event
async def on_message(message):
    global CURRENT_MODEL_INDEX
    if message.author == client.user: return
    if client.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        async with message.channel.typing():
            if not MODEL_POOL:
                refresh_model_pool()
                if not MODEL_POOL:
                    await message.reply("T chịu chết, ko tìm thấy cái model nào hết 🥀💔")
                    return

            # Thử lần lượt các model trong pool
            for _ in range(len(MODEL_POOL)):
                model_name = MODEL_POOL[CURRENT_MODEL_INDEX]
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={GOOGLE_API_KEY}"
                    payload = {
                        "contents": [{
                            "parts": [{
                                "text": f"Mày là một con bot Discord cực kỳ nhây, lầy lội và hài hước. Xưng m - t. Teen code nhẹ, dùng icon 🥀🐧💀😇💔 và emoticon. Trả lời ngắn gọn, hay cà khịa. Câu hỏi: {message.content}"
                            }]
                        }]
                    }
                    res = requests.post(url, json=payload)
                    data = res.json()

                    if 'candidates' in data:
                        reply = data['candidates'][0]['content']['parts'][0]['text']
                        await message.reply(reply)
                        return # Xong việc thì nghỉ
                    
                    # Nếu lỗi Quota (429) hoặc lỗi model ko tồn tại (404)
                    error_code = data.get('error', {}).get('code')
                    if error_code in [429, 404, 400]:
                        print(f"❌ Model {model_name} đang nghẹn (Code {error_code}), đổi con khác...")
                        CURRENT_MODEL_INDEX = (CURRENT_MODEL_INDEX + 1) % len(MODEL_POOL)
                        continue # Thử model tiếp theo
                    else:
                        await message.reply(f"Google bảo: {data.get('error', {}).get('message')} 💀")
                        return

                except Exception as e:
                    print(f"Lỗi khi gọi {model_name}: {e}")
                    CURRENT_MODEL_INDEX = (CURRENT_MODEL_INDEX + 1) % len(MODEL_POOL)

            await message.reply("Tất cả model đều đi ỉa r m ơi, đợi tí nhé 💀💔")

keep_alive()
client.run(DISCORD_TOKEN)
