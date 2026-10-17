import base64
import pandas as pd
import streamlit as st

from excel_backend import execute_plan

st.set_page_config(
    page_title="SheetWise",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- Theme ----------
st.markdown(
    """
    <style>
    :root {
        --forest: #294720;
        --forest-dark: #1c2b20;
        --panel: #3e5e35;
        --canvas: #83a875;
        --canvas-light: #91b485;
        --bubble: #294720;
        --white: #f7faf4;
    }

    [data-testid="stAppViewContainer"] {
        background: var(--canvas);
    }
    [data-testid="stHeader"] {
        background: var(--forest-dark);
    }
    [data-testid="stToolbar"] { right: 1rem; }
    [data-testid="stSidebar"] {
        background: var(--forest);
        border-right: 1px solid rgba(255,255,255,.10);
    }
    [data-testid="stSidebar"] * {
        color: #f4f7ef;
    }
    [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {
        background: rgba(255,255,255,.08);
        border: 1px dashed rgba(255,255,255,.25);
    }
    .block-container {
        max-width: 1450px;
        padding: 1.1rem 1.5rem 6.5rem 1.5rem;
    }
    /* Keep the main content compact and readable at desktop resolutions. */
    [data-testid="stMainBlockContainer"] {
        max-width: 1450px;
    }
    h1 { font-size: clamp(1.7rem, 2.4vw, 2.35rem) !important; }
    h2 { font-size: 1.55rem !important; }
    p, label, [data-testid="stMarkdownContainer"] {
        line-height: 1.45;
    }
    [data-testid="stSidebar"] .block-container {
        padding: 1rem .85rem 1rem .85rem;
        display: flex;
        flex-direction: column;
        min-height: calc(100vh - 2rem);
    }
    [data-testid="stSidebar"] [data-testid="stFileUploader"] {
        margin-top: .75rem;
    }
    [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {
        padding: .8rem;
        min-height: 120px;
        background: rgba(255,255,255,.08);
        border: 1px dashed rgba(255,255,255,.3);
    }
    [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] div,
    [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] small {
        color: #f4f7ef !important;
    }
    h1, h2, h3, p, label, .stCaption {
        color: #f7faf4;
    }
    .brand {
        display: flex;
        align-items: center;
        gap: 12px;
        font-size: 1.25rem;
        font-weight: 750;
        margin: .25rem 0 1.2rem 0;
    }
    .brand-icon {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 38px;
        height: 38px;
        border-radius: 12px;
        background: #f2f5ed;
        color: var(--forest);
        font-weight: 800;
    }
        /* Browse files button */
    [data-testid="stFileUploaderDropzone"] button {
        background-color: #294720 !important;
        color: #ffffff !important;
        border: 1px solid #294720 !important;
        border-radius: 8px !important;
        opacity: 1 !important;
    }

    [data-testid="stFileUploaderDropzone"] button:hover {
        background-color: #3e5e35 !important;
        color: #ffffff !important;
        border-color: #3e5e35 !important;
    }

    [data-testid="stFileUploaderDropzone"] button p,
    [data-testid="stFileUploaderDropzone"] button span {
        color: #ffffff !important;
    }
    .topbar {
        background: var(--canvas-light);
        border-bottom: 1px solid rgba(255,255,255,.15);
        margin: -1.25rem -1rem 1.5rem -1rem;
        padding: 1rem 1.4rem;
        font-weight: 650;
        color: white;
        font-size: 1.05rem;
    }
    .eyebrow {
        text-transform: uppercase;
        letter-spacing: .12em;
        color: #dce8d5;
        font-size: .72rem;
        font-weight: 700;
        margin: 1.2rem 0 .5rem 0;
    }
    .chat-user {
        background: #f5f8f1;
        color: #273626;
        border-radius: 20px 20px 5px 20px;
        padding: 14px 18px;
        margin: .5rem 0 1.25rem auto;
        width: fit-content;
        max-width: 75%;
        box-shadow: 0 4px 12px rgba(25,55,25,.08);
    }
    .chat-assistant {
        background: var(--bubble);
        color: #f7faf4;
        border-radius: 20px 20px 20px 5px;
        padding: 16px 19px;
        margin: .4rem 0 1rem 0;
        max-width: 88%;
        line-height: 1.55;
        box-shadow: 0 5px 14px rgba(25,55,25,.12);
    }
    .result-label {
        display: inline-block;
        background: rgba(41,71,32,.62);
        color: white;
        padding: 7px 14px;
        border-radius: 20px;
        font-size: .82rem;
        margin: .4rem 0 .75rem 0;
    }
    div.stButton > button {
        width: 100%;
        min-height: 54px;
        height: auto;
        padding: .65rem .85rem;
        border: 1px solid rgba(255,255,255,.22);
        border-radius: 12px;
        background: #f5f7f2;
        color: #263a25 !important;
        font-weight: 600;
        font-size: .92rem;
        line-height: 1.3;
        white-space: normal;
        opacity: 1 !important;
        transition: transform .12s ease, background .12s ease;
    }
    div.stButton > button p,
    div.stButton > button span {
        color: #263a25 !important;
        font-weight: 600;
        font-size: .92rem;
        line-height: 1.3;
        white-space: normal;
        opacity: 1 !important;
    }
    div.stButton > button:hover,
    div.stButton > button:hover p,
    div.stButton > button:hover span {
        background: #ffffff;
        color: #1e321d !important;
        border-color: #ffffff;
        transform: translateY(-1px);
    }
    div.stButton > button:focus:not(:active) {
        border-color: #294720;
        color: #1e321d !important;
    }
    [data-testid="stBottom"] {
        background: #83a875;
    }
    [data-testid="stChatInput"] {
        border-radius: 16px;
        background: #f7f8f5;
        border: 1px solid rgba(41,71,32,.25);
        box-shadow: 0 4px 14px rgba(25,55,25,.12);
    }
    [data-testid="stChatInput"] textarea {
        color: #263a25 !important;
        -webkit-text-fill-color: #263a25 !important;
        font-size: 1rem;
    }
    [data-testid="stChatInput"] textarea::placeholder {
        color: #657460 !important;
        -webkit-text-fill-color: #657460 !important;
        opacity: 1;
    }
    [data-testid="stChatInput"] button {
        color: #263a25 !important;
    }
    /* Sidebar controls need the same strong contrast as the main buttons. */
    [data-testid="stSidebar"] div.stButton > button,
    [data-testid="stSidebar"] div.stButton > button p,
    [data-testid="stSidebar"] div.stButton > button span {
        background: #f5f7f2;
        color: #263a25 !important;
    }
    [data-testid="stFileUploaderDropzone"] button,
    [data-testid="stFileUploaderDropzone"] button span {
        color: #263a25 !important;
    }
    [data-testid="stAlert"] {
        border-radius: 12px;
    }
    [data-testid="stDataFrame"] {
        border-radius: 14px;
        overflow: hidden;
    }
    hr { border-color: rgba(255,255,255,.20); }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------- Sample data ----------
@st.cache_data
def load_sample_data():
    return pd.DataFrame({
        "Product": [
            "Air Purifier", "Water Filter", "Shower Filter",
            "Water Filter", "Air Purifier", "Shower Filter",
            "Water Filter", "Air Purifier", "Shower Filter",
            "Water Filter", "Air Purifier", "Shower Filter"
        ],
        "Region": [
            "South", "West", "North", "South",
            "West", "East", "North", "South",
            "West", "East", "North", "South"
        ],
        "Revenue": [
            18500, 12000, 8500, 15000,
            22000, 9500, 13500, 19800,
            11000, 14500, 17500, 12500
        ],
        "Units": [37, 30, 34, 25, 44, 19, 27, 40, 22, 29, 35, 25],
        "Discount": [5, 10, 0, 5, 8, 0, 10, 5, 12, 5, 8, 0],
    })

sample_df = load_sample_data()

# ---------- Sidebar ----------
with st.sidebar:
    st.markdown(
        '<div class="brand"><span class="brand-icon">S</span> SheetWise</div>',
        unsafe_allow_html=True,
    )

    if st.button("＋  New Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    st.markdown('<div class="eyebrow">Recent</div>', unsafe_allow_html=True)
    if st.session_state.get("messages"):
        latest = next(
            (m["content"] for m in reversed(st.session_state.messages)
             if m["role"] == "user"),
            "New conversation",
        )
        st.caption(latest[:30] + ("…" if len(latest) > 30 else ""))
    else:
        st.caption("Your questions will appear here.")

    st.markdown("<hr style='margin: 1.2rem 0 .8rem 0; opacity: .25;'>", unsafe_allow_html=True)
    uploaded_file = st.file_uploader(
        "Choose an Excel file",
        type=["xlsx", "xls", "csv"],
        label_visibility="collapsed",
    )
    if uploaded_file is not None:
        try:
            if uploaded_file.name.lower().endswith(".csv"):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            st.success(f"Loaded {uploaded_file.name}")
        except Exception as exc:
            st.error(f"Couldn't read file: {exc}")
            df = sample_df.copy()
    else:
        df = sample_df.copy()

    st.caption("Using fictional sample data" if uploaded_file is None else f"{len(df):,} rows loaded")

# ---------- Query planning ----------
def make_plan(question):
    q = question.lower().strip()

    if "correlation" in q and "units" in q and "revenue" in q:
        return {"tool": "correlation", "x_column": "Units", "y_column": "Revenue"}

    if any(word in q for word in ["plot", "chart", "graph", "visualise", "visualize"]):
        if "revenue" in q and "product" in q:
            return {
                "tool": "plot", "plot": "bar",
                "x_column": "Product", "y_column": "Revenue"
            }

    if "top" in q and "revenue" in q:
        n = 5
        for token in q.split():
            if token.isdigit():
                n = max(1, min(int(token), 20))
                break
        return {"tool": "top_n", "y_column": "Revenue", "n": n}

    if "average" in q or "mean" in q:
        if "revenue" in q and "region" in q:
            return {
                "tool": "aggregate", "x_column": "Region",
                "y_column": "Revenue", "agg": "mean"
            }

    if "west" in q and any(word in q for word in ["filter", "show", "sales", "region"]):
        return {
            "tool": "filter", "condition_column": "Region",
            "condition_op": "==", "condition_value": "West"
        }

    if any(word in q for word in ["summarise", "summarize", "summary", "overview"]):
        return {"tool": "summary"}

    return None


def analyse(question, data):
    plan = make_plan(question)
    if plan is None:
        return {
            "type": "message",
            "data": (
                "I can't handle that question in this demo yet. Try one of the "
                "suggestions below, or ask about average revenue by region, top "
                "products, West-region sales, or the relationship between units and revenue."
            ),
        }

    result = execute_plan(plan, data.copy())
    return {"type": result.get("type", "json"), "data": result.get("data"),
            "columns": result.get("columns"), "tool": result.get("tool", plan["tool"])}


def render_result(result):
    if result["type"] == "message":
        st.markdown(f'<div class="chat-assistant">{result["data"]}</div>', unsafe_allow_html=True)
        return

    st.markdown(
        f'<div class="result-label">Analysis · {result.get("tool", "result")}</div>',
        unsafe_allow_html=True,
    )
    if result["type"] == "table":
        output = pd.DataFrame(result["data"], columns=result.get("columns"))
        st.dataframe(output, use_container_width=True, hide_index=True)
    elif result["type"] == "chart":
        image_bytes = base64.b64decode(result["data"])
        st.image(image_bytes, use_container_width=False)
    else:
        st.json(result["data"])


# ---------- Main conversation ----------
if "messages" not in st.session_state:
    st.session_state.messages = []

last_question = next(
    (m["content"] for m in reversed(st.session_state.messages) if m["role"] == "user"),
    "Ask a question about your data",
)
st.markdown(
    f'<div class="topbar">{last_question[:72]}'
    f'<span style="float:right;font-size:.82rem;font-weight:500;opacity:.8">● Ready</span></div>',
    unsafe_allow_html=True,
)

if not st.session_state.messages:
    st.markdown("## Your data, in plain English")
    st.markdown(
        '<div class="chat-assistant">Ask a question about your spreadsheet and SheetWise '
        'will turn it into a supported analysis.</div>',
        unsafe_allow_html=True,
    )
else:
    for message in st.session_state.messages:
        if message["role"] == "user":
            st.markdown(
                f'<div class="chat-user">{message["content"]}</div>',
                unsafe_allow_html=True,
            )
        else:
            with st.container():
                render_result(message["result"])

st.markdown('<div class="eyebrow">Try asking</div>', unsafe_allow_html=True)
suggestions = [
    "Show average revenue by region",
    "Show the top 5 products by revenue",
    "Filter sales from the West region",
    "Plot revenue by product",
    "Find the correlation between units and revenue",
    "Summarise the dataset",
]
cols = st.columns(3, gap="medium")
for i, suggestion in enumerate(suggestions):
    with cols[i % 3]:
        if st.button(suggestion, key=f"suggestion_{i}", use_container_width=True):
            st.session_state.pending_query = suggestion
            st.rerun()

typed_query = st.chat_input("Ask something about your data…")
query = typed_query or st.session_state.pop("pending_query", None)

if query:
    st.session_state.messages.append({"role": "user", "content": query})
    try:
        with st.spinner("Analysing your data…"):
            result = analyse(query, df)
        st.session_state.messages.append({"role": "assistant", "result": result})
    except Exception as exc:
        st.session_state.messages.append({
            "role": "assistant",
            "result": {"type": "message", "data": f"Couldn't complete the analysis: {exc}"},
        })
    st.rerun()
