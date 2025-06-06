import nextcord
from nextcord.ext import commands
import logging
import os
from db.database import setup_db
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filename="bot.log",
    filemode="a",
)

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

    try:
        await bot.sync_all_application_commands()
        print("🔃 Slash commands synced")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")


@bot.event
async def on_command_error(ctx, error):
    await ctx.send(f"❗ เกิดข้อผิดพลาด: {error}")
    logging.exception("Command Error: %s", str(error))


if __name__ == "__main__":
    bot.run(TOKEN)
