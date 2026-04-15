import discord
import os
import asyncio
import aiohttp
import random
import datetime
import pytz
import base64  # Thêm để encode ảnh
from discord.ext import commands
from discord import app_commands
from groq import Groq
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

load_dotenv()

# --- Clients ---
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- Config Model (Đã bật Vision cho Gemma4) ---
MODELS_CONFIG = {
    "Groq-Llama-Scout": {"id": "meta-llama/llama-4-scout-17b-16e-instruct", "provider": "groq", "vision": True},
    "GPT-OSS-120B": {"id": "openai/gpt-oss-120b", "provider": "groq", "vision": False},
    "Groq-Qwen3": {"id": "qwen/qwen3-32b", "provider": "groq", "vision": False},
    # BẬT VISION TRUE CHO GEMMA 4 🥀
    "Gemma4-26B": {"id": "google/gemma-4-26b-a4b-it", "provider": "groq", "vision": True} 
}

MODEL_CHOICES = [
    app_commands.Choice(name="Llama 4 Scout (GROQ - Vision)", value="Groq-Llama-Scout"),
    app_commands.Choice(name="GPT-OSS-120B (GROQ)", value="GPT-OSS-120B"),
    app_commands.Choice(name="Qwen 3 32B (GROQ)", value="Groq-Qwen3"),
    app_commands.Choice(name="Gemma4 26B (Google - Vision)", value="Gemma4-26B")
]

CURRENT_MODEL = "Groq-Llama-Scout"

# System Prompt (Giữ nguyên vibe)
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
- Đứa đang chat với mày là: {user_id}.
- NẾU NGƯỜI DÙNG GỬI ẢNH: Phải quan sát thật kỹ ảnh và trả lời dựa trên nội dung ảnh đó (miêu tả ngắn gọn, cà khịa nếu xấu)."""

chat_history = {}
user_locks = {}
last_msg_time = datetime.datetime.now(pytz.timezone('Asia/Ho_Chi_Minh'))

app = Flask(__name__)
@app.route('/')
def home(): return "GenA-bot Live with Groq + Gemma4 Vision! 🔥"
def run_flask(): app.run(host="0.0.0.0", port=8000)

def random_vibe():
    vibes = ["(¬‿¬)", "(ಠ_ಠ)", "(•_•)", "(ง •_•)ง", "ಠ益ಠ"]
    emojis = ["💔", "🥀", "💀", "☠️", "🔥"]
    return f"{random.choice(vibes)} {random.choice(emojis)}"

# --- Hàm gọi API có xử lý Vision ---
async def get_model_response(messages, model_config):
    try:
        response = groq_client.chat.completions.create(
            messages=messages, 
            model=model_config["id"]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Lỗi r m ơi: {str(e)[:100]} (ಠ_ಠ)💔"

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"GenA-bot Ready with Groq + Gemma4 Vision! 🔥")

# ========================================================
# 3 CMDS CHÍNH ĐƯỢC GIỮ LẠI
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

@bot.tree.command(name="bot_info", description="Status bot xịn hơn tí")
async def bot_info(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    embed = discord.Embed(title="GenA-bot Status 🚀", color=0xff1493, timestamp=discord.utils.utcnow())
    embed.add_field(name="🤖 Tên boss", value=f"{bot.user.mention}", inline=True)
    embed.add_field(name="📶 Ping", value=f"{latency}ms {'(lag vl)' if latency > 200 else '(mượt vl)'}", inline=True)
    embed.add_field(name="📜 Version", value="v18.0.1 (Vision)", inline=True)
    embed.add_field(name="🧠 Model hiện tại", value=f"**{CURRENT_MODEL}**", inline=False)
    embed.add_field(name="🛠️ Provider", value="GROQ", inline=True)
    embed.set_footer(text="Powered by Groq | By Datlun2k11 | " + random_vibe())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="update_log", description="Nhật ký update")
async def update_log(interaction: discord.Interaction):
    embed = discord.Embed(title="GenA-bot Update Log 🗒️", color=0x9b59b6)
    embed.add_field(name="v18.0.1 - Vision", value="• Bật Vision cho Gemma4\n• Bot đọc được ảnh m gửi r đó 🥀", inline=False)
    embed.add_field(name="v18.0.0 - Gọn nhẹ", value="• Xóa bớt lệnh giải trí\n• Chỉ giữ 3 lệnh chính\n• Fix URL & Model ID Gemma4.", inline=False)
    embed.add_field(name="v17.9.3 - fix", value="• Bugs fixing \n• xoá ping chat mỗi 10 tiếng.", inline=False)
    embed.set_footer(text="Updated Ngày 15/04/2026 | Vision ver")
    await interaction.response.send_message(embed=embed)

# ========================================================
# XỬ LÝ CHAT (ĐÃ BỔ SUNG ĐỌC ẢNH BASE64)
# ========================================================
@bot.tree.command(name="clear", description="Reset ký ức cho bot đỡ ngáo")
async def clear(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    tz_VN = pytz.timezone('Asia/Ho_Chi_Minh')
    now = datetime.datetime.now(tz_VN).strftime("%H:%M:%S %d/%m/%Y")
    current_sys = system_instruction.format(
        user_id=f"{interaction.user.mention} (Tên: {interaction.user.display_name})",
        current_time=now
    )
    chat_history[uid] = [{"role": "system", "content": current_sys}]
    await interaction.response.send_message(f"Đã xoá não, t lại nhây như mới tinh m ơi! {random_vibe()} 🔥")

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
            
            # Chuẩn bị user_msg_content dạng list cho Vision API
            user_msg_content = []
            
            # Thêm text nếu có
            if content:
                user_msg_content.append({"type": "text", "text": content})
            else:
                user_msg_content.append({"type": "text", "text": "nx"})

            # XỬ LÝ ẢNH (VISION) - PHẦN MỚI THÊM VÀO 🥀
            if MODELS_CONFIG[CURRENT_MODEL]["vision"] and message.attachments:
                for att in message.attachments:
                    if att.content_type and att.content_type.startswith('image/'):
                        try:
                            # Đọc ảnh và encode base64
                            img_data = await att.read()
                            img_base64 = base64.b64encode(img_data).decode('utf-8')
                            
                            # Tạo URL data scheme cho Groq Vision
                            img_url = f"data:{att.content_type};base64,{img_base64}"
                            
                            # Thêm vào nội dung gửi lên model
                            user_msg_content.append({
                                "type": "image_url",
                                "image_url": {"url": img_url}
                            })
                            print(f"✅ Đã nạp ảnh: {att.filename}") # Log để debug
                        except Exception as img_e:
                            print(f"❌ Lỗi đọc ảnh: {img_e}")
                    # Đọc file text như cũ
                    elif any(att.filename.lower().endswith(ext) for ext in ['.txt', '.py', '.js', '.json']):
                        try:
                            file_data = await att.read()
                            text = file_data.decode('utf-8')[:2000] 
                            # Nếu là file text, thêm vào text có sẵn
                            user_msg_content[0]["text"] += f"\n\n[File {att.filename}]:\n{text}"
                        except: 
                            pass

            user_msg = {"role": "user", "content": user_msg_content}
            
            chat_history[uid].append(user_msg)
            reply = await get_model_response(chat_history[uid], MODELS_CONFIG[CURRENT_MODEL])

            # Đơn giản hóa history lưu trữ (chỉ lưu text để tránh lỗi format khi gửi lại)
            # Lưu ý: Groq không yêu cầu format base64 trong history, chỉ cần lần gọi đầu có ảnh.
            # Để đơn giản, ta lưu lại tin nhắn text đã có.
            chat_history[uid][-1] = {"role": "user", "content": content or "[Đã gửi ảnh]"}
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