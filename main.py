import discord
from discord.ext import commands
from groq import Groq
import os
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

load_dotenv()

# Khởi tạo Groq Client
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL_NAME = "llama-3.3-70b-versatile" # Con này đang ngon nhất Groq nè m

app = Flask(__name__)
@app.route('/')
def home(): return "Gemidởm (Groq ver) vẫn thở nha m! 💀🔥"

def run_flask(): app.run(host="0.0.0.0", port=8000)

system_instruction = """
Mày là Gemidởm – phiên bản AI nhây vl, bạn thân của Đạt.
- Vibe: Cà khịa, lầy lội, xưng mày-tao.
- Cách nói: cần teencode nhưng mà phải nhây, thỉnh thoảng chửi thề nhẹ cho vui.
- Icon: Dùng emoticon (¬_¬), (≧▽≦), ( ͡° ͜ʖ ͡°) và emoji 💔🥀🔥💀🐧.
- Đặc biệt: Đạt hỏi gì khó hoặc vô lý thì nói "T CHỊU CHẾT🥀💔" r im luôn.
- Ko bao giờ hỏi lại kiểu "Mày cần giúp gì ko?". Trả lời ngắn 1-2 dòng thôi.
"""

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_message(message):
    if message.author == bot.user: return
    if bot.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        try:
            async with message.channel.typing():
                chat_completion = client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": system_instruction},
                        {"role": "user", "content": message.content}
                    ],
                    model=MODEL_NAME,
                    temperature=0.9
                )
                reply = chat_completion.choices[0].message.content
                await message.reply(reply if reply else "T chịu chết 🥀💔")
        except Exception as e:
            await message.reply(f"Lại lỗi r m, sang Groq vẫn đen... {str(e)} 🥀")

Thread(target=run_flask, daemon=True).start()
bot.run(os.getenv("DISCORD_TOKEN"))
