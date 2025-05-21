from nextcord.ext import commands
from nextcord import Interaction, slash_command, Embed
from db.database import count_active_games, count_active_players
from datetime import datetime

class XOStatus(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @slash_command(name="status", description="ดูสถานะของระบบ XO")
    async def status(self, interaction: Interaction):
        await interaction.response.defer()

        num_games = await count_active_games()
        num_players = await count_active_players()

        embed = Embed(
            title="📊 สถานะระบบ XO",
            description=f"""🕹️ เกมที่กำลังดำเนินอยู่: **{num_games}** เกม
👥 ผู้เล่นที่กำลังเล่นอยู่: **{num_players}** คน

🕒 เวลาปัจจุบัน: {datetime.utcnow().strftime('%d %B %Y - %H:%M UTC')}

**💡 คำแนะนำสำหรับคุณ:**
• ใช้คำสั่ง `/xomatch` เพื่อเริ่มเล่นเกม
• ตรวจสอบว่าเปิดรับข้อความ DM จากบอทเพื่อให้ระบบส่งเกมหาได้

ขอให้สนุกกับการเล่น XO!""",
            color=0x1ABC9C
        )

        await interaction.followup.send(embed=embed)

def setup(bot):
    bot.add_cog(XOStatus(bot))
