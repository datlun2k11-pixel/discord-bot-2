import discord
from discord import app_commands
import json
import os
import threading

# Thread lock for file operations
file_lock = threading.Lock()

def load_json(filepath, default):
    """Load JSON file with error handling for corrupted files."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # If file doesn't exist or is corrupted, return default and create new file
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(default, f, indent=2)
        return default

def save_json(filepath, data):
    """Save JSON file with thread lock to prevent race conditions."""
    with file_lock:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

async def setup_cmd(tree, config):
    @tree.command(name="server_setting", description="Quản lý setting server (Admin only)")
    @app_commands.checks.has_permissions(administrator=True)
    async def server_setting(interaction: discord.Interaction, action: str, role_name: str = None, channel_name: str = None):
        guild_id = str(interaction.guild_id)
        settings = load_json('server_settings.json', {})
        
        # Check if server settings exist
        if guild_id not in settings:
            await interaction.response.send_message("❌ Server này chưa được khởi tạo. Hãy dùng `/server_setting create` trước!", ephemeral=True)
            return
        
        if action == "create":
            if guild_id in settings:
                await interaction.response.send_message("⚠️ Server đã được khởi tạo rồi!", ephemeral=True)
                return
            settings[guild_id] = {"roles": {}, "channels": {}}
            save_json('server_settings.json', settings)
            await interaction.response.send_message("✅ Đã khởi tạo server settings!")
            
        elif action == "edit":
            if not role_name:
                await interaction.response.send_message("❌ Thiếu role_name!", ephemeral=True)
                return
            if role_name not in settings[guild_id]["roles"]:
                await interaction.response.send_message(f"❌ Role '{role_name}' không tồn tại!", ephemeral=True)
                return
            # Edit logic here
            await interaction.response.send_message(f"✅ Đã edit role {role_name}")
            
        elif action == "delete":
            if not role_name:
                await interaction.response.send_message("❌ Thiếu role_name!", ephemeral=True)
                return
            if role_name in settings[guild_id]["roles"]:
                del settings[guild_id]["roles"][role_name]
                save_json('server_settings.json', settings)
                await interaction.response.send_message(f"✅ Đã xóa role {role_name}")
            else:
                await interaction.response.send_message(f"❌ Role '{role_name}' không tồn tại!", ephemeral=True)
    
    @tree.command(name="kick", description="Kick thành viên (Admin only)")
    @app_commands.checks.has_permissions(administrator=True)
    async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "Không có lý do"):
        # Check bot permissions
        if not interaction.guild.me.guild_permissions.kick_members:
            await interaction.response.send_message("❌ Bot không có quyền KICK_MEMBERS!", ephemeral=True)
            return
        
        # Check role hierarchy
        if member.top_role >= interaction.guild.me.top_role:
            await interaction.response.send_message("❌ Không thể kick thành viên có role cao hơn hoặc bằng bot!", ephemeral=True)
            return
        
        try:
            await member.kick(reason=reason)
            await interaction.response.send_message(f"✅ Đã kick {member.mention}: {reason}")
        except Exception as e:
            await interaction.response.send_message(f"❌ Lỗi: {e}", ephemeral=True)
    
    @tree.command(name="ban", description="Ban thành viên (Admin only)")
    @app_commands.checks.has_permissions(administrator=True)
    async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "Không có lý do"):
        # Check bot permissions
        if not interaction.guild.me.guild_permissions.ban_members:
            await interaction.response.send_message("❌ Bot không có quyền BAN_MEMBERS!", ephemeral=True)
            return
        
        # Check role hierarchy
        if member.top_role >= interaction.guild.me.top_role:
            await interaction.response.send_message("❌ Không thể ban thành viên có role cao hơn hoặc bằng bot!", ephemeral=True)
            return
        
        try:
            await member.ban(reason=reason)
            await interaction.response.send_message(f"✅ Đã ban {member.mention}: {reason}")
        except Exception as e:
            await interaction.response.send_message(f"❌ Lỗi: {e}", ephemeral=True)
    
    @tree.command(name="roleplay", description="Bật/tắt chế độ roleplay")
    async def roleplay(interaction: discord.Interaction, enabled: bool):
        guild_id = str(interaction.guild_id)
        settings = load_json('server_settings.json', {})
        
        if guild_id not in settings:
            await interaction.response.send_message("❌ Server chưa được khởi tạo!", ephemeral=True)
            return
        
        settings[guild_id]["roleplay_enabled"] = enabled
        save_json('server_settings.json', settings)
        await interaction.response.send_message(f"✅ Roleplay đã {'bật' if enabled else 'tắt'}!")
    
    @tree.command(name="setting", description="Cài đặt bot (Admin only)")
    @app_commands.checks.has_permissions(administrator=True)
    async def setting(interaction: discord.Interaction, max_tokens: int = None, temperature: float = None, chat_enabled: bool = None):
        guild_id = str(interaction.guild_id)
        settings = load_json('server_settings.json', {})
        
        if guild_id not in settings:
            await interaction.response.send_message("❌ Server chưa được khởi tạo!", ephemeral=True)
            return
        
        if max_tokens is not None:
            settings[guild_id]["max_tokens"] = max_tokens
        if temperature is not None:
            settings[guild_id]["temperature"] = temperature
        if chat_enabled is not None:
            settings[guild_id]["chat_enabled"] = chat_enabled
        
        save_json('server_settings.json', settings)
        await interaction.response.send_message("✅ Đã cập nhật setting!")
