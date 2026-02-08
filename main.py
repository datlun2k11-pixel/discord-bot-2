import discord, random, os, asyncio
from discord.ext import commands
from discord import app_commands
from groq import Groq
from dotenv import load_dotenv
from flask import Flask
from threading import Thread
from openai import AsyncOpenAI
import aiohttp

load_dotenv()

# Clients
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
novita_client = AsyncOpenAI(
    base_url="https://api.novita.ai/openai",
    api_key=os.getenv("NOVITA_API_KEY")
)

MODELS_CONFIG = {
    "Groq-Llama-Maverick": {"id": "meta-llama/llama-4-maverick-17b-128e-instruct", "vision": True, "provider": "groq"},
    "Groq-Kimi": {"id": "moonshotai/kimi-k2-instruct-0905", "vision": False, "provider": "groq"},
    "Groq-Qwen3": {"id": "qwen/qwen3-32b", "vision": False, "provider": "groq"},
    "Nova-DeepSeek-OCR2": {"id": "deepseek/deepseek-ocr-2", "vision": True, "provider": "novita"},
    "Nova-Llama-3.2-1B": {"id": "meta-llama/llama-3.2-1b-instruct", "vision": False, "provider": "novita"},
    "Nova-MiniMax-M2.1": {"id": "minimax/minimax-m2.1", "vision": False, "provider": "novita"}
}

MODEL_CHOICES = [app_commands.Choice(name=k.split("-",1)[1].replace("-", " ") + f" ({v['provider'].upper()})", value=k) for k,v in MODELS_CONFIG.items()]
CURRENT_MODEL = "Nova-DeepSeek-OCR2"
system_instruction = "Mày là GenA-bot - AI nhây vl, vibe GenZ teencode. Xưng m-t, icon emoticon đầy đủ."

chat_history, custom_prompts, user_locks = {}, {}, {}

app = Flask(__name__)
@app.route('/')
def home(): return "GenniAI Up! 🔥"
def run_flask(): app.run(host="0.0.0.0", port=8000)
    
def random_vibe():
    vibes = ["(¬‿¬)", "(ಠ_ಠ)", "(•_•)", "(ง •_•)ง", "ಠ益ಠ"]
    emojis = ["💔", "🥀", "💀", "☠️", "🔥"]
    return f"{random.choice(vibes)} {random.choice(emojis)}"

async def get_model_response(messages, model_config):
    try:
        if model_config["provider"] == "groq":
            response = groq_client.chat.completions.create(messages=messages, model=model_config["id"])
            return response.choices[0].message.content
        elif model_config["provider"] == "novita":
            response = await novita_client.chat.completions.create(
                messages=messages, model=model_config["id"],
                max_tokens=2048, temperature=0.7, stream=False
            )
            return response.choices[0].message.content
    except Exception as e:
        # TRẢ VỀ LỖI NHƯNG KO ĐƯỢC NGẮT (RETURN) Ở ĐÂY ĐỂ DEBUG
        return f"DEBUG_ERROR_SYSTEM: {str(e)}"

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"GenA-bot Ready to Debug! 🔥")
# [CMDS CỦA M GẮN Ở ĐÂY NHÉ #]
bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"GenA-bot v15.3.5 anti-đà-điểu ready! 🔥")

# CMDs giữ nguyên xịn (t ko paste dài, copy từ code cũ m nhé: model, list_models, bot_info, update_log, imagine, meme, ship, check_gay, 8ball, clear)
@bot.tree.command(name="model", description="Đổi model AI xịn hơn")
@app_commands.choices(chon_model=MODEL_CHOICES)
async def switch_model(interaction, chon_model: app_commands.Choice[str]):
    global CURRENT_MODEL
    CURRENT_MODEL = chon_model.value
    embed = discord.Embed(title="Model Switcheroo!", description=f"Chuyển sang **{chon_model.name}** r nè bro\nRẻ vl + chất hơn xưa 🔥", color=0x00ff9d)
    embed.set_footer(text=f"Current: {CURRENT_MODEL} | {random_vibe()}")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="list_models", description="List model ngon bổ rẻ update")
async def list_models(interaction):
    embed = discord.Embed(title="📚 Model rẻ của bot", color=0xff69b4, description="Rẻ thì Llama 3.2 1B gần free, chất thì Kimi K2.5/GLM-4.7 đi m!")
    groq_t = "\n".join([f"• **{k}** ({v['provider'].upper()})" for k, v in MODELS_CONFIG.items() if v["provider"] == "groq"])
    nova_t = "\n".join([f"• **{k}** (Nova - rẻ vl)" for k, v in MODELS_CONFIG.items() if v["provider"] == "novita"])
    embed.add_field(name="Groq (nhanh chất)", value=groq_t or "None", inline=False)
    embed.add_field(name="Novita (rẻ + ngon)", value=nova_t or "None", inline=False)
    embed.set_footer(text=f"Pick đi {random_vibe()}")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="bot_info", description="Status bot xịn hơn tí")
async def bot_info(interaction):
    latency = round(bot.latency * 1000)
    embed = discord.Embed(title="GenA-bot Status 🚀", color=0xff1493, timestamp=discord.utils.utcnow())
    embed.add_field(name="Tên boss", value=f"{bot.user.mention}", inline=True)
    embed.add_field(name="Ping", value=f"{latency}ms {'(lag vl)' if latency > 200 else '(mượt vl)'}", inline=True)
    embed.add_field(name="Version", value="v15.5.0 - Novita", inline=True)
    embed.add_field(name="Model hiện tại", value=f"**{CURRENT_MODEL}**", inline=False)
    embed.add_field(name="Provider", value=MODELS_CONFIG[CURRENT_MODEL]["provider"].upper(), inline=True)
    embed.set_footer(text="Powered by Groq + Novita | By Datlun2k11")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="update_log", description="Nhật ký update")
async def update_log(interaction):
    embed = discord.Embed(title="GenA-bot Update Log 🗒️", color=0x9b59b6)
    embed.add_field(name="v15.5.0 - New command", value="• Vẫn debug:))\n• Đã thêm lệnh `/spring`\n• Cải thiện 1 số lệnh\n• Chuẩn bị đón xuân nha mn🧧:3", inline=False)
    embed.add_field(name="v15.3.5 - Debugging", value="• Tiếp tục fixing\n• Đang debug", inline=False)
    embed.set_footer(text="Updated ngày: 7/2/2026")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="imagine", description="tạo ảnh bằng AI (nhưng dởm)")
async def imagine(interaction, prompt: str):
    await interaction.response.defer(thinking=True)
    url = f"https://image.pollinations.ai/prompt/{prompt.replace(' ', '%20')}?nologo=true&model=flux"
    embed = discord.Embed(title="🎨 Ảnh tưởng tượng đây bro!", color=0x00ffff)
    embed.set_image(url=url)
    embed.set_footer(text=f"Prompt: {prompt[:50]}... | {random_vibe()}")
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="meme", description="meme random (tối đa 5 cái)")
@app_commands.describe(amount="Số lượng meme (1-5)")
async def meme(interaction: discord.Interaction, amount: int = 1):
    # Giới hạn từ 1-5 thôi ko nó spam nát server
    amount = max(1, min(amount, 5))
    
    await interaction.response.defer()
    
    async with aiohttp.ClientSession() as s:
        for i in range(amount):
            async with s.get("https://phimtat.vn/api/random-meme/") as r:
                url = str(r.url)
                embed = discord.Embed(title=f"Meme thứ {i+1}", color=0xff4500)
                embed.set_image(url=url)
                embed.set_footer(text=f"Meme chất lượng cao | {random_vibe()}")
                
                if i == 0:
                    await interaction.followup.send(embed=embed)
                else:
                    await message.channel.send(embed=embed)
            # Delay nhẹ tí cho đỡ bị Discord liệt vào hàng spam
            if amount > 1: await asyncio.sleep(0.5)

@bot.tree.command(name="spring", description="Bốc thăm lì xì đầu năm lấy hên m ơi")
async def spring(interaction: discord.Interaction):
    # List phần quà nhây
    rewards = [
    "🧧 Lì xì 500k (tưởng tượng đi m) 💸",
    "💀 1 vé quét sân, rửa bát xuyên Tết",
    "💍 Năm nay chắc chắn có người yêu (AI nói dối đấy)",
    "🥀 Crush xem story nhưng ko rep",
    "🧨 1 tràng pháo tay cho sự nghèo của m",
    "🥟 Một miếng bánh chưng toàn mỡ",
    "🔥 Nhân phẩm bùng nổ: Được lì xì gấp đôi năm ngoái",
    "🐧 Nhận được lời chúc 'Hay ăn chóng lớn' dù đã 18+",
    "☠️ Bị hỏi: 'Bao giờ lấy vợ/chồng?' 100 lần",
    "🌟 Vận may cả năm: Chơi bài toàn thắng (trừ lúc thua)",
    "💸 Tiền vào như nước sông Đà, tiền ra như tát nước ao",
    "🤡 1 suất làm 'con nhà người ta' trong truyền thuyết",
    "🍑 Một cành đào nở toàn lá",
    "🐍 Năm con Rắn, lươn lẹo ít thôi ko bị nghiệp quật"
]
    gift = random.choice(rewards)
    
    embed = discord.Embed(
        title="🧧 LÌ XÌ NHÂN PHẨM 2026 🧧",
        description=f"Chúc mừng {interaction.user.mention} đã bốc được:\n**{gift}**",
        color=0xff0000 # Màu đỏ cho nó may mắn
    )
    embed.set_footer(text=f"Tết nhất vui vẻ ko quạo nha bro {random_vibe()}")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="ship", description="Check OTP hoặc random một cặp trời đánh")
@app_commands.describe(user1="Người thứ 1", user2="Người thứ 2")
async def ship(interaction: discord.Interaction, user1: discord.Member = None, user2: discord.Member = None):
    await interaction.response.defer()
    
    # Lấy list member ko phải bot, nếu server bật intent members thì mới chuẩn nha
    members = [m for m in interaction.guild.members if not m.bot]
    
    # Trường hợp ko chọn ai thì bot tự "đi chợ" chọn hộ
    if user1 is None: 
        user1 = random.choice(members)
    if user2 is None: 
        # Chọn đứa thứ 2 khác đứa thứ 1, nếu server có mỗi 1 mống thì đành chịu
        remaining = [m for m in members if m.id != user1.id]
        user2 = random.choice(remaining) if remaining else user1

    if user1.id == user2.id:
        caption = "Tự luyến à m? Ship vs chính mình luôn ghê vl 🤡"
        match_pct = random.randint(80, 100)
    else:
        match_pct = random.randint(0, 100)
        if match_pct >= 90: caption = "OTP đỉnh, cưới đi ko t cướp 🔥"
        elif match_pct >= 70: caption = "Match chất đấy, nhắn tin lẹ đi 🐧"
        elif match_pct >= 40: caption = "Cũng ổn... mà chắc là friendzone 🥀"
        elif match_pct >= 10: caption = "Nhìn là thấy ko hạp r, swipe left đi 💀"
        else: caption = "GAH DAYUM! Cứu vãn j tầm này nx ☠️"
    
    embed = discord.Embed(title="💖 Tinder Ship 2026 💖", color=0xff69b4)
    embed.add_field(name="Partner 1", value=f"{user1.mention}", inline=True)
    embed.add_field(name="Partner 2", value=f"{user2.mention}", inline=True)
    embed.add_field(name="Tỉ lệ khớp", value=f"**{match_pct}%**\n=> *{caption}*", inline=False)
    embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/2589/2589175.png")
    embed.set_footer(text=f"Server: {len(members)} mống | {random_vibe()}")
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="check_gay")
async def check_gay(interaction, target: discord.Member):
    pts = random.randint(0,100)
    desc = "🏳️‍🌈 Max level!" if pts > 80 else "Có tí tí" if pts > 40 else "Straight vl bro"
    embed = discord.Embed(title=f"Gay meter của {target.display_name}", description=f"**{pts}%** {desc}", color=0x00ff00 if pts < 30 else 0xff00ff)
    embed.set_footer(text=random_vibe())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="8ball")
async def eight_ball(interaction, question: str):
    ans = random.choice(["có vl", "ko bao giờ", "cút", "hên xui bro", "đm hỏi ngu", "chắc chắn r", "có thể", "ko đc đâu"])
    embed = discord.Embed(title="🎱 Quả cầu tiên tri nhây", description=f"**Q**: {question}\n**A**: {ans}", color=0x8a2be2)
    embed.set_footer(text=random_vibe())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="clear", description="Reset ký ức nhưng giữ độ lầy")
async def clear(interaction):
    uid = str(interaction.user.id)
    chat_history[uid] = [{"role": "system", "content": custom_prompts.get(uid, system_instruction)}]
    await interaction.response.send_message(f"Đã clear ký ức, t lại nhây như mới tinh m ơi! {random_vibe()} 🥀🔥")

@bot.event
async def on_message(message):
    if message.author.bot: return
    
    is_dm = isinstance(message.channel, discord.DMChannel)
    is_mentioned = bot.user in message.mentions
    is_reply_to_bot = False
    if message.reference:
        try:
            ref_msg = await message.channel.fetch_message(message.reference.message_id)
            is_reply_to_bot = (ref_msg.author.id == bot.user.id)
        except: pass

    if not (is_mentioned or is_dm or is_reply_to_bot): return
    
    uid = str(message.author.id)
    lock = user_locks.get(uid, asyncio.Lock())
    user_locks[uid] = lock
    if lock.locked(): return
    
    async with lock:
        if uid not in chat_history:
            chat_history[uid] = [{"role": "system", "content": custom_prompts.get(uid, system_instruction)}]
        
        await message.channel.typing()
        
        try:
            content = message.content
            for mention in message.mentions: content = content.replace(mention.mention, "").strip()
            
            if message.attachments:
                # Xử lý Vision bth...
                img_url = message.attachments[0].url
                msgs = [{"role": "user", "content": [{"type": "text", "text": f"{system_instruction}\n\n{content or 'nx'}"}, {"type": "image_url", "image_url": {"url": img_url}}]}]
                reply = await get_model_response(msgs, MODELS_CONFIG["Nova-DeepSeek-OCR2"])
            else:
                chat_history[uid].append({"role": "user", "content": content or "nx"})
                reply = await get_model_response(chat_history[uid], MODELS_CONFIG[CURRENT_MODEL])

            # CHECK LỖI 403 NHƯNG KHÔNG DÙNG RETURN ĐỂ NGẮT MẠCH
            if "403" in reply or "DEBUG_ERROR_SYSTEM" in reply:
                await message.reply(f"Hết tiền Novita r m ơi, nạp $1 đi ko t nghỉ chơi luôn 💔😭 {random_vibe()}", mention_author=False)
                # Vẫn giữ nguyên reply lỗi để nó chạy tiếp xuống dưới lưu history
            
            # Xử lý format r gửi tiếp tin nhắn debug
            reply = reply.split("]")[-1].strip() if "]" in reply else reply
            chat_history[uid].append({"role": "assistant", "content": reply})
            chat_history[uid] = [chat_history[uid][0]] + chat_history[uid][-10:]
            
            # Gửi tin nhắn chính (hoặc tin nhắn chứa lỗi)
            await message.reply(f"{reply[:1800]}", mention_author=False)
        
        except Exception as e:
            await message.reply(f"Sập nguồn debug: {str(e)[:100]} 💀", mention_author=False)

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    bot.run(os.getenv("DISCORD_TOKEN"))
