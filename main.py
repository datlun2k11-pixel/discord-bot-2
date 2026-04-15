import discord
import os
import asyncio
import aiohttp
import random
import datetime
import pytz
import base64
import json  # Thêm để parse JSON
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

load_dotenv()

# --- Config ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")  # Lấy từ https://aistudio.google.com/apikey
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

# --- Model Config cho Google AI Studio (Gemini API) ---
MODELS_CONFIG = {
    # Gemma 4 qua Google AI Studio (Gemini API)
    "Gemma4-26B": {
        "id": "gemma-4-26b-a4b-it",  # Model ID chính xác cho Google AI Studio [citation:3][citation:5][citation:9]
        "provider": "google",
        "vision": True,
        "context_window": 256000
    },
    "Gemma4-31B": {
        "id": "gemma-4-31b-it",  # Model 31B dense [citation:1][citation:5]
        "provider": "google", 
        "vision": True,
        "context_window": 256000
    }
}

MODEL_CHOICES = [
    app_commands.Choice(name="Gemma4 26B (Google - Vision)", value="Gemma4-26B"),
    app_commands.Choice(name="Gemma4 31B (Google - Vision)", value="Gemma4-31B")
]

CURRENT_MODEL = "Gemma4-26B"

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
- Đứa đang chat với mày là: {user_id}."""

chat_history = {}
user_locks = {}
last_msg_time = datetime.datetime.now(pytz.timezone('Asia/Ho_Chi_Minh'))

app = Flask(__name__)
@app.route('/')
def home(): return "GenA-bot Live with Google Gemini API + Gemma4! 🔥"
def run_flask(): app.run(host="0.0.0.0", port=8000)

def random_vibe():
    vibes = ["(¬‿¬)", "(ಠ_ಠ)", "(•_•)", "(ง •_•)ง", "ಠ益ಠ"]
    emojis = ["💔", "🥀", "💀", "☠️", "🔥"]
    return f"{random.choice(vibes)} {random.choice(emojis)}"

# --- Hàm gọi Google Gemini API (thay thế Groq) ---
async def get_gemini_response(messages, model_config):
    """
    Gọi Google Gemini API với format chuẩn [citation:4]
    """
    try:
        # Chuyển đổi format messages từ Groq style sang Gemini style
        contents = []
        for msg in messages:
            if msg["role"] == "system":
                # Gemini dùng system_instruction riêng, không để trong contents
                continue
            elif msg["role"] == "user":
                parts = []
                content = msg["content"]
                
                # Xử lý nội dung text hoặc multimodal
                if isinstance(content, list):
                    for item in content:
                        if item["type"] == "text":
                            parts.append({"text": item["text"]})
                        elif item["type"] == "image_url":
                            # Gemini yêu cầu format inline_data cho ảnh base64
                            base64_data = item["image_url"]["url"].split(",")[1]
                            parts.append({
                                "inline_data": {
                                    "mime_type": "image/jpeg",
                                    "data": base64_data
                                }
                            })
                else:
                    parts.append({"text": content})
                    
                contents.append({
                    "role": "user",
                    "parts": parts
                })
            elif msg["role"] == "assistant":
                contents.append({
                    "role": "model",
                    "parts": [{"text": msg["content"]}]
                })

        # Tìm system instruction
        system_instruction_text = None
        for msg in messages:
            if msg["role"] == "system":
                system_instruction_text = msg["content"]
                break

        # Tạo payload cho Gemini API [citation:4]
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.9,
                "maxOutputTokens": 2048
            }
        }
        
        if system_instruction_text:
            payload["system_instruction"] = {
                "parts": [{"text": system_instruction_text}]
            }

        # Gọi API
        url = f"{GEMINI_BASE_URL}/{model_config['id']}:generateContent?key={GEMINI_API_KEY}"
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    return f"Lỗi API ({response.status}): {error_text[:100]} 💀"
                
                data = await response.json()
                
                # Parse response
                if "candidates" in data and len(data["candidates"]) > 0:
                    candidate = data["candidates"][0]
                    if "content" in candidate and "parts" in candidate["content"]:
                        parts = candidate["content"]["parts"]
                        if parts and "text" in parts[0]:
                            return parts[0]["text"]
                
                return "Tao đơ rồi, không hiểu Gemini trả về gì cả 🥀"

    except Exception as e:
        return f"Lỗi r m ơi: {str(e)[:100]} (ಠ_ಠ)💔"

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"GenA-bot Ready with Google Gemini API + Gemma4! 🔥")

# ========================================================
# 3 CMDS CHÍNH
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
    embed.add_field(name="📜 Version", value="v19.0.0 (Google API)", inline=True)
    embed.add_field(name="🧠 Model hiện tại", value=f"**{CURRENT_MODEL}**", inline=False)
    embed.add_field(name="🛠️ Provider", value="Google AI Studio (Gemini API)", inline=True)
    embed.set_footer(text="Powered by Google Gemini API | By Datlun2k11 | " + random_vibe())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="update_log", description="Nhật ký update")
async def update_log(interaction: discord.Interaction):
    embed = discord.Embed(title="GenA-bot Update Log 🗒️", color=0x9b59b6)
    embed.add_field(name="v19.0.0 - Chuyển nhà", value="• Chuyển từ Groq sang Google AI Studio\n• Model ID chính xác: `gemma-4-26b-a4b-it`\n• Hỗ trợ Vision xịn sò 🥀", inline=False)
    embed.add_field(name="v18.0.1 - Vision", value="• Bật Vision cho Gemma4\n• Bot đọc được ảnh m gửi", inline=False)
    embed.set_footer(text="Updated Ngày 15/04/2026 | Google API ver")
    await interaction.response.send_message(embed=embed)

# ========================================================
# XỬ LÝ CHAT
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
            
            # Chuẩn bị user_msg_content
            user_msg_content = []
            
            if content:
                user_msg_content.append({"type": "text", "text": content})
            else:
                user_msg_content.append({"type": "text", "text": "nx"})

            # Xử lý ảnh cho Vision
            if MODELS_CONFIG[CURRENT_MODEL]["vision"] and message.attachments:
                for att in message.attachments:
                    if att.content_type and att.content_type.startswith('image/'):
                        try:
                            img_data = await att.read()
                            img_base64 = base64.b64encode(img_data).decode('utf-8')
                            img_url = f"data:{att.content_type};base64,{img_base64}"
                            
                            user_msg_content.append({
                                "type": "image_url",
                                "image_url": {"url": img_url}
                            })
                            print(f"✅ Đã nạp ảnh: {att.filename}")
                        except Exception as img_e:
                            print(f"❌ Lỗi đọc ảnh: {img_e}")

            user_msg = {"role": "user", "content": user_msg_content}
            
            chat_history[uid].append(user_msg)
            reply = await get_gemini_response(chat_history[uid], MODELS_CONFIG[CURRENT_MODEL])

            # Lưu history
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