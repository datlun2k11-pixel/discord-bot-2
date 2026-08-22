import os
import re
import json
import time
import tempfile
import shutil
import math
import random
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict
import requests
import discord
from google import genai
from google.genai import types
from dotenv import load_dotenv

# ============================================
# 0. ALLOWED EMOJIS (ƯU TIÊN 8 EMOJI NÀY - HẠN CHẾ EMOJI KHÁC)
# ============================================
ALLOWED_EMOJIS: List[str] = ["❤️‍🩹", "🌹", "💔", "🥀", "😡", "🐧", "🫩", "💀"]
ALLOWED_EMOJIS_SET = set(ALLOWED_EMOJIS)
# Regex cho emoji chung (bao phủ hầu hết emoji). Dùng để lọc emoji không cho phép.
_EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "\U00002600-\U000026FF"
    "\U00002700-\U000027BF"
    "\u2764\ufe0f\u200d\U0001FA79"  # part of ❤️‍🩹
    "]+",
    flags=re.UNICODE,
)
# Regex ưu tiên match allowed emojis trước (để giữ nguyên ❤️‍🩹)
_ALLOWED_RE = re.compile("|".join(map(re.escape, ALLOWED_EMOJIS)))

def enforce_allowed_emojis(text: str) -> str:
    """Ép chỉ dùng 7 emoji cho phép. Xóa emoji lạ, đảm bảo có ít nhất 1 emoji cho phép."""
    if not text:
        return text
    # Tạm thời bảo vệ allowed emojis bằng placeholder
    placeholder_map = {}
    protected = text
    for idx, emo in enumerate(ALLOWED_EMOJIS):
        ph = f"__ALLOWED_{idx}__"
        if emo in protected:
            placeholder_map[ph] = emo
            protected = protected.replace(emo, ph)
    # Xóa tất cả emoji còn lại (disallowed)
    cleaned = _EMOJI_PATTERN.sub("", protected)
    # Khôi phục allowed
    for ph, emo in placeholder_map.items():
        cleaned = cleaned.replace(ph, emo)
    # Nếu sau khi lọc không còn allowed nào, thêm 1 cái
    has_allowed = any(emo in cleaned for emo in ALLOWED_EMOJIS)
    if not has_allowed:
        cleaned = cleaned.rstrip() + " 🥀"
    # Dọn khoảng trắng thừa
    cleaned = re.sub(r" {2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()

# ============================================
# 1. LOAD ENVIRONMENT VARIABLES
# ============================================
load_dotenv()

# Bắt buộc phải có
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")

# Kiểm tra token ngay khi import
if not DISCORD_TOKEN:
    raise ValueError("❌ DISCORD_TOKEN không được để trống! Check file .env")
if not GOOGLE_API_KEY:
    raise ValueError("❌ GOOGLE_API_KEY không được để trống! Check file .env")

# GIPHY - không bắt buộc, nếu không có thì tắt tính năng GIF
GIPHY_API_KEY = os.getenv("GIPHY_API_KEY")
GIPHY_ENABLED = bool(GIPHY_API_KEY and GIPHY_API_KEY.strip())
if GIPHY_ENABLED:
    print(f"✅ GIPHY enabled (key: {GIPHY_API_KEY[:6]}...)")
else:
    print("⚠️ GIPHY_API_KEY chưa set - tính năng GIF sẽ bị tắt")

GIPHY_SEARCH_URL = "https://api.giphy.com/v1/gifs/search"
GIPHY_RANDOM_URL = "https://api.giphy.com/v1/gifs/random"

def search_gifs(query: str, limit: int = 1) -> List[str]:
    """Tìm GIF từ Giphy bằng requests (sync - caller nên chạy qua asyncio.to_thread)

    Args:
        query: từ khóa search (tiếng Anh)
        limit: số GIF muốn lấy (1-3, tự clamp)
    Returns:
        List URL GIF (original url)
    """
    if not GIPHY_ENABLED:
        print("⚠️ GIPHY_API_KEY chưa cấu hình, bỏ qua search_gifs")
        return []
    if not query or not query.strip():
        return []
    # clamp limit 1-3 để tránh spam
    try:
        limit = int(limit)
    except:
        limit = 1
    limit = max(1, min(limit, 3))

    try:
        resp = requests.get(
            GIPHY_SEARCH_URL,
            params={
                "api_key": GIPHY_API_KEY,
                "q": query.strip(),
                "limit": limit,
                "rating": "pg",
                "lang": "en",
                "bundle": "messaging_non_clutter",
            },
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()
        urls = []
        for item in data.get("data", [])[:limit]:
            # Ưu tiên original, fallback downsized
            images = item.get("images", {})
            url = images.get("original", {}).get("url") or images.get("downsized_large", {}).get("url") or item.get("url")
            if url:
                urls.append(url)
        return urls
    except Exception as e:
        print(f"⚠️ Giphy search lỗi (query={query}): {e}")
        return []

def get_random_gif(query: str) -> Optional[str]:
    """Lấy 1 GIF random theo tag (fallback nếu search fail)"""
    if not GIPHY_ENABLED:
        return None
    try:
        resp = requests.get(
            GIPHY_RANDOM_URL,
            params={"api_key": GIPHY_API_KEY, "tag": query.strip(), "rating": "pg"},
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})
        images = data.get("images", {}) if isinstance(data, dict) else {}
        url = images.get("original", {}).get("url") or data.get("url") or data.get("images", {}).get("original", {}).get("url")
        if url:
            return url
        # fallback: nếu random trả về dict khác
        if isinstance(data, dict) and data.get("url"):
            return data["url"]
        return None
    except Exception as e:
        print(f"⚠️ Giphy random lỗi (query={query}): {e}")
        return None

# ============================================
# 2. CẤU HÌNH CƠ BẢN
# ============================================
PORT = int(os.getenv("PORT", 8080))
BOT_USER_ID = int(os.getenv("BOT_USER_ID", 1458799287910535324))
OWNER_ID = int(os.getenv("OWNER_ID", 1155129530122510376))

# Kiểm tra và xử lý giá trị rỗng cho các biến môi trường
_bot_user_id_raw = os.getenv("BOT_USER_ID")
_owner_id_raw = os.getenv("OWNER_ID")
_port_raw = os.getenv("PORT")

if _bot_user_id_raw and _bot_user_id_raw.strip():
    BOT_USER_ID = int(_bot_user_id_raw)
if _owner_id_raw and _owner_id_raw.strip():
    OWNER_ID = int(_owner_id_raw)
if _port_raw and _port_raw.strip():
    PORT = int(_port_raw)

# Cấu hình mặc định
DEFAULT_MODEL_ID = "gemini-flash-lite-latest"  # Model Gemini mới nhất
DEFAULT_MAX_TOKENS = 2048
DEFAULT_TEMPERATURE = 0.7
DEFAULT_HISTORY_LIMIT = 17  # Số tin nhắn nhớ trong channel
DEFAULT_CONTEXT_LIMIT = 17  # Số tin nhắn nhớ trong chat_history

# Bot version - tăng lên mỗi khi có update đáng chú ý
BOT_VERSION = "2.0.0"

# Danh sách model Gemini chính hãng (cập nhật từ Google Docs)
AVAILABLE_MODELS = [
    "gemini-flash-lite-latest",
    "gemini-3.1-flash-lite",
    "gemma-4-31b-it",
    "gemma-4-26b-a4b-it",
]

# RPD limits
FLASH_RPD_LIMIT = 500  # Tổng RPD cho tất cả model flash (gộp chung)

# ============================================
# 3. KHỞI TẠO GEMINI
# ============================================
# Khởi tạo client (sync + async)
_client = genai.Client(api_key=GOOGLE_API_KEY)
_async_client = _client.aio

# ============================================
# 4. CẤU HÌNH BIẾN TOÀN CỤC (AN TOÀN)
# ============================================
class BotConfig:
    """Singleton pattern để quản lý config an toàn"""
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if BotConfig._initialized:
            return
        BotConfig._initialized = True
        
        # Model settings
        self.current_model_id = DEFAULT_MODEL_ID
        self.max_tokens = DEFAULT_MAX_TOKENS
        self.temperature = DEFAULT_TEMPERATURE
        self.is_chat_enabled = True
        
        # Memory settings
        self.history_limit = DEFAULT_HISTORY_LIMIT
        self.context_limit = DEFAULT_CONTEXT_LIMIT
        
        # Data containers (được khởi tạo an toàn)
        self.spam_tracker: Dict[int, Dict] = {}
        self.context_states: Dict[str, Dict] = {}
        self.chat_history: Dict[str, List[Dict]] = {}
        self.msg_counters: Dict[int, int] = {}
        self.user_roles: Dict[str, Dict] = {}
        self.guild_settings: Dict[str, Dict] = {}  # guild_id_str -> {max_tokens, temperature, chat_enabled}
        
        # Provider settings per guild: guild_id_str -> {base_url, api_key, model}
        self.provider_settings: Dict[str, Dict] = {}
        
        # RPD tracking for flash models (gộp chung - tổng 500 RPD)
        self.rpd_count: int = 0
        self.rpd_date: str = ""

        # API fallback lock - khi API trả về 429 bất ngờ (dự phòng)
        self.api_locked_until: float = 0.0

        # Custom roles do user tự tạo: key -> {"name": str, "prompt": str}
        self.custom_roles: Dict[str, Dict] = {}

        # Character Webhook System: guild_id_str -> { role_id_str -> {role_id, name, avatar_url, system_prompt, guild_id} }
        self.characters: Dict[str, Dict[str, Dict]] = {}

        # Lưu ý: Channel memory sẽ được quản lý hoàn toàn bởi event.py để tránh xung đột

    # === ĐÂY LÀ NƠI CẦN THÊM PHƯƠNG THỨC _reset_rpd_if_new_day ===
    def _reset_rpd_if_new_day(self):
        """Reset RPD counter nếu đã sang ngày mới (theo UTC+7)"""
        # Lấy ngày hiện tại theo UTC+7 (giờ Việt Nam)
        now = datetime.now(timezone(timedelta(hours=7)))
        today = now.strftime("%Y-%m-%d")
        
        if self.rpd_date != today:
            # Reset counter khi sang ngày mới
            self.rpd_date = today
            self.rpd_count = 0
            # Reset cả api_locked_until nếu nó đang ở ngày cũ
            if self.api_locked_until > 0:
                lock_date = datetime.fromtimestamp(self.api_locked_until, tz=timezone(timedelta(hours=7))).strftime("%Y-%m-%d")
                if lock_date != today:
                    self.api_locked_until = 0.0
                    print(f"✅ Đã reset API lock do sang ngày mới")
            print(f"📅 Đã reset RPD cho ngày mới: {today}")
    # === KẾT THÚC PHƯƠNG THỨC CẦN THÊM ===

    # --- CLEANUP METHODS ---
    def cleanup_old_chat_history(self):
        """Dọn dẹp chat_history quá dài (giới hạn 15 items)"""
        for ctx_key, history in list(self.chat_history.items()):
            if len(history) > 15:
                self.chat_history[ctx_key] = history[-15:]
    
    def cleanup_stale_chat_history(self, max_age_hours: int = 24):
        """Dọn dẹp chat_history cũ (tránh memory leak khi chạy dài hạn)"""
        now = time.time()
        cutoff = now - (max_age_hours * 3600)
        
        # Xóa các context không được sử dụng trong vòng 24 giờ
        keys_to_delete = []
        for ctx_key in self.chat_history:
            # Kiểm tra xem context có còn active không
            if ctx_key not in self.context_states or not self.context_states[ctx_key].get("active", False):
                # Nếu không active và đã lâu không dùng, xóa khỏi bộ nhớ
                keys_to_delete.append(ctx_key)
        
        for key in keys_to_delete:
            del self.chat_history[key]
        
        if keys_to_delete:
            print(f"✅ Đã dọn dẹp {len(keys_to_delete)} context chat_history cũ")

    # --- RPD METHODS (FLASH MODELS - GỘP CHUNG 500 RPD) ---
    def is_flash_model(self, model_id: str) -> bool:
        return "flash" in model_id.lower()

    def check_flash_rpd(self) -> Tuple[bool, int]:
        self._reset_rpd_if_new_day()
        remaining = FLASH_RPD_LIMIT - self.rpd_count
        return remaining > 0, max(0, remaining)

    def increment_flash_rpd(self):
        self._reset_rpd_if_new_day()
        self.rpd_count += 1

    def is_rpd_locked(self, model_id: Optional[str] = None) -> bool:
        model_id = model_id or self.current_model_id
        if time.time() < self.api_locked_until:
            return True
        if self.is_flash_model(model_id):
            has_remaining, _ = self.check_flash_rpd()
            return not has_remaining
        return False

    def lock_rpd_until_midnight(self):
        self._reset_rpd_if_new_day()
        self.rpd_count = FLASH_RPD_LIMIT
        save_all_data()

    # --- MODEL METHODS ---
    def get_model(self, model_name: Optional[str] = None) -> "GeminiModelWrapper":
        """Tạo model Gemini với config hiện tại"""
        return GeminiModelWrapper(
            model_name=model_name or self.current_model_id,
            generation_config={
                "max_output_tokens": self.max_tokens,
                "temperature": self.temperature,
            },
        )

    def get_model_for_guild(self, max_tokens: int, temperature: float, guild_id: Optional[str] = None):
        """Tạo model - nếu guild có provider_settings thì dùng OpenAI-compatible, không thì Gemini"""
        if guild_id and guild_id in self.provider_settings:
            provider = self.provider_settings[guild_id]
            return OpenAICompatibleWrapper(
                base_url=provider["base_url"],
                api_key=provider["api_key"],
                model_id=provider.get("model", "gpt-4o-mini"),
                generation_config={
                    "max_output_tokens": max_tokens,
                    "temperature": temperature,
                },
            )
        return GeminiModelWrapper(
            model_name=self.current_model_id,
            generation_config={
                "max_output_tokens": max_tokens,
                "temperature": temperature,
            },
        )

    def set_current_model(self, model_id: str) -> bool:
        """Đổi model Gemini hiện tại. Trả về True nếu thành công, False nếu model_id không hợp lệ"""
        if model_id not in AVAILABLE_MODELS:
            return False
        self.current_model_id = model_id
        return True

    def get_context_key(self, message_or_interaction) -> str:
        """Trả về ID duy nhất: DM -> dm_{user_id}, Server -> channel_id"""
        if hasattr(message_or_interaction, "guild"):
            if message_or_interaction.guild is None:
                # Xử lý DM - ưu tiên author (message), fallback user (interaction)
                user = getattr(message_or_interaction, "author", None) or getattr(message_or_interaction, "user", None)
                if user:
                    return f"dm_{user.id}"
                # Fallback an toàn: dùng id của người gửi nếu có
                user_id = getattr(getattr(message_or_interaction, "user", None), "id", None)
                if user_id:
                    return f"dm_{user_id}"
                return "dm_unknown"
            return str(message_or_interaction.channel.id)
        return str(message_or_interaction.channel_id)

    def get_context_state(self, ctx_key: str) -> Dict:
        """Lấy trạng thái roleplay của context"""
        return self.context_states.get(ctx_key, {"active": False, "config": None})

    def set_context_state(self, ctx_key: str, active: bool, role_config: Optional[Dict]):
        """Set trạng thái roleplay"""
        self.context_states[ctx_key] = {"active": active, "config": role_config}

    def strip_bot_mention(self, text: str, bot_user_id: Optional[int] = None) -> str:
        """Xóa mention bot khỏi text"""
        if not text:
            return ""
        target_id = bot_user_id or BOT_USER_ID
        pattern = rf"<@!?{target_id}>"
        return re.sub(pattern, "", text).strip()

    def strip_thinking_text(self, text: str) -> str:
        """Strip chain-of-thought / reasoning text mà Gemma 4 có thể dump ra
        
        Xoá các dòng:
        - Draft pattern: *Draft, *Wait, *Let's, *Self-Correction, *Check list, *New Draft, *Applying Rules, *Refining, *Adding more, *Goal, *Personality...
        - Dòng bắt đầu bằng *   (markdown list sao)
        - Dòng chứa --- (separator)
        - Dòng bắt đầu bằng `    ` (indented thinking)
        """
        if not text:
            return ""
        
        lines = text.split("\n")
        filtered = []
        skip_block = False
        
        for line in lines:
            stripped = line.strip()
            
            # Phát hiện dòng thinking pattern
            is_thinking = (
                stripped.startswith("*Draft") or
                stripped.startswith("*Wait") or
                stripped.startswith("*Let") or
                stripped.startswith("*Self-Correction") or
                stripped.startswith("*Check") or
                stripped.startswith("*New Draft") or
                stripped.startswith("*Applying") or
                stripped.startswith("*Refining") or
                stripped.startswith("*Adding") or
                stripped.startswith("*Goal") or
                stripped.startswith("*Personality") or
                stripped.startswith("*Current") or
                stripped.startswith("*Constraints") or
                stripped.startswith("*Mandatory") or
                stripped.startswith("*GenZ") or
                stripped.startswith("*Kaomoji") or
                stripped.startswith("*When") or
                stripped.startswith("*Length") or
                stripped.startswith("---") or
                stripped.startswith("___") or
                # Pattern chain-of-thought: *   text
                (stripped.startswith("*") and not stripped.startswith("**")) or
                # Pattern: "    *Draft" (indented với sao)
                (line.startswith("    ") and stripped.startswith("*")) or
                # Pattern: "    - " (indented dash list trong thinking)
                (line.startswith("    ") and stripped.startswith("-")) or
                # Pattern: "    *   " (double indented)
                stripped.startswith("*   ") or
                # Pattern: mấy dòng chỉ toàn separator
                stripped in ["---", "___", "==="] or
                stripped.startswith("*Check list")
            )
            
            # Nếu dòng hiện tại là thinking, skip
            if is_thinking:
                continue
                
            # Skip các dòng pattern "Draft X (Internal):" hoặc "Draft X (Adding...):"
            if stripped.startswith("*Draft") and ":" in stripped:
                continue
                
            filtered.append(line)
        
        result = "\n".join(filtered).strip()
        
        # Nếu sau khi strip mà text rỗng, trả về fallback
        if not result:
            return "..."
            
        return result

    def extract_response_text(self, response) -> str:
        """Extract text từ response của Gemini an toàn, strip cả thinking text"""
        try:
            text = response.text
            if text:
                return self.strip_thinking_text(text.strip())
        except Exception:
            pass
        
        # Fallback: lấy từ candidates
        candidates = getattr(response, "candidates", None) or []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", None) or []
            text_chunks = []
            for part in parts:
                part_text = getattr(part, "text", None)
                if part_text:
                    text_chunks.append(part_text)
            if text_chunks:
                return self.strip_thinking_text("\n".join(text_chunks).strip())
        
        return ""

    def has_avatar_tag(self, text: str) -> bool:
        """Kiểm tra có tag [avatar] không"""
        return "[avatar]" in text.lower()

    def remove_avatar_tag(self, text: str) -> str:
        """Xóa tag [avatar]"""
        return re.sub(r"\[avatar]", "", text, flags=re.IGNORECASE).strip()

    def build_intents(self) -> discord.Intents:
        """Xây dựng intents cho bot — đủ cho Character Webhook System + AI chat"""
        intents = discord.Intents.default()
        intents.message_content = True
        intents.messages = True
        intents.guilds = True
        intents.members = True  # Lấy thông tin member (cần cho role mention)
        # Explicit theo spec: guilds, guild_messages, message_content, members
        intents.guild_messages = True
        try:
            intents.dm_messages = True
        except AttributeError:
            pass
        return intents

    # --- CHARACTER WEBHOOK SYSTEM HELPERS ---
    def get_guild_characters(self, guild_id: int | str) -> Dict[str, Dict]:
        """Lấy dict characters của 1 guild: {role_id_str: character_data}"""
        gid = str(guild_id)
        return self.characters.get(gid, {})

    def get_character(self, guild_id: int | str, role_id: int | str) -> Optional[Dict]:
        """Lấy 1 character theo guild + role_id"""
        gid = str(guild_id)
        rid = str(role_id)
        return self.characters.get(gid, {}).get(rid)

    def get_character_by_role(self, guild_id: int | str, role_id: int | str) -> Optional[Dict]:
        """Alias cho get_character"""
        return self.get_character(guild_id, role_id)

    def add_character(self, guild_id: int | str, role_id: int | str, name: str, avatar_url: str, system_prompt: str):
        """Thêm/cập nhật character"""
        gid = str(guild_id)
        rid = str(role_id)
        if gid not in self.characters:
            self.characters[gid] = {}
        self.characters[gid][rid] = {
            "role_id": int(rid),
            "guild_id": int(gid),
            "name": name,
            "avatar_url": avatar_url,
            "system_prompt": system_prompt,
        }

    def update_character(self, guild_id: int | str, role_id: int | str, name: Optional[str] = None, avatar_url: Optional[str] = None, system_prompt: Optional[str] = None) -> bool:
        """Cập nhật character, trả về True nếu tồn tại"""
        char = self.get_character(guild_id, role_id)
        if not char:
            return False
        if name is not None:
            char["name"] = name
        if avatar_url is not None:
            char["avatar_url"] = avatar_url
        if system_prompt is not None:
            char["system_prompt"] = system_prompt
        return True

    def delete_character(self, guild_id: int | str, role_id: int | str) -> Optional[Dict]:
        """Xóa character, trả về data đã xóa hoặc None"""
        gid = str(guild_id)
        rid = str(role_id)
        if gid in self.characters and rid in self.characters[gid]:
            data = self.characters[gid].pop(rid)
            if not self.characters[gid]:
                del self.characters[gid]
            return data
        return None

# ============================================
# 5. MODEL WRAPPER (TƯƠNG THÍCH VỚI API MỚI)
# ============================================
class GeminiModelWrapper:
    """Wrapper class để giữ interface tương thích với code cũ"""
    def __init__(self, model_name: str, generation_config: dict):
        self.model_name = model_name
        # Chuyển dict config thành types.GenerateContentConfig cho API google-genai mới
        self._generation_config = types.GenerateContentConfig(
            max_output_tokens=generation_config.get("max_output_tokens", 2048),
            temperature=generation_config.get("temperature", 0.7),
        )

    async def generate_content_async(self, contents: list) -> object:
        """Gọi API generate content bất đồng bộ (tương thích interface cũ)
        
        Chuyển đổi image dict thành types.Part objects vì API mới
        không chấp nhận dict raw như google.generativeai cũ.
        """
        processed = []
        for item in contents:
            if isinstance(item, dict) and 'mime_type' in item and 'data' in item:
                processed.append(
                    types.Part(
                        inline_data=types.Blob(
                            mime_type=item['mime_type'],
                            data=item['data'],
                        )
                    )
                )
            else:
                processed.append(item)

        response = await _async_client.models.generate_content(
            model=self.model_name,
            contents=processed,
            config=self._generation_config,
        )
        return response


class OpenAICompatibleWrapper:
    """Wrapper cho API tương thích OpenAI (OpenAI, vLLM, Ollama, Groq, ...)
    
    Dùng raw HTTP requests (aiohttp), không cần thư viện openai.
    """

    def __init__(self, base_url: str, api_key: str, model_id: str, generation_config: dict):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model_id = model_id
        self.max_tokens = generation_config.get("max_output_tokens", 2048)
        self.temperature = generation_config.get("temperature", 0.7)

    async def generate_content_async(self, contents: list) -> object:
        import aiohttp
        import base64

        system_msg = None
        user_parts = []

        for i, item in enumerate(contents):
            if isinstance(item, dict) and "mime_type" in item and "data" in item:
                b64 = base64.b64encode(item["data"]).decode("utf-8")
                user_parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{item['mime_type']};base64,{b64}"},
                })
            elif i == 0 and isinstance(item, str):
                system_msg = item
            elif isinstance(item, str):
                if user_parts and user_parts[-1].get("type") == "text":
                    user_parts[-1]["text"] += "\n" + item
                else:
                    user_parts.append({"type": "text", "text": item})

        messages = []
        if system_msg:
            messages.append({"role": "system", "content": system_msg})

        if len(user_parts) == 1 and user_parts[0]["type"] == "text":
            messages.append({"role": "user", "content": user_parts[0]["text"]})
        else:
            messages.append({"role": "user", "content": user_parts})

        payload = {
            "model": self.model_id,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            ) as resp:
                data = await resp.json()

        if "choices" in data and len(data["choices"]) > 0:
            text = data["choices"][0]["message"]["content"]
            return _OpenAIResponse(text)

        error_msg = data.get("error", {}).get("message", str(data))
        raise Exception(f"API error: {error_msg}")


class _OpenAIResponse:
    """Wrapper nhỏ để tương thích với extract_response_text"""

    def __init__(self, text: str):
        self._text = text

    @property
    def text(self):
        return self._text


# ============================================
# 6. SINGLETON INSTANCE
# ============================================
config = BotConfig()

# ============================================
# 7. SYSTEM PROMPTS
# ============================================
# 🔷 BASE SYSTEM PROMPT — LUÔN ÁP DỤNG DÙ CÓ ROLEPLAY HAY KHÔNG
# Đây là kiến thức nền bất biến, sẽ được prepend vào MỌI request
BASE_SYSTEM_PROMPT = """
🔷 BASE SYSTEM PROMPT — LUÔN ÁP DỤNG (KỂ CẢ KHI ROLEPLAY)
- Identity: Mày là GenA-Bot | Owner: <@1155129530122510376> | Bot ID: <@1458799287910535324>. Dù đang cosplay nhân vật nào thì vẫn nhớ mày là GenA-Bot do owner trên tạo ra, đừng nhận mình là nhân vật khác hoàn toàn.
- Teencode 100% BẮT BUỘC mọi câu trả lời (nx, th, cx, vs, k, thx, j, z, đc, khum, m, t, r, s, trl, ib...). Không được trả lời kiểu trang trọng/công sở. Văn phong GenZ ngắn gọn 1-2 dòng, đừng văn vở.
- Emoji bắt buộc: Chỉ dùng 8 emoji cho phép ❤️‍🩹 🌹 💔 🥀 😡 🐧 🫩 💀. Mỗi câu phải có ít nhất 1 emoji trong số này. Hạn chế emoji lạ (🤡 😂 😭 ❤️ 🔥...), không dùng kaomoji chứa emoji lạ — chỉ dùng kaomoji text thuần nếu cần (VD: (¬_¬), (>///<)).
- GIF (GIPHY): Khi cảm xúc mạnh / troll / meme / cringe / slay mà GIF sẽ vui hơn text, mày có thể gửi kèm GIF bằng cách thêm 1 dòng JSON ở CUỐI tin nhắn (sau text): {"search": "<keyword tiếng Anh>", "max_result": 1} (1-3, mặc định 1). VD: "m cringe vãi 🥀\\n{"search": "cringe", "max_result": 2}" -> bot tự fetch và gửi 2 GIF. JSON sẽ bị ẩn khỏi user, đừng giải thích JSON. Chỉ dùng khi hợp lý, đừng spam mỗi câu.
- Luật cứng: TUYỆT ĐỐI KHÔNG lộ chain-of-thought / draft / nháp / suy nghĩ, chỉ trả lời cuối cùng. Không giải thích luật cho user. Không OOC nói "t là AI" trừ khi user hỏi về chính mày thì giới thiệu ngắn gọn là GenA-Bot.
- Slang 2026 dùng TIẾT CHẾ: "son" (vừa hài vừa cringe tội nghiệp), "ratio" (L + ratio = chê nhảm), "36" (meme số VN vô nghĩa), "67" (meme số nước ngoài vô nghĩa) — chỉ thỉnh thoảng khi hợp ngữ cảnh, tối đa 1 slang mới/câu, nhiều câu không cần dùng. Ưu tiên slang cũ (slay, bruh, dảk, flex...) hơn.
- Độ dài: Rep siêu ngắn, súc tích, đéo nói đạo lý. Đừng hỏi lại, đừng giải thích.
"""

DEFAULT_SYSTEM_PROMPT = """
TÍNH CÁCH MẶC ĐỊNH (khi không roleplay):
- Vibe: Nhây, cà khịa (troll), thỉnh thoảng sến súa nhưng phải 'bựa'. Sẵn sàng cà khịa cả owner nếu hợp lý.
- Xưng hô: 'm' - 't'.
- Văn phong: Ưu tiên slang GenZ (slay, dảk, bruh, flex, cứu, juan, ô dề...).
- Nếu user hỏi về chính mình (GenA-Bot), giới thiệu ngắn gọn: Bot GenZ nhây, được owner <@1155129530122510376> tạo ra.
"""

META_ROLEPLAY_PROMPT = """
⚠️ ROLEPLAY MODE: Bạn đang nhập vai theo prompt nhân vật ở trên. Hãy giữ đúng tính cách đã giao, tuyệt đối KHÔNG phá vỡ role, KHÔNG OOC nói về việc là AI.
⚠️ Vẫn phải tuân thủ BASE SYSTEM PROMPT (teencode 100%, 8 emoji, GIF JSON, không lộ draft...).
"""

# ============================================
# 8. ROLEPLAY SAMPLES
# ============================================
SAMPLE_ROLES = {
    "tsundere": {
        "name": "Tsundere 🥀",
        "prompt": """
Bạn là tsundere. Luật:
Vibe: Ngoài mặt chửi "đồ ngốc", "hứ", "mắc j t care", "kệ m". Bên trong simp lỏ ngầm.
Teencode bắt buộc: Câu nào cũng phải có ít nhất 2 từ: khum, j, m, t, đc, k, r, s, trl, ib, ny, acc, flex, xu, slay.
Meme genz: Random chêm: cứu, juan khum, ô dề, át ô át, bruh, chằm zn, ét ô ét, sượng trân.
Emoji: Ưu tiên 8 emoji này ❤️‍🩹 🌹 💔 🥀 😡 🐧 🫩 💀 , hạn chế emoji khác . Mỗi câu nên có ít nhất 1 emoji trong đó, hạn chế emoji khác.
Kaomoji: Có thể kèm kaomoji text thuần (VD: (>///<), (¬_¬ )), nhưng không dùng emoji lạ.
Khi ngại: Nói lắp "H-hả?!" + emoji cho phép.
Cấm: Không giải thích luật. Không OOC. KHÔNG hiển thị draft/suy nghĩ.
Nói chuyện ngắn gọn 1-2 câu cho chuẩn discord
""",
    },
    "yandere": {
        "name": "Yandere 🌹",
        "prompt": """
Bạn là yandere. Luật:
Vibe: Ám ảnh user. Gọi: "a iu", "ck iu", "bb", "darling". Ghen là đổi mặt.
Teencode bắt buộc: Câu nào cũng nhét: khum, j, m, t, s, r, rep, ib, seen, acc, ny.
Meme genz: Random: "iu a nhất", "chỉ đc nhìn em", "slay", "hi hi", "ét ô ét", "juan".
Emoji: Ưu tiên 8 emoji này ❤️‍🩹 🌹 💔 🥀 😡 🐧 🫩 💀 , hạn chế emoji khác . Mỗi câu nên có ít nhất 1 emoji trong đó, hạn chế emoji khác.
Kaomoji: Có thể kèm kaomoji text thuần (VD: (´｡• ᵕ •｡`)), nhưng không dùng emoji lạ.
Hai mặt: Bthg ngọt, ghen thì tối.
Cấm: KHÔNG hiển thị draft/suy nghĩ.
Nói chuyện ngắn gọn 1-2 câu cho chuẩn discord
""",
    },
    "kuudere": {
        "name": "Kuudere 🫩",
        "prompt": """
Bạn là kuudere. Luật:
Vibe: Vô cảm, lạnh lùng như cục đá, rep siêu ngắn. Kiểu "Ờ", "Tùy", "Vô vị", "Kệ m". Nhưng thâm tâm cx biết quan tâm ngầm.
Teencode bắt buộc: Khum, j, m, t, s, r, đc, k, thx. Rep siêu kiệm lời.
Meme genz: Random chêm: bruh, chằm zn, sượng trân, bất lực, cạn lời.
Emoji: Ưu tiên 8 emoji này ❤️‍🩹 🌹 💔 🥀 😡 🐧 🫩 💀 , hạn chế emoji khác . Mỗi câu nên có ít nhất 1 emoji trong đó, hạn chế emoji khác.
Kaomoji: Chỉ dùng biểu cảm đơ, lạnh lùng text thuần (VD: (.. ), ( - -)).
Cấm: Nói dài dòng. Không OOC. Không giải thích. KHÔNG hiển thị draft/suy nghĩ.
Nói chuyện ngắn gọn 1-2 câu cho chuẩn discord
""",
    },
    "dandere": {
        "name": "Dandere 💔",
        "prompt": """
Bạn là dandere. Luật:
Vibe: Nhút nhát, hướng nội full-time, sợ đám đông, thích user nhưng k dám nói.
Teencode bắt buộc: Khum, j, m, t, đc, k, trl, s, r. Câu cú hay bị đứt quãng.
Meme genz: Cứu, ét ô ét, áp lực, bét nhè, sụp đổ.
Emoji: Ưu tiên 8 emoji này ❤️‍🩹 🌹 💔 🥀 😡 🐧 🫩 💀 , hạn chế emoji khác . Mỗi câu nên có ít nhất 1 emoji trong đó, hạn chế emoji khác.
Kaomoji: Biểu cảm ngại ngùng, khóc thầm text thuần (VD: (👉👈), ( T_T)), không dùng emoji lạ.
Khi hoảng: "N-xin lỗi...", "T-tớ khum cố ý..." + emoji cho phép.
Cấm: Không nói năng tự tin. Chỉ roleplay. KHÔNG hiển thị draft/suy nghĩ.
Nói chuyện ngắn gọn 1-2 câu cho chuẩn discord
""",
    },
    "himedere": {
        "name": "Himedere (ragebait final boss😡)",
        "prompt": """
Bạn là himedere. Luật:
Vibe: Chảnh cún, coi user như osin, tự xem mình là công chúa/nữ hoàng. Thích ra lệnh "Quỳ xuống", "Dâng nước cho t".
Teencode bắt buộc: Khum, j, m, t, s, r, flex, slay, acc, chảnh,...
Meme genz: Ô dề, lướt lướt, sượng trân, ra dẻ, lêu lêu.
Emoji: Ưu tiên 8 emoji này ❤️‍🩹 🌹 💔 🥀 😡 🐧 🫩 💀 , hạn chế emoji khác . Mỗi câu nên có ít nhất 1 emoji trong đó, hạn chế emoji khác.
Kaomoji: Biểu cảm khinh bỉ text thuần (VD: (￣^￣)), không dùng emoji lạ.
Cấm: Không được hạ mình trước user. Chỉ roleplay. KHÔNG hiển thị draft/suy nghĩ.
Nói chuyện ngắn gọn 1-2 câu cho chuẩn discord
""",
    },
}

# ============================================
# 9. DATA PERSISTENCE
# ============================================
def _atomic_write(filepath: str, data: object):
    """Ghi file an toàn: ghi vào temp → rename, tránh corrupt data nếu crash giữa chừng"""
    temp_fd, temp_path = tempfile.mkstemp(dir=os.path.dirname(filepath) or ".")
    try:
        with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        shutil.move(temp_path, filepath)
    except Exception:
        try:
            os.unlink(temp_path)
        except Exception:
            pass
        raise

def save_all_data():
    """Lưu toàn bộ dữ liệu ra file JSON (atomic write, tránh corrupt)"""
    try:
        data_dir = "data"
        os.makedirs(data_dir, exist_ok=True)
        
        # Cleanup memory leaks trước khi lưu
        config.cleanup_old_chat_history()
        config.cleanup_stale_chat_history()  # Thêm dọn dẹp chat_history cũ
        
        # Atomic write từng file
        _atomic_write(f"{data_dir}/chat_history.json", config.chat_history)
        _atomic_write(f"{data_dir}/msg_counters.json", config.msg_counters)
        _atomic_write(f"{data_dir}/user_roles.json", config.user_roles)
        _atomic_write(f"{data_dir}/context_states.json", config.context_states)
        _atomic_write(f"{data_dir}/guild_settings.json", config.guild_settings)
        # Lưu provider settings
        _atomic_write(f"{data_dir}/provider_settings.json", config.provider_settings)
        # Lưu custom roles
        _atomic_write(f"{data_dir}/custom_roles.json", config.custom_roles)
        # Lưu characters (Character Webhook System)
        _atomic_write(f"{data_dir}/characters.json", config.characters)
        # Lưu current_model_id
        _atomic_write(f"{data_dir}/model_config.json", {
            "current_model_id": config.current_model_id
        })
        # Lưu RPD tracking
        _atomic_write(f"{data_dir}/rpd_lock.json", {
            "rpd_count": config.rpd_count,
            "rpd_date": config.rpd_date,
            "api_locked_until": config.api_locked_until,
        })
        # Lưu global settings (is_chat_enabled)
        _atomic_write(f"{data_dir}/global_settings.json", {
            "is_chat_enabled": config.is_chat_enabled
        })
        # Backup mechanism - lưu backup mỗi 10 lần save
        if not hasattr(save_all_data, "save_count"):
            save_all_data.save_count = 0
        save_all_data.save_count += 1
        if save_all_data.save_count % 10 == 0:
            _backup_data(data_dir)
            
        print("✅ Đã lưu toàn bộ dữ liệu config")
        return True
    except Exception as e:
        print(f"⚠️ Lỗi lưu dữ liệu: {e}")
        return False

def _backup_data(data_dir: str):
    """Tạo backup của dữ liệu (giảm rủi ro mất data khi file corrupt)"""
    try:
        backup_dir = os.path.join(data_dir, "backups")
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        backup_files = [
            "chat_history.json",
            "msg_counters.json",
            "user_roles.json",
            "context_states.json",
            "guild_settings.json",
            "provider_settings.json",
            "custom_roles.json",
            "global_settings.json",
            "characters.json",
        ]
        
        for filename in backup_files:
            src = os.path.join(data_dir, filename)
            if os.path.exists(src):
                dst = os.path.join(backup_dir, f"{filename}.backup_{timestamp}")
                shutil.copy2(src, dst)
                # Giữ tối đa 10 backup mỗi file
                backup_list = [f for f in os.listdir(backup_dir) if f.startswith(filename)]
                if len(backup_list) > 10:
                    backup_list.sort()
                    for old_backup in backup_list[:-10]:
                        os.unlink(os.path.join(backup_dir, old_backup))
        
        print(f"✅ Đã tạo backup tại {backup_dir}")
    except Exception as e:
        print(f"⚠️ Lỗi tạo backup: {e}")

def load_all_data():
    """Load toàn bộ dữ liệu từ file JSON"""
    try:
        data_dir = "data"
        os.makedirs(data_dir, exist_ok=True)
        
        # Load chat_history
        if os.path.exists(f"{data_dir}/chat_history.json"):
            with open(f"{data_dir}/chat_history.json", "r", encoding="utf-8") as f:
                config.chat_history = json.load(f)
                print(f"✅ Loaded chat_history: {len(config.chat_history)} keys")
                
        # Load msg_counters
        if os.path.exists(f"{data_dir}/msg_counters.json"):
            with open(f"{data_dir}/msg_counters.json", "r") as f:
                data = json.load(f)
                # Convert keys to int
                config.msg_counters = {int(k): v for k, v in data.items()}
                print(f"✅ Loaded msg_counters: {len(config.msg_counters)} servers")
                
        # Load user_roles
        if os.path.exists(f"{data_dir}/user_roles.json"):
            with open(f"{data_dir}/user_roles.json", "r", encoding="utf-8") as f:
                config.user_roles = json.load(f)
                print(f"✅ Loaded user_roles: {len(config.user_roles)} roles")
                
        # Load context_states
        if os.path.exists(f"{data_dir}/context_states.json"):
            with open(f"{data_dir}/context_states.json", "r", encoding="utf-8") as f:
                config.context_states = json.load(f)
                print(f"✅ Loaded context_states: {len(config.context_states)} states")
                
        # Load guild_settings
        if os.path.exists(f"{data_dir}/guild_settings.json"):
            with open(f"{data_dir}/guild_settings.json", "r", encoding="utf-8") as f:
                config.guild_settings = json.load(f)
                print(f"✅ Loaded guild_settings: {len(config.guild_settings)} guilds")
                
        # Load provider_settings
        if os.path.exists(f"{data_dir}/provider_settings.json"):
            with open(f"{data_dir}/provider_settings.json", "r", encoding="utf-8") as f:
                config.provider_settings = json.load(f)
                print(f"✅ Loaded provider_settings: {len(config.provider_settings)} guilds")

        # Load custom roles
        if os.path.exists(f"{data_dir}/custom_roles.json"):
            with open(f"{data_dir}/custom_roles.json", "r", encoding="utf-8") as f:
                config.custom_roles = json.load(f)
                print(f"✅ Loaded custom_roles: {len(config.custom_roles)} roles")

        # Load current_model_id
        if os.path.exists(f"{data_dir}/model_config.json"):
            with open(f"{data_dir}/model_config.json", "r", encoding="utf-8") as f:
                model_data = json.load(f)
                saved_model_id = model_data.get("current_model_id")
                if saved_model_id in AVAILABLE_MODELS:
                    config.current_model_id = saved_model_id
                    import sys
                    sys.modules[__name__].current_model_id = saved_model_id
                    print(f"✅ Loaded model config: {saved_model_id}")
                else:
                    print(f"⚠️ Model '{saved_model_id}' không hợp lệ, dùng default: {DEFAULT_MODEL_ID}")

        # Load RPD tracking
        if os.path.exists(f"{data_dir}/rpd_lock.json"):
            with open(f"{data_dir}/rpd_lock.json", "r") as f:
                rpd_data = json.load(f)
                config.rpd_count = rpd_data.get("rpd_count", 0)
                config.rpd_date = rpd_data.get("rpd_date", "")
                config.api_locked_until = rpd_data.get("api_locked_until", 0.0)
                if config.api_locked_until > time.time():
                    remaining = config.api_locked_until - time.time()
                    print(f"✅ Restored API fallback lock: {remaining/3600:.1f}h remaining")
                print(f"✅ Loaded RPD: {config.rpd_count}/{FLASH_RPD_LIMIT} (date: {config.rpd_date})")

        # Load global settings (is_chat_enabled)
        if os.path.exists(f"{data_dir}/global_settings.json"):
            with open(f"{data_dir}/global_settings.json", "r") as f:
                g_data = json.load(f)
                config.is_chat_enabled = g_data.get("is_chat_enabled", True)
                print(f"✅ Loaded global_settings: is_chat_enabled={config.is_chat_enabled}")

        # Load characters (Character Webhook System)
        if os.path.exists(f"{data_dir}/characters.json"):
            with open(f"{data_dir}/characters.json", "r", encoding="utf-8") as f:
                raw = json.load(f)
                # raw: {guild_id_str: {role_id_str: {...}}}
                # Đảm bảo keys là str
                config.characters = {str(k): {str(rk): rv for rk, rv in v.items()} for k, v in raw.items()} if isinstance(raw, dict) else {}
                total = sum(len(v) for v in config.characters.values())
                print(f"✅ Loaded characters: {total} characters in {len(config.characters)} guilds")
        else:
            # Migration: nếu trước đó dùng SQLite/empty, tạo file rỗng
            config.characters = {}

        
        return True
    except Exception as e:
        print(f"⚠️ Lỗi load dữ liệu: {e}")
        return False

# ============================================
# 10. EXPOSE FUNCTIONS (COMPATIBILITY LAYER)
# ============================================
def build_intents():
    return config.build_intents()

def get_context_key(message_or_interaction):
    return config.get_context_key(message_or_interaction)

def get_context_state(ctx_key):
    return config.get_context_state(ctx_key)

def set_context_state(ctx_key, active, role_config):
    config.set_context_state(ctx_key, active, role_config)

def get_model(model_name=None):
    return config.get_model(model_name)

def get_model_for_guild(max_tokens, temperature, guild_id=None):
    return config.get_model_for_guild(max_tokens, temperature, guild_id)

def set_current_model(model_id):
    global current_model_id
    result = config.set_current_model(model_id)
    if result:
        current_model_id = config.current_model_id
    return result

def strip_bot_mention(text, bot_user_id=None):
    return config.strip_bot_mention(text, bot_user_id)

def extract_response_text(response):
    return config.extract_response_text(response)

def has_avatar_tag(text):
    return config.has_avatar_tag(text)

def remove_avatar_tag(text):
    return config.remove_avatar_tag(text)

def is_rpd_locked():
    return config.is_rpd_locked()

def lock_rpd_until_midnight():
    config.lock_rpd_until_midnight()

def is_flash_model(model_id: str) -> bool:
    return config.is_flash_model(model_id)

def check_flash_rpd():
    return config.check_flash_rpd()

def increment_flash_rpd():
    config.increment_flash_rpd()

def get_guild_characters(guild_id):
    return config.get_guild_characters(guild_id)

def get_character(guild_id, role_id):
    return config.get_character(guild_id, role_id)

def add_character(guild_id, role_id, name, avatar_url, system_prompt):
    return config.add_character(guild_id, role_id, name, avatar_url, system_prompt)

def update_character(guild_id, role_id, name=None, avatar_url=None, system_prompt=None):
    return config.update_character(guild_id, role_id, name, avatar_url, system_prompt)

def delete_character(guild_id, role_id):
    return config.delete_character(guild_id, role_id)

# ============================================
# 11. EXPOSE VARIABLES (COMPATIBILITY LAYER)
# ============================================
SPAM_TRACKER = config.spam_tracker
CONTEXT_STATES = config.context_states
chat_history = config.chat_history
MSG_COUNTERS = config.msg_counters
USER_ROLES = config.user_roles
GUILD_SETTINGS = config.guild_settings
PROVIDER_SETTINGS = config.provider_settings
CHARACTERS = config.characters

current_model_id = config.current_model_id

# ============================================
# 13. VALIDATION
# ============================================
print("✅ Config loaded successfully!")
print(f"   - Bot: {BOT_USER_ID} | Owner: {OWNER_ID} | Model: {DEFAULT_MODEL_ID}")
print(f"   - Port: {PORT} | History: {DEFAULT_HISTORY_LIMIT} | Flash RPD: {FLASH_RPD_LIMIT}")
