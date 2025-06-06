from nextcord.ui import View, Button
from nextcord import ButtonStyle, Interaction
from db.database import update_board, end_game
from game.game_state import check_winner
import asyncio
from datetime import datetime, timedelta
from config import GAME_TIMEOUT_MINUTES


class XOGameView(View):
    def __init__(
        self,
        game_id: int,
        player_x: int,
        player_o: int,
        board: str,
        turn: str,
        start_time: str,
    ):
        super().__init__(timeout=None)
        self.game_id = game_id
        self.player_x = player_x
        self.player_o = player_o
        self.board = list(board)
        self.turn = turn
        self.start_time = datetime.fromisoformat(start_time)
        self.lock = asyncio.Lock()
        self.messages = []
        self.build_buttons()

    def build_buttons(self):
        self.clear_items()
        for idx in range(9):
            label = self.board[idx] if self.board[idx] != "-" else "⬜"
            style = (
                ButtonStyle.green
                if self.board[idx] == "X"
                else (ButtonStyle.red if self.board[idx] == "O" else ButtonStyle.grey)
            )
            self.add_item(XOButton(idx, label, style))

    def get_time_left(self):
        elapsed = datetime.utcnow() - self.start_time
        remaining = max(
            timedelta(minutes=GAME_TIMEOUT_MINUTES) - elapsed, timedelta(seconds=0)
        )
        minutes, seconds = divmod(int(remaining.total_seconds()), 60)
        return f"{minutes} นาที {seconds} วินาที"

    def current_turn_display(self):
        turn_user = f"<@{self.player_x}>" if self.turn == "X" else f"<@{self.player_o}>"
        return f"""🎯 ตาของ {turn_user}
⏳ เวลาที่เหลือ: {self.get_time_left()}"""

    async def update_all_messages(self):
        for msg in self.messages:
            await msg.edit(content=self.current_turn_display(), view=self)

    async def end_game_display(self, winner):
        if winner == "X":
            result_msg = f"""🎉 <@{self.player_x}> ชนะ!
😢 <@{self.player_o}> แพ้"""
        elif winner == "O":
            result_msg = f"""🎉 <@{self.player_o}> ชนะ!
😢 <@{self.player_x}> แพ้"""
        else:
            result_msg = "🤝 เกมเสมอ!"

        for item in self.children:
            item.disabled = True

        await end_game(self.game_id)

        for msg in self.messages:
            await msg.edit(content=result_msg, view=self)

        self.stop()

    async def expire_due_to_timeout(self):
        for item in self.children:
            item.disabled = True
        await end_game(self.game_id)
        for msg in self.messages:
            await msg.edit(content="⏰ หมดเวลาแล้ว! เกมนี้ถือว่าเสมอ", view=self)
        self.stop()

    async def handle_move(self, interaction: Interaction, index: int):
        async with self.lock:
            current_player = interaction.user.id
            if (self.turn == "X" and current_player != self.player_x) or (
                self.turn == "O" and current_player != self.player_o
            ):
                await interaction.response.send_message(
                    "⛔ ไม่ใช่ตาของคุณ!", ephemeral=True
                )
                return

            if self.board[index] != "-":
                await interaction.response.send_message(
                    "❗ ช่องนี้ถูกเลือกไปแล้ว!", ephemeral=True
                )
                return

            self.board[index] = self.turn
            winner = check_winner("".join(self.board))

            if winner:
                await interaction.response.defer()
                await self.end_game_display(winner)
                return

            self.turn = "O" if self.turn == "X" else "X"
            await update_board(self.game_id, "".join(self.board), self.turn)
            self.build_buttons()
            await interaction.response.edit_message(view=self)
            await self.update_all_messages()


class XOButton(Button):
    def __init__(self, index: int, label: str, style: ButtonStyle):
        super().__init__(label=label, style=style, row=index // 3)
        self.index = index

    async def callback(self, interaction: Interaction):
        view: XOGameView = self.view
        await view.handle_move(interaction, self.index)
