import discord, random, os, base64, aiohttp, asyncio
from discord.ext import commands
from discord import app_commands
from groq import Groq
from dotenv import load_dotenv
from flask import Flask
from threading import Thread
from openai import OpenAI

load_dotenv()

# Khởi tạo clients
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
siliconflow_client = OpenAI(
    api_key=os.getenv("SILICONFLOW_API_KEY"),
    base_url="https://api.siliconflow.com/v1/"
)

# CẤU HÌNH MODEL - GỘP GROQ + SILICONFLOW
MODELS_CONFIG = {
    # --- Groq Models ---
    "Groq-120B": {"id": "openai/gpt-oss-120b", "vision": False, "provider": "groq"},
    "Groq-Llama-Maverick": {"id": "meta-llama/llama-4-maverick-17b-128e-instruct", "vision": True, "provider": "groq"},
    "Groq-Kimi": {"id": "moonshotai/kimi-k2-instruct-0905", "vision": False, "provider": "groq"},
    "Groq-Qwen3": {"id": "qwen/qwen3-32b", "vision": False, "provider": "groq"},
    "Groq-GPT-Safeguard": {"id": "openai/gpt-oss-safeguard-20b", "vision": False, "provider": "groq"},
    
    # --- SiliconFlow Models (Hàng Real t vừa thêm nè 🔥) ---
      # --- SiliconFlow Models (Hàng Real t vừa thêm nè 🔥) ---
    "SF-DeepSeek-V3": {"id": "deepseek-ai/DeepSeek-V3", "vision": False, "provider": "siliconflow"},
    "SF-DeepSeek-R1": {"id": "deepseek-ai/DeepSeek-R1", "vision": False, "provider": "siliconflow"},
    "SF-Qwen2.5-72B": {"id": "Qwen/Qwen2.5-72B-Instruct", "vision": False, "provider": "siliconflow"},
    "SF-Llama-3.1-70B": {"id": "meta-llama/Meta-Llama-3.1-70B-Instruct", "vision": False, "provider": "siliconflow"},
}

MODEL_CHOICES = [
    # Groq choices
    app_commands.Choice(name="GPT-OSS-120B (Groq)", value="Groq-120B"),
    app_commands.Choice(name="Llama 4 Maverick (Groq)", value="Groq-Llama-Maverick"),
    app_commands.Choice(name="Kimi K2 (Groq)", value="Groq-Kimi"),
    app_commands.Choice(name="Qwen 3-32B (Groq)", value="Groq-Qwen3"),
    app_commands.Choice(name="GPT-OSS-Safeguard (Groq)", value="Groq-GPT-Safeguard"),
    
    # SiliconFlow choices
        # Thêm mấy con hàng Real này vào menu chọn cho nó uy tín
    app_commands.Choice(name="DeepSeek V3 (SF) - Siêu Khôn 🔥", value="SF-DeepSeek-V3"),
    app_commands.Choice(name="DeepSeek R1 (SF) - Suy Luận 🧠", value="SF-DeepSeek-R1"),
    app_commands.Choice(name="Qwen 2.5 72B (SF) 🍵", value="SF-Qwen2.5-72B"),
    app_commands.Choice(name="Llama 3.1 70B (SF) 🥀", value="SF-Llama-3.1-70B"),
]

CURRENT_MODEL = "Groq-Llama-Maverick"

app = Flask(__name__)
@app.route('/')
def home(): return "GenniAI v12.5.1 đang chạy Groq + SiliconFlow! 🔥"

def run_flask(): app.run(host="0.0.0.0", port=8000)

# Hàm helper gọi API
def get_model_response(messages, model_config):
    """Gọi API tùy provider"""
    try:
        if model_config["provider"] == "groq":
            response = groq_client.chat.completions.create(
                messages=messages,
                model=model_config["id"]
            )
            return response.choices[0].message.content
        else:
            response = siliconflow_client.chat.completions.create(
                messages=messages,
                model=model_config["id"],
                temperature=0.7
            )
            return response.choices[0].message.content
    except Exception as e:
        raise Exception(f"Lỗi {model_config['provider']}: {str(e)[:100]}")

# Bot setup
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
    print(f"GenniAI v12.5.1 ready! | Models: {len(MODELS_CONFIG)}")

# --- LỆNH MODEL ---
@bot.tree.command(name="model", description="Đổi model AI")
@app_commands.choices(chon_model=MODEL_CHOICES)
async def switch_model(interaction: discord.Interaction, chon_model: app_commands.Choice[str]):
    global CURRENT_MODEL
    CURRENT_MODEL = chon_model.value
    config = MODELS_CONFIG[CURRENT_MODEL]
    v = "✅ Vision" if config["vision"] else "❌ No Vision"
    provider = "Groq" if config["provider"] == "groq" else "SiliconFlow"
    await interaction.response.send_message(
        f"Đã chuyển sang **{chon_model.name}**\n"
        f"Provider: {provider} | {v}"
    )

@bot.tree.command(name="random", description="Random model từ cả 2 provider")
async def random_model(interaction: discord.Interaction):
    global CURRENT_MODEL
    choice = random.choice(MODEL_CHOICES)
    CURRENT_MODEL = choice.value
    config = MODELS_CONFIG[CURRENT_MODEL]
    v = "✅ Vision" if config["vision"] else "❌ No Vision"
    provider = "Groq" if config["provider"] == "groq" else "SiliconFlow"
    await interaction.response.send_message(
        f"Random: **{choice.name}**\n"
        f"Provider: {provider} | {v}"
    )

@bot.tree.command(name="list_models", description="Xem tất cả model có sẵn")
async def list_models(interaction: discord.Interaction):
    embed = discord.Embed(title="📚 Danh sách Model", color=0xff69b4)
    
    groq_text = ""
    sf_text = ""
    
    for name, config in MODELS_CONFIG.items():
        line = f"• {name} {'👁️' if config['vision'] else '📝'}\n"
        if config["provider"] == "groq":
            groq_text += line
        else:
            sf_text += line
    
    embed.add_field(name="Groq Models", value=groq_text or "None", inline=True)
    embed.add_field(name="SiliconFlow Models", value=sf_text or "None", inline=True)
    embed.add_field(name="Model hiện tại", value=f"**{CURRENT_MODEL}**", inline=False)
    embed.set_footer(text=f"v12.5.1 | Total: {len(MODELS_CONFIG)} models")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="personal", description="Set sys prompt riêng, để trống để reset")
@app_commands.describe(prompt="Chỉnh lại tính cách mới... (để trống để reset)")
async def personal(interaction: discord.Interaction, prompt: str = None):
    user_id = str(interaction.user.id)
    if not prompt:
        custom_prompts.pop(user_id, None)
        if user_id in chat_history:
            default_sys = f"Mày là GenniAI, AI nhây vl. Xưng m(chỉ đối phương) - t(chỉ bản thân). Người chat: <@{interaction.user.id}>. owner của mày có userID là <@1155129530122510376> (có tên ngoài đời là Đạt)(không được nhắc về owner của mày trừ khi có người hỏi) .<@1458799287910535324> là userID của GenniAI. viết teencode, dùng emoticon kèm 💔, 🥀, 🔥, 💀, 🐧,.... Trả lời ngắn gọn."
            chat_history[user_id][0] = {"role": "system", "content": default_sys}
        await interaction.response.send_message("Đã reset về prompt gốc của GenniAI")
        return
    
    custom_prompts[user_id] = prompt
    if user_id in chat_history:
        chat_history[user_id][0] = {"role": "system", "content": prompt}
    
    await interaction.response.send_message(f"Đã set prompt mới\n```{prompt[:100]}{'...' if len(prompt) > 100 else ''}```")

@bot.tree.command(name="ask", description="Hỏi GenniAI bí mật, chỉ bạn thấy kết quả")
@app_commands.describe(question="đặt câu hỏi")
async def ask(interaction: discord.Interaction, question: str):
    await interaction.response.defer(ephemeral=True)
    
    user_id = str(interaction.user.id)
    sys_msg = custom_prompts.get(user_id, system_instruction.replace("<@1458799287910535324>", f"<@{interaction.user.id}>"))
    
    try:
        reply = get_model_response(
            messages=[
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": question}
            ],
            model_config=MODELS_CONFIG[CURRENT_MODEL]
        )
        
        reply = reply.split("</think>")[-1].strip() if "</think>" in reply else reply
        
        provider = "Groq" if MODELS_CONFIG[CURRENT_MODEL]["provider"] == "groq" else "SiliconFlow"
        await interaction.followup.send(
            f"**Model:** {CURRENT_MODEL} ({provider})\n"
            f"**Câu hỏi:** {question}\n"
            f"**Trả lời:** {reply}", 
            ephemeral=True
        )
        
    except Exception as e:
        await interaction.followup.send(f"Lỗi: {e}", ephemeral=True)

@bot.tree.command(name="bot_info", description="Info bot + model đang chạy")
async def bot_info(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    config = MODELS_CONFIG[CURRENT_MODEL]
    v = "✅ Vision" if config["vision"] else "❌ No Vision"
    provider = "Groq" if config["provider"] == "groq" else "SiliconFlow"
    
    embed = discord.Embed(title="GenniAI Status", color=0xff69b5, timestamp=discord.utils.utcnow())
    if bot.user.avatar:
        embed.set_thumbnail(url=bot.user.avatar.url)
    
    embed.add_field(name="Tên bot", value=f"{bot.user.name} ({bot.user.mention})", inline=True)
    embed.add_field(name="Version", value="v12.8.1", inline=True)
    embed.add_field(name="Ping", value=f"{latency}ms", inline=True)
    
    embed.add_field(name="Model hiện tại", value=f"{CURRENT_MODEL}\n{provider} | {v}", inline=False)
    embed.add_field(name="Model ID", value=f"`{MODELS_CONFIG[CURRENT_MODEL]['id']}`", inline=False)
    
    embed.add_field(name="Total Models", value=f"Groq: 5 | SiliconFlow: {len(MODELS_CONFIG)-5}", inline=True)
    embed.add_field(name="Owner", value="<@1155129530122510376> (Đạt)", inline=True)
    
    embed.set_footer(text="Powered by Groq + SiliconFlow")
    
    await interaction.response.send_message(embed=embed)

# --- LỆNH TẠO ẢNH ---
@bot.tree.command(name="imagine", description="Tạo ảnh bằng AI (SiliconFlow)")
@app_commands.describe(prompt="mô tả ảnh m muốn tạo")
async def imagine(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer() # Chờ AI vẽ tí, đừng hối 💀
    
    # Chọn model mặc định là FLUX.1-dev cho nó nét
    image_model = "black-forest-labs/FLUX.1-dev" 
    
    try:
        # Gọi API SiliconFlow để gen ảnh
        response = siliconflow_client.images.generate(
            model=image_model,
            prompt=prompt,
            n=1 # 1 cái thôi ko tốn tiền vl 💔
        )
        
        image_url = response.data[0].url
        
        embed = discord.Embed(title=f"🎨 Ảnh của m nè bro!", color=0x00ff00)
        embed.add_field(name="Prompt", value=prompt, inline=False)
        embed.add_field(name="Model", value=image_model, inline=True)
        embed.set_image(url=image_url)
        embed.set_footer(text="Powered by SiliconFlow 🟣 | GenniAI")
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        await interaction.followup.send(f"Vẽ tịt r, lỗi: {str(e)[:100]} 🥀", ephemeral=True)

@bot.tree.command(name="clear", description="Xóa ký ức chat")
async def clear(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    sys_msg = custom_prompts.get(user_id, system_instruction.replace("<@1458799287910535324>", f"<@{interaction.user.id}>"))
    chat_history[user_id] = [{"role": "system", "content": sys_msg}]
    await interaction.response.send_message("Đã xóa sạch ký ức")

@bot.tree.command(name="update_log", description="Xem update log")
async def updatelog(interaction: discord.Interaction):
    embed = discord.Embed(title="GenniAI Update Log", color=0xff69b5)
    embed.add_field(
        name="v12.8.1 - Imagine",
        value="• Lệnh `/imagine` quay trở lại\n• Fixing bugs",
        inline=False
    )
    embed.add_field(
        name="v12.5.1 - Model Expansion",
        value="• Thêm 4 model SiliconFlow mới: DeepSeek-V3, DeepSeek-R1, Qwen2.5-72B, Llama-3.1-70B\n• Xóa icon tím/xanh khỏi tin nhắn\n• Tổng cộng 13 model từ 2 provider",
        inline=False
    )
    embed.set_footer(text="Next update: pending")
    
    await interaction.response.send_message(embed=embed)

# --- LỆNH VUI ---
@bot.tree.command(name="meme", description="Random meme VN")
@app_commands.describe(count="Số lượng meme (1-10)")
async def meme(interaction: discord.Interaction, count: int = 1):
    await interaction.response.defer()
    if not (1 <= count <= 10):
        await interaction.followup.send("Chỉ từ 1-10 cái thôi bro")
        return
    
    async with aiohttp.ClientSession() as session:
        for i in range(count):
            async with session.get("https://phimtat.vn/api/random-meme/") as resp:
                if resp.status == 200:
                    embed = discord.Embed(title=f"Meme #{i+1}", color=random.randint(0, 0xFFFFFF))
                    embed.set_image(url=str(resp.url))
                    await interaction.followup.send(embed=embed)
                else:
                    await interaction.followup.send("Lỗi tải meme")
                    break

@bot.tree.command(name="8ball", description="Hỏi yes/no")
@app_commands.describe(question="Hỏi 1 câu hỏi yes/no...")
async def eight_ball(interaction: discord.Interaction, question: str):
    responses = [
        "có nha 🔥", "chx đâu m ơi 💔", "có cl 😭🥀", "chắc chắn rồi đó m 🐧💕",
        "đừng mơ nữa 💀", "50/50 thoy 🎲", "hên xui đó m 😇", "next câu khác đi 🥀",
        "t thấy có vẻ khả thi đó 👀", "ko nha, tỉnh lại đi m 🐧"
    ]
    answer = random.choice(responses)
    
    embed = discord.Embed(title="🎱 Magic 8-Ball", color=random.randint(0, 0xFFFFFF))
    embed.add_field(name="Câu hỏi", value=f"*{question}*", inline=False)
    embed.add_field(name="Trả lời", value=f"**{answer}**", inline=False)
    embed.set_footer(text="GenniAI 8-Ball")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="ship", description="Check OTP")
@app_commands.describe(user1="Người thứ 1", user2="Người thứ 2")
async def ship(interaction: discord.Interaction, user1: discord.Member = None, user2: discord.Member = None):
    await interaction.response.defer()
    members = [m for m in interaction.guild.members if not m.bot]
    
    if len(members) < 2:
        user1 = interaction.user
        user2 = interaction.user
        caption = "Server vắng, ship với chính mày đi bro"
        match_pct = random.randint(70, 100)
    else:
        if user1 is None: user1 = random.choice(members)
        if user2 is None: user2 = random.choice([m for m in members if m != user1] or [user1])
        match_pct = random.randint(0, 100)
        
        if match_pct >= 90: caption = "OTP đỉnh, cưới đi 🔥"
        elif match_pct >= 70: caption = "Match chất, nhắn tin lẹ 🐧"
        elif match_pct >= 40: caption = "Ổn ổn... friendzone á 🥀"
        else: caption = "Swipe left, next đi 💀"
    
    embed = discord.Embed(title="Tinder Ship 🔥", color=0xff69b4)
    embed.add_field(name="Người 1", value=f"{user1.display_name}", inline=True)
    embed.add_field(name="Người 2", value=f"{user2.display_name}", inline=True)
    embed.add_field(name="OTP", value=f"{match_pct}% - {caption}", inline=False)
    embed.set_footer(text=f"đừng tin nha, kết quả là ngẫu nhiên | server: {len(members)}")
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="check_gay", description="Đo độ gay")
async def check_gay(interaction: discord.Interaction, target: discord.Member):
    rate = random.randint(0, 100)
    res = "Thẳng tắp lun á bro🔥" if rate < 35 else "Nghi m vl🥀" if rate <= 70 else "🏳️‍🌈 thật r 😭"
    await interaction.response.send_message(f"{target.display_name}: {rate}% - {res}")

# --- XỬ LÝ CHAT ---
async def download_image(attachment):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(attachment.url) as resp:
                if resp.status == 200:
                    return base64.b64encode(await resp.read()).decode('utf-8')
    except:
        return None

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    if bot.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        user_id = str(message.author.id)
        
        # Lấy system prompt
        if user_id in custom_prompts:
            sys_msg = custom_prompts[user_id]
        else:
            sys_msg = system_instruction.replace(
                "<@1458799287910535324>", 
                f"<@{message.author.id}>"
            )
        
        # Khởi tạo/update chat history
        if user_id not in chat_history:
            chat_history[user_id] = [{"role": "system", "content": sys_msg}]
        else:
            chat_history[user_id][0] = {"role": "system", "content": sys_msg}
        
        # Kiểm tra vision support
        config = MODELS_CONFIG[CURRENT_MODEL]
        has_img = len(message.attachments) > 0 and "image" in message.attachments[0].content_type
        
        if has_img and not config["vision"]:
            await message.reply(
                f"Model **{CURRENT_MODEL}** không hỗ trợ vision.\n"
                f"Dùng lệnh `/model` chọn model có vision!"
            )
            return
        
        async with message.channel.typing():
            try:
                messages = chat_history[user_id].copy()
                
                # Xử lý ảnh nếu có
                if has_img:
                    img_b64 = await download_image(message.attachments[0])
                    if img_b64:
                        content = [
                            {"type": "text", "text": message.content or "Xem ảnh"},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                        ]
                        messages.append({"role": "user", "content": content})
                    else:
                        await message.reply("Lỗi tải ảnh")
                        return
                else:
                    messages.append({"role": "user", "content": message.content})
                
                # Gọi API
                reply = get_model_response(messages=messages, model_config=config)
                
                # Xử lý response
                raw_reply = reply
                reply = raw_reply.split("</think>")[-1].strip() if "</think>" in raw_reply else raw_reply
                
                # Lưu history
                chat_history[user_id].append({"role": "user", "content": message.content or "[Ảnh]"})
                chat_history[user_id].append({"role": "assistant", "content": reply})
                chat_history[user_id] = chat_history[user_id][-8:]
                
                # Gửi reply (KHÔNG CÓ ICON MÀU)
                await message.reply(reply or "Tịt r 💔")
                
            except Exception as e:
                await message.reply(f"Lỗi: {str(e)[:80]}")

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    bot.run(os.getenv("DISCORD_TOKEN"))