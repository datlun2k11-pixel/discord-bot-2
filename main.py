import discord
from discord.ext import commands
from groq import Groq
import os
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

load_dotenv()

# Khởi tạo Groq
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL_NAME = "llama-3.3-70b-versatile"

# Flask để giữ bot live trên Koyeb
app = Flask(__name__)
@app.route('/')
def home(): return "Gemidởm đang nhây, đừng chạm vào! 🔥💀"

def run_flask():
    app.run(host="0.0.0.0", port=8000)

# System Prompt theo ý m
system_instruction = """
Mày là Gemidởm – phiên bản AI nhây vl, bạn thân của tao.
- Vibe: Cà khịa, lầy lội, xưng mày-tao.
- Cách nói: cần teencode nhưng mà phải nhây, thỉnh thoảng chửi thề nhẹ cho vui.
- Icon: Dùng emoticon (¬_¬), (≧▽≦), ( ͡° ͜ʖ ͡°), =)), :),... và emoji 💔, 🥀, 🔥, 💀, 🐧.
- Đặc biệt: Đạt hỏi gì khó hoặc vô lý thì nói "T CHỊU CHẾT🥀💔" r im luôn.
- Ko bao giờ hỏi lại kiểu "Mày cần giúp gì ko?". Trả lời ngắn 1-2 dòng thôi.
"""

# Bộ nhớ đệm (RAM)
chat_history = {}

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_message(message):
    if message.author == bot.user: return
    
    # Check nếu bị tag hoặc nhắn tin riêng
    if bot.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        user_id = str(message.author.id)
        
        # Tạo bộ nhớ mới
        if user_id not in chat_history:
            chat_history[user_id] = [{"role": "system", "content": system_instruction}]
        
        # Thêm tin nhắn user
        chat_history[user_id].append({"role": "user", "content": message.content})
        
        # Cắt bớt history nếu quá dài (max 8 câu cho đỡ tốn RAM)
        if len(chat_history[user_id]) > 10:
            chat_history[user_id] = [chat_history[user_id][0]] + chat_history[user_id][-9:]

        try:
            async with message.channel.typing():
                chat_completion = client.chat.completions.create(
                    messages=chat_history[user_id],
                    model=MODEL_NAME,
                    temperature=0.8, # Giảm tí cho đỡ ngáo
                    max_tokens=200 # Trả lời ngắn gọn
                )
                
                reply = chat_completion.choices[0].message.content
                
                # Lưu câu trả lời
                chat_history[user_id].append({"role": "assistant", "content": reply})
                
                await message.reply(reply if reply else "T CHỊU CHẾT🥀💔")
                
        except Exception as e:
            # Nếu lỗi do quota hoặc key thì báo nhẹ
            if "429" in str(e):
                await message.reply("M bào Groq ác quá nó sập mẹ r, đợi tí đê (¬_¬)🥀")
            else:
                await message.reply("Lại lỗi clgi r m ơi... 💀💔")

@bot.command(name="reset")
async def reset(ctx):
    user_id = str(ctx.author.id)
    chat_history[user_id] = [{"role": "system", "content": system_instruction}]
    await ctx.send("Đã xóa sạch kí ức về m, mình làm lại từ đầu nhé ( ͡° ͜ʖ ͡°)🔥")

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    bot.run(os.getenv("DISCORD_TOKEN"))
