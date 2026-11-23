from typing import Annotated, get_args

from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth import admin
from ..database import db
from ..schemas import Category, Status, StatusUpdate
from .complaints import ComplaintId, Search, columns, complaint_record, list_complaints
from .dashboard import complaint_stats

router = APIRouter(prefix="/admin", tags=["Administration"], dependencies=[Depends(admin)])
next_status = {"Pending": "In Progress", "In Progress": "Resolved"}


@router.get("/complaints")
def complaints(search: Search = "", status: Status | None = None, category: Category | None = None,
               department: Annotated[str, Query(max_length=100)] = "",
               roll_number: Annotated[str, Query(max_length=30)] = ""):
    with db() as cursor:
        return list_complaints(
            cursor, search=search, status=status, category=category,
            department=department, roll_number=roll_number,
        )


@router.get("/complaints/{complaint_id}")
def detail(complaint_id: ComplaintId):
    with db() as cursor:
        cursor.execute(
            f"""SELECT {columns}, s.full_name, s.roll_number, s.department, s.email
                FROM complaints c JOIN students s ON s.student_id = c.student_id
                WHERE c.complaint_id = %s AND c.deleted_at IS NULL""",
            (complaint_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise HTTPException(404, "Complaint not found.")
        cursor.execute(
            """SELECT previous_status, new_status, changed_at FROM complaint_history
               WHERE complaint_id = %s ORDER BY history_id""",
            (complaint_id,),
        )
        return {**complaint_record(row), "history": cursor.fetchall()}


@router.patch("/complaints/{complaint_id}/status")
def update_status(complaint_id: ComplaintId, data: StatusUpdate, user=Depends(admin)):
    if data.resolution_note and data.status != "Resolved":
        raise HTTPException(422, "Resolution notes can be added when resolving a complaint.")

    # Lock the same row that students must lock to edit or delete it.
    with db() as cursor:
        cursor.execute(
            "SELECT status FROM complaints WHERE complaint_id = %s AND deleted_at IS NULL FOR UPDATE",
            (complaint_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise HTTPException(404, "Complaint not found.")
        previous = row["status"]
        if next_status.get(previous) != data.status:
            raise HTTPException(409, "Move the complaint from Pending to In Progress, then to Resolved.")
        cursor.execute(
            "UPDATE complaints SET status = %s, resolution_note = %s WHERE complaint_id = %s",
            (data.status, data.resolution_note or None, complaint_id),
        )
        cursor.execute(
            """INSERT INTO complaint_history (complaint_id, admin_id, previous_status, new_status)
               VALUES (%s, %s, %s, %s)""",
            (complaint_id, user["id"], previous, data.status),
        )
    return {"complaint_id": complaint_id, "status": data.status}


@router.get("/students")
def students(name: Annotated[str, Query(max_length=100)] = "",
             roll_number: Annotated[str, Query(max_length=30)] = ""):
    with db() as cursor:
        cursor.execute(
            """SELECT s.student_id, s.full_name, s.roll_number, s.department, s.email,
                      COUNT(c.complaint_id) AS complaint_count
               FROM students s LEFT JOIN complaints c
                   ON c.student_id = s.student_id AND c.deleted_at IS NULL
               WHERE (%s = '' OR LOCATE(%s, s.full_name) > 0)
                 AND (%s = '' OR s.roll_number = %s)
               GROUP BY s.student_id, s.full_name, s.roll_number, s.department, s.email
               ORDER BY s.full_name, s.student_id""",
            (name.strip(), name.strip(), roll_number.strip(), roll_number.strip()),
        )
        return cursor.fetchall()


@router.get("/dashboard")
def dashboard():
    with db() as cursor:
        stats = complaint_stats(cursor)
        recent = list_complaints(cursor, limit=5)
        cursor.execute(
            """SELECT category, COUNT(*) AS count FROM complaints
               WHERE deleted_at IS NULL GROUP BY category"""
        )
        counts = dict.fromkeys(get_args(Category), 0)
        counts.update({row["category"]: row["count"] for row in cursor.fetchall()})
        return {**stats, "by_category": counts, "recent": recent}
