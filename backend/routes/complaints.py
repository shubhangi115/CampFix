"""Complaint queries shared by student and administrator pages."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from ..auth import student
from ..database import db
from ..schemas import Category, ComplaintInput, Status

router = APIRouter(prefix="/complaints", tags=["Student complaints"])
ComplaintId = Annotated[int, Path(gt=0, le=2147483647)]
Search = Annotated[str, Query(max_length=200)]
columns = """
    c.complaint_id, c.title, c.category, c.description, c.location,
    c.status, c.resolution_note, c.created_at, c.updated_at
"""


def complaint_record(row):
    return {**row, "reference": f"CMP-{row['complaint_id']:04d}"}


def list_complaints(cursor, *, student_id=None, search="", status=None, category=None,
                    department="", roll_number="", limit=None):
    fields = columns
    source = "FROM complaints c"
    conditions = ["c.deleted_at IS NULL"]
    values = []
    if student_id is None:
        fields += ", s.full_name, s.roll_number, s.department, s.email"
        source += " JOIN students s ON s.student_id = c.student_id"
        if department.strip():
            conditions.append("LOCATE(%s, s.department) > 0")
            values.append(department.strip())
        if roll_number.strip():
            conditions.append("s.roll_number = %s")
            values.append(roll_number.strip())
    else:
        conditions.append("c.student_id = %s")
        values.append(student_id)
    if search.strip():
        conditions.append(
            """(LOCATE(%s, c.title) > 0 OR
                LOCATE(%s, CONCAT('CMP-', LPAD(c.complaint_id,
                    GREATEST(4, CHAR_LENGTH(c.complaint_id)), '0'))) > 0)"""
        )
        values.extend([search.strip(), search.strip().upper()])
    if status:
        conditions.append("c.status = %s")
        values.append(status)
    if category:
        conditions.append("c.category = %s")
        values.append(category)

    sql = f"SELECT {fields} {source} WHERE " + " AND ".join(conditions)
    sql += " ORDER BY c.created_at DESC, c.complaint_id DESC"
    if limit is not None:
        sql += " LIMIT %s"
        values.append(limit)
    cursor.execute(sql, tuple(values))
    return [complaint_record(row) for row in cursor.fetchall()]


def owned_complaint(cursor, complaint_id, student_id, *, lock=False):
    sql = f"""SELECT {columns} FROM complaints c
              WHERE c.complaint_id = %s AND c.student_id = %s AND c.deleted_at IS NULL"""
    if lock:
        sql += " FOR UPDATE"
    cursor.execute(sql, (complaint_id, student_id))
    row = cursor.fetchone()
    if row is None:
        raise HTTPException(404, "Complaint not found.")
    return complaint_record(row)


def require_pending(row):
    if row["status"] != "Pending":
        raise HTTPException(409, "Only pending complaints can be edited or deleted.")


@router.post("", status_code=201)
def create(data: ComplaintInput, user=Depends(student)):
    with db() as cursor:
        cursor.execute(
            """INSERT INTO complaints (student_id, title, category, description, location)
               VALUES (%s, %s, %s, %s, %s)""",
            (user["id"], data.title, data.category, data.description, data.location),
        )
        return owned_complaint(cursor, cursor.lastrowid, user["id"])


@router.get("")
def list_own(search: Search = "", status: Status | None = None,
             category: Category | None = None, user=Depends(student)):
    with db() as cursor:
        return list_complaints(
            cursor, student_id=user["id"], search=search, status=status, category=category,
        )


@router.get("/{complaint_id}")
def detail(complaint_id: ComplaintId, user=Depends(student)):
    with db() as cursor:
        return owned_complaint(cursor, complaint_id, user["id"])


@router.put("/{complaint_id}")
def update(complaint_id: ComplaintId, data: ComplaintInput, user=Depends(student)):
    with db() as cursor:
        require_pending(owned_complaint(cursor, complaint_id, user["id"], lock=True))
        cursor.execute(
            """UPDATE complaints SET title = %s, category = %s, description = %s, location = %s
               WHERE complaint_id = %s""",
            (data.title, data.category, data.description, data.location, complaint_id),
        )
        return owned_complaint(cursor, complaint_id, user["id"])


@router.delete("/{complaint_id}", status_code=204)
def delete(complaint_id: ComplaintId, user=Depends(student)):
    with db() as cursor:
        require_pending(owned_complaint(cursor, complaint_id, user["id"], lock=True))
        cursor.execute(
            "UPDATE complaints SET deleted_at = CURRENT_TIMESTAMP WHERE complaint_id = %s",
            (complaint_id,),
        )
