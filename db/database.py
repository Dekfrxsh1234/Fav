
import aiosqlite
import datetime
import os

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
            start_time TEXT
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
async def create_game(player1_id, player2_id):
    import random
    if random.choice([True, False]):
        player_x, player_o = player1_id, player2_id
    else:
        player_x, player_o = player2_id, player1_id

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO active_games (player_x_id, player_o_id, turn, board_state, status, start_time)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (player_x, player_o, 'X', '---------', 'active', datetime.datetime.utcnow().isoformat()))
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
            SELECT player_x_id, player_o_id, board_state, turn, status, start_time
            FROM active_games
            WHERE game_id = ?
        """, (game_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "player_x": row[0],
                    "player_o": row[1],
                    "board": row[2],
                    "turn": row[3],
                    "status": row[4],
                    "start_time": row[5]
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
