import logging
import asyncio # Added asyncio
import nextcord # Added nextcord for Color and User
from nextcord.ext import commands
from nextcord import Interaction, slash_command, Embed, SlashOption # Added SlashOption
from db.database import (
    add_to_queue, find_match, create_game, get_game_state,
    is_in_queue, is_in_game, get_leaderboard_data, get_profile_data # Added get_profile_data
)
from game.views import XOGameView
from datetime import datetime

logger = logging.getLogger(__name__)

class XO(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.matchmaking_lock = asyncio.Lock() # Initialize lock

    @slash_command(name="xomatch", description="เข้าคิวเพื่อเล่นเกม XO")
    async def xomatch(self, interaction: Interaction,
                       game_mode: str = SlashOption(
                           name="game_mode",
                           description="Choose the game mode",
                           required=True,
                           choices={"Casual": "casual", "Ranked": "ranked"}
                       )):
        logger.info(f"START: /xomatch called by {interaction.user} (ID: {interaction.user.id}) with game_mode: {game_mode}") # Added game_mode to log
        await interaction.response.defer(ephemeral=True)

        user = interaction.user
        user_id = user.id

        # Initial checks (outside the lock, for quick feedback)
        if await is_in_queue(user_id):
            embed = Embed(
                title="คุณอยู่ในคิวอยู่แล้ว", # Removed emoji
                description="ไม่สามารถเข้าคิวซ้ำได้ กรุณารอระบบจับคู่ หรือใช้ `/cancel` เพื่อออกจากคิว",
                color=0xFF5733
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        if await is_in_game(user_id):
            embed = Embed(
                title="คุณมีเกมที่ยังไม่จบ", # Removed emoji
                description="กรุณาเล่นเกมที่ค้างไว้ให้จบก่อน หรือใช้คำสั่ง `/forfeit` เพื่อยอมแพ้",
                color=0xFFC300
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        async with self.matchmaking_lock:
            logger.info(f"User {user_id} acquired matchmaking_lock")

            # Re-check conditions inside the lock
            if await is_in_queue(user_id):
                logger.info(f"User {user_id} is already in queue (checked inside lock).")
                embed = Embed(
                    title="คุณอยู่ในคิวอยู่แล้ว", # Removed emoji
                    description="ระบบกำลังประมวลผลคำขอของคุณ หรือคุณได้เข้าคิวไปแล้ว",
                    color=0xFF5733
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            if await is_in_game(user_id):
                logger.info(f"User {user_id} is already in game (checked inside lock).")
                embed = Embed(
                    title="เกมของคุณเริ่มแล้ว!", # Removed emoji
                    description="คุณเพิ่งถูกจับคู่! กรุณาตรวจสอบ DM และเล่นเกมที่เริ่มแล้ว",
                    color=0xFFC300
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            await add_to_queue(user_id, str(user), interaction.guild.id, interaction.channel.id)
            logger.info(f"Added to queue: {user_id} (inside lock)")

            opponent = await find_match(user_id)
            if opponent:
                logger.info(f"Found opponent: {opponent} for user: {user_id} (inside lock)")
                # Pass game_mode to create_game
                game_id, _ = await create_game(user_id, opponent, game_mode)
                logger.info(f"Game created: {game_id} for users {user_id} and {opponent} with mode {game_mode} (inside lock)") # Added game_mode to log

                state = await get_game_state(game_id)
                if not state:
                    logger.error(f"Failed to get game state for game_id {game_id} (inside lock)")
                    embed = Embed(
                        title="โหลดสถานะเกมไม่สำเร็จ", # Removed emoji
                        description="โปรดลองใหม่ภายหลัง หรือแจ้งผู้ดูแลระบบ",
                        color=0xE74C3C
                    )
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return

                view = XOGameView(
                    self.bot,
                    game_id=game_id,
                    player_x=state["player_x"],
                    player_o=state["player_o"],
                    board=state["board"],
                    turn=state["turn"],
                    start_time=state["start_time"],
                    game_mode=state["game_mode"] # Added game_mode
                )

                try:
                    user1 = await self.bot.fetch_user(state["player_x"])
                    user2 = await self.bot.fetch_user(state["player_o"])
                    logger.info(f"Sending DM for game {game_id} to {user1} and {user2} (inside lock)")

                    msg1 = await user1.send(content=view.current_turn_display(), view=view)
                    msg2 = await user2.send(content=view.current_turn_display(), view=view)
                    view.messages = [msg1, msg2]

                    embed_dm = Embed(
                        title="เกมเริ่มแล้ว!", # Removed emoji
                        description=f"""ผู้เล่น <@{state['player_x']}> พบกับ <@{state['player_o']}>
เกมได้ถูกส่งไปยัง DM ของคุณทั้งคู่แล้ว กรุณาตรวจสอบ!""",
                        color=0x2ECC71
                    )

                    # Sending to channel does not need to be ephemeral
                    await interaction.channel.send( 
                        content=f"<@{state['player_x']}> <@{state['player_o']}>",
                        embed=embed_dm
                    )

                    await interaction.followup.send(embed=Embed(
                        description="เกมของคุณเริ่มต้นแล้ว! เช็ค DM เพื่อเริ่มเล่น", # Removed emoji
                        color=0x2ECC71
                    ), ephemeral=True)

                except Exception as e:
                    logger.error(f"Failed to send DM for game {game_id}: {e} (inside lock)", exc_info=True)
                    await interaction.followup.send(embed=Embed(
                        title="ไม่สามารถส่ง DM ได้", # Removed emoji
                        description="โปรดตรวจสอบว่าคุณเปิดรับข้อความจากสมาชิกในเซิร์ฟเวอร์",
                        color=0xE74C3C
                    ), ephemeral=True)
            else:
                logger.info(f"No opponent found for {user_id}. User remains in queue. (inside lock)")
                embed = Embed(
                    title="เข้าคิวสำเร็จ", # Removed emoji
                    description="""ระบบกำลังรอผู้เล่นคนอื่นเข้าร่วม
โปรดเปิดรับข้อความ DM จากบอท และรอระบบจับคู่โดยอัตโนมัติ""", # Removed emoji
                    color=0x3498DB
                )
                embed.set_footer(text=f"เข้าคิวเมื่อ: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
                await interaction.followup.send(embed=embed, ephemeral=True)
        logger.info(f"User {user_id} released matchmaking_lock")

    @slash_command(name="leaderboard", description="แสดงอันดับผู้เล่นเกม XO")
    async def leaderboard(self, interaction: Interaction):
        logger.info(f"START: /leaderboard called by {interaction.user} (ID: {interaction.user.id})")
        await interaction.response.defer()

        try:
            leaderboard_entries = await get_leaderboard_data(top_n=10) # This now returns elo

            embed = Embed(title="🏆 XO Game Leaderboard (Top 10 by ELO)", color=nextcord.Color.gold()) # Updated title and color

            if not leaderboard_entries:
                embed.description = "ยังไม่มีข้อมูลใน leaderboard เลย เริ่มเล่นเกมเพื่อสร้างสถิติสิ! 🚀"
            else:
                description_lines = []
                for rank, entry in enumerate(leaderboard_entries, start=1):
                    user_id, username, wins, losses, draws, elo = entry # Unpack elo
                    # Ensure username is not None and is a string
                    username_display = str(username) if username else f"User ID: {user_id}"
                    description_lines.append(
                        f"**{rank}.** <@{user_id}> ({username_display}) - **ELO: {elo}**\n" # Added ELO display
                        f"   ชนะ: {wins} แพ้: {losses} เสมอ: {draws}"
                    )
                embed.description = "\n\n".join(description_lines)
            
            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Error fetching leaderboard data: {e}", exc_info=True)
            error_embed = Embed(
                title="เกิดข้อผิดพลาด",
                description="ไม่สามารถดึงข้อมูล leaderboard ได้ในขณะนี้ โปรดลองอีกครั้งภายหลัง",
                color=0xFF0000 # Red color
            )
            await interaction.followup.send(embed=error_embed)

    @slash_command(name="profile", description="แสดงสถิติเกม XO ของผู้เล่น")
    async def profile(self, interaction: Interaction,
                      user: nextcord.User = SlashOption(
                          name="user",
                          description="ผู้เล่นที่ต้องการดูโปรไฟล์ (ปล่อยว่างเพื่อดูของตัวเอง)",
                          required=False,
                          default=None
                      )):
        logger.info(f"START: /profile called by {interaction.user} (ID: {interaction.user.id}) for user: {user}")
        await interaction.response.defer()

        target_user = user if user else interaction.user

        profile_data = await get_profile_data(target_user.id)

        if profile_data is None:
            embed = Embed(
                title="ไม่มีข้อมูลสถิติ",
                description=f"<@{target_user.id}> ยังไม่มีสถิติการเล่นเกม XO หรือยังไม่ได้เล่นเกมแรก",
                color=nextcord.Color.orange()
            )
        else:
            embed = Embed(
                title=f"📊 โปรไฟล์ XO ของ {target_user.display_name}",
                color=nextcord.Color.blue()
            )
            embed.set_thumbnail(url=target_user.display_avatar.url)
            embed.add_field(name="ELO Rating", value=profile_data['elo'], inline=True)
            embed.add_field(name="Wins", value=profile_data['wins'], inline=True)
            embed.add_field(name="Losses", value=profile_data['losses'], inline=True)
            embed.add_field(name="Draws", value=profile_data['draws'], inline=True)
            
            total_games = profile_data['wins'] + profile_data['losses'] + profile_data['draws']
            embed.add_field(name="Total Games", value=total_games, inline=False)

            if total_games > 0:
                win_rate = (profile_data['wins'] / total_games) * 100
                embed.add_field(name="Win Rate", value=f"{win_rate:.2f}%", inline=False)
            else:
                embed.add_field(name="Win Rate", value="N/A", inline=False)


        await interaction.followup.send(embed=embed)


def setup(bot):
    bot.add_cog(XO(bot))
