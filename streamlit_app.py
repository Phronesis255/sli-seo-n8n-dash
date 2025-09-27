# app.py
import streamlit as st
import requests
from requests.auth import HTTPBasicAuth

st.set_page_config(page_title="Trigger n8n Workflow", page_icon="⚡")
st.title("Trigger n8n Workflow")

WEBHOOK_URL = "https://phr0nesis.app.n8n.cloud/webhook-test/25d396ce-f3ff-4376-996f-3e26bc73edb2"

username = st.secrets["username"]
password = st.secrets["password"]

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
