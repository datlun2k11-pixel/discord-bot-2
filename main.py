import discord
import requests
import os
from dotenv import load_dotenv

# Load mấy cái secret từ file .env hoặc môi trường Koyeb
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

    # Trả lời khi đc tag hoặc nhắn tin riêng
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
                reply = res.json()['choices'][0]['message']['content']
                await message.reply(reply)
            except Exception as e:
                await message.reply(f"Lỗi r m ơi: {e} 💀")

client.run(DISCORD_TOKEN)