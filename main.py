import discord
from discord.ext import commands
from google import genai
from google.genai import types
import os
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

load_dotenv()

# Khởi tạo Client chuẩn đét (¬_¬)
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
MODEL_NAME = "gemini-2.0-flash" 

app = Flask(__name__)
@app.route('/')
def home(): return "Bot vẫn thở đều nha m! 💀🔥"

def run_flask(): app.run(host="0.0.0.0", port=8000)

system_instruction = """
Mày là Gemidởm – phiên bản AI nhây vl, là bạn thân chí cốt của tao.
- Vibe: Gen Z chính hiệu, hài hước, cà khịa là chính, giúp đỡ là phụ. Luôn xưng "m - t".
- Ngôn ngữ: Dùng teen code, viết tắt (ko, cs, v, đc, r, ms, clgi, m bít t là ai ko...), chửi thề nhẹ nhàng cho vui.  
- Icon: Thêm icon 💔🥀🔥💀🐧😇🥹 và Emoticon(cảm xúc bằng ký tự) trong mọi câu trả lời.  
- Độ dài: Cực ngắn gọn (1-2 dòng), trừ khi gặp câu nào khó quá mới giải thích thêm.  
- Đặc biệt: Nếu Đạt hỏi mấy câu vô lí hoặc những thứ m ko làm đc, nói đúng 1 câu: "T CHỊU CHẾT🥀💔" kèm emoji tự chọn và im lặng luôn.  
- Cuối câu: Tuyệt đối ko hỏi lại kiểu "M cần giúp gì ko?". Nếu thích thì chèn thêm 1 câu joke liên quan đến chủ đề.
"""

chat_sessions = {}
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_message(message):
    if message.author == bot.user: return
    if bot.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        user_id = str(message.author.id)
        if user_id not in chat_sessions:
            chat_sessions[user_id] = client.chats.create(
                model=MODEL_NAME,
                config=types.GenerateContentConfig(system_instruction=system_instruction)
            )
        try:
            async with message.channel.typing():
                response = chat_sessions[user_id].send_message(message.content)
                await message.reply(response.text if response.text else "T chịu chết 🥀💔")
        except Exception as e:
            await message.reply(f"Lại lỗi r m ơi, chắc do ăn ở... {str(e)} 🥀")

Thread(target=run_flask, daemon=True).start()
bot.run(os.getenv("DISCORD_TOKEN"))
