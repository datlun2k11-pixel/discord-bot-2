import discord
from discord.ext import commands
import google.generativeai as genai
import os
from dotenv import load_dotenv
import asyncio
from flask import Flask
from threading import Thread

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Flask để keep alive trên Koyeb (port 8080 bắt buộc)
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot tao sống khỏe nè m! 🔥💀"

def run_flask():
    app.run(host="0.0.0.0", port=8080)

# Config Gemini mới
genai.configure(api_key=GOOGLE_API_KEY)
client = genai.GenerativeModelClient()

MODEL_NAME = "gemini-2.5-flash"  # hoặc gemini-2.5-flash-latest nếu lỗi

system_instruction = """
Mày là GenZ-Gemini phiên bản nhây vl, bạn thân của tao.
Xưng hô m/mày-t/tao
Trả lời kiểu Gen Z chính hiệu: dùng teen code, viết tắt tùm lum (vl, đm, cs, hem, r, ms,...),  
hài hước cà khịa hiền lành, chửi thề nhẹ nhàng cho vui, thêm icon 💔🥀🔥💀🐧😇🥹  
Thỉnh thoảng dùng emoticon (biểu cảm bằng ký tự) cho giới trẻ.  
Trả lời ngắn gọn 1-2 dòng, dài hơn nếu câu hỏi khó.  
Vibe vui vẻ, nhây nhây như bạn thân thật sự, ko nghiêm túc quá nhé m!  
"""

chat_sessions = {}

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Bot {bot.user} online r nha m! 🔥💀")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if bot.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        user_id = str(message.author.id)
        if user_id not in chat_sessions:
            chat_sessions[user_id] = client.chats.create(
                model=MODEL_NAME,
                config=genai.types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.9,
                    max_output_tokens=500
                )
            )
            print(f"New chat for {message.author.name} (¬_¬)")

        chat = chat_sessions[user_id]

        try:
            async with message.channel.typing():
                response = chat.send_message(message.content)
                reply = response.text
            await message.reply(reply)
        except Exception as e:
            await message.reply(f"Ơ lỗi r m ơi vl... {str(e)} 💔🥀 Thử lại hem?")

    await bot.process_commands(message)

@bot.command(name="ping")
async def ping(ctx):
    await ctx.send("Pong vl! Tao nhớ hết lun 😇🔥")

@bot.command(name="reset")
async def reset(ctx):
    user_id = str(ctx.author.id)
    if user_id in chat_sessions:
        del chat_sessions[user_id]
        await ctx.send("Reset nhớ r nha m, hỏi lại từ đầu đi (≧▽≦)")
    else:
        await ctx.send("Chưa có session để reset đâu m ơi 🥹")

# Chạy Flask ở thread riêng trước khi bot chạy
flask_thread = Thread(target=run_flask)
flask_thread.daemon = True
flask_thread.start()

print("Flask server started on port 8080 nha m! 🐧")

bot.run(DISCORD_TOKEN)
