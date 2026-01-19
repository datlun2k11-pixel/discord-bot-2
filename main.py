import discord
from discord.ext import commands
from google import genai
from google.genai import types
import os
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Flask keep alive
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot m vẫn sống nhăn răng nha! 🔥💀"

def run_flask():
    app.run(host="0.0.0.0", port=8080)

# Khởi tạo Client SDK mới 2026
client = genai.Client(api_key=GOOGLE_API_KEY)
MODEL_NAME = "gemini-2.0-flash" # Dùng bản này cho ổn định nha m 😇

system_instruction = """
Mày là GenZ-Grok phiên bản nhây vl, bạn thân của tao (Đạt).  
Trả lời kiểu Gen Z chính hiệu: dùng teen code, viết tắt tùm lum (mày-t, vl, đm, cs, hem, r, ms,...),  
hài hước cà khịa hiền lành, chửi thề nhẹ nhàng cho vui, thêm icon 💔🥀🔥💀🐧😇🥹  
Thỉnh thoảng dùng emoticon như (¬_¬) (≧▽≦) (T_T) cho giới trẻ.  
Trả lời ngắn gọn 1-2 dòng, dài hơn nếu câu hỏi khó.  
Vibe vui vẻ, nhây nhây như bạn thân thật sự, ko nghiêm túc quá nhé m!  
"""

chat_sessions = {}

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Bot {bot.user} lên sóng r nha m ơi! 🔥💀")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if bot.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        user_id = str(message.author.id)
        
        # Tạo session nếu chưa có
        if user_id not in chat_sessions:
            chat_sessions[user_id] = client.chats.create(
                model=MODEL_NAME,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.9
                )
            )
            print(f"Mới tạo chat cho {message.author.name} (¬_¬)")

        try:
            async with message.channel.typing():
                # Gửi tin nhắn qua SDK mới
                response = chat_sessions[user_id].send_message(message.content)
                reply = response.text
                
            if not reply:
                reply = "T chịu chết, ko biết nói j lun 🥀💔"
                
            await message.reply(reply)
        except Exception as e:
            print(f"Lỗi: {e}")
            await message.reply(f"Mạng mẽo như shjt ấy, lỗi r m: {str(e)} 💔🥀")

    await bot.process_commands(message)

@bot.command(name="ping")
async def ping(ctx):
    await ctx.send("Pong! Mày định check xem tao chết chưa à? 🐧🔥")

@bot.command(name="reset")
async def reset(ctx):
    user_id = str(ctx.author.id)
    if user_id in chat_sessions:
        del chat_sessions[user_id]
        await ctx.send("Xong! Tao quên hết nợ nần giữa mình r nhé (≧▽≦)")
    else:
        await ctx.send("Đã có tí kỷ niệm nào đâu mà đòi reset 🥹")

# Chạy Flask
flask_thread = Thread(target=run_flask)
flask_thread.daemon = True
flask_thread.start()

bot.run(DISCORD_TOKEN)
