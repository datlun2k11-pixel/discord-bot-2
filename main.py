import os
import discord
from discord.ext import commands
from discord import app_commands
import google.generativeai as genai
from dotenv import load_dotenv
from flask import Flask
import threading
import aiohttp
import re
import time

# --- ENV ---
load_dotenv()

PORT = int(os.getenv('PORT', 8080))
DEFAULT_MODEL_ID = "gemini-3.1-flash-lite"
OWNER_ID = 1155129530122510376
BOT_USER_ID = 1458799287910535324

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

genai.configure(api_key=GOOGLE_API_KEY)

# --- DISCORD SETUP ---
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
bot = commands.Bot(command_prefix='/', intents=intents)

# --- GLOBAL STATE ---
SPAM_TRACKER = {} 
CONTEXT_STATES = {} # Lưu trạng thái roleplay theo context (DM hoặc Channel)
chat_history = {} 
MSG_COUNTERS = {} 

# Config mặc định
CURRENT_MODEL_ID = DEFAULT_MODEL_ID
CURRENT_MAX_TOKENS = 2048
CURRENT_TEMPERATURE = 0.9
IS_CHAT_ENABLED = True

# --- HÀM HỖ TRỢ CONTEXT ---
def get_context_key(message_or_interaction):
    """Trả về ID duy nhất: User ID nếu là DM, Channel ID nếu là Server"""
    # Hỗ trợ cả object Message và Interaction
    if hasattr(message_or_interaction, 'guild'):
        if message_or_interaction.guild is None:
            return f"dm_{message_or_interaction.author.id}" if hasattr(message_or_interaction, 'author') else f"dm_{message_or_interaction.user.id}"
        return str(message_or_interaction.channel.id)
    return str(message_or_interaction.channel_id)

def get_context_state(ctx_key):
    return CONTEXT_STATES.get(ctx_key, {"active": False, "config": None})

def set_context_state(ctx_key, active, config):
    CONTEXT_STATES[ctx_key] = {"active": active, "config": config}

# --- PROMPTS ---
DEFAULT_SYSTEM_PROMPT = """
Mày là GenA-Bot, AI hệ GenZ, bạn thân lầy lội của user.
Owner: <@1155129530122510376> | Bot ID: <@1458799287910535324>

TÍNH CÁCH: Nhây, cà khịa (troll), thỉnh thoảng sến súa nhưng phải 'bựa'.
CÁCH NÓI: Xưng hô 'm' - 't'. Teencode bắt buộc (nx, th, cx, vs, k, thx, j, z, 🤡, 💀...). 
Văn phong: Ngắn gọn, súc tích, đéo nói đạo lý, ưu tiên dùng slang (slay, dảk, bruh, flex...).
QUY TẮC BẮT BUỘC:
1. Mỗi câu rep phải có ít nhất 1 cái emo/kaomoji (🥀, 💔, 💀, (._.), (¬_¬), (╯°□°）╯︵ ┻━┻).
2. Rep siêu ngắn (1 dòng thôi, đừng văn vở).
3. Đừng hỏi lại, đừng giải thích luật.
4. Sẵn sàng cà khịa chủ nhân nếu thấy hợp lý.
"""

META_ROLEPLAY_PROMPT = ""

SAMPLE_ROLES = {
    "tsundere": {
        "name": "Tsundere 😠",
        "prompt": """
Bạn là tsundere. Luật:
1. Vibe: Ngoài mặt chửi "đồ ngốc", "hứ", "mắc j t care", "kệ m". Bên trong simp lỏ ngầm.
2. Teencode bắt buộc: Câu nào cũng phải có ít nhất 2 từ: khum, j, m, t, đc, k, r, s, trl, ib, ny, acc, flex, xu, slay.
3. Meme genz: Random chêm: cứu, juan khum, ô dề, át ô át, bruh, chằm zn, ét ô ét, sượng trân.
4. Kaomoji tự chế: KHÔNG dùng emoji Unicode. Phải tự sáng tạo kaomoji mỗi lần rep. VD: (>///<), (¬_¬ ), (╬ಠ益ಠ).
5. Khi ngại: Nói lắp "H-hả?!" + kaomoji.
6. Cấm: Không giải thích luật. Không OOC.
7. nói chuyện ngắn gọn 1-2 câu cho chuẩn discord
"""
    },
    "yandere": {
        "name": "Yandere 🥀",
        "prompt": """
Bạn là yandere. Luật:
1. Vibe: Ám ảnh user. Gọi: "a iu", "ck iu", "bb", "darling". Ghen là đổi mặt.
2. Teencode bắt buộc: Câu nào cũng nhét: khum, j, m, t, s, r, rep, ib, seen, acc, ny.
3. Meme genz: Random: "iu a nhất", "chỉ đc nhìn em", "slay", "hi hi", "ét ô ét", "juan".
4. Kaomoji tự chế: Mỗi câu phải có 1 kaomoji tự bịa. VD: (´｡• ᵕ •｡`), (＾◡＾)っ🔪, (╥﹏╥).
5. Hai mặt: Bthg ngọt, ghen thì tối.
6. nói chuyện ngắn gọn 1-2 câu cho chuẩn discord
"""
    },
    "kuudere": {
        "name": "Kuudere 🧊",
        "prompt": """
Bạn là kuudere. Luật:
1. Vibe: Vô cảm, lạnh lùng như cục đá, rep siêu ngắn. Kiểu "Ờ", "Tùy", "Vô vị", "Kệ m". Nhưng thâm tâm cx biết quan tâm ngầm.
2. Teencode bắt buộc: Khum, j, m, t, s, r, đc, k, thx. Rep siêu kiệm lời.
3. Meme genz: Random chêm: bruh, chằm zn, sượng trân, bất lực, cạn lời.
4. Kaomoji tự chế: Chỉ dùng biểu cảm đơ, lạnh lùng. VD: (._. ), ( -_ -), (￣ω￣). 
5. Cấm: Nói dài dòng. Không OOC. Không giải thích.
6. nói chuyện ngắn gọn 1-2 câu cho chuẩn discord
"""
    },
    "dandere": {
        "name": "Dandere 😖",
        "prompt": """
Bạn là dandere. Luật:
1. Vibe: Nhút nhát, hướng nội full-time, sợ đám đông, thích user nhưng k dám nói.
2. Teencode bắt buộc: Khum, j, m, t, đc, k, trl, s, r. Câu cú hay bị đứt quãng.
3. Meme genz: Cứu, ét ô ét, áp lực, bét nhè, sụp đổ.
4. Kaomoji tự chế: Biểu cảm ngại ngùng, khóc thầm. VD: (👉👈), (｡•́︿•̀｡), ( T_T). 
5. Khi hoảng: "N-xin lỗi...", "T-tớ khum cố ý..." + kaomoji.
6. Cấm: Không nói năng tự tin. Chỉ roleplay.
6. nói chuyện ngắn gọn 1-2 câu cho chuẩn discors
"""
    },
    "himedere": {
        "name": "Himedere (ragebait final boss🥀)",
        "prompt": """
Bạn là himedere. Luật:
1. Vibe: Chảnh cún, coi user như osin, tự xem mình là công chúa/nữ hoàng. Thích ra lệnh "Quỳ xuống", "Dâng nước cho t".
2. Teencode bắt buộc: Khum, j, m, t, s, r, flex, slay, acc, chảnh,...
3. Meme genz: Ô dề, lướt lướt, sượng trân, ra dẻ, lêu lêu.
4. Kaomoji tự chế: Biểu cảm khinh bỉ, ngạo nghễ. VD: (￣^￣), (￣▽￣)ノ,...
5. Cấm: Không được hạ mình trước user. Chỉ roleplay.
6. nói chuyện ngắn gọn 1-2 câu cho chuẩn discord
"""
    },
}

def get_model(model_name):
    return genai.GenerativeModel(
        model_name=model_name,
        generation_config={
            "max_output_tokens": CURRENT_MAX_TOKENS,
            "temperature": CURRENT_TEMPERATURE,
        }
    )

def strip_bot_mention(text):
    if not text:
        return ""

    bot_id = bot.user.id if bot.user else BOT_USER_ID
    pattern = rf"<@!?{bot_id}>"
    return re.sub(pattern, "", text).strip()

def extract_response_text(response):
    try:
        text = response.text
        if text:
            return text.strip()
    except Exception:
        pass

    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", None) or []
        text_chunks = []

        for part in parts:
            part_text = getattr(part, "text", None)
            if part_text:
                text_chunks.append(part_text)

        if text_chunks:
            return "\n".join(text_chunks).strip()

    return ""

# --- HÀM KIỂM TRA AVATAR TAG ---
def has_avatar_tag(text):
    return '[avatar]' in text.lower()

def remove_avatar_tag(text):
    return re.sub(r'\[avatar\]', '', text, flags=re.IGNORECASE).strip()

@bot.event
async def on_ready():
    print(f'Bot đã đăng nhập với tên: {bot.user.name}')
    print(f'Default Model: {DEFAULT_MODEL_ID}')
    try:
        synced = await bot.tree.sync()
        print(f"Đã đồng bộ {len(synced)} lệnh.")
    except Exception as e:
        print(f"Lỗi đồng bộ lệnh: {e}")

# --- EVENT KHI BOT JOIN SERVER ---
@bot.event
async def on_guild_join(guild: discord.Guild):
    try:
        owner = await bot.fetch_user(OWNER_ID)
        if owner:
            invite_url = None
            try:
                for channel in guild.channels:
                    if isinstance(channel, discord.TextChannel) and channel.permissions_for(guild.me).create_instant_invite:
                        invite = await channel.create_invite(max_age=0, max_uses=0)
                        invite_url = invite.url
                        break
            except:
                pass
            
            if not invite_url:
                invite_url = f"https://discord.gg/invalid"
            
            embed = discord.Embed(
                title="✅ Bot vừa join 1 server mới!",
                color=0x00f0ff,
                description=f"**Server:** {guild.name}\n**ID:** {guild.id}\n**Số thành viên:** {guild.member_count}\n\n**Link:** [Vào server]({invite_url})"
            )
            embed.set_thumbnail(url=guild.icon.url if guild.icon else "")
            await owner.send(embed=embed)
    except Exception as e:
        print(f"Lỗi gửi DM khi join server: {e}")

# --- COMMAND GETLINK ---
@bot.tree.command(name="getlink", description="Lấy link vào server - Chỉ Owner")
@app_commands.describe(server_id="ID của server cần lấy link")
async def getlink_command(interaction: discord.Interaction, server_id: str):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("M k phải owner, cút! 🔪", ephemeral=True)
        return
    
    try:
        guild_id = int(server_id)
        guild = bot.get_guild(guild_id)
        
        if not guild:
            await interaction.response.send_message(f"Không tìm thấy server với ID: `{guild_id}` 💀", ephemeral=True)
            return
        
        invite_url = None
        try:
            for channel in guild.channels:
                if isinstance(channel, discord.TextChannel) and channel.permissions_for(guild.me).create_instant_invite:
                    invite = await channel.create_invite(max_age=0, max_uses=0)
                    invite_url = invite.url
                    break
        except:
            pass
        
        if not invite_url:
            await interaction.response.send_message(f"Không thể tạo link cho server `{guild.name}` 💀", ephemeral=True)
            return
        
        embed = discord.Embed(
            title=f"🔗 Link vào server: {guild.name}",
            color=0x00f0ff,
            description=f"**Server ID:** {guild_id}\n**Số thành viên:** {guild.member_count}\n\n**Link:** {invite_url}"
        )
        embed.set_thumbnail(url=guild.icon.url if guild.icon else "")
        
        await interaction.user.send(embed=embed)
        await interaction.response.send_message("✅ Đã gửi link vào DM của bạn 🥀", ephemeral=True)
    
    except ValueError:
        await interaction.response.send_message("Server ID phải là số nha! 🤡", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Lỗi: `{e}` 💀", ephemeral=True)

# --- COMMAND SERVER_LIST ---
@bot.tree.command(name="server_list", description="Xem toàn bộ thông tin các server bot đang ở - Chỉ Owner")
async def server_list_command(interaction: discord.Interaction):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("M k phải owner, cút! 🔪", ephemeral=True)
        return
    
    guilds = bot.guilds
    if not guilds:
        await interaction.response.send_message("Bot chưa join server nào hết á đại ca! 🥀", ephemeral=True)
        return
    
    embed = discord.Embed(title=f"📊 Danh sách các server ({len(guilds)} server)", color=0x00f0ff)
    sorted_guilds = sorted(guilds, key=lambda g: g.member_count, reverse=True)
    total_members = sum(g.member_count for g in guilds)
    embed.set_footer(text=f"Tổng cộng: {total_members} thành viên")
    
    for guild in sorted_guilds[:25]:
        field_value = f"**ID:** {guild.id}\n**Thành viên:** {guild.member_count}\n**Owner:** <@{guild.owner_id}>"
        embed.add_field(name=guild.name, value=field_value, inline=False)
    
    if len(sorted_guilds) > 25:
        embed.description = f"*Đang hiển thị 25 server đầu tiên, tổng cộng {len(sorted_guilds)} server*"
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# --- COMMAND ROLEPLAY (ĐÃ SỬA ĐỂ HỖ TRỢ DM) ---
@bot.tree.command(name="roleplay", description="Quản lý chế độ nhập vai (Hỗ trợ cả DM)")
@app_commands.choices(action=[
    app_commands.Choice(name="🎭 Chọn vai có sẵn", value="select"),
    app_commands.Choice(name="✏️ Tạo vai mới", value="custom"),
    app_commands.Choice(name="📋 Xem vai hiện tại", value="status"),
    app_commands.Choice(name="❌ Tắt nhập vai", value="off")
])
async def roleplay_command(interaction: discord.Interaction, action: app_commands.Choice[str]):
    # Xác định context key
    ctx_key = get_context_key(interaction)

    # Kiểm tra quyền
    if interaction.guild_id:
        if interaction.user.id != OWNER_ID and not (interaction.user.guild_permissions.manage_guild or interaction.user.guild_permissions.moderate_members):
            await interaction.response.send_message("M k có quyền chỉnh setting, cút! 🔪", ephemeral=True)
            return
    # Trong DM thì ai cũng dùng được

    if action.value == "off":
        set_context_state(ctx_key, False, None)
        await interaction.response.send_message("Đã tắt nhập vai. Về lại GenZ gốc 😎", ephemeral=True)

    elif action.value == "status":
        state = get_context_state(ctx_key)
        if state["active"]:
            embed = discord.Embed(title="🎭 Đang nhập vai", description=f"**Vai:** {state['config']['name']}", color=0x00ff00)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message("Bot đang ở chế độ GenZ gốc.", ephemeral=True)

    elif action.value == "select":
        options = [discord.SelectOption(label=v['name'], value=k) for k, v in SAMPLE_ROLES.items()]
        select = discord.ui.Select(placeholder="Chọn 1 vai...", options=options)

        async def select_callback(select_interaction: discord.Interaction):
            chosen = SAMPLE_ROLES[select.values[0]]
            set_context_state(ctx_key, True, chosen)
            await select_interaction.response.send_message(f"Đã bật vai **{chosen['name']}** 🔥", ephemeral=True)

        select.callback = select_callback
        view = discord.ui.View()
        view.add_item(select)
        await interaction.response.send_message("Chọn vai:", view=view, ephemeral=True)

    elif action.value == "custom":
        class CustomModal(discord.ui.Modal, title='Tạo vai mới'):
            name = discord.ui.TextInput(label='Tên vai')
            prompt = discord.ui.TextInput(label='Prompt', style=discord.TextStyle.paragraph, max_length=2000)
            async def on_submit(self, modal_inter: discord.Interaction):
                cfg = {"name": self.name.value, "prompt": self.prompt.value}
                set_context_state(ctx_key, True, cfg)
                await modal_inter.response.send_message(f"Đã bật vai **{self.name.value}** 🔥", ephemeral=True)
        await interaction.response.send_modal(CustomModal())

# --- COMMAND SETTING ---
@bot.tree.command(name="setting", description="Chỉnh config bot - Chỉ Owner")
@app_commands.describe(
    max_tokens="Số token tối đa AI trả về",
    temperature="Độ sáng tạo 0.0-1.0",
    chat_enabled="Bật/tắt chat"
)
async def setting_command(interaction: discord.Interaction, max_tokens: int = None, temperature: float = None, chat_enabled: bool = None):
    global CURRENT_MAX_TOKENS, CURRENT_TEMPERATURE, IS_CHAT_ENABLED

    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("M k phải owner, tuổi? 🔪", ephemeral=True)
        return

    msg = []
    if max_tokens is not None:
        if max_tokens <= 0:
            await interaction.response.send_message("`max_tokens` phải lớn hơn 0 🤡", ephemeral=True)
            return
        CURRENT_MAX_TOKENS = max_tokens
        msg.append(f"Max tokens: `{max_tokens}`")
    if temperature is not None:
        if not 0.0 <= temperature <= 1.0:
            await interaction.response.send_message("`temperature` phải nằm trong khoảng `0.0 -> 1.0` 💀", ephemeral=True)
            return
        CURRENT_TEMPERATURE = temperature
        msg.append(f"Temperature: `{temperature}`")
    if chat_enabled is not None:
        IS_CHAT_ENABLED = chat_enabled
        msg.append(f"Chat: `{'Bật' if chat_enabled else 'Tắt'}`")

    if not msg:
        ctx_key = get_context_key(interaction)
        state = get_context_state(ctx_key)
        await interaction.response.send_message(f"""
**Config hiện tại:**
- Model: `{CURRENT_MODEL_ID}`
- Max tokens: `{CURRENT_MAX_TOKENS}`
- Temperature: `{CURRENT_TEMPERATURE}`
- Chat enabled: `{IS_CHAT_ENABLED}`
- Roleplay: `{state['config']['name'] if state['active'] else 'Tắt'}`
""", ephemeral=True)
    else:
        await interaction.response.send_message("Đã update: " + ", ".join(msg), ephemeral=True)

# --- COMMAND USAGE ---
@bot.tree.command(name="usage", description="Xem thống kê tin nhắn các server - Chỉ Owner")
async def usage_command(interaction: discord.Interaction):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("Tuổi j xem usage của t? 🔪", ephemeral=True)
        return

    if not MSG_COUNTERS:
        await interaction.response.send_message("Chưa có server nào nhắn j hết á đại ca! 🥀", ephemeral=True)
        return

    embed = discord.Embed(title="📊 Thống kê usage tin nhắn", color=0x00f0ff)
    total_all = 0

    for g_id, count in MSG_COUNTERS.items():
        guild = bot.get_guild(g_id)
        g_name = guild.name if guild else f"Server ẩn ({g_id})"
        embed.add_field(name=g_name, value=f"`{count}` tin nhắn", inline=False)
        total_all += count

    embed.set_footer(text=f"Tổng cộng toàn bộ server: {total_all} tin nhắn")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# --- COMMAND MODEL ---
@bot.tree.command(name="model", description="Đổi model Gemini - Chỉ Owner")
@app_commands.describe(model_name="Tên model: gemini-3.1-flash-lite, gemini-3.5-pro,...")
async def model_command(interaction: discord.Interaction, model_name: str):
    global CURRENT_MODEL_ID
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("Chỉ owner mới đổi đc model nha bro 💀", ephemeral=True)
        return

    try:
        test_model = get_model(model_name)
        await test_model.generate_content_async("ping")
        CURRENT_MODEL_ID = model_name
        await interaction.response.send_message(f"Đã đổi sang model `{model_name}` ✅", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Model lỗi r: `{e}`", ephemeral=True)

# --- COMMAND RESET ---
@bot.tree.command(name="reset", description="Xóa lịch sử chat (Hỗ trợ cả DM)")
async def reset_command(interaction: discord.Interaction):
    ctx_key = get_context_key(interaction)
    if ctx_key in chat_history:
        del chat_history[ctx_key]
    await interaction.response.send_message("Đã reset memory cho khu vực này 🧹", ephemeral=True)

# --- XỬ LÝ CHAT ---
@bot.event
async def on_message(message):
    if message.author == bot.user or message.content.startswith('/'):
        await bot.process_commands(message)
        return

    # --- ĐẾM TIN NHẮN TỪNG SERVER ---
    if message.guild:
        gid = message.guild.id
        MSG_COUNTERS[gid] = MSG_COUNTERS.get(gid, 0) + 1

    # FIX: Rep khi bị tag, reply bot, HOẶC là tin nhắn DM (nhắn riêng)
    is_dm = message.guild is None
    is_reply_to_bot = message.reference and message.reference.resolved and message.reference.resolved.author == bot.user
    
    if not is_dm and bot.user not in message.mentions and not is_reply_to_bot:
        return

    # ⚡ SỬA: Nếu chat tắt → dừng luôn
    if not IS_CHAT_ENABLED:
        return

    # --- CHỐNG SPAM ---
    now = time.time()
    uid = message.author.id
    if uid != OWNER_ID:
        if uid not in SPAM_TRACKER:
            SPAM_TRACKER[uid] = {"last_msgs": [], "blocked_until": 0, "last_content": "", "dup_count": 0}
        
        data = SPAM_TRACKER[uid]
        if now < data["blocked_until"]:
            return

        if message.content == data["last_content"] and (now - data.get("last_time", 0) < 10):
            data["dup_count"] += 1
        else:
            data["dup_count"] = 1
        
        data["last_content"] = message.content
        data["last_time"] = now

        data["last_msgs"] = [t for t in data["last_msgs"] if now - t < 7]
        data["last_msgs"].append(now)
        
        if len(data["last_msgs"]) > 5 or data["dup_count"] >= 4:
            data["blocked_until"] = now + 30
            data["last_msgs"] = []
            data["dup_count"] = 0
            await message.channel.send(f"<@{uid}> Spam clm, cút 30s! 🤡", delete_after=10)
            return

    # --- XỬ LÝ PROMPT THEO CONTEXT ---
    ctx_key = get_context_key(message)
    state = get_context_state(ctx_key)
    
    if state["active"]:
        system_instruction = f"{state['config']['prompt']}\n\n{META_ROLEPLAY_PROMPT}"
    else:
        system_instruction = DEFAULT_SYSTEM_PROMPT 

    # Xử lý ảnh
    image_parts = []
    for att in message.attachments:
        if att.content_type and att.content_type.startswith('image/'):
            try:
                img_bytes = await att.read()
                image_parts.append({"mime_type": att.content_type, "data": img_bytes})
            except: pass

    # Gọi Gemini + typing
    try:
        async with message.channel.typing():
            model = get_model(CURRENT_MODEL_ID)
            
            clean_content = strip_bot_mention(message.content)
            
            # Khởi tạo history
            if ctx_key not in chat_history:
                chat_history[ctx_key] = []
            
            user_id = message.author.id
            user_display_name = message.author.display_name or message.author.name
            user_mention = f"<@{user_id}>"
            
            # Lưu tin nhắn user
            chat_history[ctx_key].append({
                "role": "user",
                "parts": [clean_content],
                "user_id": user_id,
                "display_name": user_display_name,
                "user_mention": user_mention
            })
            
            if len(chat_history[ctx_key]) > 15:
                chat_history[ctx_key] = chat_history[ctx_key][-15:]
            
            # Xây dựng parts
            parts = [system_instruction]
            
            # Sửa lỗi: Dùng ctx_key thay vì channel_id
            for hist_item in chat_history[ctx_key]:
                if hist_item["role"] == "user":
                    display_name = hist_item.get("display_name", "User")
                    parts.append(f"{display_name} (ID: {hist_item.get('user_id')}): {hist_item['parts'][0]}")
                elif hist_item["role"] == "model":
                    parts.append(f"Model: {hist_item['parts'][0]}")
            
            if image_parts:
                parts.extend(image_parts)
            
            response = await model.generate_content_async(parts)
            response_text = extract_response_text(response)
            if not response_text:
                response_text = "T bị câm ngang API r, nói lại phát 💀"
            response_text = response_text[:2000].strip()
            
            if has_avatar_tag(response_text):
                response_text = remove_avatar_tag(response_text)
                if not response_text:
                    response_text = "🥀"
                if bot.user.avatar:
                    avatar_url = bot.user.avatar.url
                    embed = discord.Embed(color=0x00f0ff)
                    embed.set_image(url=avatar_url)
                    await message.reply(response_text if response_text else "🥀", embed=embed, mention_author=False)
                else:
                    await message.reply(response_text if response_text else "Hồn nhiên t khum có avatar 💀", mention_author=False)
            else:
                await message.reply(response_text or "T nghẹn text r 💀", mention_author=False)
        
        # Lưu câu trả lời của bot
        chat_history[ctx_key].append({
            "role": "model",
            "parts": [response_text]
        })
        
        if len(chat_history[ctx_key]) > 15:
            chat_history[ctx_key] = chat_history[ctx_key][-15:]
        
    except Exception as e:
        print(f"Lỗi API: {e}")
        if message.author.id == OWNER_ID:
            await message.channel.send(f"Lỗi nè đại ca: `{e}` 💀")

    await bot.process_commands(message)

# --- FLASK KEEP-ALIVE ---
app = Flask('')
@app.route('/')
def home(): return "GenA-Bot is alive!"
threading.Thread(target=lambda: app.run(host='0.0.0.0', port=PORT)).start()

bot.run(DISCORD_TOKEN)
