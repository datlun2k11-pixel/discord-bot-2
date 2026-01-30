import discord, random, os, base64, aiohttp, asyncio
from discord.ext import commands
from discord import app_commands
from groq import Groq
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

load_dotenv()

# Khởi tạo client
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# CẤU HÌNH MODEL - GỘP GROQ + POLLINATIONS
MODELS_CONFIG = {
    "Groq-120B": {"id": "openai/gpt-oss-120b", "vision": False, "provider": "groq"},
    "Groq-Llama-Maverick": {"id": "meta-llama/llama-4-maverick-17b-128e-instruct", "vision": True, "provider": "groq"},
    "Groq-Kimi": {"id": "moonshotai/kimi-k2-instruct-0905", "vision": False, "provider": "groq"},
    "Groq-Qwen3": {"id": "qwen/qwen3-32b", "vision": False, "provider": "groq"},
    "Groq-GPT-Safeguard": {"id": "openai/gpt-oss-safeguard-20b", "vision": False, "provider": "groq"},
            # --- Pollinations Models (Hàng vừa test, ko chạy t đi đầu xuống đất 💀) ---
    "Poli-Llama-3.3": {"id": "openai", "vision": False, "provider": "pollinations"},
    "Poli-DeepSeek-R1": {"id": "deepseek", "vision": False, "provider": "pollinations"},
    "Poli-Mistral": {"id": "mistral", "vision": False, "provider": "pollinations"},
    "Poli-Qwen-2.5-72B": {"id": "qwen", "vision": False, "provider": "pollinations"},
}

MODEL_CHOICES = [
    app_commands.Choice(name="GPT-OSS-120B (Groq)", value="Groq-120B"),
    app_commands.Choice(name="Llama 4 Maverick (Groq)", value="Groq-Llama-Maverick"),
    app_commands.Choice(name="Kimi K2 (Groq)", value="Groq-Kimi"),
    app_commands.Choice(name="Qwen 3-32B (Groq)", value="Groq-Qwen3"),
    app_commands.Choice(name="GPT-OSS-Safeguard (Groq)", value="Groq-GPT-Safeguard"),
    app_commands.Choice(name="Llama 3.3 70B (Poli) 🔥", value="Poli-Llama-3.3"),
    app_commands.Choice(name="DeepSeek R1 (Poli) 🧠", value="Poli-DeepSeek-R1"),
    app_commands.Choice(name="Mistral Large (Poli) 🍃", value="Poli-Mistral"),
    app_commands.Choice(name="Qwen 2.5 72B (Poli) 🍵", value="Poli-Qwen-2.5-72B"),
]

CURRENT_MODEL = "Groq-Llama-Maverick"

app = Flask(__name__)
@app.route('/')
def home(): return "GenniAI đang chạy Groq + Pollinations! 🔥"
def run_flask(): app.run(host="0.0.0.0", port=8000)

async def get_model_response(messages, model_config):
    try:
        if model_config["provider"] == "groq":
            response = groq_client.chat.completions.create(messages=messages, model=model_config["id"])
            return response.choices[0].message.content
        else:
            async with aiohttp.ClientSession() as session:
                payload = {"messages": messages, "model": model_config["id"], "seed": random.randint(0, 99999)}
                async with session.post("https://text.pollinations.ai/", json=payload) as resp:
                    return await resp.text()
    except Exception as e:
        raise Exception(f"Lỗi {model_config['provider']}: {str(e)[:100]}")

system_instruction = "Mày là GenniAI, AI nhây vl. Xưng m(chỉ đối phương) - t(chỉ bản thân). viết teencode (cx, ko, đc, r, v, chx, nx, cs, ns,...), dùng emoticon kèm 💔, 🥀, 🔥, 💀, 🐧. Trả lời cực ngắn gọn."
chat_history = {}
custom_prompts = {}
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"GenniAI v15 ready! 🔥")

@bot.tree.command(name="model", description="Đổi model AI")
@app_commands.choices(chon_model=MODEL_CHOICES)
async def switch_model(interaction: discord.Interaction, chon_model: app_commands.Choice[str]):
    global CURRENT_MODEL
    CURRENT_MODEL = chon_model.value
    await interaction.response.send_message(f"Đã chuyển sang **{chon_model.name}** 🐧")

@bot.tree.command(name="random", description="Random model")
async def random_model(interaction: discord.Interaction):
    global CURRENT_MODEL
    choice = random.choice(MODEL_CHOICES)
    CURRENT_MODEL = choice.value
    await interaction.response.send_message(f"Random trúng: **{choice.name}** 🎲")

@bot.tree.command(name="list_models", description="Xem tất cả model")
async def list_models(interaction: discord.Interaction):
    embed = discord.Embed(title="📚 Danh sách Model", color=0xff69b4)
    groq_t = "\n".join([f"• {k}" for k, v in MODELS_CONFIG.items() if v["provider"] == "groq"])
    poli_t = "\n".join([f"• {k}" for k, v in MODELS_CONFIG.items() if v["provider"] == "pollinations"])
    embed.add_field(name="Groq", value=groq_t or "None")
    embed.add_field(name="Pollinations", value=poli_t or "None")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="personal", description="Set sys prompt riêng")
async def personal(interaction: discord.Interaction, prompt: str = None):
    uid = str(interaction.user.id)
    if not prompt:
        custom_prompts.pop(uid, None)
        await interaction.response.send_message("Đã reset prompt gốc 🥀")
    else:
        custom_prompts[uid] = prompt
        await interaction.response.send_message(f"Đã set prompt mới: `{prompt[:50]}...` 🔥")

@bot.tree.command(name="ask", description="Hỏi bí mật (ephemeral)")
async def ask(interaction: discord.Interaction, question: str):
    await interaction.response.defer(ephemeral=True)
    uid = str(interaction.user.id)
    sys = custom_prompts.get(uid, system_instruction)
    reply = await get_model_response([{"role":"system","content":sys},{"role":"user","content":question}], MODELS_CONFIG[CURRENT_MODEL])
    await interaction.followup.send(f"**Q:** {question}\n**A:** {reply}", ephemeral=True)

@bot.tree.command(name="bot_info", description="Info bot")
async def bot_info(interaction: discord.Interaction):
    embed = discord.Embed(title="GenniAI Status", color=0xff69b5)
    embed.add_field(name="Model hiện tại", value=CURRENT_MODEL)
    embed.add_field(name="Ping", value=f"{round(bot.latency * 1000)}ms")
    embed.set_footer(text="Powered by Groq + Pollinations 💀")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="imagine", description="Tạo ảnh (Pollinations)")
async def imagine(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    seed = random.randint(0, 99999)
    url = f"https://image.pollinations.ai/prompt/{prompt.replace(' ', '%20')}?seed={seed}&nologo=true"
    embed = discord.Embed(title="🎨 Ảnh của m nè").set_image(url=url)
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="clear", description="Xóa ký ức chat")
async def clear(interaction: discord.Interaction):
    chat_history[str(interaction.user.id)] = []
    await interaction.response.send_message("Sạch bóng kin kít r m 🥀")

@bot.tree.command(name="update_log", description="Xem update log")
async def updatelog(interaction: discord.Interaction):
    embed = discord.Embed(title="GenniAI Update Log", color=0xff69b5)
    embed.add_field(name="v15.0.0", value="• Thay SiliconFlow thành Pollinations (Free vcl)\n• Giữ nguyên toàn bộ cmd cũ cho thằng chủ đỡ chửi 🐧")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="meme", description="Random meme VN")
async def meme(interaction: discord.Interaction):
    await interaction.response.defer()
    async with aiohttp.ClientSession() as session:
        async with session.get("https://phimtat.vn/api/random-meme/") as resp:
            embed = discord.Embed().set_image(url=str(resp.url))
            await interaction.followup.send(embed=embed)

@bot.tree.command(name="8ball", description="Hỏi yes/no")
async def eight_ball(interaction: discord.Interaction, question: str):
    ans = random.choice(["có nha 🔥", "chx đâu m ơi 💔", "có cl 😭🥀", "chắc chắn rồi đó m 🐧", "đừng mơ nữa 💀"])
    await interaction.response.send_message(f"🎱 **{question}**: {ans}")

@bot.tree.command(name="ship", description="Check OTP")
async def ship(interaction: discord.Interaction, user1: discord.Member, user2: discord.Member):
    pts = random.randint(0, 100)
    await interaction.response.send_message(f"OTP {user1.display_name} x {user2.display_name}: {pts}% 🔥")

@bot.tree.command(name="check_gay", description="Đo độ gay")
async def check_gay(interaction: discord.Interaction, target: discord.Member):
    await interaction.response.send_message(f"{target.display_name}: {random.randint(0, 100)}% 🏳️‍🌈")

@bot.event
async def on_message(message):
    if message.author.bot or not bot.user.mentioned_in(message): return
    uid = str(message.author.id)
    if uid not in chat_history: chat_history[uid] = [{"role": "system", "content": custom_prompts.get(uid, system_instruction)}]
    async with message.channel.typing():
        try:
            chat_history[uid].append({"role": "user", "content": message.content})
            reply = await get_model_response(chat_history[uid], MODELS_CONFIG[CURRENT_MODEL])
            reply = reply.split("</think>")[-1].strip() if "</think>" in reply else reply
            chat_history[uid].append({"role": "assistant", "content": reply})
            chat_history[uid] = chat_history[uid][-10:]
            await message.reply(reply[:1900])
        except Exception as e: await message.reply(f"Lỗi: {e} 🥀")

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    bot.run(os.getenv("DISCORD_TOKEN"))