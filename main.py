import json
import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
from threading import Thread
from flask import Flask

app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# تحميل الإعدادات والتوكن
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# واجهة أزرار التحكم داخل التذكرة (إغلاق / حذف)
class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="قفل التذكرة 🔒", style=discord.ButtonStyle.secondary, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.channel
        
        # سحب صلاحية الكتابة من العضو صاحب التذكرة
        for target, overwrite in channel.overwrites.items():
            if isinstance(target, discord.Member) and not target.guild_permissions.manage_channels:
                await channel.set_permissions(target, send_messages=False, read_messages=True)
                
        button.disabled = True
        await interaction.response.edit_message(view=self)
        await channel.send("تم إغلاق التذكرة. يمكن للإدارة الآن اتخاذ الإجراء المناسب أو حذفها.")

    @discord.ui.button(label="حذف التذكرة 🗑️", style=discord.ButtonStyle.danger, custom_id="delete_ticket")
    async def delete_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        staff_role = interaction.guild.get_role(config["STAFF_ROLE_ID"])
        if staff_role not in interaction.user.roles and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("عذراً، هذا الخيار متاح لفريق الدعم فقط.", ephemeral=True)
            return

        await interaction.response.send_message("سيتم حذف التذكرة خلال 5 ثوانٍ...")
        await asyncio.sleep(5)
        await interaction.channel.delete()

# واجهة زر فتح التذكرة الرئيسي
class TicketLaunchView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label=config["BUTTON_LABEL"], style=discord.ButtonStyle.primary, emoji="📩", custom_id="open_ticket_btn")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        member = interaction.user
        staff_role = guild.get_role(config["STAFF_ROLE_ID"])

        # منع تكرار فتح تذاكر لنفس العضو
        existing_channel = discord.utils.get(guild.text_channels, name=f"{config['TICKET_PREFIX']}{member.name}".lower())
        if existing_channel:
            await interaction.response.send_message(f"لديك تذكرة مفتوحة بالفعل: {existing_channel.mention}", ephemeral=True)
            return

        # ضبط خصوصية القناة
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
        }
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True)

        category = guild.get_channel(config["CATEGORY_ID"]) if config.get("CATEGORY_ID") else None

        channel = await guild.create_text_channel(
            name=f"{config['TICKET_PREFIX']}{member.name}",
            overwrites=overwrites,
            category=category,
            topic=f"تذكرة خاصة بالعضو {member.mention}"
        )

        embed = discord.Embed(
            title="تذكرة جديدة 🎫",
            description=f"أهلاً {member.mention}، يرجى كتابة استفسارك أو طلبك هنا وسيقوم فريق الدعم بالرد عليك قريباً.",
            color=discord.Color.green()
        )
        await channel.send(content=f"{member.mention} | {staff_role.mention if staff_role else ''}", embed=embed, view=TicketControlView())
        await interaction.response.send_message(f"تم إنشاء تذكرتك بنجاح: {channel.mention}", ephemeral=True)

@bot.event
async def on_ready():
    bot.add_view(TicketLaunchView())
    bot.add_view(TicketControlView())
    print(f"تم تشغيل البوت بنجاح تحت اسم: {bot.user}")

# أمر الإدارة لإرسال لوحة التذاكر
@bot.command(name="setup_tickets")
@commands.has_permissions(administrator=True)
async def setup_tickets(ctx):
    target_channel_id = config.get("PANEL_CHANNEL_ID") or ctx.channel.id
    target_channel = bot.get_channel(target_channel_id)

    embed = discord.Embed(
        title=config["EMBED_TITLE"],
        description=config["EMBED_DESCRIPTION"],
        color=discord.Color.blue()
    )
    await target_channel.send(embed=embed, view=TicketLaunchView())
    await ctx.send(f"تم إرسال لوحة التذاكر إلى {target_channel.mention} بنجاح.")

if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)
