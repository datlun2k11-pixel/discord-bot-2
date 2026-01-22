import discord
from discord.ext import commands
from discord import app_commands
from groq import Groq
import os, io, urllib.parse
import google.generativeai as genai
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

load_dotenv()

# --- Khởi tạo Multi SDK (Groq + Google) ---
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# 1. Config Model ID
MODELS_CONFIG = {
    "120B": "openai/gpt-oss-120b",
    "Llama-4-Maverick": "meta-llama/llama-4-maverick-17b-128e-instruct",
    "Kimi-K2": "moonshotai/kimi-k2-instruct-0905",
    "Gemini-2.5-Pro": "gemini-2.5-pro",
    "Gemini-2.5-Flash": "gemini-2.5-flash",
    "Gemini-3-Flash": "gemini-3.0-flash-preview",
    "Gemini-3-Pro": "gemini-3.0-pro-preview"
}

# 2. Danh sách Model cho Slash Command
MODEL_CHOICES = [
    app_commands.Choice(name="Gemini 3 Pro Preview (Peakest/ez out quata)", value="Gemini-3-Pro"),
    app_commands.Choice(name="Gemini 3 Flash Preview (fast)", value="Gemini-3-Flash"),
    app_commands.Choice(name="Gemini 2.5 Pro (peak)", value="Gemini-2-Pro"),
    app_commands.Choice(name="Gemini 2.5 Flash (Smooth)", value="Gemini-2-Flash"),
    app_commands.Choice(name="Llama 4 Maverick (master of teencode)", value="Llama-4-Maverick"),
    app_commands.Choice(name="Kimi K2 (trolling)", value="Kimi-K2"),
    app_commands.Choice(name="GPT-OSS-120B (Reasoning)", value="120B")
]

MODEL_NAME = MODELS_CONFIG["Llama-4-Maverick"] 

app = Flask(__name__)
@app.route('/')
def home(): return "GenA-bot đang nhây, đừng chạm vào! 🔥💀"

def run_flask():
    app.run(host="0.0.0.0", port=8000)

system_instruction = """
Bot là GenA-bot – phiên bản AI nhây vl, vibe bạn thân.
- Vibe: Cà khịa, lầy lội.
- Xưng hô: m(mày) và t(tao)
- Cách nói: cần teencode và viết tắt (j, v, r, cx, nx, ko,...)
- Icon: Emoticon và emoji 💔, 🥀, 🔥, 💀, 🐧.
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
    await tree.sync()
    print(f"Bot {bot.user} ready cắn m r! (≧▽≦)")

# --- Lệnh SLASH để VẼ ẢNH (Dùng Pollinations cho nó "mlem") ---
@tree.command(name="imagine", description="Vẽ ảnh bằng AI")
@app_commands.describe(prompt="Ném prompt mlem vào đây")
async def imagine(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    try:
        encoded_prompt = urllib.parse.quote(prompt)
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true"
        embed = discord.Embed(title="Ảnh:", description=f"Prompt: `{prompt}`", color=0xff69b4)
        embed.set_image(url=image_url)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"Chuối nát r m ơi... 💀: {e}")

# --- Lệnh SLASH ĐỔI MODEL ---
@tree.command(name="model", description="Đổi model AI để chat")
@app_commands.choices(chon_model=MODEL_CHOICES)
async def switch_model(interaction: discord.Interaction, chon_model: app_commands.Choice[str]):
    global MODEL_NAME
    MODEL_NAME = MODELS_CONFIG[chon_model.value]
    await interaction.response.send_message(f"Đã chuyển sang model **{chon_model.name}** thành công")

@bot.event
async def on_message(message):
    if message.author == bot.user: return
    if bot.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        user_id = str(message.author.id)
        if user_id not in chat_history:
            chat_history[user_id] = [{"role": "system", "content": system_instruction}]
        chat_history[user_id].append({"role": "user", "content": message.content})
        
        try:
            async with message.channel.typing():
                # Phân loại dùng SDK nào
                if "gemini" in MODEL_NAME.lower():
                    m = genai.GenerativeModel(MODEL_NAME)
                    response = m.generate_content(message.content)
                    reply = response.text
                else:
                    chat_completion = client.chat.completions.create(
                        messages=chat_history[user_id],
                        model=MODEL_NAME,
                        temperature=0.7
                    )
                    reply = chat_completion.choices[0].message.content
                
                await message.reply(reply if reply else "T CHỊU CHẾT🥀💔")
        except Exception as e:
            await message.reply(f"Lại lỗi clgi r... 💀: {e}")

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    bot.run(os.getenv("DISCORD_TOKEN"))
