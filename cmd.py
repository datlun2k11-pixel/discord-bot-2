# Đầu file cmd.py
import discord
from discord import app_commands
from discord.ext import commands
import config
from datetime import datetime, timezone, timedelta
from typing import Optional, List
import time

# Branding màu sắc cho Embed
BRAND_COLOR = 0x00F0FF
ERROR_COLOR = 0xFF0040
SUCCESS_COLOR = 0x00FF88

# --- CHARACTER SYSTEM CONSTANTS ---
MAX_AVATAR_SIZE = 20 * 1024 * 1024  # 20MB theo spec
_pending_character_pfps: dict[int, Optional[discord.Attachment]] = {}  # user_id -> attachment

async def autocomplete_users(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    """Autocomplete gợi ý người dùng khi gõ /usage"""
    choices = []
    if interaction.guild:
        # Lấy danh sách member trong guild
        try:
            members = [m for m in interaction.guild.members if not m.bot]
            for member in members[:100]:  # Giới hạn 100 member để tránh lag
                name = f"{member.display_name} ({member.id})"
                if not current or current.lower() in name.lower() or current in str(member.id):
                    choices.append(app_commands.Choice(name=name, value=str(member.id)))
        except Exception:
            pass
    return choices[:25]

# --- MODAL TẠO ROLE MỚI ---
class CreateRoleModal(discord.ui.Modal, title="Tạo role mới"):
    name_input = discord.ui.TextInput(
        label="Tên role",
        placeholder="VD: Catgirl, Waifu, ...",
        required=True,
        max_length=100,
    )
    prompt_input = discord.ui.TextInput(
        label="System Prompt",
        style=discord.TextStyle.paragraph,
        placeholder="Nhập mô tả tính cách, cách nói chuyện, ...",
        required=True,
        max_length=2000,
    )

    async def on_submit(self, interaction: discord.Interaction):
        name = self.name_input.value.strip()
        prompt = self.prompt_input.value.strip()
        if not name or not prompt:
            await interaction.response.send_message("❌ Thiếu thông tin!", ephemeral=True)
            return
        key = name.lower().replace(" ", "_")
        config.config.custom_roles[key] = {"name": name, "prompt": prompt}
        config.save_all_data()
        embed = discord.Embed(
            title="✅ Đã tạo role mới",
            description=f"**{name}** đã được thêm vào danh sách role!\nDùng `/roleplay start` để chọn.",
            color=SUCCESS_COLOR,
        )
        embed.set_footer(text="Có thể dùng /roleplay list để xem tất cả role")
        await interaction.response.send_message(embed=embed, ephemeral=True)

# --- AUTOCOMPLETE CHO ROLEPLAY CHARACTERS ---
async def autocomplete_characters(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    """Autocomplete gợi ý tên nhân vật khi gõ /roleplay start"""
    choices = []
    for key, role in config.SAMPLE_ROLES.items():
        if not current or current.lower() in key.lower() or current.lower() in role["name"].lower():
            choices.append(app_commands.Choice(name=f"{role['name']} ({key})", value=key))
    for key, role in config.config.custom_roles.items():
        if not current or current.lower() in key.lower() or current.lower() in role["name"].lower():
            choices.append(app_commands.Choice(name=f"{role['name']} ⭐", value=f"custom_{key}"))
    return choices[:25]

# --- CHARACTER WEBHOOK SYSTEM: MODALS & AUTOCOMPLETE ---
class CreateCharacterModal(discord.ui.Modal, title="Tạo Character mới"):
    name_input = discord.ui.TextInput(
        label="Tên Character",
        placeholder="VD: Miku, Rem, Gojo...",
        required=True,
        max_length=100,
    )
    prompt_input = discord.ui.TextInput(
        label="System Prompt",
        style=discord.TextStyle.paragraph,
        placeholder="Mô tả tính cách, cách nói chuyện, bối cảnh... (teencode, vibe...)",
        required=True,
        max_length=2000,
    )

    def __init__(self, pfp: Optional[discord.Attachment] = None):
        super().__init__()
        self.pfp = pfp

    async def on_submit(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("❌ Lệnh chỉ dùng trong server!", ephemeral=True)
            return

        # Kiểm tra quyền Manage Roles
        if not interaction.guild.me.guild_permissions.manage_roles:
            await interaction.response.send_message(
                "❌ Bot thiếu quyền **Manage Roles** để tạo role! 🥀",
                ephemeral=True,
            )
            return
        if not interaction.user.guild_permissions.manage_roles and interaction.user.id != config.OWNER_ID:
            await interaction.response.send_message(
                "❌ Bạn cần quyền **Manage Roles** để tạo Character!",
                ephemeral=True,
            )
            return

        name = self.name_input.value.strip()
        system_prompt = self.prompt_input.value.strip()

        if not name or not system_prompt:
            await interaction.response.send_message("❌ Thiếu tên hoặc System Prompt!", ephemeral=True)
            return

        # Kiểm tra avatar size nếu có
        avatar_url = ""
        if self.pfp:
            if self.pfp.size > MAX_AVATAR_SIZE:
                await interaction.response.send_message(
                    f"❌ File avatar quá lớn ({self.pfp.size / 1024 / 1024:.1f}MB) — phải < 20MB!",
                    ephemeral=True,
                )
                return
            # Validate là ảnh
            if self.pfp.content_type and not self.pfp.content_type.startswith("image/"):
                await interaction.response.send_message("❌ Avatar phải là file ảnh!", ephemeral=True)
                return
            avatar_url = self.pfp.url
        else:
            # Thử lấy từ pending (trường hợp user gửi file kèm lệnh)
            pending = _pending_character_pfps.pop(interaction.user.id, None)
            if pending:
                if pending.size > MAX_AVATAR_SIZE:
                    await interaction.response.send_message(f"❌ File avatar quá lớn — phải < 20MB!", ephemeral=True)
                    return
                avatar_url = pending.url

        # Nếu vẫn không có avatar, dùng default (optional, cho phép tạo không cần avatar nhưng spec yêu cầu có)
        if not avatar_url:
            avatar_url = ""  # Webhook sẽ fallback avatar mặc định

        # Kiểm tra trùng tên role/character trong guild
        guild_chars = config.get_guild_characters(interaction.guild.id)
        for c in guild_chars.values():
            if c["name"].lower() == name.lower():
                await interaction.response.send_message(
                    f"❌ Đã có Character tên **{name}** rồi! Dùng tên khác nhé.",
                    ephemeral=True,
                )
                return

        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            # Tạo Role mới trên Server trùng tên với Character - mentionable để @tag được
            new_role = await interaction.guild.create_role(
                name=name,
                mentionable=True,
                reason=f"Character created by {interaction.user} via /character create",
            )
        except discord.Forbidden:
            await interaction.followup.send("❌ Bot không có quyền tạo Role (Forbidden)! Kiểm tra role hierarchy 🥀", ephemeral=True)
            return
        except discord.HTTPException as e:
            await interaction.followup.send(f"❌ Lỗi khi tạo role: `{e}`", ephemeral=True)
            return

        # Lưu vào DB/JSON
        config.add_character(interaction.guild.id, new_role.id, name, avatar_url, system_prompt)
        config.save_all_data()

        embed = discord.Embed(
            title="✅ Đã tạo Character",
            description=(
                f"**Tên:** {name}\n"
                f"**Role:** {new_role.mention} (`{new_role.id}`)\n"
                f"**Avatar:** {'Đã đính kèm ✅' if avatar_url else 'Chưa có (webhook sẽ dùng default)'}\n"
                f"**System Prompt:** {system_prompt[:300]}{'...' if len(system_prompt)>300 else ''}\n\n"
                f"💡 Mention {new_role.mention} trong chat để gọi Character!"
            ),
            color=SUCCESS_COLOR,
        )
        if avatar_url:
            embed.set_thumbnail(url=avatar_url)
        embed.set_footer(text="Dùng /character edit để sửa, /character delete để xóa")
        await interaction.followup.send(embed=embed, ephemeral=True)


class EditCharacterModal(discord.ui.Modal, title="Chỉnh sửa Character"):
    name_input = discord.ui.TextInput(
        label="Tên Character (mới)",
        placeholder="Để trống nếu không đổi - sẽ giữ nguyên",
        required=False,
        max_length=100,
    )
    prompt_input = discord.ui.TextInput(
        label="System Prompt (mới)",
        style=discord.TextStyle.paragraph,
        placeholder="Để trống nếu không đổi",
        required=False,
        max_length=2000,
    )

    def __init__(self, guild_id: int, role_id: int, current: dict, pfp: Optional[discord.Attachment] = None):
        super().__init__()
        self.guild_id = guild_id
        self.role_id = role_id
        self.current = current
        self.pfp = pfp
        # Pre-fill với giá trị hiện tại
        self.name_input.default = current.get("name", "")
        self.prompt_input.default = current.get("system_prompt", "")

    async def on_submit(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("❌ Chỉ dùng trong server!", ephemeral=True)
            return

        new_name = self.name_input.value.strip()
        new_prompt = self.prompt_input.value.strip()

        # Nếu để trống thì giữ nguyên
        if not new_name:
            new_name = self.current["name"]
        if not new_prompt:
            new_prompt = self.current["system_prompt"]

        # Avatar handling
        new_avatar = self.current.get("avatar_url", "")
        pfp_to_check = self.pfp or _pending_character_pfps.pop(interaction.user.id, None)
        if pfp_to_check:
            if pfp_to_check.size > MAX_AVATAR_SIZE:
                await interaction.response.send_message(f"❌ File avatar quá lớn — phải < 20MB!", ephemeral=True)
                return
            if pfp_to_check.content_type and not pfp_to_check.content_type.startswith("image/"):
                await interaction.response.send_message("❌ Avatar phải là file ảnh!", ephemeral=True)
                return
            new_avatar = pfp_to_check.url

        # Kiểm tra quyền Manage Roles nếu đổi tên
        role = interaction.guild.get_role(self.role_id)
        if new_name != self.current["name"]:
            if not interaction.guild.me.guild_permissions.manage_roles:
                await interaction.response.send_message("❌ Bot thiếu quyền **Manage Roles** để đổi tên Role!", ephemeral=True)
                return
            if role:
                try:
                    await role.edit(name=new_name, reason=f"Character edited by {interaction.user}")
                except discord.Forbidden:
                    await interaction.response.send_message("❌ Bot không có quyền sửa Role (Forbidden)!", ephemeral=True)
                    return
                except discord.HTTPException as e:
                    await interaction.response.send_message(f"❌ Lỗi khi sửa role: `{e}`", ephemeral=True)
                    return

        # Cập nhật DB
        config.update_character(self.guild_id, self.role_id, name=new_name, avatar_url=new_avatar, system_prompt=new_prompt)
        config.save_all_data()

        embed = discord.Embed(
            title="✅ Đã cập nhật Character",
            description=(
                f"**Tên:** {new_name}\n"
                f"**Role:** <@&{self.role_id}>\n"
                f"**Avatar:** {'Đã đổi ✅' if pfp_to_check else 'Giữ nguyên'}\n"
                f"**System Prompt:** {new_prompt[:300]}{'...' if len(new_prompt)>300 else ''}"
            ),
            color=SUCCESS_COLOR,
        )
        if new_avatar:
            embed.set_thumbnail(url=new_avatar)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def autocomplete_character_choices(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    """Autocomplete cho /character edit/delete — list characters của guild hiện tại"""
    choices: List[app_commands.Choice[str]] = []
    if not interaction.guild:
        return choices
    guild_chars = config.get_guild_characters(interaction.guild.id)
    for role_id_str, char in guild_chars.items():
        label = f"{char['name']} ({role_id_str})"
        # value là role_id str
        if not current or current.lower() in char["name"].lower() or current in role_id_str or current.lower() in label.lower():
            choices.append(app_commands.Choice(name=label[:100], value=role_id_str))
    return choices[:25]

def register_commands(bot):
    # --- GLOBAL ERROR HANDLER FOR PERMISSIONS ---
    @bot.event
    async def on_command_error(ctx, error):
        # Error handler cho prefix commands
        pass
    
    # Dùng cách này thay vì @bot.tree.error
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
                title="🥀 Lỗi hệ thống",
                description=err_desc,
                color=ERROR_COLOR
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    # --- ROLEPLAY COMMAND ---
    @bot.tree.command(name="roleplay", description="🎭 Bật/Tắt chế độ nhập vai với các tính cách có sẵn")
    @app_commands.describe(
        action="Chọn hành động muốn thực hiện",
        character="Tên nhân vật (chỉ cần khi chọn Bắt đầu)",
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="📋 Xem danh sách nhân vật", value="list"),
        app_commands.Choice(name="🎭 Bắt đầu nhập vai", value="start"),
        app_commands.Choice(name="🛑 Dừng nhập vai", value="stop"),
        app_commands.Choice(name="➕ Tạo role mới", value="create"),
    ])
    @app_commands.autocomplete(character=autocomplete_characters)
    async def roleplay(interaction: discord.Interaction, action: str = "list", character: Optional[str] = None):
        ctx_key = config.get_context_key(interaction)
        
        if action == "list":
            roles_list = "\n".join([f"- **{k}**: {v['name']}" for k, v in config.SAMPLE_ROLES.items()])
            if config.config.custom_roles:
                roles_list += "\n\n**⭐ Role tự tạo:**\n"
                roles_list += "\n".join([f"- **{k}**: {v['name']}" for k, v in config.config.custom_roles.items()])
            embed = discord.Embed(
                title="🎭 Danh sách tính cách có sẵn",
                description=f"Dùng `/roleplay start <tên>` để bắt đầu.\n\n{roles_list}",
                color=BRAND_COLOR
            )
            embed.set_footer(text="💡 Chọn action 'Bắt đầu' rồi chọn nhân vật từ dropdown!")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if action == "stop":
            config.set_context_state(ctx_key, False, None)
            embed = discord.Embed(
                title="🛑 Đã tắt chế độ nhập vai",
                description="Bot đã trở về trạng thái GenZ bình thường.",
                color=ERROR_COLOR
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if action == "create":
            await interaction.response.send_modal(CreateRoleModal())
            return

        if action == "start":
            selected_role = None
            if character and character.lower() in config.SAMPLE_ROLES:
                selected_role = config.SAMPLE_ROLES[character.lower()]
            elif character and character.startswith("custom_"):
                actual_key = character[7:]
                if actual_key in config.config.custom_roles:
                    selected_role = config.config.custom_roles[actual_key]
            
            if selected_role is None:
                roles_list = "\n".join([f"• `{k}` - {v['name']}" for k, v in config.SAMPLE_ROLES.items()])
                if config.config.custom_roles:
                    roles_list += "\n\n**Role tự tạo:**\n"
                    roles_list += "\n".join([f"• `custom_{k}` - {v['name']}" for k, v in config.config.custom_roles.items()])
                embed = discord.Embed(
                    title="❌ Sai tên nhân vật",
                    description=(
                        f"Bro chưa chọn nhân vật kìa! 🥀\n\n"
                        f"**Các nhân vật có sẵn:**\n"
                        f"{roles_list}\n\n"
                        f"📝 **Cách dùng:** Chọn action **Bắt đầu** → gõ tên nhân vật vào ô **character**"
                    ),
                    color=ERROR_COLOR
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
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
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return

        await interaction.response.send_message("❌ Lệnh không hợp lệ. Dùng `/roleplay list` để xem hướng dẫn.", ephemeral=True)

    # --- CHARACTER WEBHOOK SYSTEM (/character) ---
    @bot.tree.command(name="character", description="🎭 Quản lý Character Webhook System (create/edit/delete)")
    @app_commands.describe(
        action="Chọn hành động",
        character="Character cần edit/delete (chọn từ autocomplete)",
        pfp="Avatar cho Character (file ảnh < 20MB) — dùng cho create/edit",
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="➕ Create - Tạo Character mới", value="create"),
        app_commands.Choice(name="✏️ Edit - Sửa Character", value="edit"),
        app_commands.Choice(name="🗑️ Delete - Xóa Character + Role", value="delete"),
    ])
    @app_commands.autocomplete(character=autocomplete_character_choices)
    async def character_cmd(
        interaction: discord.Interaction,
        action: str,
        character: Optional[str] = None,
        pfp: Optional[discord.Attachment] = None,
    ):
        # Chỉ dùng trong guild
        if not interaction.guild:
            await interaction.response.send_message("❌ Lệnh `/character` chỉ dùng trong server!", ephemeral=True)
            return

        # Kiểm tra avatar size ngay tại command level (nếu có file)
        if pfp and pfp.size > MAX_AVATAR_SIZE:
            await interaction.response.send_message(
                f"❌ File avatar quá lớn ({pfp.size / 1024 / 1024:.1f}MB) — giới hạn < 20MB!",
                ephemeral=True,
            )
            return

        # Lưu pending pfp cho modal flow (create/edit cần modal)
        if pfp:
            _pending_character_pfps[interaction.user.id] = pfp

        # === CREATE ===
        if action == "create":
            # Mở Modal hỏi Name + System Prompt (pfp đã được attach ở param hoặc pending)
            # Nếu user không đính kèm file nhưng vẫn muốn tạo, cho phép (avatar optional)
            await interaction.response.send_modal(CreateCharacterModal(pfp=pfp))
            return

        # === EDIT ===
        if action == "edit":
            if not character:
                await interaction.response.send_message(
                    "❌ Vui lòng chọn Character cần sửa ở parameter `character` (gõ để autocomplete) !",
                    ephemeral=True,
                )
                return
            try:
                role_id = int(character)
            except ValueError:
                await interaction.response.send_message("❌ `character` không hợp lệ!", ephemeral=True)
                return

            char_data = config.get_character(interaction.guild.id, role_id)
            if not char_data:
                await interaction.response.send_message(
                    f"❌ Không tìm thấy Character với Role ID `{role_id}`! Có thể đã bị xóa.",
                    ephemeral=True,
                )
                return

            # Kiểm tra quyền
            if not interaction.user.guild_permissions.manage_roles and interaction.user.id != config.OWNER_ID:
                await interaction.response.send_message("❌ Bạn cần quyền **Manage Roles** để edit Character!", ephemeral=True)
                return

            # Mở Modal edit với pfp nếu có
            await interaction.response.send_modal(EditCharacterModal(interaction.guild.id, role_id, char_data, pfp=pfp))
            return

        # === DELETE ===
        if action == "delete":
            if not character:
                await interaction.response.send_message(
                    "❌ Vui lòng chọn Character cần xóa ở parameter `character`!",
                    ephemeral=True,
                )
                return
            try:
                role_id = int(character)
            except ValueError:
                await interaction.response.send_message("❌ `character` không hợp lệ!", ephemeral=True)
                return

            char_data = config.get_character(interaction.guild.id, role_id)
            if not char_data:
                await interaction.response.send_message(f"❌ Không tìm thấy Character với Role ID `{role_id}`!", ephemeral=True)
                return

            # Kiểm tra quyền Manage Roles
            if not interaction.user.guild_permissions.manage_roles and interaction.user.id != config.OWNER_ID:
                await interaction.response.send_message("❌ Bạn cần quyền **Manage Roles** để xóa Character!", ephemeral=True)
                return
            if not interaction.guild.me.guild_permissions.manage_roles:
                await interaction.response.send_message("❌ Bot thiếu quyền **Manage Roles** để xóa Role!", ephemeral=True)
                return

            await interaction.response.defer(ephemeral=True, thinking=True)

            # Xóa Role trên Discord trước
            role = interaction.guild.get_role(role_id)
            role_deleted = False
            role_error = None
            if role:
                try:
                    await role.delete(reason=f"Character delete by {interaction.user} via /character delete")
                    role_deleted = True
                except discord.Forbidden as e:
                    role_error = f"Forbidden: {e}"
                except discord.NotFound:
                    role_deleted = True  # Role đã không tồn tại
                except discord.HTTPException as e:
                    role_error = str(e)
            else:
                # Role không tồn tại trên server nhưng vẫn có trong DB -> coi như đã xóa
                role_deleted = True

            if role_error:
                await interaction.followup.send(
                    f"⚠️ Không thể xóa Role <@&{role_id}> : `{role_error}`\nVẫn sẽ xóa dữ liệu Character trong DB nếu bạn xác nhận.",
                    ephemeral=True,
                )
                # Không return, vẫn xóa DB? Theo spec phải xóa cả 2, nhưng nếu role không xóa được thì báo lỗi
                # Ở đây ta vẫn tiếp tục xóa DB để tránh rác, nhưng thông báo rõ
                # Nếu muốn strict, có thể return

            # Xóa dữ liệu trong DB/JSON — QUAN TRỌNG: tránh rác server
            deleted = config.delete_character(interaction.guild.id, role_id)
            if deleted:
                config.save_all_data()
                # Xóa pending pfp nếu có
                _pending_character_pfps.pop(interaction.user.id, None)
                embed = discord.Embed(
                    title="🗑️ Đã xóa Character",
                    description=(
                        f"**Tên:** {deleted['name']}\n"
                        f"**Role ID:** `{role_id}`\n"
                        f"**Role Discord:** {'Đã xóa ✅' if role_deleted and not role_error else '⚠️ Không xóa được (xem lỗi trên)'}\n"
                        f"**DB:** Đã xóa khỏi `data/characters.json` ✅"
                    ),
                    color=SUCCESS_COLOR,
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send("❌ Lỗi khi xóa Character khỏi DB!", ephemeral=True)
            return

        await interaction.response.send_message("❌ Action không hợp lệ!", ephemeral=True)

    # --- SETTING COMMAND ---
    @bot.tree.command(name="setting", description="[Admin/Owner] Tùy chỉnh cấu hình bot cho server")
    @app_commands.describe(
        max_tokens="Số token tối đa (128-8192)",
        temperature="Độ sáng tạo (0.0-2.0)",
        chat_enabled="Bật/tắt chat AI trong server",
        send_gif="Bật/tắt gửi GIF từ Giphy (true/false)"
    )
    async def setting(
        interaction: discord.Interaction,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        chat_enabled: Optional[bool] = None,
        send_gif: Optional[bool] = None,
    ):
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
        
        if not interaction.guild:
            embed = discord.Embed(
                title="❌ Không hỗ trợ DM",
                description="Lệnh `/setting` chỉ dùng được trong server.",
                color=ERROR_COLOR
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        guild_id = str(interaction.guild.id)
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
            changed.append(f"chat_enabled (server này): {chat_enabled}")
            # Nếu là Owner -> áp dụng global + tất cả server bot đang ở (theo yêu cầu tắt toàn bộ)
            if interaction.user.id == config.OWNER_ID:
                config.config.is_chat_enabled = chat_enabled
                updated = 0
                for g in bot.guilds:
                    gid = str(g.id)
                    gs = config.GUILD_SETTINGS.get(gid, {})
                    gs["chat_enabled"] = chat_enabled
                    config.GUILD_SETTINGS[gid] = gs
                    updated += 1
                # Đảm bảo guild hiện tại đã được đồng bộ (tránh double)
                if updated == 0:
                    # Bot chưa ready hoặc không có guild nào khác, vẫn set global
                    pass
                changed.append(f"global chat_enabled: {chat_enabled} (đã áp dụng cho {updated} server + DM)")
        
        if send_gif is not None:
            current["send_gif"] = send_gif
            changed.append(f"send_gif: {send_gif}")
        
        if not changed:
            max_t = current.get("max_tokens", config.DEFAULT_MAX_TOKENS)
            temp = current.get("temperature", config.DEFAULT_TEMPERATURE)
            enabled = current.get("chat_enabled", True)
            gif_enabled = current.get("send_gif", True)
            global_enabled = config.config.is_chat_enabled
            
            embed = discord.Embed(
                title="⚙️ Cấu hình server hiện tại",
                color=BRAND_COLOR,
                description=f"**Server:** {interaction.guild.name}"
            )
            embed.add_field(name="Max Tokens", value=str(max_t), inline=True)
            embed.add_field(name="Temperature", value=str(temp), inline=True)
            embed.add_field(name="Chat Enabled (server)", value="✅ Bật" if enabled else "❌ Tắt", inline=True)
            embed.add_field(name="Send GIF", value="✅ Bật" if gif_enabled else "❌ Tắt", inline=True)
            embed.add_field(name="Global Chat", value="✅ Bật" if global_enabled else "❌ Tắt (tất cả server)", inline=True)
            embed.set_footer(text="Dùng /setting <option> <value> để thay đổi | Owner: chat_enabled sẽ áp dụng toàn bộ server")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        config.GUILD_SETTINGS[guild_id] = current
        config.save_all_data()
        
        embed = discord.Embed(
            title="✅ Đã cập nhật cấu hình",
            color=SUCCESS_COLOR,
            description="\n".join([f"• Đã đặt **{c}**" for c in changed])
        )
        await interaction.response.send_message(embed=embed, delete_after=10)
    
    # --- SETUP COMMAND ---
    @bot.tree.command(name="setup", description="[Admin/Owner] Cấu hình OpenAI-compatible provider cho server")
    async def setup(
        interaction: discord.Interaction,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        is_admin = interaction.user.guild_permissions.administrator if interaction.guild else False
        is_owner = interaction.user.id == config.OWNER_ID
        if not is_admin and not is_owner:
            embed = discord.Embed(
                title="🚫 Access Denied",
                description="Bạn cần quyền Administrator hoặc là Owner để dùng lệnh này.",
                color=ERROR_COLOR,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if not interaction.guild:
            embed = discord.Embed(
                title="❌ Không hỗ trợ DM",
                description="Lệnh `/setup` chỉ dùng được trong server.",
                color=ERROR_COLOR,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        guild_id = str(interaction.guild.id)
        current = config.PROVIDER_SETTINGS.get(guild_id, {})
        changed = []

        if base_url is not None:
            if not base_url.startswith(("http://", "https://")):
                await interaction.response.send_message(
                    "❌ `base_url` phải bắt đầu bằng http:// hoặc https://!",
                    ephemeral=True,
                )
                return
            current["base_url"] = base_url.rstrip("/")
            changed.append(f"base_url: {base_url}")

        if api_key is not None:
            if not api_key.strip():
                await interaction.response.send_message(
                    "❌ `api_key` không được để trống!",
                    ephemeral=True,
                )
                return
            current["api_key"] = api_key.strip()
            changed.append("api_key: ✅ đã đặt")

        if model is not None:
            if not model.strip():
                await interaction.response.send_message(
                    "❌ `model` không được để trống!",
                    ephemeral=True,
                )
                return
            current["model"] = model.strip()
            changed.append(f"model: {model}")

        if not changed:
            if current:
                embed = discord.Embed(
                    title="🔧 Cấu hình provider hiện tại",
                    color=BRAND_COLOR,
                    description=f"**Server:** {interaction.guild.name}",
                )
                embed.add_field(name="Base URL", value=current.get("base_url", "❌"), inline=False)
                embed.add_field(name="Model", value=current.get("model", "gpt-4o-mini"), inline=True)
                embed.add_field(name="API Key", value="✅ đã đặt" if current.get("api_key") else "❌", inline=True)
                embed.set_footer(text="Dùng /setup <option> <value> để thay đổi")
            else:
                embed = discord.Embed(
                    title="🔧 Chưa cấu hình provider",
                    color=ERROR_COLOR,
                    description="Server chưa set provider nào. Dùng `/setup base_url:... api_key:... model:...` để thêm.",
                )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        config.PROVIDER_SETTINGS[guild_id] = current
        config.save_all_data()

        embed = discord.Embed(
            title="✅ Đã cập nhật provider",
            color=SUCCESS_COLOR,
            description="\n".join([f"• Đã đặt **{c}**" for c in changed]),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    # --- JOKE COMMAND ---
    @bot.tree.command(name="joke", description="Tạo joke hài hước với username và chủ đề")
    async def joke(interaction: discord.Interaction, username: discord.Member, topic: str = None):
        if config.is_rpd_locked():
            _, remaining = config.check_flash_rpd()
            embed = discord.Embed(
                title="😴 Bot đã hết lượt hôm nay!",
                description=(
                    f"Hôm nay đã dùng hết **{config.FLASH_RPD_LIMIT}** lượt RPD rồi 🥀\n\n"
                    f"Bot sẽ hoạt động trở lại vào **0:00** hôm nay.\n\n"
                    f"Quay lại vào ngày mai nha! 🕐"
                ),
                color=ERROR_COLOR,
            )
            embed.set_footer(text="=)) mai t lại lên sóng!")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        target_name = username.display_name or username.name
        
        prompt = f"""
Hãy tạo một joke hài hước về người tên là "{target_name}".
Joke phải:
- Ngắn gọn, hài hước, dễ hiểu
- Có liên quan đến display name của người này
- Dùng ngôn ngữ GenZ, teencode (nx, th, cx, vs, k, thx, j, z...)
- Có ít nhất 1 emoji trong danh sách cho phép (❤️‍🩹, 🌹, 💔, 🥀, 😡, 🐧, 🫩) - Cấm emoji khác
"""
        
        if topic:
            prompt += f"\n- Chủ đề của joke là: {topic}"
        
        prompt += "\nChỉ trả về joke duy nhất, không giải thích, không giới thiệu gì cả."
        
        await interaction.response.defer()
        
        try:
            model = config.get_model()
            response = await model.generate_content_async([prompt])
            joke_text = config.extract_response_text(response)
            
            if not joke_text:
                joke_text = "API bị mù rồi, nói lại phát 🥀"
            
            embed = discord.Embed(
                title="🥀 Joke Hài Hước",
                description=f"**Joke về {target_name}:**\n\n{joke_text}",
                color=BRAND_COLOR
            )
            embed.set_footer(text="Được tạo bởi GenA-Bot với Gemini AI")
            
            await interaction.followup.send(embed=embed)
            
            if hasattr(model, 'model_name') and config.is_flash_model(model.model_name):
                config.increment_flash_rpd()
            
        except Exception as error:
            error_str = str(error).lower()
            
            if "429" in error_str or "rate" in error_str or "quota" in error_str or "resource exhausted" in error_str:
                config.lock_rpd_until_midnight()
                embed = discord.Embed(
                    title="😴 Bot đã hết lượt hôm nay!",
                    description=(
                        f"Hôm nay đã dùng hết **{config.FLASH_RPD_LIMIT}** lượt RPD rồi 🥀\n\n"
                        f"Bot sẽ hoạt động trở lại vào **0:00** hôm nay.\n\n"
                        f"Quay lại vào ngày mai nha! 🕐"
                    ),
                    color=ERROR_COLOR,
                )
                embed.set_footer(text="=)) mai t lại lên sóng!")
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                embed = discord.Embed(
                    title="🥀 Lỗi hệ thống",
                    description=f"Đã xảy ra lỗi khi tạo joke: `{error}`",
                    color=ERROR_COLOR
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
    # Thêm vào cuối file cmd.py, trong hàm register_commands(bot)

    # --- QUOTA SETTING COMMAND (OWNER ONLY) ---
   # --- QUOTA SETTING COMMAND (OWNER ONLY) ---
    @bot.tree.command(name="quota_setting", description="[Owner] Tùy chỉnh quota RPD cho bot")
    @app_commands.describe(
        action="Chọn hành động: set (đặt lại), reset (reset về mặc định), view (xem trạng thái)",
        rpd_count="Số RPD hiện tại (chỉ cần khi action='set')",
        rpd_limit="Giới hạn RPD tối đa (chỉ cần khi action='set')"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="📊 Xem trạng thái RPD", value="view"),
        app_commands.Choice(name="🔧 Đặt lại RPD", value="set"),
        app_commands.Choice(name="🔄 Reset về mặc định", value="reset"),
        app_commands.Choice(name="🔓 Mở khóa API lock", value="unlock")
    ])
    async def quota_setting(
        interaction: discord.Interaction,
        action: str = "view",
        rpd_count: Optional[int] = None,
        rpd_limit: Optional[int] = None
    ):
        """Quản lý quota RPD của bot"""
        
        # Chỉ Owner mới được dùng
        if interaction.user.id != config.OWNER_ID:
            embed = discord.Embed(
                title="🚫 Access Denied",
                description="Chỉ Owner mới được quản lý quota RPD.",
                color=ERROR_COLOR
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Lấy instance config
        bot_config = config.config

        # === ACTION: VIEW ===
        if action == "view":
            # Reset RPD nếu sang ngày mới
            bot_config._reset_rpd_if_new_day()
            
            remaining = config.FLASH_RPD_LIMIT - bot_config.rpd_count
            is_locked = bot_config.is_rpd_locked()
            lock_time = ""
            if bot_config.api_locked_until > time.time():
                remaining_time = bot_config.api_locked_until - time.time()
                hours = int(remaining_time // 3600)
                minutes = int((remaining_time % 3600) // 60)
                lock_time = f"⏰ {hours}h {minutes}m còn lại"
            else:
                lock_time = "🔓 Không bị khóa"
            
            embed = discord.Embed(
                title="📊 Trạng thái RPD",
                color=BRAND_COLOR,
                description=f"**Server:** {interaction.guild.name if interaction.guild else 'DM'}"
            )
            embed.add_field(
                name="📈 RPD hiện tại",
                value=f"`{bot_config.rpd_count}` / `{config.FLASH_RPD_LIMIT}`",
                inline=True
            )
            embed.add_field(
                name="📉 RPD còn lại",
                value=f"`{max(0, remaining)}`",
                inline=True
            )
            embed.add_field(
                name="🔒 Trạng thái",
                value="🔴 Đã khóa" if is_locked else "🟢 Hoạt động",
                inline=True
            )
            embed.add_field(
                name="⏰ API Lock",
                value=lock_time,
                inline=False
            )
            embed.add_field(
                name="📅 Ngày reset",
                value=bot_config.rpd_date or "Chưa có",
                inline=False
            )
            embed.set_footer(text="Dùng /quota_setting set để thay đổi giá trị")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # === ACTION: SET ===
        if action == "set":
            if rpd_count is None or rpd_limit is None:
                embed = discord.Embed(
                    title="❌ Thiếu tham số",
                    description="Khi action='set' cần cung cấp cả `rpd_count` và `rpd_limit`",
                    color=ERROR_COLOR
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            if rpd_count < 0 or rpd_count > rpd_limit:
                embed = discord.Embed(
                    title="❌ Giá trị không hợp lệ",
                    description=f"`rpd_count` ({rpd_count}) phải từ 0 đến `rpd_limit` ({rpd_limit})",
                    color=ERROR_COLOR
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            if rpd_limit < 0 or rpd_limit > 2000:
                embed = discord.Embed(
                    title="❌ Giá trị không hợp lệ",
                    description="`rpd_limit` phải từ 0 đến 2000",
                    color=ERROR_COLOR
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Lưu giá trị cũ
            old_count = bot_config.rpd_count
            old_limit = config.FLASH_RPD_LIMIT
            old_date = bot_config.rpd_date
            
            # Cập nhật giá trị mới
            bot_config.rpd_count = rpd_count
            # Cần sửa FLASH_RPD_LIMIT trong config (global variable)
            config.FLASH_RPD_LIMIT = rpd_limit
            
            # Reset date về hôm nay
            bot_config.rpd_date = datetime.now(timezone(timedelta(hours=7))).strftime("%Y-%m-%d")
            
            # Mở khóa API nếu đang bị lock
            bot_config.api_locked_until = 0.0
            
            # Lưu config
            config.save_all_data()
            
            embed = discord.Embed(
                title="✅ Đã cập nhật RPD",
                color=SUCCESS_COLOR,
                description=f"**Server:** {interaction.guild.name if interaction.guild else 'DM'}"
            )
            embed.add_field(
                name="📊 RPD cũ → mới",
                value=f"`{old_count}` → `{rpd_count}` / `{old_limit}` → `{rpd_limit}`",
                inline=False
            )
            embed.add_field(
                name="📅 Ngày reset",
                value=bot_config.rpd_date,
                inline=True
            )
            embed.add_field(
                name="🔓 API Lock",
                value="✅ Đã mở khóa",
                inline=True
            )
            embed.set_footer(text="Thay đổi sẽ áp dụng ngay lập tức")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # === ACTION: RESET ===
        if action == "reset":
            old_count = bot_config.rpd_count
            old_limit = config.FLASH_RPD_LIMIT
            
            # Reset về mặc định
            bot_config.rpd_count = 0
            config.FLASH_RPD_LIMIT = 500  # Giá trị mặc định
            bot_config.rpd_date = datetime.now(timezone(timedelta(hours=7))).strftime("%Y-%m-%d")
            bot_config.api_locked_until = 0.0
            
            config.save_all_data()
            
            embed = discord.Embed(
                title="🔄 Đã reset RPD về mặc định",
                color=SUCCESS_COLOR,
                description=f"**Server:** {interaction.guild.name if interaction.guild else 'DM'}"
            )
            embed.add_field(
                name="📊 RPD cũ → mới",
                value=f"`{old_count}` → `0` / `{old_limit}` → `500`",
                inline=False
            )
            embed.add_field(
                name="📅 Ngày reset",
                value=bot_config.rpd_date,
                inline=True
            )
            embed.add_field(
                name="🔓 API Lock",
                value="✅ Đã mở khóa",
                inline=True
            )
            embed.set_footer(text="Đã reset về cấu hình mặc định")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # === ACTION: UNLOCK ===
        if action == "unlock":
            if bot_config.api_locked_until == 0.0 and not bot_config.is_rpd_locked():
                embed = discord.Embed(
                    title="🔓 API đang hoạt động",
                    description="Bot không bị khóa API, không cần mở khóa.",
                    color=BRAND_COLOR
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Mở khóa API
            bot_config.api_locked_until = 0.0
            config.save_all_data()
            
            embed = discord.Embed(
                title="🔓 Đã mở khóa API",
                description="API lock đã được gỡ bỏ, bot có thể tiếp tục hoạt động.",
                color=SUCCESS_COLOR
            )
            embed.set_footer(text="Bot đã sẵn sàng hoạt động trở lại")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Fallback
        embed = discord.Embed(
            title="❌ Action không hợp lệ",
            description="Dùng: `view`, `set`, `reset`, hoặc `unlock`",
            color=ERROR_COLOR
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    # --- PING COMMAND ---
    @bot.tree.command(name="ping", description="Kiểm tra độ trễ của bot")
    async def ping(interaction: discord.Interaction):
        latency = round(bot.latency * 1000)
        await interaction.response.send_message(f"Pong! 🏓 Độ trễ: {latency}ms")

    # --- MODEL COMMAND ---
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
        if interaction.user.id != config.OWNER_ID:
            embed = discord.Embed(
                title="🚫 Access Denied",
                description="Chỉ Owner mới được quản lý model Gemini.",
                color=ERROR_COLOR
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

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

        if action == "current":
            embed = discord.Embed(
                title="🤖 Model hiện tại",
                description=f"Bot đang dùng model: `{config.current_model_id}`",
                color=SUCCESS_COLOR
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if action == "set":
            if not model_id:
                await interaction.response.send_message(
                    "❌ Thiếu `model_id`! Dùng `/model set <model_id>`",
                    ephemeral=True
                )
                return
            
            if model_id not in config.AVAILABLE_MODELS:
                available = ", ".join(f"`{m}`" for m in config.AVAILABLE_MODELS)
                await interaction.response.send_message(
                    f"❌ Model `{model_id}` không hợp lệ!\n\nModel có sẵn: {available}",
                    ephemeral=True
                )
                return
            
            old_model = config.current_model_id
            success = config.set_current_model(model_id)
            
            if success:
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

        await interaction.response.send_message(
            "❌ Action không hợp lệ. Dùng: `list`, `current`, hoặc `set`",
            ephemeral=True
        )

    # --- USAGE COMMAND ---
    @bot.tree.command(name="usage", description="📊 Kiểm tra số lượt chat của người dùng")
    @app_commands.describe(
        user="Người dùng cần kiểm tra (nhập ID hoặc @mention)",
    )
    @app_commands.autocomplete(user=autocomplete_users)
    async def usage(interaction: discord.Interaction, user: Optional[str] = None):
        # Nếu không truyền user, mặc định là người gọi lệnh
        if user is None:
            target_user = interaction.user
        else:
            # Thử parse user từ string (có thể là ID hoặc mention)
            target_user = None
            # Trường hợp 1: user là ID số
            if user.isdigit():
                try:
                    if interaction.guild:
                        target_user = await interaction.guild.fetch_member(int(user))
                    else:
                        target_user = await bot.fetch_user(int(user))
                except Exception:
                    pass
            
            # Trường hợp 2: user là mention <@123456789>
            if not target_user:
                import re
                mention_match = re.match(r"<@!?(\d+)>", user.strip())
                if mention_match:
                    user_id = int(mention_match.group(1))
                    try:
                        if interaction.guild:
                            target_user = await interaction.guild.fetch_member(user_id)
                        else:
                            target_user = await bot.fetch_user(user_id)
                    except Exception:
                        pass
            
            # Trường hợp 3: không tìm thấy, báo lỗi
            if not target_user:
                embed = discord.Embed(
                    title="❌ Không tìm thấy người dùng",
                    description=f"Không tìm thấy người dùng với thông tin: `{user}`\n\n💡 **Gợi ý:**\n• Nhập trực tiếp ID người dùng\n• Hoặc dùng @mention để tag người dùng",
                    color=ERROR_COLOR
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
        
        # Lấy thông tin RPD counter của user này
        # Lưu ý: Hiện tại bot chỉ track tổng RPD, chưa track per-user
        # Nên sẽ hiển thị thông tin chung
        has_remaining, remaining = config.check_flash_rpd()
        total_limit = config.FLASH_RPD_LIMIT
        used_count = total_limit - remaining
        
        # Tạo embed hiển thị
        embed = discord.Embed(
            title=f"📊 Thống kê sử dụng của {target_user.display_name}",
            color=BRAND_COLOR,
            description=(
                f"**User ID:** `{target_user.id}`\n"
                f"**Username:** {target_user.name}\n"
            )
        )
        
        # Thêm thông tin về hạn mức
        embed.add_field(
            name="🎯 Hạn mức hôm nay",
            value=(
                f"Đã dùng: **{used_count}**/{total_limit}\n"
                f"Còn lại: **{remaining}** lượt\n"
                f"Trạng thái: {'✅ Bình thường' if has_remaining else '⚠️ Hết lượt'}"
            ),
            inline=False
        )
        
        # Ghi chú về cơ chế RPD
        embed.set_footer(
            text="💡 Lưu ý: Bot hiện đang tính RPD chung cho tất cả người dùng trong server. "
                 "Hạn mức sẽ reset vào 0:00 mỗi ngày (giờ Việt Nam)."
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
