import os
import logging
from dotenv import load_dotenv
from factories.slack_factory import create_slack_app
from utilities.slack import download_files

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initializes the app
slack_app = create_slack_app()

@slack_app.event("message")
def handle_message_events(body, ack, say):
  ack()

  if "files" in body["event"]:
    files = body["event"]["files"]
    download_files(files, say)

slack_app.start(port=int(os.environ.get("PORT", 3000))) 