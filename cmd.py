import discord
from discord import app_commands
from discord.ext import commands
import config
import datetime
from typing import Optional, List
# Branding màu sắc cho Embed
BRAND_COLOR = 0x00F0FF
ERROR_COLOR = 0xFF0040
SUCCESS_COLOR = 0x00FF88

# --- AUTOCOMPLETE CHO ROLEPLAY CHARACTERS ---
async def autocomplete_characters(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    """Autocomplete gợi ý tên nhân vật khi gõ /roleplay start"""
    choices = []
    for key, role in config.SAMPLE_ROLES.items():
        # Nếu chưa gõ gì thì hiện full list, nếu có gõ thì filter
        if not current or current.lower() in key.lower() or current.lower() in role["name"].lower():
            choices.append(app_commands.Choice(name=f"{role['name']} ({key})", value=key))
    # Giới hạn 25 choices (Discord limit)
    return choices[:25]

def register_commands(bot):
    # --- GLOBAL ERROR HANDLER FOR PERMISSIONS ---
    @bot.tree.error
    async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            embed = discord.Embed(
                title="🚫 Access Denied",
                description="Bạn không có quyền Administrator để thực hiện lệnh này.",
                color=ERROR_COLOR
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            err_desc = "Đã xảy ra lỗi: `" + str(error) + "`"
            embed = discord.Embed(
                title="💀 Lỗi hệ thống",
                description=err_desc,
                color=ERROR_COLOR
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    # --- ROLEPLAY COMMAND (NÂNG CẤP - DỄ DÙNG HƠN) ---
    @bot.tree.command(name="roleplay", description="🎭 Bật/Tắt chế độ nhập vai với các tính cách có sẵn")
    @app_commands.describe(
        action="Chọn hành động muốn thực hiện",
        character="Tên nhân vật (chỉ cần khi chọn Bắt đầu)",
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="📋 Xem danh sách nhân vật", value="list"),
        app_commands.Choice(name="🎭 Bắt đầu nhập vai", value="start"),
        app_commands.Choice(name="🛑 Dừng nhập vai", value="stop"),
    ])
    @app_commands.autocomplete(character=autocomplete_characters)
    async def roleplay(interaction: discord.Interaction, action: str = "list", character: Optional[str] = None):
        """
        action: 'list' (xem danh sách), 'start' (bắt đầu), 'stop' (dừng)
        character: tên nhân vật (chỉ cần khi action là 'start')
        """
        ctx_key = config.get_context_key(interaction)
        
        # 1. Xem danh sách nhân vật
        if action == "list":
            roles_list = "\n".join([f"- **{k}**: {v['name']}" for k, v in config.SAMPLE_ROLES.items()])
            embed = discord.Embed(
                title="🎭 Danh sách tính cách có sẵn",
                description=f"Dùng lệnh `/roleplay start <tên>` để bắt đầu.\n\n{roles_list}",
                color=BRAND_COLOR
            )
            embed.set_footer(text="💡 Chọn action 'Bắt đầu' rồi chọn nhân vật từ dropdown!")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # 2. Dừng nhập vai
        if action == "stop":
            config.set_context_state(ctx_key, False, None)
            embed = discord.Embed(
                title="🛑 Đã tắt chế độ nhập vai",
                description="Bot đã trở về trạng thái GenZ bình thường.",
                color=ERROR_COLOR
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # 3. Bắt đầu nhập vai
        if action == "start":
            if not character or character.lower() not in config.SAMPLE_ROLES:
                available = ", ".join(config.SAMPLE_ROLES.keys())
                roles_display = "\n".join([f"• `{k}` - {v['name']}" for k, v in config.SAMPLE_ROLES.items()])
                embed = discord.Embed(
                    title="❌ Sai tên nhân vật",
                    description=(
                        f"Bro chưa chọn nhân vật kìa! 🤡\n\n"
                        f"**Các nhân vật có sẵn:**\n"
                        f"{roles_display}\n\n"
                        f"📝 **Cách dùng:** Chọn action **Bắt đầu** → gõ tên nhân vật vào ô **character**"
                    ),
                    color=ERROR_COLOR
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            selected_role = config.SAMPLE_ROLES[character.lower()]
            config.set_context_state(ctx_key, True, selected_role)
            
            embed = discord.Embed(
                title=f"🎭 Đang nhập vai: {selected_role['name']}",
                description=(
                    f"Từ giờ t sẽ nói chuyện như **{selected_role['name']}**! 🎭\n\n"
                    f"📌 **Cách dùng:** Tag bot hoặc reply tin nhắn của bot để nói chuyện\n"
                    f"🛑 **Tắt:** Dùng `/roleplay stop`"
                ),
                color=SUCCESS_COLOR
            )
            embed.set_footer(text="=)) chuẩn bị tinh thần đi bro")
            await interaction.response.send_message(embed=embed, ephemeral=False) # Public để mọi người cùng thấy và chơi chung
            return

        # Fallback nếu nhập sai action
        await interaction.response.send_message("❌ Lệnh không hợp lệ. Dùng `/roleplay list` để xem hướng dẫn.", ephemeral=True)

    # --- SETTING COMMAND (ADMIN/OWNER) ---
    @bot.tree.command(name="setting", description="[Admin/Owner] Tùy chỉnh cấu hình bot cho server")
    async def setting(
        interaction: discord.Interaction,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        chat_enabled: Optional[bool] = None,
    ):
        """
        Tùy chỉnh cấu hình bot cho server hiện tại.
        - max_tokens: Số token tối đa (128-8192, để trống giữ nguyên)
        - temperature: Độ sáng tạo (0.0-2.0, để trống giữ nguyên)
        - chat_enabled: Bật/tắt chat AI (True/False, để trống giữ nguyên)
        """
        # Kiểm tra quyền: Administrator hoặc Owner
        is_admin = interaction.user.guild_permissions.administrator if interaction.guild else False
        is_owner = interaction.user.id == config.OWNER_ID
        
        if not is_admin and not is_owner:
            embed = discord.Embed(
                title="🚫 Access Denied",
                description="Bạn cần quyền Administrator hoặc là Owner để dùng lệnh này.",
                color=ERROR_COLOR
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        guild_id = str(interaction.guild.id)
        
        # Lấy settings hiện tại (hoặc tạo mới với giá trị mặc định)
        current = config.GUILD_SETTINGS.get(guild_id, {})
        
        changed = []
        
        if max_tokens is not None:
            if max_tokens < 128 or max_tokens > 8192:
                await interaction.response.send_message(
                    "❌ `max_tokens` phải từ 128 đến 8192!",
                    ephemeral=True
                )
                return
            current["max_tokens"] = max_tokens
            changed.append(f"max_tokens: {max_tokens}")
        
        if temperature is not None:
            if temperature < 0.0 or temperature > 2.0:
                await interaction.response.send_message(
                    "❌ `temperature` phải từ 0.0 đến 2.0!",
                    ephemeral=True
                )
                return
            current["temperature"] = temperature
            changed.append(f"temperature: {temperature}")
        
        if chat_enabled is not None:
            current["chat_enabled"] = chat_enabled
            changed.append(f"chat_enabled: {chat_enabled}")
        
        # Nếu không có gì thay đổi -> hiển thị settings hiện tại
        if not changed:
            max_t = current.get("max_tokens", config.DEFAULT_MAX_TOKENS)
            temp = current.get("temperature", config.DEFAULT_TEMPERATURE)
            enabled = current.get("chat_enabled", True)
            
            embed = discord.Embed(
                title="⚙️ Cấu hình server hiện tại",
                color=BRAND_COLOR,
                description=f"**Server:** {interaction.guild.name}"
            )
            embed.add_field(name="Max Tokens", value=str(max_t), inline=True)
            embed.add_field(name="Temperature", value=str(temp), inline=True)
            embed.add_field(name="Chat Enabled", value="✅ Bật" if enabled else "❌ Tắt", inline=True)
            embed.set_footer(text="Dùng /setting <option> <value> để thay đổi")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Lưu settings
        config.GUILD_SETTINGS[guild_id] = current
        config.save_all_data()
        
        embed = discord.Embed(
            title="✅ Đã cập nhật cấu hình",
            color=SUCCESS_COLOR,
            description="\n".join([f"• Đã đặt **{c}**" for c in changed])
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    
    # Thêm lệnh /joke để tạo joke bằng AI
    @bot.tree.command(name="joke", description="Tạo joke hài hước với username và chủ đề")
    async def joke(interaction: discord.Interaction, username: discord.Member, topic: str = None):
        """
        Tạo joke bằng AI với username và chủ đề được chỉ định
        - username: @mention của user (bắt buộc)
        - topic: chủ đề của joke (tùy chọn)
        """
        # Kiểm tra daily limit
        user_id = interaction.user.id
        if user_id != config.OWNER_ID:
            has_remaining, remaining = config.check_daily_limit(user_id)
            if not has_remaining:
                embed = discord.Embed(
                    title="😴 Hết lượt chat hôm nay rồi!",
                    description=(
                        f"Bạn đã dùng hết **{config.DAILY_LIMIT_PER_USER}** lượt chat với bot hôm nay rồi! 🥀\n\n"
                        f"Quay lại vào ngày mai nha! ⏰\n"
                        f"(Lượt sẽ reset lúc **0:00** theo giờ Việt Nam)"
                    ),
                    color=ERROR_COLOR
                )
                embed.set_footer(text="=)) chat ít thôi để còn lượt nha bro")
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
        
        # Lấy display name của user
        target_name = username.display_name or username.name
        
        # Tạo prompt cho Gemini
        prompt = f"""
Hãy tạo một joke hài hước, hài hước về người tên là "{target_name}".
Joke phải:
- Ngắn gọn, hài hước, dễ hiểu
- Có liên quan đến display name của người này
- Dùng ngôn ngữ GenZ, teencode (nx, th, cx, vs, k, thx, j, z, 🤡, 💀...)
- Có ít nhất 1 emoji/kaomoji (🥀, 💔, 💀, (._.), (¬_¬), (╯°□°）╯︵ ┻━┻)
"""
        
        if topic:
            prompt += f"\n- Chủ đề của joke là: {topic}"
        
        prompt += """
\nChỉ trả về joke duy nhất, không giải thích, không giới thiệu gì cả."""
        
        # Defer response vì gọi API có thể mất >3s
        await interaction.response.defer()
        
        try:
            # Lấy model từ config (dùng instance method)
            model = config.get_model()
            
            # Gọi Gemini API
            response = await model.generate_content_async([prompt])
            joke_text = config.extract_response_text(response)
            
            if not joke_text:
                joke_text = "API bị mù rồi, nói lại phát 💀"
            
            # Tạo embed
            embed = discord.Embed(
                title="😂 Joke Hài Hước",
                description=f"**Joke về {target_name}:**\n\n{joke_text}",
                color=BRAND_COLOR
            )
            embed.set_footer(text="Được tạo bởi GenA-Bot với Gemini AI")
            
            await interaction.followup.send(embed=embed)
            
            # Tăng daily usage
            config.increment_daily_usage(user_id)
            
        except Exception as error:
            error_str = str(error).lower()
            
            # Xử lý rate limit
            if "429" in error_str or "rate" in error_str or "quota" in error_str or "resource exhausted" in error_str:
                embed = discord.Embed(
                    title="😴 API hết quota hôm nay rồi!",
                    description=(
                        f"**Gemini API** đã hết lượt sử dụng trong hôm nay! 💀\n\n"
                        f"• Bot sẽ không trả lời được cho tới khi **reset vào 0:00** 🕐\n"
                        f"• Các tính năng khác (lệnh, roleplay) vẫn hoạt động bình thường ✅\n\n"
                        f"**Giải pháp:** Chờ mai hoặc nhắn Owner nạp thêm API key! 😎"
                    ),
                    color=ERROR_COLOR,
                )
                embed.set_footer(text="=)) hết xài r, để dành tiền nạp API đi bro")
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                # Xử lý lỗi khác
                embed = discord.Embed(
                    title="💀 Lỗi hệ thống",
                    description=f"Đã xảy ra lỗi khi tạo joke: `{error}`",
                    color=ERROR_COLOR
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
    
    # Thêm lệnh /ping đơn giản để test
    @bot.tree.command(name="ping", description="Kiểm tra độ trễ của bot")
    async def ping(interaction: discord.Interaction):
        latency = round(bot.latency * 1000)
        await interaction.response.send_message(f"Pong! 🏓 Độ trễ: {latency}ms")

    # --- MODEL COMMAND (OWNER ONLY) ---
    @bot.tree.command(name="model", description="[Owner] Xem/đổi model Gemini đang dùng")
    @app_commands.describe(
        action="list (xem danh sách), current (xem model hiện tại), set (đổi model)",
        model_id="Model ID cần đổi (chỉ cần khi action='set')"
    )
    async def model(
        interaction: discord.Interaction,
        action: str,
        model_id: Optional[str] = None
    ):
        """
        Quản lý model Gemini.
        - action="list": Hiển thị danh sách model có sẵn + highlight model đang dùng
        - action="current": Hiển thị model hiện tại
        - action="set": Đổi model (chỉ OWNER mới được)
        """
        # Chỉ OWNER được dùng lệnh này
        if interaction.user.id != config.OWNER_ID:
            embed = discord.Embed(
                title="🚫 Access Denied",
                description="Chỉ Owner mới được quản lý model Gemini.",
                color=ERROR_COLOR
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # === ACTION: LIST ===
        if action == "list":
            lines = ["**Danh sách model Gemini chính hãng:**\n"]
            for m in config.AVAILABLE_MODELS:
                marker = " ✅ **ĐANG DÙNG**" if m == config.current_model_id else ""
                lines.append(f"• `{m}`{marker}")
            
            embed = discord.Embed(
                title="🤖 Danh sách Model Gemini",
                description="\n".join(lines),
                color=BRAND_COLOR
            )
            embed.set_footer(text=f"Model hiện tại: {config.current_model_id}")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # === ACTION: CURRENT ===
        if action == "current":
            embed = discord.Embed(
                title="🤖 Model hiện tại",
                description=f"Bot đang dùng model: `{config.current_model_id}`",
                color=SUCCESS_COLOR
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # === ACTION: SET ===
        if action == "set":
            if not model_id:
                await interaction.response.send_message(
                    "❌ Thiếu `model_id`! Dùng `/model set <model_id>`",
                    ephemeral=True
                )
                return
            
            # Validate model_id
            if model_id not in config.AVAILABLE_MODELS:
                available = ", ".join(f"`{m}`" for m in config.AVAILABLE_MODELS)
                await interaction.response.send_message(
                    f"❌ Model `{model_id}` không hợp lệ!\n\nModel có sẵn: {available}",
                    ephemeral=True
                )
                return
            
            # Đổi model
            old_model = config.config.current_model_id
            success = config.set_current_model(model_id)
            
            if success:
                # Lưu ngay
                config.save_all_data()
                
                embed = discord.Embed(
                    title="✅ Đã đổi model",
                    color=SUCCESS_COLOR,
                    description=(
                        f"**Model cũ:** `{old_model}`\n"
                        f"**Model mới:** `{model_id}`\n\n"
                        f"Lưu ý: Model mới sẽ được áp dụng cho tất cả chat từ bây giờ."
                    )
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(
                    f"❌ Không thể đổi sang model `{model_id}`!",
                    ephemeral=True
                )
            return

        # Fallback: action không hợp lệ
        await interaction.response.send_message(
            "❌ Action không hợp lệ. Dùng: `list`, `current`, hoặc `set`",
            ephemeral=True
        )
