"""Atlassian Document Format (ADF) helpers. Jira REST v3 rich-text fields require ADF."""

import re

_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_BULLET_RE = re.compile(r"^[-*]\s+")


def _inline_nodes(line: str) -> list[dict]:
    """Split a line on **bold** spans into ADF text nodes, marking the bold runs with a
    `strong` mark. A line with no ** markers is just one plain text node."""
    if not line:
        return []
    nodes = []
    pos = 0
    for m in _BOLD_RE.finditer(line):
        if m.start() > pos:
            nodes.append({"type": "text", "text": line[pos:m.start()]})
        nodes.append({"type": "text", "text": m.group(1), "marks": [{"type": "strong"}]})
        pos = m.end()
    if pos < len(line):
        nodes.append({"type": "text", "text": line[pos:]})
    return nodes


def text_to_adf(text: str) -> dict:
    """Convert plain(-ish) text to ADF: consecutive '- '/'* ' lines become a real bulletList
    (not literal dash characters in a paragraph), '**bold**' spans become real strong-marked
    text, everything else is a paragraph per line (blank lines become an empty paragraph, same
    as before). This is what actually makes AI-drafted content render with real bullets/bold
    in Jira instead of a flat wall of unstyled paragraphs — the field-level prompt
    instructions already ask for this style, this is the render-side half of that."""
    lines = (text or "-").split("\n")
    content = []
    bullet_buffer: list[str] = []

    def flush_bullets():
        if not bullet_buffer:
            return
        content.append({
            "type": "bulletList",
            "content": [
                {"type": "listItem",
                 "content": [{"type": "paragraph", "content": _inline_nodes(item)}]}
                for item in bullet_buffer
            ],
        })
        bullet_buffer.clear()

    for line in lines:
        if _BULLET_RE.match(line):
            bullet_buffer.append(_BULLET_RE.sub("", line, count=1))
            continue
        flush_bullets()
        content.append({"type": "paragraph", "content": _inline_nodes(line)})
    flush_bullets()

    return {"type": "doc", "version": 1, "content": content}


def adf_to_text(node) -> str:
    """Convert an Atlassian Document Format node (as returned by Jira REST v3) to plain text.
    Used when READING rich-text fields (description, acceptance criteria) back from the API.
    Bullet list items are rendered back with a leading '- ' so the round-trip through the
    Analyze form's textarea preserves bullet structure instead of flattening it. Top-level
    blocks (paragraphs, bullet lists) are newline-separated instead of run together."""
    if not isinstance(node, dict):
        return ""
    if node.get("type") == "doc":
        return "\n".join(adf_to_text(child).strip() for child in node.get("content", []) or [])
    if node.get("type") == "bulletList":
        return "\n".join(f"- {adf_to_text(item).strip()}" for item in node.get("content", []) or [])
    text = node.get("text", "")
    for child in node.get("content", []) or []:
        text += adf_to_text(child)
        if node.get("type") in ("paragraph", "listItem"):
            text += " "
    return text.strip()
