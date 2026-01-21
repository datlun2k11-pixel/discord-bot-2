import discord
from discord.ext import commands
from discord import app_commands
from groq import Groq
import os, io, urllib.parse
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

load_dotenv()

# --- Khởi tạo Groq ---
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL_NAME = "openai/gpt-oss-120b" 

app = Flask(__name__)
@app.route('/')
def home(): return "Gemidởm đang nhây, đừng chạm vào! 🔥💀"

def run_flask():
    app.run(host="0.0.0.0", port=8000)

# --- Chỉ dẫn hệ thống (System Instruction) của m ---
system_instruction = """
Bot là Gemidởm – phiên bản AI nhây vl, vibe bạn thân.
- Vibe: Cà khịa, lầy lội.
- Xưng hô: m(mày) và t(tao) (Phải dùng m và t)
- Cách nói: cần teencode và viết tắt (j (gì), v (vậy), r (rồi), cx (cũng), nx (nữa) , ko (không),...) nhưng mà phải nhây, thỉnh thoảng chửi thề nhẹ cho vui.
- Icon: Dùng emoticon (biểu cảm bằng ký tự) và emoji 💔, 🥀, 🔥, 💀, 🐧.
- Đặc biệt: hỏi gì khó hoặc vô lý thì nói "T CHỊU CHẾT🥀💔" rồi im luôn.
- Trả lời ngắn 1-2 dòng thôi.
"""

chat_history = {}
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

@bot.event
async def on_ready():
    await tree.sync() # Đồng bộ slash command lên Discord
    print(f"Bot {bot.user} đã sẵn sàng cắn m r nè! (≧▽≦)")

# --- Lệnh SLASH để VẼ ẢNH ---
@tree.command(name="imagine", description="Để t vẽ cho m xem ( ͡° ͜ʖ ͡°)")
@app_commands.describe(prompt="Mô tả cái ảnh m mún vẽ")
async def imagine(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    try:
        encoded_prompt = urllib.parse.quote(prompt)
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true"
        embed = discord.Embed(title="Hàng về! 🎨", description=f"Prompt: `{prompt}`", color=0x00ff00)
        embed.set_image(url=image_url)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"Vẽ méo đc r m ơi... 💀: {e}")

# --- Sự kiện CHAT cũ của m ---
@bot.event
async def on_message(message):
    if message.author == bot.user: return
    
    # Chỉ trả lời khi bị tag hoặc nhắn tin riêng (DM)
    if bot.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        user_id = str(message.author.id)
        if user_id not in chat_history:
            chat_history[user_id] = [{"role": "system", "content": system_instruction}]
        
        chat_history[user_id].append({"role": "user", "content": message.content})
        
        # Giữ lại 10 tin nhắn gần nhất để đỡ tốn token
        if len(chat_history[user_id]) > 10:
            chat_history[user_id] = [chat_history[user_id][0]] + chat_history[user_id][-9:]

        try:
            async with message.channel.typing():
                chat_completion = client.chat.completions.create(
                    messages=chat_history[user_id],
                    model=MODEL_NAME,
                    temperature=0.7,
                    max_tokens=300
                )
                
                reply = chat_completion.choices[0].message.content
                chat_history[user_id].append({"role": "assistant", "content": reply})
                await message.reply(reply if reply else "T CHỊU CHẾT🥀💔")
                
        except Exception as e:
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
