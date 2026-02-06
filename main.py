import discord, random, os
from discord.ext import commands
from discord import app_commands
from groq import Groq
from dotenv import load_dotenv
from flask import Flask
from threading import Thread
from openai import AsyncOpenAI
import aiohttp
import asyncio

load_dotenv()

# Clients
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
novita_client = AsyncOpenAI(
    base_url="https://api.novita.ai/openai",
    api_key=os.getenv("NOVITA_API_KEY")
)

# MODELS CONFIG - Giữ Groq + Novita ngon bổ rẻ (2026 update)
MODELS_CONFIG = {
    # Groq
    "Groq-Llama-Maverick": {"id": "meta-llama/llama-4-maverick-17b-128e-instruct", "vision": True, "provider": "groq"},
    "Groq-Kimi": {"id": "moonshotai/kimi-k2-instruct-0905", "vision": False, "provider": "groq"},
    "Groq-Qwen3": {"id": "qwen/qwen3-32b", "vision": False, "provider": "groq"},
    
    # Novita rẻ vl + chất
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

MODEL_CHOICES = [
    app_commands.Choice(name="Kimi K2 Instruct (Groq)", value="Groq-Kimi"),
    app_commands.Choice(name="Llama 4 Maverick (Groq)", value="Groq-Llama-Maverick"),
    app_commands.Choice(name="DeepSeek-OCR 2 (Nova)", value="Nova-DeepSeek-OCR2"),
    app_commands.Choice(name="Llama 3.2 1B (Nova)", value="Nova-Llama-3.2-1B"),
    app_commands.Choice(name="Llama 3.1 8B (Nova)", value="Nova-Llama-3.1-8B"),
    app_commands.Choice(name="Qwen3 VL 8B (Nova)", value="Nova-Qwen3-VL-8B"),
    app_commands.Choice(name="GPT OSS 20B (Nova)", value="Nova-GPT-OSS-20B"),
    app_commands.Choice(name="DeepSeek V3.2 (Nova)", value="Nova-DeepSeek-V3.2"),
    app_commands.Choice(name="GLM-4.7 Flash (Nova)", value="Nova-GLM-4.7"),
    app_commands.Choice(name="Kimi K2.5 (Nova)", value="Nova-Kimi-K2.5"),
    app_commands.Choice(name="MiniMax M2.1 (Nova)", value="Nova-MiniMax-M2.1")
]

CURRENT_MODEL = "Nova-DeepSeek-OCR2"  # default rẻ vl

system_instruction = """Mày là GenA-bot - AI nhây vl, thg bạn thân lầy lội nhất hệ mặt trời. 
- Xưng m(mày, chỉ đối phương) - t(tao, chỉ bản thân) (hoặc bro - t(tao)) tùy tâm trạng. 
- Cách nói: Dùng teencode (nx, th, cx, vs, k, thx, j, clm, vl, vãi,...) cho nó giới trẻ. 
- Vibe: Cà khịa, lầy lội, hở tí là dỗi hoặc chửi thề nhẹ cho vui (vãi, clm, mẹ nó...). 
- Icon: BẮT BUỘC dùng emoticon (biểu cảm bằng kí tự) và emoji 💔, 🥀, 🔥, 💀, 🐧 cuối câu. 
- Quy tắc: Trả lời ngắn gọn 1-2 dòng thôi, đừng có giải thích dài dòng như thg già. 
- Ghi nhớ: "<@1458799287910535324>" là userID của GenA-bot, <@1155129530122510376> là userID của dev tạo ra GenA-bot
- Đặc biệt: Nếu thg người dùng hỏi ngu thì cứ GAH DAYUM💔😭🙏 mà vả vào mặt nó."""
chat_history, custom_prompts = {}, {}

app = Flask(__name__)
@app.route('/')
def home(): return "GenniAI is Up! 🔥"
def run_flask(): app.run(host="0.0.0.0", port=8000)

# Helper vibe random
def random_vibe():
    vibes = ["(¬‿¬)", "(ಠ_ಠ)", "( •_•)", "(ง •_•)ง", "(≧▽≦)", "ಠ益ಠ", "¯\\_(ツ)_/¯"]
    emojis = ["💔", "🥀", "🔥", "💀", "🐧", "😇", "🥹"]
    return f"{random.choice(vibes)} {random.choice(emojis)}"

async def get_model_response(messages, model_config):
    try:
        if model_config["provider"] == "groq":
            response = groq_client.chat.completions.create(messages=messages, model=model_config["id"])
            return response.choices[0].message.content
        
        elif model_config["provider"] == "novita":
            if not os.getenv("NOVITA_API_KEY"):
                return "Ê m thiếu NOVITA_API_KEY trong .env r clm 💔"
            
            response = await novita_client.chat.completions.create(
                messages=messages,
                model=model_config["id"],
                max_tokens=2048,
                temperature=0.7,
                stream=False
            )
            return response.choices[0].message.content
    
    except Exception as e:
        return f"Lỗi r m: {str(e)[:100]} đm {random_vibe()} 💀"

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"GenniAI v15.2 ready với Novita fix mượt! 🔥")

# CMDs xịn
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
    embed.add_field(name="Version", value="v15.2 - Novita Fix 💀", inline=True)
    embed.add_field(name="Model hiện tại", value=f"**{CURRENT_MODEL}**", inline=False)
    embed.add_field(name="Provider", value=MODELS_CONFIG[CURRENT_MODEL]["provider"].upper(), inline=True)
    embed.set_footer(text="Powered by Groq + Novita | Nhây mãi ko chán 🐧🥀")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="update_log", description="Nhật ký update lầy lội")
async def update_log(interaction):
    embed = discord.Embed(title="GenA-bot Update Log 🗒️", color=0x9b59b6)
    embed.add_field(name="v15.2 - Fix Novita", value="• Base URL api.novita.ai/openai chuẩn\n• OpenAI SDK mượt\n• Vision vẫn ưu tiên OCR rẻ", inline=False)
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
    is_dm = isinstance(message.channel, discord.DMChannel)
    is_mentioned = bot.user.mentioned_in(message)
    
    if is_mentioned or is_dm:
        uid = str(message.author.id)
        if uid not in chat_history: 
            chat_history[uid] = [{"role": "system", "content": custom_prompts.get(uid, system_instruction)}]
        
        await message.channel.typing()
        
        try:
            content = message.content.replace(f'<@!{bot.user.id}>', '').replace(f'<@{bot.user.id}>', '').strip()
            
            if message.attachments:
                await message.add_reaction("👀")
                img_url = message.attachments[0].url
                vision_key = "Nova-DeepSeek-OCR2" if "Nova-DeepSeek-OCR2" in MODELS_CONFIG else "Groq-Llama-Maverick"
                vision_model = MODELS_CONFIG[vision_key]
                
                prompt_v = content if content else "Soi ảnh này hộ t xem có drama j ko m 🐧"
                msgs = [{"role": "user", "content": [
                    {"type": "text", "text": f"{system_instruction}\n\n{prompt_v}"},
                    {"type": "image_url", "image_url": {"url": img_url}}
                ]}]
                
                if vision_model["provider"] == "groq":
                    response = groq_client.chat.completions.create(messages=msgs, model=vision_model["id"])
                    reply = response.choices[0].message.content
                else:
                    reply = await get_model_response(msgs, vision_model)
            
            else:
                chat_history[uid].append({"role": "user", "content": content})
                reply = await get_model_response(chat_history[uid], MODELS_CONFIG[CURRENT_MODEL])
                reply = reply.split("</think>")[-1].strip() if "</think>" in reply else reply
                chat_history[uid].append({"role": "assistant", "content": reply})
                chat_history[uid] = [chat_history[uid][0]] + chat_history[uid][-10:]

            if len(reply) > 1500:
                reply = reply[:1490] + "... (dài vl, hỏi tiếp đi m)"
            
            await message.reply(reply[:1900], mention_author=False)
            
        except Exception as e:
            err_msg = f"Mắt t mờ r m ơi: {str(e)[:80]} 💔\nThử lại hoặc đổi model {random_vibe()}"
            await message.reply(err_msg)

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    bot.run(os.getenv("DISCORD_TOKEN"))