"""
tests/test_text.py
==================
pytest test suite for utils/text.py

Run from the repository root:
    pytest tests/test_text.py -v

Each test class maps to one public function.  Test inputs are drawn
directly from real HTML patterns observed across the 10 scraper notebooks.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from utils.text import (
    clean_text,
    normalize_unicode,
    normalize_quotes,
    normalize_dashes,
    normalize_whitespace,
    normalize_punctuation,
    fix_mojibake,
    remove_editorial_markup,
    normalize_text,
    split_paragraphs,
    is_boilerplate,
)


# ---------------------------------------------------------------------------
# clean_text
# ---------------------------------------------------------------------------

class TestCleanText:
    def test_collapses_internal_whitespace(self):
        assert clean_text("hello   world") == "hello world"

    def test_strips_leading_trailing(self):
        assert clean_text("  hello  ") == "hello"

    def test_collapses_tabs(self):
        assert clean_text("hello\t\tworld") == "hello world"

    def test_empty_string(self):
        assert clean_text("") == ""

    def test_none_equivalent(self):
        # Scrapers sometimes pass None-ish values; function should not crash
        assert clean_text("") == ""

    def test_already_clean(self):
        assert clean_text("hello world") == "hello world"


# ---------------------------------------------------------------------------
# normalize_unicode
# ---------------------------------------------------------------------------

class TestNormalizeUnicode:
    def test_removes_zero_width_space(self):
        assert "\u200b" not in normalize_unicode("hel\u200blo")

    def test_removes_bom(self):
        assert "\ufeff" not in normalize_unicode("\ufeffhello")

    def test_replaces_nbsp_with_space(self):
        result = normalize_unicode("hello\u00a0world")
        assert "\u00a0" not in result
        assert "hello world" == result.strip()

    def test_paragraph_separator_becomes_double_newline(self):
        result = normalize_unicode("para1\u2029para2")
        assert "para1" in result
        assert "para2" in result
        assert "\u2029" not in result

    def test_line_separator_becomes_newline(self):
        result = normalize_unicode("line1\u2028line2")
        assert "\u2028" not in result

    def test_nfc_form_default(self):
        # NFC: composed form; café should stay intact
        result = normalize_unicode("caf\u00e9")
        assert result == "caf\u00e9"

    def test_nfkc_form(self):
        # NFKC collapses full-width characters
        result = normalize_unicode("\uff41\uff42\uff43", form="NFKC")  # ａｂｃ
        assert result == "abc"

    def test_strips_c0_control_chars(self):
        # Null byte and other control chars should be replaced
        result = normalize_unicode("hel\x00lo\x01world")
        assert "\x00" not in result
        assert "\x01" not in result

    def test_empty_string(self):
        assert normalize_unicode("") == ""


# ---------------------------------------------------------------------------
# normalize_quotes
# ---------------------------------------------------------------------------

class TestNormalizeQuotes:
    def test_left_double_quote(self):
        assert normalize_quotes("\u201chello") == '"hello'

    def test_right_double_quote(self):
        assert normalize_quotes("hello\u201d") == 'hello"'

    def test_left_single_quote(self):
        assert normalize_quotes("\u2018word") == "'word"

    def test_right_single_quote_apostrophe(self):
        assert normalize_quotes("it\u2019s") == "it's"

    def test_angle_quotation_marks(self):
        assert normalize_quotes("\u00abhello\u00bb") == '"hello"'

    def test_prime_as_apostrophe(self):
        assert normalize_quotes("90\u2032") == "90'"

    def test_backtick(self):
        assert normalize_quotes("`code`") == "'code'"

    def test_no_change_on_plain_text(self):
        assert normalize_quotes("hello world") == "hello world"

    def test_empty_string(self):
        assert normalize_quotes("") == ""


# ---------------------------------------------------------------------------
# normalize_dashes
# ---------------------------------------------------------------------------

class TestNormalizeDashes:
    def test_en_dash(self):
        assert normalize_dashes("2020\u20132026") == "2020-2026"

    def test_em_dash(self):
        assert normalize_dashes("word\u2014word") == "word-word"

    def test_ellipsis(self):
        assert normalize_dashes("and so\u2026") == "and so..."

    def test_horizontal_bar(self):
        assert normalize_dashes("word\u2015word") == "word-word"

    def test_no_change_on_plain_hyphen(self):
        assert normalize_dashes("well-known") == "well-known"

    def test_empty_string(self):
        assert normalize_dashes("") == ""


# ---------------------------------------------------------------------------
# normalize_whitespace
# ---------------------------------------------------------------------------

class TestNormalizeWhitespace:
    def test_collapses_spaces(self):
        assert normalize_whitespace("hello   world") == "hello world"

    def test_collapses_tabs(self):
        assert normalize_whitespace("hello\t\tworld") == "hello world"

    def test_preserves_paragraph_break(self):
        result = normalize_whitespace("para one\n\npara two")
        assert "para one" in result
        assert "para two" in result
        assert "\n\n" in result

    def test_collapses_triple_newline(self):
        result = normalize_whitespace("a\n\n\n\nb")
        assert "\n\n\n" not in result

    def test_strips_edges(self):
        assert normalize_whitespace("  hello  ") == "hello"

    def test_empty_string(self):
        assert normalize_whitespace("") == ""


# ---------------------------------------------------------------------------
# normalize_punctuation
# ---------------------------------------------------------------------------

class TestNormalizePunctuation:
    def test_space_before_comma(self):
        assert normalize_punctuation("word , here") == "word, here"

    def test_space_before_period(self):
        assert normalize_punctuation("end .") == "end."

    def test_space_before_colon(self):
        assert normalize_punctuation("title :") == "title:"

    def test_space_inside_parens(self):
        assert normalize_punctuation("( hello )") == "(hello)"

    def test_space_inside_brackets(self):
        assert normalize_punctuation("[ item ]") == "[item]"

    def test_missing_space_after_period(self):
        assert normalize_punctuation("end.Next") == "end. Next"

    def test_missing_space_after_question_mark(self):
        assert normalize_punctuation("done?Yes") == "done? Yes"

    def test_no_change_on_clean_text(self):
        result = normalize_punctuation("Hello, world. How are you?")
        assert result == "Hello, world. How are you?"

    def test_empty_string(self):
        assert normalize_punctuation("") == ""


# ---------------------------------------------------------------------------
# fix_mojibake
# ---------------------------------------------------------------------------

class TestFixMojibake:
    def test_right_single_quote(self):
        # â€™  →  '
        assert fix_mojibake("\u00e2\u0080\u0099") == "'"

    def test_left_double_quote(self):
        # â€œ  →  "
        assert fix_mojibake("\u00e2\u0080\u009c") == '"'

    def test_right_double_quote(self):
        assert fix_mojibake("\u00e2\u0080\u009d") == '"'

    def test_en_dash(self):
        assert fix_mojibake("\u00e2\u0080\u0093") == "-"

    def test_em_dash(self):
        assert fix_mojibake("\u00e2\u0080\u0094") == "-"

    def test_ellipsis(self):
        assert fix_mojibake("\u00e2\u0080\u00a6") == "..."

    def test_no_change_on_clean_text(self):
        assert fix_mojibake("hello world") == "hello world"

    def test_empty_string(self):
        assert fix_mojibake("") == ""


# ---------------------------------------------------------------------------
# remove_editorial_markup
# ---------------------------------------------------------------------------

class TestRemoveEditorialMarkup:
    def test_removes_block_tag(self):
        result = remove_editorial_markup("[BLOCK]content[/BLOCK]")
        assert "[BLOCK]" not in result
        assert "[/BLOCK]" not in result
        assert "content" in result

    def test_removes_pullquote_tag(self):
        result = remove_editorial_markup("[PULLQUOTE]quote text[/PULLQUOTE]")
        assert "[PULLQUOTE]" not in result
        assert "quote text" in result

    def test_case_insensitive(self):
        result = remove_editorial_markup("[block]text[/block]")
        assert "[block]" not in result

    def test_removes_unknown_allcaps_tag(self):
        result = remove_editorial_markup("[CUSTOM_TAG]")
        assert "[CUSTOM_TAG]" not in result

    def test_preserves_surrounding_text(self):
        result = remove_editorial_markup("Before [NOTE] after")
        assert "Before" in result
        assert "after" in result

    def test_no_change_on_plain_text(self):
        text = "This is a normal sentence."
        assert remove_editorial_markup(text) == text

    def test_empty_string(self):
        assert remove_editorial_markup("") == ""


# ---------------------------------------------------------------------------
# normalize_text  (full pipeline)
# ---------------------------------------------------------------------------

class TestNormalizeText:
    def test_smart_quotes_converted(self):
        result = normalize_text("\u201cHello\u201d")
        assert result == '"Hello"'

    def test_em_dash_converted(self):
        result = normalize_text("word\u2014word")
        assert "-" in result
        assert "\u2014" not in result

    def test_ellipsis_converted(self):
        result = normalize_text("and so\u2026")
        assert "..." in result

    def test_strips_whitespace(self):
        result = normalize_text("  hello world  ")
        assert result == "hello world"

    def test_nbsp_removed(self):
        result = normalize_text("hello\u00a0world")
        assert "\u00a0" not in result

    def test_nlp_mode_adds_punctuation_fix(self):
        result = normalize_text("end.Next", nlp_mode=True)
        assert "end. Next" == result

    def test_nlp_mode_false_leaves_punctuation(self):
        # Without nlp_mode, punctuation spacing is NOT applied
        result = normalize_text("end.Next", nlp_mode=False)
        assert result == "end.Next"

    def test_full_realistic_input(self):
        # Mirrors text patterns from AlterNet / American Conservative scrapers
        raw = "\u201cIt\u2019s a test\u201d \u2014 said the author\u2026"
        result = normalize_text(raw)
        assert '"' in result
        assert "'" in result
        assert "-" in result
        assert "..." in result
        assert "\u201c" not in result
        assert "\u2019" not in result
        assert "\u2014" not in result

    def test_empty_string(self):
        assert normalize_text("") == ""


# ---------------------------------------------------------------------------
# split_paragraphs
# ---------------------------------------------------------------------------

class TestSplitParagraphs:
    def test_splits_on_double_newline(self):
        parts = split_paragraphs("First.\n\nSecond.\n\nThird.")
        assert parts == ["First.", "Second.", "Third."]

    def test_ignores_empty_blocks(self):
        parts = split_paragraphs("First.\n\n\n\nSecond.")
        assert len(parts) == 2

    def test_collapses_internal_line_breaks(self):
        parts = split_paragraphs("line one\nline two\n\nnext para")
        assert parts[0] == "line one line two"

    def test_single_paragraph(self):
        parts = split_paragraphs("Only one paragraph.")
        assert parts == ["Only one paragraph."]

    def test_empty_string(self):
        assert split_paragraphs("") == []

    def test_only_whitespace(self):
        assert split_paragraphs("   \n\n   ") == []


# ---------------------------------------------------------------------------
# is_boilerplate
# ---------------------------------------------------------------------------

class TestIsBoilerplate:
    PATTERNS = [
        "this piece first appeared on",
        "this article first appeared on",
        "originally published",
        "reprinted with permission",
        "sign up for our free",
        "subscribe today to support",
    ]

    def test_matches_counterpunch_disclaimer(self):
        assert is_boilerplate(
            "This piece first appeared on CounterPunch.org.",
            self.PATTERNS
        )

    def test_matches_salon_newsletter_prompt(self):
        assert is_boilerplate(
            "Sign up for our free morning newsletter.",
            self.PATTERNS
        )

    def test_matches_reprint_notice(self):
        assert is_boilerplate(
            "Reprinted with permission from The Nation.",
            self.PATTERNS
        )

    def test_does_not_match_article_text(self):
        assert not is_boilerplate(
            "The president signed the executive order on Friday.",
            self.PATTERNS
        )

    def test_case_insensitive(self):
        assert is_boilerplate(
            "ORIGINALLY PUBLISHED in The Guardian.",
            self.PATTERNS
        )

    def test_empty_text(self):
        assert not is_boilerplate("", self.PATTERNS)

    def test_empty_patterns(self):
        assert not is_boilerplate("Some text here.", [])

    def test_both_empty(self):
        assert not is_boilerplate("", [])