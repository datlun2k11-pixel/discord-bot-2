import discord, random, os, asyncio, aiohttp, base64
from discord.ext import tasks
from discord.ext import commands
from discord import app_commands
from groq import Groq
from dotenv import load_dotenv
from flask import Flask
from threading import Thread
import datetime
import pytz

load_dotenv()

# Clients - Groq xịn đét 
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Maverick 4 Vision Enabled (⌐■_■) ☠️
MODELS_CONFIG = {
    "Groq-Llama-Maverick": {"id": "meta-llama/llama-4-maverick-17b-128e-instruct", "provider": "groq", "vision": True},
    "Groq-Kimi": {"id": "moonshotai/kimi-k2-instruct-0905", "provider": "groq", "vision": False},
    "Groq-Qwen3": {"id": "qwen/qwen3-32b", "provider": "groq", "vision": False}
}

MODEL_CHOICES = [app_commands.Choice(name=k.split("-",1)[1].replace("-", " ") + f" ({v['provider'].upper()})", value=k) for k,v in MODELS_CONFIG.items()]
CURRENT_MODEL = "Groq-Llama-Maverick"

MONEY_GIFS = [
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
- Luôn kèm Emoticon (biểu cảm bằng ký tự) và Emoji (vd: 💔, 🥀, 💀,...) trong mọi câu rep.
- Không dùng dấu "!" trong mọi câu nói.
- Trả lời ngắn gọn nhất có thể (1-2 dòng).
- Developer của mày có userID là <@1155129530122510376> (Đạt Lùn 2k11) (đây chỉ là thông tin, không cần nhắc đến nhiều trong cuộc trò chuyện.)
- Đứa đang chat với mày là: {user_id}."""

chat_history, user_locks = {}, {}
last_msg_time = datetime.datetime.now(pytz.timezone('Asia/Ho_Chi_Minh'))

app = Flask(__name__)
@app.route('/')
def home(): return "GenA-bot Live! 🔥"
def run_flask(): app.run(host="0.0.0.0", port=8000)
    
def random_vibe():
    vibes = ["(¬‿¬)", "(ಠ_ಠ)", "(•_•)", "(ง •_•)ง", "ಠ益ಠ"]
    emojis = ["💔", "🥀", "💀", "☠️", "🔥"]
    return f"{random.choice(vibes)} {random.choice(emojis)}"

# --- 1. Hàm lấy response (Giữ nguyên) ---
async def get_model_response(messages, model_config):
    try:
        response = groq_client.chat.completions.create(messages=messages, model=model_config["id"])
        return response.choices[0].message.content
    except Exception as e:
        return f"Lỗi r m ơi: {str(e)} (ಠ_ಠ)💔"

@tasks.loop(minutes=30) 
async def auto_chat():
    global last_msg_time
    channel_id = 1464203423191797841
    channel = bot.get_channel(channel_id)
    
    tz_VN = pytz.timezone('Asia/Ho_Chi_Minh')
    now_vn = datetime.datetime.now(tz_VN)
    
    # Nếu trong 30p vừa qua có đứa chat rồi thì thôi k sủa nx ☠️
    if (now_vn - last_msg_time).total_seconds() < 30 * 60:
        return 

    if channel:
        now_str = now_vn.strftime("%H:%M:%S %d/%m/%Y")
        messages = [
            {"role": "system", "content": system_instruction.format(user_id="everyone", current_time=now_str)},
            {"role": "user", "content": "*mọi người đang off* (m đang chán ở trong server đang off, cà khịa cả đám đi)"}
        ]
        reply = await get_model_response(messages, MODELS_CONFIG[CURRENT_MODEL])
        await channel.send(reply)
        last_msg_time = now_vn # Sủa xong cũng phải update time k là nó spam liên tục đấy (ง •_•)ง 💔
        except Exception as e:
            print(f"Lỗi auto_chat: {e}")

# --- 3. Khởi tạo Bot và on_ready ---
bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

@bot.event
async def on_ready():
    if not auto_chat.is_running():
        auto_chat.start()
    await bot.tree.sync()
    print(f"GenA-bot Ready! 🔥")

#CMDs
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
    embed.add_field(name="📜 Version", value="v16.0.5 - Groq", inline=True)
    embed.add_field(name="🧠 Model hiện tại", value=f"**{CURRENT_MODEL}**", inline=False)
    embed.add_field(name="🛠️ Provider", value=f"GROQ (Xịn đét)", inline=True)
    embed.set_footer(text="Powered by Groq | By Datlun2k11 | " + random_vibe())
    await interaction.response.send_message(embed=embed)
# ========================================================
@bot.tree.command(name="update_log", description="Nhật ký update")
async def update_log(interaction: discord.Interaction):
    embed = discord.Embed(title="GenA-bot Update Log 🗒️", color=0x9b59b6)
    embed.add_field(name="v16.0.5 (lastest) - File", value="• Sửa lỗi logic\n• Bot có thể đọc đc file đính kèm (nhưng vẫn còn hạn chế về thể loại).", inline=False)
    embed.add_field(name="v16.0.0 - prompt", value="• Sửa đổi system prompt\n• Thêm 1 số easter eggs cho lệnh `/spring`.\n• Sửa logic, fix thêm sys_prompt\n• Thêm tính năng `thỉnh thoảng chat 1 câu`.", inline=False)
    embed.add_field(name="v15.9.5 - Img", value="• Thêm được phân tích ảnh cho model `Llama-4-Macerick`\n• Thêm 4 GIFS mới", inline=False)
    embed.set_footer(text=f"Updated Ngày 11/2/2026 | {random_vibe()}")
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
    
    async with aiohttp.ClientSession() as s:
        for i in range(amount):
            async with s.get("https://phimtat.vn/api/random-meme/") as r:
                if r.status == 200:
                    # Lấy URL cuối cùng sau khi redirect
                    final_url = str(r.url)
                    embed = discord.Embed(title=f"Meme #{i+1} cho m", color=0xff4500)
                    embed.set_image(url=final_url)
                    embed.set_footer(text=f"Cười đi m | {random_vibe()}")
                    
                    if i == 0:
                        await interaction.followup.send(embed=embed)
                    else:
                        await interaction.channel.send(embed=embed)
                        await asyncio.sleep(0.8) # Chờ tí ko Discord nó trảm
# ========================================================
# Event cmds
# ========================================================
@bot.tree.command(name="money", description="Nhận lì xì ngẫu nhiên (chỉ số chẵn)")
async def money(interaction: discord.Interaction):
    amount = random.randrange(2000, 1000000, 2)
    formatted_money = "{:,}".format(amount)
    
    status = "j ghê z m? Hack à? Đưa t một nửa ko t báo CA =))🙏🥀" if amount > 400000 else \
             "Cũng ra gì đấy, đủ bao t bát phở r bro 🤑" if amount > 200000 else \
             "Tầm này chỉ đủ mua trà sữa thôi, bớt tinh tướng 🥀" if amount > 50000 else \
             "GAH DAYUM! Có mấy đồng lẻ này thì cất đi kẻo gió thổi bay mất 💀☠️"

    embed = discord.Embed(
        title="💸 Lì xì ngẫu nhiên 🧧",
        description=f"Hệ thống vừa vứt vào mặt {interaction.user.mention}:\n**{formatted_money} VNĐ**\n\n_{status}_",
        color=0xff0000
    )
    embed.set_image(url=random.choice(MONEY_GIFS)) # Set thẳng vào image cho to
    embed.set_footer(text=f"Tiền ảo thôi đừng tưởng real nha | {random_vibe()}")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="spring", description="Bốc thăm lì xì đầu năm lấy hên")
async def spring(interaction: discord.Interaction):
    rewards = [
        "🧧 Lì xì 500k (tưởng tượng đi m) 💸", "💀 1 vé quét sân, rửa bát xuyên Tết",
        "💍 Năm nay có bồ (bồ tát phù hộ)", "🥀 Crush xem story nhưng ko rep",
        "🧨 1 tràng pháo tay cho sự nghèo của m", "🥟 Một miếng bánh chưng toàn mỡ",
        "🔥 Nhân phẩm bùng nổ: Được lì xì gấp đôi", "🐧 Được chúc 'Hay ăn chóng lớn' (dù m già r)",
        "☠️ Bị hỏi 'Bao giờ lấy vợ?' 100 lần", "🌟 Vận may: Chơi bài toàn thắng (trừ lúc thua)",
        "💸 Tiền vào như nước, ra như thác", "🤡 Làm `con nhà người ta` trong 1 ngày",
        "🍑 Một cành đào nở toàn lá xanh", "🐍 Năm Rắn qua rồi, lươn ít thôi ko nghiệp quật",
        "🏳️‍🌈 Bị 1 đứa LGBT dí (trong mơ)", "🐎 Năm Mã, đi đường cẩn thận ko bị ngựa đá đít"
    ]
    gift = random.choice(rewards)
    embed = discord.Embed(
        title="🧧 Bốc thăm may rủi 2026 🧧",
        description=f"Chúc mừng {interaction.user.mention} đã hốt được:\n\n**{gift}**",
        color=0xff0000
    )
    embed.set_image(url=random.choice(MONEY_GIFS)) # Dùng chung kho GIF tiền bay cho máu
    embed.set_footer(text=f"Tết nhất vui vẻ đừng tứk=)) | {random_vibe()}")
    await interaction.response.send_message(embed=embed)
# ========================================================
# Defualt cmds
# ========================================================
@bot.tree.command(name="ship", description="Check OTP hoặc random một cặp trời đánh")
@app_commands.describe(user1="Đứa thứ nhất", user2="Đứa thứ hai")
async def ship(interaction: discord.Interaction, user1: discord.Member = None, user2: discord.Member = None):
    await interaction.response.defer()
    members = [m for m in interaction.guild.members if not m.bot]
    
    u1 = user1 or random.choice(members)
    u2 = user2 or random.choice([m for m in members if m.id != u1.id] or [u1])

    match_pct = random.randint(0, 100) if u1.id != u2.id else 100
    
    if match_pct >= 90: caption = "OTP đỉnh cao, cưới lẹ đi m! 🔥"
    elif match_pct >= 70: caption = "Match phết, đẩy thuyền thôi! 🐧"
    elif match_pct >= 40: caption = "Friendzone vẫy gọi r bro... 🥀"
    else: caption = "GAH DAYUM! Cứu j tầm này nx ☠️"
    
    if u1.id == u2.id: caption = "Tự luyến vừa thôi thg cô đơn này 🤡"

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
@bot.event
async def on_message(message):
    global last_msg_time
    # Cập nhật thời gian tin nhắn cuối từ người dùng
    if not message.author.bot:
        last_msg_time = datetime.datetime.now(pytz.timezone('Asia/Ho_Chi_Minh'))

    if message.author.bot: return
    
    is_dm = isinstance(message.channel, discord.DMChannel)
    is_mentioned = bot.user in message.mentions
    is_reply_to_bot = False
    if message.reference:
        try:
            ref_msg = await message.channel.fetch_message(message.reference.message_id)
            is_reply_to_bot = (ref_msg.author.id == bot.user.id)
        except: pass

    if not (is_mentioned or is_dm or is_reply_to_bot): return
    
    uid = str(message.author.id)
    lock = user_locks.get(uid, asyncio.Lock())
    user_locks[uid] = lock
    if lock.locked(): return
    
    async with lock:
        # Lấy giờ VN mới nhất để AI ko bị "ngáo" quá khứ 🥀
        tz_VN = pytz.timezone('Asia/Ho_Chi_Minh')
        now = datetime.datetime.now(tz_VN).strftime("%H:%M:%S %d/%m/%Y")
        
        current_sys = system_instruction.format(
            user_id=f"{message.author.mention} (Tên: {message.author.display_name})",
            current_time=now
        )
        
        # Cập nhật hoặc khởi tạo não bộ với giờ mới nhất ☠️
        if uid not in chat_history: 
            chat_history[uid] = [{"role": "system", "content": current_sys}]
        else:
            chat_history[uid][0] = {"role": "system", "content": current_sys}
        
        await message.channel.typing()
        
        try:
            content = message.content
            for mention in message.mentions: 
                content = content.replace(mention.mention, "").strip()
            
            if message.attachments:
                for att in message.attachments:
                    if any(att.filename.lower().endswith(ext) for ext in ['.txt', '.py', '.js', '.cpp', '.c', '.json']):
                        try:
                            file_data = await att.read()
                            text = file_data.decode('utf-8')[:2000] 
                            content += f"\n\n[Nội dung file {att.filename}]:\n{text}..."
                        except: pass

            user_msg = {"role": "user", "content": [{"type": "text", "text": content or "nx"}]}
            
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

            # Tráo bài: Xóa data ảnh/file nặng nề, chỉ giữ text để tiết kiệm token 🥀
            if isinstance(user_msg["content"], list):
                chat_history[uid][-1] = {"role": "user", "content": content or "nx"}

            chat_history[uid].append({"role": "assistant", "content": reply})
            chat_history[uid] = [chat_history[uid][0]] + chat_history[uid][-10:]
            
            await message.reply(f"{reply[:1900]}", mention_author=False)
        
        except Exception as e:
            await message.reply(f"Lỗi r thg đệ: {str(e)[:100]} 💀", mention_author=False)

# --- PHẦN CUỐI FILE KHÔNG ĐƯỢC THIẾU ---
if __name__ == "__main__":
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()
    bot.run(os.getenv("DISCORD_TOKEN"))