"""
Container-side tool registry — mirrors backend/tools/registry.py.
Plain callables only, no LangChain. Each fn(input: str) -> str.
"""
import os
import re
import requests
from datetime import datetime

WORKSPACE = "/app/data"


def _safe_path(filename: str) -> str:
    path = os.path.abspath(os.path.join(WORKSPACE, filename))
    if not path.startswith(os.path.abspath(WORKSPACE)):
        raise ValueError("Access denied: path traversal detected.")
    return path


def _format_text(content: str) -> str:
    sentences = re.split(r'(?<=[.!?]) +', content)
    return "\n".join(sentences)


# ── Tools ──────────────────────────────────────────────────────────────────

def web_search(query: str) -> str:
    """Search the web via Tavily. Input: search query string."""
    api_key = os.environ.get("TAVILY_API_KEY", "")
    if not api_key:
        return "Error: TAVILY_API_KEY not set."
    resp = requests.post(
        "https://api.tavily.com/search",
        json={"api_key": api_key, "query": query, "max_results": 3},
        timeout=15,
    )
    resp.raise_for_status()
    results = resp.json().get("results", [])
    cleaned = [f"{r.get('title')}: {r.get('content', '')[:200]}" for r in results[:3]]
    return "\n".join(cleaned) or "No results found."


def web_scraper(input_str: str) -> str:
    """Extract content from a webpage. Input: url  OR  url::what_to_extract"""
    parts = input_str.split("::")
    url = parts[0].strip()
    query = parts[1].strip() if len(parts) > 1 else None

    resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()

    # Strip HTML tags simply
    text = re.sub(r"<[^>]+>", " ", resp.text)
    text = re.sub(r"\s+", " ", text).strip()[:5000]

    if query:
        return f"Extract '{query}' from:\n{text}"
    return text


def file_read(filename: str) -> str:
    """Read a file from the task workspace. Input: filename."""
    try:
        path = _safe_path(filename)
        if not os.path.exists(path):
            return f"File not found: {filename}"
        with open(path, encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error: {e}"


def file_write(input_str: str) -> str:
    """Write content to a file. Input: filename::content"""
    try:
        if "::" not in input_str:
            return "Error: expected format 'filename::content'"
        filename, content = input_str.split("::", 1)
        path = _safe_path(filename.strip())
        with open(path, "w", encoding="utf-8") as f:
            f.write(_format_text(content))
        return f"File '{filename.strip()}' written successfully."
    except Exception as e:
        return f"Error: {e}"


def file_search(query: str) -> str:
    """Search for text across all files in the workspace. Input: search query."""
    results = []
    try:
        for fname in os.listdir(WORKSPACE):
            path = _safe_path(fname)
            if not os.path.isfile(path):
                continue
            try:
                with open(path, encoding="utf-8") as f:
                    content = f.read()
                if query.lower() in content.lower():
                    results.append(f"Found in {fname}:\n{content[:300]}")
            except Exception:
                continue
    except Exception as e:
        return f"Error: {e}"
    return "\n\n".join(results[:5]) if results else "No matches found."


def calendar_tool(task: str) -> str:
    """Schedule a task and return a confirmation. Input: task description."""
    return f"Scheduled: '{task}' at {datetime.now().strftime('%Y-%m-%d %H:%M')}"


# ── Registry ───────────────────────────────────────────────────────────────

_REGISTRY: dict[str, tuple] = {
    "web_search":    (web_search,    "Search the web for current information. Input: search query string."),
    "web_scraper":   (web_scraper,   "Extract content from a webpage. Input: url  OR  url::what_to_extract"),
    "file_read":     (file_read,     "Read a file from the workspace. Input: filename."),
    "file_write":    (file_write,    "Write content to a file. Input: 'filename::content'."),
    "file_search":   (file_search,   "Search text across all workspace files. Input: search query."),
    "calendar_tool": (calendar_tool, "Schedule a task. Input: task description string."),
}

TOOLS: dict[str, callable] = {name: fn for name, (fn, _) in _REGISTRY.items()}


def describe_tools(names: list[str]) -> str:
    lines = [f"- {n}: {_REGISTRY[n][1]}" for n in names if n in _REGISTRY]
    return "\n".join(lines) if lines else "No tools available."
