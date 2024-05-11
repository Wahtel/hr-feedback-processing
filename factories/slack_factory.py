import os
from dotenv import load_dotenv
from slack_bolt import App

load_dotenv()

def create_slack_app():
  slack_app = App(
      token=os.environ.get("SLACK_BOT_TOKEN"),
      signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
  )
  return slack_app

