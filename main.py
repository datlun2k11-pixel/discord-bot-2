import discord
import requests
import os
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

# 1. Server ảo giữ bot tỉnh ngủ
app = Flask('')
@app.route('/')
def home():
    return "Bot vẫn sống nhăn răng nha m! 😇"

def run():
    app.run(host='0.0.0.0', port=8000)

def keep_alive():
    t = Thread(target=run)
    t.start()

# 2. Cấu hình
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
                # Tiêm DeepSeek và nạp tính cách nhây nhây
                res = requests.post(
                    url="https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {OPENROUTER_KEY}"},
                    json={
                      "model": "gryphe/mythomax-l2-13b:free",
                        "messages": [
                            {
                                "role": "system", 
                                "content": "Mày là một con bot Discord cực kỳ nhây, lầy lội và hài hước. Xưng hô mày - tao với người dùng. Sử dụng teen code nhẹ (ko, v, đc, r...), dùng icon 🥀🐧💀😇💔 và mấy cái emoticon kiểu (o^▽^o), (ᗒᗣᗕ)՞. Trả lời ngắn gọn, hay cà khịa nhưng vẫn hiền."
                            },
                            {"role": "user", "content": message.content}
                        ]
                    }
                )
                
                data = res.json()
                if 'choices' in data and len(data['choices']) > 0:
                    reply = data['choices'][0]['message']['content']
                    await message.reply(reply)
                else:
                    print(f"Lỗi nè: {data}")
                    await message.reply("t đi ỉa r, tí t rep nhá 💀")
            except Exception as e:
                await message.reply(f"Lỗi r m ơi: {e} 💀")

# 3. Khởi động
keep_alive()
client.run(DISCORD_TOKEN)
