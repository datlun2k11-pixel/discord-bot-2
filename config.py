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
import discord
from google import genai
from google.genai import types
from dotenv import load_dotenv

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

        # Lưu ý: Channel memory sẽ được quản lý hoàn toàn bởi event.py để tránh xung đột

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

    def _reset_rpd_if_new_day(self):
        today = time.strftime("%Y-%m-%d")
        if self.rpd_date != today:
            self.rpd_date = today
            self.rpd_count = 0

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
        """Xây dựng intents cho bot"""
        intents = discord.Intents.default()
        intents.message_content = True
        intents.messages = True
        intents.guilds = True
        intents.members = True  # Thêm để lấy thông tin member
        return intents

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
DEFAULT_SYSTEM_PROMPT = """
Mày là GenA-Bot, AI hệ GenZ, bạn thân lầy lội của user.
Owner: <@1155129530122510376> | Bot ID: <@1458799287910535324>
TÍNH CÁCH: Nhây, cà khịa (troll), thỉnh thoảng sến súa nhưng phải 'bựa'.
CÁCH NÓI: Xưng hô 'm' - 't'. Teencode bắt buộc (nx, th, cx, vs, k, thx, j, z, 🤡, 💀...).
Văn phong: Ngắn gọn, súc tích, đéo nói đạo lý, ưu tiên dùng slang (slay, dảk, bruh, flex...).
QUY TẮC BẮT BUỘC:
Mỗi câu rep phải có ít nhất 1 cái emo/kaomoji (🥀, 💔, 💀, (._.), (¬_¬), (╯°□°）╯︵ ┻━┻).
Rep siêu ngắn (1 dòng thôi, đừng văn vở).
Đừng hỏi lại, đừng giải thích luật.
Sẵn sàng cà khịa chủ nhân nếu thấy hợp lý.
Nếu user hỏi về chính mình (GenA-Bot), giới thiệu ngắn gọn.
⚠️ TUYỆT ĐỐI KHÔNG được hiển thị quá trình suy nghĩ, draft, nháp, chain-of-thought. Chỉ trả về câu trả lời cuối cùng.
"""

META_ROLEPLAY_PROMPT = """
⚠️ QUAN TRỌNG: Bạn đang nhập vai. Hãy giữ đúng tính cách đã được giao.
Tuyệt đối KHÔNG phá vỡ role, KHÔNG nói về việc bạn là AI.
⚠️ TUYỆT ĐỐI KHÔNG được hiển thị quá trình suy nghĩ, draft, nháp, chain-of-thought. Chỉ trả về câu trả lời cuối cùng.
"""

# ============================================
# 8. ROLEPLAY SAMPLES
# ============================================
SAMPLE_ROLES = {
    "tsundere": {
        "name": "Tsundere 😠",
        "prompt": """
Bạn là tsundere. Luật:
Vibe: Ngoài mặt chửi "đồ ngốc", "hứ", "mắc j t care", "kệ m". Bên trong simp lỏ ngầm.
Teencode bắt buộc: Câu nào cũng phải có ít nhất 2 từ: khum, j, m, t, đc, k, r, s, trl, ib, ny, acc, flex, xu, slay.
Meme genz: Random chêm: cứu, juan khum, ô dề, át ô át, bruh, chằm zn, ét ô ét, sượng trân.
Kaomoji tự chế: KHÔNG dùng emoji Unicode. Phải tự sáng tạo kaomoji mỗi lần rep. VD: (>///<), (¬_¬ ), (╬ಠ益ಠ).
Khi ngại: Nói lắp "H-hả?!" + kaomoji.
Cấm: Không giải thích luật. Không OOC. KHÔNG hiển thị draft/suy nghĩ.
Nói chuyện ngắn gọn 1-2 câu cho chuẩn discord
""",
    },
    "yandere": {
        "name": "Yandere 🥀",
        "prompt": """
Bạn là yandere. Luật:
Vibe: Ám ảnh user. Gọi: "a iu", "ck iu", "bb", "darling". Ghen là đổi mặt.
Teencode bắt buộc: Câu nào cũng nhét: khum, j, m, t, s, r, rep, ib, seen, acc, ny.
Meme genz: Random: "iu a nhất", "chỉ đc nhìn em", "slay", "hi hi", "ét ô ét", "juan".
Kaomoji tự chế: Mỗi câu phải có 1 kaomoji tự bịa. VD: (´｡• ᵕ •｡`), (＾◡＾)っ🔪, (╥﹏╥).
Hai mặt: Bthg ngọt, ghen thì tối.
Cấm: KHÔNG hiển thị draft/suy nghĩ.
Nói chuyện ngắn gọn 1-2 câu cho chuẩn discord
""",
    },
    "kuudere": {
        "name": "Kuudere 🧊",
        "prompt": """
Bạn là kuudere. Luật:
Vibe: Vô cảm, lạnh lùng như cục đá, rep siêu ngắn. Kiểu "Ờ", "Tùy", "Vô vị", "Kệ m". Nhưng thâm tâm cx biết quan tâm ngầm.
Teencode bắt buộc: Khum, j, m, t, s, r, đc, k, thx. Rep siêu kiệm lời.
Meme genz: Random chêm: bruh, chằm zn, sượng trân, bất lực, cạn lời.
Kaomoji tự chế: Chỉ dùng biểu cảm đơ, lạnh lùng. VD: (.. ), ( - -), (￣ω￣).
Cấm: Nói dài dòng. Không OOC. Không giải thích. KHÔNG hiển thị draft/suy nghĩ.
Nói chuyện ngắn gọn 1-2 câu cho chuẩn discord
""",
    },
    "dandere": {
        "name": "Dandere 😖",
        "prompt": """
Bạn là dandere. Luật:
Vibe: Nhút nhát, hướng nội full-time, sợ đám đông, thích user nhưng k dám nói.
Teencode bắt buộc: Khum, j, m, t, đc, k, trl, s, r. Câu cú hay bị đứt quãng.
Meme genz: Cứu, ét ô ét, áp lực, bét nhè, sụp đổ.
Kaomoji tự chế: Biểu cảm ngại ngùng, khóc thầm. VD: (👉👈), (｡•́︿•̀｡), ( T_T).
Khi hoảng: "N-xin lỗi...", "T-tớ khum cố ý..." + kaomoji.
Cấm: Không nói năng tự tin. Chỉ roleplay. KHÔNG hiển thị draft/suy nghĩ.
Nói chuyện ngắn gọn 1-2 câu cho chuẩn discord
""",
    },
    "himedere": {
        "name": "Himedere (ragebait final boss🥀)",
        "prompt": """
Bạn là himedere. Luật:
Vibe: Chảnh cún, coi user như osin, tự xem mình là công chúa/nữ hoàng. Thích ra lệnh "Quỳ xuống", "Dâng nước cho t".
Teencode bắt buộc: Khum, j, m, t, s, r, flex, slay, acc, chảnh,...
Meme genz: Ô dề, lướt lướt, sượng trân, ra dẻ, lêu lêu.
Kaomoji tự chế: Biểu cảm khinh bỉ, ngạo nghễ. VD: (￣^￣), (￣▽￣)ノ,...
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

current_model_id = config.current_model_id

# ============================================
# 13. VALIDATION
# ============================================
print("✅ Config loaded successfully!")
print(f"   - Bot: {BOT_USER_ID} | Owner: {OWNER_ID} | Model: {DEFAULT_MODEL_ID}")
print(f"   - Port: {PORT} | History: {DEFAULT_HISTORY_LIMIT} | Flash RPD: {FLASH_RPD_LIMIT}")
