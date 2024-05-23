import asyncio
import json
import aiosmtplib
import aioimaplib
import nio


class EmailHandler:
    def __init__(self, smtp_config, imap_config):
        self.smtp_config = smtp_config
        self.imap_config = imap_config

    async def read_emails(self):
        imap_client = aioimaplib.IMAP4_SSL(
            self.imap_config["server"], self.imap_config["port"]
        )
        await imap_client.login(
            self.imap_config["username"], self.imap_config["password"]
        )
        await imap_client.select(self.imap_config["mailbox"])
        status, messages = await imap_client.search()
        messages = messages[0].split()
        email_messages = []

        for num in messages:
            status, msg_data = await imap_client.fetch(num, "(RFC822)")
            email_messages.append(msg_data[0][1])

        await imap_client.logout()
        return email_messages

    async def send_email(self, recipient, subject, content):
        message = f"From: {self.smtp_config['username']}\nTo: {recipient}\nSubject: {subject}\n\n{content}"
        await aiosmtplib.send(
            message,
            hostname=self.smtp_config["server"],
            port=self.smtp_config["port"],
            username=self.smtp_config["username"],
            password=self.smtp_config["password"],
            start_tls=True,
        )


async def send_email_to_matrix():
    config = json.load(open("config.json"))
    matrix_client = nio.AsyncClient(config["homeserver"], config["username"])
    await matrix_client.login(config["password"])

    email_handler = EmailHandler(config["smtp"], config["imap"])
    emails = await email_handler.read_emails()

    for email in emails:
        room_id = config["bridge"]["channel_id"]
        await matrix_client.room_send(
            room_id=room_id,
            message_type="m.room.message",
            content={
                "body": email.decode("utf-8").strip(),
                "msgtype": "m.text",
            },
        )

    await matrix_client.close()


if __name__ == "__main__":
    asyncio.run(send_email_to_matrix())
