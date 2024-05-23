import asyncio
import json
import nio
import aiofiles


class FileHandler:
    def __init__(self, file_path):
        self.file_path = file_path

    async def read_messages(self):
        async with aiofiles.open(self.file_path, "r") as f:
            messages = await f.readlines()
        return messages


async def send_file_messages():
    config = json.load(open("config.json"))
    matrix_client = nio.AsyncClient(config["homeserver"], config["username"])
    await matrix_client.login(config["password"])

    file_handler = FileHandler(config["file_path"])
    messages = await file_handler.read_messages()

    for message in messages:
        # FIXME
        if "bridge" in config:
            room_id = (config["bridge"]["address"],)
        else:
            room_id = "!CnVctzwDJpyOXuMSLl:jbara.xyz"

        await matrix_client.room_send(
            room_id=room_id,
            message_type="m.room.message",
            content={
                "body": message.strip(),
                "msgtype": "m.text",
            },
        )

    await matrix_client.close()


if __name__ == "__main__":
    asyncio.run(send_file_messages())
