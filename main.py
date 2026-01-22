import discord
from discord.ext import commands
from discord import app_commands
from groq import Groq
from openai import OpenAI
import os, urllib.parse
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

load_dotenv()

# --- KHỞI TẠO SDK (Vĩnh biệt Google Rate Limit 🥀) ---
# Groq cho mấy con model m thích
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
# OpenRouter cho mấy con hàng FREE
or_client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

# 1. Config Model ID (thêm free OpenRouter)
MODELS_CONFIG = {
    "120B": "openai/gpt-oss-120b",
    "Llama-Maverick": "meta-llama/llama-4-maverick-17b-128e-instruct",
    "Kimi": "moonshotai/kimi-k2-instruct-0905",
    "Llama-Free": "meta-llama/llama-3.1-8b-instruct:free",
    "MiMo-Flash": "xiaomi/mimo-v2-flash:free",          # vl xịn, context 262k 🔥
    "Devstral": "mistralai/devstral-2512:free",         # coding god free luôn
    "Chimera-R1T2": "tngtech/deepseek-r1t2-chimera:free",  # roleplay/creepy ngon
    "LFM-Instruct": "liquid/lfm-2.5-1.2b-instruct:free"   # nhỏ gọn, chat nhanh
}

# 2. Danh sách Model cho Slash Command (thêm mấy con free)
MODEL_CHOICES = [
    app_commands.Choice(name="GPT-OSS-120B (Groq)", value="120B"),
    app_commands.Choice(name="Llama 4 Maverick (Groq)", value="Llama-Maverick"),
    app_commands.Choice(name="Kimi K2 (Groq)", value="Kimi"),
    app_commands.Choice(name="Llama 3.1 8B (OpenRouter FREE)", value="Llama-Free"),
    app_commands.Choice(name="MiMo-V2-Flash (Free 262k ctx)", value="MiMo-Flash"),
    app_commands.Choice(name="Devstral 2 2512 (Coding Beast Free)", value="Devstral"),
    app_commands.Choice(name="DeepSeek R1T2 Chimera (Roleplay Free)", value="Chimera-R1T2"),
    app_commands.Choice(name="LFM 1.2B Instruct (Nhỏ gọn Free)", value="LFM-Instruct")
]

CURRENT_MODEL = "120B" 

# --- FLASK ĐỂ TREO BOT TRÊN KOYEB ---
app = Flask(__name__)
@app.route('/')
def home(): return "GenA-bot đang 'quẩy' Groq + OpenRouter free, né ra ko cắn! 🔥💀"

def run_flask():
    app.run(host="0.0.0.0", port=8000)

# --- CONFIG BOT ---
system_instruction = "Mày là GenA-bot, AI nhây vl. Xưng m-t, viết teencode, dùng icon 💔🥀🔥💀🐧. Trả lời cực ngắn 1-2 dòng. Khó/vô lý quá thì 'GAH DAYUM💔😭🙏'."

chat_history = {}
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Bot {bot.user} ready cắn m r! (≧▽≦)")

# --- LỆNH SLASH ĐỔI MODEL ---
@bot.tree.command(name="model", description="Đổi model AI để chat")
@app_commands.choices(chon_model=MODEL_CHOICES)
async def switch_model(interaction: discord.Interaction, chon_model: app_commands.Choice[str]):
    global CURRENT_MODEL
    CURRENT_MODEL = chon_model.value
    await interaction.response.send_message(f"Đã chuyển sang model **{chon_model.name}** thành công 🐧🔥")

# --- LỆNH SLASH VẼ ẢNH ---
@bot.tree.command(name="imagine", description="Vẽ ảnh bằng AI")
async def imagine(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    encoded = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&nologo=true"
    embed = discord.Embed(title="Hàng về!", description=f"Prompt: `{prompt}`", color=0xff69b4)
    embed.set_image(url=url)
    await interaction.followup.send(embed=embed)

# --- XỬ LÝ CHAT ---
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
                model_id = MODELS_CONFIG[CURRENT_MODEL]
                
                # Logic chọn SDK
                if CURRENT_MODEL in ["120B", "Llama-Maverick", "Kimi"]:
                    # Dùng Groq SDK
                    chat_completion = groq_client.chat.completions.create(
                        messages=chat_history[user_id],
                        model=model_id,
                        temperature=0.7
                    )
                    reply = chat_completion.choices[0].message.content
                else:
                    # Dùng OpenRouter SDK (cho tất cả free + Llama-Free)
                    res = or_client.chat.completions.create(
                        model=model_id,
                        messages=chat_history[user_id]
                    )
                    reply = res.choices[0].message.content
                
                await message.reply(reply if reply else "GAH DAYUM💔😭🙏")
        except Exception as e:
            await message.reply(f"Lỗi clgi r m ơi... 💀: {e}")

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    bot.run(os.getenv("DISCORD_TOKEN"))
