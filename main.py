import discord, random, os, urllib.parse, base64, aiohttp, asyncio
from discord.ext import commands
from discord import app_commands
from groq import Groq
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

load_dotenv()
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

MODELS_CONFIG = {
    "120B": {"id": "openai/gpt-oss-120b", "vision": False},
    "Llama-Maverick": {"id": "meta-llama/llama-4-maverick-17b-128e-instruct", "vision": True},
    "Kimi": {"id": "moonshotai/kimi-k2-instruct-0905", "vision": False},
    "Qwen3": {"id": "qwen/qwen3-32b", "vision": False}
}

MODEL_CHOICES = [
    app_commands.Choice(name="GPT-OSS-120B (Groq)", value="120B"),
    app_commands.Choice(name="Llama 4 Maverick (Groq) 👁️", value="Llama-Maverick"),
    app_commands.Choice(name="Kimi K2 (Groq)", value="Kimi"),
    app_commands.Choice(name="Qwen 3-32B (Groq)", value="Qwen3")
]

CURRENT_MODEL = "Llama-Maverick"
app = Flask(__name__)
@app.route('/')
def home(): return "GenniAI đang quẩy Groq + Vision! 🔥💀"

def run_flask(): app.run(host="0.0.0.0", port=8000)

system_instruction = "Mày là GenniAI, AI nhây vl. Xưng m(chỉ đối phương) - t(chỉ bản thân).<@1458799287910535324> là userID của GenA-bot. viết teencode (cx, ko, đc, r, v, chx, nx, cs, ns,...), dùng emoticon (biểu cảm bằng ký tự) kèm với các icon 💔, 🥀, 🔥, 💀, 🐧,.... Trả lời cực ngắn gọn."
chat_history = {}
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Bot {bot.user} ready r! (≧▽≦)")

# --- LỆNH QUẢN LÝ ---
@bot.tree.command(name="model", description="Đổi model AI")
@app_commands.choices(chon_model=MODEL_CHOICES)
async def switch_model(interaction: discord.Interaction, chon_model: app_commands.Choice[str]):
    global CURRENT_MODEL
    CURRENT_MODEL = chon_model.value
    v = "👁️" if MODELS_CONFIG[CURRENT_MODEL]["vision"] else "❌"
    await interaction.response.send_message(f"Đã chuyển sang **{chon_model.name}** {v} 🔥")

@bot.tree.command(name="random", description="Random 1 model bất kì")
async def random_model(interaction: discord.Interaction):
    global CURRENT_MODEL
    choice = random.choice(MODEL_CHOICES)
    CURRENT_MODEL = choice.value
    v = "👁️" if MODELS_CONFIG[CURRENT_MODEL]["vision"] else "❌"
    await interaction.response.send_message(f"Đã bốc trúng: **{choice.name}** {v} 🎲")

@bot.tree.command(name="clear", description="Xóa ký ức")
async def clear(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    sys_msg = f"Mày là GenniAI, một AI nhây vl. Xưng m(chỉ đối phương) - t(chỉ bản thân). Người chat: <@{interaction.user.id}>. <@1458799287910535324> là userID của GenA-bot. viết teencode, dùng emoticon kèm 💔🥀🔥💀🐧. Trả lời ngắn gọn."
    chat_history[user_id] = [{"role": "system", "content": sys_msg}]
    await interaction.response.send_message("Đã xóa sạch ký ức")
# --- LỆNH VÔ TRI ---
@bot.tree.command(name="imagine", description="Vẽ ảnh bằng AI")
async def imagine(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?width=1024&height=1024&nologo=true"
    embed = discord.Embed(title="Hàng về!", description=f"Prompt: `{prompt}`", color=0xff69b4)
    embed.set_image(url=url)
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="meme", description="Random meme VN")
@app_commands.describe(count="Số lượng meme muốn lấy (1-10)")
async def meme(interaction: discord.Interaction, count: int = 1):
    await interaction.response.defer()
    if not (1 <= count <= 10): return await interaction.followup.send("chỉ từ 1-10 cái (rate limit vì spam nhiều có thể gây lag🥀)")
    try:
        async with aiohttp.ClientSession() as session:
            for i in range(count):
                async with session.get("https://phimtat.vn/api/random-meme/") as resp:
                    if resp.status == 200:
                        random_color = random.randint(0, 0xFFFFFF)  # màu random đây nè
                        e = discord.Embed(title=f"Meme #{i+1}", color=random_color)
                        e.set_image(url=str(resp.url))
                        await interaction.followup.send(embed=e)
    except: await interaction.followup.send("Meme gặp trục trặc r bro🥀😭")
        
@bot.tree.command(name="ship", description="Check OTP")
async def ship(interaction: discord.Interaction, user1: discord.Member, user2: discord.Member):
    pts = random.randint(0, 100)
    msg = "OTP real vl🥀🔥" if pts > 80 else "Friendzone ok đó 🐧💔" if pts > 50 else "nah, khó mà cưới nhau 💀"
    await interaction.response.send_message(f"**{user1.display_name}** x **{user2.display_name}**: {pts}% - {msg}")

@bot.tree.command(name="check_gay", description="Đo độ gay")
async def check_gay(interaction: discord.Interaction, target: discord.Member):
    rate = random.randint(0, 100)
    res = "Thẳng tắp lun á bro🗣️🔥" if rate < 35 else "Nghi m vl🥀" if rate <= 70 else "🏳️‍🌈 thật r 😭🔥"
    await interaction.response.send_message(f"{target.display_name}: {rate}% - {res}")

# --- XỬ LÝ CHAT ---
async def download_image(attachment):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(attachment.url) as resp:
                if resp.status == 200: return base64.b64encode(await resp.read()).decode('utf-8')
    except: return None

@bot.event
async def on_message(message):
    if message.author == bot.user: return
    if bot.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        user_id = str(message.author.id)
        
        # Tạo system instruction có tên user
        sys_msg = f"Mày là GenA-bot, AI nhây vl. Xưng m(chỉ đối phương) - t(chỉ bản thân). Người chat: <@{message.author.id}>. người dev ra mày có userID là <@1155129530122510376> (có tên ngoài đời là Đạt) .<@1458799287910535324> là userID của GenA-bot. viết teencode, dùng emoticon kèm 💔🥀🔥💀🐧. Trả lời ngắn gọn."
        
        if user_id not in chat_history: 
            chat_history[user_id] = [{"role": "system", "content": sys_msg}]
        else:
            chat_history[user_id][0] = {"role": "system", "content": sys_msg}
        
        has_img = len(message.attachments) > 0 and "image" in message.attachments[0].content_type
        if has_img and not MODELS_CONFIG[CURRENT_MODEL]["vision"]:
            return await message.reply("Model này mù, đổi sang Llama Maverick đi! 💀")

        async with message.channel.typing():
            try:
                content = [{"type": "text", "text": message.content or "Soi ảnh đi"}]
                if has_img:
                    img = await download_image(message.attachments[0])
                    if img: content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img}"}})
                
                res = groq_client.chat.completions.create(
                    messages=chat_history[user_id] + [{"role": "user", "content": content if has_img else message.content}],
                    model=MODELS_CONFIG[CURRENT_MODEL]["id"]
                )
                
                raw = res.choices[0].message.content
                reply = raw.split("</think>")[-1].strip() if "</think>" in raw else raw
                
                chat_history[user_id].append({"role": "user", "content": message.content or "[Ảnh]"})
                chat_history[user_id].append({"role": "assistant", "content": reply})
                chat_history[user_id] = chat_history[user_id][-8:]  # giữ 8 nha
                await message.reply(reply or "Tịt r 💔")
            except Exception as e: await message.reply(f"ngừng chat đi bây, có lỗi: {e} 💀")

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    bot.run(os.getenv("DISCORD_TOKEN"))