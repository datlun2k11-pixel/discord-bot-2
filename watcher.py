import asyncio
import json
import re
import discord
from discord import app_commands
from discord.ext import commands
from google.genai import types
import config

# Model Gemma 4 trên Google AI Studio (Gemma 3 đã khai tử 404)
GEMMA_MODEL_ID = "gemma-4-31b-it"

# Dict lưu trạng thái Watcher theo channel_id - mặc định tắt (False)
watcher_status: dict[int, bool] = {}

# Regex để trích JSON từ response Gemma (hỗ trợ ```json block)
_JSON_RE = re.compile(r"\{[^{}]*\"should_reply\"[^{}]*\}", re.IGNORECASE | re.DOTALL)


def _extract_json(raw: str) -> dict | None:
    """Trích JSON đầu tiên chứa should_reply từ raw text của Gemma."""
    if not raw:
        return None
    # Thử parse trực tiếp nếu raw là JSON thuần
    raw_stripped = raw.strip()
    # Loại bỏ code block ```json ... ```
    if "```" in raw_stripped:
        # Lấy nội dung trong ```json ... ``` hoặc ``` ... ```
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_stripped, re.IGNORECASE | re.DOTALL)
        if m:
            raw_stripped = m.group(1).strip()
    try:
        obj = json.loads(raw_stripped)
        if isinstance(obj, dict) and "should_reply" in obj:
            return obj
    except:
        pass
    # Fallback: tìm regex JSON
    for m in _JSON_RE.finditer(raw):
        try:
            obj = json.loads(m.group(0))
            if isinstance(obj, dict) and "should_reply" in obj:
                return obj
        except:
            continue
    # Thử tìm bất kỳ JSON object nào
    try:
        # Tìm block { ... } đầu tiên
        m2 = re.search(r"\{.*\}", raw, re.DOTALL)
        if m2:
            obj = json.loads(m2.group(0))
            if isinstance(obj, dict):
                return obj
    except:
        pass
    return None


async def select_character_with_gemma3(text: str, guild_id: int) -> tuple[bool, dict | None]:
    """Dùng Gemma 4 31B để quyết định có reply không và chọn character nào.

    Returns:
        (should_reply: bool, character: dict|None)
        - should_reply False -> không reply
        - should_reply True, character None -> reply bằng GenA-Bot mặc định
        - should_reply True, character dict -> reply bằng webhook character đó
    """
    if not text or not text.strip():
        return False, None
    try:
        # Lấy danh sách character của guild
        guild_chars = config.get_guild_characters(guild_id) if guild_id else {}
        # Build đoạn mô tả character cho prompt - giữ ngắn gọn để tiết kiệm token
        if guild_chars:
            char_lines = []
            for role_id_str, c in guild_chars.items():
                # Cắt prompt 150 ký tự để không quá dài
                short_prompt = (c.get("system_prompt") or "")[:150].replace("\n", " ").strip()
                if len(c.get("system_prompt", "")) > 150:
                    short_prompt += "..."
                char_lines.append(f'- ID:{role_id_str} | Tên:"{c.get("name","")}" | Prompt:{short_prompt}')
            character_list_str = "\n".join(char_lines)
        else:
            character_list_str = "(Hiện chưa có character custom nào - chỉ có DEFAULT)"

        selector_prompt = (
            "Bạn là hệ thống Character Selector cho Discord bot.\n"
            "Nhiệm vụ: Phân tích tin nhắn Discord và quyết định:\n"
            "1) User có đang muốn nói chuyện / gọi / hỏi bot hoặc 1 character không? (chat giữa user với nhau thì false)\n"
            "2) Nếu có, chọn character phù hợp nhất để trả lời.\n\n"
            f"Danh sách character trong server:\n{character_list_str}\n"
            f'- DEFAULT: GenA-Bot (bot chính, vibe GenZ nhây, teencode)\n\n'
            f'Tin nhắn cần phân tích: "{text.strip()[:500]}"\n\n'
            "Quy tắc chọn:\n"
            "- Nếu tin nhắn nhắc tên character cụ thể (VD: Miku, Rem...) -> chọn ID của character đó\n"
            "- Nếu chung chung / không rõ / hỏi bot -> chọn \"DEFAULT\"\n"
            "- Nếu là chat giữa user với nhau, không gọi bot -> should_reply=false\n"
            "- Vibe/hài hước: nếu tin nhắn hợp vibe 1 character (vd tsundere, yandere...) có thể chọn character đó cho thú vị, nhưng ưu tiên nhắc tên trực tiếp\n\n"
            "CHỈ trả về JSON duy nhất, không giải thích, không markdown, format chính xác:\n"
            '{"should_reply": true/false, "character_id": "ROLE_ID hoặc DEFAULT hoặc null"}\n'
            "Ví dụ: {\"should_reply\": true, \"character_id\": \"123456789\"} hoặc {\"should_reply\": false, \"character_id\": null} hoặc {\"should_reply\": true, \"character_id\": \"DEFAULT\"}"
        )

        cfg = types.GenerateContentConfig(
            temperature=0.0,
            max_output_tokens=512,  # Gemma 4 có thinking (~300 tok) nên cần >=512 để ra JSON
        )
        import time
        _t0 = time.time()
        print(f"🔍 [Watcher Debug] Gọi Gemma 4 selector | guild={guild_id} | chars={len(guild_chars)} | text={repr(text[:80])}")
        print(f"🔍 [Watcher Debug] Prompt preview: {selector_prompt[:300]}...")
        response = await asyncio.wait_for(
            config._async_client.models.generate_content(
                model=GEMMA_MODEL_ID,
                contents=[selector_prompt],
                config=cfg,
            ),
            timeout=15.0,  # Gemma 4 full prompt ~11s nên 8s hay timeout với "bot ơi"
        )
        _elapsed = time.time() - _t0
        raw = config.config.extract_response_text(response) if hasattr(config.config, "extract_response_text") else (getattr(response, "text", "") or "")
        if not raw:
            try:
                raw = response.text or ""
            except Exception:
                raw = ""
        print(f"🔍 [Watcher Debug] Gemma raw ({_elapsed:.2f}s): {repr(raw[:400])}")

        obj = _extract_json(raw)
        if not obj:
            # Fallback: nếu không parse được JSON, thử logic cũ true/false
            normalized = raw.strip().lower()
            if "true" in normalized and "false" not in normalized:
                # Không xác định được character -> default
                print(f"⚠️ [Gemma3 Selector] không parse JSON, fallback true/DEFAULT, raw: {raw[:100]}")
                return True, None
            print(f"⚠️ [Gemma3 Selector] không parse được JSON, coi như false. raw: {raw[:200]}")
            return False, None

        should_reply = bool(obj.get("should_reply"))
        if not should_reply:
            return False, None

        char_id_raw = obj.get("character_id")
        if char_id_raw is None:
            return True, None
        char_id_str = str(char_id_raw).strip()
        if not char_id_str or char_id_str.lower() in ("null", "none", "default", "gena-bot", "genabot"):
            return True, None

        # Tìm character trong guild
        # Cho phép Gemma trả về tên thay vì ID -> thử match tên
        char_data = guild_chars.get(char_id_str)
        if char_data:
            return True, char_data
        # Thử match theo tên (case-insensitive)
        for c in guild_chars.values():
            if c["name"].lower() == char_id_str.lower():
                return True, c
        # Thử match chứa
        for c in guild_chars.values():
            if char_id_str.lower() in c["name"].lower() or c["name"].lower() in char_id_str.lower():
                return True, c

        # ID không tồn tại -> fallback DEFAULT để vẫn reply
        print(f"⚠️ [Gemma3 Selector] character_id {char_id_str} không tồn tại, fallback DEFAULT")
        return True, None

    except asyncio.TimeoutError:
        print(f"⚠️ [Gemma3 Selector] timeout 15s với text: {text[:80]} | chars={len(guild_chars)} -> fallback check keyword 'bot ơi'")
        # Fallback: nếu timeout mà tin nhắn chứa từ khóa gọi bot thì vẫn rep DEFAULT để không im lặng
        low = text.lower()
        if any(k in low for k in ["bot ơi", "bot oi", "ê bot", "gena", "gema", "bot " ]):
            print(f"🔁 [Watcher Fallback] timeout nhưng chứa keyword bot -> cho rep DEFAULT")
            return True, None
        return False, None
    except Exception as e:
        print(f"⚠️ [Gemma3 Selector] lỗi: {e}")
        import traceback; traceback.print_exc()
        # Fallback tương tự nếu lỗi bất ngờ mà có keyword bot
        low = text.lower() if text else ""
        if any(k in low for k in ["bot ơi", "bot oi"]):
            return True, None
        return False, None


# Giữ hàm cũ để backward compat (không dùng nữa nhưng để tránh break nếu chỗ khác import)
async def check_intent_with_gemma3(text: str) -> bool:
    should, _ = await select_character_with_gemma3(text, 0)
    return should


async def _get_or_create_webhook(channel, bot_user) -> discord.Webhook | None:
    """Tạo/tái sử dụng webhook cho character - hỗ trợ Thread (dùng parent)."""
    target_channel = channel.parent if isinstance(channel, discord.Thread) and channel.parent else channel
    if not hasattr(target_channel, 'webhooks') or not hasattr(target_channel, 'create_webhook'):
        return None
    try:
        if not target_channel.permissions_for(target_channel.guild.me).manage_webhooks:
            return None
    except Exception:
        pass
    try:
        webhooks = await target_channel.webhooks()
        for wh in webhooks:
            if wh.user and wh.user.id == bot_user.id:
                return wh
            if wh.name == "GenA-Character":
                return wh
        wh = await target_channel.create_webhook(name="GenA-Character", reason="Watcher character selector")
        return wh
    except Exception as e:
        print(f"⚠️ [Watcher] webhook lỗi: {e}")
        return None


class Watcher(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---- Slash Command /watcher ----
    @app_commands.command(name="watcher", description="Bật/tắt Watcher Mode - Gemma 4 tự chọn character để rep (thú vị hơn)")
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
            guild_chars = config.get_guild_characters(interaction.guild.id)
            if guild_chars:
                char_names = ", ".join([f"`{c['name']}`" for c in guild_chars.values()])
                desc += f"\nBot sẽ dùng **Gemma 4 31B** để tự chọn character phù hợp khi không mention.\n**Characters:** {char_names}\n+ `DEFAULT` (GenA-Bot)"
            else:
                desc += "\nBot sẽ dùng **Gemma 4 31B** để nhận diện ý định chat khi không mention.\n(Chưa có character custom - sẽ rep bằng GenA-Bot)"
            desc += "\n*Gemma sẽ chọn character thú vị nhất dựa trên nội dung tin nhắn* ✨"
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
        # Tôn trọng chat_enabled (global + guild)
        if not config.config.is_chat_enabled:
            return
        gs_check = config.GUILD_SETTINGS.get(str(message.guild.id), {})
        if gs_check.get("chat_enabled") is False:
            return

        should_reply = False
        selected_character: dict | None = None

        # Debug trạng thái watcher cho mỗi tin nhắn (để tui biết sao "bot ơi" không rep)
        _watcher_enabled = watcher_status.get(message.channel.id, False)
        _mentions_bot = self.bot.user in message.mentions if self.bot.user else False
        print(f"🔍 [Watcher Debug] on_message guild={message.guild.id} channel={message.channel.id} watcher={_watcher_enabled} content={repr(message.content[:100])} mentions_bot={_mentions_bot}")

        # FIX double-rep: Khi mention bot, để event.py (handler chính) rep 1 lần, watcher bỏ qua để tránh rep 2 lần
        if _mentions_bot:
            print(f"🔍 [Watcher Debug] Mention bot -> BỎ QUA watcher (nhường cho event.py rep 1 lần, tránh double)")
            return
        # Trường hợp duy nhất watcher xử lý: Watcher BẬT và KHÔNG mention -> qua Gemma 4 selector
        if _watcher_enabled:
            content = message.content or ""
            if content.strip():
                print(f"🔍 [Watcher Debug] Watcher BẬT -> gọi Gemma 4 selector...")
                should_reply, selected_character = await select_character_with_gemma3(content, message.guild.id)
                if should_reply and selected_character:
                    print(f"👁️ [Watcher] Gemma chọn character: {selected_character['name']} ({selected_character['role_id']}) cho tin nhắn: {content[:80]}")
                elif should_reply:
                    print(f"👁️ [Watcher] Gemma chọn DEFAULT (GenA-Bot) cho tin nhắn: {content[:80]}")
                else:
                    print(f"👁️ [Watcher] Gemma quyết định KHÔNG rep cho: {content[:80]}")
                    print(f"🔍 [Watcher Debug] -> Không rep, kết thúc watcher branch")
                    return
            else:
                print(f"🔍 [Watcher Debug] Bỏ qua do content rỗng/attachment -> không rep")
                return
        else:
            print(f"🔍 [Watcher Debug] Watcher TẮT và không mention -> bỏ qua")
            return

        if not should_reply:
            return

        # Thực thi phản hồi - phân nhánh character vs default
        try:
            async with message.channel.typing():
                guild_id = str(message.guild.id)
                gs = config.GUILD_SETTINGS.get(guild_id, {})
                g_max = gs.get("max_tokens", config.DEFAULT_MAX_TOKENS)
                g_temp = gs.get("temperature", config.DEFAULT_TEMPERATURE)
                model = config.get_model_for_guild(g_max, g_temp, guild_id)

                # Chuẩn bị prompt + attachments
                image_parts = []
                for att in message.attachments:
                    if att.content_type and att.content_type.startswith("image/") and att.size <= 5 * 1024 * 1024:
                        try:
                            data = await att.read()
                            image_parts.append({"mime_type": att.content_type, "data": data})
                        except Exception:
                            pass

                # === NHÁNH 1: Có character được chọn -> webhook style (tự do emoji/phong cách) ===
                if selected_character:
                    system_instruction = (
                        f"Bạn là Character \"{selected_character['name']}\" trong Discord server.\n"
                        f"System Prompt của bạn (TUÂN THỦ TUYỆT ĐỐI, được tự do emoji/phong cách theo prompt này):\n{selected_character['system_prompt']}\n\n"
                        f"⚠️ Bạn là webhook phụ được Watcher gọi, KHÔNG bị giới hạn 8 emoji như GenA-Bot chính. Hãy tự do dùng mọi emoji, slang, phong cách đúng như system prompt đã cho.\n"
                        f"{config.META_ROLEPLAY_PROMPT}"
                    )
                    # GIF instruction nếu bật
                    if config.GIPHY_ENABLED and gs.get("send_gif", True):
                        gif_instr = ""
                        # reuse logic từ event.py
                        try:
                            from event import _get_gif_instruction
                            gif_instr = _get_gif_instruction()
                        except:
                            gif_instr = ""
                        if gif_instr and "GIF" not in system_instruction:
                            system_instruction += "\n" + gif_instr

                    clean_content = message.content or ""
                    # Xóa mention bot nếu có lẫn
                    clean_content = config.strip_bot_mention(clean_content, self.bot.user.id if self.bot.user else None).strip()
                    if not clean_content and not image_parts:
                        clean_content = "Chào"

                    # Lấy channel context ngắn gọn (tùy chọn, để thú vị hơn)
                    try:
                        from event import get_channel_context
                        channel_context = get_channel_context(message.channel.id, max_messages=8)
                    except:
                        channel_context = ""

                    prompt_parts = [system_instruction]
                    if channel_context:
                        prompt_parts.append("\n--- LỊCH SỬ CHAT GẦN ĐÂY ---\n" + channel_context)
                    prompt_parts.append(f"\n--- TIN NHẮN CỦA {message.author.display_name}: ---\n{clean_content}")
                    prompt_parts.append("\nTrả lời ngắn gọn, đúng tính cách character đã giao, thú vị, GenZ nếu hợp.")
                    if image_parts:
                        prompt_parts.extend(image_parts)

                    response = await model.generate_content_async(prompt_parts)
                    reply_text = config.config.extract_response_text(response)
                    if not reply_text:
                        reply_text = "T bị lag xíu, nói lại đi 🥀"
                    reply_text = reply_text[:2000].strip()

                    # Xử lý GIF tương tự event
                    gif_urls = []
                    try:
                        from event import extract_gif_requests
                        if config.GIPHY_ENABLED and gs.get("send_gif", True):
                            clean_text, gif_queries = extract_gif_requests(reply_text)
                            if gif_queries:
                                for search_term, limit in gif_queries:
                                    try:
                                        urls = await asyncio.to_thread(config.search_gifs, search_term, limit)
                                        if urls:
                                            gif_urls.extend(urls)
                                    except Exception as e:
                                        print(f"⚠️ [Watcher] GIF lỗi: {e}")
                                reply_text = clean_text.strip()[:2000] if clean_text.strip() else reply_text
                    except Exception:
                        pass

                    # Gửi qua webhook
                    webhook = await _get_or_create_webhook(message.channel, self.bot.user)
                    if webhook is None:
                        # Fallback embed nếu không có quyền webhook
                        embed = discord.Embed(color=0x00F0FF, description=reply_text)
                        embed.set_author(name=selected_character["name"], icon_url=selected_character.get("avatar_url") or None)
                        if selected_character.get("avatar_url"):
                            embed.set_thumbnail(url=selected_character["avatar_url"])
                        embed.set_footer(text="⚠️ Thiếu quyền Manage Webhooks — fallback embed | Watcher")
                        await message.reply(embed=embed, mention_author=False)
                        for url in gif_urls:
                            try:
                                await message.channel.send(url)
                            except:
                                pass
                    else:
                        webhook_name = selected_character["name"][:80]
                        webhook_avatar = selected_character.get("avatar_url") or None
                        is_thread = isinstance(message.channel, discord.Thread)
                        try:
                            if is_thread:
                                await webhook.send(content=reply_text or "🥀", username=webhook_name, avatar_url=webhook_avatar, allowed_mentions=discord.AllowedMentions.none(), wait=True, thread=message.channel)
                            else:
                                await webhook.send(content=reply_text or "🥀", username=webhook_name, avatar_url=webhook_avatar, allowed_mentions=discord.AllowedMentions.none(), wait=True)
                        except discord.HTTPException:
                            # Thử lại không avatar
                            try:
                                if is_thread:
                                    await webhook.send(content=reply_text or "🥀", username=webhook_name, allowed_mentions=discord.AllowedMentions.none(), wait=True, thread=message.channel)
                                else:
                                    await webhook.send(content=reply_text or "🥀", username=webhook_name, allowed_mentions=discord.AllowedMentions.none(), wait=True)
                            except Exception as e2:
                                print(f"⚠️ [Watcher] webhook fallback fail: {e2}")
                                await message.reply(reply_text or "🥀", mention_author=False)
                        # GIFs qua webhook
                        for url in gif_urls:
                            try:
                                if is_thread:
                                    await webhook.send(content=url, username=webhook_name, avatar_url=webhook_avatar, allowed_mentions=discord.AllowedMentions.none(), thread=message.channel)
                                else:
                                    await webhook.send(content=url, username=webhook_name, avatar_url=webhook_avatar, allowed_mentions=discord.AllowedMentions.none())
                            except:
                                try:
                                    await message.channel.send(url)
                                except:
                                    pass
                        # Lưu vào chat_history để bot nhớ (optional)
                        ctx_key = config.get_context_key(message)
                        if ctx_key not in config.chat_history:
                            config.chat_history[ctx_key] = []
                        config.chat_history[ctx_key].append({"role": "user", "parts": [clean_content], "user_id": message.author.id, "display_name": message.author.display_name, "character": selected_character["name"]})
                        config.chat_history[ctx_key].append({"role": "model", "parts": [reply_text], "character": selected_character["name"]})
                        if len(config.chat_history[ctx_key]) > 15:
                            config.chat_history[ctx_key] = config.chat_history[ctx_key][-15:]

                    if hasattr(model, "model_name") and config.config.is_flash_model(model.model_name):
                        config.config.increment_flash_rpd()
                    return  # Đã xử lý xong nhánh character

                # === NHÁNH 2: DEFAULT GenA-Bot (mention hoặc watcher chọn DEFAULT) ===
                system = getattr(config, "BASE_SYSTEM_PROMPT", "Bạn là bot AI thân thiện.")
                # Nếu đang roleplay? watcher ưu tiên GenA-Bot mặc định, không lấy roleplay state
                # Nhưng vẫn tôn trọng nếu muốn giữ style GenA
                prompt_parts = [system, f"\nUser {message.author.display_name}: {message.content}"]
                if image_parts:
                    prompt_parts.extend(image_parts)

                response = await model.generate_content_async(prompt_parts)
                reply_text = config.config.extract_response_text(response)
                if not reply_text:
                    reply_text = "T bị lag xíu, nói lại đi 🥀"
                reply_text = reply_text[:2000]

                # GIF handling cho default (strip JSON nhưng không gửi nếu tắt)
                try:
                    from event import extract_gif_requests
                    if not gs.get("send_gif", True):
                        tmp_clean, tmp_q = extract_gif_requests(reply_text)
                        if tmp_q:
                            reply_text = tmp_clean.strip()[:2000] if tmp_clean.strip() else reply_text
                    else:
                        clean_text, gif_queries = extract_gif_requests(reply_text)
                        gif_urls = []
                        if gif_queries:
                            for search_term, limit in gif_queries:
                                try:
                                    urls = await asyncio.to_thread(config.search_gifs, search_term, limit)
                                    if urls:
                                        gif_urls.extend(urls)
                                except:
                                    pass
                            reply_text = clean_text.strip()[:2000] if clean_text.strip() else reply_text
                            for url in gif_urls:
                                try:
                                    await message.channel.send(url)
                                except:
                                    pass
                except:
                    pass

                await message.reply(reply_text, mention_author=False)

                if hasattr(model, "model_name") and config.config.is_flash_model(model.model_name):
                    config.config.increment_flash_rpd()

        except Exception as e:
            print(f"❌ [Watcher] lỗi khi reply: {e}")
            import traceback
            traceback.print_exc()


async def setup(bot: commands.Bot):
    await bot.add_cog(Watcher(bot))
