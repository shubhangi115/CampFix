from html import escape

import streamlit as st

from frontend.api_client import call
from frontend.components.ui import cards, complaint_form, detail_body, filters, go, metrics


def home(user):
    with st.container(key="hero"):
        st.html(f'<h1>Welcome, {escape(user["full_name"])}</h1>')
        st.write("Report a campus issue and follow it through to resolution.")
        if st.button("Report an issue", icon=":material/add:", type="primary"):
            go("Submit Complaint")
    st.header("Your complaints")
    stats = call("GET", "/dashboard/stats")
    if stats is not None:
        metrics(stats)
    with st.container(horizontal=True, vertical_alignment="center"):
        st.subheader("Recent complaints")
        if st.button("View my complaints", icon=":material/list_alt:"):
            go("My Complaints")
    cards(
        call("GET", "/dashboard/recent-complaints"), "Home",
        empty="You haven’t submitted any complaints yet.",
    )


def submit():
    st.title("Submit Complaint")
    st.write("Tell us what happened and where on campus you noticed the issue.")
    data = complaint_form()
    if data:
        record = call("POST", "/complaints", json=data)
        if record:
            go("My Complaints", notice=f'{record["reference"]} submitted successfully.')


def complaints():
    st.title("My Complaints")
    if st.button("Report an issue", icon=":material/add:", type="primary"):
        go("Submit Complaint")
    cards(call("GET", "/complaints", params=filters()), "My Complaints")


def detail():
    complaint_id = st.session_state.get("complaint_id")
    origin = st.session_state.get("detail_origin", "My Complaints")
    if st.button(f"Back to {origin}", icon=":material/arrow_back:", type="tertiary"):
        go(origin)
    record = call("GET", f"/complaints/{complaint_id}")
    if record is None:
        return
    detail_body(record)
    if record["status"] == "Pending":
        with st.container(horizontal=True):
            if st.button("Edit complaint", icon=":material/edit:"):
                go("Edit", complaint_id)
            if st.button("Delete complaint", icon=":material/delete:"):
                confirm_delete(complaint_id, record["reference"])


@st.dialog("Delete complaint?")
def confirm_delete(complaint_id, reference):
    st.write(f"This will remove {reference} from your complaints.")
    with st.container(horizontal=True):
        if st.button("Cancel"):
            st.rerun()
        if st.button("Delete", type="primary"):
            if call("DELETE", f"/complaints/{complaint_id}"):
                go("My Complaints", notice=f"{reference} deleted.")


def edit():
    complaint_id = st.session_state.get("complaint_id")
    if st.button("Back to complaint", icon=":material/arrow_back:", type="tertiary"):
        go("Detail", complaint_id)
    record = call("GET", f"/complaints/{complaint_id}")
    if record is None:
        return
    st.title("Edit Complaint")
    if record["status"] != "Pending":
        st.warning("Only pending complaints can be edited.")
        return
    data = complaint_form(record)
    if data and call("PUT", f"/complaints/{complaint_id}", json=data):
        go("Detail", complaint_id, notice="Complaint updated.")


def about():
    st.title("About CampFix")
    st.write(
        "CampFix gives students one place to report campus facilities and service issues "
        "and gives administrators a shared record for following up."
    )
    st.markdown(
        "1. Open **Submit Complaint**, select a category, and describe the issue and its location.\n"
        "2. Find your complaint reference and current status in **My Complaints**.\n"
        "3. Administrators review the report, move it from **Pending** to **In Progress**, "
        "and mark it **Resolved** when the work is complete. Resolution notes appear in the complaint details."
    )
    st.write("Keeping reports, updates, and resolution notes together makes follow-up easier for both students and staff.")


def profile(user):
    st.title("My Profile")
    with st.container(border=True, key="form_panel"):
        if user["role"] == "student":
            for label, field in (("Full name", "full_name"), ("Roll number", "roll_number"),
                                 ("Academic department", "department")):
                st.markdown(f"**{label}**")
                st.text(user[field])
        st.markdown("**Email address**")
        st.text(user["email"])
