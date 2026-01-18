import discord
import requests
import os
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

# 1. Tạo server ảo để mở cổng 8000 né lỗi Pending
app = Flask('')
@app.route('/')
def home():
    return "Bot vẫn sống nhăn răng nha m! 😇"

def run():
    # Koyeb mặc định check cổng 8000 nên phải để port=8000
    app.run(host='0.0.0.0', port=8000)

def keep_alive():
    t = Thread(target=run)
    t.start()

# 2. Load biến môi trường
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
OPENROUTER_KEY = os.getenv('OPENROUTER_KEY')

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
                res = requests.post(
                    url="https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {OPENROUTER_KEY}"},
                    json={
                        "model": "google/gemini-2.0-flash-exp:free",
                        "messages": [{"role": "user", "content": message.content}]
                    }
                )
                data = res.json()
                if 'choices' in data:
                    reply = data['choices'][0]['message']['content']
                    await message.reply(reply)
                else:
                    await message.reply("AI đang bận, tí t rep nhá 💀")
            except Exception as e:
                await message.reply(f"Lỗi r m ơi: {e} 💀")

# 3. Chạy server ảo và Bot
keep_alive()
client.run(DISCORD_TOKEN)
