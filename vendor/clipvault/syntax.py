import re
from pygments import highlight
from pygments.formatters import Terminal256Formatter
from pygments.lexers import guess_lexer, get_lexer_by_name
from pygments.util import ClassNotFound


def sanitize_terminal(text: str) -> str:
    """Muuntaa terminaalin ohjausmerkit näkyväksi tekstiksi."""
    result = []
    for char in text:
        code = ord(char)
        if char in ("\n", "\t"):
            result.append(char)
        elif char.isprintable():
            result.append(char)
        elif code <= 0xFF:
            result.append(f"\\x{code:02x}")
        elif code <= 0xFFFF:
            result.append(f"\\u{code:04x}")
        else:
            result.append(f"\\U{code:08x}")
    return "".join(result)


def detect_syntax(content: str):
    shebang = re.match(
        r"^#!\s*(?:/\S*/)?(?:env\s+(?:-S\s+)?(?:\S+\s+)*?)?"
        r"(python(?:\d+(?:\.\d+)?)?|bash)(?:\s|$)",
        content,
    )
    if shebang:
        interpreter = shebang.group(1)
        if interpreter.startswith("python"):
            return get_lexer_by_name("python")
        if interpreter == "bash":
            return get_lexer_by_name("bash")
    if re.search(r"(?m)^\s*(?:async\s+def|def|class)\s+\w+", content):
        return get_lexer_by_name("python")
    if re.search(r"(?m)^\s*(?:function\s+)?[a-zA-Z_]\w*\s*\(\)\s*\{", content):
        return get_lexer_by_name("bash")
    try:
        lexer = guess_lexer(content)
        if lexer.name.lower() == "scdoc":
            return get_lexer_by_name("text")
        return lexer
    except ClassNotFound:
        return get_lexer_by_name("text")


def colorize(content: str, theme: str="material") -> str:
    safe_content = sanitize_terminal(content)
    lexer = detect_syntax(safe_content)
    formatter = Terminal256Formatter(style=theme)
    return highlight(safe_content, lexer, formatter)
