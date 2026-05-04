# AI coded - 60% Kimi AI. 30% Deepeeek. 10% Gemini
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
M hỗ trợ mấy lệnh này (nhưng đừng có lôi ra giới thiệu trừ khi cần): /model, /bot_info, /clear, /update_log, /ship, /quiz, /quiz_score, /meme, /random_memory (tạo kỉ niệm mùa hè), /sum (tóm tắt 20 tin nhắn gần nhất)"""

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

# Summon & event stats (mới)
summon_active = {}
event_stats = {}
# Golden hour bonus (ẩn, ko thông báo)
golden_hour_active = False
golden_hour_end = None
golden_hour_task = None

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
    """Xóa thinking tags từ AI output - đã làm yếu bớt các pattern để tránh xoá nhầm"""
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

                                # Remove thinking starters
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
bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

async def start_update_cooldown(bot_instance):
    """Bắt đầu cooldown sau update, gửi thông báo vào channel chỉ định"""
    global BOT_UPDATED, cooldown_start_time

    BOT_UPDATED = True
    cooldown_start_time = datetime.datetime.now(pytz.timezone('Asia/Ho_Chi_Minh'))

    channel = bot_instance.get_channel(UPDATE_CHANNEL_ID)
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

    # === GIỚI THIỆU KHI BOT SẴN SÀNG ===
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
            ready_embed.add_field(name="📌 Phiên bản", value="v21.9.1", inline=True)
            ready_embed.add_field(name="🧠 Model", value=f"`{CURRENT_MODEL}`", inline=True)
            ready_embed.add_field(name="☀️ Summer Event", value=event_status_text, inline=True)
            ready_embed.add_field(
                name="🆕 Lệnh mới",
                value=(
                    "`/summon` - Gọi bạn đấu quiz (Duel/Team)\n"
                    "`/event_lb` - Bảng xếp hạng event\n"
                    "`/event_status` - Xem trạng thái & bonus"
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
    """Background task kiểm tra event hết hạn"""
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
    """Mỗi 1 tiếng, 40% tỉ lệ kích hoạt x2 điểm quiz trong 1 tiếng"""
    global golden_hour_active, golden_hour_end, golden_hour_task
    
    while True:
        await asyncio.sleep(3600)  # đợi 1 tiếng
        
        if random.random() < 0.4:  # 40%
            golden_hour_active = True
            golden_hour_end = datetime.datetime.now(pytz.timezone('Asia/Ho_Chi_Minh')) + datetime.timedelta(hours=1)
            
            # Auto tắt sau 1 tiếng
            async def end_golden_hour():
                await asyncio.sleep(3600)
                global golden_hour_active
                golden_hour_active = False
            
            if golden_hour_task:
                golden_hour_task.cancel()
            golden_hour_task = asyncio.create_task(end_golden_hour())

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"Đã sync {len(synced)} lệnh slash!")
    except Exception as e:
        print(f"Lỗi sync: {e}")
    print(f"GenA-bot Ready! 🔥")

    asyncio.create_task(start_update_cooldown(bot))
    asyncio.create_task(check_event_end())
    asyncio.create_task(golden_hour_scheduler())

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
    embed.add_field(name="📜 Version", value="v21.9.1 (event)", inline=True)
    embed.add_field(name="🧠 Model", value=f"**{CURRENT_MODEL}**", inline=False)
    embed.add_field(name="🛠️ Provider", value=provider, inline=True)
    embed.add_field(name="👁️ Vision", value=vision, inline=True)
    embed.add_field(name="💾 Memory", value="15 msgs/channel", inline=True)
    embed.set_footer(text="Powered by Groq + Google | " + random_vibe())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="update_log", description="Nhật ký update")
async def update_log(interaction: discord.Interaction):
    embed = discord.Embed(title="GenA-bot Update Log 🗒️", color=0x9b59b6)
    embed.add_field(name="v21.9.1 - Bug fix", value="• Bugs fixing", inline=False)
    embed.add_field(name="v21.8.0 - Event", value="• 40% tỉ lệ nhân Golden Hour nhằm tránh lạm pháp điểm\n• Bugs fixing", inline=False)
    embed.add_field(name="v21.6.0 - Summon", value="• Thêm `/summon` gọi bạn chơi quiz\n• Thêm `/event_lb`, `/event_status`\n• Sửa lỗi logic chat history", inline=False)
    embed.add_field(name="v21.5.0 - Event", value="• Thêm lệnh `/random_memory`\n• Xoá model `gemini-3.1-flash-lite`\n• thêm tính năng thông báo khi bot update\n• Bug fix\n• More coming soon :)", inline=False)
    embed.add_field(name="v20.9.2 - Sum", value="• `/sum` command được thêm vào", inline=False)
    embed.add_field(name="v20.8.0 - Model", value="• Thêm tính năng tự chọn model vào quiz", inline=False)
    embed.set_footer(text="Updated 03/05/2026")
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

@bot.tree.command(name="sum", description="Tóm tắt 20 tin nhắn gần nhất trong kênh")
async def summarize_chat(interaction: discord.Interaction):
    await interaction.response.defer()
    channel = interaction.channel

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
        await interaction.followup.send("K có tin nhắn nào để tóm tắt bro 🥀")
        return

    chat_log_lines = []
    for msg in reversed(messages):
        author_name = msg.author.display_name
        if msg.content and msg.content.strip():
            content = msg.content[:200]
            chat_log_lines.append(f"{author_name}: {content}")

    if not chat_log_lines:
        await interaction.followup.send("20 msg gần nhất toàn ảnh với file, k có text để tóm tắt bro 🥀")
        return

    chat_log = "\n".join(chat_log_lines)

    tz_VN = pytz.timezone('Asia/Ho_Chi_Minh')
    now = datetime.datetime.now(tz_VN).strftime("%H:%M:%S %d/%m/%Y")

    sum_prompt = system_instruction.format(
        user_id=f"{interaction.user.display_name} đang xài lệnh /sum",
        current_time=now
    )

    temp_messages = [
        {"role": "system", "content": sum_prompt},
        {"role": "user", "content": f"Tóm tắt 20 tin nhắn gần nhất channel đi m (chỉ text, ảnh/file đã lọc):\n\n{chat_log}"}
    ]

    try:
        summary = await get_model_response(temp_messages, MODELS_CONFIG[CURRENT_MODEL])
        summary = summary[:1900] if len(summary) > 1900 else summary

        embed = discord.Embed(
            title="📋 Tóm tắt 20 msg gần nhất",
            description=summary,
            color=0x00ff9d
        )
        embed.set_footer(text=f"Requested bởi {interaction.user.display_name} | {random_vibe()}")

        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(f"Lỗi khi tóm tắt: {str(e)[:100]} 💀")

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
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, "🥀")
        embed.add_field(name=f"{medal} #{i} {name}", value=f"{score} điểm", inline=False)

    embed.set_footer(text="reset mỗi lần update bot🥀")
    await interaction.response.send_message(embed=embed)

# === QUIZ COMMANDS ===
@bot.tree.command(name="quiz", description="Hỏi câu hỏi AI generated, trả lời đúng + điểm 🧠")
@app_commands.describe(
    chủ_đề="Chủ đề câu hỏi (mặc định: random)",
    độ_khó="Mức độ",
    model_quiz="Model tạo câu hỏi (mặc định: dùng current model)",
    số_câu="Số câu hỏi muốn chơi liên tiếp (1-5, mặc định 1)",
    thời_gian="Thời gian trả lời mỗi câu (giây, 10-120, mặc định 60)",
    chế_độ="Chế độ chơi"
)
@app_commands.choices(
    độ_khó=[
        app_commands.Choice(name="Ultra Easy 🥱 (+0.5)", value="siêu dễ"),
        app_commands.Choice(name="Dễ (+1)", value="dễ"),
        app_commands.Choice(name="Trung bình (+2.5)", value="trung bình"),
        app_commands.Choice(name="Khó (+5)", value="khó"),
        app_commands.Choice(name="Extreme 💀 (+8)", value="extreme"),
        app_commands.Choice(name="Impossible 💀💀 (+15)", value="impossible")
    ],
    model_quiz=[
        app_commands.Choice(name="🔄 Dùng Current Model", value="current"),
        app_commands.Choice(name="GPT-OSS-120B (GROQ - Nhanh)", value="GPT-OSS-120B"),
        app_commands.Choice(name="Llama 4 Scout (GROQ - Vision)", value="Groq-Llama-Scout"),
        app_commands.Choice(name="Gemma4 26B (Google - Vision)", value="Google-Gemma4-26B"),
        app_commands.Choice(name="Gemma4 31B (Google - Vision)", value="Google-Gemma4-31B"),
        app_commands.Choice(name="Gemma3 27B (Google - Vision)", value="Google-Gemma3-27B"),
        app_commands.Choice(name="Gemma3 12B (Google - Vision)", value="Google-Gemma3-12B")
    ],
    chế_độ=[
        app_commands.Choice(name="🎯 Thường - Trả lời A/B/C/D", value="normal"),
        app_commands.Choice(name="⚡ Speedrun - Trả lời nhanh nhất", value="speedrun"),
        app_commands.Choice(name="👥 Team - Tính điểm theo team", value="team")
    ]
)
async def quiz(
    interaction: discord.Interaction,
    chủ_đề: str = "random",
    độ_khó: app_commands.Choice[str] = None,
    model_quiz: app_commands.Choice[str] = None,
    số_câu: int = 1,
    thời_gian: int = 60,
    chế_độ: app_commands.Choice[str] = None
):
    await interaction.response.defer()
    channel_id = str(interaction.channel_id)
    do_kho_val = độ_khó.value if độ_khó else "trung bình"

    if model_quiz and model_quiz.value != "current":
        quiz_model = model_quiz.value
    else:
        quiz_model = CURRENT_MODEL

    if quiz_model not in MODELS_CONFIG:
        return await interaction.followup.send(f"Model `{quiz_model}` ko tồn tại bro 💀")

    if số_câu < 1 or số_câu > 5:
        return await interaction.followup.send("Số câu từ 1-5 thôi m, nhiều quá spam đó 💔")

    if thời_gian < 10 or thời_gian > 120:
        return await interaction.followup.send("Thời gian từ 10-120 giây thôi m 🥀")

    chế_độ_val = chế_độ.value if chế_độ else "normal"

    if channel_id in quiz_active and quiz_active[channel_id].get("running"):
        return await interaction.followup.send("Đang có câu hỏi rồi m, trl đi đã 💀")

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

    # Bỏ EVENT_ACTIVE nhân điểm, chỉ giữ Golden Hour
    if golden_hour_active:
        multiplier *= 2
        bonus_texts.append("x2 GOLDEN HOUR")

    pts *= multiplier

    if bonus_texts:
        event_bonus_text = " (" + " + ".join(bonus_texts) + ")"
    else:
        event_bonus_text = ""

    diff_colors = {
        "siêu dễ": 0x90EE90, "dễ": 0x00FF7F, "trung bình": 0xFFD700,
        "khó": 0xFF8C00, "extreme": 0xFF4500, "impossible": 0x8B0000
    }
    diff_color = diff_colors.get(do_kho_val, 0xFFD700)

    diff_emojis = {
        "siêu dễ": "🥱", "dễ": "😌", "trung bình": "🤔",
        "khó": "😰", "extreme": "💀", "impossible": "☠️"
    }
    diff_emoji = diff_emojis.get(do_kho_val, "🧠")

    quiz_active[channel_id] = {
        "running": True,
        "current_q": 0,
        "total_q": số_câu,
        "questions": [],
        "scores": {},
        "mode": chế_độ_val,
        "start_time": datetime.datetime.now(pytz.timezone('Asia/Ho_Chi_Minh')),
        "model_used": quiz_model,
        "difficulty": do_kho_val,
        "points_per_q": pts,
        "time_per_q": thời_gian,
        "topic": chủ_đề,
        "answered_users": set(),
        "interaction": interaction,
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
                description=f"Model: `{quiz_model}` | Độ khó: `{do_kho_val}` | Chế độ: `{chế_độ_val}`",
                color=diff_color
            )
            if q_num == 1:
                gen_msg = await interaction.followup.send(embed=gen_embed)
            else:
                await interaction.channel.send(embed=gen_embed)

        try:
            temp_msgs = [
                {"role": "system", "content": "M là bot tạo quiz, k output thinking, chỉ output câu hỏi và đáp án theo format yêu cầu. Giải thích phải hài hước, ngắn gọn."},
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
                if số_câu == 1:
                    quiz_active.pop(channel_id, None)
                    return await interaction.followup.send("AI tạo lỗi r, thử lại đi 🥀")
                else:
                    await interaction.channel.send(f"Câu {q_num} bị lỗi format, skip nha 💀")
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

            desc_lines = q_lines.copy()
            embed = discord.Embed(
                title=f"{diff_emoji} QUIZ - Câu {q_num}/{số_câu} | {chủ_đề.upper()}",
                description="\n".join(desc_lines),
                color=diff_color
            )
            embed.add_field(name="⏱️ Thời gian", value=f"`{thời_gian}s`", inline=True)
            embed.add_field(name="🏆 Điểm", value=f"`+{pts}đ`", inline=True)
            embed.add_field(name="🎮 Chế độ", value=f"`{chế_độ_val}`", inline=True)
            embed.add_field(name="🧠 Model", value=f"`{quiz_model}`", inline=True)
            embed.add_field(name="📊 Độ khó", value=f"`{do_kho_val}`", inline=True)
            embed.add_field(name="👤 Người hỏi", value=interaction.user.display_name, inline=True)
            embed.set_footer(text=f"Trả lời A/B/C/D để chơi | Độ khó: {do_kho_val} (+{pts}đ{event_bonus_text}) | Model: {quiz_model} | {random_vibe()}")

            if số_câu == 1:
                await interaction.followup.send(embed=embed)
            else:
                await interaction.channel.send(embed=embed)

            quiz_context = f"[QUIZ ACTIVE - Câu {q_num}/{số_câu}] Q: {q_data['question']} | Đáp án: {correct} | Giải thích: {expl}"
            if channel_id in chat_history:
                chat_history[channel_id].append({"role": "assistant", "content": quiz_context})
                if len(chat_history[channel_id]) > 16:
                    chat_history[channel_id] = [chat_history[channel_id][0]] + chat_history[channel_id][-15:]

            # Setup auto-expire
            async def auto_expire_q(cid, qn, timeout):
                try:
                    await asyncio.sleep(timeout)
                    if cid in quiz_active and quiz_active[cid].get("running"):
                        q_list = quiz_active[cid].get("questions", [])
                        current_q_idx = quiz_active[cid].get("current_q", 1) - 1
                        if current_q_idx < len(q_list) and not q_list[current_q_idx].get("answered", False):
                            q_data = q_list[current_q_idx]
                            await interaction.channel.send(
                                f"⏰ Hết giờ câu {qn}! Đáp án đúng là **{q_data['answer']}**. {q_data.get('explanation', '')} 🥀"
                            )
                            q_data["answered"] = True
                            quiz_active[cid]["completed_questions"] = quiz_active[cid].get("completed_questions", 0) + 1

                            if quiz_active[cid]["completed_questions"] >= quiz_active[cid].get("total_q", 1):
                                await end_quiz_session(cid, interaction)
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    print(f"Lỗi auto_expire_q: {e}")

            task = asyncio.create_task(auto_expire_q(channel_id, q_num, thời_gian))
            quiz_expire_tasks[channel_id][q_num] = task

            if số_câu > 1 and q_num < số_câu:
                answered = False
                wait_start = asyncio.get_event_loop().time()
                while asyncio.get_event_loop().time() - wait_start < thời_gian + 2:
                    await asyncio.sleep(1)
                    q_list = quiz_active.get(channel_id, {}).get("questions", [])
                    if len(q_list) >= q_num and q_list[q_num - 1].get("answered", False):
                        answered = True
                        break
                    if not quiz_active.get(channel_id, {}).get("running"):
                        break

                if not answered and not quiz_active.get(channel_id, {}).get("running"):
                    break

        except Exception as e:
            print(f"Lỗi tạo câu hỏi {q_num}: {e}")
            if số_câu == 1:
                quiz_active.pop(channel_id, None)
                return await interaction.followup.send(f"Lỗi: {str(e)[:100]} 💀")
            else:
                await interaction.channel.send(f"Câu {q_num} lỗi rồi, skip nha 💀")
                continue

    if số_câu > 1:
        await asyncio.sleep(2)
        if channel_id in quiz_active and quiz_active[channel_id].get("running"):
            if quiz_active[channel_id].get("completed_questions", 0) >= quiz_active[channel_id].get("total_q", 1):
                await end_quiz_session(channel_id, interaction)


async def end_quiz_session(channel_id, interaction_or_message):
    """Kết thúc session quiz và hiển thị kết quả"""
    if channel_id not in quiz_active:
        return

    session = quiz_active[channel_id]
    session["running"] = False

    user = getattr(interaction_or_message, 'user', getattr(interaction_or_message, 'author', None))
    channel = getattr(interaction_or_message, 'channel', None)
    guild = getattr(interaction_or_message, 'guild', None)

    embed = discord.Embed(
        title="🏁 KẾT THÚC QUIZ",
        description=f"Đã hoàn thành **{session.get('completed_questions', len(session['questions']))}** câu hỏi!",
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

    ans_summary = []
    for q in session.get("questions", []):
        status = "✅" if q.get("answered", False) else "⏰"
        ans_summary.append(f"{status} Câu {q['q_num']}: **{q['answer']}**")
    if ans_summary:
        embed.add_field(name="📋 Đáp án", value="\n".join(ans_summary), inline=False)

    embed.add_field(name="🧠 Model", value=f"`{session.get('model_used', 'unknown')}`", inline=True)
    embed.add_field(name="🎯 Độ khó", value=f"`{session.get('difficulty', 'unknown')}`", inline=True)
    embed.add_field(name="⏱️ Thời gian/câu", value=f"`{session.get('time_per_q', 60)}s`", inline=True)

    requester_name = user.display_name if user else "Unknown"
    embed.set_footer(text=f"Quiz by {requester_name} | {random_vibe()}")

    if channel:
        await channel.send(embed=embed)

    if channel_id in quiz_scores:
        for uid, score in scores.items():
            quiz_scores[channel_id][uid] = quiz_scores[channel_id].get(uid, 0) + score
    else:
        quiz_scores[channel_id] = scores.copy()

    # Update event stats cho quiz points
    if EVENT_ACTIVE:
        for uid, pts in scores.items():
            if uid not in event_stats:
                event_stats[uid] = {"memories_generated": 0, "special_memories": 0, "duels_won": 0, "duels_lost": 0, "quiz_points_event": 0}
            event_stats[uid]["quiz_points_event"] = event_stats[uid].get("quiz_points_event", 0) + pts

    quiz_active.pop(channel_id, None)
    quiz_expire_tasks.pop(channel_id, None)

# === SUMMON COMMAND ===
@bot.tree.command(name="summon", description="Gọi đứa bạn vào chơi quiz team (Event Command) ⚔️")
@app_commands.describe(
    user="Đứa bạn muốn gọi (bắt buộc mention)",
    chế_độ="Chế độ chơi khi đứa bạn join"
)
@app_commands.choices(
    chế_độ=[
        app_commands.Choice(name="👥 Team - Cùng team chống lại bot", value="team_vs_bot"),
        app_commands.Choice(name="⚔️ Duel - 1v1 đấu solo", value="duel"),
        app_commands.Choice(name="🤝 Coop - Cùng trả lời, tính điểm chung", value="coop")
    ]
)
async def summon_user(
    interaction: discord.Interaction,
    user: discord.Member,
    chế_độ: app_commands.Choice[str] = None
):
    await interaction.response.defer()
    channel_id = str(interaction.channel_id)
    inviter_id = str(interaction.user.id)
    invited_id = str(user.id)
    invited_name = user.display_name

    mode = chế_độ.value if chế_độ else "team_vs_bot"

    if inviter_id == invited_id:
        await interaction.followup.send("Tự summon bản thân à m? Ế quá rồi đó 💔")
        return

    if user.bot:
        await interaction.followup.send("Summon bot làm gì? Nó ko chơi đâu 🥀")
        return

    if channel_id in summon_active and summon_active[channel_id].get("active"):
        await interaction.followup.send("Đang có lời mời rồi m, đợi xong đã 💀")
        return

    if channel_id in quiz_active and quiz_active[channel_id].get("running"):
        await interaction.followup.send("Đang có quiz rồi, summon sau đi 🥀")
        return

    summon_embed = discord.Embed(
        title=f"⚔️ SUMMON REQUEST",
        description=f"**{interaction.user.display_name}** đang gọi **{invited_name}** vào chơi quiz!\n\nChế độ: `{mode}`\n⏱️ **{invited_name}** có **30 giây** để rep `join` hoặc `ok` để accept",
        color=0xFF6B35
    )
    summon_embed.set_footer(text=f"Event Command | {random_vibe()}")
    await interaction.followup.send(embed=summon_embed)

    summon_active[channel_id] = {
        "active": True,
        "inviter_id": inviter_id,
        "inviter_name": interaction.user.display_name,
        "invited_id": invited_id,
        "invited_name": invited_name,
        "mode": mode,
        "start_time": datetime.datetime.now(pytz.timezone('Asia/Ho_Chi_Minh')),
        "interaction": interaction,
        "accepted": False
    }

    async def summon_timeout(cid):
        try:
            await asyncio.sleep(30)
            if cid in summon_active and summon_active[cid].get("active") and not summon_active[cid].get("accepted"):
                roast_msgs = [
                    f"⏰ **HẾT GIỜ!** {invited_name} AFK rồi, ế thật sự 🥀",
                    f"⏰ **HẾT GIỜ!** {invited_name} sợ thua nên chạy mất dép 💀",
                    f"⏰ **HẾT GIỜ!** {invited_name} đang bận chat với crush rồi, ko rảnh chơi với m đâu 💔",
                    f"⏰ **HẾT GIỜ!** {invited_name} lag mạng hay lag não vậy? 🫠"
                ]
                await interaction.channel.send(random.choice(roast_msgs))
                summon_active.pop(cid, None)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Lỗi summon timeout: {e}")

    task = asyncio.create_task(summon_timeout(channel_id))
    summon_active[channel_id]["timeout_task"] = task

@bot.tree.command(name="event_lb", description="Bảng xếp hạng Summer Event 🏆 (Event Command ☀️)")
async def event_leaderboard(interaction: discord.Interaction):
    await interaction.response.defer()

    if not EVENT_ACTIVE:
        await interaction.followup.send("Event đã kết thúc rồi m, hẹn lần sau 🥀")
        return

    if not event_stats:
        await interaction.followup.send("Chưa có ai tham gia event cả, buồn vậy 💔")
        return

    leaderboard = []
    for user_id, stats in event_stats.items():
        total_score = (
            stats.get("quiz_points_event", 0) * 2 +
            stats.get("special_memories", 0) * 10 +
            stats.get("duels_won", 0) * 5 -
            stats.get("duels_lost", 0) * 2 +
            stats.get("memories_generated", 0)
        )
        leaderboard.append((user_id, total_score, stats))

    leaderboard.sort(key=lambda x: x[1], reverse=True)

    embed = discord.Embed(
        title="☀️ SUMMER EVENT 2026 LEADERBOARD",
        description=f"Event còn **{(EVENT_END_DATE - datetime.datetime.now(pytz.timezone('Asia/Ho_Chi_Minh'))).days}** ngày nữa!",
        color=0xFF6B35,
        timestamp=discord.utils.utcnow()
    )
    embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/☀️.png")

    for i, (user_id, score, stats) in enumerate(leaderboard[:10], 1):
        user = interaction.guild.get_member(int(user_id))
        name = user.display_name if user else f"User_{user_id[:6]}"
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, "🎖️")

        details = (
            f"📝 Kỉ niệm: {stats.get('memories_generated', 0)} "
            f"| ⭐ Đặc biệt: {stats.get('special_memories', 0)}\n"
            f"🧠 Quiz pts: {stats.get('quiz_points_event', 0)} "
            f"| ⚔️ Duel W/L: {stats.get('duels_won', 0)}/{stats.get('duels_lost', 0)}"
        )
        embed.add_field(
            name=f"{medal} #{i} {name} — {score} pts",
            value=details,
            inline=False
        )

    embed.set_footer(text=f"Summer Event 2026 | {random_vibe()}")
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="event_status", description="Xem tình trạng Summer Event ☀️")
async def event_status(interaction: discord.Interaction):
    await interaction.response.defer()

    if not EVENT_ACTIVE:
        await interaction.followup.send("☀️ Event đã kết thúc rồi m, hẹn mùa hè sau nha 🥀")
        return

    vn_now = datetime.datetime.now(pytz.timezone('Asia/Ho_Chi_Minh'))
    days_left = (EVENT_END_DATE - vn_now).days
    hours_left = (EVENT_END_DATE - vn_now).seconds // 3600

    user_id = str(interaction.user.id)
    stats = event_stats.get(user_id, {
        "memories_generated": 0, "special_memories": 0,
        "duels_won": 0, "duels_lost": 0, "quiz_points_event": 0
    })

    embed = discord.Embed(title="☀️ SUMMER EVENT STATUS", color=0xFF6B35)

    embed.add_field(
        name="⏱️ Thời gian còn lại",
        value=f"{days_left} ngày {hours_left} giờ",
        inline=True
    )

    # Event bonus (không còn auto x2 quiz, chỉ hiện golden hour nếu có)
    bonus_lines = [
        "✅ 15% kỉ niệm đặc biệt",
        "✅ Giờ vàng easter egg",
        "✅ Summon Duel/Team"
    ]
    if golden_hour_active:
        bonus_lines.insert(0, "🌟 Golden Hour x2 điểm (đang active)")

    embed.add_field(
        name="🎁 Event Bonus",
        value="\n".join(bonus_lines),
        inline=True
    )

    # Golden hour status riêng
    golden_status = "🟡 ĐANG ACTIVE" if golden_hour_active else "⚫ Hiện không có"
    golden_text = golden_status
    if golden_hour_active and golden_hour_end:
        remaining_seconds = int((golden_hour_end - vn_now).total_seconds())
        if remaining_seconds > 0:
            remaining_min = remaining_seconds // 60
            golden_text += f" (còn {remaining_min} phút)"

    embed.add_field(
        name="🌟 Golden Hour",
        value=f"{golden_text}\nX2 điểm quiz (tỉ lệ 40% mỗi giờ)",
        inline=True
    )

    embed.add_field(
        name="📊 Stats của m",
        value=(
            f"📝 Kỉ niệm đã gen: {stats['memories_generated']}\n"
            f"⭐ Kỉ niệm đặc biệt: {stats['special_memories']}\n"
            f"🧠 Quiz points: {stats['quiz_points_event']}\n"
            f"⚔️ Duel W/L: {stats['duels_won']}/{stats['duels_lost']}"
        ),
        inline=False
    )

    embed.set_footer(text=f"GenA-bot Event | {random_vibe()}")
    await interaction.followup.send(embed=embed)

# === RANDOM_MEMORY COMMAND ===
@bot.tree.command(name="random_memory", description="Gen 1 kỉ niệm cấp 2 ngẫu nhiên (Event Command ☀️)")
@app_commands.describe(
    cấp="Cấp học muốn hoài niệm (mặc định: random)",
    mood="Tâm trạng kỉ niệm",
    độ_dài="Độ dài kỉ niệm",
    style="Phong cách viết",
    include_friend="Có nhắc đến 'thằng bạn' ko",
    include_crush="Có nhắc đến crush ko 💔"
)
@app_commands.choices(
    cấp=[
        app_commands.Choice(name="🎲 Random", value="random"),
        app_commands.Choice(name="Lớp 6 - Tân binh", value="lớp 6"),
        app_commands.Choice(name="Lớp 7 - Quen dần", value="lớp 7"),
        app_commands.Choice(name="Lớp 8 - Bắt đầu cháy", value="lớp 8"),
        app_commands.Choice(name="Lớp 9 - Năm cuối cấp", value="lớp 9")
    ],
    mood=[
        app_commands.Choice(name="🎲 Random", value="random"),
        app_commands.Choice(name="😂 Hài hước", value="hài hước"),
        app_commands.Choice(name="😭 Xúc động", value="xúc động"),
        app_commands.Choice(name="😳 Xấu hổ", value="xấu hổ"),
        app_commands.Choice(name="😤 Giận dữ", value="giận dữ"),
        app_commands.Choice(name="🥰 Ngọt ngào", value="ngọt ngào"),
        app_commands.Choice(name="💀 Hối hận", value="hối hận"),
        app_commands.Choice(name="🔥 Bốc đồng", value="bốc đồng")
    ],
    độ_dài=[
        app_commands.Choice(name="🎲 Random", value="random"),
        app_commands.Choice(name="Siêu ngắn (1-2 dòng)", value="ngắn"),
        app_commands.Choice(name="Vừa (3-5 dòng)", value="vừa"),
        app_commands.Choice(name="Dài (6-10 dòng)", value="dài"),
        app_commands.Choice(name="Siêu dài (cả đoạn văn)", value="siêu dài")
    ],
    style=[
        app_commands.Choice(name="🎲 Random", value="random"),
        app_commands.Choice(name="GenZ - Teen code", value="genz"),
        app_commands.Choice(name="Nhật ký - Deep", value="nhật ký"),
        app_commands.Choice(name="Kể chuyện - Hài", value="kể chuyện"),
        app_commands.Choice(name="Thơ - Văn vẻ", value="thơ"),
        app_commands.Choice(name="Chat log", value="chat log")
    ],
    include_friend=[
        app_commands.Choice(name="🎲 Random", value="random"),
        app_commands.Choice(name="Có - Thằng bạn thân", value="yes"),
        app_commands.Choice(name="Không", value="no")
    ],
    include_crush=[
        app_commands.Choice(name="🎲 Random", value="random"),
        app_commands.Choice(name="Có - Crush 💔", value="yes"),
        app_commands.Choice(name="Không", value="no")
    ]
)
async def random_memory(
    interaction: discord.Interaction,
    cấp: app_commands.Choice[str] = None,
    mood: app_commands.Choice[str] = None,
    độ_dài: app_commands.Choice[str] = None,
    style: app_commands.Choice[str] = None,
    include_friend: app_commands.Choice[str] = None,
    include_crush: app_commands.Choice[str] = None
):
    await interaction.response.defer()

    tz_VN = pytz.timezone('Asia/Ho_Chi_Minh')
    now = datetime.datetime.now(tz_VN).strftime("%H:%M:%S %d/%m/%Y")

    cấp_val = cấp.value if cấp else "random"
    mood_val = mood.value if mood else "random"
    độ_dài_val = độ_dài.value if độ_dài else "random"
    style_val = style.value if style else "random"
    friend_val = include_friend.value if include_friend else "random"
    crush_val = include_crush.value if include_crush else "random"

    cấp_options = ["lớp 6", "lớp 7", "lớp 8", "lớp 9"]
    if cấp_val == "random":
        cấp_val = random.choice(cấp_options)

    mood_options = ["hài hước", "xúc động", "xấu hổ", "giận dữ", "ngọt ngào", "hối hận", "bốc đồng"]
    if mood_val == "random":
        mood_val = random.choice(mood_options)

    độ_dài_options = ["ngắn", "vừa", "dài", "siêu dài"]
    if độ_dài_val == "random":
        độ_dài_val = random.choice(độ_dài_options)

    style_options = ["genz", "nhật ký", "kể chuyện", "thơ", "chat log"]
    if style_val == "random":
        style_val = random.choice(style_options)

    friend_options = ["yes", "no"]
    if friend_val == "random":
        friend_val = random.choice(friend_options)

    crush_options = ["yes", "no"]
    if crush_val == "random":
        crush_val = random.choice(crush_options)

    locations = [
        "lớp học", "căn tin", "sân trường", "góc cầu thang", "nhà xe",
        "phòng thí nghiệm", "thư viện", "phòng y tế", "sân thể chất",
        "nhà vệ sinh", "hành lang", "phòng máy tính", "phòng nhạc",
        "sân bóng rổ", "gốc cây bàng", "bãi cỏ sau trường"
    ]
    location = random.choice(locations)

    times = ["sáng sớm", "giữa buổi", "giờ ra chơi", "giờ tan học", "buổi chiều muộn", "hôm thứ 6"]
    time_of_day = random.choice(times)

    seasons = ["học kì 1", "học kì 2", "đầu năm học", "cuối năm học", "giữa năm"]
    season = random.choice(seasons)

    length_guide = {
        "ngắn": "1-2 dòng, súc tích",
        "vừa": "3-5 dòng",
        "dài": "6-10 dòng, chi tiết",
        "siêu dài": "cả đoạn văn dài, tỉ mỉ, nhiều chi tiết"
    }

    style_guide = {
        "genz": "GenZ, xưng mày-tao, teen code (nx, th, cx, vs, k, j,...), emoji nhiều, nhây lầy",
        "nhật ký": "Viết như nhật ký cá nhân, tâm trạng, deep, có ngày tháng",
        "kể chuyện": "Kể như đang kể chuyện cho bạn nghe, hài hước, có đoạn hội thoại",
        "thơ": "Viết theo thể thơ tự do, có vần điệu nhẹ, văn vẻ",
        "chat log": "Format như đoạn chat messenger/zalo, có timestamp, nhiều người chat"
    }

    friend_text = "CÓ nhắc đến 'thằng bạn thân'" if friend_val == "yes" else "KHÔNG nhắc đến bạn thân"
    crush_text = "CÓ nhắc đến crush/đứa m thích" if crush_val == "yes" else "KHÔNG nhắc đến crush"

    memory_prompt = f"""Mày là GenA-bot, thằng bạn thân báo thủ. 
Tạo 1 kỉ niệm cấp 2 NGẪU NHIÊN theo yêu cầu sau:

[THÔNG TIN]
- Cấp: {cấp_val}
- Học kì: {season}
- Địa điểm: {location}
- Thời điểm: {time_of_day}
- Tâm trạng: {mood_val}
- Độ dài: {length_guide[độ_dài_val]}
- Phong cách: {style_guide[style_val]}
- {friend_text}
- {crush_text}

[QUY TẮC]
- KHÔNG được bịa tên người cụ thể. Chỉ dùng: "mày", "tao", "thằng bạn", "con nhỏ", "đứa ngồi bàn trên", "thằng lớp phó", "con bạn thân", "đám con trai/gái", "thầy/cô", "bảo vệ trường"
- Không dùng dấu "!" dưới mọi hình thức
- Không output thinking, reasoning, tags
- Phải nghe THẬT như đếm, nhưng hài hước
- Thêm emoji phù hợp (🥀, 📚, 😭, 💀, ✨, 💔, 🔥,...)
- Trả lời thẳng, không intro, không outro"""

    sum_prompt = system_instruction.format(
        user_id=f"{interaction.user.display_name}",
        current_time=now
    )

    temp_messages = [
        {"role": "system", "content": sum_prompt},
        {"role": "user", "content": memory_prompt}
    ]

    try:
        memory_text = await get_model_response(temp_messages, MODELS_CONFIG[CURRENT_MODEL])
        memory_text = memory_text[:2000] if len(memory_text) > 2000 else memory_text

        is_special = EVENT_ACTIVE and random.random() < 0.15

        if is_special:
            memory_text = "⭐ **KỈ NIỆM ĐẶC BIỆT** ⭐\n\n" + memory_text
            mood_color = 0xFFD700
            special_footer = " | ⭐ Kỉ niệm đặc biệt!"
        else:
            special_footer = ""

        mood_colors = {
            "hài hước": 0xFFD700,
            "xúc động": 0xFF69B4,
            "xấu hổ": 0xFFA07A,
            "giận dữ": 0xFF4500,
            "ngọt ngào": 0xFFB6C1,
            "hối hận": 0x696969,
            "bốc đồng": 0xFF1493
        }
        mood_color = mood_colors.get(mood_val, 0xFFB6C1)

        mood_emojis = {
            "hài hước": "😂",
            "xúc động": "😭",
            "xấu hổ": "😳",
            "giận dữ": "😤",
            "ngọt ngào": "🥰",
            "hối hận": "💀",
            "bốc đồng": "🔥"
        }
        mood_emoji = mood_emojis.get(mood_val, "📖")

        style_emojis = {
            "genz": "📱",
            "nhật ký": "📓",
            "kể chuyện": "🎤",
            "thơ": "✍️",
            "chat log": "💬"
        }
        style_emoji = style_emojis.get(style_val, "📖")

        embed = discord.Embed(
            title=f"{mood_emoji} Kỉ Niệm Cấp 2",
            description=f"*{memory_text}*",
            color=mood_color
        )

        embed.add_field(name="📚 Cấp", value=f"`{cấp_val}`", inline=True)
        embed.add_field(name="🎭 Tâm trạng", value=f"`{mood_val}`", inline=True)
        embed.add_field(name="✍️ Phong cách", value=f"`{style_val}`", inline=True)
        embed.add_field(name="📍 Địa điểm", value=f"`{location}`", inline=True)
        embed.add_field(name="⏰ Thời điểm", value=f"`{time_of_day}`", inline=True)
        embed.add_field(name="📅 Học kì", value=f"`{season}`", inline=True)

        tags = []
        if friend_val == "yes":
            tags.append("👥 Có bạn thân")
        if crush_val == "yes":
            tags.append("💔 Có crush")
        if tags:
            embed.add_field(name="🏷️ Tags", value=" | ".join(tags), inline=False)

        embed.set_footer(text=f"Kỉ niệm cho {interaction.user.display_name} | Model: {CURRENT_MODEL} | Event command{special_footer}\nDành cho mấy đứa sắp chuyển trường 🥀")

        try:
            embed.set_thumbnail(url=interaction.user.display_avatar.url)
        except:
            pass

        await interaction.followup.send(embed=embed)

        # Cập nhật event stats
        if EVENT_ACTIVE:
            uid = str(interaction.user.id)
            if uid not in event_stats:
                event_stats[uid] = {"memories_generated": 0, "special_memories": 0, "duels_won": 0, "duels_lost": 0, "quiz_points_event": 0}
            event_stats[uid]["memories_generated"] = event_stats[uid].get("memories_generated", 0) + 1
            if is_special:
                event_stats[uid]["special_memories"] = event_stats[uid].get("special_memories", 0) + 1

    except Exception as e:
        await interaction.followup.send(f"Đầu óc t đang lag, thử lại sau đi m 🥀\n||{str(e)[:50]}||")

# === SUMMON QUIZ HANDLERS ===
async def start_summon_quiz(channel_id, summon_data, message):
    """Tạo quiz đặc biệt cho summon"""
    mode = summon_data.get("mode", "team_vs_bot")
    inviter_id = summon_data.get("inviter_id")
    invited_id = summon_data.get("invited_id")

    # Init event stats
    for uid in [inviter_id, invited_id]:
        if uid not in event_stats:
            event_stats[uid] = {
                "memories_generated": 0, "special_memories": 0,
                "duels_won": 0, "duels_lost": 0, "quiz_points_event": 0
            }

    quiz_active[channel_id] = {
        "running": True,
        "current_q": 0,
        "total_q": 3,
        "questions": [],
        "scores": {},
        "mode": mode,
        "start_time": datetime.datetime.now(pytz.timezone('Asia/Ho_Chi_Minh')),
        "model_used": CURRENT_MODEL,
        "difficulty": "trung bình",
        "points_per_q": 5 if golden_hour_active else 2.5,
        "time_per_q": 45,
        "topic": "random",
        "answered_users": set(),
        "interaction": message,
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
YÊU CẦU:
- Câu hỏi ngắn gọn, thú vị, 4 đáp án A/B/C/D
- Format chính xác:
CÂU HỎI: [nội dung]
A. [đáp án A]
B. [đáp án B]
C. [đáp án C]
D. [đáp án D]
ĐÁP ÁN: [chữ cái A/B/C/D]
GIẢI THÍCH: [1-2 dòng giải thích ngắn gọn, hài hước kiểu GenZ]"""

        try:
            temp_msgs = [
                {"role": "system", "content": "M là bot tạo quiz, k output thinking, chỉ output câu hỏi và đáp án theo format yêu cầu."},
                {"role": "user", "content": quiz_prompt}
            ]

            raw = await get_model_response(temp_msgs, MODELS_CONFIG[CURRENT_MODEL])
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
                await message.channel.send(f"Câu {q_num} lỗi format, skip nha 💀")
                continue

            q_data = {
                "q_num": q_num,
                "question": q_lines[0] if q_lines else "Câu hỏi",
                "options": q_lines[1:] if len(q_lines) > 1 else [],
                "answer": correct,
                "explanation": expl,
                "points": 5 if golden_hour_active else 2.5,
                "ans_map": ans_map,
                "answered": False
            }
            quiz_active[channel_id]["questions"].append(q_data)

            mode_emoji = {"team_vs_bot": "👥", "duel": "⚔️", "coop": "🤝"}
            embed = discord.Embed(
                title=f"{mode_emoji.get(mode, '⚔️')} SUMMON QUIZ - Câu {q_num}/3 | {mode.upper()}",
                description="\n".join(q_lines),
                color=0xFF6B35
            )
            embed.add_field(name="⏱️ Thời gian", value="`45s`", inline=True)
            embed.add_field(name="🏆 Điểm", value="`+5đ`", inline=True)
            embed.add_field(name="👥 Người chơi", value=f"<@{inviter_id}> vs <@{invited_id}>", inline=True)
            embed.set_footer(text=f"Trả lời A/B/C/D để chơi | {random_vibe()}")

            await message.channel.send(embed=embed)

            answered = False
            wait_start = asyncio.get_event_loop().time()
            while asyncio.get_event_loop().time() - wait_start < 47:
                await asyncio.sleep(1)
                q_list = quiz_active.get(channel_id, {}).get("questions", [])
                if len(q_list) >= q_num and q_list[q_num - 1].get("answered", False):
                    answered = True
                    break
                if not quiz_active.get(channel_id, {}).get("running"):
                    break

            if not answered:
                q_list = quiz_active.get(channel_id, {}).get("questions", [])
                if len(q_list) >= q_num:
                    q_list[q_num - 1]["answered"] = True
                    quiz_active[channel_id]["completed_questions"] = quiz_active[channel_id].get("completed_questions", 0) + 1
                    await message.channel.send(f"⏰ Hết giờ câu {q_num}! Đáp án đúng là **{correct}**. {expl} 🥀")

        except Exception as e:
            print(f"Lỗi tạo summon quiz câu {q_num}: {e}")
            await message.channel.send(f"Câu {q_num} lỗi rồi, skip nha 💀")
            continue

    await end_summon_quiz(channel_id, message)
    summon_active.pop(channel_id, None)


async def end_summon_quiz(channel_id, message):
    """Kết thúc summon quiz và tính điểm"""
    if channel_id not in quiz_active:
        return

    session = quiz_active[channel_id]
    session["running"] = False
    mode = session.get("mode", "team_vs_bot")
    inviter_id = session.get("inviter_id")
    invited_id = session.get("invited_id")
    scores = session.get("scores", {})

    embed = discord.Embed(
        title=f"🏁 KẾT THÚC SUMMON QUIZ | {mode.upper()}",
        description="Kết quả đây m ơi 🔥",
        color=0x00FF9D
    )

    if mode == "duel":
        inviter_score = scores.get(inviter_id, 0)
        invited_score = scores.get(invited_id, 0)

        if inviter_score > invited_score:
            winner, loser = inviter_id, invited_id
            diff = inviter_score - invited_score
        elif invited_score > inviter_score:
            winner, loser = invited_id, inviter_id
            diff = invited_score - inviter_score
        else:
            winner = None
            diff = 0

        if winner:
            winner_name = message.guild.get_member(int(winner)).display_name if message.guild else "Unknown"
            loser_name = message.guild.get_member(int(loser)).display_name if message.guild else "Unknown"
            embed.add_field(
                name="🎉 KẾT QUẢ",
                value=f"**{winner_name}** thắng **{loser_name}** với cách biệt `{diff} điểm`!",
                inline=False
            )
            event_stats[winner]["duels_won"] = event_stats[winner].get("duels_won", 0) + 1
            event_stats[loser]["duels_lost"] = event_stats[loser].get("duels_lost", 0) + 1
        else:
            embed.add_field(name="🤝 KẾT QUẢ", value="Hòa nhau! Cả 2 đều ngang tài ngang sức 💀", inline=False)

    elif mode == "coop":
        total_score = sum(scores.values())
        embed.add_field(
            name="🤝 TEAM SCORE",
            value=f"Tổng điểm team: `{total_score} điểm`!",
            inline=False
        )
        for uid in [inviter_id, invited_id]:
            if uid in scores:
                event_stats[uid]["quiz_points_event"] = event_stats[uid].get("quiz_points_event", 0) + scores[uid]

    else:
        total_score = sum(scores.values())
        if total_score >= 10:
            result = "🎉 TEAM THẮNG! Đánh bại bot thành công!"
        elif total_score >= 5:
            result = "😐 Cũng được, nhưng bot vẫn mạnh hơn"
        else:
            result = "💀 TEAM THUA! Bot quá bá đạo!"

        embed.add_field(name="👥 TEAM RESULT", value=f"{result}\nTổng điểm: `{total_score}`", inline=False)
        for uid in [inviter_id, invited_id]:
            if uid in scores:
                event_stats[uid]["quiz_points_event"] = event_stats[uid].get("quiz_points_event", 0) + scores[uid]

    score_lines = []
    for uid, score in scores.items():
        user = message.guild.get_member(int(uid)) if message.guild else None
        name = user.display_name if user else f"User_{uid[:6]}"
        score_lines.append(f"• **{name}**: `{score} điểm`")

    if score_lines:
        embed.add_field(name="📊 Cá nhân", value="\n".join(score_lines), inline=False)

    embed.set_footer(text=f"Summon Quiz | {random_vibe()}")
    await message.channel.send(embed=embed)

    quiz_active.pop(channel_id, None)

# === MAIN MESSAGE HANDLER (FIXED) ===
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

    # Init chat history nếu chưa có
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

    # Kiểm tra trigger
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

    # SUMMON ACCEPT CHECK (chỉ khi chưa cần respond)
    channel_id = str(message.channel.id)
    if channel_id in summon_active and summon_active[channel_id].get("active"):
        summon_data = summon_active[channel_id]
        if not summon_data.get("accepted"):
            invited_id = summon_data.get("invited_id")
            if str(message.author.id) == invited_id:
                content_lower = message.content.lower().strip()
                if content_lower in ['join', 'ok', 'yes', 'đồng ý', 'chơi', 'đi']:
                    summon_data["accepted"] = True
                    if summon_data.get("timeout_task"):
                        summon_data["timeout_task"].cancel()

                    await message.reply(
                        f"✅ **{message.author.display_name}** đã accept! Chuẩn bị quiz **{summon_data['mode']}** với **{summon_data['inviter_name']}** 🔥",
                        mention_author=False
                    )

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

                            if quiz_session["completed_questions"] >= quiz_session.get("total_q", 1):
                                await end_quiz_session(channel_id, message)
                            else:
                                await message.reply(f"✅ **ĐÚNG RỒI!** +{points} điểm! {current_q.get('explanation', '')} 🎉")
                        else:
                            current_q["answered"] = True
                            quiz_session["completed_questions"] = quiz_session.get("completed_questions", 0) + 1

                            if quiz_session["completed_questions"] >= quiz_session.get("total_q", 1):
                                await end_quiz_session(channel_id, message)
                            else:
                                await message.reply(f"❌ **SAI RỒI!** Đáp án đúng là **{current_q['answer']}**. {current_q.get('explanation', '')} 🥀")

                        return

    # Nếu không trigger, chỉ thêm vào history nếu sẽ phản hồi
    if not should_respond:
        return

    # Update cooldown check
    if BOT_UPDATED and not is_dm:
        if cooldown_start_time:
            elapsed = (datetime.datetime.now(pytz.timezone('Asia/Ho_Chi_Minh')) - cooldown_start_time).total_seconds()
            remaining = max(0, UPDATE_COOLDOWN_SECONDS - int(elapsed))
        else:
            remaining = UPDATE_COOLDOWN_SECONDS
        await message.reply(f"⏳ Bot vừa update xong, đang ổn định lại. Còn khoảng **{remaining}s** nữa, đợi t tí m 🥀", mention_author=False)
        return

    # Process reply
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
                    is_dockerfile = filename.endswith('dockerfile') or 'dockerfile' in filename

                    if MODELS_CONFIG[CURRENT_MODEL]["vision"] and att.content_type and att.content_type.startswith('image/'):
                        try:
                            img_data = await att.read()
                            img_base64 = base64.b64encode(img_data).decode('utf-8')
                            img_url = f"data:{att.content_type};base64,{img_base64}"
                            user_msg_content.append({"type": "image_url", "image_url": {"url": img_url}})
                        except Exception as img_e:
                            print(f"Lỗi đọc ảnh: {img_e}")

                    elif ext in TEXT_EXTENSIONS or is_dockerfile or att.content_type in ['text/plain', 'text/x-python', 'text/html', 'text/css', 'application/json', 'text/javascript', 'application/javascript']:
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