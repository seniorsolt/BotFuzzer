import asyncio
import os
from pyrogram import Client, filters


api_id = os.getenv('TELEGRAM_API_ID')
api_hash = os.getenv('TELEGRAM_API_HASH')

target_bot_username = "photo_aihero_bot"


async def main():

    app = Client("my_bot", api_id=api_id, api_hash=api_hash)
    response_event = asyncio.Event()

    @app.on_message(filters.chat(target_bot_username))
    async def handle_response(client, response_message):
        print(response_message)
        response_event.set()

    async with app:
        await app.send_message(target_bot_username, "/start")
        await response_event.wait()


if __name__ == "__main__":
    asyncio.run(main())
