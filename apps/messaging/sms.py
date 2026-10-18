"""How many SMS a text takes.

Texts in the GSM 7-bit alphabet (which includes å, ä, ö and é) fit 160
characters in one SMS, or 153 per part when longer. Any other character
(for example an emoji or a curly quote) makes the whole text Unicode: 70,
or 67 per part.
"""

import math

GSM_BASIC = set(
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
)
GSM_EXTENDED = set("^{}\\[~]|€\f")  # two characters each


def segments(text):
    """(number of SMS, characters used, characters per SMS)."""
    if all(c in GSM_BASIC or c in GSM_EXTENDED for c in text):
        length = sum(2 if c in GSM_EXTENDED else 1 for c in text)
        single, part = 160, 153
    else:
        length = len(text.encode("utf-16-le")) // 2
        single, part = 70, 67
    if length == 0:
        return 0, 0, single
    if length <= single:
        return 1, length, single
    return math.ceil(length / part), length, part
