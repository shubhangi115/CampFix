from typing import get_args

from fastapi import APIRouter, Depends

from ..auth import student
from ..database import db
from ..schemas import Status
from .complaints import list_complaints

router = APIRouter(prefix="/dashboard", tags=["Student dashboard"])


def complaint_stats(cursor, student_id=None):
    sql = "SELECT status, COUNT(*) AS count FROM complaints WHERE deleted_at IS NULL"
    values = ()
    if student_id is not None:
        sql += " AND student_id = %s"
        values = (student_id,)
    cursor.execute(sql + " GROUP BY status", values)
    counts = dict.fromkeys(get_args(Status), 0)
    counts.update({row["status"]: row["count"] for row in cursor.fetchall()})
    return {"total": sum(counts.values()), "by_status": counts}


@router.get("/stats")
def stats(user=Depends(student)):
    with db() as cursor:
        return complaint_stats(cursor, user["id"])


@router.get("/recent-complaints")
def recent(user=Depends(student)):
    with db() as cursor:
        return list_complaints(cursor, student_id=user["id"], limit=5)
