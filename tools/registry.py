from langchain.tools import tool
from datetime import datetime
import ast
import operator

# ── Safe calculator (no eval) ─────────────────────────────────

_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
}


def _safe_eval(node):
    if isinstance(node, ast.Constant):
        return node.n
    if isinstance(node, ast.BinOp):
        return _OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp):
        return _OPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError(f"Unsupported: {ast.dump(node)}")


@tool
def calculator(expression: str) -> str:
    """Safely evaluate a math expression. Example: '2 + 3 * 4'"""
    print(f"[TOOL USED] calculator called with: {expression}")
    try:
        result = _safe_eval(ast.parse(expression, mode="eval").body)
        return str(result)
    except Exception as e:
        return f"Error: {e}"


@tool
def current_time(_: str) -> str:
    """Return the current date and time."""
    print(f"[TOOL USED] current_time called")
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@tool
def calendar_tool(task: str) -> str:
    """Schedule a task and return a confirmation."""
    print(f"[TOOL USED] calendar_tool called with: {task}")
    return f"Scheduled: '{task}' at {datetime.now().strftime('%Y-%m-%d %H:%M')}"


@tool
def doc_search(query: str) -> str:
    """Search developer documentation. Wire up a real index when ready."""
    print(f"[TOOL USED] doc_search called with: {query}")
    return f"[doc_search] No index connected yet. Query: '{query}'"


# All available tools by name
TOOL_REGISTRY: dict = {
    "calculator": calculator,
    "current_time": current_time,
    "calendar_tool": calendar_tool,
    "doc_search": doc_search,
}

# Default tools per agent category
CATEGORY_TOOLS: dict = {
    "Development": [doc_search, calculator],
    "Code Quality": [doc_search],
}
