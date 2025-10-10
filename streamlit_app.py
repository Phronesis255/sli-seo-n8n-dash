# app.py
import ast
import json
import requests
import pandas as pd
import streamlit as st
from urllib.parse import urlparse
from supabase import create_client, Client
import os
import time
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity


st.set_page_config(page_title="n8n + Supabase Demo", page_icon="⚡")
st.title("n8n trigger + Supabase table")


WEBHOOK_URL = "https://phr0nesis.app.n8n.cloud/webhook/25d396ce-f3ff-4376-996f-3e26bc73edb2s-test/25d396ce-f3ff-4376-996f-3e26bc73edb2"

username = st.secrets["username"]
password = st.secrets["password"]

st.subheader("Trigger n8n workflow")
st.write("Press the button to call the webhook and run the workflow.")

# if st.button("Run workflow"):
#     with st.spinner("Triggering workflow..."):
#         try:
#             # # --- Basic Auth (most common for n8n Webhook Trigger) ---
#             # resp = requests.post(
#             #     WEBHOOK_URL,
#             #     auth=HTTPBasicAuth(username, password),
#             #     timeout=20,
#             # )

#             # --- If you actually used 'Header Auth' in n8n, use this instead:
#             resp = requests.post(
#                 WEBHOOK_URL,
#                 headers={"streamlit0": st.secrets["password"]},
#                 timeout=20,
#             )

#             status = resp.status_code
#             st.subheader(f"Response: {status}")

#             ctype = resp.headers.get("content-type", "")
#             if "application/json" in ctype:
#                 st.json(resp.json())
#             else:
#                 # Show a small text preview for non-JSON responses
#                 text = resp.text if resp.text else "(empty body)"
#                 st.code(text[:4000])  # avoid dumping huge bodies
#         except requests.RequestException as e:
#             st.error(f"Request failed: {e}")
# st.divider()
# # app.py
from supabase import create_client, Client

st.set_page_config(page_title="n8n + Supabase Demo", page_icon="⚡")
st.title("n8n trigger + Supabase table")

WEBHOOK_URL = "https://phr0nesis.app.n8n.cloud/webhook/25d396ce-f3ff-4376-996f-3e26bc73edb2"

# ── n8n (Header Auth) ──────────────────────────────────────────────────────────
N8N_HEADER_NAME = "streamlit0"  # fixed per your config
N8N_HEADER_VALUE = st.secrets["password"]

# st.subheader("Trigger n8n workflow")
# if st.button("Run n8n workflow"):
#     with st.spinner("Triggering workflow..."):
#         try:
#             resp = requests.post(
#                 WEBHOOK_URL,
#                 headers={N8N_HEADER_NAME: N8N_HEADER_VALUE},
#                 timeout=20,
#             )
#             st.success(f"Webhook called (status {resp.status_code})")
#             ctype = resp.headers.get("content-type", "")
#             if "application/json" in ctype:
#                 st.json(resp.json())
#             else:
#                 st.code((resp.text or "(empty body)")[:4000])
#         except requests.RequestException as e:
#             st.error(f"Request failed: {e}")

# st.divider()
# ── Supabase setup ─────────────────────────────────────────────────────────────
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_supabase()

@st.cache_data(ttl=600, show_spinner=False)
def fetch_cache(limit: int = 200, keyword_query: str | None = None):
    q = supabase.table("Cache").select("id, keyword, fetched_at, json, AI_Summary").order("fetched_at", desc=True)
    if keyword_query:
        # ilike -> case-insensitive contains; adjust if you use a different operator
        q = q.ilike("keyword", f"%{keyword_query}%")
    res = q.limit(limit).execute()
    return res.data or []

# ── Parsing helpers ────────────────────────────────────────────────────────────
def parse_jsonish(v):
    """Try JSON first, then Python literal (handles single quotes)."""
    if isinstance(v, (dict, list)):
        return v
    if isinstance(v, str):
        s = v.strip()
        try:
            return json.loads(s)
        except Exception:
            pass
        try:
            obj = ast.literal_eval(s)
            if isinstance(obj, (dict, list)):
                return obj
        except Exception:
            pass
    return None

def extract_domain(url: str | None) -> str:
    if not url:
        return ""
    try:
        netloc = urlparse(url).netloc
        return netloc[4:] if netloc.startswith("www.") else netloc
    except Exception:
        return url or ""

def build_serp_table(serp_obj: dict, topk: int = 5) -> pd.DataFrame:
    """Return DataFrame with rank, title, domain, snippet for topk organic results."""
    rows = []
    for item in (serp_obj or {}).get("organic_results", [])[:topk]:
        rows.append({
            "rank": item.get("position"),
            "title": item.get("title"),
            "domain": extract_domain(item.get("link")),
            "snippet": item.get("snippet"),
        })
    return pd.DataFrame(rows)

def get_ai_summary_bits(ai_summary_val):
    """Return (summary_100w:str|None, top_competitor_topics:list[str]|None)."""
    obj = parse_jsonish(ai_summary_val)
    if not isinstance(obj, dict):
        return None, None
    return obj.get("summary_100w"), obj.get("top_competitor_topics")

# ── Controls ───────────────────────────────────────────────────────────────────
col_a, col_b, col_c = st.columns([2, 1, 1])
with col_a:
    kw = st.text_input("Filter by keyword (optional)", placeholder="e.g., prompt engineering")
with col_b:
    limit = st.slider("Max rows", 50, 1000, 200, 50)
with col_c:
    topk = st.slider("Top K organic", 3, 10, 5, 1)

if st.button("Load summaries", type="primary", use_container_width=True):
    rows = fetch_cache(limit=limit, keyword_query=kw.strip() or None)
    if not rows:
        st.info("No rows found.")
    else:
        for row in rows:
            serp = parse_jsonish(row.get("json"))
            df = build_serp_table(serp if isinstance(serp, dict) else {}, topk=topk)

            summary_100w, topics = get_ai_summary_bits(row.get("AI_Summary"))

            with st.container(border=True):
                # Header line
                st.markdown(
                    f"**Keyword:** `{row.get('keyword')}` &nbsp;&nbsp; "
                    f"**Fetched:** `{row.get('fetched_at')}` &nbsp;&nbsp; "
                    f"**ID:** `{row.get('id')}`"
                )

                # AI summary + topics
                if summary_100w or topics:
                    c1, c2 = st.columns([3, 2], vertical_alignment="top")
                    with c1:
                        if summary_100w:
                            st.markdown("**AI Summary (≈100w)**")
                            st.write(summary_100w)
                    with c2:
                        if topics:
                            st.markdown("**Top competitor topics**")
                            # Small tag-like list
                            for t in topics:
                                st.markdown(f"- {t}")
                else:
                    st.caption("No AI_Summary available for this row.")

                # SERP compact table
                if not df.empty:
                    st.markdown("**Top results (compact)**")
                    st.dataframe(df, use_container_width=True, hide_index=True)
                else:
                    st.caption("No organic results found in SERP payload.")

        st.success(f"Rendered {len(rows)} row(s).")

# ── Keyword Research Workflow ─────────────────────────────────────────────────
def perform_analysis(keyword):
    """Perform keyword research analysis."""
    if 'words_to_check' not in st.session_state:
        st.session_state['words_to_check'] = []

    start_time = time.time()
    user_email = st.session_state.get("username", "guest")

    status_placeholder = st.empty()
    status_placeholder.info('Retrieving top search results...')
    st.write(f"Keyword: {keyword}")

    st.session_state['keyword'] = keyword
    st.session_state['serp_contents'] = []

    api_key = os.getenv("API_KEY")
    cse_id = os.getenv("CSE_ID")
    st.write(f"API Key: {api_key}, CSE ID: {cse_id}")

    # Simulate retrieving search results (replace with actual implementation)
    results = [{"link": f"https://example.com/{i}"} for i in range(1, 6)]
    st.write(f"Search results: {results}")
    if not results:
        status_placeholder.error('No results found.')
        return

    top_urls = [item['link'] for item in results if 'link' in item]
    st.write(f"Top URLs: {top_urls}")
    if not top_urls:
        status_placeholder.error('No URLs found.')
        return
    st.session_state['top_urls'] = top_urls

    # Simulate content extraction (replace with actual implementation)
    retrieved_content = ["Sample content from URL"] * len(top_urls)
    st.session_state['serp_contents'] = [{"url": url, "content": content} for url, content in zip(top_urls, retrieved_content)]

    # Simulate TF-IDF analysis (replace with actual implementation)
    terms = ["term1", "term2", "term3"]
    scores = [0.8, 0.6, 0.4]
    st.session_state['chart_data'] = pd.DataFrame({
        'Terms': terms,
        'Scores': scores
    })

    st.success(f"Analysis completed for keyword: {keyword}")
    elapsed_time = time.time() - start_time
    st.write(f"Time taken: {elapsed_time:.2f} seconds")

# ── Add Keyword Research Section ──────────────────────────────────────────────
st.subheader("Keyword Research Workflow")
keyword = st.text_input("Enter a keyword for research", placeholder="e.g., AI tools")
if st.button("Analyze Keyword"):
    if keyword.strip():
        perform_analysis(keyword.strip())
    else:
        st.error("Please enter a valid keyword.")

# Display analysis results
if 'chart_data' in st.session_state:
    st.subheader("Keyword Analysis Results")
    st.dataframe(st.session_state['chart_data'], use_container_width=True)
