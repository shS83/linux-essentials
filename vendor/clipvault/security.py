import math
import re
from collections import Counter

SAFE_PATTERNS = [
    r"^[\w-]+\.(md|txt|py|json|yaml|yml|toml|ini|cfg|csv|log|sh|cpp|h)$",
    r"^[a-z0-9]+(?:-[a-z0-9]+)+-v\d+(?:\.\d+)*$",
]

SECRET_PATTERNS = [
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b",
    r"\bgithub_pat_[A-Za-z0-9_]{20,}\b",
    r"\bglpat-[A-Za-z0-9_-]{20,}\b",
    r"\bAKIA[A-Z0-9]{16}\b",
    r"\bBearer\s+\S+",
    r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b",
    r"\b(?:password|passwd|api_key|secret|token)\s*[:=]\s*\S+",
]


def entropy(text: str) -> float:
    """Laskee Shannonin entropian bitteinä/merkki."""
    counts = Counter(text)
    length = len(text)
    return -sum(
        (count / length) * math.log2(count / length)
        for count in counts.values()
    ) if length else 0.0


def is_secret(text: str) -> bool:
    text = text.strip()
    if not text:
        return False
    for pattern in SECRET_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    if not 8 <= len(text) <= 128:
        return False
    if any(char.isspace() for char in text):
        return False
    classes = [
        any(c.islower() for c in text),
        any(c.isupper() for c in text),
        any(c.isdigit() for c in text),
        any(not c.isalnum() for c in text),
    ]
    if sum(classes) < 3:
        return False
    for pattern in SAFE_PATTERNS:
        if re.fullmatch(pattern, text, re.IGNORECASE):
            return False
    threshold = 2.5 if len(text) < 12 else (3.0 if len(text) < 16 else 3.5)
    return entropy(text) >= threshold
