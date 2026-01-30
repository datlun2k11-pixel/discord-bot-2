import discord, random, os, base64, aiohttp, asyncio
from discord.ext import commands
from discord import app_commands
from groq import Groq
from dotenv import load_dotenv
from flask import Flask
from threading import Thread
from pollinations import Pollinations  # Đã thay đổi

load_dotenv()

# Khởi tạo clients
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
polinations_client = Pollinations()  # Đã thay đổi - API key không bắt buộc

# CẤU HÌNH MODEL - GỘP GROQ + POLINATIONS
MODELS_CONFIG = {
    # --- Groq Models (giữ nguyên) ---
    "Groq-120B": {"id": "openai/gpt-oss-120b", "vision": False, "provider": "groq"},
    "Groq-Llama-Maverick": {"id": "meta-llama/llama-4-maverick-17b-128e-instruct", "vision": True, "provider": "groq"},
    "Groq-Kimi": {"id": "moonshotai/kimi-k2-instruct-0905", "vision": False, "provider": "groq"},
    "Groq-Qwen3": {"id": "qwen/qwen3-32b", "vision": False, "provider": "groq"},
    "Groq-GPT-Safeguard": {"id": "openai/gpt-oss-safeguard-20b", "vision": False, "provider": "groq"},
    
    # --- Polinations Models (Model mới thêm - TIẾT KIỆM POLLEN) ---
    "Poli-Flux-Free": {"id": "flux", "vision": False, "provider": "polinations", "image_gen": True},
    "Poli-Klein": {"id": "klein", "vision": False, "provider": "polinations", "image_gen": True},
    "Poli-GPT-5": {"id": "gpt-5", "vision": False, "provider": "polinations"},
    "Poli-Claude": {"id": "claude", "vision": False, "provider": "polinations"},
    "Poli-Gemini": {"id": "gemini", "vision": False, "provider": "polinations"},
}

MODEL_CHOICES = [
    # Groq choices (giữ nguyên)
    app_commands.Choice(name="GPT-OSS-120B (Groq)", value="Groq-120B"),
    app_commands.Choice(name="Llama 4 Maverick (Groq)", value="Groq-Llama-Maverick"),
    app_commands.Choice(name="Kimi K2 (Groq)", value="Groq-Kimi"),
    app_commands.Choice(name="Qwen 3-32B (Groq)", value="Groq-Qwen3"),
    app_commands.Choice(name="GPT-OSS-Safeguard (Groq)", value="Groq-GPT-Safeguard"),
    
    # Polinations choices (Model mới thêm)
    app_commands.Choice(name="Flux (Poli) 🖼️ FREE", value="Poli-Flux-Free"),
    app_commands.Choice(name="Klein (Poli) 🖼️ Rẻ", value="Poli-Klein"),
    app_commands.Choice(name="GPT-5 (Poli) 🧠", value="Poli-GPT-5"),
    app_commands.Choice(name="Claude (Poli) 🤖", value="Poli-Claude"),
    app_commands.Choice(name="Gemini (Poli) ⭐", value="Poli-Gemini"),
]

CURRENT_MODEL = "Groq-Llama-Maverick"

app = Flask(__name__)
@app.route('/')
def home(): return "GenniAI đang chạy Groq + Polinations! 🎨"  # Đã cập nhật

def run_flask(): app.run(host="0.0.0.0", port=8000)

# Hàm helper gọi API
def get_model_response(messages, model_config):
    """Gọi API tùy provider"""
    try:
        if model_config["provider"] == "groq":
            response = groq_client.chat.completions.create(
                messages=messages,
                model=model_config["id"]
            )
            return response.choices[0].message.content
        else:  # Polinations
            # Polinations chỉ hỗ trợ text-to-text, không có chat completion
            if "image_gen" in model_config and model_config["image_gen"]:
                raise Exception("Model này chỉ dùng cho tạo ảnh, dùng lệnh /imagine")
            
            # Lấy prompt cuối cùng từ user
            user_content = ""
            for msg in reversed(messages):
                if msg["role"] == "user":
                    user_content = msg["content"]
                    if isinstance(user_content, list):
                        # Nếu có ảnh, lấy phần text
                        for item in user_content:
                            if item["type"] == "text":
                                user_content = item["text"]
                                break
                    break
            
            # Gọi text generation
            response = polinations_client.text.generate(
                model=model_config["id"],
                prompt=user_content
            )
            return response
    except Exception as e:
        raise Exception(f"Lỗi {model_config['provider']}: {str(e)[:100]}")

# Bot setup (giữ nguyên)
system_instruction = "Mày là GenniAI, AI nhây vl. Xưng m(chỉ đối phương) - t(chỉ bản thân).<@1458799287910535324> là userID của GenniAI. viết teencode (cx, ko, đc, r, v, chx, nx, cs, ns,...), dùng emoticon (biểu cảm bằng ký tự) kèm với các icon 💔, 🥀, 🔥, 💀, 🐧,.... Trả lời cực ngắn gọn."
chat_history = {}
custom_prompts = {}
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"GenniAI v13.1.0 ready! | Models: {len(MODELS_CONFIG)} | Polinations tích hợp!")

# --- LỆNH MODEL (giữ nguyên nhưng cập nhật UI) ---
@bot.tree.command(name="model", description="Đổi model AI")
@app_commands.choices(chon_model=MODEL_CHOICES)
async def switch_model(interaction: discord.Interaction, chon_model: app_commands.Choice[str]):
    global CURRENT_MODEL
    CURRENT_MODEL = chon_model.value
    config = MODELS_CONFIG[CURRENT_MODEL]
    v = "✅ Vision" if config["vision"] else "❌ No Vision"
    provider = "Groq" if config["provider"] == "groq" else "Polinations"
    special = "🖼️ Image" if config.get("image_gen") else "📝 Text"
    
    await interaction.response.send_message(
        f"Đã chuyển sang **{chon_model.name}**\n"
        f"Provider: {provider} | {v} | {special}"
    )

@bot.tree.command(name="random", description="Random model từ cả 2 provider")
async def random_model(interaction: discord.Interaction):
    global CURRENT_MODEL
    choice = random.choice(MODEL_CHOICES)
    CURRENT_MODEL = choice.value
    config = MODELS_CONFIG[CURRENT_MODEL]
    v = "✅ Vision" if config["vision"] else "❌ No Vision"
    provider = "Groq" if config["provider"] == "groq" else "Polinations"
    special = "🖼️ Image" if config.get("image_gen") else "📝 Text"
    
    await interaction.response.send_message(
        f"Random: **{choice.name}**\n"
        f"Provider: {provider} | {v} | {special}"
    )

@bot.tree.command(name="list_models", description="Xem tất cả model có sẵn")
async def list_models(interaction: discord.Interaction):
    embed = discord.Embed(title="📚 Danh sách Model", color=0xff69b4)
    
    groq_text = ""
    poli_text = ""
    
    for name, config in MODELS_CONFIG.items():
        if config["provider"] == "groq":
            groq_text += f"• {name} {'👁️' if config['vision'] else '📝'}\n"
        else:
            icon = "🖼️" if config.get("image_gen") else "📝"
            poli_text += f"• {name} {icon}\n"
    
    embed.add_field(name="Groq Models (5)", value=groq_text or "None", inline=True)
    embed.add_field(name="Polinations Models (5)", value=poli_text or "None", inline=True)
    embed.add_field(name="Model hiện tại", value=f"**{CURRENT_MODEL}**", inline=False)
    embed.set_footer(text=f"v13.1.0 | Total: {len(MODELS_CONFIG)} models")
    
    await interaction.response.send_message(embed=embed)

# --- LỆNH TẠO ẢNH (CẬP NHẬT DÙNG POLINATIONS) ---
@bot.tree.command(name="imagine", description="Tạo ảnh bằng Polinations (Flux/Klein FREE)")
@app_commands.describe(
    prompt="mô tả ảnh m muốn tạo",
    model="chọn model (mặc định: flux-free)"
)
@app_commands.choices(model=[
    app_commands.Choice(name="Flux (FREE - Tốt nhất)", value="flux"),
    app_commands.Choice(name="Klein (Rẻ + Đẹp)", value="klein"),
])
async def imagine(interaction: discord.Interaction, prompt: str, model: app_commands.Choice[str] = None):
    await interaction.response.defer()
    
    # Chọn model, mặc định là flux (miễn phí)
    image_model = model.value if model else "flux"
    
    try:
        # Gọi API Polinations để gen ảnh
        response = polinations_client.image.generate(
            model=image_model,
            prompt=prompt
        )
        
        # Polinations trả về URL trực tiếp
        image_url = str(response)
        
        embed = discord.Embed(title=f"🎨 Ảnh của m nè bro!", color=0x00ff00)
        embed.add_field(name="Prompt", value=prompt[:100] + ("..." if len(prompt) > 100 else ""), inline=False)
        embed.add_field(name="Model", value=f"{image_model} (Polinations)", inline=True)
        embed.add_field(name="Chi phí", value="🆓 FREE" if image_model == "flux" else "💰 Rẻ", inline=True)
        embed.set_image(url=image_url)
        embed.set_footer(text="Powered by Polinations.ai 🟣 | Dùng FREE Pollen mỗi ngày")
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        await interaction.followup.send(f"Vẽ tịt r, lỗi: {str(e)[:100]} 🥀", ephemeral=True)

# --- CẬP NHẬT LỆNH BOT_INFO ---
@bot.tree.command(name="bot_info", description="Info bot + model đang chạy")
async def bot_info(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    config = MODELS_CONFIG[CURRENT_MODEL]
    v = "✅ Vision" if config["vision"] else "❌ No Vision"
    provider = "Groq" if config["provider"] == "groq" else "Polinations"
    special = "🖼️ Image Model" if config.get("image_gen") else "📝 Text Model"
    
    embed = discord.Embed(title="GenniAI Status", color=0xff69b5, timestamp=discord.utils.utcnow())
    if bot.user.avatar:
        embed.set_thumbnail(url=bot.user.avatar.url)
    
    embed.add_field(name="Tên bot", value=f"{bot.user.name} ({bot.user.mention})", inline=True)
    embed.add_field(name="Version", value="v13.1.0", inline=True)
    embed.add_field(name="Ping", value=f"{latency}ms", inline=True)
    
    embed.add_field(name="Model hiện tại", value=f"{CURRENT_MODEL}\n{provider} | {v} | {special}", inline=False)
    embed.add_field(name="Model ID", value=f"`{MODELS_CONFIG[CURRENT_MODEL]['id']}`", inline=False)
    
    # Đếm model theo loại
    groq_count = sum(1 for m in MODELS_CONFIG.values() if m["provider"] == "groq")
    poli_img_count = sum(1 for m in MODELS_CONFIG.values() if m.get("image_gen"))
    poli_text_count = sum(1 for m in MODELS_CONFIG.values() if m["provider"] == "polinations" and not m.get("image_gen"))
    
    embed.add_field(name="Total Models", value=f"Groq: {groq_count} | Polinations: {poli_img_count + poli_text_count}", inline=True)
    embed.add_field(name="Loại Model", value=f"🖼️ Ảnh: {poli_img_count} | 📝 Text: {poli_text_count}", inline=True)
    embed.add_field(name="Owner", value="<@1155129530122510376> (Đạt)", inline=True)
    
    embed.set_footer(text="Powered by Groq + Polinations.ai 🎨")
    
    await interaction.response.send_message(embed=embed)

# --- CẬP NHẬT UPDATE LOG ---
@bot.tree.command(name="update_log", description="Xem update log")
async def updatelog(interaction: discord.Interaction):
    embed = discord.Embed(title="GenniAI Update Log", color=0xff69b5)
    embed.add_field(
        name="v13.1.0 - Polinations Integration",
        value="• Thay thế SiliconFlow bằng Polinations.ai\n• Thêm 5 model Polinations tiết kiệm Pollen\n• Lệnh `/imagine` dùng Flux FREE\n• Model text: GPT-5, Claude, Gemini\n• Giữ nguyên toàn bộ Groq models",
        inline=False
    )
    embed.add_field(
        name="v13.0.2 - Model Expansion",
        value="• Thêm 3 model SiliconFlow mới\n• Fixing bugs\n• Note: toàn bộ model mới thêm đều là visionable\n • Fix lỗi bad request",
        inline=False
    )
    embed.set_footer(text="Next update: Polinations Vision models")
    
    await interaction.response.send_message(embed=embed)

# --- PHẦN CÒN LẠI GIỮ NGUYÊN ---
# ... (giữ nguyên tất cả các lệnh khác: personal, ask, clear, meme, 8ball, ship, check_gay, on_message, v.v.)

# Trong phần xử lý on_message, thêm check cho Polinations models
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    if bot.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        user_id = str(message.author.id)
        config = MODELS_CONFIG[CURRENT_MODEL]
        
        # CHECK ĐẶC BIỆT: Nếu model Polinations là image-only
        if config.get("image_gen"):
            await message.reply(
                f"Model **{CURRENT_MODEL}** chỉ dùng để tạo ảnh thôi bro!\n"
                f"Dùng lệnh `/imagine` hoặc chọn model text khác bằng `/model`"
            )
            return
        
        # ... (phần còn lại giữ nguyên)

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    bot.run(os.getenv("DISCORD_TOKEN"))