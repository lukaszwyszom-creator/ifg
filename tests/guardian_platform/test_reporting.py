"""Guardian Platform reporting tests."""
from __future__ import annotations

import json

from guardian_platform.core.reporting.writers import (
    render_json,
    render_markdown,
    render_report,
    render_terminal,
)


class TestReporting:
    def test_render_terminal_title(self):
        out = render_terminal({"title": "Test Report", "sections": {"status": "OK"}})
        assert "Test Report" in out
        assert "OK" in out

    def test_render_terminal_list_section(self):
        out = render_terminal({"title": "T", "sections": {"items": ["a", "b"]}})
        assert "• a" in out
        assert "• b" in out

    def test_render_terminal_dict_section(self):
        out = render_terminal({"title": "T", "sections": {"meta": {"k": "v"}}})
        assert "k: v" in out

    def test_render_json_valid(self):
        payload = {"title": "T", "sections": {"x": 1}}
        parsed = json.loads(render_json(payload))
        assert parsed["title"] == "T"

    def test_render_markdown_headers(self):
        out = render_markdown({"title": "My Report", "sections": {"status": "OK"}})
        assert "# My Report" in out
        assert "## status" in out

    def test_render_markdown_list(self):
        out = render_markdown({"title": "T", "sections": {"items": ["one"]}})
        assert "- one" in out

    def test_render_report_terminal_default(self):
        out = render_report({"title": "T", "sections": {}}, "terminal")
        assert "T" in out

    def test_render_report_json(self):
        out = render_report({"title": "T", "sections": {"a": 1}}, "json")
        assert json.loads(out)["sections"]["a"] == 1

    def test_render_report_markdown(self):
        out = render_report({"title": "T", "sections": {"a": 1}}, "markdown")
        assert "# T" in out

    def test_render_markdown_dict_section(self):
        out = render_markdown({"title": "T", "sections": {"meta": {"branch": "main"}}})
        assert "**branch:** main" in out
