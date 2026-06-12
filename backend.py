"""
SheetWise Backend
=================
Reads { "filePath": "...", "query": "..." } from stdin
Routes to:
  - Conversational path: plain-text explanation via Ollama (with dataframe context)
  - Operational path:    JSON plan → execute_plan (no hallucinations)
Prints result as JSON to stdout

Compile with:
    pyinstaller --onefile backend.py
"""

import sys
import json
import os
import requests
import pandas as pd

# ── Add current directory to path so excel_backend can be found ──
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from excel_backend import execute_plan

# ── Config ────────────────────────────────────────────────────────
OLLAMA_URL  = "http://localhost:11434/api/generate"
MODEL_NAME  = "excel-assistant"

# Prompt 1: intent classifier — returns JSON {intent, reason}
INTENT_SYSTEM_PROMPT = """You are a query intent classifier for a spreadsheet assistant.

Classify the user's query as one of two intents:
- "conversational": the user wants an explanation, definition, advice, or general knowledge answer
  that does NOT require reading or modifying data from the spreadsheet.
  Examples: "what is a p-value?", "explain correlation", "how does linear regression work?",
  "what should I look for in this data?", "what chart type is best for comparing categories?"

- "operational": the user wants to perform an action on the loaded spreadsheet data.
  Examples: "show me the top 5 rows by salary", "filter where region is North",
  "plot revenue vs month", "find duplicate emails", "what is the average age?"

Respond ONLY with a valid JSON object. No explanation. No markdown.
Format: {"intent": "conversational" | "operational", "reason": "<one short sentence>"}"""

# Prompt 2: conversational answer — plain text, context-aware
CONVERSATIONAL_SYSTEM_PROMPT = """You are a helpful data analysis assistant.
The user has loaded a spreadsheet with the following structure:
{df_context}

Answer the user's question clearly and concisely in plain text.
You may reference column names or data types from the spreadsheet context if relevant.
Do NOT make up data values. Do NOT perform calculations — just explain."""

# Prompt 3: operational plan — existing behaviour
OPERATIONAL_SYSTEM_PROMPT = """You are a data analysis assistant. Convert the user's natural language request into JSON using this schema:
{
  "tool": "summary | filter | sort | search | aggregate | percentage | top_n | correlation | linear_regression | conditional_calc | plot | heatmap | boxplot | find_duplicates | fill_missing | drop_column",
  "x_column": "",
  "y_column": "",
  "agg": "",
  "n": 0,
  "ascending": false,
  "plot": "",
  "bins": 0,
  "condition_column": "",
  "condition_op": "",
  "condition_value": "",
  "fill_method": "",
  "columns": []
}
Rules:
- Return ONLY valid JSON. No explanation. No SQL. No code.
- Use empty string "" or 0 where not applicable.
- Response must start with { and end with }."""
# ──────────────────────────────────────────────────────────────────


# ── Keyword pre-classifier (runs before Ollama, zero latency) ────
#
# Three tiers, evaluated in order:
#   1. STRONG_OPERATIONAL  → return "operational" immediately
#   2. STRONG_CONVERSATIONAL → return "conversational" immediately
#   3. No match            → fall through to Ollama for ambiguous cases
#
# Design rules:
#   - Prefer false-negatives over false-positives.
#     It's fine to send an ambiguous query to Ollama.
#     It's bad to skip Ollama and get the wrong path.
#   - Operational keywords must appear at the START of the query
#     (after stripping) so "explain what sort does" doesn't misfire.
#   - Conversational keywords can appear ANYWHERE in the query.

_OP_START_VERBS = {
    # Data exploration
    "show", "display", "list", "give me", "get", "fetch",
    # Filtering / searching
    "filter", "search", "find", "where", "select",
    # Sorting
    "sort", "order", "rank",
    # Aggregation
    "calculate", "compute", "sum", "count", "average", "mean",
    "min", "max", "median", "total",
    # Top-N
    "top", "bottom", "highest", "lowest", "largest", "smallest",
    # Visualisation
    "plot", "chart", "graph", "draw", "visualise", "visualize",
    "histogram", "heatmap", "boxplot", "scatter",
    # Stats
    "correlate", "correlation", "regress", "regression",
    # Cleaning
    "drop", "remove", "delete", "fill", "clean", "fix",
    "duplicate", "duplicates", "missing",
    # Percentage / conditional
    "percentage", "percent", "conditional",
}

_CONV_ANYWHERE = {
    # Meta-questions about concepts
    "what is", "what are", "what does", "what do",
    "how does", "how do", "how is", "how are",
    "why does", "why do", "why is",
    "explain", "describe", "define", "definition",
    "tell me about", "can you explain", "could you explain",
    # Advice / recommendation
    "should i", "which chart", "which plot", "best way",
    "recommend", "suggestion", "advice",
    # Conceptual
    "difference between", "when to use", "pros and cons",
}


def _keyword_classify(query: str):
    """
    Fast pre-classifier using keyword matching.
    Returns "operational", "conversational", or None (unknown → use Ollama).
    """
    q = query.strip().lower()

    # Check operational: verb must appear at the very start of the query
    for verb in _OP_START_VERBS:
        if q.startswith(verb):
            return "operational"

    # Check conversational: phrase can appear anywhere
    for phrase in _CONV_ANYWHERE:
        if phrase in q:
            return "conversational"

    return None  # ambiguous — let Ollama decide


# ─────────────────────────────────────────────────────────────────

def _ollama_generate(system: str, prompt: str) -> str:
    """Call Ollama and return the raw response string."""
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL_NAME,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {"temperature": 0.1}
        },
        timeout=60
    )
    response.raise_for_status()
    return response.json()["response"].strip()


def classify_intent(query: str) -> str:
    """
    Returns "conversational" or "operational".

    Fast path: keyword pre-classifier (microseconds, no Ollama call).
    Slow path: Ollama intent classifier, only for ambiguous queries.
    Falls back to "operational" on any parse error (safe default).
    """
    # ── Fast path ────────────────────────────────────────────────
    keyword_result = _keyword_classify(query)
    if keyword_result is not None:
        return keyword_result

    # ── Slow path (Ollama) ───────────────────────────────────────
    raw = _ollama_generate(INTENT_SYSTEM_PROMPT, query)
    start = raw.find("{")
    end   = raw.rfind("}") + 1
    if start == -1 or end == 0:
        return "operational"
    try:
        result = json.loads(raw[start:end])
        intent = result.get("intent", "operational").strip().lower()
        return intent if intent in ("conversational", "operational") else "operational"
    except (json.JSONDecodeError, AttributeError):
        return "operational"


def answer_conversational(query: str, df: pd.DataFrame) -> str:
    """Generate a plain-text explanation using dataframe structure as context."""
    df_context = build_df_context(df)
    system     = CONVERSATIONAL_SYSTEM_PROMPT.format(df_context=df_context)
    return _ollama_generate(system, query)


def nl_to_plan(query: str) -> dict:
    """Convert natural language query to JSON plan via Ollama."""
    raw   = _ollama_generate(OPERATIONAL_SYSTEM_PROMPT, query)
    start = raw.find("{")
    end   = raw.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError(f"No JSON found in model response: {raw}")
    return json.loads(raw[start:end])


def build_df_context(df: pd.DataFrame) -> str:
    """Build a compact description of the dataframe for the conversational prompt."""
    lines = [
        f"Rows: {len(df)}, Columns: {len(df.columns)}",
        "Column names and types:",
    ]
    for col, dtype in df.dtypes.items():
        lines.append(f"  - {col} ({dtype})")
    # Sample a few values per column to give the model real context
    lines.append("Sample values (first 3 rows):")
    sample = df.head(3).to_dict(orient="list")
    for col, vals in sample.items():
        lines.append(f"  - {col}: {vals}")
    return "\n".join(lines)


def load_dataframe(file_path: str) -> pd.DataFrame:
    """Load Excel or CSV file into a DataFrame."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".csv":
        return pd.read_csv(file_path)
    elif ext in [".xlsx", ".xls"]:
        return pd.read_excel(file_path)
    else:
        raise ValueError(f"Unsupported file type: {ext}. Use .xlsx or .csv")


def format_result(result: dict) -> dict:
    """Format execute_plan result for the frontend."""
    rtype = result.get("type")
    tool  = result.get("tool")
    data  = result.get("data")

    if rtype == "chart":
        return {
            "type": "chart",
            "tool": tool,
            "graph": data,
            "text": f"Here is the {tool} chart."
        }
    elif rtype == "table":
        columns = result.get("columns", [])
        rows    = data
        text = f"Found {len(rows)} rows."
        if len(rows) > 0 and len(rows) <= 10:
            text = json.dumps(rows, indent=2)
        elif len(rows) > 10:
            text = f"Showing top {len(rows)} results.\n" + json.dumps(rows[:5], indent=2) + "\n..."
        return {
            "type": "table",
            "tool": tool,
            "columns": columns,
            "rows": rows,
            "text": text
        }
    elif rtype == "scalar":
        return {
            "type": "scalar",
            "tool": tool,
            "text": json.dumps(data, indent=2)
        }
    else:
        return {"type": "unknown", "text": str(data)}


def main():
    raw_input = sys.stdin.read().strip()

    if not raw_input:
        print(json.dumps({"error": "No input received"}))
        sys.exit(1)

    try:
        payload = json.loads(raw_input)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid input JSON: {e}"}))
        sys.exit(1)

    file_path = payload.get("filePath")
    query     = payload.get("query")

    if not file_path:
        print(json.dumps({"error": "No filePath provided"}))
        sys.exit(1)

    if not query:
        print(json.dumps({"error": "No query provided"}))
        sys.exit(1)

    if not os.path.exists(file_path):
        print(json.dumps({"error": f"File not found: {file_path}"}))
        sys.exit(1)

    # Load data (needed for both paths — context for conversational, data for operational)
    try:
        df = load_dataframe(file_path)
    except Exception as e:
        print(json.dumps({"error": f"Failed to load file: {e}"}))
        sys.exit(1)

    # ── Step 1: Classify intent ───────────────────────────────────
    try:
        intent = classify_intent(query)
    except requests.exceptions.ConnectionError:
        print(json.dumps({"error": "Cannot connect to Ollama. Make sure Ollama is running."}))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": f"Intent classification error: {e}"}))
        sys.exit(1)

    # ── Step 2a: Conversational path ─────────────────────────────
    if intent == "conversational":
        try:
            answer = answer_conversational(query, df)
            print(json.dumps({
                "type": "text",
                "tool": "explain",
                "text": answer
            }))
            sys.exit(0)
        except Exception as e:
            print(json.dumps({"error": f"Conversational answer error: {e}"}))
            sys.exit(1)

    # ── Step 2b: Operational path (original behaviour) ───────────
    try:
        plan = nl_to_plan(query)
    except requests.exceptions.ConnectionError:
        print(json.dumps({"error": "Cannot connect to Ollama. Make sure Ollama is running."}))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": f"Model error: {e}"}))
        sys.exit(1)

    try:
        result = execute_plan(plan, df)
    except Exception as e:
        print(json.dumps({"error": f"Execution error: {e}"}))
        sys.exit(1)

    output = format_result(result)
    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    main()
