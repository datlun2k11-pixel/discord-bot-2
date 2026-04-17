
import discord
import os
import asyncio
import aiohttp
import random
import datetime
import pytz
import base64
import json
import re
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

# --- Model Config ---
MODELS_CONFIG = {
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
    },
    "Google-Gemini3.1-Flast-Lite": {
        "id": "gemini-3.1-flash-lite-preview",
        "provider": "google",
        "vision": True
    }
}
# Sửa lại đoạn MODEL_CHOICES này cho chuẩn đét nè:
MODEL_CHOICES = [
    app_commands.Choice(name="Llama 4 Scout (GROQ - Vision)", value="Groq-Llama-Scout"),
    app_commands.Choice(name="GPT-OSS-120B (GROQ)", value="GPT-OSS-120B"),
    app_commands.Choice(name="Gemma 4 26B (Google - Vision)", value="Google-Gemma4-26B"),
    app_commands.Choice(name="Gemma 4 31B (Google - Vision)", value="Google-Gemma4-31B"),
    app_commands.Choice(name="Gemma 3 27B (Google - Vision)", value="Google-Gemma3-27B"),
    app_commands.Choice(name="Gemma 3 12B (Google - Vision)", value="Google-Gemma3-12B"),
    app_commands.Choice(name="Gemini 3.1 flash lite (Google - Vision)", value="Google-Gemini3.1-Flast-Lite")
]


CURRENT_MODEL = "Groq-Llama-Scout"

# System Prompt
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
- Developer: <@1155129530122510376> (Đạt Lùn 2k11), sống ở Thanh Hoá (36).
- Người đang chat: {user_id}"""

chat_history = {}
user_locks = {}
last_msg_time = datetime.datetime.now(pytz.timezone('Asia/Ho_Chi_Minh'))

app = Flask(__name__)
@app.route('/')
def home(): return "GenA-bot Live! 🔥"
def run_flask(): app.run(host="0.0.0.0", port=8000)

def random_vibe():
    vibes = ["(¬‿¬)", "(ಠ_ಠ)", "(•_•)", "(ง •_•)ง", "ಠ益ಠ"]
    emojis = ["💔", "🥀", "💀", "☠️", "🔥"]
    return f"{random.choice(vibes)} {random.choice(emojis)}"

# --- GROQ ---
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
# --- GOOGLE (FIXED CHO GEMMA 4 THINKING) ---
async def get_google_response(messages, model_config):
    try:
        # Tách system và user messages
        system_text = ""
        user_messages = []
        
        for m in messages:
            if m["role"] == "system":
                system_text = str(m["content"]) if m["content"] else ""
            else:
                user_messages.append(m)

        # Build contents - gắn system vào user đầu tiên
        # TẮT THINKING bằng cách KHÔNG thêm <|think|>
        contents = []
        first_user = True
        
        for m in user_messages:
            role = "model" if m["role"] == "assistant" else "user"
            parts = []
            
            if isinstance(m["content"], list):
                text_parts = []
                image_parts = []
                
                for item in m["content"]:
                    if item["type"] == "text":
                        text_parts.append(item["text"])
                    elif item["type"] == "image_url":
                        img_url = item["image_url"]["url"]
                        if img_url.startswith("data:image"):
                            header, b64_data = img_url.split(",", 1)
                            mime_type = header.split(":")[1].split(";")[0]
                            image_parts.append({
                                "inline_data": {
                                    "mime_type": mime_type,
                                    "data": b64_data
                                }
                            })
                
                # Gắn system vào text đầu tiên, KHÔNG thêm <|think|>
                if text_parts and role == "user" and first_user and system_text:
                    text_parts[0] = f"{system_text}\n\n{text_parts[0]}"
                    first_user = False
                
                for txt in text_parts:
                    parts.append({"text": txt})
                parts.extend(image_parts)
                
            else:
                text = str(m["content"]) if m["content"] else ""
                if role == "user" and first_user and system_text:
                    text = f"{system_text}\n\n{text}"
                    first_user = False
                if text.strip():
                    parts.append({"text": text})
            
            if parts:
                contents.append({"role": role, "parts": parts})
                if role == "user":
                    first_user = False

        if not contents:
            return "K có nội dung để xử lý bro 🥀"

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": 1.0,  # Gemma 4 khuyến nghị 1.0
                "maxOutputTokens": 2048,
                "topP": 0.95,
                "topK": 64  # Gemma 4 khuyến nghị 64
            },
            "safetySettings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
            ]
        }

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_config['id']}:generateContent?key={GEMINI_API_KEY}"
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers={"Content-Type": "application/json"}) as response:
                data = await response.json()
                
                if response.status != 200:
                    print(f"Google error {response.status}: {json.dumps(data, indent=2)}")
                    return f"Lỗi API {response.status}: {data.get('error', {}).get('message', 'Unknown')} 💀"
                
                # Parse response - xử lý cả trường hợp có thinking
                if "candidates" in data and len(data["candidates"]) > 0:
                    candidate = data["candidates"][0]
                    
                    if candidate.get("finishReason") == "SAFETY":
                        return "Bị chặn vì safety settings bro 🥀"
                    
                    # Check nếu có content
                    if "content" in candidate and "parts" in candidate["content"]:
                        parts = candidate["content"]["parts"]
                        
                        # Tìm text part (có thể có nhiều parts)
                        for part in parts:
                            if "text" in part:
                                res_text = part["text"]
                                
                                # Lọc thinking tags nếu có
                                res_text = re.sub(r'<\|?think\|?>.*?</?\|?think\|?>', '', res_text, flags=re.DOTALL | re.IGNORECASE).strip()
                                res_text = re.sub(r'<\|channel>thought.*?\|channel\|>', '', res_text, flags=re.DOTALL | re.IGNORECASE).strip()
                                res_text = re.sub(r'<(thinking|thought|reasoning)>.*?</\1>', '', res_text, flags=re.DOTALL | re.IGNORECASE).strip()
                                
                                if res_text:
                                    return res_text[:1900]
                        
                        # Nếu ko có text nào có nội dung
                        print(f"Empty text in parts: {json.dumps(parts, indent=2)}")
                        return "Gemma 4 trả về rỗng, thử lại đi bro 🥀"
                    
                    # Trường hợp có reasoning field (hiếm khi xảy ra với Gemini API nhưng check cho chắc)
                    elif "reasoning" in candidate:
                        return candidate["reasoning"][:1900]
                
                # Log để debug
                print(f"Unexpected response structure: {json.dumps(data, indent=2)[:800]}")
                return "Im thin thít, thử lại đi bro 🥀"

    except Exception as e:
        print(f"Google exception: {str(e)}")
        return f"Lỗi code: {str(e)[:100]} 💀"
# --- Router ---
async def get_model_response(messages, model_config):
    if model_config["provider"] == "groq":
        return await get_groq_response(messages, model_config)
    elif model_config["provider"] == "google":
        return await get_google_response(messages, model_config)
    return "Provider lạ quá m ơi 💀"

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"Đã sync {len(synced)} lệnh slash!")
    except Exception as e:
        print(f"Lỗi sync: {e}")
    print(f"GenA-bot Ready! 🔥")

# --- Commands ---
@bot.tree.command(name="model", description="Đổi model AI xịn hơn")
@app_commands.choices(chon_model=MODEL_CHOICES)
async def switch_model(interaction: discord.Interaction, chon_model: app_commands.Choice[str]):
    global CURRENT_MODEL
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
    embed.add_field(name="📜 Version", value="v19.1.0", inline=True)
    embed.add_field(name="🧠 Model", value=f"**{CURRENT_MODEL}**", inline=False)
    embed.add_field(name="🛠️ Provider", value=provider, inline=True)
    embed.add_field(name="👁️ Vision", value=vision, inline=True)
    embed.set_footer(text="Powered by Groq + Google | " + random_vibe())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="update_log", description="Nhật ký update")
async def update_log(interaction: discord.Interaction):
    embed = discord.Embed(title="GenA-bot Update Log 🗒️", color=0x9b59b6)
    embed.add_field(name="v19.1.0 - New Models", value="• Model mới `Gemini 3.1 flash lite`", inline=False)
    embed.add_field(name="v19.0.0 - Full Fix", value="• Xóa enable_thinking (lỗi 400)\n• Fix systemInstruction cho Gemma 3/4\n• Code clean lại từ đầu", inline=False)
    embed.set_footer(text="Updated 16/04/2026")
    await interaction.response.send_message(embed=embed)

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

# --- Chat Handler ---
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

            # Lưu history dạng text đơn giản
            text_content = content if content else "[Đã gửi ảnh]"
            chat_history[uid][-1] = {"role": "user", "content": text_content}
            chat_history[uid].append({"role": "assistant", "content": reply})
            
            # Giữ tối đa 20 messages
            if len(chat_history[uid]) > 21:
                chat_history[uid] = [chat_history[uid][0]] + chat_history[uid][-20:]

            await message.reply(f"{reply[:1900]}", mention_author=False)
        except Exception as e:
            print(f"Lỗi chat: {str(e)}")
            await message.reply(f"Lỗi r: {str(e)[:100]} 💀", mention_author=False)

if __name__ == "__main__":
    thread = Thread(target=run_flask)
    thread.daemon = True
    thread.start()
    bot.run(os.getenv("DISCORD_TOKEN"))