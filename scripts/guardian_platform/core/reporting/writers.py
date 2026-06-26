from __future__ import annotations

import json
from typing import Any


def render_terminal(payload: dict[str, Any]) -> str:
    lines = [payload.get("title", "Guardian Report"), "=" * 40]
    for key, value in payload.get("sections", {}).items():
        lines.append(f"\n{key}:")
        if isinstance(value, list):
            lines.extend(f"  • {item}" for item in value)
        elif isinstance(value, dict):
            for k, v in value.items():
                lines.append(f"  {k}: {v}")
        else:
            lines.append(f"  {value}")
    lines.append("")
    return "\n".join(lines)


def render_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2)


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [f"# {payload.get('title', 'Guardian Report')}", ""]
    for key, value in payload.get("sections", {}).items():
        lines.append(f"## {key}")
        lines.append("")
        if isinstance(value, list):
            lines.extend(f"- {item}" for item in value)
        elif isinstance(value, dict):
            for k, v in value.items():
                lines.append(f"- **{k}:** {v}")
        else:
            lines.append(str(value))
        lines.append("")
    return "\n".join(lines)


def render_report(payload: dict[str, Any], fmt: str) -> str:
    if fmt == "json":
        return render_json(payload)
    if fmt == "markdown":
        return render_markdown(payload)
    return render_terminal(payload)
