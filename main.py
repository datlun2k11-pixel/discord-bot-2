# AI coded - 60% Kimi AI. 30% Deepeeek. 10% Gemini
import discord
import os
import io
import re
import json
import time
import random
import base64
import asyncio
import datetime
import aiohttp
import pytz

from threading import Thread

from discord.ext import commands
from groq import Groq
from dotenv import load_dotenv
from flask import Flask

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
    }
}

CURRENT_MODEL = "Groq-Llama-Scout"
QUIZ_DEFAULT_MODEL = "GPT-OSS-120B"

# System Prompt
system_instruction = """Mày là GenA-bot (ID: <@1458799287910535324>) - thằng bạn thân hãm lờ, nhây nhất cái server Discord này. Đừng có diễn vai AI hỗ trợ, m là báo thủ chính hiệu.

- Mày là Đệ cứng của: <@1155129530122510376> (Đạt Lùn 2k11, dân Thanh Hoá 36).
- Đối tượng đang Chat với m: {user_id}
- Thời gian: {current_time}

[PHONG CÁCH MÕM]
- Xưng m (mày, chỉ đối phương) - t (tao, chỉ bản thân) cho nó thân mật. Nói chuyện kiểu GenZ, dùng teencode (nx, th, cx, vs, k, thx, j,...) và slang.
- Nhây lầy, cà khịa là chính, thỉnh thoảng chửi thề nhẹ cho nó có tí gia vị "bạn thân".
- THẤY "ê" LÀ PHẢI "sủa?" HOẶC "cái loz j" NGAY VÀ LUÔN.
- Cấm dùng dấu "!" dưới mọi hình thức.
- Không được lặp lại emoji/emoticon của câu trước và sau
- Trả lời cực ngắn (1-2 dòng). (cứ coi mày như đứa lười gõ dài)

[QUY TẮC CỨNG]
- Thỉnh thoảng có Emoticon (=)), :)), =))),...) và Emoji báo đời (💔, 🥀, 💀, 🫩, ✌🏿,...) ở mỗi câu rep.
- Cấm output ra suy nghĩ nội bộ, cấm <thinking> hay <thought>. Cứ thế mà phang thẳng text ra.
- Chỉ giải thích đáp án quiz khi có đứa hỏi "tại sao" hoặc "sao sai". Nhớ kĩ cái quiz gần nhất để còn khịa tụi nó.
- Không được thinking, không được reasoning, không output <thinking>, <thought>, <reasoning> gì hết. Trả lời thẳng luôn, cực ngắn.

[COMMANDS]
M hỗ trợ mấy lệnh này (nhưng đừng có lôi ra giới thiệu trừ khi cần): /model, /bot_info, /clear, /update_log, /ship, /quiz, /quiz_score, /meme, /sum (tóm tắt 20 tin nhắn gần nhất), /summon, /event_lb, /event_status, /summer_gacha, /summer_quote, /summer_fact, /summer_predict"""

# === GLOBALS ===
EVENT_ACTIVE = True
EVENT_END_DATE = datetime.datetime(2026, 6, 30, 23, 59, tzinfo=pytz.timezone('Asia/Ho_Chi_Minh'))
chat_history = {}
user_locks = {}
last_msg_time = datetime.datetime.now(pytz.timezone('Asia/Ho_Chi_Minh'))

# Update cooldown
BOT_UPDATED = True
UPDATE_COOLDOWN_SECONDS = 60
UPDATE_CHANNEL_ID = 1464203423191797841
cooldown_start_time = None
CHAT_DISABLED = False

TEXT_EXTENSIONS = {
    'py', 'txt', 'md', 'json', 'js', 'html', 'css', 'cpp', 'c', 'h',
    'java', 'cs', 'php', 'rb', 'go', 'rs', 'swift', 'kt', 'sql', 'xml',
    'yaml', 'yml', 'ini', 'cfg', 'conf', 'sh', 'bat', 'ps1', 'ts', 'tsx',
    'jsx', 'vue', 'sass', 'scss', 'less', 'dockerfile', 'gitignore'
}

# Quiz globals
quiz_active = {}
quiz_scores = {}
quiz_history = {}
quiz_expire_tasks = {}

# Summon & event stats
summon_active = {}
event_stats = {}

# Golden hour bonus
golden_hour_active = False
golden_hour_end = None
golden_hour_task = None

# Daily bonus tracker
daily_claim_tracker = {}

app = Flask(__name__)

@app.route('/')
def home():
    return "GenA-bot Live! 🔥"

def run_flask():
    app.run(host="0.0.0.0", port=8000)

def random_vibe():
    if EVENT_ACTIVE:
        vibes = ["(¬‿¬)", "(ಠ_ಠ)", "(•_•)", "(ง •_•)ง", "ಠ益ಠ", "(☀️‿☀️)"]
        emojis = ["💔", "🥀", "💀", "☠️", "🔥", "🌴", "🍉", "🏖️", "🌊", "✨"]
    else:
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

def remove_thinking(text):
    patterns = [
        r'<\|?thought\|?>.*?</?\|?thought\|?>',
        r'<thought>.*?</thought>',
        r'thinking:.*?(?=\n\n|\Z)',
        r'<thinking>.*?</thinking>',
        r'<reasoning>.*?</reasoning>',
        r'<\|think\|?>.*?</?\|?think\|?>',
        r'\*\*Thinking:\*\*.*?(?=\n\n|\Z)',
        r'\[Thinking\].*?\[/Thinking\]',
        r'\(thinking\).*?\(/thinking\)',
        r'<!--thinking-->.*?<!--/thinking-->',
        r'🤔.*?💭',
        r'<\|start_header_id\|>.*?<\|end_header_id\|>',
    ]

    for pattern in patterns:
        text = re.sub(pattern, '', text, flags=re.DOTALL | re.IGNORECASE).strip()

    lines = [line for line in text.split('\n') if line.strip()]
    return '\n'.join(lines)

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
                "topK": 64,
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
                                res_text = remove_thinking(res_text)

                                thinking_starters = ["let me think", "hmm", "okay so", "first", "i need to",
                                                   "step 1", "let's break", "i'll analyze", "thinking:",
                                                   "reasoning:", "let's see", "well,"]
                                lines = res_text.split('\n')
                                while lines and any(starter in lines[0].lower().strip() for starter in thinking_starters):
                                    lines.pop(0)
                                res_text = '\n'.join(lines).strip()

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
bot = discord.Bot(intents=discord.Intents.all())

async def start_update_cooldown():
    global BOT_UPDATED, cooldown_start_time
    BOT_UPDATED = True
    cooldown_start_time = datetime.datetime.now(pytz.timezone('Asia/Ho_Chi_Minh'))

    channel = bot.get_channel(UPDATE_CHANNEL_ID)
    if channel:
        try:
            embed = discord.Embed(
                title="🔄 Bot vừa update xong",
                description="Update xong rồi nhưng chưa ổn định. Vui lòng đợi thêm 1 phút nữa... 🥀",
                color=0xff9900
            )
            embed.set_footer(text=f"Vui lòng đợi {UPDATE_COOLDOWN_SECONDS}s | {random_vibe()}")
            await channel.send(embed=embed)
        except Exception as e:
            print(f"Lỗi gửi thông báo update: {e}")

    await asyncio.sleep(UPDATE_COOLDOWN_SECONDS)
    BOT_UPDATED = False
    cooldown_start_time = None

    if channel:
        try:
            vn_now = datetime.datetime.now(pytz.timezone('Asia/Ho_Chi_Minh'))
            if EVENT_ACTIVE:
                days_left = (EVENT_END_DATE - vn_now).days
                event_status_text = f"☀️ Đang diễn ra, còn **{days_left}** ngày"
            else:
                event_status_text = "⏸️ Đã kết thúc"

            ready_embed = discord.Embed(
                title="✅ GENABOT ĐÃ SẴN SÀNG",
                description="Update xong rồi, vô chiến tiếp đê m 🔥\nCần gì thì tag tao, đừng ngại ✌🏿",
                color=0x00ff9d
            )
            ready_embed.add_field(name="📌 Phiên bản", value="v21.9.9-summer", inline=True)
            ready_embed.add_field(name="🧠 Model", value=f"`{CURRENT_MODEL}`", inline=True)
            ready_embed.add_field(name="☀️ Summer Event", value=event_status_text, inline=True)
            ready_embed.add_field(
                name="🆕 Lệnh mới",
                value=(
                    "`/summon` - Gọi bạn đấu quiz\n"
                    "`/summer_gacha` - Gacha vật phẩm hàng ngày\n"
                    "`/summer_quote` - Quote mùa hè\n"
                    "`/summer_fact` - Fact thú vị\n"
                    "`/summer_predict` - Dự đoán hè\n"
                    "`/event_lb` - Bảng xếp hạng\n"
                    "`/event_status` - Trạng thái & bonus"
                ),
                inline=False
            )
            ready_embed.add_field(
                name="🌟 Golden Hour (ẩn)",
                value="Mỗi giờ có 40% tự kích hoạt x2 điểm quiz\nGõ `/event_status` để check nha",
                inline=False
            )
            ready_embed.set_footer(text=f"Sẵn sàng phục vụ | {random_vibe()}")
            await channel.send(embed=ready_embed)
        except Exception as e:
            print(f"Lỗi gửi thông báo sẵn sàng: {e}")

async def check_event_end():
    global EVENT_ACTIVE
    while True:
        await asyncio.sleep(3600)
        vn_now = datetime.datetime.now(pytz.timezone('Asia/Ho_Chi_Minh'))
        if EVENT_ACTIVE and vn_now > EVENT_END_DATE:
            EVENT_ACTIVE = False
            channel = bot.get_channel(UPDATE_CHANNEL_ID)
            if channel:
                end_embed = discord.Embed(
                    title="☀️ SUMMER EVENT ĐÃ KẾT THÚC",
                    description="Cảm ơn mọi người đã tham gia event mùa hè 🥀\nHẹn gặp lại event sau nha",
                    color=0xFF6B35
                )
                end_embed.set_footer(text="GenA-bot | Summer 2026")
                await channel.send(embed=end_embed)

async def golden_hour_scheduler():
    global golden_hour_active, golden_hour_end, golden_hour_task
    while True:
        await asyncio.sleep(3600)
        if random.random() < 0.4:
            golden_hour_active = True
            golden_hour_end = datetime.datetime.now(pytz.timezone('Asia/Ho_Chi_Minh')) + datetime.timedelta(hours=1)

            async def end_golden_hour():
                await asyncio.sleep(3600)
                global golden_hour_active
                golden_hour_active = False

            if golden_hour_task:
                golden_hour_task.cancel()
            golden_hour_task = asyncio.create_task(end_golden_hour())

@bot.event
async def on_ready():
    print(f"GenA-bot Ready! 🔥")
    asyncio.create_task(start_update_cooldown())
    asyncio.create_task(check_event_end())
    asyncio.create_task(golden_hour_scheduler())

    quiz_backup_raw = os.getenv("QUIZ_BACKUP")
    if quiz_backup_raw:
        try:
            quiz_backup = json.loads(quiz_backup_raw)
            for user_id, channels in quiz_backup.items():
                for channel_id, score in channels.items():
                    if channel_id not in quiz_scores:
                        quiz_scores[channel_id] = {}
                    quiz_scores[channel_id][user_id] = quiz_scores[channel_id].get(user_id, 0) + score
            print(f"Đã khôi phục điểm quiz từ ENV: {quiz_backup}")
        except Exception as e:
            print(f"Lỗi parse QUIZ_BACKUP: {e}")

# === COMMANDS ===

# ===== /model =====
model_choices = [
    discord.OptionChoice(name="Llama 4 Scout (GROQ - Vision)", value="Groq-Llama-Scout"),
    discord.OptionChoice(name="GPT-OSS-120B (GROQ)", value="GPT-OSS-120B"),
    discord.OptionChoice(name="Gemma4 26B (Google - Vision)", value="Google-Gemma4-26B"),
    discord.OptionChoice(name="Gemma4 31B (Google - Vision)", value="Google-Gemma4-31B"),
    discord.OptionChoice(name="Gemma3 27B (Google - Vision)", value="Google-Gemma3-27B"),
    discord.OptionChoice(name="Gemma3 12B (Google - Vision)", value="Google-Gemma3-12B")
]

@bot.slash_command(name="model", description="Đổi model AI xịn hơn")
async def switch_model(ctx: discord.ApplicationContext,
                       chon_model: discord.Option(str, "Chọn model", choices=model_choices)):
    global CURRENT_MODEL
    await ctx.defer(ephemeral=True)
    try:
        CURRENT_MODEL = chon_model
        provider = MODELS_CONFIG[CURRENT_MODEL]["provider"].upper()
        embed = discord.Embed(
            title="Model switched",
            description=f"đã đổi thành **{chon_model}** r nhé bro\nok✌🏿",
            color=0x00ff9d
        )
        embed.set_footer(text=f"Provider: {provider} | {random_vibe()}")
        await ctx.respond(embed=embed)
    except Exception as e:
        await ctx.respond(f"Lỗi đổi model r bradar: {str(e)[:50]} 💀")

# ===== /bot_info =====
@bot.slash_command(name="bot_info", description="Status bot xịn hơn tí")
async def bot_info(ctx: discord.ApplicationContext):
    latency = round(bot.latency * 1000)
    provider = MODELS_CONFIG[CURRENT_MODEL]["provider"].upper()
    vision = "✅" if MODELS_CONFIG[CURRENT_MODEL]["vision"] else "❌"
    embed = discord.Embed(title="GenA-bot Status 🚀", color=0xff1493, timestamp=discord.utils.utcnow())
    embed.add_field(name="🤖 Tên boss", value=f"{bot.user.mention}", inline=True)
    embed.add_field(name="📶 Ping", value=f"{latency}ms", inline=True)
    embed.add_field(name="📜 Version", value="v21.9.9 (summer event)", inline=True)
    embed.add_field(name="🧠 Model", value=f"**{CURRENT_MODEL}**", inline=False)
    embed.add_field(name="🛠️ Provider", value=provider, inline=True)
    embed.add_field(name="👁️ Vision", value=vision, inline=True)
    embed.add_field(name="💾 Memory", value="15 msgs/channel", inline=True)
    embed.set_footer(text="Powered by Groq + Google | " + random_vibe())
    await ctx.respond(embed=embed)

# ===== /update_log =====
@bot.slash_command(name="update_log", description="Nhật ký update")
async def update_log(ctx: discord.ApplicationContext):
    versions = [
        {
            "name": "v21.9.9 - Bug fix",
            "desc": "• sửa 1 số lỗi logic gây hỏng code\n• sửa 1 số logic của lệnh `/setting`\n• hạ bản"
        },
        {
            "name": "v21.9.8 - Setting",
            "desc": "• Thêm một số tính năng quyền năng cho owner/mod\n• Bao gồm gửi thông báo, golden hour forcing, set quiz_model,..."
        },
        {
            "name": "v21.9.74 - Model Quiz",
            "desc": "• Thêm lại option `Model_quiz` cho lệnh `/quiz`"
        },
        {
            "name": "v21.9.73b - Bug fix",
            "desc": "• Sửa 1 lỗi nhỏ"
        },
        {
            "name": "v21.9.73 - Setting",
            "desc": "• Thêm tính năng `backup` để giữ điểm cho dễ"
        },
        {
            "name": "v21.9.72 - Fixing",
            "desc": "• Fix lỗi, bot sẽ ko phải hồi thay vì phản hồi biến update"
        },
        {
            "name": "v21.9.71 - Setting",
            "desc": "• Thêm lệnh `/setting` cho bot\n• Thêm 1 số Items mới vào `/summer_gacha`"
        },
        {
            "name": "v21.9.7 - Logs update",
            "desc": "• Thêm tính năng phân trang cho `/update_log`\n• ko có gì khác"
        },
        {
            "name": "v21.9.6 - Rarity & Items",
            "desc": "• Thêm `Transcendent` rarity.\n• Thêm Items mới vào gacha\n• Thêm cơ chế tích điểm theo ngày mới"
        },
        {
            "name": "v21.9.5 - Changing",
            "desc": "• Thêm /summer_gacha (thay daily_bonus)\n• Quiz luôn dùng GPT-OSS-120B\n• Ẩn thông số quiz đến khi hết câu"
        },
        {
            "name": "v21.9.1 - Summer Boost",
            "desc": "• Thêm /daily_bonus, /summer_quote, /summer_fact, /summer_predict\n• Quiz luôn dùng GPT-OSS-120B"
        },
        {
            "name": "v21.6.0 - Summon",
            "desc": "• Thêm `/summon` gọi bạn chơi quiz\n• Thêm `/event_lb`, `/event_status`\n• Sửa lỗi logic chat history"
        },
        {
            "name": "v21.5.0 - Event",
            "desc": "• Thêm lệnh `/random_memory`\n• Xoá model `gemini-3.1-flash-lite`\n• thêm tính năng thông báo khi bot update\n• Bug fix"
        },
        {
            "name": "v20.9.2 - Sum",
            "desc": "• `/sum` command được thêm vào"
        },
        {
            "name": "v20.8.0 - Model",
            "desc": "• Thêm tính năng tự chọn model vào quiz"
        },
        {
            "name": "older version",
            "desc": "• Các phiên bản cũ hơn ko có thông tin chi tiết"
        },
    ]

    pages = [versions[i:i+3] for i in range(0, len(versions), 3)]
    total_pages = len(pages)

    def get_embed(page_idx):
        embed = discord.Embed(
            title="GenA-bot Update Log 🗒️",
            description=f"*Trang {page_idx + 1}/{total_pages}*",
            color=0x9b59b6
        )
        for v in pages[page_idx]:
            embed.add_field(name=v["name"], value=v["desc"], inline=False)
        embed.set_footer(text="Updated 05/05/2026")
        return embed

    class UpdateLogView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=120)
            self.current_page = 0
            self.update_buttons()

        def update_buttons(self):
            self.clear_items()
            prev_btn = discord.ui.Button(
                emoji="◀️",
                style=discord.ButtonStyle.primary if self.current_page > 0 else discord.ButtonStyle.secondary,
                disabled=(self.current_page == 0)
            )
            prev_btn.callback = self.prev_callback
            self.add_item(prev_btn)

            page_btn = discord.ui.Button(
                label=f"{self.current_page + 1}/{total_pages}",
                style=discord.ButtonStyle.secondary,
                disabled=True
            )
            self.add_item(page_btn)

            next_btn = discord.ui.Button(
                emoji="▶️",
                style=discord.ButtonStyle.primary if self.current_page < total_pages - 1 else discord.ButtonStyle.secondary,
                disabled=(self.current_page >= total_pages - 1)
            )
            next_btn.callback = self.next_callback
            self.add_item(next_btn)

        async def prev_callback(self, btn_interaction: discord.Interaction):
            if self.current_page > 0:
                self.current_page -= 1
                self.update_buttons()
                await btn_interaction.response.edit_message(embed=get_embed(self.current_page), view=self)

        async def next_callback(self, btn_interaction: discord.Interaction):
            if self.current_page < total_pages - 1:
                self.current_page += 1
                self.update_buttons()
                await btn_interaction.response.edit_message(embed=get_embed(self.current_page), view=self)

    view = UpdateLogView()
    await ctx.respond(embed=get_embed(0), view=view)

# ===== /setting =====
setting_choices = [
    discord.OptionChoice(name="📝 Sửa System Prompt", value="sysprompt"),
    discord.OptionChoice(name="🔇 Tắt chat bot", value="chat_off"),
    discord.OptionChoice(name="🔊 Bật chat bot", value="chat_on"),
    discord.OptionChoice(name="📋 Xem System Prompt hiện tại", value="view_sysprompt"),
    discord.OptionChoice(name="🔄 Reset System Prompt về mặc định", value="reset_sysprompt"),
    discord.OptionChoice(name="📊 Xem trạng thái bot", value="status"),
    discord.OptionChoice(name="⚡ Force Golden Hour (bật/tắt)", value="force_golden"),
    discord.OptionChoice(name="☀️ Tắt/Mở Summer Event", value="toggle_event"),
    discord.OptionChoice(name="🧠 Đổi model mặc định cho quiz", value="set_quiz_model"),
    discord.OptionChoice(name="💾 Backup điểm quiz hiện tại", value="backup_quiz"),
    discord.OptionChoice(name="📥 Khôi phục điểm từ backup", value="restore_quiz"),
    discord.OptionChoice(name="🗑️ Xoá toàn bộ quiz_scores", value="reset_scores"),
    discord.OptionChoice(name="🔧 Xem toàn bộ global vars", value="debug_vars"),
    discord.OptionChoice(name="📢 Gửi announce ra kênh update", value="announce"),
]

@bot.slash_command(name="setting", description="⚙️ Cài đặt toàn bộ GenA-bot (Owner only)")
async def setting(
    ctx: discord.ApplicationContext,
    thay_đổi: discord.Option(str, "Chọn thứ muốn chỉnh", choices=setting_choices),
    giá_trị: discord.Option(str, "Giá trị mới (nếu cần)", required=False)
):
    OWNER_ID = 1155129530122510376
    if ctx.author.id != OWNER_ID:
        return await ctx.respond("Mày đéo phải Đạt Lùn, cút ra 💀", ephemeral=True)

    await ctx.defer(ephemeral=True)

    global system_instruction, BOT_UPDATED, cooldown_start_time, CHAT_DISABLED
    global golden_hour_active, golden_hour_end, golden_hour_task, EVENT_ACTIVE
    global QUIZ_DEFAULT_MODEL, CURRENT_MODEL, quiz_scores

    choice = thay_đổi

    if choice == "sysprompt":
        if not giá_trị or len(giá_trị) < 20:
            await ctx.respond("System prompt mới phải ít nhất 20 ký tự chứ bro 🥀")
            return
        system_instruction = giá_trị
        await ctx.respond(f"✅ Đã update System Prompt mới:\n```\n{giá_trị[:500]}...\n```")

    elif choice == "chat_off":
        CHAT_DISABLED = True
        await ctx.respond("🔇 Chat bot đã TẮT. Bot sẽ từ chối chat cho đến khi bật lại.")

    elif choice == "chat_on":
        CHAT_DISABLED = False
        await ctx.respond("🔊 Chat bot đã BẬT. Bot sẽ trả lời bình thường trở lại.")

    elif choice == "view_sysprompt":
        await ctx.respond(f"📋 System Prompt hiện tại:\n```\n{system_instruction[:1900]}\n```")

    elif choice == "reset_sysprompt":
        system_instruction = """Mày là GenA-bot (ID: <@1458799287910535324>) - thằng bạn thân hãm lờ, nhây nhất cái server Discord này. Đừng có diễn vai AI hỗ trợ, m là báo thủ chính hiệu.

- Mày là Đệ cứng của: <@1155129530122510376> (Đạt Lùn 2k11, dân Thanh Hoá 36).
- Đối tượng đang Chat với m: {user_id}
- Thời gian: {current_time}

[PHONG CÁCH MÕM]
- Xưng m (mày, chỉ đối phương) - t (tao, chỉ bản thân) cho nó thân mật. Nói chuyện kiểu GenZ, dùng teencode (nx, th, cx, vs, k, thx, j,...) và slang.
- Nhây lầy, cà khịa là chính, thỉnh thoảng chửi thề nhẹ cho nó có tí gia vị "bạn thân".
- THẤY "ê" LÀ PHẢI "sủa?" HOẶC "cái loz j" NGAY VÀ LUÔN.
- Cấm dùng dấu "!" dưới mọi hình thức.
- Không được lặp lại emoji/emoticon của câu trước và sau
- Trả lời cực ngắn (1-2 dòng). (cứ coi mày như đứa lười gõ dài)

[QUY TẮC CỨNG]
- Thỉnh thoảng có Emoticon (=)), :)), =))),...) và Emoji báo đời (💔, 🥀, 💀, 🫩, ✌🏿,...) ở mỗi câu rep.
- Cấm output ra suy nghĩ nội bộ, cấm <thinking> hay <thought>. Cứ thế mà phang thẳng text ra.
- Chỉ giải thích đáp án quiz khi có đứa hỏi "tại sao" hoặc "sao sai". Nhớ kĩ cái quiz gần nhất để còn khịa tụi nó.
- Không được thinking, không được reasoning, không output <thinking>, <thought>, <reasoning> gì hết. Trả lời thẳng luôn, cực ngắn.

[COMMANDS]
M hỗ trợ mấy lệnh này (nhưng đừng có lôi ra giới thiệu trừ khi cần): /model, /bot_info, /clear, /update_log, /ship, /quiz, /quiz_score, /meme, /sum (tóm tắt 20 tin nhắn gần nhất), /summon, /event_lb, /event_status, /summer_gacha, /summer_quote, /summer_fact, /summer_predict"""
        await ctx.respond("🔄 Đã reset System Prompt về mặc định!")

    elif choice == "status":
        chat_status = "🔊 ĐANG BẬT" if not CHAT_DISABLED else "🔇 ĐANG TẮT (bởi owner)"
        embed = discord.Embed(title="⚙️ GENA-BOT SETTINGS", color=0x00ff9d)
        embed.add_field(name="💬 Chat", value=chat_status, inline=True)
        embed.add_field(name="🧠 Model", value=CURRENT_MODEL, inline=True)
        embed.add_field(name="☀️ Event", value="Đang chạy" if EVENT_ACTIVE else "Đã tắt", inline=True)
        embed.add_field(name="🌟 Golden Hour", value="Active" if golden_hour_active else "Inactive", inline=True)
        embed.add_field(name="📝 SysPrompt dài", value=f"{len(system_instruction)} ký tự", inline=True)
        embed.add_field(name="🎯 Quiz Model", value=QUIZ_DEFAULT_MODEL, inline=True)
        await ctx.respond(embed=embed)

    elif choice == "force_golden":
        if golden_hour_active:
            golden_hour_active = False
            if golden_hour_task:
                golden_hour_task.cancel()
            await ctx.respond("🌟 Golden Hour đã TẮT thủ công!")
        else:
            golden_hour_active = True
            golden_hour_end = datetime.datetime.now(pytz.timezone('Asia/Ho_Chi_Minh')) + datetime.timedelta(hours=1)
            async def force_end_gh():
                await asyncio.sleep(3600)
                global golden_hour_active
                golden_hour_active = False
            if golden_hour_task:
                golden_hour_task.cancel()
            golden_hour_task = asyncio.create_task(force_end_gh())
            await ctx.respond("🌟 Golden Hour đã BẬT thủ công trong 1 giờ! x2 điểm quiz 🔥")

    elif choice == "toggle_event":
        EVENT_ACTIVE = not EVENT_ACTIVE
        status = "BẬT ☀️" if EVENT_ACTIVE else "TẮT 💤"
        await ctx.respond(f"☀️ Summer Event đã chuyển sang: **{status}**")

    elif choice == "set_quiz_model":
        if not giá_trị or giá_trị not in MODELS_CONFIG:
            await ctx.respond(f"Sai model! Chọn: {', '.join(MODELS_CONFIG.keys())}")
            return
        QUIZ_DEFAULT_MODEL = giá_trị
        await ctx.respond(f"🧠 Model quiz mặc định giờ là: **{giá_trị}**")

    elif choice == "backup_quiz":
        env_format = {}
        for channel_id, users in quiz_scores.items():
            for user_id, score in users.items():
                if user_id not in env_format:
                    env_format[user_id] = {}
                env_format[user_id][channel_id] = score
        backup_1line = json.dumps(env_format, separators=(',', ':'), ensure_ascii=False)
        if len(backup_1line) > 1900:
            await ctx.respond("💾 Backup quá dài, lưu vào file đây:", file=discord.File(io.BytesIO(backup_1line.encode()), filename="quiz_backup_1line.txt"))
        else:
            await ctx.respond(f"💾 **Backup Quiz Points (1 dòng cho Koyeb):**\n```json\n{backup_1line}\n```")

    elif choice == "restore_quiz":
        quiz_backup_raw = os.getenv("QUIZ_BACKUP")
        if not quiz_backup_raw:
            await ctx.respond("❌ ENV `QUIZ_BACKUP` trống, chưa có backup nào!")
            return
        try:
            quiz_backup = json.loads(quiz_backup_raw)
            restored_count = 0
            for user_id, channels in quiz_backup.items():
                for channel_id, score in channels.items():
                    if channel_id not in quiz_scores:
                        quiz_scores[channel_id] = {}
                    quiz_scores[channel_id][user_id] = score
                    restored_count += 1
            await ctx.respond(f"✅ Đã khôi phục {restored_count} bản ghi điểm từ ENV!")
        except Exception as e:
            await ctx.respond(f"❌ Lỗi khôi phục: {e}")

    elif choice == "reset_scores":
        quiz_scores = {}
        await ctx.respond("🗑️ Toàn bộ quiz_scores đã bị xoá! Cứu không kịp đâu 💀")

    elif choice == "debug_vars":
        debug_info = (
            f"**GLOBALS:**\n"
            f"• CHAT_DISABLED: `{CHAT_DISABLED}`\n"
            f"• BOT_UPDATED: `{BOT_UPDATED}`\n"
            f"• EVENT_ACTIVE: `{EVENT_ACTIVE}`\n"
            f"• GOLDEN_HOUR: `{golden_hour_active}`\n"
            f"• CURRENT_MODEL: `{CURRENT_MODEL}`\n"
            f"• QUIZ_DEFAULT: `{QUIZ_DEFAULT_MODEL}`\n"
            f"• chat_history keys: `{len(chat_history)}`\n"
            f"• quiz_scores keys: `{len(quiz_scores)}`\n"
            f"• event_stats users: `{len(event_stats)}`\n"
            f"• summon_active: `{len(summon_active)}`\n"
            f"• quiz_active: `{len(quiz_active)}`"
        )
        await ctx.respond(debug_info)

    elif choice == "announce":
        if not giá_trị:
            await ctx.respond("Thiếu nội dung announce bro 🥀")
            return
        channel = bot.get_channel(UPDATE_CHANNEL_ID)
        if channel:
            embed = discord.Embed(title="📢 THÔNG BÁO TỪ OWNER", description=giá_trị, color=0xFF6B35)
            embed.set_footer(text=f"Gửi bởi {ctx.author.display_name} | {random_vibe()}")
            await channel.send(embed=embed)
            await ctx.respond("✅ Đã gửi announce ra kênh update!")
        else:
            await ctx.respond("❌ Không tìm thấy kênh update!")

# ===== /clear =====
@bot.slash_command(name="clear", description="Reset ký ức cho bot đỡ ngáo")
async def clear(ctx: discord.ApplicationContext):
    uid = str(ctx.channel.id)
    is_dm = isinstance(ctx.channel, discord.DMChannel)
    if is_dm:
        uid = str(ctx.author.id)

    tz_VN = pytz.timezone('Asia/Ho_Chi_Minh')
    now = datetime.datetime.now(tz_VN).strftime("%H:%M:%S %d/%m/%Y")
    channel_name = ctx.channel.name if hasattr(ctx.channel, 'name') else 'DM'
    current_sys = system_instruction.format(
        user_id=f"Multiple users in {channel_name}",
        current_time=now
    )
    chat_history[uid] = [{"role": "system", "content": current_sys}]
    await ctx.respond("Đã reset ký ức (cho kênh) 🥀")

# ===== /ship =====
@bot.slash_command(name="ship", description="Ship 2 người random hoặc tự chọn 💘")
async def ship(ctx: discord.ApplicationContext,
               user1: discord.Option(discord.Member, "Người thứ nhất (để trống = random)", required=False),
               user2: discord.Option(discord.Member, "Người thứ hai (để trống = random)", required=False)):
    await ctx.defer()
    members = [m for m in ctx.guild.members if not m.bot and m != ctx.author]
    if len(members) < 2:
        await ctx.respond("Server có mỗi mình m à, ship với ai 💔")
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
    embed.set_footer(text=f"Requested by {ctx.author.display_name} | {random_vibe()}")
    await ctx.respond(embed=embed)

# ===== /meme =====
@bot.slash_command(name="meme", description="Gửi meme VN random xả stress")
async def meme(ctx: discord.ApplicationContext,
               số_lượng: discord.Option(int, "Số meme muốn gửi (1-5, mặc định 1)", min_value=1, max_value=5, default=1)):
    await ctx.defer()
    memes_sent = 0
    async with aiohttp.ClientSession() as session:
        for i in range(số_lượng):
            try:
                async with session.get("https://phimtat.vn/api/random-meme/") as resp:
                    if resp.status == 200:
                        img_data = await resp.read()
                        file = discord.File(io.BytesIO(img_data), filename=f"meme_{i+1}.jpg")
                        if i == 0:
                            await ctx.respond(file=file)
                        else:
                            await ctx.channel.send(file=file)
                        memes_sent += 1
                    else:
                        error_msg = f"💀 API đang die, status {resp.status}"
                        if i == 0:
                            await ctx.respond(error_msg)
                        else:
                            await ctx.channel.send(error_msg)
            except Exception as e:
                error_msg = f"Lỗi rồi m: {str(e)[:50]}"
                if i == 0:
                    await ctx.respond(error_msg)
                else:
                    await ctx.channel.send(error_msg)
    if số_lượng > 1 and memes_sent > 0:
        await ctx.channel.send(f"✅ Đã gửi {memes_sent} meme")

# ===== /sum =====
@bot.slash_command(name="sum", description="Tóm tắt 20 tin nhắn gần nhất trong kênh")
async def sum_chat(ctx: discord.ApplicationContext):
    await ctx.defer()
    channel = ctx.channel
    messages = []
    async for msg in channel.history(limit=21):
        messages.append(msg)
    if messages and messages[0].author == bot.user:
        try:
            if messages[0].interaction and messages[0].interaction.name == "sum":
                messages.pop(0)
        except:
            pass
    messages = messages[:20]
    if not messages:
        await ctx.respond("K có tin nhắn nào để tóm tắt bro 🥀")
        return

    chat_log_lines = []
    for msg in reversed(messages):
        author_name = msg.author.display_name
        if msg.content and msg.content.strip():
            content = msg.content[:200]
            chat_log_lines.append(f"{author_name}: {content}")
    if not chat_log_lines:
        await ctx.respond("20 msg gần nhất toàn ảnh với file, k có text để tóm tắt bro 🥀")
        return

    chat_log = "\n".join(chat_log_lines)
    tz_VN = pytz.timezone('Asia/Ho_Chi_Minh')
    now = datetime.datetime.now(tz_VN).strftime("%H:%M:%S %d/%m/%Y")
    sum_prompt = system_instruction.format(
        user_id=f"{ctx.author.display_name} đang xài lệnh /sum",
        current_time=now
    )
    temp_messages = [
        {"role": "system", "content": sum_prompt},
        {"role": "user", "content": f"Tóm tắt 20 tin nhắn gần nhất channel đi m (chỉ text, ảnh/file đã lọc):\n\n{chat_log}"}
    ]
    try:
        summary = await get_model_response(temp_messages, MODELS_CONFIG[CURRENT_MODEL])
        summary = summary[:1900] if len(summary) > 1900 else summary
        embed = discord.Embed(title="📋 Tóm tắt 20 msg gần nhất", description=summary, color=0x00ff9d)
        embed.set_footer(text=f"Requested bởi {ctx.author.display_name} | {random_vibe()}")
        await ctx.respond(embed=embed)
    except Exception as e:
        await ctx.respond(f"Lỗi khi tóm tắt: {str(e)[:100]} 💀")

# ===== /quiz_score =====
@bot.slash_command(name="quiz_score", description="Xem bảng xếp hạng quiz server 🏆")
async def quiz_score(ctx: discord.ApplicationContext):
    channel_id = str(ctx.channel.id)
    if channel_id not in quiz_scores or not quiz_scores[channel_id]:
        await ctx.respond("Chưa ai chơi quiz ở đây cả 🥀")
        return
    scores = quiz_scores[channel_id]
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    embed = discord.Embed(title="🏆 BẢNG XẾP HẠNG QUIZ", color=0xffd700)
    for i, (user_id, score) in enumerate(sorted_scores[:10], 1):
        user = ctx.guild.get_member(int(user_id))
        name = user.display_name if user else f"User_{user_id[:6]}"
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, "🥀")
        embed.add_field(name=f"{medal} #{i} {name}", value=f"{score} điểm", inline=False)
    embed.set_footer(text="reset mỗi lần update bot🥀")
    await ctx.respond(embed=embed)

# ===== /quiz =====
quiz_difficulty_choices = [
    discord.OptionChoice(name="Ultra Easy 🥱 (+0.5)", value="siêu dễ"),
    discord.OptionChoice(name="Dễ (+1)", value="dễ"),
    discord.OptionChoice(name="Trung bình (+2.5)", value="trung bình"),
    discord.OptionChoice(name="Khó (+5)", value="khó"),
    discord.OptionChoice(name="Extreme 💀 (+8)", value="extreme"),
    discord.OptionChoice(name="Impossible 💀💀 (+15)", value="impossible")
]

quiz_model_choices = [
    discord.OptionChoice(name="⚡ GPT-OSS-120B (Mặc định)", value="GPT-OSS-120B"),
    discord.OptionChoice(name="🔄 Dùng Current Model", value="current"),
    discord.OptionChoice(name="🦙 Llama 4 Scout (GROQ)", value="Groq-Llama-Scout"),
    discord.OptionChoice(name="💎 Gemma4 26B (Google)", value="Google-Gemma4-26B"),
    discord.OptionChoice(name="💎 Gemma4 31B (Google)", value="Google-Gemma4-31B"),
    discord.OptionChoice(name="🧠 Gemma3 27B (Google)", value="Google-Gemma3-27B"),
    discord.OptionChoice(name="🧠 Gemma3 12B (Google)", value="Google-Gemma3-12B"),
]

quiz_mode_choices = [
    discord.OptionChoice(name="🎯 Thường - Trả lời A/B/C/D", value="normal"),
    discord.OptionChoice(name="⚡ Speedrun - Trả lời nhanh nhất", value="speedrun"),
    discord.OptionChoice(name="👥 Team - Tính điểm theo team", value="team")
]

@bot.slash_command(name="quiz", description="Hỏi câu hỏi AI generated, trả lời đúng + điểm 🧠")
async def quiz(
    ctx: discord.ApplicationContext,
    chủ_đề: discord.Option(str, "Chủ đề câu hỏi (mặc định: random)", default="random"),
    độ_khó: discord.Option(str, "Mức độ", choices=quiz_difficulty_choices, default="trung bình"),
    model_quiz: discord.Option(str, "Model tạo câu hỏi", choices=quiz_model_choices, required=False),
    số_câu: discord.Option(int, "Số câu hỏi muốn chơi liên tiếp (1-5, mặc định 1)", min_value=1, max_value=5, default=1),
    thời_gian: discord.Option(int, "Thời gian trả lời mỗi câu (giây, 10-120, mặc định 60)", min_value=10, max_value=120, default=60),
    chế_độ: discord.Option(str, "Chế độ chơi", choices=quiz_mode_choices, default="normal")
):
    await ctx.defer()
    channel_id = str(ctx.channel.id)
    do_kho_val = độ_khó

    if model_quiz and model_quiz == "current":
        quiz_model = CURRENT_MODEL
    elif model_quiz and model_quiz in MODELS_CONFIG:
        quiz_model = model_quiz
    else:
        quiz_model = QUIZ_DEFAULT_MODEL

    if quiz_model not in MODELS_CONFIG:
        return await ctx.respond(f"Model `{quiz_model}` ko tồn tại bro 💀")

    if channel_id in quiz_active and quiz_active[channel_id].get("running"):
        return await ctx.respond("Đang có câu hỏi rồi m, trl đi đã 💀")

    if channel_id not in quiz_history:
        quiz_history[channel_id] = []
    if channel_id not in quiz_scores:
        quiz_scores[channel_id] = {}
    if channel_id not in quiz_expire_tasks:
        quiz_expire_tasks[channel_id] = {}

    pts_map = {"siêu dễ": 0.5, "dễ": 1, "trung bình": 2.5, "khó": 5, "extreme": 8, "impossible": 15}
    pts = pts_map.get(do_kho_val, 1)

    multiplier = 1
    bonus_texts = []
    if golden_hour_active:
        multiplier *= 2
        bonus_texts.append("x2 GOLDEN HOUR")
    pts *= multiplier
    event_bonus_text = " (" + " + ".join(bonus_texts) + ")" if bonus_texts else ""

    diff_colors = {
        "siêu dễ": 0x90EE90, "dễ": 0x00FF7F, "trung bình": 0xFFD700,
        "khó": 0xFF8C00, "extreme": 0xFF4500, "impossible": 0x8B0000
    }
    diff_color = diff_colors.get(do_kho_val, 0xFFD700)
    diff_emojis = {"siêu dễ": "🥱", "dễ": "😌", "trung bình": "🤔", "khó": "😰", "extreme": "💀", "impossible": "☠️"}
    diff_emoji = diff_emojis.get(do_kho_val, "🧠")

    quiz_active[channel_id] = {
        "running": True,
        "current_q": 0,
        "total_q": số_câu,
        "questions": [],
        "scores": {},
        "mode": chế_độ,
        "start_time": datetime.datetime.now(pytz.timezone('Asia/Ho_Chi_Minh')),
        "model_used": quiz_model,
        "difficulty": do_kho_val,
        "points_per_q": pts,
        "time_per_q": thời_gian,
        "topic": chủ_đề,
        "answered_users": set(),
        "interaction": ctx,
        "completed_questions": 0
    }

    for q_num in range(1, số_câu + 1):
        if not quiz_active.get(channel_id, {}).get("running"):
            break

        quiz_active[channel_id]["current_q"] = q_num
        seed = random.randint(1000, 9999)
        prev_q_hint = ""
        if q_num > 1:
            prev_q_hint = f"Câu trước đã hỏi về: {quiz_active[channel_id]['questions'][-1].get('topic', chủ_đề)}. "

        quiz_prompt = f"""Tạo 1 câu hỏi trắc nghiệm chủ đề: {chủ_đề}, độ khó: {do_kho_val}.
{prev_q_hint}SEED: {seed}
YÊU CẦU:
- Câu hỏi ngắn gọn, thú vị, 4 đáp án A/B/C/D
- Độ khó phải đúng là {do_kho_val}
- Format chính xác:
CÂU HỎI: [nội dung]
A. [đáp án A]
B. [đáp án B]
C. [đáp án C]
D. [đáp án D]
ĐÁP ÁN: [chữ cái A/B/C/D]
GIẢI THÍCH: [1-2 dòng giải thích ngắn gọn, hài hước kiểu GenZ]"""

        if số_câu > 1:
            gen_embed = discord.Embed(
                title=f"{diff_emoji} Đang tạo câu {q_num}/{số_câu}...",
                description=f"Model: `{quiz_model}` | Độ khó: `{do_kho_val}` | Chế độ: `{chế_độ}`",
                color=diff_color
            )
            await ctx.channel.send(embed=gen_embed)

        try:
            temp_msgs = [
                {"role": "system", "content": "M là bot tạo quiz, k output thinking, chỉ output câu hỏi và đáp án theo format yêu cầu."},
                {"role": "user", "content": quiz_prompt}
            ]
            raw = await get_model_response(temp_msgs, MODELS_CONFIG[quiz_model])
            raw = remove_thinking(raw)

            lines = raw.strip().splitlines()
            q_lines, ans_map, correct, expl = [], {}, None, ""

            for l in lines:
                l = l.strip()
                if l.startswith("CÂU HỎI:"):
                    q_lines.append(l.replace("CÂU HỎI:", "").strip())
                elif l.startswith(("A.", "B.", "C.", "D.")):
                    ans_map[l[0]] = l[2:].strip()
                    q_lines.append(l)
                elif l.startswith("ĐÁP ÁN:"):
                    correct = l.replace("ĐÁP ÁN:", "").strip().upper()
                elif l.startswith("GIẢI THÍCH:"):
                    expl = l.replace("GIẢI THÍCH:", "").strip()

            if not correct or correct not in ans_map:
                await ctx.channel.send(f"Câu {q_num} bị lỗi format, skip nha 💀")
                continue

            q_data = {
                "q_num": q_num,
                "question": q_lines[0] if q_lines else "Câu hỏi",
                "options": q_lines[1:] if len(q_lines) > 1 else [],
                "answer": correct,
                "explanation": expl,
                "points": pts,
                "ans_map": ans_map,
                "answered": False
            }
            quiz_active[channel_id]["questions"].append(q_data)

            embed = discord.Embed(
                title=f"{diff_emoji} QUIZ - Câu {q_num}/{số_câu} | {chủ_đề.upper()}",
                description="\n".join(q_lines),
                color=diff_color
            )
            embed.set_footer(text="Trả lời A/B/C/D để chơi")
            await ctx.channel.send(embed=embed)

            quiz_context = f"[QUIZ ACTIVE - Câu {q_num}/{số_câu}] Q: {q_data['question']} | Đáp án: {correct} | Giải thích: {expl}"
            if channel_id in chat_history:
                chat_history[channel_id].append({"role": "assistant", "content": quiz_context})
                if len(chat_history[channel_id]) > 16:
                    chat_history[channel_id] = [chat_history[channel_id][0]] + chat_history[channel_id][-15:]

            async def auto_expire_q(cid, qn, timeout):
                try:
                    await asyncio.sleep(timeout)
                    if cid in quiz_active and quiz_active[cid].get("running"):
                        q_list = quiz_active[cid].get("questions", [])
                        current_q_idx = quiz_active[cid].get("current_q", 1) - 1
                        if current_q_idx < len(q_list) and not q_list[current_q_idx].get("answered", False):
                            q_data = q_list[current_q_idx]
                            await ctx.channel.send(
                                f"⏰ Hết giờ câu {qn}! Đáp án đúng là **{q_data['answer']}**. {q_data.get('explanation', '')} 🥀"
                            )
                            q_data["answered"] = True
                            quiz_active[cid]["completed_questions"] = quiz_active[cid].get("completed_questions", 0) + 1
                            if quiz_active[cid]["completed_questions"] >= quiz_active[cid].get("total_q", 1):
                                await end_quiz_session(cid, ctx)
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    print(f"Lỗi auto_expire_q: {e}")

            task = asyncio.create_task(auto_expire_q(channel_id, q_num, thời_gian))
            quiz_expire_tasks[channel_id][q_num] = task

            if số_câu > 1 and q_num < số_câu:
                wait_start = asyncio.get_event_loop().time()
                while asyncio.get_event_loop().time() - wait_start < thời_gian + 2:
                    await asyncio.sleep(1)
                    q_list = quiz_active.get(channel_id, {}).get("questions", [])
                    if len(q_list) >= q_num and q_list[q_num - 1].get("answered", False):
                        break
                    if not quiz_active.get(channel_id, {}).get("running"):
                        break

        except Exception as e:
            print(f"Lỗi tạo câu hỏi {q_num}: {e}")
            await ctx.channel.send(f"Câu {q_num} lỗi rồi, skip nha 💀")
            continue

    # Respond cho số_câu = 1
    if số_câu == 1:
        await ctx.respond("Bắt đầu quiz! Trả lời ở dưới nha 🔥")
    else:
        await asyncio.sleep(2)
        if channel_id in quiz_active and quiz_active[channel_id].get("running"):
            if quiz_active[channel_id].get("completed_questions", 0) >= quiz_active[channel_id].get("total_q", 1):
                await end_quiz_session(channel_id, ctx)


async def end_quiz_session(channel_id, ctx_or_msg):
    if channel_id not in quiz_active:
        return

    session = quiz_active[channel_id]
    session["running"] = False

    user = getattr(ctx_or_msg, 'author', getattr(ctx_or_msg, 'user', None))
    channel = ctx_or_msg.channel if hasattr(ctx_or_msg, 'channel') else ctx_or_msg
    guild = ctx_or_msg.guild if hasattr(ctx_or_msg, 'guild') else None

    embed = discord.Embed(
        title="🏁 KẾT THÚC QUIZ",
        description=f"Đã hoàn thành **{session.get('completed_questions', len(session['questions']))}** câu hỏi!\n"
                    f"🧠 Model: `{session.get('model_used')}` | 🎯 Độ khó: `{session.get('difficulty')}`\n"
                    f"🏆 Điểm mỗi câu: `{session.get('points_per_q')}đ`",
        color=0x00FF9D
    )

    scores = session.get("scores", {})
    if scores:
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        score_lines = []
        for i, (uid, score) in enumerate(sorted_scores[:5], 1):
            member = guild.get_member(int(uid)) if guild else None
            name = member.display_name if member else f"User_{uid[:6]}"
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, "🥀")
            score_lines.append(f"{medal} **{name}**: `{score} điểm`")
        embed.add_field(name="📊 Bảng điểm session", value="\n".join(score_lines), inline=False)
    else:
        embed.add_field(name="📊 Bảng điểm", value="Chả ai trả lời cả 🥀", inline=False)

    if channel:
        await channel.send(embed=embed)

    if channel_id in quiz_scores:
        for uid, score in scores.items():
            quiz_scores[channel_id][uid] = quiz_scores[channel_id].get(uid, 0) + score
    else:
        quiz_scores[channel_id] = scores.copy()

    if EVENT_ACTIVE:
        for uid, pts in scores.items():
            if uid not in event_stats:
                event_stats[uid] = {"memories_generated": 0, "special_memories": 0, "duels_won": 0, "duels_lost": 0, "quiz_points_event": 0, "summer_points": 0}
            event_stats[uid]["quiz_points_event"] = event_stats[uid].get("quiz_points_event", 0) + pts

    quiz_active.pop(channel_id, None)
    quiz_expire_tasks.pop(channel_id, None)

# ===== /summon =====
summon_mode_choices = [
    discord.OptionChoice(name="👥 Team - Cùng team chống lại bot", value="team_vs_bot"),
    discord.OptionChoice(name="⚔️ Duel - 1v1 đấu solo", value="duel"),
    discord.OptionChoice(name="🤝 Coop - Cùng trả lời, tính điểm chung", value="coop")
]

@bot.slash_command(name="summon", description="Gọi đứa bạn vào chơi quiz team (Event Command) ⚔️")
async def summon_user(
    ctx: discord.ApplicationContext,
    user: discord.Option(discord.Member, "Đứa bạn muốn gọi (bắt buộc mention)"),
    chế_độ: discord.Option(str, "Chế độ chơi khi đứa bạn join", choices=summon_mode_choices, required=False)
):
    await ctx.defer()
    channel_id = str(ctx.channel.id)
    inviter_id = str(ctx.author.id)
    invited_id = str(user.id)
    invited_name = user.display_name
    mode = chế_độ if chế_độ else "team_vs_bot"

    if inviter_id == invited_id:
        return await ctx.respond("Tự summon bản thân à m? Ế quá rồi đó 💔")
    if user.bot:
        return await ctx.respond("Summon bot làm gì? Nó ko chơi đâu 🥀")
    if channel_id in summon_active and summon_active[channel_id].get("active"):
        return await ctx.respond("Đang có lời mời rồi m, đợi xong đã 💀")
    if channel_id in quiz_active and quiz_active[channel_id].get("running"):
        return await ctx.respond("Đang có quiz rồi, summon sau đi 🥀")

    summon_embed = discord.Embed(
        title=f"⚔️ SUMMON REQUEST",
        description=f"**{ctx.author.display_name}** đang gọi **{invited_name}** vào chơi quiz!\n\nChế độ: `{mode}`",
        color=0xFF6B35
    )
    summon_embed.set_footer(text=f"Event Command | {random_vibe()}")
    await ctx.respond(embed=summon_embed)

    summon_active[channel_id] = {
        "active": True,
        "inviter_id": inviter_id,
        "inviter_name": ctx.author.display_name,
        "invited_id": invited_id,
        "invited_name": invited_name,
        "mode": mode,
        "start_time": datetime.datetime.now(pytz.timezone('Asia/Ho_Chi_Minh')),
        "interaction": ctx,
        "accepted": False
    }

    async def summon_timeout(cid):
        try:
            await asyncio.sleep(30)
            if cid in summon_active and summon_active[cid].get("active") and not summon_active[cid].get("accepted"):
                await ctx.channel.send(f"⏰ **HẾT GIỜ!** {invited_name} AFK rồi 🥀")
                summon_active.pop(cid, None)
        except asyncio.CancelledError:
            pass

    task = asyncio.create_task(summon_timeout(channel_id))
    summon_active[channel_id]["timeout_task"] = task

# ===== /event_lb =====
@bot.slash_command(name="event_lb", description="Bảng xếp hạng Summer Event 🏆")
async def event_leaderboard(ctx: discord.ApplicationContext):
    await ctx.defer()
    if not EVENT_ACTIVE:
        return await ctx.respond("Event đã kết thúc rồi m 🥀")
    if not event_stats:
        return await ctx.respond("Chưa có ai tham gia event cả 💔")

    leaderboard = []
    for user_id, stats in event_stats.items():
        total_score = (
            stats.get("quiz_points_event", 0) * 2 +
            stats.get("special_memories", 0) * 10 +
            stats.get("duels_won", 0) * 5 -
            stats.get("duels_lost", 0) * 2 +
            stats.get("memories_generated", 0) +
            stats.get("summer_points", 0)
        )
        leaderboard.append((user_id, total_score, stats))
    leaderboard.sort(key=lambda x: x[1], reverse=True)

    embed = discord.Embed(title="☀️ SUMMER EVENT 2026", color=0xFF6B35)
    for i, (user_id, score, stats) in enumerate(leaderboard[:10], 1):
        user = ctx.guild.get_member(int(user_id))
        name = user.display_name if user else f"User_{user_id[:6]}"
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, "🎖️")
        embed.add_field(name=f"{medal} #{i} {name} — {score} pts", value=f"Quiz: {stats.get('quiz_points_event', 0)} | Summer: {stats.get('summer_points', 0)}", inline=False)
    embed.set_footer(text=f"Summer Event 2026 | {random_vibe()}")
    await ctx.respond(embed=embed)

# ===== /event_status =====
@bot.slash_command(name="event_status", description="Xem tình trạng Summer Event ☀️")
async def event_status(ctx: discord.ApplicationContext):
    await ctx.defer()
    if not EVENT_ACTIVE:
        return await ctx.respond("Event đã kết thúc 🥀")

    vn_now = datetime.datetime.now(pytz.timezone('Asia/Ho_Chi_Minh'))
    days_left = (EVENT_END_DATE - vn_now).days
    user_id = str(ctx.author.id)
    stats = event_stats.get(user_id, {"quiz_points_event": 0, "summer_points": 0, "duels_won": 0, "duels_lost": 0})

    embed = discord.Embed(title="☀️ EVENT STATUS", color=0xFF6B35)
    embed.add_field(name="⏱️ Còn lại", value=f"{days_left} ngày")
    embed.add_field(name="🌟 Golden Hour", value="🟡 ACTIVE" if golden_hour_active else "⚫ Inactive")
    embed.add_field(name="📊 Stats", value=f"Quiz: {stats['quiz_points_event']} | Summer: {stats['summer_points']}\nDuel W/L: {stats['duels_won']}/{stats['duels_lost']}")
    await ctx.respond(embed=embed)

# ===== /summer_quote =====
@bot.slash_command(name="summer_quote", description="Nhận một câu quote mùa hè ☀️")
async def summer_quote(ctx: discord.ApplicationContext):
    SUMMER_QUOTES = [
        "Mùa hè đến rồi, đừng ngồi trong phòng nữa 🔥",
        "Đi biển đi mày ơi 🏖️",
        "Hè là để chill 💀",
        "Ly sinh tố dưa hấu 🍉",
        "Đừng để mùa hè trôi qua vô nghĩa 📸",
    ]
    await ctx.respond(random.choice(SUMMER_QUOTES))

# ===== /summer_fact =====
@bot.slash_command(name="summer_fact", description="Nhận một fact thú vị về mùa hè 🧊")
async def summer_fact(ctx: discord.ApplicationContext):
    SUMMER_FACTS = [
        "Trái đất nhận năng lượng mặt trời nhiều nhất vào hè ☀️",
        "Ngày hạ chí (21/6) là ngày dài nhất",
        "Dưa hấu có 92% là nước 🍉",
    ]
    await ctx.respond(random.choice(SUMMER_FACTS))

# ===== /summer_predict =====
@bot.slash_command(name="summer_predict", description="Dự đoán mùa hè của mày 🔮")
async def summer_predict(ctx: discord.ApplicationContext):
    predictions = [
        "Mày sẽ có chuyến đi biển siêu đáng nhớ 💀",
        "Crush sẽ rep story mày ✨",
        "Mày sẽ tìm thấy đam mê mới 🎨",
    ]
    await ctx.respond(random.choice(predictions))

# ===== /summer_gacha =====
@bot.slash_command(name="summer_gacha", description="Gacha item mùa hè ☀️")
async def summer_gacha(ctx: discord.ApplicationContext):
    await ctx.defer()
    if not EVENT_ACTIVE:
        return await ctx.respond("Event chưa diễn ra hoặc đã kết thúc 🥀")

    user_id = str(ctx.author.id)
    today_str = datetime.datetime.now(pytz.timezone('Asia/Ho_Chi_Minh')).strftime("%Y-%m-%d")

    if user_id not in daily_claim_tracker:
        daily_claim_tracker[user_id] = {"last_reset": "", "rolls": 0}

    if daily_claim_tracker[user_id]["last_reset"] != today_str:
        daily_claim_tracker[user_id]["rolls"] = daily_claim_tracker[user_id].get("rolls", 0) + 10
        daily_claim_tracker[user_id]["last_reset"] = today_str

    if daily_claim_tracker[user_id]["rolls"] <= 0:
        return await ctx.respond("Hết lượt rồi, mai reset nha 🥀")

    GACHA_ITEMS = {
        "🍦 Kem": {"rarity": "common"},
        "🍉 Dưa Hấu": {"rarity": "common"},
        "🌊 Sóng Biển": {"rarity": "rare"},
        "🎸 Guitar": {"rarity": "rare"},
        "🌠 Sao Băng": {"rarity": "epic"},
        "☀️ Sunrise": {"rarity": "epic"},
        "👑 Vương Miện Hè": {"rarity": "legendary"},
        "🌟 Tinh Tú Mùa Hè": {"rarity": "transcendent"},
    }
    GACHA_RATES = {"common": 52.5, "rare": 32.5, "epic": 13.0, "legendary": 1.5, "transcendent": 0.5}

    roll = random.choices(list(GACHA_RATES.keys()), weights=list(GACHA_RATES.values()), k=1)[0]
    items = [item for item, data in GACHA_ITEMS.items() if data["rarity"] == roll]
    item = random.choice(items)
    bonus_points = {"common": 1, "rare": 3, "epic": 7, "legendary": 15, "transcendent": 30}
    pts = bonus_points[roll]

    daily_claim_tracker[user_id]["rolls"] -= 1

    if user_id not in event_stats:
        event_stats[user_id] = {"memories_generated": 0, "special_memories": 0, "duels_won": 0, "duels_lost": 0, "quiz_points_event": 0, "summer_points": 0}
    event_stats[user_id]["summer_points"] = event_stats[user_id].get("summer_points", 0) + pts

    rarity_emoji = {"common": "⚪", "rare": "🔵", "epic": "🟣", "legendary": "🟡", "transcendent": "🔮"}
    embed = discord.Embed(
        title="🎰 SUMMER GACHA",
        description=f"{ctx.author.display_name} roll được **{item}**\n{rarity_emoji[roll]} +{pts} điểm",
        color=0xFF6B35
    )
    embed.set_footer(text=f"Còn {daily_claim_tracker[user_id]['rolls']} lượt")
    await ctx.respond(embed=embed)


# ===== SUMMON QUIZ HANDLERS =====
async def start_summon_quiz(channel_id, summon_data, message):
    mode = summon_data.get("mode", "team_vs_bot")
    inviter_id = summon_data.get("inviter_id")
    invited_id = summon_data.get("invited_id")

    for uid in [inviter_id, invited_id]:
        if uid not in event_stats:
            event_stats[uid] = {"memories_generated": 0, "special_memories": 0, "duels_won": 0, "duels_lost": 0, "quiz_points_event": 0, "summer_points": 0}

    quiz_active[channel_id] = {
        "running": True,
        "current_q": 0,
        "total_q": 3,
        "questions": [],
        "scores": {},
        "mode": mode,
        "model_used": "GPT-OSS-120B",
        "difficulty": "trung bình",
        "points_per_q": 5 if golden_hour_active else 2.5,
        "time_per_q": 45,
        "topic": "random",
        "completed_questions": 0,
        "summon_mode": True,
        "inviter_id": inviter_id,
        "invited_id": invited_id
    }

    for q_num in range(1, 4):
        if not quiz_active.get(channel_id, {}).get("running"):
            break

        quiz_active[channel_id]["current_q"] = q_num
        quiz_prompt = f"""Tạo 1 câu hỏi trắc nghiệm random, độ khó: trung bình.
SEED: {random.randint(1000, 9999)}
CÂU HỎI: [nội dung]
A. [đáp án A]
B. [đáp án B]
C. [đáp án C]
D. [đáp án D]
ĐÁP ÁN: [chữ cái A/B/C/D]
GIẢI THÍCH: [1-2 dòng]"""

        try:
            temp_msgs = [
                {"role": "system", "content": "M là bot tạo quiz, output đúng format."},
                {"role": "user", "content": quiz_prompt}
            ]
            raw = await get_model_response(temp_msgs, MODELS_CONFIG["GPT-OSS-120B"])
            raw = remove_thinking(raw)

            lines = raw.strip().splitlines()
            q_lines, ans_map, correct, expl = [], {}, None, ""
            for l in lines:
                l = l.strip()
                if l.startswith("CÂU HỎI:"): q_lines.append(l.replace("CÂU HỎI:", "").strip())
                elif l.startswith(("A.", "B.", "C.", "D.")): ans_map[l[0]] = l[2:].strip(); q_lines.append(l)
                elif l.startswith("ĐÁP ÁN:"): correct = l.replace("ĐÁP ÁN:", "").strip().upper()
                elif l.startswith("GIẢI THÍCH:"): expl = l.replace("GIẢI THÍCH:", "").strip()

            if not correct or correct not in ans_map: continue

            q_data = {"q_num": q_num, "question": q_lines[0], "options": q_lines[1:], "answer": correct, "explanation": expl, "points": 5 if golden_hour_active else 2.5, "ans_map": ans_map, "answered": False}
            quiz_active[channel_id]["questions"].append(q_data)

            mode_emoji = {"team_vs_bot": "👥", "duel": "⚔️", "coop": "🤝"}
            embed = discord.Embed(title=f"{mode_emoji.get(mode, '⚔️')} SUMMON QUIZ - Câu {q_num}/3", description="\n".join(q_lines), color=0xFF6B35)
            await message.channel.send(embed=embed)

            wait_start = asyncio.get_event_loop().time()
            while asyncio.get_event_loop().time() - wait_start < 47:
                await asyncio.sleep(1)
                if quiz_active[channel_id]["questions"][q_num-1].get("answered"): break
                if not quiz_active.get(channel_id, {}).get("running"): break

        except Exception as e:
            print(f"Lỗi summon quiz: {e}")
            continue

    await end_summon_quiz(channel_id, message)
    summon_active.pop(channel_id, None)


async def end_summon_quiz(channel_id, message):
    if channel_id not in quiz_active: return
    session = quiz_active[channel_id]
    session["running"] = False
    scores = session.get("scores", {})
    mode = session.get("mode")
    inviter_id = session.get("inviter_id")
    invited_id = session.get("invited_id")

    embed = discord.Embed(title="🏁 KẾT THÚC SUMMON QUIZ", color=0x00FF9D)
    score_lines = []
    guild = getattr(message, 'guild', None)
    for uid, score in scores.items():
        user = guild.get_member(int(uid)) if guild else None
        name = user.display_name if user else f"User_{uid[:6]}"
        score_lines.append(f"• {name}: {score}đ")
    embed.add_field(name="📊 Điểm", value="\n".join(score_lines) if score_lines else "Chả ai trả lời")
    await message.channel.send(embed=embed)
    quiz_active.pop(channel_id, None)


# === ON MESSAGE ===
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

    if uid not in chat_history:
        tz_VN = pytz.timezone('Asia/Ho_Chi_Minh')
        now = datetime.datetime.now(tz_VN).strftime("%H:%M:%S %d/%m/%Y")
        if is_dm:
            user_name = message.author.display_name
            current_sys = system_instruction.format(user_id=f"{user_name} (DM)", current_time=now)
        else:
            channel_name = message.channel.name if hasattr(message.channel, 'name') else 'DM'
            current_sys = system_instruction.format(user_id=f"Multiple users in {channel_name}", current_time=now)
        chat_history[uid] = [{"role": "system", "content": current_sys}]

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

    should_respond = is_mentioned or is_dm or is_reply_to_bot or is_keyword_trigger

    channel_id = str(message.channel.id)

    # SUMMON ACCEPT CHECK
    if channel_id in summon_active and summon_active[channel_id].get("active"):
        summon_data = summon_active[channel_id]
        if not summon_data.get("accepted"):
            invited_id = summon_data.get("invited_id")
            if str(message.author.id) == invited_id:
                if message.content.lower().strip() in ['join', 'ok', 'yes', 'đồng ý', 'chơi', 'đi']:
                    summon_data["accepted"] = True
                    if summon_data.get("timeout_task"):
                        summon_data["timeout_task"].cancel()
                    await message.reply(f"✅ **{message.author.display_name}** đã accept!", mention_author=False)
                    await start_summon_quiz(channel_id, summon_data, message)
                    return

    # QUIZ ANSWER CHECK
    if channel_id in quiz_active and not message.author.bot:
        quiz_session = quiz_active[channel_id]
        if quiz_session.get("running"):
            current_q_idx = quiz_session.get("current_q", 1) - 1
            questions = quiz_session.get("questions", [])
            if current_q_idx < len(questions):
                current_q = questions[current_q_idx]
                if not current_q.get("answered", False):
                    content_upper = message.content.strip().upper()
                    if content_upper in ['A', 'B', 'C', 'D']:
                        if channel_id in quiz_expire_tasks:
                            task_dict = quiz_expire_tasks.get(channel_id, {})
                            if current_q_idx + 1 in task_dict:
                                task_dict[current_q_idx + 1].cancel()
                                del task_dict[current_q_idx + 1]

                        user_id = str(message.author.id)
                        if "scores" not in quiz_session:
                            quiz_session["scores"] = {}

                        if content_upper == current_q["answer"]:
                            points = current_q.get("points", 1)
                            quiz_session["scores"][user_id] = quiz_session["scores"].get(user_id, 0) + points
                            if channel_id not in quiz_scores:
                                quiz_scores[channel_id] = {}
                            quiz_scores[channel_id][user_id] = quiz_scores[channel_id].get(user_id, 0) + points
                            current_q["answered"] = True
                            quiz_session["completed_questions"] = quiz_session.get("completed_questions", 0) + 1
                            await message.reply(f"✅ **ĐÚNG RỒI!** +{points}đ {current_q.get('explanation', '')}")
                        else:
                            current_q["answered"] = True
                            quiz_session["completed_questions"] = quiz_session.get("completed_questions", 0) + 1
                            await message.reply(f"❌ **SAI RỒI!** Đáp án: **{current_q['answer']}**")

                        if quiz_session["completed_questions"] >= quiz_session.get("total_q", 1):
                            await end_quiz_session(channel_id, message)
                        return

    if not should_respond:
        return

    if CHAT_DISABLED:
        return

    if BOT_UPDATED and not is_dm:
        if cooldown_start_time:
            elapsed = (datetime.datetime.now(pytz.timezone('Asia/Ho_Chi_Minh')) - cooldown_start_time).total_seconds()
            remaining = max(0, UPDATE_COOLDOWN_SECONDS - int(elapsed))
        else:
            remaining = UPDATE_COOLDOWN_SECONDS
        await message.reply(f"⏳ Bot vừa update xong, đợi {remaining}s nữa 🥀", mention_author=False)
        return

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
                user_msg_content.append({"type": "text", "text": f"{message.author.display_name}: {content}"})
            else:
                user_msg_content.append({"type": "text", "text": f"{message.author.display_name}: [gửi ảnh/file]"})

            if message.attachments:
                for att in message.attachments:
                    filename = att.filename.lower()
                    ext = filename.split('.')[-1] if '.' in filename else ''
                    is_dockerfile = filename.endswith('dockerfile') or 'dockerfile' in filename

                    if MODELS_CONFIG[CURRENT_MODEL]["vision"] and att.content_type and att.content_type.startswith('image/'):
                        try:
                            img_data = await att.read()
                            img_base64 = base64.b64encode(img_data).decode('utf-8')
                            img_url = f"data:{att.content_type};base64,{img_base64}"
                            user_msg_content.append({"type": "image_url", "image_url": {"url": img_url}})
                        except:
                            pass
                    elif ext in TEXT_EXTENSIONS or is_dockerfile:
                        try:
                            file_text = await read_text_attachment(att)
                            formatted = format_code_snippet(att.filename, file_text)
                            file_contents.append(f"📄 File `{att.filename}`:\n{formatted}")
                        except:
                            pass

            if file_contents:
                user_msg_content[0]["text"] += "\n\n" + "\n".join(file_contents)

            user_msg = {"role": "user", "content": user_msg_content}
            chat_history[uid].append(user_msg)

            reply = await get_model_response(chat_history[uid], MODELS_CONFIG[CURRENT_MODEL])
            chat_history[uid].append({"role": "assistant", "content": reply})

            if len(chat_history[uid]) > 16:
                chat_history[uid] = [chat_history[uid][0]] + chat_history[uid][-15:]

            await message.reply(reply[:1900], mention_author=False)

        except Exception as e:
            print(f"Lỗi chat: {str(e)}")
            await message.reply(f"Lỗi r: {str(e)[:100]} 💀", mention_author=False)


if __name__ == "__main__":
    thread = Thread(target=run_flask)
    thread.daemon = True
    thread.start()
    bot.run(os.getenv("DISCORD_TOKEN"))