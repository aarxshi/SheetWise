# SheetWise — AI-Powered Excel Assistant

A natural language data analysis assistant. Ask questions about your data in plain English and get results instantly.

Built with a fine-tuned Qwen2.5-1.5B model for NL→JSON conversion, and a Python backend that executes 15 data operations.

---

## How it works

```
User types: "show average salary by department"
        ↓
  Ollama (excel-assistant model)
        ↓
  { "tool": "aggregate", "x_column": "department", "y_column": "salary", "agg": "mean" }
        ↓
  excel_backend.py → execute_plan(plan, df)
        ↓
  Result rendered in UI (table / chart / scalar)
```

---

## Supported Operations (15 tools)

| Category | Tools |
|---|---|
| Data Exploration | `summary`, `filter`, `sort`, `search` |
| Calculations | `aggregate`, `percentage`, `top_n`, `correlation`, `linear_regression`, `conditional_calc` |
| Visualization | `plot`, `heatmap`, `boxplot` |
| Data Cleaning | `find_duplicates`, `fill_missing`, `drop_column` |

---

## Setup

### 1. Install Ollama
Download from [ollama.com](https://ollama.com) and install.

### 2. Download the model
Download `excel-assistant-GGUF.gguf` from HuggingFace:
[huggingface.co/aarxshi/excel-assistant-Q8_0-GGUF](https://huggingface.co/aarxshi/excel-assistant-Q8_0-GGUF)

Also download the `Modelfile` from the same page.

### 3. Create the Ollama model
Put both files in the same folder, then run:
```bash
ollama create excel-assistant -f Modelfile
```

### 4. Test it
```bash
ollama run excel-assistant
>>> show average salary by department
{"tool": "aggregate", "x_column": "department", "y_column": "salary", ...}
```

### 5. Install Python dependencies
```bash
pip install pandas numpy matplotlib scikit-learn openpyxl
```

---

## Using the backend

```python
import pandas as pd
from excel_backend import execute_plan

# Load your data
df = pd.read_excel("yourfile.xlsx")

# Execute a plan from the model
plan = {
    "tool": "aggregate",
    "x_column": "Department",
    "y_column": "Salary",
    "agg": "mean",
    "plot": "bar"
}

result = execute_plan(plan, df)
print(result["type"])   # "table", "chart", or "scalar"
print(result["data"])   # the actual result
```

### Result types

| type | data | Use for |
|---|---|---|
| `table` | list of dicts + `columns` key | render as data table |
| `chart` | base64 PNG string | decode and show as image |
| `scalar` | dict of values | show as text / cards |

---

## Calling the model from your app

```python
import requests
import json

SYSTEM_PROMPT = """You are a data analysis assistant. Convert the user request into JSON using this schema:
{
  "tool": "summary | filter | sort | search | aggregate | percentage | top_n | correlation | linear_regression | conditional_calc | plot | heatmap | boxplot | find_duplicates | fill_missing | drop_column",
  "x_column": "", "y_column": "", "agg": "", "n": 0, "ascending": false,
  "plot": "", "bins": 0, "condition_column": "", "condition_op": "",
  "condition_value": "", "fill_method": "", "columns": []
}
Rules: Return ONLY valid JSON. No explanation. No SQL. Start with { end with }."""

def nl_to_json(user_input: str) -> dict:
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "excel-assistant",
            "prompt": user_input,
            "system": SYSTEM_PROMPT,
            "stream": False,
            "options": {"temperature": 0.1}
        }
    )
    return json.loads(response.json()["response"])

# Full pipeline
def process_user_request(user_input: str, df):
    plan = nl_to_json(user_input)
    result = execute_plan(plan, df)
    return result

# Example
df = pd.read_excel("data.xlsx")
result = process_user_request("show average salary by department", df)
print(result)
```

---

## Rendering charts

Charts are returned as base64 PNG strings. To display in your frontend:

**Python / Flask:**
```python
# Pass directly to HTML
img_src = f"data:image/png;base64,{result['data']}"
```

**React / JS:**
```javascript
<img src={`data:image/png;base64,${result.data}`} />
```

---

## Project structure

```
SheetWise/
├── excel_backend.py          # Python backend — all 15 tools
├── dataset.jsonl             # 1000 training examples
├── finetune_excel_assistant_v3.ipynb  # Colab fine-tuning notebook
├── generate_dataset.py       # Dataset generation script (needs Ollama)
└── README.md
```

---

## Model

- **Base model:** Qwen2.5-1.5B-Instruct (Alibaba, Apache 2.0)
- **Fine-tuning:** QLoRA on 1000 NL→JSON examples across 15 tools
- **Training:** Google Colab T4 GPU, ~45 minutes
- **Hosted at:** [huggingface.co/aarxshi/excel-assistant-Q8_0-GGUF](https://huggingface.co/aarxshi/excel-assistant-Q8_0-GGUF)

---

## Re-training

If you want to retrain or extend the model:

1. Add new tools to `excel_backend.py`
2. Add examples to `dataset.jsonl`  
3. Run `finetune_excel_assistant_v3.ipynb` on Colab (T4 GPU, free tier)
4. Upload new GGUF to HuggingFace
