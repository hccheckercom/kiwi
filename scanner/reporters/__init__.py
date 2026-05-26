"""Reporter registry."""

from .text import TextReporter
from .json import JsonReporter

REPORTERS = {
    "text": TextReporter(),
    "json": JsonReporter(),
}


def get_reporter(name: str):
    return REPORTERS.get(name, REPORTERS["text"])
