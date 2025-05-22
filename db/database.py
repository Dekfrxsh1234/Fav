
import aiosqlite
import datetime
import os
import math

DB_PATH = os.getenv("DB_PATH", "data/games.db")

# ✅ สร้างตารางหากยังไม่มี
async def setup_db():
    db_dir = os.path.dirname(DB_PATH)
    if db_dir: # This will be "data" for the default, or custom if DB_PATH is "custom/path/db.sqlite"
        os.makedirs(db_dir, exist_ok=True)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS matchmaking_queue (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            guild_id INTEGER,
            channel_id INTEGER,
            timestamp TEXT
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS active_games (
            game_id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_x_id INTEGER,
            player_o_id INTEGER,
            turn TEXT,
            board_state TEXT,
            status TEXT,
            start_time TEXT,
            game_mode TEXT
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS leaderboard (
            user_id INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            draws INTEGER DEFAULT 0,
            elo INTEGER DEFAULT 1000,
            last_game_timestamp TEXT
        )
        """)
        await db.commit()

# ➕ เพิ่มผู้เล่นเข้าสู่คิว
async def add_to_queue(user_id, username, guild_id, channel_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO matchmaking_queue (user_id, username, guild_id, channel_id, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, username, guild_id, channel_id, datetime.datetime.utcnow().isoformat()))
        await db.commit()

# 🔍 ตรวจว่าผู้เล่นอยู่ในคิวไหม
async def is_in_queue(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT 1 FROM matchmaking_queue WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone() is not None

# 🔍 ตรวจว่าผู้เล่นมีเกมอยู่ไหม
async def is_in_game(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT 1 FROM active_games
            WHERE (player_x_id = ? OR player_o_id = ?) AND status = 'active'
        """, (user_id, user_id)) as cursor:
            return await cursor.fetchone() is not None

# 🔍 ค้นหาคู่ที่ไม่ใช่ user นี้
async def find_match(current_user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT user_id, username FROM matchmaking_queue
            WHERE user_id != ?
            ORDER BY timestamp ASC
            LIMIT 1
        """, (current_user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                await db.execute("DELETE FROM matchmaking_queue WHERE user_id IN (?, ?)", (row[0], current_user_id))
                await db.commit()
                return row[0]
    return None

# 🎮 สร้างเกมใหม่
async def create_game(player1_id, player2_id, game_mode): # Added game_mode
    import random
    if random.choice([True, False]):
        player_x, player_o = player1_id, player2_id
    else:
        player_x, player_o = player2_id, player1_id

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO active_games (player_x_id, player_o_id, turn, board_state, status, start_time, game_mode)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (player_x, player_o, 'X', '---------', 'active', datetime.datetime.utcnow().isoformat(), game_mode)) # Added game_mode
        await db.commit()

        cursor = await db.execute("SELECT last_insert_rowid()")
        row = await cursor.fetchone()
        return row[0], (player1_id == player_x)

# ✏️ อัปเดตกระดาน
async def update_board(game_id, new_board, next_turn):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE active_games
            SET board_state = ?, turn = ?
            WHERE game_id = ? AND status = 'active'
        """, (new_board, next_turn, game_id))
        await db.commit()

# 📥 ดึงสถานะเกม
async def get_game_state(game_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT player_x_id, player_o_id, board_state, turn, status, start_time, game_mode
            FROM active_games
            WHERE game_id = ?
        """, (game_id,)) as cursor: # Added game_mode to SELECT
            row = await cursor.fetchone()
            if row:
                return {
                    "player_x": row[0],
                    "player_o": row[1],
                    "board": row[2],
                    "turn": row[3],
                    "status": row[4],
                    "start_time": row[5],
                    "game_mode": row[6] # Added game_mode to return dict
                }
    return None

# 🔒 จบเกม
async def end_game(game_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE active_games
            SET status = 'finished'
            WHERE game_id = ?
        """, (game_id,))
        await db.commit()

# 📊 นับจำนวนเกมที่กำลังดำเนินอยู่
async def count_active_games():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM active_games WHERE status = 'active'") as cursor:
            row = await cursor.fetchone()
            return row[0]

# 👥 นับจำนวนผู้เล่นที่กำลังเล่นอยู่
async def count_active_players():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT COUNT(DISTINCT player_id)
            FROM (
                SELECT player_x_id AS player_id FROM active_games WHERE status = 'active'
                UNION
                SELECT player_o_id AS player_id FROM active_games WHERE status = 'active'
            )
        """) as cursor:
            row = await cursor.fetchone()
            return row[0]

# ⏰ ดึงเกมทั้งหมดที่ active
async def get_all_active_games():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT game_id, start_time FROM active_games
            WHERE status = 'active'
        """) as cursor:
            return await cursor.fetchall()

# 🏆 อัปเดตกระดานผู้นำ
async def update_leaderboard(user_id, username, result):
    async with aiosqlite.connect(DB_PATH) as db:
        # Attempt to insert a new player, or ignore if they already exist
        await db.execute("""
            INSERT OR IGNORE INTO leaderboard (user_id, username, wins, losses, draws, last_game_timestamp)
            VALUES (?, ?, 0, 0, 0, ?)
        """, (user_id, username, datetime.datetime.utcnow().isoformat()))

        # Update scores based on the result
        if result == 'win':
            await db.execute("""
                UPDATE leaderboard
                SET wins = wins + 1, username = ?, last_game_timestamp = ?
                WHERE user_id = ?
            """, (username, datetime.datetime.utcnow().isoformat(), user_id))
        elif result == 'loss':
            await db.execute("""
                UPDATE leaderboard
                SET losses = losses + 1, username = ?, last_game_timestamp = ?
                WHERE user_id = ?
            """, (username, datetime.datetime.utcnow().isoformat(), user_id))
        elif result == 'draw':
            await db.execute("""
                UPDATE leaderboard
                SET draws = draws + 1, username = ?, last_game_timestamp = ?
                WHERE user_id = ?
            """, (username, datetime.datetime.utcnow().isoformat(), user_id))
        await db.commit()

# 🏅 ดึงข้อมูลกระดานผู้นำ
async def get_leaderboard_data(top_n=10): # Removed sort_by parameter
    async with aiosqlite.connect(DB_PATH) as db:
        query = """
            SELECT user_id, username, wins, losses, draws, elo
            FROM leaderboard
            ORDER BY elo DESC
            LIMIT ?
        """ # Updated query to sort by elo and select elo
        async with db.execute(query, (top_n,)) as cursor:
            return await cursor.fetchall()

# 👤 ดึงข้อมูลโปรไฟล์ผู้เล่น
async def get_profile_data(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT username, wins, losses, draws, elo
            FROM leaderboard
            WHERE user_id = ?
        """, (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "username": row[0],
                    "wins": row[1],
                    "losses": row[2],
                    "draws": row[3],
                    "elo": row[4]
                }
            else:
                return None # User not found in leaderboard

# 🎯 ดึง ELO ของผู้เล่น
async def get_player_elo(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT elo FROM leaderboard WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return row[0]
            else:
                # Player not found, return default ELO.
                # This assumes update_leaderboard has been called at least once for the user,
                # or they are new and will get the default ELO set in the table schema.
                # If a user somehow has no entry, they start at 1000.
                return 1000

# 🔄 อัปเดต ELO ของผู้เล่น
async def update_player_elo(user_id, new_elo):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE leaderboard
            SET elo = ?
            WHERE user_id = ?
        """, (new_elo, user_id))
        await db.commit()

# 🧮 คำนวณและอัปเดต ELO หลังจบเกม
async def calculate_and_update_elo(player1_id, player2_id, game_result):
    """
    Calculates and updates ELO ratings for two players based on a game result.

    Args:
        player1_id: The user ID of the first player.
        player2_id: The user ID of the second player.
        game_result: Can be player1_id (if player1 wins), player2_id (if player2 wins),
                     or the string 'draw'.
    """
    elo1 = await get_player_elo(player1_id)
    elo2 = await get_player_elo(player2_id)

    K = 32  # K-factor

    if game_result == player1_id:
        s1, s2 = 1, 0  # Player 1 wins
    elif game_result == player2_id:
        s1, s2 = 0, 1  # Player 2 wins
    elif game_result == 'draw':
        s1, s2 = 0.5, 0.5  # Draw
    else:
        # Should not happen with current usage in command_handler
        raise ValueError("Invalid game_result. Must be player1_id, player2_id, or 'draw'.")

    # Expected scores
    e1 = 1 / (1 + math.pow(10, (elo2 - elo1) / 400))
    e2 = 1 / (1 + math.pow(10, (elo1 - elo2) / 400))

    # New ELO ratings
    new_elo1 = round(elo1 + K * (s1 - e1))
    new_elo2 = round(elo2 + K * (s2 - e2))

    await update_player_elo(player1_id, new_elo1)
    await update_player_elo(player2_id, new_elo2)
