"""Weekly report API endpoints."""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlmodel import Session

from lab_manager.api.auth import require_permission
from lab_manager.api.deps import get_db
from lab_manager.services import weekly_report as svc

router = APIRouter(dependencies=[Depends(require_permission("view_analytics"))])


@router.get("/weekly")
def get_weekly_report(
    week_start: Optional[date] = Query(
        None, description="Start of the week (Monday). Defaults to current week."
    ),
    db: Session = Depends(get_db),
):
    """Generate and return a weekly summary report."""
    return svc.generate_weekly_report(db, week_start=week_start)


@router.get("/weekly/pdf")
def get_weekly_report_pdf(
    week_start: Optional[date] = Query(
        None, description="Start of the week (Monday). Defaults to current week."
    ),
    db: Session = Depends(get_db),
):
    """Return weekly report as downloadable JSON (PDF placeholder).

    For now returns JSON with a Content-Disposition header for download.
    Full PDF generation via reportlab can be added in a future iteration.
    """
    report = svc.generate_weekly_report(db, week_start=week_start)
    response = JSONResponse(content=report)
    filename = f"weekly-report-{report['report_period']['week_start']}.json"
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
