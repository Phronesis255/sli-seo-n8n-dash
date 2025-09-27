# app.py
import streamlit as st
import requests
from requests.auth import HTTPBasicAuth
import pandas as pd
from st_supabase_connection import SupabaseConnection

st.set_page_config(page_title="n8n + Supabase Control Panel", page_icon="⚡")
st.title("n8n + Supabase Control Panel")


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

# --- Supabase table viewer ---
st.subheader("Load rows from Supabase")
st.caption("Reads from table `mytable` and renders a data table.")

if st.button("Fetch table rows"):
    with st.spinner("Querying Supabase..."):
        try:
            # Uses credentials from Streamlit secrets (see example below)
            conn = st.connection("supabase", type=SupabaseConnection)
            rows = conn.query("*", table="Cache", ttl="10m").execute()
            data = rows.data or []
            if not data:
                st.info("No rows returned.")
            else:
                df = pd.DataFrame(data)
                st.dataframe(df, use_container_width=True)
        except Exception as e:
            st.error(f"Supabase query failed: {e}")
