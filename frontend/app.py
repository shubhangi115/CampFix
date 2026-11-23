"""Run from the project root with python -m streamlit run frontend/app.py."""

import streamlit as st

from frontend.api_client import call
from frontend.components.ui import cap, navbar, notice, theme
from frontend.pages import admin, student

st.set_page_config(page_title="CampFix", page_icon="🎓", layout="wide")


def access():
    mode = st.session_state.get("access", "Student sign-in")
    registering = mode == "Student registration"
    is_admin = mode == "Admin sign-in"
    with st.container(border=True, key="access_panel"):
        st.html(f'<div class="cf-emblem">{cap}</div>')
        st.title("CampFix")
        st.write("Sign in to manage campus complaints." if is_admin else
                 "Create your student account to report campus issues." if registering else
                 "Sign in to report and track campus issues.")
        notice()
        with st.form(mode, border=False):
            data = {}
            if registering:
                data["full_name"] = st.text_input("Full name", max_chars=100)
                data["roll_number"] = st.text_input("College roll number", max_chars=30)
                data["department"] = st.text_input("Academic department", max_chars=100)
            data["email"] = st.text_input("Admin email" if is_admin else "College email", max_chars=150)
            data["password"] = st.text_input("Password", type="password", max_chars=128)
            if registering:
                data["confirm_password"] = st.text_input("Confirm password", type="password", max_chars=128)
                st.caption("Use at least 8 characters.")
            action = "Create student account" if registering else "Sign in as admin" if is_admin else "Sign in"
            if st.form_submit_button(action, type="primary", width="stretch"):
                if not all(value.strip() for value in data.values()):
                    st.error("Complete all required fields.")
                elif registering and (len(data["password"]) < 8 or data["password"] != data["confirm_password"]):
                    st.error("Use at least 8 characters and make sure both passwords match.")
                elif registering:
                    if call("POST", "/auth/student/register", json=data):
                        st.session_state["access"] = "Student sign-in"
                        st.session_state["notice"] = ("success", "Account created. Sign in with your college email.")
                        st.rerun()
                else:
                    role = "admin" if is_admin else "student"
                    result = call("POST", f"/auth/{role}/login", json=data)
                    if result:
                        st.session_state["token"] = result["access_token"]
                        st.rerun()

        with st.container(horizontal=True, horizontal_alignment="center"):
            links = {
                "Student sign-in": "Student sign-in",
                "Student registration": "New student? Register",
                "Admin sign-in": "Admin sign-in",
            }
            for destination, label in links.items():
                if destination != mode and st.button(label, type="tertiary"):
                    st.session_state["access"] = destination
                    st.rerun()


def render():
    theme()
    if not st.session_state.get("token"):
        access()
        return

    user = call("GET", "/auth/me")
    if user is None:
        if st.button("Retry"):
            st.rerun()
        return

    if user["role"] == "admin":
        pages = {
            "Dashboard": admin.dashboard, "All Complaints": admin.complaints,
            "Students": admin.students, "Profile": lambda: student.profile(user),
        }
        landing = "Dashboard"
        extra = {"Detail": admin.detail}
    else:
        pages = {
            "Home": lambda: student.home(user), "Submit Complaint": student.submit,
            "My Complaints": student.complaints, "About": student.about,
            "Profile": lambda: student.profile(user),
        }
        landing = "Home"
        extra = {"Detail": student.detail, "Edit": student.edit}

    selected = navbar(pages, landing)
    notice()
    handlers = {**pages, **extra}
    handlers.get(selected, handlers[landing])()


st.navigation([st.Page(render, title="CampFix", default=True)], position="hidden").run()
