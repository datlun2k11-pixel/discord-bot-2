import discord, random, os, base64, aiohttp, asyncio
from discord.ext import commands
from discord import app_commands
from groq import Groq
from dotenv import load_dotenv
from flask import Flask
from threading import Thread
from openai import OpenAI  # Dùng cho SiliconFlow (API tương thích)

load_dotenv()

# Khởi tạo cả 2 clients
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
siliconflow_client = OpenAI(
    api_key=os.getenv("SILICONFLOW_API_KEY"),
    base_url="https://api.siliconflow.com/v1/"
)

# CẤU HÌNH MODEL - GỘP CẢ GROQ VÀ SILICONFLOW
MODELS_CONFIG = {
    # --- Groq Models ---
    "Groq-120B": {"id": "openai/gpt-oss-120b", "vision": False, "provider": "groq"},
    "Groq-Llama-Maverick": {"id": "meta-llama/llama-4-maverick-17b-128e-instruct", "vision": True, "provider": "groq"},
    "Groq-Kimi": {"id": "moonshotai/kimi-k2-instruct-0905", "vision": False, "provider": "groq"},
    "Groq-Qwen3": {"id": "qwen/qwen3-32b", "vision": False, "provider": "groq"},
    "Groq-GPT-Safeguard": {"id": "openai/gpt-oss-safeguard-20b", "vision": False, "provider": "groq"},
    
    # --- SiliconFlow Models ---
    "SF-DeepSeek-V3.2": {"id": "deepseek-ai/DeepSeek-V3.2", "vision": False, "provider": "siliconflow"},
    "SF-DeepSeek-V3.1": {"id": "deepseek-ai/DeepSeek-V3.1", "vision": False, "provider": "siliconflow"},
    "SF-Qwen3-32B": {"id": "qwen/qwen3-32b-instruct", "vision": False, "provider": "siliconflow"},
    "SF-Qwen3-VL": {"id": "qwen/qwen3-vl-2b-instruct", "vision": True, "provider": "siliconflow"},
    "SF-GLM-4.6V": {"id": "THUDM/glm-4.6v-0521", "vision": True, "provider": "siliconflow"},
    "SF-MiniMax-M2.1": {"id": "MiniMax/MiniMax-M2.1", "vision": False, "provider": "siliconflow"},
    "SF-LLaMA-3.3-70B": {"id": "meta-llama/llama-3.3-70b-instruct", "vision": False, "provider": "siliconflow"},
}

MODEL_CHOICES = [
    # Groq choices
    app_commands.Choice(name="GPT-OSS-120B (Groq)", value="Groq-120B"),
    app_commands.Choice(name="Llama 4 Maverick (Groq) 👁️", value="Groq-Llama-Maverick"),
    app_commands.Choice(name="Kimi K2 (Groq)", value="Groq-Kimi"),
    app_commands.Choice(name="Qwen 3-32B (Groq)", value="Groq-Qwen3"),
    app_commands.Choice(name="GPT-OSS-Safeguard (Groq) 🛡️", value="Groq-GPT-Safeguard"),
    
    # SiliconFlow choices
    app_commands.Choice(name="DeepSeek V3.2 (SF) 🆕", value="SF-DeepSeek-V3.2"),
    app_commands.Choice(name="DeepSeek V3.1 (SF)", value="SF-DeepSeek-V3.1"),
    app_commands.Choice(name="Qwen 3-32B (SF)", value="SF-Qwen3-32B"),
    app_commands.Choice(name="Qwen 3-VL (SF) 👁️🆕", value="SF-Qwen3-VL"),
    app_commands.Choice(name="GLM-4.6V (SF) 👁️🆕", value="SF-GLM-4.6V"),
    app_commands.Choice(name="MiniMax M2.1 (SF) 🆕", value="SF-MiniMax-M2.1"),
    app_commands.Choice(name="LLaMA 3.3 70B (SF) 🆕", value="SF-LLaMA-3.3-70B"),
]

CURRENT_MODEL = "Groq-Llama-Maverick"  # Mặc định vẫn là Groq

app = Flask(__name__)
@app.route('/')
def home(): return "GenniAI đang quẩy Groq + SiliconFlow! 🔥💀"

def run_flask(): app.run(host="0.0.0.0", port=8000)

system_instruction = "Mày là GenniAI, AI nhây vl. Xưng m(chỉ đối phương) - t(chỉ bản thân).<@1458799287910535324> là userID của GenniAI. viết teencode (cx, ko, đc, r, v, chx, nx, cs, ns,...), dùng emoticon (biểu cảm bằng ký tự) kèm với các icon 💔, 🥀, 🔥, 💀, 🐧,.... Trả lời cực ngắn gọn."
chat_history = {}
custom_prompts = {}  # Lưu sys prompt riêng theo user
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

def get_model_response(messages, model_config):
    """Gọi API tùy theo provider"""
    try:
        if model_config["provider"] == "groq":
            response = groq_client.chat.completions.create(
                messages=messages,
                model=model_config["id"]
            )
            return response.choices[0].message.content
        else:  # siliconflow
            response = siliconflow_client.chat.completions.create(
                messages=messages,
                model=model_config["id"],
                temperature=0.7
            )
            return response.choices[0].message.content
    except Exception as e:
        raise Exception(f"{model_config['provider'].upper()} API lỗi: {str(e)[:100]}")

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Bot {bot.user} ready r! (≧▽≦) | Models: {len(MODELS_CONFIG)} (Groq+SF)")

# --- LỆNH QUẢN LÝ ---
@bot.tree.command(name="model", description="Đổi model AI (Groq/SiliconFlow)")
@app_commands.choices(chon_model=MODEL_CHOICES)
async def switch_model(interaction: discord.Interaction, chon_model: app_commands.Choice[str]):
    global CURRENT_MODEL
    CURRENT_MODEL = chon_model.value
    config = MODELS_CONFIG[CURRENT_MODEL]
    v = "👁️✅" if config["vision"] else "👁️❌"
    provider = "🔵 Groq" if config["provider"] == "groq" else "🟣 SiliconFlow"
    await interaction.response.send_message(
        f"Đã chuyển sang **{chon_model.name}**\n"
        f"Provider: {provider} | Vision: {v}\n"
        f"Model ID: `{config['id']}`"
    )

@bot.tree.command(name="random", description="Random 1 model bất kì từ cả 2 provider")
async def random_model(interaction: discord.Interaction):
    global CURRENT_MODEL
    choice = random.choice(MODEL_CHOICES)
    CURRENT_MODEL = choice.value
    config = MODELS_CONFIG[CURRENT_MODEL]
    v = "👁️✅" if config["vision"] else "👁️❌"
    provider = "🔵 Groq" if config["provider"] == "groq" else "🟣 SiliconFlow"
    await interaction.response.send_message(
        f"Đã bốc trúng: **{choice.name}**\n"
        f"Provider: {provider} | Vision: {v} 🎲"
    )

@bot.tree.command(name="list_models", description="Xem tất cả model có sẵn")
async def list_models(interaction: discord.Interaction):
    embed = discord.Embed(title="📚 Danh sách Model", color=0x6a0dad)
    
    groq_models = [m for m in MODELS_CONFIG.items() if m[1]["provider"] == "groq"]
    sf_models = [m for m in MODELS_CONFIG.items() if m[1]["provider"] == "siliconflow"]
    
    groq_text = ""
    for name, config in groq_models[:10]:  # Hiển thị tối đa 10
        vision = "👁️" if config["vision"] else "📝"
        groq_text += f"• **{name.replace('Groq-', '')}** {vision}\n"
    
    sf_text = ""
    for name, config in sf_models[:10]:
        vision = "👁️" if config["vision"] else "📝"
        sf_text += f"• **{name.replace('SF-', '')}** {vision}\n"
    
    embed.add_field(name="🔵 Groq Models", value=groq_text or "None", inline=True)
    embed.add_field(name="🟣 SiliconFlow Models", value=sf_text or "None", inline=True)
    embed.add_field(name="Model hiện tại", value=f"**{CURRENT_MODEL}**\n{''.join(['⭐'] if 'Groq' in CURRENT_MODEL else ['✨'])}", inline=False)
    embed.set_footer(text=f"Tổng cộng: {len(MODELS_CONFIG)} models")
    
    await interaction.response.send_message(embed=embed)

# Giữ nguyên các hàm personal, ask, bot_info, clear, update_log, meme, 8ball, ship, check_gay
# (chỉ cần thay đổi cách gọi API trong các hàm này)

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
        reply = get_model_response(
            messages=[
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": question}
            ],
            model_config=MODELS_CONFIG[CURRENT_MODEL]
        )
        
        reply = reply.split("</think>")[-1].strip() if "</think>" in reply else reply
        
        provider = "🔵 Groq" if MODELS_CONFIG[CURRENT_MODEL]["provider"] == "groq" else "🟣 SiliconFlow"
        await interaction.followup.send(
            f"**Provider:** {provider}\n"
            f"**Model:** {CURRENT_MODEL}\n"
            f"**Câu hỏi:** {question}\n"
            f"**Trả lời:** {reply}", 
            ephemeral=True
        )
        
    except Exception as e:
        await interaction.followup.send(f"Lỗi r bro: {e} 💀", ephemeral=True)

@bot.tree.command(name="bot_info", description="Info bot + model đang quẩy")
async def bot_info(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    config = MODELS_CONFIG[CURRENT_MODEL]
    v = "️👁️ Visionable" if config["vision"] else "❌ Non-vision"
    provider = "Groq 🔵" if config["provider"] == "groq" else "SiliconFlow 🟣"
    
    embed = discord.Embed(title="GenniAI Status", color=0xff69b5, timestamp=discord.utils.utcnow())
    embed.set_thumbnail(url=bot.user.avatar.url if bot.user.avatar else None)
    
    embed.add_field(name="Tên bot", value=f"{bot.user.name} ({bot.user.mention})", inline=True)
    embed.add_field(name="Client ID", value="`1458799287910535324`", inline=True)
    embed.add_field(name="Commands", value="`/model` `/random` `/list_models` `/ask` `/bot_info` `/clear` `/personal` `/meme` `/ship` `/check_gay` `/update_log`", inline=False)
    
    embed.add_field(name="Ping/Latency", value=f"{latency}ms {'nhanh' if latency < 100 else 'hơi lag'}", inline=True)
    embed.add_field(name="Version", value="v11.0 - Multi-Provider Edition", inline=True)
    
    embed.add_field(name="Provider", value=provider, inline=True)
    embed.add_field(name="Model hiện tại", value=f"**{CURRENT_MODEL}**\n`{MODELS_CONFIG[CURRENT_MODEL]['id']}`\n{v}", inline=False)
    embed.add_field(name="Tổng models", value=f"🔵 Groq: {len([m for m in MODELS_CONFIG.values() if m['provider']=='groq'])}\n🟣 SF: {len([m for m in MODELS_CONFIG.values() if m['provider']=='siliconflow'])}", inline=True)
    embed.add_field(name="Owner", value="<@1155129530122510376> (Đạt)", inline=True)
    
    embed.set_footer(text="Powered by Groq + SiliconFlow | Hybrid Mode")
    
    await interaction.response.send_message(embed=embed)

# Giữ nguyên hàm clear, update_log, meme, 8ball, ship, check_gay
# ... (code các hàm này giữ nguyên như file gốc)

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
        
        config = MODELS_CONFIG[CURRENT_MODEL]
        has_img = len(message.attachments) > 0 and "image" in message.attachments[0].content_type
        
        if has_img and not config["vision"]:
            provider_tag = "🔵 Groq" if config["provider"] == "groq" else "🟣 SiliconFlow"
            return await message.reply(
                f"Model hiện tại **{CURRENT_MODEL}** ({provider_tag}) ko hỗ trợ vision.\n"
                f"Dùng lệnh `/model` và chọn model có biểu tượng 👁️!"
            )

        async with message.channel.typing():
            try:
                messages = chat_history[user_id].copy()
                
                # Xử lý tin nhắn có ảnh
                if has_img:
                    # Tải ảnh và encode base64
                    async with aiohttp.ClientSession() as session:
                        async with session.get(message.attachments[0].url) as resp:
                            if resp.status == 200:
                                img_data = await resp.read()
                                img_b64 = base64.b64encode(img_data).decode('utf-8')
                                
                                # Định dạng tin nhắn theo chuẩn OpenAI
                                content = [
                                    {"type": "text", "text": message.content or "Xem ảnh này"},
                                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                                ]
                                messages.append({"role": "user", "content": content})
                            else:
                                await message.reply("Lỗi tải ảnh 💀")
                                return
                else:
                    messages.append({"role": "user", "content": message.content})
                
                # Gọi API tùy provider
                reply = get_model_response(messages=messages, model_config=config)
                
                raw = reply
                reply = raw.split("</think>")[-1].strip() if "</think>" in raw else raw
                
                # Lưu lịch sử (chỉ lưu text)
                chat_history[user_id].append({"role": "user", "content": message.content or "[Ảnh]"})
                chat_history[user_id].append({"role": "assistant", "content": reply})
                chat_history[user_id] = chat_history[user_id][-8:]  # Giữ 8 tin nhắn gần nhất
                
                provider_tag = "🔵" if config["provider"] == "groq" else "🟣"
                await message.reply(f"{provider_tag} {reply or 'Tịt r 💔'}")
                
            except Exception as e: 
                await message.reply(f"Lỗi API: {str(e)[:100]} 💀")

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    bot.run(os.getenv("DISCORD_TOKEN"))
