import os
import re
import json
import time
from typing import Dict, List, Optional, Any
from collections import defaultdict
import discord
import google.generativeai as genai
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

# Cấu hình mặc định
DEFAULT_MODEL_ID = "gemini-3.1-flash-lite"  # Model Gemini mới nhất
DEFAULT_MAX_TOKENS = 2048
DEFAULT_TEMPERATURE = 0.7
DEFAULT_HISTORY_LIMIT = 15  # Số tin nhắn nhớ trong channel
DEFAULT_CONTEXT_LIMIT = 15  # Số tin nhắn nhớ trong chat_history

# ============================================
# 3. KHỞI TẠO GEMINI
# ============================================
genai.configure(api_key=GOOGLE_API_KEY)

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
        
        # Lưu ý: Channel memory sẽ được quản lý hoàn toàn bởi event.py để tránh xung đột

    def get_model(self, model_name: Optional[str] = None) -> genai.GenerativeModel:
        """Tạo model Gemini với config hiện tại"""
        return genai.GenerativeModel(
            model_name=model_name or self.current_model_id,
            generation_config={
                "max_output_tokens": self.max_tokens,
                "temperature": self.temperature,
            },
        )

    def get_model_for_guild(self, max_tokens: int, temperature: float) -> genai.GenerativeModel:
        """Tạo model Gemini với config riêng cho từng guild"""
        return genai.GenerativeModel(
            model_name=self.current_model_id,
            generation_config={
                "max_output_tokens": max_tokens,
                "temperature": temperature,
            },
        )

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

    def extract_response_text(self, response) -> str:
        """Extract text từ response của Gemini an toàn"""
        try:
            text = response.text
            if text:
                return text.strip()
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
                return "\n".join(text_chunks).strip()
        
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
# 5. SINGLETON INSTANCE
# ============================================
config = BotConfig()

# ============================================
# 6. SYSTEM PROMPTS (TÁCH RIÊNG DỄ QUẢN LÝ)
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
"""

META_ROLEPLAY_PROMPT = """
⚠️ QUAN TRỌNG: Bạn đang nhập vai. Hãy giữ đúng tính cách đã được giao.
Tuyệt đối KHÔNG phá vỡ role, KHÔNG nói về việc bạn là AI.
"""

# ============================================
# 7. ROLEPLAY SAMPLES
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
Cấm: Không giải thích luật. Không OOC.
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
Cấm: Nói dài dòng. Không OOC. Không giải thích.
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
Cấm: Không nói năng tự tin. Chỉ roleplay.
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
Cấm: Không được hạ mình trước user. Chỉ roleplay.
Nói chuyện ngắn gọn 1-2 câu cho chuẩn discord
""",
    },
}

# ============================================
# 8. DATA PERSISTENCE (LƯU TRỮ AN TOÀN)
# ============================================
def save_all_data():
    """Lưu toàn bộ dữ liệu ra file JSON (trừ channel memory vì event.py đã lo)"""
    try:
        data_dir = "data"
        os.makedirs(data_dir, exist_ok=True)
        
        # Lưu chat_history
        with open(f"{data_dir}/chat_history.json", "w", encoding="utf-8") as f:
            json.dump(config.chat_history, f, ensure_ascii=False, indent=2)
            
        # Lưu msg_counters
        with open(f"{data_dir}/msg_counters.json", "w") as f:
            json.dump(config.msg_counters, f, indent=2)
            
        # Lưu user_roles
        with open(f"{data_dir}/user_roles.json", "w", encoding="utf-8") as f:
            json.dump(config.user_roles, f, ensure_ascii=False, indent=2)
            
        # Lưu context_states
        with open(f"{data_dir}/context_states.json", "w", encoding="utf-8") as f:
            json.dump(config.context_states, f, ensure_ascii=False, indent=2)
            
        # Lưu guild_settings
        with open(f"{data_dir}/guild_settings.json", "w", encoding="utf-8") as f:
            json.dump(config.guild_settings, f, ensure_ascii=False, indent=2)
            
        print("✅ Đã lưu toàn bộ dữ liệu config")
        return True
    except Exception as e:
        print(f"⚠️ Lỗi lưu dữ liệu: {e}")
        return False

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
                
        return True
    except Exception as e:
        print(f"⚠️ Lỗi load dữ liệu: {e}")
        return False

# ============================================
# 9. EXPOSE CÁC HÀM TIỆN ÍCH (ĐỂ TƯƠNG THÍCH NGƯỢC)
# ============================================
def build_intents():
    return config.build_intents()

def get_context_key(message_or_interaction):
    return config.get_context_key(message_or_interaction)

def get_context_state(ctx_key):
    return config.get_context_state(ctx_key)

def set_context_state(ctx_key, active, role_config):
    config.set_context_state(ctx_key, active, role_config)

def get_model(model_name):
    return config.get_model(model_name)

def get_model_for_guild(max_tokens, temperature):
    return config.get_model_for_guild(max_tokens, temperature)

def strip_bot_mention(text, bot_user_id=None):
    return config.strip_bot_mention(text, bot_user_id)

def extract_response_text(response):
    return config.extract_response_text(response)

def has_avatar_tag(text):
    return config.has_avatar_tag(text)

def remove_avatar_tag(text):
    return config.remove_avatar_tag(text)

# ============================================
# 10. EXPOSE BIẾN (ĐỂ TƯƠNG THÍCH)
# ============================================
SPAM_TRACKER = config.spam_tracker
CONTEXT_STATES = config.context_states
chat_history = config.chat_history
MSG_COUNTERS = config.msg_counters
USER_ROLES = config.user_roles
GUILD_SETTINGS = config.guild_settings
CURRENT_MODEL_ID = config.current_model_id
CURRENT_MAX_TOKENS = config.max_tokens
CURRENT_TEMPERATURE = config.temperature
IS_CHAT_ENABLED = config.is_chat_enabled

# ============================================
# 11. VALIDATION KHI IMPORT
# ============================================
print("✅ Config loaded successfully!")
print(f"   - Bot User ID: {BOT_USER_ID}")
print(f"   - Owner ID: {OWNER_ID}")
print(f"   - Default Model: {DEFAULT_MODEL_ID}")
print(f"   - Port: {PORT}")
print(f"   - History Limit: {DEFAULT_HISTORY_LIMIT} messages")