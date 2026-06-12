"""
Excel Assistant - Expanded Python Backend
==========================================
Supports 15 tools callable via a JSON plan (from fine-tuned NLP model).

Schema:
{
  "tool": "<tool_name>",
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

Tools:
  Data Exploration : summary, filter, sort, search
  Calculations     : aggregate, percentage, top_n, correlation, linear_regression, conditional_calc
  Visualization    : plot, heatmap, boxplot
  Data Cleaning    : find_duplicates, fill_missing, drop_column
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use("Agg")  # non-interactive backend (safe for all environments)
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score
import io, base64


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _fig_to_base64() -> str:
    """Convert current matplotlib figure to base64 PNG string."""
    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", dpi=120)
    plt.close()
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def _require(plan: dict, *keys):
    for k in keys:
        if not plan.get(k):
            raise ValueError(f"Missing required field: '{k}'")


OPERATORS = {
    ">": lambda col, val: col > val,
    "<": lambda col, val: col < val,
    ">=": lambda col, val: col >= val,
    "<=": lambda col, val: col <= val,
    "==": lambda col, val: col == val,
    "!=": lambda col, val: col != val,
    "contains": lambda col, val: col.astype(str).str.contains(str(val), case=False, na=False),
}


# ─────────────────────────────────────────────────────────────────────────────
# Data Exploration Tools
# ─────────────────────────────────────────────────────────────────────────────

def summary(df: pd.DataFrame, plan: dict) -> dict:
    """
    Returns a statistical overview of the entire dataset.
    No required fields.
    """
    desc = df.describe(include="all").fillna("").astype(str).to_dict()
    return {
        "rows": len(df),
        "columns": len(df.columns),
        "column_names": list(df.columns),
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "missing_values": df.isnull().sum().to_dict(),
        "describe": desc,
    }


def filter_rows(df: pd.DataFrame, plan: dict) -> pd.DataFrame:
    """
    Filter rows based on a condition.
    Required: condition_column, condition_op, condition_value
    Example: salary > 50000 | department contains 'eng'
    """
    _require(plan, "condition_column", "condition_op", "condition_value")
    col = plan["condition_column"]
    op = plan["condition_op"]
    raw_val = plan["condition_value"]

    if op not in OPERATORS:
        raise ValueError(f"Unsupported operator '{op}'. Use: {list(OPERATORS.keys())}")

    # Try to cast value to numeric if column is numeric
    try:
        val = float(raw_val) if df[col].dtype in [np.float64, np.int64] else raw_val
    except (ValueError, TypeError):
        val = raw_val

    mask = OPERATORS[op](df[col], val)
    result = df[mask].reset_index(drop=True)
    return result


def sort_data(df: pd.DataFrame, plan: dict) -> pd.DataFrame:
    """
    Sort dataset by a column.
    Required: x_column
    Optional: ascending (default False)
    """
    _require(plan, "x_column")
    return df.sort_values(
        by=plan["x_column"],
        ascending=plan.get("ascending", False)
    ).reset_index(drop=True)


def search(df: pd.DataFrame, plan: dict) -> pd.DataFrame:
    """
    Search for rows where any column contains a value.
    Required: condition_value (the search term)
    Optional: condition_column (search in specific column only)
    """
    _require(plan, "condition_value")
    term = str(plan["condition_value"])
    col = plan.get("condition_column")

    if col:
        mask = df[col].astype(str).str.contains(term, case=False, na=False)
    else:
        mask = df.apply(lambda row: row.astype(str).str.contains(term, case=False, na=False).any(), axis=1)

    return df[mask].reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# Calculation Tools
# ─────────────────────────────────────────────────────────────────────────────

def aggregate(df: pd.DataFrame, plan: dict) -> pd.DataFrame | dict:
    """
    Group by x_column and aggregate y_column.
    Required: y_column, agg
    Optional: x_column (if omitted, aggregates entire column)
    Supported agg: mean, sum, min, max, count, median, std
    """
    _require(plan, "y_column", "agg")
    agg_fn = plan["agg"]
    y_col = plan["y_column"]
    x_col = plan.get("x_column")

    supported = ["mean", "sum", "min", "max", "count", "median", "std"]
    if agg_fn not in supported:
        raise ValueError(f"Unsupported agg '{agg_fn}'. Use: {supported}")

    if not x_col:
        series = df[y_col].dropna()
        return {agg_fn: float(getattr(series, agg_fn)())}

    result = df.groupby(x_col)[y_col].agg(agg_fn).reset_index()
    result.columns = [x_col, f"{agg_fn}_{y_col}"]
    return result


def percentage(df: pd.DataFrame, plan: dict) -> pd.DataFrame:
    """
    Percentage breakdown of a categorical column's value counts,
    or percentage of a numeric column relative to total.
    Required: x_column
    """
    _require(plan, "x_column")
    col = plan["x_column"]

    if df[col].dtype == object or df[col].nunique() < 20:
        counts = df[col].value_counts()
        pct = (counts / counts.sum() * 100).round(2)
        return pd.DataFrame({"value": pct.index, "percentage": pct.values})
    else:
        total = df[col].sum()
        result = df[[col]].copy()
        result["percentage"] = (df[col] / total * 100).round(2)
        return result


def top_n(df: pd.DataFrame, plan: dict) -> pd.DataFrame:
    """
    Return top or bottom N rows by a column.
    Required: y_column
    Optional: n (default 5), ascending (default False = top)
    """
    _require(plan, "y_column")
    n = int(plan.get("n") or 5)
    return df.sort_values(
        by=plan["y_column"],
        ascending=plan.get("ascending", False)
    ).head(n).reset_index(drop=True)


def correlation(df: pd.DataFrame, plan: dict) -> dict:
    """
    Compute correlation between two numeric columns, or full correlation matrix.
    Optional: x_column, y_column (if omitted, returns full matrix)
    """
    x_col = plan.get("x_column")
    y_col = plan.get("y_column")

    if x_col and y_col:
        corr = df[x_col].corr(df[y_col])
        return {
            "x_column": x_col,
            "y_column": y_col,
            "correlation": round(float(corr), 4),
            "interpretation": (
                "strong positive" if corr > 0.7 else
                "moderate positive" if corr > 0.4 else
                "weak positive" if corr > 0 else
                "weak negative" if corr > -0.4 else
                "moderate negative" if corr > -0.7 else
                "strong negative"
            )
        }
    else:
        numeric_df = df.select_dtypes(include="number")
        return numeric_df.corr().round(4).to_dict()


def linear_regression(df: pd.DataFrame, plan: dict) -> dict:
    """
    Fit a linear regression between x_column and y_column.
    Required: x_column, y_column
    """
    _require(plan, "x_column", "y_column")
    x_col, y_col = plan["x_column"], plan["y_column"]
    df_clean = df[[x_col, y_col]].dropna()
    X = df_clean[[x_col]].values
    y = df_clean[y_col].values
    model = LinearRegression()
    model.fit(X, y)
    y_pred = model.predict(X)
    return {
        "slope": round(float(model.coef_[0]), 4),
        "intercept": round(float(model.intercept_), 4),
        "r2_score": round(float(r2_score(y, y_pred)), 4),
        "interpretation": f"For every 1 unit increase in {x_col}, {y_col} changes by {model.coef_[0]:.4f}",
    }


def conditional_calc(df: pd.DataFrame, plan: dict) -> dict:
    """
    SUMIF / COUNTIF / AVERAGEIF style calculation.
    Required: condition_column, condition_op, condition_value, agg, y_column
    Example: average salary WHERE department == Engineering
    """
    _require(plan, "condition_column", "condition_op", "condition_value", "agg", "y_column")
    filtered = filter_rows(df, plan)
    sub_plan = {**plan, "x_column": None}
    return aggregate(filtered, sub_plan)


# ─────────────────────────────────────────────────────────────────────────────
# Visualization Tools
# ─────────────────────────────────────────────────────────────────────────────

def plot(df: pd.DataFrame, plan: dict) -> str:
    """
    Plot data. Returns base64 PNG.
    Required: plot (chart type), x_column
    Optional: y_column, bins
    Supported: line, bar, scatter, histogram, area, pie
    """
    _require(plan, "plot", "x_column")
    x_col = plan["x_column"]
    y_col = plan.get("y_column")
    plot_type = plan["plot"]
    bins = int(plan.get("bins") or 20)

    fig, ax = plt.subplots(figsize=(8, 5))

    if plot_type == "histogram":
        col = y_col or x_col
        ax.hist(df[col].dropna(), bins=bins, edgecolor="black")
        ax.set_xlabel(col)
        ax.set_ylabel("Frequency")
        ax.set_title(f"Distribution of {col}")

    elif plot_type == "line":
        _require(plan, "y_column")
        df_clean = df[[x_col, y_col]].dropna()
        ax.plot(df_clean[x_col], df_clean[y_col], marker="o")
        ax.set_xlabel(x_col)
        ax.set_ylabel(y_col)
        ax.set_title(f"{y_col} over {x_col}")

    elif plot_type == "bar":
        _require(plan, "y_column")
        df_clean = df[[x_col, y_col]].dropna()
        ax.bar(df_clean[x_col].astype(str), df_clean[y_col])
        ax.set_xlabel(x_col)
        ax.set_ylabel(y_col)
        ax.set_title(f"{y_col} by {x_col}")
        plt.xticks(rotation=45, ha="right")

    elif plot_type == "scatter":
        _require(plan, "y_column")
        df_clean = df[[x_col, y_col]].dropna()
        ax.scatter(df_clean[x_col], df_clean[y_col], alpha=0.6)
        ax.set_xlabel(x_col)
        ax.set_ylabel(y_col)
        ax.set_title(f"{y_col} vs {x_col}")

    elif plot_type == "area":
        _require(plan, "y_column")
        df_clean = df[[x_col, y_col]].dropna()
        ax.fill_between(range(len(df_clean)), df_clean[y_col], alpha=0.4)
        ax.plot(range(len(df_clean)), df_clean[y_col])
        ax.set_title(f"{y_col} area chart")

    elif plot_type == "pie":
        counts = df[x_col].value_counts()
        ax.pie(counts.values, labels=counts.index, autopct="%1.1f%%", startangle=90)
        ax.set_title(f"Distribution of {x_col}")

    else:
        raise ValueError(f"Unsupported plot type '{plot_type}'. Use: line, bar, scatter, histogram, area, pie")

    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    return _fig_to_base64()


def heatmap(df: pd.DataFrame, plan: dict) -> str:
    """
    Correlation heatmap of all numeric columns. Returns base64 PNG.
    No required fields.
    """
    numeric_df = df.select_dtypes(include="number")
    corr = numeric_df.corr()

    fig, ax = plt.subplots(figsize=(max(6, len(corr)), max(5, len(corr) - 1)))
    im = ax.imshow(corr, cmap="coolwarm", vmin=-1, vmax=1)
    plt.colorbar(im, ax=ax)

    ax.set_xticks(range(len(corr.columns)))
    ax.set_yticks(range(len(corr.columns)))
    ax.set_xticklabels(corr.columns, rotation=45, ha="right")
    ax.set_yticklabels(corr.columns)

    for i in range(len(corr)):
        for j in range(len(corr.columns)):
            ax.text(j, i, f"{corr.iloc[i, j]:.2f}", ha="center", va="center", fontsize=8)

    ax.set_title("Correlation Heatmap")
    plt.tight_layout()
    return _fig_to_base64()


def boxplot(df: pd.DataFrame, plan: dict) -> str:
    """
    Boxplot of y_column, optionally grouped by x_column. Returns base64 PNG.
    Required: y_column
    Optional: x_column (for grouped boxplot)
    """
    _require(plan, "y_column")
    y_col = plan["y_column"]
    x_col = plan.get("x_column")

    fig, ax = plt.subplots(figsize=(8, 5))

    if x_col:
        groups = [grp[y_col].dropna().values for _, grp in df.groupby(x_col)]
        labels = [str(k) for k in df[x_col].unique()]
        ax.boxplot(groups, tick_labels=labels)
        ax.set_xlabel(x_col)
        plt.xticks(rotation=45, ha="right")
    else:
        ax.boxplot(df[y_col].dropna().values)
        ax.set_xticklabels([y_col])

    ax.set_ylabel(y_col)
    ax.set_title(f"Distribution of {y_col}" + (f" by {x_col}" if x_col else ""))
    ax.grid(True, alpha=0.3, axis="y")
    plt.tight_layout()
    return _fig_to_base64()


# ─────────────────────────────────────────────────────────────────────────────
# Data Cleaning Tools
# ─────────────────────────────────────────────────────────────────────────────

def find_duplicates(df: pd.DataFrame, plan: dict) -> dict:
    """
    Find duplicate rows, optionally by specific columns.
    Optional: columns (list of column names to check)
    """
    cols = plan.get("columns") or None
    dupes = df[df.duplicated(subset=cols, keep=False)]
    return {
        "duplicate_count": len(dupes),
        "total_rows": len(df),
        "duplicate_rows": dupes.reset_index(drop=True).to_dict(orient="records"),
    }


def fill_missing(df: pd.DataFrame, plan: dict) -> pd.DataFrame:
    """
    Fill missing values in a column.
    Required: x_column, fill_method
    Supported fill_method: mean, median, mode, zero, forward, backward
    Optional: condition_value (literal fill value, overrides fill_method)
    """
    _require(plan, "x_column", "fill_method")
    col = plan["x_column"]
    method = plan["fill_method"]
    result = df.copy()

    if plan.get("condition_value") is not None:
        result[col] = result[col].fillna(plan["condition_value"])
    elif method == "mean":
        result[col] = result[col].fillna(result[col].mean())
    elif method == "median":
        result[col] = result[col].fillna(result[col].median())
    elif method == "mode":
        result[col] = result[col].fillna(result[col].mode()[0])
    elif method == "zero":
        result[col] = result[col].fillna(0)
    elif method == "forward":
        result[col] = result[col].ffill()
    elif method == "backward":
        result[col] = result[col].bfill()
    else:
        raise ValueError(f"Unsupported fill_method '{method}'. Use: mean, median, mode, zero, forward, backward")

    return result


def drop_column(df: pd.DataFrame, plan: dict) -> pd.DataFrame:
    """
    Drop one or more columns from the dataset.
    Required: columns (list) OR x_column (single column)
    """
    cols = plan.get("columns") or ([plan["x_column"]] if plan.get("x_column") else None)
    if not cols:
        raise ValueError("Provide 'columns' list or 'x_column' to drop.")
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"Columns not found: {missing}")
    return df.drop(columns=cols).reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# Master dispatcher
# ─────────────────────────────────────────────────────────────────────────────

TOOL_MAP = {
    # Data Exploration
    "summary":            summary,
    "filter":             filter_rows,
    "sort":               sort_data,
    "search":             search,
    # Calculations
    "aggregate":          aggregate,
    "percentage":         percentage,
    "top_n":              top_n,
    "correlation":        correlation,
    "linear_regression":  linear_regression,
    "conditional_calc":   conditional_calc,
    # Visualization
    "plot":               plot,
    "heatmap":            heatmap,
    "boxplot":            boxplot,
    # Data Cleaning
    "find_duplicates":    find_duplicates,
    "fill_missing":       fill_missing,
    "drop_column":        drop_column,
}


def execute_plan(plan: dict, df: pd.DataFrame):
    """
    Main entry point. Receives a JSON plan from the NLP model and executes it.

    Returns:
        dict with keys:
          - "type": "table" | "chart" | "scalar"
          - "data": the result (DataFrame, dict, or base64 string)
          - "tool": which tool was used
    """
    tool = plan.get("tool")
    if not tool:
        raise ValueError("Plan is missing 'tool' field.")
    if tool not in TOOL_MAP:
        raise ValueError(f"Unknown tool '{tool}'. Available: {list(TOOL_MAP.keys())}")

    # Fix column name casing — match model output to actual column names
    col_map = {c.lower(): c for c in df.columns}
    for field in ["x_column", "y_column", "condition_column"]:
        if plan.get(field):
            plan[field] = col_map.get(plan[field].lower(), plan[field])
    if plan.get("columns"):
        plan["columns"] = [col_map.get(c.lower(), c) for c in plan["columns"]]

    result = TOOL_MAP[tool](df, plan)

    # Determine result type for UI rendering
    if isinstance(result, pd.DataFrame):
        return {"type": "table", "tool": tool, "data": result.to_dict(orient="records"), "columns": list(result.columns)}
    elif isinstance(result, str):  # base64 image
        return {"type": "chart", "tool": tool, "data": result}
    elif isinstance(result, dict):
        return {"type": "scalar", "tool": tool, "data": result}
    else:
        return {"type": "scalar", "tool": tool, "data": result}


# ─────────────────────────────────────────────────────────────────────────────
# Quick smoke test
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    df = pd.DataFrame({
        "Department": ["HR", "HR", "Engineering", "Engineering", "Sales", "Sales"],
        "Salary":     [45000, 47000, 80000, 82000, 55000, 60000],
        "Experience": [2, 3, 5, 7, 4, 6],
        "Name":       ["Alice", "Bob", "Charlie", "David", "Eva", "Frank"],
    })

    tests = [
        {"tool": "summary"},
        {"tool": "aggregate",   "x_column": "Department", "y_column": "Salary",     "agg": "mean"},
        {"tool": "filter",      "condition_column": "Salary", "condition_op": ">",   "condition_value": "50000"},
        {"tool": "top_n",       "y_column": "Salary", "n": 3},
        {"tool": "sort",        "x_column": "Salary", "ascending": True},
        {"tool": "search",      "condition_value": "eng"},
        {"tool": "percentage",  "x_column": "Department"},
        {"tool": "correlation", "x_column": "Experience", "y_column": "Salary"},
        {"tool": "linear_regression", "x_column": "Experience", "y_column": "Salary"},
        {"tool": "conditional_calc", "condition_column": "Department", "condition_op": "==",
         "condition_value": "Engineering", "agg": "mean", "y_column": "Salary"},
        {"tool": "find_duplicates"},
        {"tool": "fill_missing", "x_column": "Salary", "fill_method": "mean"},
        {"tool": "plot",    "plot": "bar",       "x_column": "Department", "y_column": "Salary"},
        {"tool": "heatmap"},
        {"tool": "boxplot", "y_column": "Salary", "x_column": "Department"},
    ]

    for plan in tests:
        try:
            result = execute_plan(plan, df)
            data_preview = str(result["data"])[:80] + "..." if len(str(result["data"])) > 80 else result["data"]
            print(f"✅ [{plan['tool']:20s}] type={result['type']:10s} | {data_preview}")
        except Exception as e:
            print(f"❌ [{plan['tool']:20s}] ERROR: {e}")