"""
utils/text.py
=============
Canonical text normalization utilities for the news-article scraper toolkit.

Consolidates all normalize_*/clean_*/fix_encoding functions that were
duplicated across the original per-site scraper notebooks.

Public API
----------
    normalize_unicode(text)          – NFC/NFKC + invisible-char cleanup
    normalize_quotes(text)           – smart quotes/apostrophes → ASCII
    normalize_dashes(text)           – em/en dashes → hyphen
    normalize_whitespace(text)       – collapse runs of whitespace
    normalize_punctuation(text)      – spacing around punctuation marks
    fix_mojibake(text)               – repair Windows-1252 mis-decoded UTF-8
    remove_editorial_markup(text)    – strip [BLOCK]/[PULLQUOTE] CMS tags
    clean_text(text)                 – minimal single-line whitespace collapse
    normalize_text(text)             – full pipeline (quotes+dashes+whitespace)
    split_paragraphs(text)           – split body text into clean paragraph list
    is_boilerplate(text, patterns)   – check paragraph against skip-pattern list
"""

import re
import unicodedata

# ---------------------------------------------------------------------------
# Character replacement tables
# ---------------------------------------------------------------------------

# Smart quotes, apostrophes, and typographic variants → plain ASCII
_QUOTE_MAP: dict[str, str] = {
    "\u201C": '"',   # LEFT DOUBLE QUOTATION MARK
    "\u201D": '"',   # RIGHT DOUBLE QUOTATION MARK
    "\u201E": '"',   # DOUBLE LOW-9 QUOTATION MARK
    "\u201F": '"',   # DOUBLE HIGH-REVERSED-9 QUOTATION MARK
    "\u00AB": '"',   # LEFT-POINTING DOUBLE ANGLE QUOTATION MARK
    "\u00BB": '"',   # RIGHT-POINTING DOUBLE ANGLE QUOTATION MARK
    "\u2018": "'",   # LEFT SINGLE QUOTATION MARK
    "\u2019": "'",   # RIGHT SINGLE QUOTATION MARK
    "\u201A": "'",   # SINGLE LOW-9 QUOTATION MARK
    "\u201B": "'",   # SINGLE HIGH-REVERSED-9 QUOTATION MARK
    "\u2032": "'",   # PRIME
    "\u2035": "'",   # REVERSED PRIME
    "\u02BC": "'",   # MODIFIER LETTER APOSTROPHE
    "\u02B9": "'",   # MODIFIER LETTER PRIME
    "\u0060": "'",   # GRAVE ACCENT (backtick used as quote)
}

# Dashes and ellipsis
_DASH_MAP: dict[str, str] = {
    "\u2013": "-",   # EN DASH
    "\u2014": "-",   # EM DASH
    "\u2015": "-",   # HORIZONTAL BAR
    "\u2212": "-",   # MINUS SIGN
    "\u2026": "...", # HORIZONTAL ELLIPSIS
}

# Whitespace variants → regular space (or empty for zero-width)
_SPACE_MAP: dict[str, str] = {
    "\u00A0": " ",   # NO-BREAK SPACE
    "\u2002": " ",   # EN SPACE
    "\u2003": " ",   # EM SPACE
    "\u2004": " ",   # THREE-PER-EM SPACE
    "\u2005": " ",   # FOUR-PER-EM SPACE
    "\u2006": " ",   # SIX-PER-EM SPACE
    "\u2007": " ",   # FIGURE SPACE
    "\u2008": " ",   # PUNCTUATION SPACE
    "\u2009": " ",   # THIN SPACE
    "\u200A": " ",   # HAIR SPACE
    "\u202F": " ",   # NARROW NO-BREAK SPACE
    "\u200B": "",    # ZERO WIDTH SPACE
    "\u200C": "",    # ZERO WIDTH NON-JOINER
    "\u200D": "",    # ZERO WIDTH JOINER
    "\u2060": "",    # WORD JOINER
    "\u2061": "",    # FUNCTION APPLICATION
    "\u2062": "",    # INVISIBLE TIMES
    "\u2063": "",    # INVISIBLE SEPARATOR
    "\uFEFF": "",    # ZERO WIDTH NO-BREAK SPACE (BOM)
    "\u2028": "\n",  # LINE SEPARATOR
    "\u2029": "\n\n", # PARAGRAPH SEPARATOR
}

# Mojibake: UTF-8 smart punctuation mis-decoded as Windows-1252
_MOJIBAKE_MAP: dict[str, str] = {
    "\u00e2\u0080\u0098": "'",   # '
    "\u00e2\u0080\u0099": "'",   # '
    "\u00e2\u0080\u009c": '"',   # "
    "\u00e2\u0080\u009d": '"',   # "
    "\u00e2\u0080\u0093": "-",   # –
    "\u00e2\u0080\u0094": "-",   # —
    "\u00e2\u0080\u00a6": "...", # …
    # Literal byte-string representations sometimes found in scraped HTML
    "â\u0080\u0098": "'",
    "â\u0080\u0099": "'",
    "â\u0080\u009c": '"',
    "â\u0080\u009d": '"',
    "â\u0080\u0093": "-",
    "â\u0080\u0094": "-",
    "â\u0080\u00a6": "...",
    # Short mojibake variants — UTF-8 bytes decoded as Latin-1 (free-beacon pattern)
    "\u00e2\u0080\u0098": "'",
    "\u00e2\u0080\u0099": "'",
    "\u00e2\u0080\u009c": '"',
    "\u00e2\u0080\u009d": '"',
    "\u00e2\u0080\u0093": "-",
    "\u00e2\u0080\u0094": "-",
    "\u00e2\u0080\u00a6": "...",
}

# Editorial CMS markup tags used by American Conservative and similar CMS systems
_EDITORIAL_TAG_RE = re.compile(
    r"\[/?(?:BLOCK|PULLQUOTE|QUOTE|NOTE)\]",
    flags=re.IGNORECASE,
)
_EDITORIAL_ALLCAPS_TAG_RE = re.compile(r"\[[A-Z0-9_\-]+\]")


# ---------------------------------------------------------------------------
# Individual normalization steps
# ---------------------------------------------------------------------------

def normalize_unicode(text: str, form: str = "NFC") -> str:
    """
    Apply Unicode normalization (NFC by default) and strip invisible/
    control characters.

    Use form="NFKC" for compatibility decomposition (recommended for NLP
    pipelines that need ligatures and width variants collapsed).

    Sources: all 10 scrapers used unicodedata.normalize; form varied between
    NFC (AlterNet, American Conservative) and NFKC (Mother Jones, Salon,
    Free Beacon). NFC is the safer default for raw text preservation;
    callers doing NLP downstream should pass form="NFKC".
    """
    if not text:
        return text

    text = unicodedata.normalize(form, text)

    for char, replacement in _SPACE_MAP.items():
        text = text.replace(char, replacement)

    # Strip remaining C0/C1 control characters (except \n and \t)
    text = re.sub(r"[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]", " ", text)
    text = re.sub(r"[\u0080-\u009F]", "", text)

    return text


def normalize_quotes(text: str) -> str:
    """
    Replace typographic/smart quotes and apostrophe variants with plain ASCII.

    Merges quote maps from: AlterNet, American Conservative, American
    Spectator, CounterPunch, Daily Beast, Daily Caller, Fox News, Mother
    Jones, Salon, Free Beacon.
    """
    if not text:
        return text

    for char, replacement in _QUOTE_MAP.items():
        text = text.replace(char, replacement)

    return text


def normalize_dashes(text: str) -> str:
    """
    Replace em dashes, en dashes, and the horizontal ellipsis with their
    plain ASCII equivalents.
    """
    if not text:
        return text

    for char, replacement in _DASH_MAP.items():
        text = text.replace(char, replacement)

    return text


def normalize_whitespace(text: str) -> str:
    """
    Collapse runs of spaces/tabs to a single space, normalize paragraph
    separators to double newlines, and strip leading/trailing whitespace.

    Preserves intentional paragraph breaks (\\n\\n).
    """
    if not text:
        return text

    # Collapse horizontal whitespace (spaces and tabs) within lines
    text = re.sub(r"[ \t]+", " ", text)

    # Collapse trailing whitespace on each line
    text = re.sub(r" +\n", "\n", text)

    # Collapse runs of 3+ newlines to a paragraph break
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def normalize_punctuation(text: str) -> str:
    """
    Fix common punctuation spacing issues:
      - Remove space before sentence-ending punctuation  ( word , → word,)
      - Remove space inside opening brackets/quotes      ( ( word → (word )
      - Remove space inside closing brackets/quotes      ( word ) → word)  )
      - Ensure space after punctuation before a word     (word.Next → word. Next)

    Sources: AlterNet, Fox News (identical implementations).
    """
    if not text:
        return text

    # Space before punctuation
    text = re.sub(r"\s+([.,!?;:])", r"\1", text)

    # Space inside opening delimiters
    text = re.sub(r"([\(\[\{'\"])\s+", r"\1", text)

    # Space inside closing delimiters
    text = re.sub(r"\s+([\)\]\}'\"])", r"\1", text)

    # Missing space after sentence-ending punctuation followed by a word char
    text = re.sub(r"([.!?])(\w)", r"\1 \2", text)

    # Final whitespace collapse (punctuation fixes can create double spaces)
    text = re.sub(r"[ \t]+", " ", text)

    return text.strip()


def fix_mojibake(text: str) -> str:
    """
    Repair text that was decoded as Windows-1252 when it was actually UTF-8,
    producing sequences like â€™ instead of '.

    Sources: Salon (fix_encoding_issues), Free Beacon (normalize_text_for_nlp).
    """
    if not text:
        return text

    for bad, good in _MOJIBAKE_MAP.items():
        text = text.replace(bad, good)

    return text


def remove_editorial_markup(text: str) -> str:
    """
    Strip CMS editorial shortcodes like [BLOCK]...[/BLOCK], [PULLQUOTE],
    [NOTE], and unknown all-caps bracketed tags.  Inner text is preserved.

    Source: American Conservative scraper (remove_editorial_markup).
    """
    if not text:
        return text

    text = _EDITORIAL_TAG_RE.sub("", text)
    text = _EDITORIAL_ALLCAPS_TAG_RE.sub("", text)

    return text


# ---------------------------------------------------------------------------
# Composite pipelines
# ---------------------------------------------------------------------------

def clean_text(text: str) -> str:
    """
    Minimal single-line cleaner: collapse whitespace and strip.

    Equivalent to the clean_text() that was copy-pasted verbatim into
    AlterNet, Fox News, Mother Jones, and Salon.  Use this for short
    strings (headlines, dates) that don't need full normalization.
    """
    if not text:
        return ""

    return re.sub(r"\s+", " ", text).strip()


def normalize_text(text: str, *, nlp_mode: bool = False) -> str:
    """
    Full normalization pipeline suitable for article body text.

    Pipeline (in order):
        1. fix_mojibake        – repair encoding artifacts
        2. normalize_unicode   – NFC (NFKC when nlp_mode=True)
        3. normalize_quotes    – smart → ASCII quotes
        4. normalize_dashes    – em/en dash → hyphen
        5. normalize_whitespace – collapse spaces and normalize newlines

    Parameters
    ----------
    text : str
        Raw text extracted from HTML.
    nlp_mode : bool
        When True, uses NFKC normalization (collapses compatibility
        variants) and also runs normalize_punctuation.  Recommended for
        text going into NLP pipelines.  Default is False for maximum
        fidelity.

    Sources: merges normalize_text_for_nlp (AlterNet, American Conservative,
    Free Beacon), normalize_unicode (American Spectator, Mother Jones, Salon),
    and normalize_text (CounterPunch, Daily Beast, Daily Caller, Fox News).
    """
    if not text:
        return ""

    text = fix_mojibake(text)
    text = normalize_unicode(text, form="NFKC" if nlp_mode else "NFC")
    text = normalize_quotes(text)
    text = normalize_dashes(text)

    if nlp_mode:
        text = normalize_punctuation(text)

    text = normalize_whitespace(text)

    return text


# ---------------------------------------------------------------------------
# Paragraph utilities
# ---------------------------------------------------------------------------

def split_paragraphs(text: str) -> list[str]:
    """
    Split a body-text string into a list of non-empty paragraph strings.

    Paragraphs are separated by one or more blank lines.  Each paragraph
    has its internal whitespace collapsed to a single line.

    Source: split_into_chunks() in CounterPunch scraper.
    """
    paragraphs = []

    for block in text.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        # Collapse internal line breaks within the block
        block = " ".join(line.strip() for line in block.splitlines() if line.strip())
        if block:
            paragraphs.append(block)

    return paragraphs


def is_boilerplate(text: str, patterns: list[str]) -> bool:
    """
    Return True if the paragraph starts with or contains any of the given
    boilerplate patterns (case-insensitive).

    Parameters
    ----------
    text : str
        Paragraph text to test.
    patterns : list[str]
        Strings to check.  A pattern is matched if text.lower() starts
        with it (for phrases like "this article first appeared on") or
        contains it (for phrases like "sign up for our free").

    Usage
    -----
        BOILERPLATE = [
            "this piece first appeared on",
            "sign up for our free",
            "subscribe today to support",
        ]
        if is_boilerplate(paragraph, BOILERPLATE):
            continue

    Sources: is_boilerplate_disclaimer (CounterPunch),
             should_skip_paragraph (Mother Jones, Salon).
    """
    if not text or not patterns:
        return False

    lowered = text.lower().strip()

    for pattern in patterns:
        p = pattern.lower()
        if lowered.startswith(p) or p in lowered:
            return True

    return False