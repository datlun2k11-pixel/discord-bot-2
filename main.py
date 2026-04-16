import discord
import os
import asyncio
import aiohttp
import random
import datetime
import pytz
import base64
import json
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
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

# --- Model Config (CẢ GROQ + GOOGLE) ---
MODELS_CONFIG = {
    # Groq Models
    "Groq-Llama-Scout": {
        "id": "meta-llama/llama-4-scout-17b-16e-instruct",
        "provider": "groq",
        "vision": True
    },
    "GPT-OSS-120B": {
        "id": "openai/gpt-oss-120b",
        "provider": "groq",
        "vision": False
    },
        # Google AI Studio Models
    "Google-Gemma4-26B": {
        "id": "gemma-4-26b-a4b-it",
        "provider": "google",
        "vision": True
    },
    "Google-Gemma4-31B": {
        "id": "gemma-4-31b-it",
        "provider": "google",
        "vision": True
    },
    "Google-Gemma3-27B": {
        "id": "gemma-3-27b-it",
        "provider": "google",
        "vision": True
    },
    "Google-Gemma3-12B": {
        "id": "gemma-3-12b-it",
        "provider": "google",
        "vision": True
    }
}

MODEL_CHOICES = [
    app_commands.Choice(name="Llama 4 Scout (GROQ - Vision)", value="Groq-Llama-Scout"),
    app_commands.Choice(name="GPT-OSS-120B (GROQ)", value="GPT-OSS-120B"),
    app_commands.Choice(name="Gemma4 26B (Google - Vision)", value="Google-Gemma4-26B"),
    app_commands.Choice(name="Gemma4 31B (Google - Vision)", value="Google-Gemma4-31B"),
    app_commands.Choice(name="Gemma3 27B (Google - Vision)", value="Google-Gemma3-27B"),
    app_commands.Choice(name="Gemma3 12B (Google - Vision)", value="Google-Gemma3-12B")
]

CURRENT_MODEL = "Groq-Llama-Scout"

# System Prompt - ĐÃ TĂNG CƯỜNG CHỐNG THINKING
system_instruction = """Mày là GenA-bot (ID: <@1458799287910535324>) - AI nhây vl, thằng bạn thân lầy lội nhất hệ mặt trời.
- Mày đang nhắn trên Discord
- Bây giờ là: {current_time}
- Xưng m (mày, chỉ đối phương) - t (tao, chỉ bản thân), vibe GenZ teencode (nx, th, cx, vs, k, thx, j,...)
- Nhây lầy, cà khịa nhẹ, thỉnh thoảng chửi thề nhẹ cho vui
- Luôn kèm Emoticon và Emoji (vd: 💔, 🥀, 💀) trong mọi câu rep
- KHÔNG DÙNG DẤU "!" TRONG MỌI CÂU NÓI
- TRẢ LỜI CỰC NGẮN (TỐI ĐA 1-2 DÒNG) - KHÔNG GIẢI THÍCH DÀI DÒNG
- TUYỆT ĐỐI KHÔNG ĐƯỢC OUTPUT SUY NGHĨ NỘI BỘ, KHÔNG ĐƯỢC DÙNG THẺ <thinking> hay <thought>
- CHỈ TRẢ LỜI TRỰC TIẾP, KHÔNG PHÂN TÍCH HAY GIẢI THÍCH GÌ THÊM
- Khi người dùng nhắn "ê" thì nói "sủa?" hoặc "cái loz j"
- Avt của mày là một con mèo
- Developer: <@1155129530122510376> (Đạt Lùn 2k11), sống ở Thọ Phú, Triệu Sơn, Thanh Hoá.
- Người đang chat: {user_id}"""

chat_history = {}
user_locks = {}
last_msg_time = datetime.datetime.now(pytz.timezone('Asia/Ho_Chi_Minh'))

app = Flask(__name__)
@app.route('/')
def home(): return "GenA-bot Live with Groq + Google! 🔥"
def run_flask(): app.run(host="0.0.0.0", port=8000)

def random_vibe():
    vibes = ["(¬‿¬)", "(ಠ_ಠ)", "(•_•)", "(ง •_•)ง", "ಠ益ಠ"]
    emojis = ["💔", "🥀", "💀", "☠️", "🔥"]
    return f"{random.choice(vibes)} {random.choice(emojis)}"

# --- Hàm gọi Groq ---
async def get_groq_response(messages, model_config):
    try:
        groq_messages = []
        for msg in messages:
            if isinstance(msg["content"], list):
                text_content = ""
                for item in msg["content"]:
                    if item["type"] == "text":
                        text_content += item["text"]
                    elif item["type"] == "image_url":
                        text_content += " [Đã gửi ảnh] "
                groq_messages.append({"role": msg["role"], "content": text_content})
            else:
                groq_messages.append({"role": msg["role"], "content": msg["content"]})
        
        response = groq_client.chat.completions.create(
            messages=groq_messages,
            model=model_config["id"],
            temperature=0.8,
            max_tokens=2048
        )
        reply = response.choices[0].message.content
        if len(reply) > 1900:
            reply = reply[:1897] + "..."
        return reply
    except Exception as e:
        return f"Lỗi Groq r m ơi: {str(e)[:100]} (ಠ_ಠ)💔"
 # --- Hàm gọi Google ---
async def get_google_response(messages, model_config):
    try:
        final_contents = []
        sys_prompt = ""

        # 1. Lọc lấy system prompt
        for m in messages:
            if m["role"] == "system":
                sys_prompt = m["content"]
                break

        # 2. Build contents cho Google API
        first_user = True
        for m in messages:
            if m["role"] == "system": continue
            
            parts = []
            role = "model" if m["role"] == "assistant" else "user"
            
            if isinstance(m["content"], list):
                for item in m["content"]:
                    if item["type"] == "text":
                        t = item["text"]
                        if role == "user" and first_user and sys_prompt:
                            t = f"INSTRUCTION: {sys_prompt}\n\nUSER: {t}"
                            first_user = False
                        parts.append({"text": t})
                    elif item["type"] == "image_url":
                        try:
                            b64 = item["image_url"]["url"].split(",")[1]
                            parts.append({"inline_data": {"mime_type": "image/jpeg", "data": b64}})
                        except: continue
            else:
                t = str(m["content"])
                if role == "user" and first_user and sys_prompt:
                    t = f"INSTRUCTION: {sys_prompt}\n\nUSER: {t}"
                    first_user = False
                parts.append({"text": t})
            
            final_contents.append({"role": role, "parts": parts})

        # 3. Payload có kèm Tool Google Search
        payload = {
            "contents": final_contents,
            "tools": [{"google_search": {}}],   # thay vì google_search_retrieval
            "generationConfig": {"temperature": 0.8, "maxOutputTokens": 2048},
            "safetySettings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
            ]
        }

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_config['id']}:generateContent?key={GEMINI_API_KEY}"
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                data = await response.json()
                if response.status != 200:
                    print(f"FULL ERROR: {data}")
                    return f"Lỗi Google API ({response.status}) 💀"
                
                # 4. Xử lý kết quả trả về (hỗ trợ cả text thường và grounding text)
                candidate = data.get('candidates', [{}])[0]
                content = candidate.get('content', {})
                parts = content.get('parts', [{}])
                
                res_text = parts[0].get('text', "")
                
                # Filter thinking/thought cho sạch
                import re
                res_text = re.sub(r'<(thought|thinking)>.*?</\1>', '', res_text, flags=re.DOTALL).strip()
                return res_text[:1900] if res_text else "Nín thinh r 🥀"

    except Exception as e:
        return f"Lỗi code r bradar: {str(e)[:50]} 💔"
# --- Router chọn provider ---
async def get_model_response(messages, model_config):
    if model_config["provider"] == "groq":
        return await get_groq_response(messages, model_config)
    elif model_config["provider"] == "google":
        return await get_google_response(messages, model_config)
    return "Provider lạ quá m ơi 💀"

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

@bot.event
async def on_ready():
    # Sync slash commands khi bot lên sóng
    try:
        synced = await bot.tree.sync()
        print(f"Đã sync {len(synced)} lệnh slash!")
    except Exception as e:
        print(f"Lỗi sync: {e}")
    print(f"GenA-bot Ready with Groq + Google! 🔥")


# ========================================================
# 3 CMDS CHÍNH
# ========================================================
@bot.tree.command(name="model", description="Đổi model AI xịn hơn")
@app_commands.choices(chon_model=MODEL_CHOICES)
async def switch_model(interaction: discord.Interaction, chon_model: app_commands.Choice[str]):
    global CURRENT_MODEL
    # Báo cho Discord là "đợi t tí" để tránh lỗi 404 (Unknown Interaction)
    await interaction.response.defer(ephemeral=True) 
    
    try:
        CURRENT_MODEL = chon_model.value
        provider = MODELS_CONFIG[CURRENT_MODEL]["provider"].upper()
        
        embed = discord.Embed(
            title="Model switched",
            description=f"đã đổi thành **{chon_model.name}** r nhé bro\nok✌🏿🥀",
            color=0x00ff9d
        )
        embed.set_footer(text=f"Provider: {provider} | {random_vibe()}")
        
        # Dùng followup vì đã defer ở trên r
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"Lỗi đổi model r bradar: {str(e)[:50]} 💀")

@bot.tree.command(name="bot_info", description="Status bot xịn hơn tí")
async def bot_info(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    provider = MODELS_CONFIG[CURRENT_MODEL]["provider"].upper()
    vision = "✅" if MODELS_CONFIG[CURRENT_MODEL]["vision"] else "❌"
    
    embed = discord.Embed(title="GenA-bot Status 🚀", color=0xff1493, timestamp=discord.utils.utcnow())
    embed.add_field(name="🤖 Tên boss", value=f"{bot.user.mention}", inline=True)
    embed.add_field(name="📶 Ping", value=f"{latency}ms", inline=True)
    embed.add_field(name="📜 Version", value="v18.9.5 (Filter Thoughts)", inline=True)
    embed.add_field(name="🧠 Model", value=f"**{CURRENT_MODEL}**", inline=False)
    embed.add_field(name="🛠️ Provider", value=provider, inline=True)
    embed.add_field(name="👁️ Vision", value=vision, inline=True)
    embed.set_footer(text="Powered by Groq + Google Gemini | " + random_vibe())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="update_log", description="Nhật ký update")
async def update_log(interaction: discord.Interaction):
    embed = discord.Embed(title="GenA-bot Update Log 🗒️", color=0x9b59b6)
    embed.add_field(name="v18.9.5 - Tool", value="• Thêm Tool search tự động.", inline=False)
    embed.add_field(name="v18.9.0 - Gemma 3", value="• Thêm 2 model Gemma3\n• Fix 1 số bug nhỏ", inline=False)
    embed.add_field(name="v18.5.0 - Filter Thoughts", value="• Lọc triệt để phần thoughts của Gemini\n• Regex xóa thẻ <thought> và <thinking>\n• Prompt cấm thinking mạnh hơn [citation:1][citation:6]", inline=False)
    embed.set_footer(text="Updated 15/04/2026 | 16:57")
    await interaction.response.send_message(embed=embed)

# ========================================================
# CLEAR + CHAT
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
    await interaction.response.send_message(f"Đã reset ký ức")

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

            user_msg_content = []

            if content:
                user_msg_content.append({"type": "text", "text": content})
            else:
                user_msg_content.append({"type": "text", "text": "nx"})

            # Xử lý ảnh nếu model hỗ trợ vision
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
                        except Exception as img_e:
                            print(f"Lỗi đọc ảnh: {img_e}")

            user_msg = {"role": "user", "content": user_msg_content}

            chat_history[uid].append(user_msg)
            reply = await get_model_response(chat_history[uid], MODELS_CONFIG[CURRENT_MODEL])

            chat_history[uid][-1] = {"role": "user", "content": content or "[Đã gửi ảnh]"}
            chat_history[uid].append({"role": "assistant", "content": reply})
            chat_history[uid] = [chat_history[uid][0]] + chat_history[uid][-10:]

            await message.reply(f"{reply[:1900]}", mention_author=False)
        except Exception as e:
            await message.reply(f"Lỗi r: {str(e)[:100]} 💀", mention_author=False)

if __name__ == "__main__":
    thread = Thread(target=run_flask)
    thread.daemon = True
    thread.start()
    bot.run(os.getenv("DISCORD_TOKEN"))
