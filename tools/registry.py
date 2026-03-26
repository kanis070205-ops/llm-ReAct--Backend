from langchain.tools import tool
from langchain.tools import Tool
from datetime import datetime
import ast
import operator
from langchain_community.tools.tavily_search import TavilySearchResults
# ── Safe calculator (no eval) ─────────────────────────────────

import os

from langgraph.func import task

BASE_DIR_ = os.path.join(os.getcwd(), "workspace")

@tool
def calendar_tool(task: str) -> str:
    """Schedule a task and return a confirmation."""
    print(f"[TOOL USED] calendar_tool called with: {task}")
    return f"Scheduled: '{task}' at {datetime.now().strftime('%Y-%m-%d %H:%M')}"


tavily_tool = TavilySearchResults(max_results=3)
def safe_search(query: str):
    results = tavily_tool.invoke({"query": query})

    # Extract only useful text
    cleaned = []
    for r in results[:3]:
        cleaned.append(f"{r.get('title')}: {r.get('content')[:200]}")
    print(f"[TOOL USED] web_search called with: {query}")
    return "\n".join(cleaned)

web_search_tool = Tool(
    name="web_search",
    func=safe_search,
    description=(
        "Use this to search the web for current information. "
        "Call this at most once. After getting results, summarize and return final answer."
    )
)

def safe_path(filename):
    path = os.path.abspath(os.path.join(BASE_DIR_, filename))

    if not path.startswith(os.path.abspath(BASE_DIR_)):
        raise ValueError("Access denied")

    return path

@tool
def file_read(filename: str) -> str:
    """Read a file from workspace directory."""
    try:
        path = safe_path(filename)

        if not os.path.exists(path):
            return "File not found"

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        print(f"[TOOL USED] file_read called with: {filename}")
        return content

    except Exception as e:
        return f"Error: {e}"
    
@tool
def file_write(input_str: str) -> str:
    """
    Write content to a file.
    Format: filename::content
    Example: notes.txt::Hello world
    """
    try:
        filename, content = input_str.split("::", 1)
        path = safe_path(filename.strip())

        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[TOOL USED] file_write called with: {filename}")
        return f"File '{filename}' written successfully"

    except Exception as e:
        return f"Error: {e}"
    
@tool
def file_search(query: str) -> str:
    """Search for text inside all files in workspace."""
    results = []

    for fname in os.listdir(BASE_DIR_):
        path = safe_path(fname)

        if not os.path.isfile(path):
            continue

        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            if query.lower() in content.lower():
                results.append(f"Found in {fname}: {content[:300]}")

        except:
            continue

    if not results:
        return "No matches found"
    print(f"[TOOL USED] file_search called with: {query}")
    return "\n\n".join(results[:5])


# All available tools by name
TOOL_REGISTRY: dict = {
    "web_search": web_search_tool,
    "file_read": file_read,
    "file_write": file_write,
    "file_search": file_search
}
# Default tools per agent category
CATEGORY_TOOLS: dict = {
    "Development": [file_read, file_write],
    "Code Quality": [file_search, web_search_tool],
}