"""Tests for Markdown escaping of user-controlled content."""
import pytest

from pullup_bot.services.xp import md_escape, display


# --- md_escape ---

def test_md_escape_underscore():
    assert md_escape("test_name") == "test\\_name"


def test_md_escape_star():
    assert md_escape("*bold*") == "\\*bold\\*"


def test_md_escape_brackets():
    assert md_escape("[link](url)") == "\\[link\\]\\(url\\)"


def test_md_escape_backtick():
    assert md_escape("`code`") == "\\`code\\`"


def test_md_escape_tilde():
    assert md_escape("~strike~") == "\\~strike\\~"


def test_md_escape_plain():
    assert md_escape("hello world") == "hello world"


def test_md_escape_empty():
    assert md_escape("") == ""


def test_md_escape_combined():
    nasty = "_*[test](url)*_"
    result = md_escape(nasty)
    assert "\\_" in result
    assert "\\*" in result
    assert "\\[" in result


# --- display() output is safe for Markdown when escaped ---

def test_display_special_chars_escaped():
    user = {"first_name": "Ivan_Petrov", "username": "ivan"}
    name = display(user)
    escaped = md_escape(name)
    assert "\\_" in escaped


def test_display_markdown_injection():
    user = {"first_name": "*hacked*", "username": "user"}
    name = display(user)
    escaped = md_escape(name)
    assert "\\*" in escaped
    assert "*hacked*" not in escaped


def test_display_link_injection():
    user = {"first_name": "[click](http://evil.com)", "username": "x"}
    escaped = md_escape(display(user))
    assert "\\[" in escaped
    assert "\\]" in escaped
