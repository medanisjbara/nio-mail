import asyncio
import json
import logging
import os
import sys

import aiofiles
import aiofiles.os
import nio


def config_gen(config_file):
    config_dict = {
        "homeserver": "https://matrix.org",
        "username": "@mymailbot:matrix.org",
        "password": "mypass+*!word",
        "file_path": "bridge_log.txt",
        "bridge": {
            "address": "room_id",
        },
    }

    if not os.path.exists(config_file):
        with open(config_file, "w") as f:
            json.dump(config_dict, f, indent=4)
            print(f"Example configuration dumped to {config_file}")
            sys.exit()

    with open(config_file, "r") as f:
        config = json.loads(f.read())

    return config


config = config_gen("config.json")


class FileHandler:
    def __init__(self, file_path):
        self.file_path = file_path

    async def write_message(self, message):
        async with aiofiles.open(self.file_path, "a") as f:
            await f.write(message + "\n")

    async def read_messages(self):
        async with aiofiles.open(self.file_path, "r") as f:
            messages = await f.readlines()
        return messages


class MatrixClient(nio.AsyncClient):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.logger = logging.getLogger("matrix_logger")

        self.listen = False
        self.uploaded_emotes = {}
        self.ready = asyncio.Event()
        self.loop = asyncio.get_event_loop()

        self.file_handler = FileHandler(config["file_path"])
        self.add_callbacks()

    def add_callbacks(self):
        callbacks = Callbacks(self)

        self.add_event_callback(
            callbacks.message_callback,
            (nio.RoomMessageText, nio.RoomMessageMedia, nio.RoomMessageEmote),
        )

        self.add_event_callback(callbacks.redaction_callback, nio.RedactionEvent)

        self.add_ephemeral_callback(callbacks.typing_callback, nio.EphemeralEvent)

    async def message_send(self, message, room_id):
        content = {
            "body": message,
            "msgtype": "m.text",
        }

        message = await self.room_send(
            room_id=room_id, message_type="m.room.message", content=content
        )

        return message.event_id

    async def message_redact(self, event_id, room_id):
        await self.room_redact(room_id=room_id, event_id=event_id)


class Callbacks:
    def __init__(self, matrix_client):
        self.matrix_client = matrix_client

    async def message_callback(self, room, event):
        message = event.body

        if not message:
            return

        await self.matrix_client.file_handler.write_message(
            f"[{room.user_name(event.sender)}]: {message}"
        )

    async def redaction_callback(self, room, event):
        pass

    async def typing_callback(self, room, event):
        pass


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s:%(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler("bridge.log"),
            logging.StreamHandler(),
        ],
    )

    retry = 2

    matrix_client = MatrixClient(config["homeserver"], config["username"])

    while True:
        resp = await matrix_client.login(config["password"])

        if type(resp) == nio.LoginError:
            matrix_client.logger.error(f"Failed to login: {resp}")
            return False

        # Login successful.
        matrix_client.logger.info(resp)

        try:
            await matrix_client.sync(full_state=True)
        except Exception:
            matrix_client.logger.exception("Initial sync failed!")
            return False

        try:
            matrix_client.ready.set()
            matrix_client.listen = True

            matrix_client.logger.info("Clients ready!")

            await matrix_client.sync_forever(timeout=30000, full_state=True)
        except Exception:
            matrix_client.logger.exception(
                f"Unknown exception occurred, retrying in {retry} seconds..."
            )

            # Clear "ready" status.
            matrix_client.ready.clear()

            await matrix_client.close()
            await asyncio.sleep(retry)

            matrix_client.listen = False
        finally:
            if matrix_client.listen:
                await matrix_client.close()
                return False


if __name__ == "__main__":
    asyncio.run(main())
