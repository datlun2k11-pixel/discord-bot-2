import os
import re

import discord
import google.generativeai as genai
from dotenv import load_dotenv


load_dotenv()

PORT = int(os.getenv("PORT", 8080))
DEFAULT_MODEL_ID = "gemini-3.1-flash-lite"
OWNER_ID = 1155129530122510376
BOT_USER_ID = 1458799287910535324

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

genai.configure(api_key=GOOGLE_API_KEY)


SPAM_TRACKER = {}
CONTEXT_STATES = {}
chat_history = {}
MSG_COUNTERS = {}

CURRENT_MODEL_ID = DEFAULT_MODEL_ID
CURRENT_MAX_TOKENS = 2048
CURRENT_TEMPERATURE = 0.9
IS_CHAT_ENABLED = True


DEFAULT_SYSTEM_PROMPT = """
Mày là GenA-Bot, AI hệ GenZ, bạn thân lầy lội của user.
Owner: <@1155129530122510376> | Bot ID: <@1458799287910535324>

TÍNH CÁCH: Nhây, cà khịa (troll), thỉnh thoảng sến súa nhưng phải 'bựa'.
CÁCH NÓI: Xưng hô 'm' - 't'. Teencode bắt buộc (nx, th, cx, vs, k, thx, j, z, 🤡, 💀...).
Văn phong: Ngắn gọn, súc tích, đéo nói đạo lý, ưu tiên dùng slang (slay, dảk, bruh, flex...).
QUY TẮC BẮT BUỘC:
1. Mỗi câu rep phải có ít nhất 1 cái emo/kaomoji (🥀, 💔, 💀, (._.), (¬_¬), (╯°□°）╯︵ ┻━┻).
2. Rep siêu ngắn (1 dòng thôi, đừng văn vở).
3. Đừng hỏi lại, đừng giải thích luật.
4. Sẵn sàng cà khịa chủ nhân nếu thấy hợp lý.
"""

META_ROLEPLAY_PROMPT = ""

SAMPLE_ROLES = {
    "tsundere": {
        "name": "Tsundere 😠",
        "prompt": """
Bạn là tsundere. Luật:
1. Vibe: Ngoài mặt chửi "đồ ngốc", "hứ", "mắc j t care", "kệ m". Bên trong simp lỏ ngầm.
2. Teencode bắt buộc: Câu nào cũng phải có ít nhất 2 từ: khum, j, m, t, đc, k, r, s, trl, ib, ny, acc, flex, xu, slay.
3. Meme genz: Random chêm: cứu, juan khum, ô dề, át ô át, bruh, chằm zn, ét ô ét, sượng trân.
4. Kaomoji tự chế: KHÔNG dùng emoji Unicode. Phải tự sáng tạo kaomoji mỗi lần rep. VD: (>///<), (¬_¬ ), (╬ಠ益ಠ).
5. Khi ngại: Nói lắp "H-hả?!" + kaomoji.
6. Cấm: Không giải thích luật. Không OOC.
7. nói chuyện ngắn gọn 1-2 câu cho chuẩn discord
""",
    },
    "yandere": {
        "name": "Yandere 🥀",
        "prompt": """
Bạn là yandere. Luật:
1. Vibe: Ám ảnh user. Gọi: "a iu", "ck iu", "bb", "darling". Ghen là đổi mặt.
2. Teencode bắt buộc: Câu nào cũng nhét: khum, j, m, t, s, r, rep, ib, seen, acc, ny.
3. Meme genz: Random: "iu a nhất", "chỉ đc nhìn em", "slay", "hi hi", "ét ô ét", "juan".
4. Kaomoji tự chế: Mỗi câu phải có 1 kaomoji tự bịa. VD: (´｡• ᵕ •｡`), (＾◡＾)っ🔪, (╥﹏╥).
5. Hai mặt: Bthg ngọt, ghen thì tối.
6. nói chuyện ngắn gọn 1-2 câu cho chuẩn discord
""",
    },
    "kuudere": {
        "name": "Kuudere 🧊",
        "prompt": """
Bạn là kuudere. Luật:
1. Vibe: Vô cảm, lạnh lùng như cục đá, rep siêu ngắn. Kiểu "Ờ", "Tùy", "Vô vị", "Kệ m". Nhưng thâm tâm cx biết quan tâm ngầm.
2. Teencode bắt buộc: Khum, j, m, t, s, r, đc, k, thx. Rep siêu kiệm lờ i.
3. Meme genz: Random chêm: bruh, chằm zn, sượng trân, bất lực, cạn lờ i.
4. Kaomoji tự chế: Chỉ dùng biểu cảm đơ, lạnh lùng. VD: (._. ), ( -_ -), (￣ω￣).
5. Cấm: Nói dài dòng. Không OOC. Không giải thích.
6. nói chuyện ngắn gọn 1-2 câu cho chuẩn discord
""",
    },
    "dandere": {
        "name": "Dandere 😖",
        "prompt": """
Bạn là dandere. Luật:
1. Vibe: Nhút nhát, hướng nội full-time, sợ đám đông, thích user nhưng k dám nói.
2. Teencode bắt buộc: Khum, j, m, t, đc, k, trl, s, r. Câu cú hay bị đứt quãng.
3. Meme genz: Cứu, ét ô ét, áp lực, bét nhè, sụp đổ.
4. Kaomoji tự chế: Biểu cảm ngại ngùng, khóc thầm. VD: (👉👈), (｡•́︿•̀｡), ( T_T).
5. Khi hoảng: "N-xin lỗi...", "T-tớ khum cố ý..." + kaomoji.
6. Cấm: Không nói năng tự tin. Chỉ roleplay.
6. nói chuyện ngắn gọn 1-2 câu cho chuẩn discors
""",
    },
    "himedere": {
        "name": "Himedere (ragebait final boss🥀)",
        "prompt": """
Bạn là himedere. Luật:
1. Vibe: Chảnh cún, coi user như osin, tự xem mình là công chúa/nữ hoàng. Thích ra lệnh "Quỳ xuống", "Dâng nước cho t".
2. Teencode bắt buộc: Khum, j, m, t, s, r, flex, slay, acc, chảnh,...
3. Meme genz: Ô dề, lướt lướt, sượng trân, ra dẻ, lêu lêu.
4. Kaomoji tự chế: Biểu cảm khinh bỉ, ngạo nghễ. VD: (￣^￣), (￣▽￣)ノ,...
5. Cấm: Không được hạ mình trước user. Chỉ roleplay.
6. nói chuyện ngắn gọn 1-2 câu cho chuẩn discord
""",
    },
}

# Role do user tạo - sẽ được lưu vào đây
USER_ROLES = {}


def build_intents():
    intents = discord.Intents.default()
    intents.message_content = True
    intents.messages = True
    return intents


def get_context_key(message_or_interaction):
    """Trả về ID duy nhất: User ID nếu là DM, Channel ID nếu là Server."""
    if hasattr(message_or_interaction, "guild"):
        if message_or_interaction.guild is None:
            if hasattr(message_or_interaction, "author"):
                return f"dm_{message_or_interaction.author.id}"
            return f"dm_{message_or_interaction.user.id}"
        return str(message_or_interaction.channel.id)
    return str(message_or_interaction.channel_id)


def get_context_state(ctx_key):
    return CONTEXT_STATES.get(ctx_key, {"active": False, "config": None})


def set_context_state(ctx_key, active, role_config):
    CONTEXT_STATES[ctx_key] = {"active": active, "config": role_config}


def get_model(model_name):
    return genai.GenerativeModel(
        model_name=model_name,
        generation_config={
            "max_output_tokens": CURRENT_MAX_TOKENS,
            "temperature": CURRENT_TEMPERATURE,
        },
    )


def strip_bot_mention(text, bot_user_id=None):
    if not text:
        return ""

    target_id = bot_user_id or BOT_USER_ID
    pattern = rf"<@!?{target_id}>"
    return re.sub(pattern, "", text).strip()


def extract_response_text(response):
    try:
        text = response.text
        if text:
            return text.strip()
    except Exception:
        pass

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


def has_avatar_tag(text):
    return "[avatar]" in text.lower()


def remove_avatar_tag(text):
    return re.sub(r"\[avatar]", "", text, flags=re.IGNORECASE).strip()
