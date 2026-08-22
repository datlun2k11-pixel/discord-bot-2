import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from google.genai import types
import config

# Model Gemma 3 12B trên Google AI Studio
GEMMA_MODEL_ID = "gemma-3-12b-it"
CLASSIFIER_SYSTEM_PROMPT = (
    "Bạn là một hệ thống phân loại ý định (Intent Classifier). "
    "Nhiệm vụ của bạn là phân tích xem người dùng trong chat Discord có đang muốn nói chuyện, "
    "gọi, hỏi câu hỏi, hoặc thu hút sự chú ý của bot AI (tên: Gemini / Bot) hay không. "
    "Chỉ trả về duy nhất một từ 'true' nếu đúng, hoặc 'false' nếu không. "
    "Không giải thích, không thêm bất kỳ văn bản nào khác."
)

# Dict lưu trạng thái Watcher theo channel_id - mặc định tắt (False)
watcher_status: dict[int, bool] = {}


async def check_intent_with_gemma3(text: str) -> bool:
    """Classifier bất đồng bộ dùng Gemma 3 12B qua Google AI Studio. Timeout 8s, lỗi -> False."""
    if not text or not text.strip():
        return False
    try:
        cfg = types.GenerateContentConfig(
            temperature=0.0,
            max_output_tokens=5,
        )
        # Dùng _async_client có sẵn từ config.py (đã init với GEMINI_API_KEY)
        response = await asyncio.wait_for(
            config._async_client.models.generate_content(
                model=GEMMA_MODEL_ID,
                contents=[f"{CLASSIFIER_SYSTEM_PROMPT}\n\nTin nhắn: \"{text.strip()}\""],
                config=cfg,
            ),
            timeout=8.0,
        )
        raw = config.config.extract_response_text(response) if hasattr(config.config, "extract_response_text") else (getattr(response, "text", "") or "")
        # Fallback nếu extract_response_text không có
        if not raw:
            try:
                raw = response.text or ""
            except Exception:
                raw = ""
        normalized = raw.strip().lower()
        # Chỉ cần chứa 'true' là True, ngược lại False
        return "true" in normalized
    except asyncio.TimeoutError:
        print(f"⚠️ [Gemma3 Classifier] timeout với text: {text[:50]}")
        return False
    except Exception as e:
        print(f"⚠️ [Gemma3 Classifier] lỗi: {e}")
        return False


class Watcher(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---- Slash Command /watcher ----
    @app_commands.command(name="watcher", description="Bật/tắt Watcher Mode cho channel hiện tại (Gemma 3 12B classifier)")
    async def watcher(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("❌ Lệnh chỉ dùng trong server!", ephemeral=True)
            return
        channel_id = interaction.channel.id
        current = watcher_status.get(channel_id, False)
        new_state = not current
        watcher_status[channel_id] = new_state

        status_text = "🟢 **BẬT**" if new_state else "🔴 **TẮT**"
        desc = f"Watcher Mode đã {status_text} cho <#{channel_id}>"
        if new_state:
            desc += "\nBot sẽ dùng **Gemma 3 12B** để nhận diện ý định chat khi không mention."
        else:
            desc += "\nBot chỉ trả lời khi được @mention trực tiếp."

        embed = discord.Embed(
            title="👁️ Watcher Mode",
            description=desc,
            color=0x00F0FF if new_state else 0xFF0040,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ---- Event on_message ----
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # 1. Bỏ qua bot (tránh loop vô tận)
        if message.author.bot:
            return

        # Chỉ xử lý trong guild text channel / thread có thể reply
        if not message.guild:
            return

        should_reply = False

        # Trường hợp 1: Bot được @mention trực tiếp -> reply ngay
        if self.bot.user and self.bot.user in message.mentions:
            should_reply = True
        # Trường hợp 2: Watcher BẬT ở channel này -> qua classifier Gemma 3 12B
        elif watcher_status.get(message.channel.id, False):
            content = message.content or ""
            # Bỏ qua tin nhắn rỗng / chỉ có attachment không có text
            if content.strip():
                should_reply = await check_intent_with_gemma3(content)

        if not should_reply:
            return

        # Thực thi phản hồi
        try:
            async with message.channel.typing():
                # Lấy model chính hiện tại của bot (tôn trọng guild settings)
                guild_id = str(message.guild.id)
                gs = config.GUILD_SETTINGS.get(guild_id, {})
                g_max = gs.get("max_tokens", config.DEFAULT_MAX_TOKENS)
                g_temp = gs.get("temperature", config.DEFAULT_TEMPERATURE)
                model = config.get_model_for_guild(g_max, g_temp, guild_id)

                # Build prompt tối giản - reuse BASE_SYSTEM_PROMPT nếu có
                system = getattr(config, "BASE_SYSTEM_PROMPT", "Bạn là bot AI thân thiện.")
                prompt_parts = [system, f"\nUser {message.author.display_name}: {message.content}"]

                # Giữ nguyên hỗ trợ ảnh nếu có
                for att in message.attachments:
                    if att.content_type and att.content_type.startswith("image/") and att.size <= 5 * 1024 * 1024:
                        try:
                            data = await att.read()
                            prompt_parts.append({"mime_type": att.content_type, "data": data})
                        except Exception:
                            pass

                response = await model.generate_content_async(prompt_parts)
                reply_text = config.config.extract_response_text(response)
                if not reply_text:
                    reply_text = "T bị lag xíu, nói lại đi 🥀"
                reply_text = reply_text[:2000]

                await message.reply(reply_text, mention_author=False)

                # Tăng RPD nếu là flash model
                if hasattr(model, "model_name") and config.config.is_flash_model(model.model_name):
                    config.config.increment_flash_rpd()

        except Exception as e:
            print(f"❌ [Watcher] lỗi khi reply: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Watcher(bot))
