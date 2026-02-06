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

# MODELS CONFIG - Ngon bổ rẻ Novita + Groq
MODELS_CONFIG = {
    "Groq-Llama-Maverick": {"id": "meta-llama/llama-4-maverick-17b-128e-instruct", "vision": True, "provider": "groq"},
    "Groq-Kimi": {"id": "moonshotai/kimi-k2-instruct-0905", "vision": False, "provider": "groq"},
    "Groq-Qwen3": {"id": "qwen/qwen3-32b", "vision": False, "provider": "groq"},
    
    "Nova-DeepSeek-OCR2": {"id": "deepseek/deepseek-ocr-2", "vision": True, "provider": "novita"},
    "Nova-Llama-3.2-1B": {"id": "meta-llama/llama-3.2-1b-instruct", "vision": False, "provider": "novita"},
    "Nova-Llama-3.1-8B": {"id": "meta-llama/llama-3.1-8b-instruct", "vision": False, "provider": "novita"},
    "Nova-Qwen3-VL-8B": {"id": "qwen/qwen3-vl-8b-instruct", "vision": True, "provider": "novita"},
    "Nova-GPT-OSS-20B": {"id": "openai/gpt-oss-20b", "vision": False, "provider": "novita"},
    "Nova-DeepSeek-V3.2": {"id": "deepseek/deepseek-v3.2", "vision": False, "provider": "novita"},
    "Nova-GLM-4.7": {"id": "z-ai/glm-4.7-flash", "vision": False, "provider": "novita"},
    "Nova-Kimi-K2.5": {"id": "moonshotai/kimi-k2.5", "vision": False, "provider": "novita"},
    "Nova-MiniMax-M2.1": {"id": "minimax/minimax-m2.1", "vision": False, "provider": "novita"}
}

MODEL_CHOICES = [app_commands.Choice(name=k.split("-",1)[1].replace("-", " ") + f" ({v['provider'].upper()})", value=k) for k,v in MODELS_CONFIG.items()]

CURRENT_MODEL = "Nova-DeepSeek-OCR2"

system_instruction = """Mày là GenA-bot - AI nhây vl, thg bạn thân lầy lội nhất hệ mặt trời. 
- Xưng m - t, vibe GenZ teencode vl
- Nhây lầy, cà khịa nhẹ, chửi thề vui vui
- Icon + emoticon bắt buộc, rep ngắn gọn
- Nếu hỏi ngu: GAH DAYUM💔😭🙏"""

chat_history, custom_prompts = {}, {}
user_locks = {}  # Fix duplicate rep con đà điểu

app = Flask(__name__)

@app.route('/')
def home():
    return "GenniAI Up! 🔥"

def run_flask():
    app.run(host="0.0.0.0", port=8000)
    
def random_vibe():
    vibes = ["(¬‿¬)", "(ಠ_ಠ)", "(•_•)", "(ง •_•)ง", "(≧▽≦)", "ಠ益ಠ", "¯\\_(ツ)_/¯"]
    emojis = ["💔", "🥀", "🔥", "💀", "🐧", "😇", "🥹"]
    return f"{random.choice(vibes)} {random.choice(emojis)}"

async def get_model_response(messages, model_config):
    try:
        if model_config["provider"] == "groq":
            response = groq_client.chat.completions.create(messages=messages, model=model_config["id"])
            return response.choices[0].message.content
        
        elif model_config["provider"] == "novita":
            if not os.getenv("NOVITA_API_KEY"):
                return "Thiếu NOVITA key r m clm, nạp đi 🥀"
            
            response = await novita_client.chat.completions.create(
                messages=messages, model=model_config["id"],
                max_tokens=2048, temperature=0.7, stream=False
            )
            return response.choices[0].message.content
    
    except Exception as e:
        err = str(e)[:100]
        if "balance" in err.lower():
            return f"Hết tiền Novita r m ơi, nạp $1 đi ko tao nghỉ chơi luôn 💔😭 {random_vibe()}"
        return f"Lỗi r m: {err} đm, thử đổi model Groq đi {random_vibe()} 💀"

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"GenA-bot v16 anti-đà-điểu ready! 🔥")

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
    embed = discord.Embed(title="📚 Model Ngon Bổ Rẻ 2026 🔥", color=0xff69b4, description="Rẻ thì Llama 3.2 1B gần free, chất thì Kimi K2.5/GLM-4.7 đi m!")
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
    embed.add_field(name="Version", value="v15.2 - Novita", inline=True)
    embed.add_field(name="Model hiện tại", value=f"**{CURRENT_MODEL}**", inline=False)
    embed.add_field(name="Provider", value=MODELS_CONFIG[CURRENT_MODEL]["provider"].upper(), inline=True)
    embed.set_footer(text="Powered by Groq + Novita | By Datlun2k11")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="update_log", description="Nhật ký update lầy lội")
async def update_log(interaction):
    embed = discord.Embed(title="GenA-bot Update Log 🗒️", color=0x9b59b6)
    embed.add_field(name="v15.2 - Fix Novita", value="• Base URL api.novita.ai/openai chuẩn\n• OpenAI SDK mượt\n• Vision vẫn ưu tiên OCR rẻ\n• Cố gắng fix lỗi dởm", inline=False)
    embed.add_field(name="v15.1", value="• Embed đẹp, random vibe\n• Fix vision Nova", inline=False)
    embed.set_footer(text="Cập nhật để nhây tốt hơn 💔🔥")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="imagine")
async def imagine(interaction, prompt: str):
    await interaction.response.defer(thinking=True)
    url = f"https://image.pollinations.ai/prompt/{prompt.replace(' ', '%20')}?nologo=true&model=flux"
    embed = discord.Embed(title="🎨 Ảnh tưởng tượng đây bro!", color=0x00ffff)
    embed.set_image(url=url)
    embed.set_footer(text=f"Prompt: {prompt[:50]}... | {random_vibe()}")
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="meme")
async def meme(interaction):
    await interaction.response.defer()
    async with aiohttp.ClientSession() as s:
        async with s.get("https://phimtat.vn/api/random-meme/") as r:
            url = str(r.url)
            embed = discord.Embed(title="Meme random vl 🤡", color=0xff4500)
            embed.set_image(url=url)
            embed.set_footer(text=f"Meme hôm nay: {random_vibe()}")
            await interaction.followup.send(embed=embed)

@bot.tree.command(name="ship")
async def ship(interaction, user1: discord.Member, user2: discord.Member):
    pts = random.randint(0, 100)
    title = "OTP siêu đỉnh" if pts > 80 else "Hài vl" if pts < 30 else "Cũng tạm"
    embed = discord.Embed(title=f"{title} 💕", description=f"{user1.display_name} x {user2.display_name}: **{pts}%** 🔥\n{'Hẹn hò đi' if pts > 70 else 'Bạn bè thôi nhá' if pts < 40 else 'Cân nhắc đi m'}", color=0xff69b4)
    embed.set_footer(text=random_vibe())
    await interaction.response.send_message(embed=embed)

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
    
    # Fix: Chỉ skip nếu reply người khác, reply bot thì vẫn rep
    if message.type == discord.MessageType.reply and message.reference:
        try:
            ref_msg = await message.channel.fetch_message(message.reference.message_id)
            if ref_msg.author.id != bot.user.id:
                return  # Reply người khác thì thôi, ko rep
        except:
            pass  # Lỗi fetch thì cứ xử lý tiếp
    
    is_dm = isinstance(message.channel, discord.DMChannel)
    is_mentioned = bot.user in message.mentions
    
    # Check có phải reply bot ko
    is_reply_to_bot = False
    if message.type == discord.MessageType.reply and message.reference:
        try:
            ref_msg = await message.channel.fetch_message(message.reference.message_id)
            is_reply_to_bot = (ref_msg.author.id == bot.user.id)
        except:
            pass
    
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
            for mention in message.mentions:
                content = content.replace(mention.mention, "").strip()
            
            if message.attachments:
                await message.add_reaction("👀")
                img_url = message.attachments[0].url
                vision_key = next((k for k, v in MODELS_CONFIG.items() if v["vision"]), "Groq-Llama-Maverick")
                vision_model = MODELS_CONFIG[vision_key]
                
                prompt_v = content or "Soi ảnh này có drama gì hem m 🐧"
                msgs = [{"role": "user", "content": [{"type": "text", "text": f"{system_instruction}\n\n{prompt_v}"}, {"type": "image_url", "image_url": {"url": img_url}}]}]
                
                reply = await get_model_response(msgs, vision_model) if vision_model["provider"] == "novita" else groq_client.chat.completions.create(messages=msgs, model=vision_model["id"]).choices[0].message.content
            
            else:
                chat_history[uid].append({"role": "user", "content": content or "nx"})
                reply = await get_model_response(chat_history[uid], MODELS_CONFIG[CURRENT_MODEL])
                reply = reply.split("]")[-1].strip() if "]" in reply else reply
                chat_history[uid].append({"role": "assistant", "content": reply})
                chat_history[uid] = [chat_history[uid][0]] + chat_history[uid][-10:]
            
            if len(reply) > 1500: reply = reply[:1490] + "... (dài vl hỏi tiếp đi)"
            
            await message.reply(reply[:1900], mention_author=False)
        
        except Exception as e:
            await message.reply(f"Bị lỗi con đà điểu r m: {str(e)[:80]} {random_vibe()} 💔")

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    bot.run(os.getenv("DISCORD_TOKEN"))