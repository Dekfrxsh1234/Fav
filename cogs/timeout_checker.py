
from nextcord.ext import commands, tasks
from datetime import datetime, timedelta
from db.database import get_all_active_games, get_game_state
from game.views import XOGameView

class TimeoutChecker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_expired_games.start()

    def cog_unload(self):
        self.check_expired_games.cancel()

    @tasks.loop(seconds=30)
    async def check_expired_games(self):
        now = datetime.utcnow()
        active_games = await get_all_active_games()

        for game_id, start_time_str in active_games:
            try:
                start_time = datetime.fromisoformat(start_time_str)
                if now - start_time > timedelta(minutes=5):
                    state = await get_game_state(game_id)
                    if state and state["status"] == "active":
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
                            msg1 = await user1.send(content="⏰ หมดเวลา! เกมนี้ถือว่าเสมอ", view=view)
                            msg2 = await user2.send(content="⏰ หมดเวลา! เกมนี้ถือว่าเสมอ", view=view)
                            view.messages = [msg1, msg2]
                            await view.expire_due_to_timeout()
                        except Exception as e:
                            print(f"❌ ไม่สามารถส่ง DM เพื่อหมดเวลาเกม {game_id}: {e}")
            except Exception as e:
                print(f"⚠️ ข้อผิดพลาดใน game {game_id}: {e}")

def setup(bot):
    bot.add_cog(TimeoutChecker(bot))
