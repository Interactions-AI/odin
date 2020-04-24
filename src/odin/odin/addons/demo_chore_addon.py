"""A demo chore that sends a message to slack, used to test/demonstrate chore plugins."""

import requests
from odin.chores import register_chore


@register_chore('demo-chore')
def slack_webhook(webhook: str) -> None:
    """Send a message on slack.

    :param webhook: The url to send the message to.
    """
    requests.post(webhook, json={"text": "This is a demo slack message sent with a chore addon"})
