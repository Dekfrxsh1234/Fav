import nextcord
from nextcord.ext import commands
from nextcord.ext.commands import (
    CommandNotFound, MissingRequiredArgument, BadArgument, CheckFailure,
    CommandOnCooldown, MissingPermissions
)
import logging
import asyncio
import os
from db.database import setup_db
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", filename="bot.log", filemode="a")

# Intents
intents = nextcord.Intents.default()
intents.guilds = True
intents.members = True
intents.messages = True
intents.message_content = True

# Bot setup
bot = commands.AutoShardedBot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} | Shards: {bot.shard_count}")
    await setup_db()

    # รายการ Cog ที่ต้องโหลด
    extensions = ["cogs.xo", "cogs.status", "cogs.timeout_checker"]

    for ext in extensions:
        try:
            bot.load_extension(ext)
            print(f"✅ Loaded extension: {ext}")
        except Exception as e:
            print(f"❌ Failed to load extension {ext}: {e}")

    print("🔄 Attempting to sync slash commands...")
    try:
        await bot.sync_all_application_commands()
        print("✅ Slash commands synced successfully")
    except Exception as e:
        print(f"❌ Failed to sync slash commands: {e}")

@bot.event
async def on_command_error(ctx, error):
    log_message = f"Command Error: {error} | Command: {ctx.command.qualified_name if ctx.command else 'N/A'} | User: {ctx.author.id} | Guild: {ctx.guild.id if ctx.guild else 'DM'}"

    if isinstance(error, CommandNotFound):
        logging.warning(f"CommandNotFound: {ctx.message.content} by {ctx.author.id}")
        # Optionally, send a subtle message or do nothing
        # await ctx.send("ไม่พบคำสั่งที่คุณใช้ ลองตรวจสอบอีกครั้งนะคะ", delete_after=10)
        return
    elif isinstance(error, MissingRequiredArgument):
        logging.info(f"MissingRequiredArgument: {error.param.name} for {ctx.command.qualified_name} by {ctx.author.id}")
        await ctx.send(f"⚠️ คุณลืมใส่ `{error.param.name}` ซึ่งจำเป็นสำหรับคำสั่งนี้นะคะ")
    elif isinstance(error, BadArgument):
        logging.info(f"BadArgument: {error} for {ctx.command.qualified_name} by {ctx.author.id}")
        await ctx.send("⚠️ คุณใส่ argument ไม่ถูกต้อง โปรดตรวจสอบประเภทและค่าที่จำเป็นอีกครั้งค่ะ")
    elif isinstance(error, CommandOnCooldown):
        logging.info(f"CommandOnCooldown: {ctx.command.qualified_name} by {ctx.author.id}. Cooldown: {error.retry_after:.2f}s")
        await ctx.send(f"⏳ คำสั่งนี้กำลังอยู่ในช่วง cooldown นะคะ กรุณารออีก {error.retry_after:.2f} วินาทีก่อนลองอีกครั้ง")
    elif isinstance(error, MissingPermissions):
        logging.warning(f"MissingPermissions: {error.missing_permissions} for {ctx.command.qualified_name} by {ctx.author.id}")
        await ctx.send("🚫 ขออภัยค่ะ คุณไม่มีสิทธิ์เพียงพอที่จะใช้คำสั่งนี้")
    elif isinstance(error, CheckFailure):
        logging.warning(f"CheckFailure: {error} for {ctx.command.qualified_name} by {ctx.author.id}")
        await ctx.send("🚫 ขออภัยค่ะ คุณไม่ผ่านเงื่อนไขการตรวจสอบเพื่อใช้คำสั่งนี้")
    else:
        logging.exception(log_message)
        await ctx.send("โอ๊ะ! เกิดข้อผิดพลาดบางอย่างที่ไม่คาดคิด โปรดลองอีกครั้งหรือติดต่อผู้ดูแลระบบนะคะ 🛠️")

if __name__ == "__main__":
    bot.run(TOKEN)
