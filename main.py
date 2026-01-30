import discord, random, os, base64, aiohttp, asyncio
from discord.ext import commands
from discord import app_commands
from groq import Groq
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

load_dotenv()

# Khởi tạo clients
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# CẤU HÌNH MODEL - GỘP GROQ + POLLINATIONS (Dùng ID chuẩn m gửi)
# CẤU HÌNH MODEL - ĐÃ THÊM KIMI VÀ CHO SAFEGUARD COOK 💀🔥
MODELS_CONFIG = {
    # --- Groq ---
    "Groq-Llama-Maverick": {"id": "meta-llama/llama-4-maverick-17b-128e-instruct", "vision": True, "provider": "groq"},
    "Groq-Kimi": {"id": "moonshotai/kimi-k2-instruct-0905", "vision": False, "provider": "groq"}, # Kimi của m đây 🌙
    "Groq-Qwen3": {"id": "qwen/qwen3-32b", "vision": False, "provider": "groq"},
    
    # --- Pollinations (Hàng ngon bổ rẻ) ---
    "Poli-Gemini-Flash": {"id": "gemini", "vision": False, "provider": "pollinations"},
    "Poli-GPT-5-Mini": {"id": "openai", "vision": False, "provider": "pollinations"},
    "Poli-DeepSeek-V3": {"id": "deepseek", "vision": False, "provider": "pollinations"},
    "Poli-Mistral-Small": {"id": "mistral", "vision": False, "provider": "pollinations"},
}

MODEL_CHOICES = [
    app_commands.Choice(name="Kimi K2 Instruct (Groq) 🌙", value="Groq-Kimi"),
    app_commands.Choice(name="Llama 4 Maverick (Groq) 👁️", value="Groq-Llama-Maverick"),
    app_commands.Choice(name="Gemini Flash (Poli) ⚡", value="Poli-Gemini-Flash"),
    app_commands.Choice(name="GPT-5 Mini (Poli) 🤖", value="Poli-GPT-5-Mini"),
    app_commands.Choice(name="DeepSeek V3 (Poli) 🧠", value="Poli-DeepSeek-V3"),
    app_commands.Choice(name="Mistral Small (Poli) 🍃", value="Poli-Mistral-Small"),
]
CURRENT_MODEL = "Poli-Gemini-Flash"
system_instruction = "Mày là GenniAI, AI nhây vl. Xưng m(đối phương)-t(bản thân). Viết teencode, dùng emoticon kèm 💔, 🥀, 🔥, 💀, 🐧. Trả lời cực ngắn."
chat_history, custom_prompts = {}, {}

app = Flask(__name__)
@app.route('/')
def home(): return "GenniAI is Up! 🔥"
def run_flask(): app.run(host="0.0.0.0", port=8000)

async def get_model_response(messages, model_config):
    try:
        if model_config["provider"] == "groq":
            response = groq_client.chat.completions.create(messages=messages, model=model_config["id"])
            return response.choices[0].message.content
        else:
            api_key = os.getenv("POLLINATIONS_API_KEY")
            headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
            payload = {"messages": messages, "model": model_config["id"], "seed": random.randint(0, 999999)}
            async with aiohttp.ClientSession() as session:
                async with session.post("https://text.pollinations.ai/", json=payload, headers=headers) as resp:
                    return await resp.text()
    except Exception as e: return f"Lỗi r m: {str(e)[:50]}"

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"GenniAI v15 ready! 🔥")

# --- CMDS MODEL ---
@bot.tree.command(name="model", description="Đổi model AI")
@app_commands.choices(chon_model=MODEL_CHOICES)
async def switch_model(interaction, chon_model: app_commands.Choice[str]):
    global CURRENT_MODEL
    CURRENT_MODEL = chon_model.value
    await interaction.response.send_message(f"Đã chuyển sang **{chon_model.name}** 🐧")

@bot.tree.command(name="list_models", description="Xem tất cả model")
async def list_models(interaction):
    embed = discord.Embed(title="📚 Danh sách Model", color=0xff69b4)
    groq_t = "\n".join([f"• {k}" for k, v in MODELS_CONFIG.items() if v["provider"] == "groq"])
    poli_t = "\n".join([f"• {k}" for k, v in MODELS_CONFIG.items() if v["provider"] == "pollinations"])
    embed.add_field(name="Groq", value=groq_t or "None").add_field(name="Pollinations", value=poli_t or "None")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="bot_info", description="Info bot chi tiết")
async def bot_info(interaction):
    latency = round(bot.latency * 1000)
    embed = discord.Embed(title="GenniAI Status", color=0xff69b5, timestamp=discord.utils.utcnow())
    embed.add_field(name="Tên bot", value=f"{bot.user.mention}", inline=True)
    embed.add_field(name="Ping", value=f"{latency}ms", inline=True)
    embed.add_field(name="Model hiện tại", value=f"**{CURRENT_MODEL}**", inline=False)
    embed.add_field(name="Provider", value=MODELS_CONFIG[CURRENT_MODEL]["provider"].upper(), inline=True)
    embed.set_footer(text="Powered by Groq + Pollinations 💀")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="update_log", description="Xem nhật ký cập nhật")
async def update_log(interaction):
    embed = discord.Embed(title="GenniAI Update Log", color=0xff69b5)
    embed.add_field(name="v15.0.0 - Pollinations Era", value="• Thay SiliconFlow thành Pollinations (Bú API Key xịn)\n• Thêm Gemini 3 Flash, GPT-5 Mini, Claude 4.5\n• Giữ nguyên toàn bộ cmd cũ cho m đỡ dỗi 🐧", inline=False)
    embed.add_field(name="v13.0.2", value="• Thêm model SF cũ (Đã khai tử)\n• Fix lỗi cụt lủn 🥀", inline=False)
    await interaction.response.send_message(embed=embed)

# --- GIỮ NGUYÊN TẤT CẢ CMD VUI VẺ CÒN LẠI ---
@bot.tree.command(name="imagine")
async def imagine(interaction, prompt: str):
    await interaction.response.defer()
    url = f"https://image.pollinations.ai/prompt/{prompt.replace(' ', '%20')}?nologo=true"
    await interaction.followup.send(embed=discord.Embed(title="🎨 Ảnh nè").set_image(url=url))

@bot.tree.command(name="meme")
async def meme(interaction):
    await interaction.response.defer()
    async with aiohttp.ClientSession() as s:
        async with s.get("https://phimtat.vn/api/random-meme/") as r:
            await interaction.followup.send(embed=discord.Embed().set_image(url=str(r.url)))

@bot.tree.command(name="ship")
async def ship(interaction, user1: discord.Member, user2: discord.Member):
    pts = random.randint(0, 100)
    await interaction.response.send_message(f"OTP {user1.display_name} x {user2.display_name}: {pts}% 🔥")

@bot.tree.command(name="check_gay")
async def check_gay(interaction, target: discord.Member):
    await interaction.response.send_message(f"{target.display_name} gay {random.randint(0,100)}% 🏳️‍🌈")

@bot.tree.command(name="8ball")
async def eight_ball(interaction, question: str):
    ans = random.choice(["có", "ko", "cút", "hên xui"])
    await interaction.response.send_message(f"🎱 **{question}**: {ans}")

@bot.tree.command(name="clear")
async def clear(interaction):
    chat_history[str(interaction.user.id)] = []
    await interaction.response.send_message("Xoá sạch r! 🥀")

@bot.event
async def on_message(message):
    if message.author.bot: return
    
    # Check xem có phải DM hoặc có tag bot ko 🐧
    is_dm = isinstance(message.channel, discord.DMChannel)
    is_mentioned = bot.user.mentioned_in(message)
    
    if is_mentioned or is_dm:
        uid = str(message.author.id)
        if uid not in chat_history: 
            chat_history[uid] = [{"role": "system", "content": custom_prompts.get(uid, system_instruction)}]
        
        async with message.channel.typing():
            try:
                # Gửi kèm lịch sử chat cho nó khôn 🧠
                history = chat_history[uid] + [{"role": "user", "content": message.content}]
                reply = await get_model_response(history, MODELS_CONFIG[CURRENT_MODEL])
                
                reply = reply.split("</think>")[-1].strip() if "</think>" in reply else reply
                
                # Lưu lại ký ức 🥀
                chat_history[uid].append({"role": "user", "content": message.content})
                chat_history[uid].append({"role": "assistant", "content": reply})
                chat_history[uid] = chat_history[uid][-10:] # Giữ 10 câu gần nhất
                
                await message.reply(reply[:1900])
            except Exception as e: 
                await message.reply(f"Lỗi r m: {e} 💀")

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    bot.run(os.getenv("DISCORD_TOKEN"))