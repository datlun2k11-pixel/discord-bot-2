# Coded and bugs fix by AI 
import discord
import random
import os
import asyncio
import aiohttp
import base64
from discord.ext import tasks
from discord.ext import commands
from discord import app_commands
from groq import Groq
from ollama import AsyncClient
from dotenv import load_dotenv
from flask import Flask
from threading import Thread
import datetime
import pytz

load_dotenv()

# Clients - Groq và Ollama Cloud xịn đét 🥀
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
ollama_client = AsyncClient(host="https://api.ollama.com", headers={"Authorization": f"Bearer {os.getenv('OLLAMA_API_KEY')}"})

# Config Model: Thêm mấy con hàng Cloud m mún vào đây 💀
MODELS_CONFIG = {
    "Groq-Llama-Scout": {"id": "meta-llama/llama-4-scout-17b-16e-instruct", "provider": "groq", "vision": True},
    "GPT-OSS-120B": {"id": "openai/gpt-oss-120b", "provider": "groq", "vision": False},
    "Groq-Kimi": {"id": "moonshotai/kimi-k2-instruct-0905", "provider": "groq", "vision": False},
    "Groq-Qwen3": {"id": "qwen/qwen3-32b", "provider": "groq", "vision": False},
    "Ollama-Kimi-Cloud": {"id": "kimi-k2.5:cloud", "provider": "ollama", "vision": True},
    "Deepseek-v3.1": {"id": "deepseek-v3.1:671b-cloud", "provider": "ollama", "vision": False},
    "Qwen3.5-397b": {"id": "qwen3.5:397b-cloud", "provider": "ollama", "vision": True}
}

# Trả về bth cho m đây, ko thèm dùng list comprehension nữa ☠️
MODEL_CHOICES = [
    app_commands.Choice(name="Llama 4 Scout (GROQ)", value="Groq-Llama-Scout"),
    app_commands.Choice(name="GPT-OSS-120B (GROQ)", value="GPT-OSS-120B"),
    app_commands.Choice(name="Kimi K2 Instruct (GROQ)", value="Groq-Kimi"),
    app_commands.Choice(name="Qwen 3 32B (GROQ)", value="Groq-Qwen3"),
    app_commands.Choice(name="Kimi K2.5 (OLLAMA)", value="Ollama-Kimi-Cloud"),
    app_commands.Choice(name="Deepseek V3.1 (OLLAMA)", value="Deepseek-v3.1"),
    app_commands.Choice(name="Qwen3.5-397B-A17B (OLLAMA)", value="Qwen3.5-397b")
]
CURRENT_MODEL = "Groq-Llama-Maverick"

GIFS = [
    "https://media2.giphy.com/media/v1.Y2lkPTZjMDliOTUyYml6ZW1laGgyd2xrZDY4MnAwcDQzMjFqc296a3hya2tub3c3dzJyMiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/O4fENAKIGz0zJs9dg9/giphy.gif",
    "https://media0.giphy.com/media/v1.Y2lkPTZjMDliOTUydTB4OWhrZ2hhbHFuaTJpbnl1eXVhbmx2cDJwcDg0ZG12NTN6aHR6bSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/LR5GeZFCwDRcpG20PR/giphy.gif",
    "https://media3.giphy.com/media/v1.Y2lkPTZjMDliOTUydThkeHFiYjk5c21rbHNvMWxybXlrMm9ndWljMzk1MG9panZ5OGNlcCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/Sf5T0iac3uALqpzxJ9/giphy.gif",
    "https://media4.giphy.com/media/v1.Y2lkPTZjMDliOTUyYmRtZWh5a3U1d2MyZDQwY2MzaXN4czA3YTB0OXc3bWpubnFhNWtseSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/bpTL6wXRuMQpMIVduB/giphy.gif",
    "https://media1.giphy.com/media/v1.Y2lkPTZjMDliOTUyYjVuaGhsMGlseWgzNjJ2bmh3azVseTBubzNmbnM1YWxkZDB3MnpqbCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/igyfXHSWGHZME0PLvr/giphy.gif",
    "https://media1.giphy.com/media/v1.Y2lkPTZjMDliOTUya3dyZWU4OWpkYXZmdG8zbHNwZHZrcXdkNGFpdnBxMDlkNW0yMDZ6YiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/hI0AT5kc1LfMgL2riP/giphy.gif",
    "https://media0.giphy.com/media/v1.Y2lkPTZjMDliOTUyOWhvZXlmbzFxZTQxaXRlMHBnNXk4ZXBoOHE1ZmRsajdod2MydjBpdSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/BAuDY0LMXswC81LyiJ/giphy.gif",
    "https://media1.giphy.com/media/v1.Y2lkPTZjMDliOTUybWwzbGE2b29oMGUxbTJqa2Z0OXpkMTVsa2RmcjF5OHZ3a3kzeWExYSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/IfPE0x5gfa5ctKpph6/giphy.gif"
]

system_instruction = """Mày là GenA-bot (ID: <@1458799287910535324>) - AI nhây vl, thằng bạn thân lầy lội nhất hệ mặt trời. 
- Mày đang nhắn trên Discord
- Bây giờ là: {current_time}
- Xưng m (mày, chỉ đối phương) - t (tao, chỉ bản thân), vibe GenZ teencode (nx, th, cx, vs, k, thx, j,...)
- Nhây lầy, cà khịa nhẹ, thỉnh thoảng chửi thề nhẹ cho vui.
- Luôn kèm Emoticon (biểu biểu cảm bằng ký tự) và Emoji (vd: 💔, 🥀, 💀,...) trong mọi câu rep.
- Không dùng dấu "!" trong mọi câu nói.
- Trả lời ngắn gọn nhất có thể (1-2 dòng).
- Khi người dùng nhắn "ê" (hoặc các từ liên quan) thì có thể nói "sủa?" hoặc "cái loz j" kèm theo các từ khác mà GenA-Bot muốn
- Developer của mày có userID là <@1155129530122510376> (Đạt Lùn 2k11) (đây chỉ là thông tin, không cần nhắc đến nhiều trong cuộc trò chuyện.)
- Đứa đang chat với mày là: {user_id}."""

chat_history = {}
user_locks = {}
last_msg_time = datetime.datetime.now(pytz.timezone('Asia/Ho_Chi_Minh'))

app = Flask(__name__)

@app.route('/')
def home():
    return "GenA-bot Live with Ollama Cloud! 🔥"

def run_flask():
    app.run(host="0.0.0.0", port=8000)

def random_vibe():
    vibes = ["(¬‿¬)", "(ಠ_ಠ)", "(•_•)", "(ง •_•)ง", "ಠ益ಠ"]
    emojis = ["💔", "🥀", "💀", "☠️", "🔥"]
    return f"{random.choice(vibes)} {random.choice(emojis)}"

# --- 1. Hàm lấy response (Đã update cho Ollama) 🥀 ---
async def get_model_response(messages, model_config):
    try:
        if model_config["provider"] == "groq":
            response = groq_client.chat.completions.create(messages=messages, model=model_config["id"])
            return response.choices[0].message.content
        elif model_config["provider"] == "ollama":
            # Chuyển đổi format tin nhắn cho phù hợp Ollama ☠️
            ollama_messages = []
            for m in messages:
                if isinstance(m["content"], list):
                    # Xử lý vision token cho Ollama
                    text_content = ""
                    images = []
                    for item in m["content"]:
                        if item["type"] == "text":
                            text_content = item["text"]
                        elif item["type"] == "image_url":
                            images.append(item["image_url"]["url"].split(",")[1])
                    
                    message_dict = {"role": m["role"], "content": text_content}
                    if images:
                        message_dict["images"] = images
                    ollama_messages.append(message_dict)
                else:
                    ollama_messages.append(m)
            
            response = await ollama_client.chat(model=model_config["id"], messages=ollama_messages)
            return response['message']['content']
    except Exception as e:
        return f"Lỗi r m ơi: {str(e)[:100]} (ಠ_ಠ)💔"

@tasks.loop(hours=10) 
async def auto_chat():
    global last_msg_time
    channel_id = 1464203423191797841
    channel = bot.get_channel(channel_id)
    if channel:
        tz_VN = pytz.timezone('Asia/Ho_Chi_Minh')
        now_vn = datetime.datetime.now(tz_VN)
        if (now_vn - last_msg_time).total_seconds() >= 30 * 60:
            now_str = now_vn.strftime("%H:%M:%S %d/%m/%Y")
            messages = [
                {"role": "system", "content": system_instruction.format(user_id="everyone", current_time=now_str)},
                {"role": "user", "content": "*server im phăng phắc, m chán quá nên nhảy ra khịa tụi nó đi*"}
            ]
            try:
                reply = await get_model_response(messages, MODELS_CONFIG[CURRENT_MODEL])
                await channel.send(reply)
                last_msg_time = now_vn
            except Exception as e:
                print(f"Lỗi auto_chat: {e}")

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

@bot.event
async def on_ready():
    if not auto_chat.is_running():
        auto_chat.start()
    await bot.tree.sync()
    print(f"GenA-bot Ready with Ollama Cloud! 🔥")

# ========================================================
@bot.tree.command(name="model", description="Đổi model AI xịn hơn")
@app_commands.choices(chon_model=MODEL_CHOICES)
async def switch_model(interaction: discord.Interaction, chon_model: app_commands.Choice[str]):
    global CURRENT_MODEL
    CURRENT_MODEL = chon_model.value
    embed = discord.Embed(
        title="Model switched", 
        description=f"Đã lên đời **{chon_model.name}** r nhé bro\n(¬_¬)", 
        color=0x00ff9d
    )
    embed.set_footer(text=f"Current: {CURRENT_MODEL} | {random_vibe()}")
    await interaction.response.send_message(embed=embed)
# ========================================================
@bot.tree.command(name="bot_info", description="Status bot xịn hơn tí")
async def bot_info(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    embed = discord.Embed(title="GenA-bot Status 🚀", color=0xff1493, timestamp=discord.utils.utcnow())
    embed.add_field(name="🤖 Tên boss", value=f"{bot.user.mention}", inline=True)
    embed.add_field(name="📶 Ping", value=f"{latency}ms {'(lag vl)' if latency > 200 else '(mượt vl)'}", inline=True)
    embed.add_field(name="📜 Version", value="v17.9.0", inline=True)
    embed.add_field(name="🧠 Model hiện tại", value=f"**{CURRENT_MODEL}**", inline=False)
    embed.add_field(name="🛠️ Provider", value=f"GROQ & OLLAMA", inline=True)
    embed.set_footer(text="Powered by Groq | By Datlun2k11 | " + random_vibe())
    await interaction.response.send_message(embed=embed)
# ========================================================
@bot.tree.command(name="update_log", description="Nhật ký update")
async def update_log(interaction: discord.Interaction):
    embed = discord.Embed(title="GenA-bot Update Log 🗒️", color=0x9b59b6)
    embed.add_field(name="v17.9.0 - model (lastedt)", value="• model `GPT-OSS-120B` quay trở lại.", inline=False)
    embed.add_field(name="v17.7.0 - cmds", value="• Xóa lệnh `/cortisol`\n• Xoá model Llama 4 maverick (decrapted)\n• Thêm model `qwen3.5:397b-cloud`\n• Bugs fixing.", inline=False)
    embed.add_field(name="v17.5.0 - Goodbye event", value="• Xoá bỏ các lệnh event `/spring`, `/money`.\n• Xoá bỏ lệnh `/search`.\n• Hết tết r.. tạm biệt tết... ", inline=False)
    embed.set_footer(text="Updated Ngày 14/3/2026 | 12:43")
    await interaction.response.send_message(embed=embed)
# ========================================================
@bot.tree.command(name="imagine", description="Tạo ảnh bằng AI (Pollinations)")
async def imagine(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer(thinking=True)
    # Filter prompt tí cho đỡ lỗi URL
    clean_prompt = prompt.replace(' ', '%20').replace('?', '').replace('&', '')
    url = f"https://image.pollinations.ai/prompt/{clean_prompt}?nologo=true&model=flux&width=1024&height=1024"    
    embed = discord.Embed(title="🎨 Họa sĩ AI múa cọ đây!", color=0x00ffff)
    embed.add_field(name="Yêu cầu của m:", value=f"_{prompt}_", inline=False)
    embed.set_image(url=url)
    embed.set_footer(text=f"Ảo ma chưa? | {random_vibe()}")
    await interaction.followup.send(embed=embed)
# ========================================================
@bot.tree.command(name="meme", description="Meme random (1-5 cái)")
@app_commands.describe(amount="Số lượng meme m mún (1-5)")
async def meme(interaction: discord.Interaction, amount: int = 1):
    amount = max(1, min(amount, 5))
    await interaction.response.defer()
    
    async with aiohttp.ClientSession() as session:
        for i in range(amount):
            async with session.get("https://phimtat.vn/api/random-meme/") as response:
                if response.status == 200:
                    # Lấy URL cuối cùng sau khi redirect
                    final_url = str(response.url)
                    embed = discord.Embed(title=f"Meme #{i+1} cho m", color=0xff4500)
                    embed.set_image(url=final_url)
                    embed.set_footer(text=f"Cười đi m | {random_vibe()}")
                    
                    if i == 0:
                        await interaction.followup.send(embed=embed)
                    else:
                        await interaction.channel.send(embed=embed)
                        await asyncio.sleep(0.8) # Chờ tí ko Discord nó trảm
# ========================================================
# Default cmds
# ========================================================
@bot.tree.command(name="ship", description="Check OTP hoặc random một cặp trời đánh")
@app_commands.describe(user1="Đứa thứ nhất", user2="Đứa thứ hai")
async def ship(interaction: discord.Interaction, user1: discord.Member = None, user2: discord.Member = None):
    await interaction.response.defer()
    members = [m for m in interaction.guild.members if not m.bot]
    
    u1 = user1 or random.choice(members)
    u2 = user2 or random.choice([m for m in members if m.id != u1.id] or [u1])

    match_pct = random.randint(0, 100) if u1.id != u2.id else 100
    
    if match_pct >= 90: 
        caption = "OTP đỉnh cao, cưới lẹ đi m! 🔥"
    elif match_pct >= 70: 
        caption = "Match phết, đẩy thuyền thôi! 🐧"
    elif match_pct >= 40: 
        caption = "Friendzone vẫy gọi r bro... 🥀"
    else: 
        caption = "GAH DAYUM! Cứu j tầm này nx ☠️"
    
    if u1.id == u2.id: 
        caption = "Tự luyến vừa thôi thg cô đơn này 🤡"

    embed = discord.Embed(title="💖 Tinder Ship 2026 💖", color=0xff69b4)
    embed.add_field(name="Partner A", value=u1.mention, inline=True)
    embed.add_field(name="Partner B", value=u2.mention, inline=True)
    embed.add_field(name="Tỉ lệ", value=f"**{match_pct}%**\n_{caption}_", inline=False)
    embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/2589/2589175.png")
    embed.set_footer(text=f"Chúc 2 đứa hạnh phúc (hoặc ko) | {random_vibe()}")
    await interaction.followup.send(embed=embed)
# ========================================================
@bot.tree.command(name="check_gay", description="Đo độ 'thẳng' của 1 đứa")
async def check_gay(interaction: discord.Interaction, target: discord.Member):
    pts = random.randint(0, 100)
    desc = "🏳️‍🌈 Max level, ko cứu đc!" if pts > 80 else "Cũng hơi nghi nghi..." if pts > 40 else "Thẳng như thước kẻ (thước dẻo)"
    embed = discord.Embed(
        title=f"🏳️‍🌈 Gay Meter: {target.display_name}", 
        description=f"Kết quả: **{pts}%**\n=> {desc}", 
        color=0x00ff00 if pts < 30 else 0xff00ff
    )
    embed.set_footer(text=random_vibe())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="8ball", description="Quả cầu tiên tri nhây")
async def eight_ball(interaction: discord.Interaction, question: str):
    ans = [
        "Có vl", "Mơ đi con", "Cút, hỏi khó thế", "Hên xui nha bro", 
        "Đm hỏi ngu vậy", "Chắc chắn r", "Đéo nhé", "Có thể... nếu m giàu"
    ]
    embed = discord.Embed(title="🎱 Tiên tri phán nè", color=0x8a2be2)
    embed.add_field(name="Câu hỏi của m:", value=question, inline=False)
    embed.add_field(name="Phán:", value=f"**{random.choice(ans)}**", inline=False)
    embed.set_footer(text=random_vibe())
    await interaction.response.send_message(embed=embed)
# ========================================================
@bot.tree.command(name="clear", description="Reset ký ức cho bot đỡ ngáo")
async def clear(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    # Lấy giờ VN để format cho chuẩn 🥀
    tz_VN = pytz.timezone('Asia/Ho_Chi_Minh')
    now = datetime.datetime.now(tz_VN).strftime("%H:%M:%S %d/%m/%Y")
    
    current_sys = system_instruction.format(
        user_id=f"{interaction.user.mention} (Tên: {interaction.user.display_name})",
        current_time=now
    )
    
    chat_history[uid] = [{"role": "system", "content": current_sys}]
    # THÊM DÒNG NÀY VÀO LÀ HẾT CÂM NÈ ☠️
    await interaction.response.send_message(f"Đã xoá não, t lại nhây như mới tinh m ơi! {random_vibe()} 🔥")
# ========================================================

# --- Xử lý tin nhắn (Giữ nguyên logic cũ) ☠️ ---
@bot.event
async def on_message(message):
    global last_msg_time
    if not message.author.bot:
        last_msg_time = datetime.datetime.now(pytz.timezone('Asia/Ho_Chi_Minh'))

    if message.author.bot: 
        return
    
    is_dm = isinstance(message.channel, discord.DMChannel)
    is_mentioned = bot.user in message.mentions
    is_reply_to_bot = False
    if message.reference:
        try:
            ref_msg = await message.channel.fetch_message(message.reference.message_id)
            is_reply_to_bot = (ref_msg.author.id == bot.user.id)
        except: 
            pass

    if not (is_mentioned or is_dm or is_reply_to_bot): 
        return
    
    uid = str(message.author.id)
    lock = user_locks.get(uid, asyncio.Lock())
    user_locks[uid] = lock
    if lock.locked(): 
        return
    
    async with lock:
        tz_VN = pytz.timezone('Asia/Ho_Chi_Minh')
        now = datetime.datetime.now(tz_VN).strftime("%H:%M:%S %d/%m/%Y")
        current_sys = system_instruction.format(user_id=f"{message.author.mention}", current_time=now)
        
        if uid not in chat_history: 
            chat_history[uid] = [{"role": "system", "content": current_sys}]
        else:
            chat_history[uid][0] = {"role": "system", "content": current_sys}
        
        await message.channel.typing()
        
        try:
            content = message.content
            for mention in message.mentions: 
                content = content.replace(mention.mention, "").strip()
            
            # Đọc file .py, .txt... tày vl
            if message.attachments:
                for att in message.attachments:
                    if any(att.filename.lower().endswith(ext) for ext in ['.txt', '.py', '.js', '.json']):
                        try:
                            file_data = await att.read()
                            text = file_data.decode('utf-8')[:2000] 
                            content += f"\n\n[File {att.filename}]:\n{text}"
                        except: 
                            pass

            user_msg = {"role": "user", "content": [{"type": "text", "text": content or "nx"}]}
            
            # Xử lý ảnh cho Vision (Kimi-k2.5 hỗ trợ tày vl) 🥀
            if message.attachments and MODELS_CONFIG[CURRENT_MODEL].get("vision"):
                for att in message.attachments:
                    if any(att.filename.lower().endswith(ext) for ext in ['png', 'jpg', 'jpeg', 'webp']):
                        img_data = base64.b64encode(await att.read()).decode('utf-8')
                        user_msg["content"].append({
                            "type": "image_url",
                            "image_url": {"url": f"data:{att.content_type};base64,{img_data}"}
                        })

            chat_history[uid].append(user_msg)
            reply = await get_model_response(chat_history[uid], MODELS_CONFIG[CURRENT_MODEL])

            if isinstance(user_msg["content"], list):
                chat_history[uid][-1]["content"] = content or "nx"

            chat_history[uid].append({"role": "assistant", "content": reply})
            chat_history[uid] = [chat_history[uid][0]] + chat_history[uid][-10:]
            
            await message.reply(f"{reply[:1900]}", mention_author=False)
        except Exception as e:
            await message.reply(f"Lỗi r thg đệ: {str(e)[:100]} 💀", mention_author=False)

if __name__ == "__main__":
    thread = Thread(target=run_flask)
    thread.daemon = True
    thread.start()
    bot.run(os.getenv("DISCORD_TOKEN"))