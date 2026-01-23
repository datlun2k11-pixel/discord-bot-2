import discord
import random
from discord.ext import commands
from discord import app_commands
from groq import Groq
import os, urllib.parse, base64
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

load_dotenv()

# --- KHỞI TẠO SDK ---
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# 1. Config Model ID (đánh dấu con nào support vision)
MODELS_CONFIG = {
    "120B": {"id": "openai/gpt-oss-120b", "vision": False},
    "Llama-Maverick": {"id": "meta-llama/llama-4-maverick-17b-128e-instruct", "vision": True},  # con này nhìn đc ảnh
    "Kimi": {"id": "moonshotai/kimi-k2-instruct-0905", "vision": False}
}

# 2. Danh sách Model cho Slash Command
MODEL_CHOICES = [
    app_commands.Choice(name="GPT-OSS-120B (Groq)", value="120B"),
    app_commands.Choice(name="Llama 4 Maverick (Groq) 👁️", value="Llama-Maverick"),  # emoji mắt = support ảnh
    app_commands.Choice(name="Kimi K2 (Groq)", value="Kimi")
]

CURRENT_MODEL = "Llama-Maverick"  # đổi default sang con nhìn đc ảnh

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

# --- LỆNH SLASH ĐỔI MODEL ---
@bot.tree.command(name="model", description="Đổi model AI để chat")
@app_commands.choices(chon_model=MODEL_CHOICES)
async def switch_model(interaction: discord.Interaction, chon_model: app_commands.Choice[str]):
    global CURRENT_MODEL
    CURRENT_MODEL = chon_model.value
    vision_status = "👁️ Nhìn đc ảnh" if MODELS_CONFIG[CURRENT_MODEL]["vision"] else "❌ Ko nhìn đc ảnh"
    await interaction.response.send_message(f"Đã chuyển sang model **{chon_model.name}** ({vision_status}) 🔥")
# --- random model ---
@bot.tree.command(name="random", description="random 1 model bất kì")
async def random_model(interaction: discord.Interaction):
    global CURRENT_MODEL
    choice = random.choice(MODEL_CHOICES)
    CURRENT_MODEL = choice.value
    vision_status = "👁️" if MODELS_CONFIG[CURRENT_MODEL]["vision"] else "❌"
    await interaction.response.send_message(f"đã bốc trúng model: **{choice.name}** {vision_status}.")

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

# --- HÀM DOWNLOAD ẢNH TỪ DISCORD ---
async def download_image(attachment):
    """Download ảnh từ Discord và convert sang base64"""
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(attachment.url) as resp:
                if resp.status == 200:
                    image_data = await resp.read()
                    return base64.b64encode(image_data).decode('utf-8')
    except Exception as e:
        print(f"Lỗi download ảnh: {e}")
    return None

# --- XỬ LÝ CHAT (CÓ HỖ TRỢ VISION) ---
@bot.event
async def on_message(message):
    if message.author == bot.user: return
    if bot.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        user_id = str(message.author.id)
        if user_id not in chat_history:
            chat_history[user_id] = [{"role": "system", "content": system_instruction}]
        
        # Kiểm tra xem có ảnh ko
        has_image = len(message.attachments) > 0 and message.attachments[0].content_type.startswith('image/')
        
        # Kiểm tra model hiện tại có support vision ko
        if has_image and not MODELS_CONFIG[CURRENT_MODEL]["vision"]:
            await message.reply("Model hiện tại ko nhìn đc ảnh m ơi 💀 Dùng /model chọn Llama 4 Maverick đi!")
            return
        
        try:
            async with message.channel.typing():
                model_id = MODELS_CONFIG[CURRENT_MODEL]["id"]
                
                # Nếu có ảnh và model support vision
                if has_image and MODELS_CONFIG[CURRENT_MODEL]["vision"]:
                    image_base64 = await download_image(message.attachments[0])
                    
                    if image_base64:
                        # Format message cho vision API
                        user_message = {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": message.content if message.content else "Phân tích ảnh này giúp t"
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{image_base64}"
                                    }
                                }
                            ]
                        }
                    else:
                        await message.reply("Download ảnh lỗi r bro 💀")
                        return
                else:
                    # Chat text bình thường
                    user_message = {"role": "user", "content": message.content}
                
                # Tạo history tạm (ko lưu ảnh vào history để tiết kiệm token)
                temp_history = chat_history[user_id].copy()
                temp_history.append(user_message)
                
                # Gọi API
                chat_completion = groq_client.chat.completions.create(
                    messages=temp_history,
                    model=model_id,
                    temperature=0.7
                )
                reply = chat_completion.choices[0].message.content
                
                # Lưu vào history (chỉ lưu text thôi)
                if has_image:
                    chat_history[user_id].append({
                        "role": "user", 
                        "content": f"[Đã gửi ảnh] {message.content if message.content else 'Phân tích ảnh'}"
                    })
                else:
                    chat_history[user_id].append(user_message)
                
                chat_history[user_id].append({"role": "assistant", "content": reply})
                
                await message.reply(reply if reply else "GAH DAYUM💔😭🙏")
        except Exception as e:
            await message.reply(f"Lỗi clgi r m ơi... 💀: {e}")

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    bot.run(os.getenv("DISCORD_TOKEN"))
