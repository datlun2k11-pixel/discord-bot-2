import time
import json
import re
import os
import tempfile
import shutil
import asyncio
from collections import deque
from typing import Dict, Optional, List, Tuple
import discord
import config

# === RATE LIMITING CONFIG ===
RATE_LIMIT_WINDOW = 60  # 60 giây
RATE_LIMIT_MAX_REQUESTS = 20  # Tối đa 20 request mỗi 60 giây
MAX_ATTACHMENT_SIZE = 5 * 1024 * 1024  # 5MB

# --- BỘ NHỚ THÔNG MINH CHO KOYEB ---
# CHANNEL_MEMORY: lưu 15 tin nhắn gần nhất mỗi channel
# Cấu trúc: {channel_id: deque(maxlen=15)}
CHANNEL_MEMORY: Dict[int, deque] = {}

# Lock cho thread-safe memory saving (khởi tạo lazy để tránh lỗi event loop)
_save_lock: asyncio.Lock = None
_save_counter = 0  # Khởi tạo biến đếm toàn cục

# File lưu memory (để khi restart bot vẫn nhớ)
MEMORY_FILE = "channel_memory.json"

# --- GIF HELPERS (GIPHY via requests) ---
_GIF_CODEBLOCK_RE = re.compile(r'```(?:json)?\s*(\{[^`]*?\})\s*```', re.IGNORECASE | re.DOTALL)
_GIF_INLINE_RE = re.compile(r'\{[^{}]*"search"\s*:\s*"[^"]*"[^{}]*\}')

def extract_gif_requests(text: str) -> Tuple[str, List[Tuple[str, int]]]:
    """Tách JSON GIF ra khỏi text

    Hỗ trợ:
    - ```json {"search": "cringe", "max_result": 2}```
    - {"search": "cringe", "max_result": "3"}
    - {"search": "anime dance", "max_results": 2} / limit
    Returns: (clean_text, [(search, limit), ...])
    """
    if not text or not config.GIPHY_ENABLED:
        return text, []
    gif_requests: List[dict] = []
    clean = text

    # 1. Codeblock json
    for m in list(_GIF_CODEBLOCK_RE.finditer(text)):
        raw = m.group(1).strip()
        try:
            obj = json.loads(raw)
            if isinstance(obj, dict) and "search" in obj:
                gif_requests.append(obj)
                clean = clean.replace(m.group(0), "")
        except:
            continue

    # 2. Inline json (tìm trong clean hiện tại để tránh duplicate)
    for m in list(_GIF_INLINE_RE.finditer(clean)):
        raw = m.group(0)
        try:
            obj = json.loads(raw)
            if isinstance(obj, dict) and "search" in obj:
                # Tránh duplicate nếu đã bắt từ codeblock
                if obj not in gif_requests:
                    gif_requests.append(obj)
                clean = clean.replace(raw, "")
        except:
            continue

    # Normalize limits
    normalized: List[Tuple[str, int]] = []
    for obj in gif_requests:
        search = str(obj.get("search", "")).strip()
        if not search:
            continue
        raw_limit = obj.get("max_result", obj.get("max_results", obj.get("limit", obj.get("maxResult", 1))))
        try:
            limit = int(str(raw_limit).strip())
        except:
            limit = 1
        limit = max(1, min(limit, 3))
        normalized.append((search, limit))

    # Dọn clean text: xóa dòng trống thừa, strip
    clean = re.sub(r'\n{3,}', '\n\n', clean).strip()
    return clean, normalized

def _get_gif_instruction() -> str:
    """Trả về instruction GIF để inject vào prompt (nếu enabled)"""
    if not config.GIPHY_ENABLED:
        return ""
    return '\n🎬 GIF: Nếu cảm xúc hợp lý (cringe, troll, meme...), có thể gửi GIF bằng cách thêm 1 dòng JSON ở CUỐI tin nhắn: {"search": "keyword tiếng Anh", "max_result": 1} (1-3). VD: {"search": "cringe", "max_result": 2}. JSON sẽ bị ẩn và bot tự gửi GIF. Chỉ dùng khi thực sự cần.'

def _get_save_lock() -> asyncio.Lock:
    """Lazy initialization of asyncio.Lock để tránh lỗi event loop chưa tồn tại"""
    global _save_lock
    if _save_lock is None:
        _save_lock = asyncio.Lock()
    return _save_lock

def load_memory():
    """Load memory từ file JSON khi bot khởi động"""
    global CHANNEL_MEMORY
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for channel_id_str, messages in data.items():
                channel_id = int(channel_id_str)
                CHANNEL_MEMORY[channel_id] = deque(messages, maxlen=15)
            print(f"✅ Đã load memory cho {len(CHANNEL_MEMORY)} channel")
        except Exception as e:
            print(f"⚠️ Lỗi load memory: {e}")

def save_memory():
    """Lưu memory ra file JSON (atomic write)"""
    try:
        data = {}
        for channel_id, messages in CHANNEL_MEMORY.items():
            data[str(channel_id)] = list(messages)
        
        # Atomic write: ghi vào temp file trước, rename sau
        temp_fd, temp_path = tempfile.mkstemp(dir=".")
        try:
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            shutil.move(temp_path, MEMORY_FILE)
        except Exception:
            try:
                os.unlink(temp_path)
            except Exception:
                pass
            raise
    except Exception as e:
        print(f"⚠️ Lỗi save memory: {e}")

def get_channel_context(channel_id: int, max_messages: int = 15) -> str:
    """Lấy context chat của channel (tối đa 15 tin)"""
    if channel_id not in CHANNEL_MEMORY:
        CHANNEL_MEMORY[channel_id] = deque(maxlen=15)
        return "Chưa có tin nhắn nào trong channel này."
    
    history = list(CHANNEL_MEMORY[channel_id])
    if not history:
        return "Chưa có tin nhắn nào trong channel này."
    
    # Lấy 15 tin gần nhất (hoặc ít hơn)
    recent = history[-max_messages:]
    context = "\n".join(recent)
    return context

def format_message_for_memory(msg: discord.Message) -> str:
    """Format tin nhắn để lưu vào memory (ngắn gọn, tiết kiệm token)"""
    author_name = msg.author.display_name or msg.author.name
    
    # Xử lý nội dung tin nhắn
    content = msg.content or ""
    # Nếu tin nhắn có ảnh đính kèm
    has_image_attachment = any(
        att.content_type and att.content_type.startswith("image/")
        for att in msg.attachments
    )
    if not content and msg.attachments:
        if has_image_attachment:
            content = "[📷 Ảnh]"
        else:
            content = "[📎 File]"
    elif not content and msg.stickers:
        content = "[🎨 Sticker]"
    elif not content:
        content = "[💬 Tin nhắn trống]"
    elif has_image_attachment:
        # Nếu có text + ảnh, thêm tag ảnh vào cuối
        content += " [📷 Ảnh]"
        
    # Cắt ngắn nội dung nếu quá dài (tiết kiệm token)
    if len(content) > 200:
        content = content[:197] + "..."
        
    # Xử lý reply (quan trọng để hiểu ngữ cảnh)
    reply_context = ""
    if msg.reference and msg.reference.resolved:
        replied = msg.reference.resolved
        if isinstance(replied, discord.Message):
            replied_name = replied.author.display_name or replied.author.name
            replied_content = replied.content or "[📷 Ảnh]"
            if len(replied_content) > 50:
                replied_content = replied_content[:47] + "..."
            reply_context = f" (→ {replied_name}: {replied_content})"
            
    return f"{author_name}: {content}{reply_context}"

async def _describe_image(image_parts: list) -> Optional[str]:
    """Dùng Gemini để mô tả ảnh ngắn gọn (1-2 câu), tiết kiệm token cho memory"""
    if not image_parts:
        return None
    try:
        # Dùng model rẻ nhất để mô tả ảnh
        desc_model = config.get_model("gemini-flash-lite-latest")
        desc_prompt = [
            "Mô tả ảnh này siêu ngắn gọn trong 1 câu (tối đa 15 từ), chỉ nội dung chính, không cảm xúc, không giải thích.",
        ]
        desc_prompt.extend(image_parts)
        response = await desc_model.generate_content_async(desc_prompt)
        description = config.extract_response_text(response)
        if description and len(description) > 100:
            description = description[:97] + "..."
        return description.strip() if description else None
    except Exception as e:
        print(f"⚠️ Lỗi describe image: {e}")
        return None

# --- CHARACTER WEBHOOK SYSTEM HELPERS ---
_ROLE_MENTION_RE = re.compile(r"<@&(\d+)>")

def _strip_role_mentions(text: str) -> str:
    """Xóa tất cả <@&role_id> tag khỏi text"""
    if not text:
        return ""
    return _ROLE_MENTION_RE.sub("", text).strip()

async def _get_or_create_webhook(channel: discord.TextChannel, bot_user) -> Optional[discord.Webhook]:
    """Tạo hoặc tái sử dụng Webhook trong channel hiện tại"""
    # Kiểm tra quyền trước
    if not channel.permissions_for(channel.guild.me).manage_webhooks:
        return None
    try:
        webhooks = await channel.webhooks()
        # Tìm webhook do bot tạo ra hoặc tên GenA-Character
        for wh in webhooks:
            if wh.user and wh.user.id == bot_user.id:
                return wh
            if wh.name == "GenA-Character":
                return wh
        # Không có -> tạo mới
        wh = await channel.create_webhook(
            name="GenA-Character",
            reason="Character Webhook System - auto create",
        )
        print(f"✅ Đã tạo webhook mới tại #{channel.name} ({channel.id})")
        return wh
    except discord.Forbidden:
        print(f"⚠️ Thiếu quyền Manage Webhooks tại #{channel.name}")
        return None
    except discord.HTTPException as e:
        print(f"⚠️ Lỗi tạo/fetch webhook tại #{channel.name}: {e}")
        return None

async def _handle_character_mention(
    bot,
    message: discord.Message,
    matched_char: dict,
) -> bool:
    """Xử lý khi user @Mention Role Character — gen AI + webhook reply

    Returns True nếu đã xử lý (để caller return), False nếu fail và muốn fallback.
    """
    guild = message.guild
    channel = message.channel
    if not guild or not isinstance(channel, discord.TextChannel):
        # Chỉ support TextChannel (có webhook)
        # Fallback: reply thường nếu không phải TextChannel
        if isinstance(channel, discord.Thread):
            # Thread không hỗ trợ webhook trực tiếp -> fallback reply thường
            pass
        else:
            return False

    # Kiểm tra RPD lock
    if config.is_rpd_locked():
        _, remaining = config.check_flash_rpd()
        embed = discord.Embed(
            title="😴 Bot đã hết lượt hôm nay!",
            description=(
                f"Hôm nay đã dùng hết **{config.FLASH_RPD_LIMIT}** lượt RPD rồi 🥀\n\n"
                f"Bot sẽ hoạt động trở lại vào **0:00** hôm nay."
            ),
            color=0xFFA500,
        )
        embed.set_footer(text="=)) mai t lại lên sóng!")
        try:
            await message.reply(embed=embed, mention_author=False)
        except:
            pass
        return True

    # Anti-spam? reuse logic ngắn gọn
    now = time.time()
    user_id = message.author.id
    if user_id != config.OWNER_ID:
        if user_id not in config.SPAM_TRACKER:
            config.SPAM_TRACKER[user_id] = {"last_msgs": [], "blocked_until": 0, "last_content": "", "dup_count": 0}
        user_spam = config.SPAM_TRACKER[user_id]
        if now < user_spam["blocked_until"]:
            return True  # chặn lặng lẽ
        # Simple dup & rate check
        is_dup = message.content == user_spam["last_content"] and (now - user_spam.get("last_time", 0) < 10)
        if is_dup:
            user_spam["dup_count"] += 1
        else:
            user_spam["dup_count"] = 1
        user_spam["last_content"] = message.content
        user_spam["last_time"] = now
        user_spam["last_msgs"] = [t for t in user_spam["last_msgs"] if now - t < 7]
        user_spam["last_msgs"].append(now)
        if len(user_spam["last_msgs"]) > 20 or user_spam["dup_count"] >= 4:
            user_spam["blocked_until"] = now + 30
            user_spam["last_msgs"] = []
            user_spam["dup_count"] = 0
            try:
                await channel.send(f"<@{user_id}> Spam clm, cút 30s! 🥀", delete_after=10)
            except:
                pass
            return True

    # --- Build System Prompt cho Character ---
    system_instruction = f"{config.BASE_SYSTEM_PROMPT}\n\n{matched_char['system_prompt']}\n\n{config.META_ROLEPLAY_PROMPT}"
    # Inject GIF instruction nếu chưa có
    if config.GIPHY_ENABLED:
        guild_send_gif = config.GUILD_SETTINGS.get(str(guild.id), {}).get("send_gif", True)
        if guild_send_gif:
            gif_instr = _get_gif_instruction()
            if gif_instr and "GIF" not in system_instruction:
                system_instruction += "\n" + gif_instr

    # --- Xử lý ảnh đính kèm (giống logic thường) ---
    image_parts = []
    for att in message.attachments:
        if att.size > MAX_ATTACHMENT_SIZE:
            continue
        is_image = att.content_type and att.content_type.startswith("image/")
        if not is_image:
            continue
        try:
            image_bytes = await att.read()
            image_parts.append({"mime_type": att.content_type, "data": image_bytes})
        except Exception as e:
            print(f"⚠️ Lỗi đọc attachment character: {e}")

    # --- Build Prompt ---
    try:
        # Guild-specific model settings
        guild_settings = config.GUILD_SETTINGS.get(str(guild.id), {})
        g_max_tokens = guild_settings.get("max_tokens", config.DEFAULT_MAX_TOKENS)
        g_temperature = guild_settings.get("temperature", config.DEFAULT_TEMPERATURE)
        model = config.get_model_for_guild(g_max_tokens, g_temperature, str(guild.id))

        # Clean content: xóa role mention + bot mention
        clean_content = _strip_role_mentions(message.content)
        clean_content = config.strip_bot_mention(clean_content, bot.user.id if bot.user else None).strip()
        # Nếu sau khi strip rỗng và không có ảnh -> bỏ qua
        if not clean_content and not image_parts:
            # Nếu chỉ ping role không kèm text, gợi ý
            clean_content = "Chào"

        author_name = message.author.display_name or message.author.name
        channel_context = get_channel_context(channel.id, max_messages=15)

        # Lấy old_history cho character channel (dùng ctx_key = guild-channel? dùng channel id)
        ctx_key = config.get_context_key(message)
        if ctx_key not in config.chat_history:
            config.chat_history[ctx_key] = []
        old_history = config.chat_history[ctx_key]
        old_history_text = ""
        if old_history:
            history_lines = []
            for item in old_history[-10:]:
                if item["role"] == "user":
                    name = item.get("display_name", "User")
                    history_lines.append(f"{name}: {item['parts'][0]}")
                else:
                    history_lines.append(f"Bot ({matched_char['name']}): {item['parts'][0]}")
            old_history_text = "\n".join(history_lines)

        reply_info = ""
        if message.reference and message.reference.resolved and isinstance(message.reference.resolved, discord.Message):
            replied = message.reference.resolved
            replied_name = getattr(replied.author, "display_name", None) or getattr(replied.author, "name", "Unknown")
            replied_content = getattr(replied, "content", "") or "[không có text]"
            if len(replied_content) > 100:
                replied_content = replied_content[:97] + "..."
            reply_info = f"\n[💬 {author_name} đang trả lời {replied_name}: \"{replied_content}\"]"

        prompt_parts = [system_instruction]
        prompt_parts.append("\n--- LỊCH SỬ CHAT 15 TIN GẦN NHẤT ---")
        prompt_parts.append(channel_context)
        if old_history_text:
            prompt_parts.append("\n--- LỊCH SỬ TƯƠNG TÁC CŨ ---")
            prompt_parts.append(old_history_text)
        if reply_info:
            prompt_parts.append(reply_info)
        prompt_parts.append(f"\n--- TIN NHẮN CỦA {author_name.upper()} (gọi {matched_char['name']}) ---")
        prompt_parts.append(clean_content)
        if message.reference and message.reference.resolved:
            prompt_parts.append("\n⚠️ LƯU Ý: Tin nhắn đang reply người khác. Hãy trả lời phù hợp ngữ cảnh!")
        prompt_parts.append("\nTrả lời ngắn gọn, hài hước, đúng phong cách GenZ, GIỮ ĐÚNG tính cách Character đã giao.")
        if image_parts:
            prompt_parts.extend(image_parts)

        # --- GỌI AI ---
        async with channel.typing():
            response = await model.generate_content_async(prompt_parts)
            response_text = config.extract_response_text(response)
            if not response_text:
                response_text = "T bị câm ngang API r, nói lại phát 🥀"
            response_text = response_text[:2000].strip()

            # GIF parsing (giống event.py chính)
            guild_send_gif = config.GUILD_SETTINGS.get(str(guild.id), {}).get("send_gif", True) if guild else True
            if not guild_send_gif:
                tmp_clean, tmp_q = extract_gif_requests(response_text)
                if tmp_q:
                    response_text = tmp_clean.strip()[:2000] if tmp_clean.strip() else response_text
                gif_urls: List[str] = []
                clean_text, gif_queries = response_text, []
            else:
                clean_text, gif_queries = extract_gif_requests(response_text)
                gif_urls: List[str] = []
                if gif_queries:
                    for search_term, limit in gif_queries:
                        try:
                            urls = await asyncio.to_thread(config.search_gifs, search_term, limit)
                            if urls:
                                gif_urls.extend(urls)
                            else:
                                rand = await asyncio.to_thread(config.get_random_gif, search_term)
                                if rand:
                                    gif_urls.append(rand)
                        except Exception as e:
                            print(f"⚠️ Lỗi fetch GIF character {search_term}: {e}")
                    if not clean_text.strip():
                        tmp = re.sub(r'```(?:json)?\s*\{[^`]*?\}\s*```', '', response_text, flags=re.IGNORECASE|re.DOTALL)
                        tmp = _GIF_INLINE_RE.sub('', tmp).strip()
                        clean_text = tmp if tmp else "🥀"
                    response_text = clean_text.strip()[:2000]
                    print(f"🎬 [Character:{matched_char['name']}] GIF requests: {gif_queries} -> {len(gif_urls)} urls")

            # Avatar tag handling
            if config.has_avatar_tag(response_text):
                response_text = config.remove_avatar_tag(response_text)
                if not response_text:
                    response_text = "🥀"

            # --- WEBHOOK SEND ---
            webhook = await _get_or_create_webhook(channel, bot.user)
            if webhook is None:
                # Fallback: không có quyền webhook -> reply thường với tên character
                embed = discord.Embed(color=0x00F0FF)
                embed.set_author(name=matched_char["name"], icon_url=matched_char.get("avatar_url") or None)
                embed.description = response_text
                if matched_char.get("avatar_url"):
                    embed.set_thumbnail(url=matched_char["avatar_url"])
                embed.set_footer(text="⚠️ Thiếu quyền Manage Webhooks — đã fallback sang embed")
                await message.reply(embed=embed, mention_author=False)
                # GIFs
                if 'gif_urls' in locals() and gif_urls:
                    for url in gif_urls:
                        try:
                            await channel.send(url)
                        except:
                            pass
            else:
                # Chuẩn bị username/avatar — Discord giới hạn 80 ký tự / 1024
                webhook_name = matched_char["name"][:80]
                webhook_avatar = matched_char.get("avatar_url") or None
                # Validate avatar_url còn usable không (nếu rỗng thì không truyền)
                try:
                    # Discord webhook sẽ fetch avatar_url, nếu lỗi sẽ fallback không avatar
                    await webhook.send(
                        content=response_text or "🥀",
                        username=webhook_name,
                        avatar_url=webhook_avatar,
                        allowed_mentions=discord.AllowedMentions.none(),
                        wait=True,
                    )
                except discord.HTTPException as e:
                    print(f"⚠️ Webhook send lỗi (thử không avatar): {e}")
                    # Thử lại không có avatar
                    try:
                        await webhook.send(
                            content=response_text or "🥀",
                            username=webhook_name,
                            allowed_mentions=discord.AllowedMentions.none(),
                            wait=True,
                        )
                    except Exception as e2:
                        print(f"⚠️ Webhook fallback fail: {e2}")
                        await message.reply(response_text or "🥀", mention_author=False)

                # GIFs riêng (webhook không tự gửi link preview? vẫn gửi như message thường)
                if 'gif_urls' in locals() and gif_urls:
                    for url in gif_urls:
                        try:
                            # Gửi qua webhook để giữ vibe character?
                            await webhook.send(
                                content=url,
                                username=webhook_name,
                                avatar_url=webhook_avatar,
                                allowed_mentions=discord.AllowedMentions.none(),
                                wait=True,
                            )
                        except:
                            try:
                                await channel.send(url)
                            except:
                                pass

            # Lưu vào chat_history
            config.chat_history[ctx_key].append(
                {"role": "user", "parts": [clean_content], "user_id": user_id, "display_name": author_name, "user_mention": f"<@{user_id}>", "character": matched_char["name"]}
            )
            config.chat_history[ctx_key].append(
                {"role": "model", "parts": [response_text], "character": matched_char["name"]}
            )
            if len(config.chat_history[ctx_key]) > 15:
                config.chat_history[ctx_key] = config.chat_history[ctx_key][-15:]

            if hasattr(model, 'model_name') and config.is_flash_model(model.model_name):
                config.increment_flash_rpd()

            return True

    except Exception as error:
        error_str = str(error).lower()
        print(f"❌ [Character {matched_char['name']}] Lỗi API: {error}")
        if "429" in error_str or "rate" in error_str or "quota" in error_str or "resource exhausted" in error_str:
            config.lock_rpd_until_midnight()
            embed = discord.Embed(
                title="😴 Bot đã hết lượt hôm nay!",
                description=f"Hôm nay đã dùng hết **{config.FLASH_RPD_LIMIT}** lượt RPD rồi 🥀",
                color=0xFF0040,
            )
            embed.set_footer(text="=)) mai t lại lên sóng!")
            try:
                await message.reply(embed=embed, mention_author=False)
            except:
                pass
            return True
        elif message.author.id == config.OWNER_ID:
            try:
                await channel.send(f"Lỗi nè đại ca: `{error}` 🥀")
            except:
                pass
        return True

# --- HÀM ON_MESSAGE NÂNG CẤP (TỐI ƯU CHO KOYEB) ---
def register_events(bot):
    @bot.event
    async def on_ready():
        print(f"Bot đã đăng nhập với tên: {bot.user.name}")
        print(f"Default Model: {config.DEFAULT_MODEL_ID}")
        # Load memory từ file
        load_memory()
        try:
            # Thử sync commands
            synced = await bot.tree.sync()
            print(f"✅ Đã đồng bộ {len(synced)} lệnh slash.")
            # Log tên các lệnh đã sync
            command_names = [cmd.name for cmd in synced]
            print(f"📋 Các lệnh đã sync: {', '.join(command_names)}")
        except Exception as error:
            print(f"❌ Lỗi đồng bộ lệnh: {error}")
            import traceback
            traceback.print_exc()
    @bot.event
    async def on_guild_join(guild: discord.Guild):
        try:
            owner = await bot.fetch_user(config.OWNER_ID)
            if not owner:
                return
            invite_url = await _build_invite_url(guild)
            if not invite_url:
                invite_url = "https://discord.gg/invalid"
            embed = discord.Embed(
                title="✅ Bot vừa join 1 server mới!",
                color=0x00F0FF,
                description=(
                    f"**Server:** {guild.name}\n"
                    f"**ID:** {guild.id}\n"
                    f"**Số thành viên:** {guild.member_count}\n\n"
                    f"**Link:** [Vào server]({invite_url})"
                ),
            )
            embed.set_thumbnail(url=guild.icon.url if guild.icon else "")
            await owner.send(embed=embed)
        except Exception as error:
            print(f"Lỗi gửi DM khi join server: {error}")

    @bot.event
    async def on_message(message: discord.Message):
        # Bỏ qua tin nhắn của chính bot
        if message.author == bot.user:
            return

        # Bot dùng slash commands (app_commands), không dùng prefix commands
        # Nếu tin nhắn bắt đầu bằng "/" và không phải lệnh hợp lệ, vẫn xử lý reply nếu có mention

        # --- 1. LƯU TIN NHẮN VÀO MEMORY (LUÔN LUÔN) ---
        if message.guild:
            channel_id = message.channel.id
            # Khởi tạo memory cho channel nếu chưa có
            if channel_id not in CHANNEL_MEMORY:
                CHANNEL_MEMORY[channel_id] = deque(maxlen=15)
            
            # Format và lưu tin nhắn
            formatted = format_message_for_memory(message)
            CHANNEL_MEMORY[channel_id].append(formatted)
            
            # Cập nhật thống kê
            guild_id = message.guild.id
            config.MSG_COUNTERS[guild_id] = config.MSG_COUNTERS.get(guild_id, 0) + 1
            
            # Lưu memory sau mỗi 10 tin nhắn mới (giảm I/O, tối ưu cho Koyeb)
            # Dùng module-level counter với lock cho thread-safety
            global _save_counter
            async with _get_save_lock():
                _save_counter += 1
                if _save_counter % 10 == 0:
                    save_memory()
            
        # --- 2. KIỂM TRA CÓ CẦN REPLY KHÔNG ---
        is_dm = message.guild is None
        is_reply_to_bot = (
            message.reference
            and message.reference.resolved
            and message.reference.resolved.author == bot.user
        )
        is_mentioned = bot.user in message.mentions
        
        # Nếu không tag, không reply, không DM -> không xử lý
        if not is_dm and not is_mentioned and not is_reply_to_bot:
            return
            
        # Check global chat_enabled (tắt toàn bộ server + DM)
        if not config.config.is_chat_enabled:
            return
        # Check guild-specific chat_enabled (nếu server đã cài đặt)
        if message.guild:
            guild_settings = config.GUILD_SETTINGS.get(str(message.guild.id), {})
            if guild_settings.get("chat_enabled") is False:
                return

        # === 2a. CHARACTER WEBHOOK SYSTEM: phát hiện @Role Character ===
        # Yêu cầu: khi user @Mention Role của Character -> trigger AI + webhook
        if message.guild and message.role_mentions is not None:
            try:
                guild_chars = config.get_guild_characters(message.guild.id)
                matched_char = None
                # Ưu tiên role_mentions (đã resolve)
                for role in message.role_mentions:
                    char = guild_chars.get(str(role.id))
                    if char:
                        matched_char = char
                        break
                # Fallback: parse thô từ content nếu role_mentions rỗng (thiếu intent/member cache)
                if not matched_char and message.content:
                    for m in _ROLE_MENTION_RE.finditer(message.content):
                        rid = m.group(1)
                        char = guild_chars.get(rid)
                        if char:
                            matched_char = char
                            break
                if matched_char:
                    handled = await _handle_character_mention(bot, message, matched_char)
                    if handled:
                        return
            except Exception as e:
                print(f"⚠️ Character mention handler lỗi: {e}")
                import traceback
                traceback.print_exc()

        # === KIỂM TRA RPD LOCK ===
        if config.is_rpd_locked():
            _, remaining = config.check_flash_rpd()
            embed = discord.Embed(
                title="😴 Bot đã hết lượt hôm nay!",
                description=(
                    f"Hôm nay đã dùng hết **{config.FLASH_RPD_LIMIT}** lượt RPD rồi 🥀\n\n"
                    f"Bot sẽ hoạt động trở lại vào **0:00** hôm nay.\n\n"
                    f"Quay lại vào ngày mai nha! 🕐"
                ),
                color=0xFFA500,
            )
            embed.set_footer(text="=)) mai t lại lên sóng!")
            await message.reply(embed=embed, mention_author=False)
            return

        # --- 3. ANTI-SPAM (GIỮ NGUYÊN) ---
        now = time.time()
        user_id = message.author.id
        if user_id != config.OWNER_ID:
            if user_id not in config.SPAM_TRACKER:
                config.SPAM_TRACKER[user_id] = {
                    "last_msgs": [],
                    "blocked_until": 0,
                    "last_content": "",
                    "dup_count": 0,
                }
            user_spam_data = config.SPAM_TRACKER[user_id]
            
            if now < user_spam_data["blocked_until"]:
                return
                
            is_duplicate = (
                message.content == user_spam_data["last_content"]
                and (now - user_spam_data.get("last_time", 0) < 10)
            )
            
            if is_duplicate:
                user_spam_data["dup_count"] += 1
            else:
                user_spam_data["dup_count"] = 1
                
            user_spam_data["last_content"] = message.content
            user_spam_data["last_time"] = now
            
            user_spam_data["last_msgs"] = [
                timestamp for timestamp in user_spam_data["last_msgs"]
                if now - timestamp < 7
            ]
            user_spam_data["last_msgs"].append(now)
            
            hit_rate_limit = (
                len(user_spam_data["last_msgs"]) > 20
                or user_spam_data["dup_count"] >= 4
            )
            
            if hit_rate_limit:
                user_spam_data["blocked_until"] = now + 30
                user_spam_data["last_msgs"] = []
                user_spam_data["dup_count"] = 0
                await message.channel.send(
                    f"<@{user_id}> Spam clm, cút 30s! 🥀",
                    delete_after=10,
                )
                return

            # Cleanup SPAM_TRACKER định kỳ (giảm memory leak)
            if not hasattr(config, "_spam_cleanup_counter"):
                config._spam_cleanup_counter = 0
            config._spam_cleanup_counter += 1
            if config._spam_cleanup_counter % 100 == 0:
                cutoff = now - 3600  # 1 giờ
                keys_to_del = [
                    uid for uid, data in config.SPAM_TRACKER.items()
                    if data["blocked_until"] < now and not data["last_msgs"]
                ]
                for uid in keys_to_del:
                    del config.SPAM_TRACKER[uid]

        # --- 4. XÂY DỰNG CONTEXT CHO AI ---
        ctx_key = config.get_context_key(message)
        state = config.get_context_state(ctx_key)
        
        # System prompt — BASE luôn áp dụng dù có roleplay hay không
        if state["active"]:
            system_instruction = f"{config.BASE_SYSTEM_PROMPT}\n\n{state['config']['prompt']}\n\n{config.META_ROLEPLAY_PROMPT}"
        else:
            system_instruction = f"{config.BASE_SYSTEM_PROMPT}\n\n{config.DEFAULT_SYSTEM_PROMPT}"
        # Inject GIF instruction fallback nếu BASE chưa có (tránh duplicate)
        _guild_send_gif_for_prompt = True
        if message.guild:
            _guild_send_gif_for_prompt = config.GUILD_SETTINGS.get(str(message.guild.id), {}).get("send_gif", True)
        if config.GIPHY_ENABLED and _guild_send_gif_for_prompt:
            gif_instr = _get_gif_instruction()
            if gif_instr and "GIF" not in system_instruction and "search" not in system_instruction:
                system_instruction += "\n" + gif_instr

        # --- 5. XỬ LÝ ẢNH (AN TOÀN) ---
        image_parts = []
        for attachment in message.attachments:
            # Kiểm tra kích thước (giới hạn 5MB) - kiểm tra trước khi tải để tiết kiệm băng thông
            if attachment.size > MAX_ATTACHMENT_SIZE:
                print(f"⚠️ Bỏ qua attachment quá lớn: {attachment.filename} ({attachment.size} bytes)")
                continue
                
            is_image = attachment.content_type and attachment.content_type.startswith("image/")
            if not is_image:
                continue
            try:
                image_bytes = await attachment.read()
                # Không cần kiểm tra lại kích thước sau khi đọc vì đã kiểm tra attachment.size
                image_parts.append(
                    {"mime_type": attachment.content_type, "data": image_bytes}
                )
            except Exception as e:
                print(f"⚠️ Lỗi đọc attachment: {e}")

        # --- 6. TẠO PROMPT THÔNG MINH (TỐI ƯU TOKEN) ---
        try:
            async with message.channel.typing():
                # Sử dụng guild-specific settings nếu có
                if message.guild:
                    guild_id = str(message.guild.id)
                    guild_settings = config.GUILD_SETTINGS.get(guild_id, {})
                    g_max_tokens = guild_settings.get("max_tokens", config.DEFAULT_MAX_TOKENS)
                    g_temperature = guild_settings.get("temperature", config.DEFAULT_TEMPERATURE)
                    model = config.get_model_for_guild(g_max_tokens, g_temperature, guild_id)
                else:
                    model = config.get_model()
                clean_content = config.strip_bot_mention(
                    message.content,
                    bot.user.id if bot.user else None,
                )
                
                # Nếu ko có nội dung và ko có ảnh thì bỏ qua
                if not clean_content and not image_parts:
                    await message.reply("Sao? Gọi t chi z? 🥀", mention_author=False)
                    return
                if not clean_content and image_parts:
                    clean_content = "Hãy mô tả ảnh này"

                # Lấy thông tin user
                author_name = message.author.display_name or message.author.name
                
                # Lấy context từ channel memory (15 tin gần nhất)
                channel_context = get_channel_context(message.channel.id, max_messages=15)
                
                # Lấy lịch sử chat cũ (để bot nhớ tương tác trước đó)
                if ctx_key not in config.chat_history:
                    config.chat_history[ctx_key] = []
                old_history = config.chat_history[ctx_key]
                
                old_history_text = ""
                if old_history:
                    history_lines = []
                    for item in old_history[-10:]:  # Chỉ lấy 10 tin cuối để tiết kiệm token
                        if item["role"] == "user":
                            name = item.get("display_name", "User")
                            history_lines.append(f"{name}: {item['parts'][0]}")
                        else:
                            history_lines.append(f"Bot: {item['parts'][0]}")
                    old_history_text = "\n".join(history_lines)

                # Kiểm tra reply - kiểm tra kiểu dữ liệu an toàn
                reply_info = ""
                if message.reference and message.reference.resolved:
                    replied = message.reference.resolved
                    # Chỉ xử lý nếu resolved là discord.Message
                    if isinstance(replied, discord.Message):
                        replied_name = getattr(replied.author, "display_name", None) or getattr(replied.author, "name", "Unknown")
                        replied_content = getattr(replied, "content", "") or "[không có text]"
                        if len(replied_content) > 100:
                            replied_content = replied_content[:97] + "..."
                        reply_info = f"\n[💬 {author_name} đang trả lời {replied_name}: \"{replied_content}\"]"

                # --- TẠO PROMPT CHUẨN (TỐI ƯU) ---
                prompt_parts = [system_instruction]
                
                # Context từ channel (QUAN TRỌNG: 15 tin gần nhất)
                prompt_parts.append("\n--- LỊCH SỬ CHAT 15 TIN GẦN NHẤT ---")
                prompt_parts.append(channel_context)
                
                # Context từ tương tác cũ với bot (nếu có)
                if old_history_text:
                    prompt_parts.append("\n--- LỊCH SỬ TƯƠNG TÁC CŨ ---")
                    prompt_parts.append(old_history_text)
                
                # Thông tin reply
                if reply_info:
                    prompt_parts.append(reply_info)
                
                # Tin nhắn hiện tại
                prompt_parts.append(f"\n--- TIN NHẮN CỦA {author_name.upper()} ---")
                prompt_parts.append(clean_content)
                
                # Hướng dẫn cuối
                if message.reference and message.reference.resolved:
                    prompt_parts.append("\n⚠️ LƯU Ý: Tin nhắn này đang reply người khác. Hãy trả lời phù hợp với ngữ cảnh!")
                
                prompt_parts.append("\nTrả lời ngắn gọn, hài hước, đúng phong cách GenZ.")
                
                # Thêm ảnh nếu có
                if image_parts:
                    prompt_parts.extend(image_parts)

                # --- GỌI API ---
                response = await model.generate_content_async(prompt_parts)
                response_text = config.extract_response_text(response)
                
                if not response_text:
                    response_text = "T bị câm ngang API r, nói lại phát 🥀"
                    
                response_text = response_text[:2000].strip()

                # --- GIF PARSING & FETCH (GIPHY via requests) ---
                # Tôn trọng setting send_gif của guild (mặc định True)
                _guild_send_gif = True
                if message.guild:
                    _guild_send_gif = config.GUILD_SETTINGS.get(str(message.guild.id), {}).get("send_gif", True)
                if not _guild_send_gif:
                    # Guild tắt GIF: vẫn strip JSON để không lộ JSON ra channel, nhưng không fetch
                    tmp_clean, tmp_q = extract_gif_requests(response_text)
                    if tmp_q:
                        response_text = tmp_clean.strip()[:2000] if tmp_clean.strip() else response_text
                        # xóa JSON khỏi hiển thị nhưng không gửi GIF
                        print(f"🎬 GIF disabled cho guild {message.guild.id}, đã strip {len(tmp_q)} request(s)")
                    gif_urls: List[str] = []
                    clean_text, gif_queries = response_text, []
                else:
                    clean_text, gif_queries = extract_gif_requests(response_text)
                    gif_urls: List[str] = []
                    if gif_queries:
                        for search_term, limit in gif_queries:
                            try:
                                urls = await asyncio.to_thread(config.search_gifs, search_term, limit)
                                if urls:
                                    gif_urls.extend(urls)
                                else:
                                    rand = await asyncio.to_thread(config.get_random_gif, search_term)
                                    if rand:
                                        gif_urls.append(rand)
                            except Exception as e:
                                print(f"⚠️ Lỗi fetch GIF {search_term}: {e}")
                        if not clean_text.strip():
                            # Nếu text chỉ toàn JSON, fallback lấy text gốc đã xóa JSON
                            tmp = re.sub(r'```(?:json)?\s*\{[^`]*?\}\s*```', '', response_text, flags=re.IGNORECASE|re.DOTALL)
                            tmp = _GIF_INLINE_RE.sub('', tmp).strip()
                            clean_text = tmp if tmp else "🥀"
                        response_text = clean_text.strip()[:2000]
                        print(f"🎬 GIF requests: {gif_queries} -> {len(gif_urls)} urls")

                # --- GỬI REPLY ---
                if config.has_avatar_tag(response_text):
                    response_text = config.remove_avatar_tag(response_text)
                    if not response_text:
                        response_text = "🥀"
                    if bot.user.avatar:
                        embed = discord.Embed(color=0x00F0FF)
                        embed.set_image(url=bot.user.avatar.url)
                        await message.reply(
                            response_text if response_text else "🥀",
                            embed=embed,
                            mention_author=False,
                        )
                    else:
                        await message.reply(
                            response_text if response_text else "Hồn nhiên t khum có avatar 🥀",
                            mention_author=False,
                        )
                else:
                    await message.reply(
                        response_text or "T nghẹn text r 🥀",
                        mention_author=False,
                    )

                # --- GỬI GIFs KÈM THEO (nếu có) ---
                if gif_urls:
                    for url in gif_urls:
                        try:
                            await message.channel.send(url)
                        except Exception as e:
                            print(f"⚠️ Lỗi gửi GIF url {url}: {e}")

                # --- CẬP NHẬT MEMORY VỚI MÔ TẢ ẢNH (NẾU CÓ) ---
                if image_parts and message.guild:
                    description = await _describe_image(image_parts)
                    if description:
                        channel_id = message.channel.id
                        if channel_id in CHANNEL_MEMORY and len(CHANNEL_MEMORY[channel_id]) > 0:
                            # Lấy nội dung gốc của user (không phải "Hãy mô tả ảnh này" đã modify)
                            original_user_text = config.strip_bot_mention(
                                message.content,
                                bot.user.id if bot.user else None,
                            )
                            # Xây dựng memory entry với mô tả ảnh thay vì [📷 Ảnh]
                            author_name = message.author.display_name or message.author.name
                            if original_user_text:
                                updated_msg = f"{author_name}: {original_user_text} [📷 {description}]"
                            else:
                                updated_msg = f"{author_name}: [📷 {description}]"
                            if len(updated_msg) > 200:
                                updated_msg = updated_msg[:197] + "..."
                            CHANNEL_MEMORY[channel_id][-1] = updated_msg

                # Lưu vào chat_history
                config.chat_history[ctx_key].append(
                    {
                        "role": "user",
                        "parts": [clean_content],
                        "user_id": user_id,
                        "display_name": message.author.display_name or message.author.name,
                        "user_mention": f"<@{user_id}>",
                    }
                )
                config.chat_history[ctx_key].append(
                    {
                        "role": "model",
                        "parts": [response_text],
                    }
                )
                if len(config.chat_history[ctx_key]) > 15:
                    config.chat_history[ctx_key] = config.chat_history[ctx_key][-15:]
                
                # Increment RPD nếu dùng flash model
                if hasattr(model, 'model_name') and config.is_flash_model(model.model_name):
                    config.increment_flash_rpd()
                    
        except Exception as error:
            error_str = str(error).lower()
            print(f"Lỗi API: {error}")
            
            # === BẮT LỖI RATE LIMIT (429) ===
            if "429" in error_str or "rate" in error_str or "quota" in error_str or "resource exhausted" in error_str:
                config.lock_rpd_until_midnight()
                embed = discord.Embed(
                    title="😴 Bot đã hết lượt hôm nay!",
                    description=(
                        f"Hôm nay đã dùng hết **{config.FLASH_RPD_LIMIT}** lượt RPD rồi 🥀\n\n"
                        f"Bot sẽ hoạt động trở lại vào **0:00** hôm nay.\n\n"
                        f"Quay lại vào ngày mai nha! 🕐"
                    ),
                    color=0xFF0040,
                )
                embed.set_footer(text="=)) mai t lại lên sóng!")
                await message.reply(embed=embed, mention_author=False)
            elif message.author.id == config.OWNER_ID:
                await message.channel.send(f"Lỗi nè đại ca: `{error}` 🥀")

# --- HÀM PHỤ TRỢ (GIỮ NGUYÊN) ---
async def _build_invite_url(guild: discord.Guild):
    try:
        for channel in guild.channels:
            can_invite = (
                isinstance(channel, discord.TextChannel)
                and channel.permissions_for(guild.me).create_instant_invite
            )
            if can_invite:
                invite = await channel.create_invite(max_age=0, max_uses=0)
                return invite.url
    except Exception:
        return None
    return None