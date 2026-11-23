"""Shared navigation, complaint cards, counters, and form controls."""

from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from typing import get_args

import streamlit as st

from frontend.api_client import call
from backend.schemas import Category, Status

categories = get_args(Category)
statuses = get_args(Status)
# Simple graduation-cap mark based on the supplied CampFix screenshots.
cap = """<svg aria-hidden="true" width="26" height="26" viewBox="0 0 24 24"
fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"
stroke-linejoin="round" style="vertical-align:middle">
<path d="M2 9l10-6 10 6-10 6-10-6Z M6 12v5l6 4 6-4v-5 M22 9v7"/></svg>"""


def theme():
    css = Path(__file__).with_name("theme.css").read_text(encoding="utf-8")
    st.html(f"<style>{css}</style>")


def go(page, complaint_id=None, notice=None):
    st.session_state["page"] = page
    st.session_state["complaint_id"] = complaint_id
    if notice:
        st.session_state["notice"] = ("success", notice)
    st.rerun()


def navbar(pages, landing):
    current = st.session_state.get("page", landing)
    selected = "My Complaints" if current in ("Detail", "Edit") and landing == "Home" else current
    if current == "Detail" and landing == "Dashboard":
        selected = "All Complaints"
    with st.container(key="navbar", horizontal=True, vertical_alignment="center"):
        st.html(f'<div class="cf-brand">{cap} &nbsp;CampFix</div>')
        for page in pages:
            if st.button(page, type="primary" if selected == page else "tertiary", key=f"nav-{page}"):
                go(page)
        if st.button("Logout", icon=":material/logout:", type="tertiary"):
            if call("POST", "/auth/logout"):
                st.session_state.clear()
                st.session_state["notice"] = ("success", "You signed out.")
                st.rerun()
    return current


def notice():
    message = st.session_state.pop("notice", None)
    if message:
        kind, text = message
        getattr(st, kind)(text)


def badge(status):
    style = status.lower().replace(" ", "-")
    symbol = {"Pending": "◷", "In Progress": "◐", "Resolved": "✓"}[status]
    st.html(f'<span class="cf-badge cf-{style}">{symbol} &nbsp;{escape(status)}</span>')


def date(value):
    submitted = datetime.fromisoformat(value)
    if submitted.tzinfo is None:
        submitted = submitted.replace(tzinfo=timezone.utc)
    india = timezone(timedelta(hours=5, minutes=30), "IST")
    return submitted.astimezone(india).strftime("%d %b %Y · %I:%M %p %Z")


def metrics(data):
    metrics_data = {"Total": data["total"], **data["by_status"]}
    icons = {"Total": "inbox", "Pending": "schedule", "In Progress": "build", "Resolved": "check_circle"}
    with st.container(key="metrics"):
        for column, label in zip(st.columns(4), metrics_data):
            column.metric(f":material/{icons[label]}: {label}", metrics_data[label])


def cards(records, origin, *, show_student=False, empty="No complaints match your filters."):
    if records is None:
        return
    if not records:
        st.info(empty)
        return
    for record in records:
        complaint_id = record["complaint_id"]
        with st.container(border=True, key=f"complaint_card_{origin}_{complaint_id}"):
            details, action = st.columns([4, 1], vertical_alignment="center")
            with details:
                st.html(f'<div class="cf-reference">{escape(record["reference"])}</div>')
                st.html(f'<h3>{escape(record["title"])}</h3>')
                st.text(f'{record["category"]} · {record["location"]}')
                st.caption(date(record["created_at"]))
                description = record["description"]
                st.text(description[:180] + ("…" if len(description) > 180 else ""))
                if show_student:
                    st.text(f'{record["department"]} · Roll {record["roll_number"]}')
            with action:
                badge(record["status"])
                if st.button("View details", key=f"details-{origin}-{complaint_id}"):
                    st.session_state["detail_origin"] = origin
                    go("Detail", complaint_id)


def filters(show_student=False):
    with st.form("complaint_filters", border=False):
        search, status, category = st.columns([2, 1, 1])
        params = {
            "search": search.text_input("Search complaints", placeholder="Complaint ID or title", max_chars=200),
            "status": status.selectbox("Status", [None, *statuses], format_func=lambda x: x or "All statuses"),
            "category": category.selectbox("Category", [None, *categories], format_func=lambda x: x or "All categories"),
        }
        if show_student:
            department, roll = st.columns(2)
            params["department"] = department.text_input("Department", max_chars=100)
            params["roll_number"] = roll.text_input("Exact roll number", max_chars=30)
        st.form_submit_button("Apply filters", icon=":material/filter_list:")
    return {key: value for key, value in params.items() if value}


def complaint_form(record=None):
    editing = record is not None
    record = record or {}
    with st.form(f"complaint_form_{record.get('complaint_id', 'new')}", border=True):
        title = st.text_input("Complaint title", value=record.get("title", ""), max_chars=200)
        current = categories.index(record["category"]) if editing else None
        category = st.selectbox("Complaint category", categories, index=current, placeholder="Choose a category")
        location = st.text_input("Campus location", value=record.get("location", ""), max_chars=200)
        description = st.text_area("Complaint description", value=record.get("description", ""), max_chars=4000)
        if st.form_submit_button("Save changes" if editing else "Submit complaint", type="primary"):
            if not all([title.strip(), category, location.strip(), description.strip()]):
                st.error("Enter a title, category, campus location, and description.")
                return None
            return {"title": title, "category": category, "location": location, "description": description}
    return None


def detail_body(record):
    st.caption(record["reference"])
    st.html(f'<h1>{escape(record["title"])}</h1>')
    badge(record["status"])
    st.text(f'{record["category"]} · {record["location"]}')
    st.caption(f'Submitted {date(record["created_at"])}')
    st.subheader("Description")
    st.text(record["description"])
    if record["resolution_note"]:
        st.subheader("Resolution note")
        st.text(record["resolution_note"])
