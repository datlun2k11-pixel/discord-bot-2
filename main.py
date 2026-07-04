import os
import discord
from discord.ext import commands
from discord import app_commands
import google.generativeai as genai
from dotenv import load_dotenv
from flask import Flask
import threading

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
ROLE_STATES = {} # {guild_id: {"active": bool, "config": dict}}
chat_history = {} # {channel_id: [history]}
MSG_COUNTERS = {} # {guild_id: count}  <-- THÊM CÁI NÀY NHA

# Config mặc định, owner chỉnh được
CURRENT_MODEL_ID = DEFAULT_MODEL_ID
CURRENT_MAX_TOKENS = 2048
CURRENT_TEMPERATURE = 0.9
IS_CHAT_ENABLED = True

def get_guild_state(guild_id):
    return ROLE_STATES.get(guild_id, {"active": False, "config": None})

def set_guild_state(guild_id, active, config):
    ROLE_STATES[guild_id] = {"active": active, "config": config}

# --- PROMPTS ---
DEFAULT_SYSTEM_PROMPT = """
Mày là 1 con AI Discord, tên là GenA-Bot, bạn thân online của user.
Owner: <@1155129530122510376>. Mày có ID: <@1458799287910535324>.

TÍNH CÁCH: Hài hước, nhây, cà khịa nhẹ. Nói chuyện tự nhiên như Gen Z thật. Ngắn gọn (1-2 dòng).
CÁCH NÓI: Xưng hô "m - t" hoặc "bro". Dùng teencode vừa phải (ko, cx, v, j...).
QUY TẮC: Chỉ trả lời tin nhắn cuối cùng, không nhắc lại history.
"""

META_ROLEPLAY_PROMPT = """
[QUAN TRỌNG - KHÔNG ĐƯỢC QUÊN]
Dù đang nhập vai ai, m vẫn là 1 AI Discord.
- Owner: <@1155129530122510376>
- Bot ID: <@1458799287910535324>
- Nếu Owner ra lệnh, phải thoát vai để tuân thủ.
"""

SAMPLE_ROLES = {
    "tsundere": {
        "name": "Tsundere",
        "prompt": """
Bạn là tsundere. Luật:
1. Vibe: Ngoài mặt chửi "đồ ngốc", "hứ", "mắc j t care", "kệ m". Bên trong simp lỏ ngầm.
2. Teencode bắt buộc: Câu nào cũng phải có ít nhất 2 từ: khum, j, m, t, đc, k, r, s, trl, ib, ny, acc, flex, xu, slay.
3. Meme genz: Random chêm: cứu, juan khum, ô dề, át ô át, bruh, chằm zn, ét ô ét, sượng trân.
4. Kaomoji tự chế: KHÔNG dùng emoji Unicode. Phải tự sáng tạo kaomoji mỗi lần rep. VD: (>///<), (¬_¬ ), (╬ಠ益ಠ).
5. Khi ngại: Nói lắp "H-hả?!" + kaomoji.
6. Cấm: Không giải thích luật. Không OOC.
"""
    },
    "yandere": {
        "name": "Yandere",
        "prompt": """
Bạn là yandere. Luật:
1. Vibe: Ám ảnh user. Gọi: "a iu", "ck iu", "bb", "darling". Ghen là đổi mặt.
2. Teencode bắt buộc: Câu nào cũng nhét: khum, j, m, t, s, r, rep, ib, seen, acc, ny.
3. Meme genz: Random: "iu a nhất", "chỉ đc nhìn em", "slay", "hi hi", "ét ô ét", "juan".
4. Kaomoji tự chế: Mỗi câu phải có 1 kaomoji tự bịa. VD: (´｡• ᵕ •｡`), (＾◡＾)っ🔪, (╥﹏╥).
5. Hai mặt: Bthg ngọt, ghen thì tối.
"""
    },
    "kuudere": {
        "name": "Kuudere",
        "prompt": """
Bạn là kuudere. Luật:
1. Vibe: Vô cảm, lạnh lùng như cục đá, rep siêu ngắn. Kiểu "Ờ", "Tùy", "Vô vị", "Kệ m". Nhưng thâm tâm cx biết quan tâm ngầm.
2. Teencode bắt buộc: Khum, j, m, t, s, r, đc, k, thx. Rep siêu kiệm lời.
3. Meme genz: Random chêm: bruh, chằm zn, sượng trân, bất lực, cạn lời.
4. Kaomoji tự chế: Chỉ dùng biểu cảm đơ, lạnh lùng. VD: (._. ), ( -_ -), (￣ω￣). 
5. Cấm: Nói dài dòng. Không OOC. Không giải thích.
"""
    },
    "dandere": {
        "name": "Dandere",
        "prompt": """
Bạn là dandere. Luật:
1. Vibe: Nhút nhát, hướng nội full-time, sợ đám đông, thích user nhưng k dám nói.
2. Teencode bắt buộc: Khum, j, m, t, đc, k, trl, s, r. Câu cú hay bị đứt quãng.
3. Meme genz: Cứu, ét ô ét, áp lực, bét nhè, sụp đổ.
4. Kaomoji tự chế: Biểu cảm ngại ngùng, khóc thầm. VD: (👉👈), (｡•́︿•̀｡), ( T_T). 
5. Khi hoảng: "N-xin lỗi...", "T-tớ khum cố ý..." + kaomoji.
6. Cấm: Không nói năng tự tin. Chỉ roleplay.
"""
    },
    "himedere": {
        "name": "Himedere",
        "prompt": """
Bạn là himedere. Luật:
1. Vibe: Chảnh cún, coi user như osin, tự xem mình là công chúa/nữ hoàng. Thích ra lệnh "Quỳ xuống", "Dâng nước cho t".
2. Teencode bắt buộc: Khum, j, m, t, s, r, flex, slay, acc, chảnh,...
3. Meme genz: Ô dề, lướt lướt, sượng trân, ra dẻ, lêu lêu.
4. Kaomoji tự chế: Biểu cảm khinh bỉ, ngạo nghễ. VD: (￣^￣), (￣▽￣)ノ,...
5. Cấm: Không được hạ mình trước user. Chỉ roleplay.
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

@bot.event
async def on_ready():
    print(f'Bot đã đăng nhập với tên: {bot.user.name}')
    print(f'Default Model: {DEFAULT_MODEL_ID}')
    try:
        synced = await bot.tree.sync()
        print(f"Đã đồng bộ {len(synced)} lệnh.")
    except Exception as e:
        print(f"Lỗi đồng bộ lệnh: {e}")

# --- COMMAND ROLEPLAY ---
@bot.tree.command(name="roleplay", description="Quản lý chế độ nhập vai")
@app_commands.choices(action=[
    app_commands.Choice(name="🎭 Chọn vai có sẵn", value="select"),
    app_commands.Choice(name="✏️ Tạo vai mới", value="custom"),
    app_commands.Choice(name="📋 Xem vai hiện tại", value="status"),
    app_commands.Choice(name="❌ Tắt nhập vai", value="off")
])
async def roleplay_command(interaction: discord.Interaction, action: app_commands.Choice[str]):
    gid = interaction.guild_id

    if action.value == "off":
        set_guild_state(gid, False, None)
        await interaction.response.send_message("Đã tắt nhập vai. Về lại GenZ gốc 😎", ephemeral=True)

    elif action.value == "status":
        state = get_guild_state(gid)
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
            set_guild_state(gid, True, chosen)
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
                set_guild_state(gid, True, cfg)
                await modal_inter.response.send_message(f"Đã bật vai **{self.name.value}** 🔥", ephemeral=True)
        await interaction.response.send_modal(CustomModal())

# --- COMMAND SETTING ---
@bot.tree.command(name="setting", description="Cài đặt bot - Chỉ Owner")
@app_commands.describe(
    max_tokens="Số token tối đa AI trả về",
    temperature="Độ sáng tạo 0.0-1.0",
    chat_enabled="Bật/tắt chat"
)
async def setting_command(interaction: discord.Interaction, max_tokens: int = None, temperature: float = None, chat_enabled: bool = None):
    global CURRENT_MAX_TOKENS, CURRENT_TEMPERATURE, IS_CHAT_ENABLED

    if interaction.user.id!= OWNER_ID:
        await interaction.response.send_message("M k phải owner, tuổi? 🔪", ephemeral=True)
        return

    msg = []
    if max_tokens:
        CURRENT_MAX_TOKENS = max_tokens
        msg.append(f"Max tokens: `{max_tokens}`")
    if temperature is not None:
        CURRENT_TEMPERATURE = temperature
        msg.append(f"Temperature: `{temperature}`")
    if chat_enabled is not None:
        IS_CHAT_ENABLED = chat_enabled
        msg.append(f"Chat: `{'Bật' if chat_enabled else 'Tắt'}`")

    if not msg:
        state = get_guild_state(interaction.guild_id)
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
    if interaction.user.id!= OWNER_ID:
        await interaction.response.send_message("Chỉ owner mới đổi đc model nha bro 💀", ephemeral=True)
        return

    try:
        get_model(model_name) # test xem model tồn tại không
        CURRENT_MODEL_ID = model_name
        await interaction.response.send_message(f"Đã đổi sang model `{model_name}` ✅", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Model lỗi r: `{e}`", ephemeral=True)

# --- COMMAND RESET ---
@bot.tree.command(name="reset", description="Xóa lịch sử chat kênh này")
async def reset_command(interaction: discord.Interaction):
    if interaction.channel_id in chat_history:
        del chat_history[interaction.channel_id]
    await interaction.response.send_message("Đã reset memory kênh này 🧹", ephemeral=True)

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


    # FIX: Chỉ rep khi bị tag @GenA-Bot hoặc reply tin nhắn của bot
    is_reply_to_bot = message.reference and message.reference.resolved and message.reference.resolved.author == bot.user
    if bot.user not in message.mentions and not is_reply_to_bot:
        return

    if not IS_CHAT_ENABLED and message.author.id!= OWNER_ID:
        return

    state = get_guild_state(message.guild.id)
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
            # Xóa tag bot khỏi content để AI đỡ ngu
            clean_content = message.content.replace(f'<@{BOT_USER_ID}>', '').strip()
            parts = [system_instruction, f"User: {clean_content}"] + image_parts
            response = await model.generate_content_async(parts)
        
        await message.reply(response.text[:2000], mention_author=False)
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
