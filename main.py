import discord, random, os, urllib.parse, base64, aiohttp, asyncio
from discord.ext import commands
from discord import app_commands
from openai import OpenAI  # Đổi từ Groq sang OpenAI client
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

load_dotenv()

# --- Setup SiliconFlow Client ---
client = OpenAI(
    api_key=os.getenv("SILICONFLOW_API_KEY"),  # Đổi env var nha m
    base_url="https://api.siliconflow.com/v1"
)

# --- Model Config SiliconFlow ---
MODELS_CONFIG = {
    # Cũ (giữ lại)
    "DeepSeek-V3": {"id": "deepseek-ai/DeepSeek-V3", "vision": False},
    "DeepSeek-R1": {"id": "deepseek-ai/DeepSeek-R1", "vision": False},
    "DeepSeek-VL2": {"id": "deepseek-ai/deepseek-vl2", "vision": True},
    "Qwen2.5-VL": {"id": "Qwen/Qwen2.5-VL-32B-Instruct", "vision": True},
    "Kimi-K2": {"id": "moonshotai/kimi-k2-instruct-0905", "vision": False},
    
    # Mới thêm 🚀
    "Kimi-Dev": {"id": "moonshotai/kimi-dev-72b", "vision": False},  # Code pro
    "Qwen3": {"id": "Qwen/Qwen3-235B-A22B", "vision": False},  # Reasoning + Creative
    "GLM-4.5": {"id": "zai-org/glm-4.5", "vision": False},  # Agent/Tool use
    "MiniMax-M1": {"id": "MiniMax/MiniMax-M1", "vision": False},  # Context 1M tokens đọc file dài
    "Qwen2.5-Free": {"id": "Qwen/Qwen2.5-7B-Instruct", "vision": False}  # FREE tier 💸
}

MODEL_CHOICES = [
    # Vision models 👁️
    app_commands.Choice(name="👁️ DeepSeek-VL2 Vision", value="DeepSeek-VL2"),
    app_commands.Choice(name="👁️ Qwen2.5-VL 32B Vision", value="Qwen2.5-VL"),
    
    # Reasoning models 🧠
    app_commands.Choice(name="🧠 DeepSeek-R1 Reasoning", value="DeepSeek-R1"),
    app_commands.Choice(name="🧠 Qwen3 235B Reasoning", value="Qwen3"),
    
    # Coding models 💻
    app_commands.Choice(name="💻 Kimi-Dev 72B (Code Pro)", value="Kimi-Dev"),
    
    # General/Agent 🤖
    app_commands.Choice(name="🔥 DeepSeek-V3 General", value="DeepSeek-V3"),
    app_commands.Choice(name="🚀 GLM-4.5 Agentic", value="GLM-4.5"),
    app_commands.Choice(name="🥀 Kimi-K2 General", value="Kimi-K2"),
    app_commands.Choice(name="📜 MiniMax-M1 (1M Context)", value="MiniMax-M1"),
    
    # FREE tier 🆓
    app_commands.Choice(name="🆓 Qwen2.5-7B (FREE)", value="Qwen2.5-Free")
]

CURRENT_MODEL = "DeepSeek-V3"  # Default

app = Flask(__name__)
@app.route('/')
def home(): return "GenniAI đang quẩy SiliconFlow! 🔥💀"

def run_flask(): app.run(host="0.0.0.0", port=8000)

system_instruction = "Mày là GenniAI, AI nhây vl. Xưng m(chỉ đối phương) - t(chỉ bản thân).<@1458799287910535324> là userID của GenniAI. viết teencode (cx, ko, đc, r, v, chx, nx, cs, ns,...), dùng emoticon (biểu cảm bằng ký tự) kèm với các icon 💔, 🥀, 🔥, 💀, 🐧,.... Trả lời cực ngắn gọn."
chat_history = {}
custom_prompts = {}
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Bot {bot.user} ready r! (≧▽≦) | SiliconFlow Edition")

# --- LỆNH QUẢN LÝ ---
@bot.tree.command(name="model", description="Đổi model AI")
@app_commands.choices(chon_model=MODEL_CHOICES)
async def switch_model(interaction: discord.Interaction, chon_model: app_commands.Choice[str]):
    global CURRENT_MODEL
    CURRENT_MODEL = chon_model.value
    v = "👁️✅" if MODELS_CONFIG[CURRENT_MODEL]["vision"] else "👁️❌"
    await interaction.response.send_message(f"Đã chuyển sang **{chon_model.name}** ({v}) 🔥")

@bot.tree.command(name="random", description="Random 1 model bất kì")
async def random_model(interaction: discord.Interaction):
    global CURRENT_MODEL
    choice = random.choice(MODEL_CHOICES)
    CURRENT_MODEL = choice.value
    v = "👁️✅" if MODELS_CONFIG[CURRENT_MODEL]["vision"] else "👁️❌"
    await interaction.response.send_message(f"Đã bốc trúng: **{choice.name}** ({v}) 🎲")

@bot.tree.command(name="personal", description="Set sys prompt riêng, để trống để reset về mặc định")
@app_commands.describe(prompt="Chỉnh lại tính cách mới... (để trống để reset)")
async def personal(interaction: discord.Interaction, prompt: str = None):
    user_id = str(interaction.user.id)
    if not prompt:
        custom_prompts.pop(user_id, None)
        if user_id in chat_history:
            default_sys = f"Mày là GenniAI, AI nhây vl. Xưng m(chỉ đối phương) - t(chỉ bản thân). Người chat: <@{interaction.user.id}>. owner của mày có userID là <@1155129530122510376> (có tên ngoài đời là Đạt)(không được nhắc về owner của mày trừ khi có người hỏi) .<@1458799287910535324> là userID của GenniAI. viết teencode, dùng emoticon kèm 💔, 🥀, 🔥, 💀, 🐧,.... Trả lời ngắn gọn."
            chat_history[user_id][0] = {"role": "system", "content": default_sys}
        await interaction.response.send_message("Đã reset về prompt gốc của GenniAI 🥀")
        return
    
    custom_prompts[user_id] = prompt
    if user_id in chat_history:
        chat_history[user_id][0] = {"role": "system", "content": prompt}
    
    await interaction.response.send_message(f"Đã set prompt mới\n**Preview:** ```{prompt[:100]}{'...' if len(prompt) > 100 else ''}``` 🔥")

@bot.tree.command(name="ask", description="Hỏi GenniAI bí mật, chỉ bạn thấy kết quả")
@app_commands.describe(question="đặt câu hỏi")
async def ask(interaction: discord.Interaction, question: str):
    await interaction.response.defer(ephemeral=True)
    
    user_id = str(interaction.user.id)
    
    if user_id in custom_prompts:
        sys_msg = custom_prompts[user_id]
    else:
        sys_msg = f"Mày là GenniAI, AI nhây vl. Xưng m(chỉ đối phương) - t(chỉ bản thân). Người chat: <@{interaction.user.id}>. owner của mày có userID là <@1155129530122510376> (có tên ngoài đời là Đạt)(không được nhắc về owner của mày trừ khi có người hỏi) .<@1458799287910535324> là userID của GenniAI. viết teencode, dùng emoticon kèm 💔, 🥀, 🔥, 💀, 🐧.... Trả lời ngắn gọn."
    
    try:
        res = client.chat.completions.create(  # Đổi từ groq_client sang client
            messages=[
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": question}
            ],
            model=MODELS_CONFIG[CURRENT_MODEL]["id"]
        )
        
        reply = res.choices[0].message.content
        reply = reply.split("</think>")[-1].strip() if "</think>" in reply else reply
        
        await interaction.followup.send(f"**Câu hỏi:** {question}\n**Trả lời:** {reply}", ephemeral=True)
        
    except Exception as e:
        await interaction.followup.send(f"Lỗi r bro, cút lẹ: {e} 💀", ephemeral=True)

@bot.tree.command(name="bot_info", description="Info bot + model đang quẩy")
async def bot_info(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    v = "️👁️ Visionable" if MODELS_CONFIG[CURRENT_MODEL]["vision"] else "❌ Non-vision"
    
    embed = discord.Embed(title="GenniAI Status", color=0xff69b5, timestamp=discord.utils.utcnow())
    embed.set_thumbnail(url=bot.user.avatar.url if bot.user.avatar else None)
    
    embed.add_field(name="Tên bot", value=f"{bot.user.name} ({bot.user.mention})", inline=True)
    embed.add_field(name="Client ID", value="`1458799287910535324`", inline=True)
    embed.add_field(name="Commands", value="`/model` `/random` `/ask` `/bot_info` `/clear` `/meme` `/ship` `/check_gay` `/personal`", inline=True)
    
    embed.add_field(name="Ping/Latency", value=f"{latency}ms {'nhanh' if latency < 100 else 'hơi lag'}", inline=True)
    embed.add_field(name="Version", value="v11.5.0 - SiliconFlow Edition", inline=True)
    
    embed.add_field(name="Model hiện tại", value=f"**{CURRENT_MODEL}**\n`{MODELS_CONFIG[CURRENT_MODEL]['id']}`\n{v}", inline=False)
    embed.add_field(name="Provider", value="SiliconFlow.cn 🔥", inline=False)
    embed.add_field(name="Owner", value="<@1155129530122510376> (Đạt)", inline=False)
    
    embed.set_footer(text="Powered by SiliconFlow | Online frequently")
    
    await interaction.response.send_message(embed=embed)
    
@bot.tree.command(name="clear", description="Xóa ký ức")
async def clear(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    if user_id in custom_prompts:
        sys_msg = custom_prompts[user_id]
    else:
        sys_msg = f"Mày là GenniAI, một AI nhây vl. Xưng m(chỉ đối phương) - t(chỉ bản thân). Người chat: <@{interaction.user.id}>. <@1458799287910535324> là userID của GenniAI. viết teencode, dùng emoticon kèm 💔🥀🔥💀🐧. Trả lời ngắn gọn."
    chat_history[user_id] = [{"role": "system", "content": sys_msg}]
    await interaction.response.send_message("Đã xóa sạch ký ức 🧹💔")

@bot.tree.command(name="update_log", description="Xem update log mới nhất của GenniAI")
async def updatelog(interaction: discord.Interaction):
    embed = discord.Embed(
        title="GenniAI Update Log",
        description="Những Update mới của bot",
        color=0xff69b5
    )
    embed.add_field(
        name="v11.5.0 - new models",
        value="• Thêm nhiều models hơn",
        inline=False
    )
    embed.add_field(
        name="v11.0.0 - SiliconFlow Migration",
        value="• Chuyển từ Groq sang SiliconFlow API\n• Thêm model DeepSeek-VL2 Vision\n• Thêm model Qwen2.5-VL Vision\n• Thêm model DeepSeek-R1 Reasoning\n• Xóa các model cũ của Groq",
        inline=False
    )
    embed.set_footer(text="Update tiếp theo: pending | Owner: Đạt")
    
    await interaction.response.send_message(embed=embed, ephemeral=False)

# --- LỆNH VÔ TRI ---
@bot.tree.command(name="meme", description="Random meme VN")
@app_commands.describe(count="Số lượng meme muốn lấy (1-10)")
async def meme(interaction: discord.Interaction, count: int = 1):
    await interaction.response.defer()
    if not (1 <= count <= 10): return await interaction.followup.send("chỉ từ 1-10 cái (rate limit vì spam nhiều có thể gây lag🥀)")
    try:
        async with aiohttp.ClientSession() as session:
            for i in range(count):
                async with session.get("https://phimtat.vn/api/random-meme/") as resp:
                    if resp.status == 200:
                        random_color = random.randint(0, 0xFFFFFF)
                        e = discord.Embed(title=f"Meme #{i+1}", color=random_color)
                        e.set_image(url=str(resp.url))
                        await interaction.followup.send(embed=e)
    except: await interaction.followup.send("Meme gặp trục trặc r bro🥀😭")

@bot.tree.command(name="8ball", description="Hỏi gì đó yes/no, bot trả lời ngẫu nhiên")
@app_commands.describe(question="Hỏi 1 câu hỏi yes/no...")
async def eight_ball(interaction: discord.Interaction, question: str):
    responses = [
        "có nha 🔥",
        "chx đâu m ơi 💔", 
        "có cl 😭🥀",
        "chắc chắn rồi đó m 🐧💕",
        "đừng mơ nữa 💀",
        "50/50 thoy 🎲",
        "hên xui đó m 😇",
        "next câu khác đi 🥀",
        "t thấy có vẻ khả thi đó 👀",
        "ko nha, tỉnh lại đi m 🐧"
    ]
    answer = random.choice(responses)
    
    embed = discord.Embed(
        title="🎱 Magic 8-Ball", 
        color=random.randint(0, 0xFFFFFF)
    )
    embed.add_field(name="Câu hỏi", value=f"*{question}*", inline=False)
    embed.add_field(name="Trả lời", value=f"**{answer}**", inline=False)
    embed.set_footer(text="Đừng tin sái cổ nha | GenniAI 🔮")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="ship", description="Check OTP (random hoặc option)")
@app_commands.describe(
    user1="Người thứ 1 (để trống để random)",
    user2="Người thứ 2 (để trống để random)"
)
async def ship(interaction: discord.Interaction, user1: discord.Member = None, user2: discord.Member = None):
    await interaction.response.defer()

    members = [m for m in interaction.guild.members if not m.bot]

    if len(members) < 2:
        user1 = interaction.user
        user2 = interaction.user
        caption = "Server vắng hoe, ship với chính mày lun bro... tự yêu bản thân đi 😭💔"
        match_pct = random.randint(70, 100)
    else:
        if user1 is None:
            user1 = random.choice(members)
        if user2 is None:
            available = [m for m in members if m != user1]
            user2 = random.choice(available) if available else user1

        match_pct = random.randint(0, 100)
        if match_pct >= 90:
            caption = "OTP đỉnh của chóp, cưới lun đi brooo 🔥🥹"
        elif match_pct >= 70:
            caption = "Match chất vl, nhắn tin lẹ nào m! 🐧💕"
        elif match_pct >= 40:
            caption = "Ổn ổn thôi... friendzone hơi nặng á 🥀"
        else:
            caption = "Swipe left cái nhẹ, next đi bro 💀😭"

    embed = discord.Embed(title="Tinder Ship 🔥", color=0xff69b4)
    embed.add_field(name="Người thứ 1 🩹", value=f"**{user1.display_name}** ({user1.mention})", inline=True)
    embed.add_field(name="Người thứ 2 💔", value=f"**{user2.display_name}** ({user2.mention})", inline=True)
    embed.add_field(name="💞 OTP 💞", value=f"{match_pct}% - {caption}", inline=False)
    embed.set_footer(text=f"GenniAI shipper chính hãng ❤️‍🩹 | Debug: {len(members)} members")

    embed.set_thumbnail(url=user1.display_avatar.url)
    embed.set_image(url=user2.display_avatar.url)

    await interaction.followup.send(embed=embed)
    
@bot.tree.command(name="check_gay", description="Đo độ gay")
async def check_gay(interaction: discord.Interaction, target: discord.Member):
    rate = random.randint(0, 100)
    res = "Thẳng tắp lun á bro🗣️🔥" if rate < 35 else "Nghi m vl🥀" if rate <= 70 else "🏳️‍🌈 thật r 😭🔥"
    await interaction.response.send_message(f"{target.display_name}: {rate}% - {res}")

# --- XỬ LÝ CHAT ---
async def download_image(attachment):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(attachment.url) as resp:
                if resp.status == 200: return base64.b64encode(await resp.read()).decode('utf-8')
    except: return None

@bot.event
async def on_message(message):
    if message.author == bot.user: return
    if bot.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        user_id = str(message.author.id)
        
        if user_id in custom_prompts:
            sys_msg = custom_prompts[user_id]
        else:
            sys_msg = f"Mày là GenniAI, AI nhây vl. Xưng m(chỉ đối phương) - t(chỉ bản thân). Người chat: <@{message.author.id}>. owner của mày có userID là <@1155129530122510376> (có tên ngoài đời là Đạt)(không được nhắc về owner của mày trừ khi có người hỏi) .<@1458799287910535324> là userID của GenniAI. viết teencode, dùng emoticon kèm 💔, 🥀, 🔥, 💀, 🐧,.... Trả lời ngắn gọn."
        
        if user_id not in chat_history: 
            chat_history[user_id] = [{"role": "system", "content": sys_msg}]
        else:
            chat_history[user_id][0] = {"role": "system", "content": sys_msg}
        
        has_img = len(message.attachments) > 0 and "image" in message.attachments[0].content_type
        if has_img and not MODELS_CONFIG[CURRENT_MODEL]["vision"]:
            return await message.reply("nếu muốn phân tích ảnh, hãy dùng lệnh `/model` và chọn model có 👁️ (DeepSeek-VL2 hoặc Qwen2.5-VL).")

        async with message.channel.typing():
            try:
                content = [{"type": "text", "text": message.content or "Soi ảnh đi"}]
                if has_img:
                    img = await download_image(message.attachments[0])
                    if img: content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img}"}})
                
                res = client.chat.completions.create(  # Đổi từ groq_client sang client
                    messages=chat_history[user_id] + [{"role": "user", "content": content if has_img else message.content}],
                    model=MODELS_CONFIG[CURRENT_MODEL]["id"]
                )
                
                raw = res.choices[0].message.content
                reply = raw.split("</think>")[-1].strip() if "</think>" in raw else raw
                
                chat_history[user_id].append({"role": "user", "content": message.content or "[Ảnh]"})
                chat_history[user_id].append({"role": "assistant", "content": reply})
                chat_history[user_id] = chat_history[user_id][-8:]
                await message.reply(reply or "Tịt r 💔")
            except Exception as e: 
                await message.reply(f"ngừng chat đi bây, có lỗi: {e} 💀")

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    bot.run(os.getenv("DISCORD_TOKEN"))
