# app.py
import streamlit as st
import requests
from supabase import create_client, Client
import pandas as pd

st.set_page_config(page_title="n8n + Supabase Demo", page_icon="⚡")
st.title("n8n trigger + Supabase table")


WEBHOOK_URL = "https://phr0nesis.app.n8n.cloud/webhook/25d396ce-f3ff-4376-996f-3e26bc73edb2s-test/25d396ce-f3ff-4376-996f-3e26bc73edb2"

username = st.secrets["username"]
password = st.secrets["password"]

st.subheader("Trigger n8n workflow")
st.write("Press the button to call the webhook and run the workflow.")

if st.button("Run workflow"):
    with st.spinner("Triggering workflow..."):
        try:
            # # --- Basic Auth (most common for n8n Webhook Trigger) ---
            # resp = requests.post(
            #     WEBHOOK_URL,
            #     auth=HTTPBasicAuth(username, password),
            #     timeout=20,
            # )

            # --- If you actually used 'Header Auth' in n8n, use this instead:
            resp = requests.post(
                WEBHOOK_URL,
                headers={"streamlit0": st.secrets["password"]},
                timeout=20,
            )

            status = resp.status_code
            st.subheader(f"Response: {status}")

            ctype = resp.headers.get("content-type", "")
            if "application/json" in ctype:
                st.json(resp.json())
            else:
                # Show a small text preview for non-JSON responses
                text = resp.text if resp.text else "(empty body)"
                st.code(text[:4000])  # avoid dumping huge bodies
        except requests.RequestException as e:
            st.error(f"Request failed: {e}")
st.divider()
# app.py
import ast
import json
import requests
import pandas as pd
import streamlit as st
from urllib.parse import urlparse
from supabase import create_client, Client

st.set_page_config(page_title="n8n + Supabase Demo", page_icon="⚡")
st.title("n8n trigger + Supabase table")

WEBHOOK_URL = "https://phr0nesis.app.n8n.cloud/webhook-test/25d396ce-f3ff-4376-996f-3e26bc73edb2"

# ── n8n (Header Auth) ──────────────────────────────────────────────────────────
N8N_HEADER_NAME = "streamlit0"  # fixed per your config
N8N_HEADER_VALUE = st.secrets["password"]

st.subheader("Trigger n8n workflow")
if st.button("Run n8n workflow"):
    with st.spinner("Triggering workflow..."):
        try:
            resp = requests.post(
                WEBHOOK_URL,
                headers={N8N_HEADER_NAME: N8N_HEADER_VALUE},
                timeout=20,
            )
            st.success(f"Webhook called (status {resp.status_code})")
            ctype = resp.headers.get("content-type", "")
            if "application/json" in ctype:
                st.json(resp.json())
            else:
                st.code((resp.text or "(empty body)")[:4000])
        except requests.RequestException as e:
            st.error(f"Request failed: {e}")

# ── Supabase setup ─────────────────────────────────────────────────────────────
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_supabase()

@st.cache_data(ttl=600)
def fetch_rows(table_name: str = "Cache", limit: int = 250):
    # Returns list[dict]
    res = supabase.table(table_name).select("*").limit(limit).execute()
    return res.data or []

# ── JSON helpers (tolerant parser + pretty/flatten/summary) ────────────────────
def parse_jsonish(v):
    """
    Return dict/list if v is JSON or a Python-literal string (single quotes).
    Else return None.
    """
    if isinstance(v, (dict, list)):
        return v
    if isinstance(v, str):
        s = v.strip()
        # 1) Try strict JSON first
        try:
            return json.loads(s)
        except Exception:
            pass
        # 2) Try Python literal (handles single quotes, True/False/None, etc.)
        try:
            obj = ast.literal_eval(s)
            if isinstance(obj, (dict, list)):
                return obj
        except Exception:
            pass
    return None

def pretty_json_text(v, max_chars: int | None = None):
    obj = parse_jsonish(v)
    if obj is not None:
        s = json.dumps(obj, indent=2, ensure_ascii=False)
    else:
        s = str(v)
    if max_chars and len(s) > max_chars:
        return s[:max_chars] + " …"
    return s

def flatten_top_level(df: pd.DataFrame, json_col: str, keys: list[str], sep="."):
    """
    Flatten selected top-level keys from a dict into columns: <json_col>.<key>...
    """
    # Parse each row to dict or {}
    parsed = df[json_col].apply(lambda v: parse_jsonish(v) or {})
    # Normalize all rows
    norm = pd.json_normalize(parsed, sep=sep)
    # Limit to chosen top-level keys (and their nested children)
    if keys:
        keep_cols = [c for c in norm.columns if c.split(sep)[0] in set(keys)]
        norm = norm[keep_cols] if keep_cols else pd.DataFrame(index=norm.index)
    # Prefix columns to avoid collisions
    if not norm.empty:
        norm.columns = [f"{json_col}{sep}{c}" for c in norm.columns]
    base = df.drop(columns=[json_col], errors="ignore").reset_index(drop=True)
    return pd.concat([base, norm.reset_index(drop=True)], axis=1)

def serp_compact_rows(df: pd.DataFrame, json_col: str, topk: int = 5):
    """Return a list of (row_index, small_df) with topk organic results: pos, title, domain."""
    out = []
    for i, v in df[json_col].items():
        obj = parse_jsonish(v)
        if not isinstance(obj, dict):
            continue
        org = obj.get("organic_results") or []
        rows = []
        for r in org[:topk]:
            title = r.get("title")
            link = r.get("link")
            domain = ""
            if link:
                try:
                    domain = urlparse(link).netloc.replace("www.", "")
                except Exception:
                    domain = link
            rows.append({"pos": r.get("position"), "title": title, "domain": domain})
        if rows:
            out.append((i, pd.DataFrame(rows)))
    return out

# ── UI: load + pretty/flatten/summary for Cache.json ──────────────────────────
st.subheader("Load rows from Supabase (Cache)")
row_limit = st.slider("Max rows to fetch", min_value=50, max_value=2000, value=250, step=50)
display_mode = st.radio(
    "JSON display mode",
    ["Pretty JSON", "Flatten selected keys", "Raw table only"],
    index=0,
    horizontal=True,
)
truncate_len = st.number_input("Preview length (chars, pretty mode)", min_value=200, max_value=10000, value=1500, step=100)

if st.button("Load rows"):
    try:
        rows = fetch_rows("Cache", limit=row_limit)
        df = pd.DataFrame(rows)

        if df.empty:
            st.info("No rows found in 'Cache'.")
        else:
            # Ensure expected columns exist
            expected_cols = {"id", "keyword", "fetched_at", "json", "AI_Summary"}
            missing = expected_cols - set(df.columns)
            if missing:
                st.warning(f"Missing columns in result: {', '.join(sorted(missing))}")

            if display_mode == "Raw table only":
                st.dataframe(df, use_container_width=True)

            elif display_mode == "Pretty JSON":
                df_pretty = df.copy()
                if "json" in df_pretty.columns:
                    df_pretty["json"] = df_pretty["json"].apply(lambda v: pretty_json_text(v, max_chars=truncate_len))
                st.dataframe(df_pretty, use_container_width=True)

                with st.expander("Per-row full JSON (untruncated)"):
                    for i, row in df.iterrows():
                        obj = parse_jsonish(row.get("json"))
                        if obj is None:
                            continue
                        with st.expander(f"Row {i} • id={row.get('id')} • keyword={row.get('keyword')}"):
                            st.code(json.dumps(obj, indent=2, ensure_ascii=False))

                with st.expander("Optional: SERP compact summary (top 5 organic)"):
                    compact = serp_compact_rows(df, "json", topk=5)
                    if not compact:
                        st.caption("No organic results found (or JSON not parsed).")
                    else:
                        for i, small_df in compact:
                            row = df.loc[i]
                            st.markdown(f"**Row {i}** • id=`{row.get('id')}` • keyword=`{row.get('keyword')}`")
                            st.dataframe(small_df, use_container_width=True)

            elif display_mode == "Flatten selected keys":
                # Probe top-level keys from first parsable row
                top_keys = []
                for v in df.get("json", []):
                    obj = parse_jsonish(v)
                    if isinstance(obj, dict):
                        top_keys = sorted(list(obj.keys()))
                        break

                sel = st.multiselect(
                    "Choose top-level keys from 'json' to flatten into columns",
                    options=top_keys,
                    default=["search_information", "organic_results"],
                    help="Creates columns like json.search_information.total_results or json.organic_results[0].title (as nested).",
                )
                sep = st.text_input("Key separator for new columns", value=".", help="Used in flattened column names.")
                df_flat = flatten_top_level(df, "json", sel, sep=sep)
                st.dataframe(df_flat, use_container_width=True)

    except Exception as e:
        st.error(f"Failed to fetch or display rows: {e}")
