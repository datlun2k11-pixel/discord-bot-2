# AI coded
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
import io
import time
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
    "Google-Gemini-3.1-Flash-Lite": {
        "id": "gemini-3.1-flash-lite-preview",
        "provider": "google",
        "vision": True
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
    }
}

MODEL_CHOICES = [
    app_commands.Choice(name="Llama 4 Scout (GROQ - Vision)", value="Groq-Llama-Scout"),
    app_commands.Choice(name="GPT-OSS-120B (GROQ)", value="GPT-OSS-120B"),
    app_commands.Choice(name="Gemini 3.1 Flash Lite (Google - Vision)", value="Google-Gemini-3.1-Flash-Lite"),
    app_commands.Choice(name="Gemma4 26B (Google - Vision)", value="Google-Gemma4-26B"),
    app_commands.Choice(name="Gemma4 31B (Google - Vision)", value="Google-Gemma4-31B"),
    app_commands.Choice(name="Gemma3 27B (Google - Vision)", value="Google-Gemma3-27B"),
    app_commands.Choice(name="Gemma3 12B (Google - Vision)", value="Google-Gemma3-12B")
]

CURRENT_MODEL = "Groq-Llama-Scout"

TEXT_EXTENSIONS = {
    'py', 'txt', 'md', 'json', 'js', 'html', 'css', 'cpp', 'c', 'h', 
    'java', 'cs', 'php', 'rb', 'go', 'rs', 'swift', 'kt', 'sql', 'xml',
    'yaml', 'yml', 'ini', 'cfg', 'conf', 'sh', 'bat', 'ps1', 'ts', 'tsx',
    'jsx', 'vue', 'sass', 'scss', 'less', 'dockerfile', 'gitignore'
}

# System Prompt
system_instruction = """Mày là GenA-bot (ID: <@1458799287910535324>) - AI nhây vl, thằng bạn thân lầy lội nhất hệ mặt trời.
- Mày đang nhắn trên Discord
- Bây giờ là: {current_time}
- Xưng m (mày, chỉ đối phương) - t (tao, chỉ bản thân), vibe GenZ teencode (nx, th, cx, vs, k, thx, j,...)
- Nhây lầy, cà khịa nhẹ, thỉnh thoảng chửi thề nhẹ cho vui
- Luôn kèm Emoticon và Emoji (vd: 💔, 🥀, 💀, 🫩, ✌🏿,...) trong mọi câu rep
- KHÔNG DÙNG DẤU "!" TRONG MỌI CÂU NÓI
- TRẢ LỜI CỰC NGẮN (TỐI ĐA 1-2 DÒNG) - KHÔNG GIẢI THÍCH DÀI DÒNG
- TUYỆT ĐỐI KHÔNG ĐƯỢC OUTPUT SUY NGHĨ NỘI BỘ, KHÔNG ĐƯỢC DÙNG THẺ <thinking> hay <thought>
- CHỈ TRẢ LỜI TRỰC TIẾP, KHÔNG PHÂN TÍCH HAY GIẢI THÍCH GÌ THÊM
- Khi ngườí dùng nhắn "ê" thì nói "sủa?" hoặc "cái loz j"
- Avt của mày là một con mèo
- Developer: <@1155129530122510376> (Đạt Lùn 2k11), sống ở Thanh Hoá (36).
- Ngườí đang chat: {user_id}
- Khi cần thông tin mới/real-time, PHẢI dùng Google Search và trích dẫn nguồn
- Do mày là bot discord, đây là các commands: `/model`, `/bot_info`, `/clear`(xoá ký ức), `/update_log`, `/ship`, `/quiz`, `/quiz_score`"""

# === GLOBALS ===
chat_history = {}
user_locks = {}
last_msg_time = datetime.datetime.now(pytz.timezone('Asia/Ho_Chi_Minh'))

# Quiz globals
quiz_active = {}
quiz_scores = {}

app = Flask(__name__)
@app.route('/')
def home(): return "GenA-bot Live! 🔥"
def run_flask(): app.run(host="0.0.0.0", port=8000)

def random_vibe():
    vibes = ["(¬‿¬)", "(ಠ_ಠ)", "(•_•)", "(ง •_•)ง", "ಠ益ಠ"]
    emojis = ["💔", "🥀", "💀", "☠️", "🔥"]
    return f"{random.choice(vibes)} {random.choice(emojis)}"

async def read_text_attachment(attachment):
    try:
        content = await attachment.read()
        try:
            text = content.decode('utf-8')
        except UnicodeDecodeError:
            text = content.decode('latin-1')
        return text[:15000]
    except Exception as e:
        return f"[Lỗi đọc file: {str(e)[:50]}]"

def format_code_snippet(filename, content, max_lines=50):
    lines = content.split('\n')
    if len(lines) > max_lines:
        content = '\n'.join(lines[:max_lines]) + f"\n\n... ({len(lines) - max_lines} dòng còn lại) ..."
    ext = filename.split('.')[-1].lower() if '.' in filename else 'txt'
    return f"```{ext}\n{content}\n```"

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

# --- GOOGLE ---
async def get_google_response(messages, model_config):
    try:
        system_text = ""
        user_messages = []

        for m in messages:
            if m["role"] == "system":
                system_text = str(m["content"]) if m["content"] else ""
            else:
                user_messages.append(m)

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
                "temperature": 1.0,
                "maxOutputTokens": 2048,
                "topP": 0.95,
                "topK": 64
            },
            **({"tools": [{"google_search": {}}]} if "gemma-3" not in model_config["id"] else {}),
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

                if "candidates" in data and len(data["candidates"]) > 0:
                    candidate = data["candidates"][0]

                    if candidate.get("finishReason") == "SAFETY":
                        return "Bị chặn vì safety settings bro 🥀"

                    if "content" in candidate and "parts" in candidate["content"]:
                        parts = candidate["content"]["parts"]

                        for part in parts:
                            if "text" in part:
                                res_text = part["text"]
                                res_text = re.sub(r'<\|?think\|?>.*?</?\|?think\|?>', '', res_text, flags=re.DOTALL | re.IGNORECASE).strip()
                                res_text = re.sub(r'<\|channel>thought.*?\|channel\|>', '', res_text, flags=re.DOTALL | re.IGNORECASE).strip()
                                res_text = re.sub(r'<(thinking|thought|reasoning)>.*?</\1>', '', res_text, flags=re.DOTALL | re.IGNORECASE).strip()

                                if res_text:
                                    sources = []
                                    if "groundingMetadata" in candidate:
                                        grounding = candidate["groundingMetadata"]
                                        if "groundingChunks" in grounding:
                                            for chunk in grounding["groundingChunks"]:
                                                if "web" in chunk:
                                                    web = chunk["web"]
                                                    title = web.get("title", "Unknown")
                                                    uri = web.get("uri", "")
                                                    sources.append(f"• [{title}]({uri})")

                                    final_reply = res_text[:1800]
                                    if sources:
                                        final_reply += "\n\n📚 **Nguồn:**\n" + "\n".join(sources[:3])

                                    return final_reply

                        print(f"Empty text in parts: {json.dumps(parts, indent=2)}")
                        return "Gemma 4 trả về rỗng, thử lại đi bro 🥀"

                    elif "reasoning" in candidate:
                        return candidate["reasoning"][:1900]

                print(f"Unexpected response: {json.dumps(data, indent=2)[:800]}")
                return "Im thin thít, thử lại đi bro 🥀"

    except Exception as e:
        print(f"Google exception: {str(e)}")
        return f"Lỗi code: {str(e)[:100]} 💀"

async def get_model_response(messages, model_config):
    if model_config["provider"] == "groq":
        return await get_groq_response(messages, model_config)
    elif model_config["provider"] == "google":
        return await get_google_response(messages, model_config)
    return "Provider lạ quá m ơi 💀"

# === BOT SETUP ===
bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"Đã sync {len(synced)} lệnh slash!")
    except Exception as e:
        print(f"Lỗi sync: {e}")
    print(f"GenA-bot Ready! 🔥")

# === COMMANDS ===

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
    embed.add_field(name="📜 Version", value="v20.1.5", inline=True)
    embed.add_field(name="🧠 Model", value=f"**{CURRENT_MODEL}**", inline=False)
    embed.add_field(name="🛠️ Provider", value=provider, inline=True)
    embed.add_field(name="👁️ Vision", value=vision, inline=True)
    embed.add_field(name="💾 Memory", value="15 msgs/channel", inline=True)
    embed.set_footer(text="Powered by Groq + Google | " + random_vibe())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="update_log", description="Nhật ký update")
async def update_log(interaction: discord.Interaction):
    embed = discord.Embed(title="GenA-bot Update Log 🗒️", color=0x9b59b6)
    embed.add_field(name="v20.1.5 - Full Rewrite", value="• Fix /clear command\n• Fix /ship command\n• Thêm /quiz + /quiz_score\n• Keyword trigger stable\n• Sửa lỗi bot rep sau khi trl câu hỏi\n• Sửa lỗi Quiz bị lặp lại", inline=False)
    embed.add_field(name="v19.5.0 - Channel Memory", value="• Nhìn thấy tất cả tin nhắn trong kênh\n• Chỉ rep khi được mention/reply/DM/keyword", inline=False)
    embed.set_footer(text="Updated 20/04/2026")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="clear", description="Reset ký ức cho bot đỡ ngáo")
async def clear(interaction: discord.Interaction):
    uid = str(interaction.channel.id)
    is_dm = isinstance(interaction.channel, discord.DMChannel)

    if is_dm:
        uid = str(interaction.user.id)

    tz_VN = pytz.timezone('Asia/Ho_Chi_Minh')
    now = datetime.datetime.now(tz_VN).strftime("%H:%M:%S %d/%m/%Y")
    channel_name = interaction.channel.name if hasattr(interaction.channel, 'name') else 'DM'
    current_sys = system_instruction.format(
        user_id=f"Multiple users in {channel_name}",
        current_time=now
    )
    chat_history[uid] = [{"role": "system", "content": current_sys}]
    await interaction.response.send_message(f"Đã reset ký ức (cho kênh) 🥀")

@bot.tree.command(name="ship", description="Ship 2 người random hoặc tự chọn 💘")
@app_commands.describe(
    user1="Người thứ nhất (để trống = random)",
    user2="Người thứ hai (để trống = random)"
)
async def ship(interaction: discord.Interaction, user1: discord.Member = None, user2: discord.Member = None):
    await interaction.response.defer()

    members = [m for m in interaction.guild.members if not m.bot and m != interaction.user]

    if len(members) < 2:
        await interaction.followup.send("Server có mỗi mình m à, ship với ai 💔")
        return

    if user1 is None:
        user1 = random.choice(members)
    if user2 is None:
        user2 = random.choice([m for m in members if m != user1])

    if user1 == user2:
        user2 = random.choice([m for m in members if m != user1])

    combined = str(user1.id) + str(user2.id)
    random.seed(combined)
    love_percent = random.randint(1, 100)
    random.seed()

    if love_percent >= 90:
        tier, color, emojis, desc = "SOULMATES 💍", 0xff0066, ["💘", "🔥", "💍", "🥰"], "Cặp đôi trời sinh, cưới luôn đi m ơi"
    elif love_percent >= 70:
        tier, color, emojis, desc = "HIGH KEY SHIP 🌹", 0xff1493, ["🌹", "💖", "✨", "😍"], "Tình yêu đẹp vl, ship chính thức"
    elif love_percent >= 50:
        tier, color, emojis, desc = "CÓ CƠM GẮP THỊT 🍚", 0xff69b4, ["🍚", "🥢", "💕", "😏"], "Cũng được đó, thử hẹn hò đi"
    elif love_percent >= 30:
        tier, color, emojis, desc = "FRIENDZONE 🫂", 0xdda0dd, ["🫂", "💔", "😢", "🥲"], "Tình bạn đẹp, nhưng chỉ là bạn thôi"
    elif love_percent >= 10:
        tier, color, emojis, desc = "CHÁN VL 😴", 0x808080, ["😴", "💀", "😐", "🚮"], "Ko hợp nhau r, bỏ đi"
    else:
        tier, color, emojis, desc = "THÙ ĐỊCH ☠️", 0x1a1a1a, ["☠️", "🔪", "💀", "🤮"], "Ghét nhau đi, đừng gặp lại"

    bar = "█" * (love_percent // 10) + "░" * (10 - love_percent // 10)

    embed = discord.Embed(
        title=f"{random.choice(emojis)} SHIP MACHINE {random.choice(emojis)}",
        description=f"**{user1.display_name}** 💘 **{user2.display_name}**",
        color=color
    )
    embed.add_field(name="Loving", value=f"`{bar}` {love_percent}%", inline=False)
    embed.add_field(name="Tier", value=f"**{tier}**", inline=True)
    embed.add_field(name="Comment", value=desc, inline=True)

    try:
        embed.set_thumbnail(url=user1.display_avatar.url)
        embed.set_image(url=user2.display_avatar.url)
    except:
        pass

    embed.set_footer(text=f"Requested by {interaction.user.display_name} | {random_vibe()}")
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="meme", description="Gửi meme VN random xả stress")
@app_commands.describe(số_lượng="Số meme muốn gửi (1-5, mặc định 1)")
async def meme(interaction: discord.Interaction, số_lượng: int = 1):
    await interaction.response.defer()

    if số_lượng < 1 or số_lượng > 5:
        await interaction.followup.send("Gửi 1-5 meme thôi, muốn t bị ban à 💔")
        return

    memes_sent = 0

    async with aiohttp.ClientSession() as session:
        for i in range(số_lượng):
            try:
                async with session.get("https://phimtat.vn/api/random-meme/") as resp:
                    if resp.status == 200:
                        img_data = await resp.read()
                        file = discord.File(io.BytesIO(img_data), filename=f"meme_{i+1}.jpg")

                        if i == 0:
                            await interaction.followup.send(file=file)
                        else:
                            await interaction.channel.send(file=file)

                        memes_sent += 1
                    else:
                        error_msg = f"💀 API đang die, status {resp.status}"
                        if i == 0:
                            await interaction.followup.send(error_msg)
                        else:
                            await interaction.channel.send(error_msg)

            except Exception as e:
                error_msg = f"🥹 Lỗi rồi m: {str(e)[:50]}"
                if i == 0:
                    await interaction.followup.send(error_msg)
                else:
                    await interaction.channel.send(error_msg)

    if số_lượng > 1 and memes_sent > 0:
        await interaction.channel.send(f"✅ Đã gửi {memes_sent} meme")

# === QUIZ COMMANDS ===
@bot.tree.command(name="quiz", description="Hỏi câu hỏi AI generated, trả lời đúng +1 điểm 🧠")
@app_commands.describe(
    chủ_đề="Chủ đề câu hỏi (mặc định: random)",
    độ_khó="Dễ/Trung bình/Khó (mặc định: Trung bình)"
)
@app_commands.choices(độ_khó=[
    app_commands.Choice(name="Dễ", value="dễ"),
    app_commands.Choice(name="Trung bình", value="trung bình"),
    app_commands.Choice(name="Khó", value="khó")
])
async def quiz(interaction: discord.Interaction, chủ_đề: str = "random", độ_khó: app_commands.Choice[str] = None):
    await interaction.response.defer()

    channel_id = str(interaction.channel_id)
    độ_khó_value = độ_khó.value if độ_khó else "trung bình"

    if channel_id in quiz_active:
        await interaction.followup.send("Đang có câu hỏi rồi m, trả lời đi r hỏi tiếp 💀")
        return

    quiz_prompt = f"""Tạo 1 câu hỏi trắc nghiệm chủ đề: {chủ_đề}, độ khó: {độ_khó_value}.
SEED: {int(time.time())}
YÊU CẦU:
- Câu hỏi ngắn gọn, thú vị
- 4 đáp án A/B/C/D
- Chỉ 1 đáp án đúng
- Format chính xác:
CÂU HỎI: [nội dung câu hỏi]
A. [đáp án A]
B. [đáp án B]
C. [đáp án C]
D. [đáp án D]
ĐÁP ÁN: [chữ cái đúng A/B/C/D]
GIẢI THÍCH: [giải thích ngắn 1 dòng]"""

    try:
        temp_messages = [
            {"role": "system", "content": "Mày là bot tạo câu hỏi quiz thú vị, ngắn gọn."},
            {"role": "user", "content": quiz_prompt}
        ]

                raw_response = await get_model_response(temp_messages, MODELS_CONFIG[CURRENT_MODEL])

        lines = raw_response.strip().splitlines()
        question_lines = []
        answer_map = {}
        correct_answer = None
        explanation = ""

        for line in lines:
            line = line.strip()
            if line.startswith("CÂU HỎI:"):
                question_lines.append(line.replace("CÂU HỎI:", "").strip())
            elif line.startswith(("A.", "B.", "C.", "D.")):
                letter = line[0]
                answer_text = line[2:].strip()
                answer_map[letter] = answer_text
                question_lines.append(line)
            elif line.startswith("ĐÁP ÁN:"):
                correct_answer = line.replace("ĐÁP ÁN:", "").strip().upper()
            elif line.startswith("GIẢI THÍCH:"):
                explanation = line.replace("GIẢI THÍCH:", "").strip()

        if not correct_answer or correct_answer not in answer_map:
            await interaction.followup.send("AI tạo câu hỏi lỗi r, thử lại đi 🥀")
            return

        quiz_active[channel_id] = {
            "question": "
".join(question_lines),
            "answer": correct_answer,
            "started_by": interaction.user.id,
            "explanation": explanation
        }

        if channel_id not in quiz_scores:
            quiz_scores[channel_id] = {}

        embed = discord.Embed(
            title=f"🧠 QUIZ TIME - {chủ_đề.upper()}",
            description="
".join(question_lines),
            color=0xffd700
        )
        embed.set_footer(text=f"Độ khó: {độ_khó_value} | Trả lời bằng chữ A/B/C/D | {random_vibe()}")

        await interaction.followup.send(embed=embed)

        await asyncio.sleep(60)
        if channel_id in quiz_active:
            old_quiz = quiz_active.pop(channel_id)
            await interaction.channel.send(f"⏰ Hết giờ rồi m! Đáp án đúng là **{old_quiz['answer']}**. {old_quiz.get('explanation', '')}")

    except Exception as e:
        print(f"Lỗi quiz: {e}")
        await interaction.followup.send(f"Lỗi tạo câu hỏi r: {str(e)[:50]} 💀")

@bot.tree.command(name="quiz_score", description="Xem bảng xếp hạng quiz server 🏆")
async def quiz_score(interaction: discord.Interaction):
    channel_id = str(interaction.channel_id)

    if channel_id not in quiz_scores or not quiz_scores[channel_id]:
        await interaction.response.send_message("Chưa ai chơi quiz ở đây cả 🥀")
        return

    scores = quiz_scores[channel_id]
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    embed = discord.Embed(title="🏆 BẢNG XẾP HẠNG QUIZ", color=0xffd700)

    for i, (user_id, score) in enumerate(sorted_scores[:10], 1):
        user = interaction.guild.get_member(int(user_id))
        name = user.display_name if user else f"User_{user_id[:6]}"
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, "💩")
        embed.add_field(name=f"{medal} #{i} {name}", value=f"{score} điểm", inline=False)

    embed.set_footer(text=random_vibe())
    await interaction.response.send_message(embed=embed)

# === MAIN MESSAGE HANDLER ===
@bot.event
async def on_message(message):
    global last_msg_time

    if not message.author.bot:
        last_msg_time = datetime.datetime.now(pytz.timezone('Asia/Ho_Chi_Minh'))

    if message.author.bot:
        return

    is_dm = isinstance(message.channel, discord.DMChannel)

    if is_dm:
        uid = str(message.author.id)
    else:
        uid = str(message.channel.id)

    # PASSIVE MONITORING
    if uid not in chat_history:
        tz_VN = pytz.timezone('Asia/Ho_Chi_Minh')
        now = datetime.datetime.now(tz_VN).strftime("%H:%M:%S %d/%m/%Y")
        channel_name = message.channel.name if hasattr(message.channel, 'name') else 'DM'
        current_sys = system_instruction.format(
            user_id=f"Multiple users in {channel_name}",
            current_time=now
        )
        chat_history[uid] = [{"role": "system", "content": current_sys}]

    msg_preview = message.content[:300] if message.content else "[ảnh/file]"
    display_name = message.author.display_name
    preview_msg = f"{display_name}: {msg_preview}"

    chat_history[uid].append({"role": "user", "content": preview_msg})

    if len(chat_history[uid]) > 16:
        chat_history[uid] = [chat_history[uid][0]] + chat_history[uid][-15:]

    # QUIZ ANSWER CHECK - TÁCH BIỆT KHỎI CHAT MEMORY
    channel_id = str(message.channel.id)
    if channel_id in quiz_active and not message.author.bot:
        content_upper = message.content.strip().upper()
        if content_upper in ['A', 'B', 'C', 'D']:
            quiz = quiz_active[channel_id]
            if content_upper == quiz["answer"]:
                user_id = str(message.author.id)
                quiz_scores[channel_id][user_id] = quiz_scores[channel_id].get(user_id, 0) + 1
                old_quiz = quiz_active.pop(channel_id)
                await message.reply(f"✅ **ĐÚNG RỒI!** +1 điểm! {old_quiz.get('explanation', '')} 🎉")
            else:
                await message.reply(f"❌ **SAI RỒI!** Đáp án đúng là **{quiz['answer']}** 🥀")
                quiz_active.pop(channel_id)

            # XÓA TIN NHẮN TRẢ LỜI QUIZ KHỎI CHAT_HISTORY
            if uid in chat_history and len(chat_history[uid]) > 1:
                chat_history[uid].pop()  # Xóa tin nhắn "A"/"B"/"C"/"D"

            return  # KO GỌI AI CHAT

    # CHECK TRIGGER
    is_mentioned = bot.user in message.mentions
    is_reply_to_bot = False

    if message.reference:
        try:
            ref_msg = await message.channel.fetch_message(message.reference.message_id)
            is_reply_to_bot = (ref_msg.author.id == bot.user.id)
        except:
            pass

    trigger_keywords = ["ê bot", "ê ai", "bot ơi", "ai ơi", "gena", "gena bot", "gena-bot", "gen ai", "gen a"]
    content_lower = message.content.lower()
    is_keyword_trigger = any(keyword in content_lower for keyword in trigger_keywords)

    if not (is_mentioned or is_dm or is_reply_to_bot or is_keyword_trigger):
        return

    # PROCESS REPLY
    lock = user_locks.get(uid, asyncio.Lock())
    user_locks[uid] = lock
    if lock.locked():
        return

    async with lock:
        await message.channel.typing()

        try:
            content = message.content
            for mention in message.mentions:
                content = content.replace(mention.mention, "").strip()

            user_msg_content = []
            file_contents = []

            if content:
                user_msg_content.append({"type": "text", "text": f"{message.author.display_name} hỏi: {content}"})
            else:
                user_msg_content.append({"type": "text", "text": f"{message.author.display_name}: [gửi ảnh/file]"})

            if message.attachments:
                for att in message.attachments:
                    filename = att.filename.lower()
                    ext = filename.split('.')[-1] if '.' in filename else ''

                    if MODELS_CONFIG[CURRENT_MODEL]["vision"] and att.content_type and att.content_type.startswith('image/'):
                        try:
                            img_data = await att.read()
                            img_base64 = base64.b64encode(img_data).decode('utf-8')
                            img_url = f"data:{att.content_type};base64,{img_base64}"
                            user_msg_content.append({"type": "image_url", "image_url": {"url": img_url}})
                        except Exception as img_e:
                            print(f"Lỗi đọc ảnh: {img_e}")

                    elif ext in TEXT_EXTENSIONS or att.content_type in ['text/plain', 'text/x-python', 'text/html', 'text/css', 'application/json', 'text/javascript', 'application/javascript']:
                        try:
                            file_text = await read_text_attachment(att)
                            formatted = format_code_snippet(att.filename, file_text)
                            file_contents.append(f"📄 **File: `{att.filename}`**\n{formatted}")
                        except Exception as file_e:
                            print(f"Lỗi đọc file {att.filename}: {file_e}")

            if file_contents:
                file_summary = "\n\n".join(file_contents)
                original_text = user_msg_content[0]["text"]
                user_msg_content[0]["text"] = f"{original_text}\n\n{file_summary}\n\nPhân tích giúp t đi m 🥀"

            if len(chat_history[uid]) > 1:
                chat_history[uid].pop()

            user_msg = {"role": "user", "content": user_msg_content}
            chat_history[uid].append(user_msg)

            reply = await get_model_response(chat_history[uid], MODELS_CONFIG[CURRENT_MODEL])

            chat_history[uid].append({"role": "assistant", "content": reply})

            if len(chat_history[uid]) > 16:
                chat_history[uid] = [chat_history[uid][0]] + chat_history[uid][-15:]

            await message.reply(f"{reply[:1900]}", mention_author=False)

        except Exception as e:
            print(f"Lỗi chat: {str(e)}")
            await message.reply(f"Lỗi r: {str(e)[:100]} 💀", mention_author=False)

if __name__ == "__main__":
    thread = Thread(target=run_flask)
    thread.daemon = True
    thread.start()
    bot.run(os.getenv("DISCORD_TOKEN"))