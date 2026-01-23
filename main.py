import discord
from discord.ext import commands
from discord import app_commands
from groq import Groq
import os, urllib.parse
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

load_dotenv()

# --- KHỞI TẠO SDK (chỉ giữ Groq thôi) ---
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# 1. Config Model ID (xoá sạch OpenRouter r nhé)
MODELS_CONFIG = {
    "120B": "openai/gpt-oss-120b",
    "Llama-Maverick": "meta-llama/llama-4-maverick-17b-128e-instruct",
    "Kimi": "moonshotai/kimi-k2-instruct-0905"
}

# 2. Danh sách Model cho Slash Command (chỉ còn Groq)
MODEL_CHOICES = [
    app_commands.Choice(name="GPT-OSS-120B (Groq)", value="120B"),
    app_commands.Choice(name="Llama 4 Maverick (Groq)", value="Llama-Maverick"),
    app_commands.Choice(name="Kimi K2 (Groq)", value="Kimi")
]

CURRENT_MODEL = "Kimi" 

# --- FLASK ĐỂ TREO BOT TRÊN KOYEB ---
app = Flask(__name__)
@app.route('/')
def home(): return "GenA-bot đang 'quẩy' Groq, né ra ko cắn! 🔥💀"

def run_flask():
    app.run(host="0.0.0.0", port=8000)

# --- CONFIG BOT ---
system_instruction = "Mày là GenA-bot, AI nhây vl. Xưng m(mày) - t(tao), viết teencode, dùng icon 💔, 🥀, 🔥, 💀, 🐧,.... Trả lời cực ngắn gọn."

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
    await interaction.response.send_message(f"Đã chuyển sang model **{chon_model.name}** thành công 🔥")

# --- LỆNH SLASH VẼ ẢNH ---
@bot.tree.command(name="imagine", description="Vẽ ảnh bằng AI")
async def imagine(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    encoded = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&nologo=true"
    embed = discord.Embed(title="Hàng về!", description=f"Prompt: `{prompt}`", color=0xff69b4)
    embed.set_image(url=url)
    await interaction.followup.send(embed=embed)

# --- Xoá ký ức ---
@bot.tree.command(name="clear", description="Xóa sạch ký ức với bot")
async def clear(interaction: discord.Interaction):
    global chat_history
    user_id = str(interaction.user.id)
    if user_id in chat_history:
        chat_history[user_id] = [{"role": "system", "content": system_instruction}]
        await interaction.response.send_message("Đã xóa sạch ký ức 💀")
    else:
        await interaction.response.send_message("Chưa xoá được do ký ức mới 🥀")

# --- Meme ---
@bot.tree.command(name="meme", description="Random meme Việt Nam")
async def meme(interaction: discord.Interaction, so_luong: int = 1):
    await interaction.response.defer()
    
    if so_luong > 5:
        await interaction.followup.send("Tối đa 5 meme thôi m ơi, nhiều vcl spam r 💀")
        return
    
    if so_luong < 1:
        await interaction.followup.send("Ít nhất 1 meme chứ bro 😭")
        return
    
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            for i in range(so_luong):
                async with session.get("https://phimtat.vn/api/random-meme/") as resp:
                    if resp.status == 200:
                        meme_url = str(resp.url)
                        
                        embed = discord.Embed(
                            title=f"Meme #{i+1}:", 
                            color=0xff69b4
                        )
                        embed.set_image(url=meme_url)
                        
                        await interaction.followup.send(embed=embed)
                    else:
                        await interaction.followup.send(f"Meme #{i+1} lỗi r bro 💀")
    except Exception as e:
        await interaction.followup.send(f"Lỗi vl: {e} 😭🙏")

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
                
                # Chỉ dùng Groq SDK thôi
                chat_completion = groq_client.chat.completions.create(
                    messages=chat_history[user_id],
                    model=model_id,
                    temperature=0.7
                )
                reply = chat_completion.choices[0].message.content
                
                await message.reply(reply if reply else "GAH DAYUM💔😭🙏")
        except Exception as e:
            await message.reply(f"Lỗi clgi r m ơi... 💀: {e}")

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    bot.run(os.getenv("DISCORD_TOKEN"))
