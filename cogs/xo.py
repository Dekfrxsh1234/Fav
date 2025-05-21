from nextcord.ext import commands
from nextcord import Interaction, slash_command, Embed
from db.database import (
    add_to_queue, find_match, create_game, get_game_state,
    is_in_queue, is_in_game
)
from game.views import XOGameView
from datetime import datetime

class XO(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @slash_command(name="xomatch", description="เข้าคิวเพื่อเล่นเกม XO")
    async def xomatch(self, interaction: Interaction):
        print("🔹 START: /xomatch called by", interaction.user)
        await interaction.response.defer(ephemeral=True)

        user = interaction.user
        user_id = user.id

        if await is_in_queue(user_id):
            embed = Embed(
                title="⛔ คุณอยู่ในคิวอยู่แล้ว",
                description="ไม่สามารถเข้าคิวซ้ำได้ กรุณารอระบบจับคู่ หรือใช้ `/cancel` เพื่อออกจากคิว",
                color=0xFF5733
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        if await is_in_game(user_id):
            embed = Embed(
                title="⚠️ คุณมีเกมที่ยังไม่จบ",
                description="กรุณาเล่นเกมที่ค้างไว้ให้จบก่อน หรือใช้คำสั่ง `/forfeit` เพื่อยอมแพ้",
                color=0xFFC300
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        await add_to_queue(user_id, str(user), interaction.guild.id, interaction.channel.id)
        print("✅ Added to queue:", user_id)

        opponent = await find_match(user_id)
        if opponent:
            print("✅ Found opponent:", opponent)
            game_id, _ = await create_game(user_id, opponent)
            print("✅ Game created:", game_id)

            state = await get_game_state(game_id)
            if not state:
                embed = Embed(
                    title="❗ โหลดสถานะเกมไม่สำเร็จ",
                    description="โปรดลองใหม่ภายหลัง หรือแจ้งผู้ดูแลระบบ",
                    color=0xE74C3C
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            view = XOGameView(
                game_id=game_id,
                player_x=state["player_x"],
                player_o=state["player_o"],
                board=state["board"],
                turn=state["turn"],
                start_time=state["start_time"]
            )

            try:
                user1 = await self.bot.fetch_user(state["player_x"])
                user2 = await self.bot.fetch_user(state["player_o"])
                print("📤 Sending DM to", user1, "and", user2)

                msg1 = await user1.send(content=view.current_turn_display(), view=view)
                msg2 = await user2.send(content=view.current_turn_display(), view=view)
                view.messages = [msg1, msg2]

                embed_dm = Embed(
                    title="🎮 เกมเริ่มแล้ว!",
                    description=f"""ผู้เล่น <@{state['player_x']}> พบกับ <@{state['player_o']}>
เกมได้ถูกส่งไปยัง DM ของคุณทั้งคู่แล้ว กรุณาตรวจสอบ!""",
                    color=0x2ECC71
                )

                await interaction.channel.send(
                    content=f"<@{state['player_x']}> <@{state['player_o']}>",
                    embed=embed_dm
                )

                await interaction.followup.send(embed=Embed(
                    description="✅ เกมของคุณเริ่มต้นแล้ว! เช็ค DM เพื่อเริ่มเล่น",
                    color=0x2ECC71
                ), ephemeral=True)

            except Exception as e:
                print("❌ Failed to send DM:", e)
                await interaction.followup.send(embed=Embed(
                    title="❗ ไม่สามารถส่ง DM ได้",
                    description="โปรดตรวจสอบว่าคุณเปิดรับข้อความจากสมาชิกในเซิร์ฟเวอร์",
                    color=0xE74C3C
                ), ephemeral=True)
        else:
            embed = Embed(
                title="⌛ เข้าคิวสำเร็จ",
                description="""ระบบกำลังรอผู้เล่นคนอื่นเข้าร่วม
⏳ โปรดเปิดรับข้อความ DM จากบอท และรอระบบจับคู่โดยอัตโนมัติ""",
                color=0x3498DB
            )
            embed.set_footer(text=f"เข้าคิวเมื่อ: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
            await interaction.followup.send(embed=embed, ephemeral=True)

def setup(bot):
    bot.add_cog(XO(bot))
