"""
Auto-detect which university a PDF belongs to.
Returns the appropriate parser instance.
"""

from .base import BaseUniversityParser
from .sri_dev_suman import SriDevSumanParser
from .hnb_garhwal import HNBGarhwalParser
from .kumaun import KumaunParser
from .lucknow import LucknowParser
from .ccs import CCSParser
from .generic import GenericParser

# Order matters - most specific first
PARSERS: list[type[BaseUniversityParser]] = [
    SriDevSumanParser,
    HNBGarhwalParser,
    KumaunParser,
    LucknowParser,
    CCSParser,
]


def detect_university(text: str) -> BaseUniversityParser:
    for parser_cls in PARSERS:
        if parser_cls.can_parse(text):
            return parser_cls()
    return GenericParser()


def get_university_name(text: str) -> str:
    parser = detect_university(text)
    return parser.name
