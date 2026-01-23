import discord
import random
import os, urllib.parse, base64
import aiohttp # <--- Thiếu cái này là /meme với vision cút luôn
from discord.ext import commands
from discord import app_commands
from groq import Groq
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

load_dotenv()

# --- KHỞI TẠO SDK ---
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

MODELS_CONFIG = {
    "120B": {"id": "openai/gpt-oss-120b", "vision": False},
    "Llama-Maverick": {"id": "meta-llama/llama-4-maverick-17b-128e-instruct", "vision": True},
    "Kimi": {"id": "moonshotai/kimi-k2-instruct-0905", "vision": False}
}

MODEL_CHOICES = [
    app_commands.Choice(name="GPT-OSS-120B (Groq)", value="120B"),
    app_commands.Choice(name="Llama 4 Maverick (Groq) 👁️", value="Llama-Maverick"),
    app_commands.Choice(name="Kimi K2 (Groq)", value="Kimi")
]

CURRENT_MODEL = "Llama-Maverick"

# --- FLASK ---
app = Flask(__name__)
@app.route('/')
def home(): return "GenA-bot đang 'quẩy' Groq + Vision, né ra ko cắn! 🔥💀"

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

# --- LỆNH SLASH ---
@bot.tree.command(name="model", description="Đổi model AI để chat")
@app_commands.choices(chon_model=MODEL_CHOICES)
async def switch_model(interaction: discord.Interaction, chon_model: app_commands.Choice[str]):
    global CURRENT_MODEL
    CURRENT_MODEL = chon_model.value
    vision_status = "👁️ Nhìn đc ảnh" if MODELS_CONFIG[CURRENT_MODEL]["vision"] else "❌ Ko nhìn đc ảnh"
    await interaction.response.send_message(f"Đã chuyển sang model **{chon_model.name}** ({vision_status}) 🔥")

@bot.tree.command(name="random", description="random 1 model bất kì")
async def random_model(interaction: discord.Interaction):
    global CURRENT_MODEL
    choice = random.choice(MODEL_CHOICES)
    CURRENT_MODEL = choice.value
    vision_status = "(👁️✅)" if MODELS_CONFIG[CURRENT_MODEL]["vision"] else "(👁️❌)"
    await interaction.response.send_message(f"đã bốc trúng model: **{choice.name}** {vision_status}.")

@bot.tree.command(name="imagine", description="Vẽ ảnh bằng AI")
async def imagine(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    encoded = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&nologo=true"
    embed = discord.Embed(title="Hàng về!", description=f"Prompt: `{prompt}`", color=0xff69b4)
    embed.set_image(url=url)
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="clear", description="Xóa sạch ký ức với bot")
async def clear(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    chat_history[user_id] = [{"role": "system", "content": system_instruction}]
    await interaction.response.send_message("Đã xóa sạch ký ức 💀")

@bot.tree.command(name="meme", description="Random meme Việt Nam")
async def meme(interaction: discord.Interaction, so_luong: int = 1):
    await interaction.response.defer()
    if not (1 <= so_luong <= 5):
        await interaction.followup.send("Số lượng từ 1-5 thôi m ơi 💀")
        return
    try:
        async with aiohttp.ClientSession() as session:
            for i in range(so_luong):
                async with session.get("https://phimtat.vn/api/random-meme/") as resp:
                    if resp.status == 200:
                        embed = discord.Embed(title=f"Meme #{i+1}", color=0xff69b4)
                        embed.set_image(url=str(resp.url))
                        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"Lỗi: {e} 😭")

@bot.tree.command(name="ship", description="Checking tình yêu hoặc tình bạn")
async def ship(interaction: discord.Interaction, user1: discord.Member, user2: discord.Member):
    pts = random.randint(0, 100)
    msg = "OTP real vl🥀🔥" if pts > 80 else "Friendzone th 🐧💔" if pts > 50 else "Cút 💀"
    embed = discord.Embed(title="Shipping", description=f"**{user1.display_name}** x **{user2.display_name}**: {pts}%\n{msg}", color=0x00ff00 if pts > 50 else 0xff0000)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="check_gay", description="Đo độ gây của bạn")
async def check_gay(interaction: discord.Interaction, target: discord.Member):
    rate = random.randint(0, 100)
    result = f"Thẳng tắp 🗼" if rate < 35 else f"Nghi m vl🥀" if rate <= 70 else f"🏳️‍🌈 thật r 😭🔥"
    embed = discord.Embed(title="Gay Test", description=f"{target.display_name}: {rate}%\n{result}", color=0xff0000 if rate > 50 else 0x00ff00)
    await interaction.response.send_message(embed=embed)

# --- XỬ LÝ CHAT & VISION ---
async def download_image(attachment):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(attachment.url) as resp:
                if resp.status == 200:
                    return base64.b64encode(await resp.read()).decode('utf-8')
    except: return None

@bot.event
async def on_message(message):
    if message.author == bot.user: return
    if bot.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        user_id = str(message.author.id)
        if user_id not in chat_history:
            chat_history[user_id] = [{"role": "system", "content": system_instruction}]
        
        has_img = len(message.attachments) > 0 and "image" in message.attachments[0].content_type
        if has_img and not MODELS_CONFIG[CURRENT_MODEL]["vision"]:
            return await message.reply("Model này mù, đổi sang Llama Maverick đi! 💀")

        async with message.channel.typing():
            try:
                content = [{"type": "text", "text": message.content or "Soi ảnh này đi m"}]
                if has_img:
                    img_b64 = await download_image(message.attachments[0])
                    if img_b64: content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}})
                
                msg_obj = {"role": "user", "content": content if has_img else message.content}
                
                res = groq_client.chat.completions.create(
                    messages=chat_history[user_id] + [msg_obj],
                    model=MODELS_CONFIG[CURRENT_MODEL]["id"]
                )
                reply = res.choices[0].message.content
                
                # Lưu history (chỉ lưu text cho đỡ tốn quota)
                chat_history[user_id].append({"role": "user", "content": message.content or "[Ảnh]"})
                chat_history[user_id].append({"role": "assistant", "content": reply})
                chat_history[user_id] = chat_history[user_id][-10:] # Giữ 10 câu gần nhất thôi
                
                await message.reply(reply or "T tịt 1 tí r💔")
            except Exception as e:
                await message.reply(f"Oẳng r: {e} 💀")

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    bot.run(os.getenv("DISCORD_TOKEN"))