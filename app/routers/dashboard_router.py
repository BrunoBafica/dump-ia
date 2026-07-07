from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import CERTIFICATIONS, LEVELS, LEVEL_LABELS
from app.dependencies import get_current_user
from app.models.models import User
from app.services.progress_service import get_or_create_progress

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    languages_data = []
    for lang_key, cert in CERTIFICATIONS.items():
        progress = get_or_create_progress(db, user.id, lang_key)
        level_index = LEVELS.index(progress.current_level)
        accuracy = (
            round(100 * progress.total_correct / progress.total_answered)
            if progress.total_answered
            else None
        )
        languages_data.append(
            {
                "key": lang_key,
                "label": cert["label"],
                "cert_name": cert["cert_name"],
                "cert_url": cert["cert_url"],
                "notes": cert["notes"],
                "current_level": progress.current_level,
                "current_level_label": LEVEL_LABELS[progress.current_level],
                "level_index": level_index,
                "total_answered": progress.total_answered,
                "total_correct": progress.total_correct,
                "accuracy": accuracy,
                "last_reasoning": progress.last_evaluation_reasoning,
            }
        )

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "languages": languages_data,
            "levels": LEVELS,
            "level_labels": LEVEL_LABELS,
        },
    )
