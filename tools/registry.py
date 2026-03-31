from langchain.tools import tool, Tool
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage
from datetime import datetime
from langchain.document_loaders import WebBaseLoader
from langchain_community.tools.tavily_search import TavilySearchResults
import re
import os

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
        cleaned.append(f"{r.get('title')}: {r.get('content')}")
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

def format_text(content: str) -> str:
    # Split after sentences
    sentences = re.split(r'(?<=[.!?]) +', content)
    return "\n".join(sentences)

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
    """
    try:
        filename, content = input_str.split("::", 1)
        path = safe_path(filename.strip())

        formatted = format_text(content)

        with open(path, "w", encoding="utf-8") as f:
            f.write(formatted)

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
                results.append(f"Found in {fname}: {content}")
        except:
            continue
    if not results:
        return "No matches found"
    print(f"[TOOL USED] file_search called with: {query}")
    return "\n\n".join(results[:5])


@tool
def web_scraper(input_str: str) -> str:
    """
    Extract content from a webpage.
    Input format: url::what_to_extract (optional)
    Example: https://example.com::pricing details
    """
    try:
        parts = input_str.split("::")
        url = parts[0].strip()
        query = parts[1].strip() if len(parts) > 1 else None

        loader = WebBaseLoader(url)
        docs = loader.load()
        content = docs[0].page_content

        print(f"[TOOL USED] web_scraper called with: {url}")

        if query:
            return f"Extract '{query}' from the following content:\n{content}"

        return content

    except Exception as e:
        return f"Error scraping website: {str(e)}"


@tool
def code_generator(input_str: str) -> str:
    """
    Generate code using an LLM based on a description.
    """
    try:
        parts = input_str.split("::", 1)
        description = parts[0].strip()
        filename = parts[1].strip() if len(parts) > 1 else None

        provider = os.environ.get("CODE_GEN_PROVIDER", "openai").lower()
        api_key  = os.environ.get("CODE_GEN_API_KEY", "")
        api_url  = os.environ.get("CODE_GEN_API_URL", "https://api.openai.com/v1").rstrip("/")
        model    = os.environ.get("CODE_GEN_MODEL", "gpt-4o-mini")

        if not api_key:
            return "Error: CODE_GEN_API_KEY env var not set."

        system = (
            "You are an expert software engineer. "
            "Generate clean, well-commented, production-ready code. "
            "Return ONLY the code — no explanations, no markdown fences."
        )

        if provider == "anthropic":
            llm = ChatAnthropic(model=model, anthropic_api_key=api_key, temperature=0)
        else:
            llm = ChatOpenAI(
                model=model,
                openai_api_key=api_key,
                openai_api_base=api_url,
                temperature=0,
            )

        result = llm.invoke([SystemMessage(content=system), HumanMessage(content=description)])
        code = result.content.strip()

        print(f"[TOOL USED] code_generator called with: {description[:80]}")

        if filename:
            path = safe_path(filename)
            with open(path, "w", encoding="utf-8") as f:
                f.write(code)
            return f"Code written to '{filename}':\n\n{code}"

        return code

    except Exception as e:
        return f"Error generating code: {e}"


# All available tools by name
TOOL_REGISTRY: dict = {
    "web_search": web_search_tool,
    "web_scraper": web_scraper,
    "file_read": file_read,
    "file_write": file_write,
    "file_search": file_search,
    "calendar_tool": calendar_tool,
    "code_generator": code_generator,
}
CATEGORY_TOOLS: dict = {
    "Development": [file_read, file_write, code_generator],
    "Knowledge & Research": [file_search, web_search_tool, web_scraper],
}