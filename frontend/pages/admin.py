import streamlit as st

from frontend.api_client import call
from frontend.components.ui import cards, date, detail_body, filters, go, metrics


def dashboard():
    with st.container(key="hero"):
        st.title("Admin Dashboard")
        st.write("Review campus reports and track their progress.")
        if st.button("View all complaints", icon=":material/list_alt:", type="primary"):
            go("All Complaints")
    data = call("GET", "/admin/dashboard")
    if data is None:
        return
    st.header("Complaint overview")
    metrics(data)
    recent, categories = st.columns([3, 2])
    with recent:
        st.subheader("Recently submitted")
        cards(data["recent"], "Dashboard", show_student=True, empty="No complaints have been submitted yet.")
    with categories:
        st.subheader("Complaints by category")
        st.dataframe(
            [{"Category": name, "Complaints": count} for name, count in data["by_category"].items()],
            hide_index=True, width="stretch",
        )


def complaints():
    st.title("All Complaints")
    records = call("GET", "/admin/complaints", params=filters(show_student=True))
    cards(records, "All Complaints", show_student=True)


def detail():
    complaint_id = st.session_state.get("complaint_id")
    origin = st.session_state.get("detail_origin", "All Complaints")
    if st.button(f"Back to {origin}", icon=":material/arrow_back:", type="tertiary"):
        go(origin)
    record = call("GET", f"/admin/complaints/{complaint_id}")
    if record is None:
        return
    detail_body(record)
    with st.container(border=True, key="form_panel"):
        st.subheader("Submitted by")
        st.text(record["full_name"])
        st.text(f'{record["department"]} · Roll {record["roll_number"]}')
        st.text(record["email"])

    next_status = {"Pending": "In Progress", "In Progress": "Resolved"}.get(record["status"])
    if next_status:
        with st.form(f"status_{complaint_id}_{record['status']}"):
            st.subheader("Update status")
            note = None
            if next_status == "Resolved":
                note = st.text_area("Resolution note (optional)", max_chars=1000)
            if st.form_submit_button(f"Mark as {next_status}", type="primary"):
                data = {"status": next_status, "resolution_note": note}
                if call("PATCH", f"/admin/complaints/{complaint_id}/status", json=data):
                    go("Detail", complaint_id, notice=f"Status updated to {next_status}.")

    if record["history"]:
        st.subheader("Status history")
        for event in record["history"]:
            st.text(f'{event["previous_status"]} → {event["new_status"]} · {date(event["changed_at"])}')


def students():
    st.title("Students")
    with st.form("student_search", border=False):
        first, second = st.columns(2)
        name = first.text_input("Student name", max_chars=100)
        roll = second.text_input("Exact roll number", max_chars=30)
        st.form_submit_button("Search students", icon=":material/search:")
    data = call("GET", "/admin/students", params={"name": name, "roll_number": roll})
    if data is None:
        return
    if not data:
        st.info("No students match your search.")
        return
    st.dataframe(
        [{"Name": row["full_name"], "Roll number": row["roll_number"], "Department": row["department"],
          "Email": row["email"], "Complaints": row["complaint_count"]} for row in data],
        hide_index=True, width="stretch",
    )
