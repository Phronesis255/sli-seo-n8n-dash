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

@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_supabase()

@st.cache_data(ttl=600)
def fetch_rows(table_name: str = "Cache"):
    # Returns a list[dict]s
    res = supabase.table(table_name).select("*").execute()
    return res.data

st.subheader("Load rows from Supabase")
if st.button("Load Rows"):
    try:
        rows = fetch_rows("Cache")  # change table name if needed
        df = pd.DataFrame(rows or [])
        if df.empty:
            st.info("No rows found in 'Cache'.")
        else:
            st.caption(f"{len(df)} rows from 'Cache'")
            st.dataframe(df, use_container_width=True)
    except Exception as e:
        st.error(f"Failed to fetch rows: {e}")
