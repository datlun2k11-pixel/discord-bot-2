import discord
import requests
import os
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

# 1. Server ảo giữ bot "thức"
app = Flask('')
@app.route('/')
def home():
    return "Bot Google đang online cực mạnh nha m! 😇"

def run():
    app.run(host='0.0.0.0', port=8000)

def keep_alive():
    t = Thread(target=run)
    t.start()

# 2. Setup
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'Bot {client.user} đã lên sóng r nhá! (⌐■_■)')

@client.event
async def on_message(message):
    if message.author == client.user: return
    if client.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        async with message.channel.typing():
            try:
                # Gọi thẳng vào API Google Gemini 1.5 Flash
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GOOGLE_API_KEY}"
                payload = {
                    "contents": [{
                        "parts": [{
                            "text": f"Mày là một con bot Discord cực kỳ nhây, lầy lội và hài hước. Xưng hô mày - tao với người dùng. Sử dụng teen code nhẹ (ko, v, đc, r...), dùng icon 🥀🐧💀😇💔 và mấy cái emoticon(biểu cảm bằng ký tự). Trả lời ngắn gọn, hay cà khịa nhưng vẫn hiền. Câu hỏi: {message.content}"
                        }]
                    }]
                }
                res = requests.post(url, json=payload)
                data = res.json()
                
                if 'candidates' in data:
                    reply = data['candidates'][0]['content']['parts'][0]['text']
                    await message.reply(reply)
                else:
                    print(f"Lỗi: {data}")
                    await message.reply("t đi ỉa r, tí t rep nhá 💀 (Check lại Key đi m)")
            except Exception as e:
                await message.reply(f"Lỗi r m ơi: {e} 💀")

keep_alive()
client.run(DISCORD_TOKEN)
