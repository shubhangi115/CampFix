"""Send REST requests from the Streamlit server. Tokens stay in session state."""

import os
from pathlib import Path

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
base_url = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def call(method, path, **kwargs):
    token = st.session_state.get("token")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        response = requests.request(method, f"{base_url}{path}", headers=headers, timeout=8, **kwargs)
    except requests.RequestException:
        st.error("CampFix could not reach the API. Try again in a moment.")
        return None
    if response.status_code == 401 and token:
        st.session_state.clear()
        st.session_state["notice"] = ("warning", "Your session ended. Sign in again to continue.")
        st.rerun()
    if response.ok:
        return True if response.status_code == 204 else response.json()

    try:
        detail = response.json().get("detail")
    except ValueError:
        detail = None
    if isinstance(detail, list):
        for error in detail:
            field = " ".join(str(part) for part in error["loc"][1:]).replace("_", " ").capitalize()
            st.error(f"{field}: {error['msg']}" if field else error["msg"])
    else:
        st.error(detail or "The request failed. Try again.")
    return None
