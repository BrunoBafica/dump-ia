from fastapi import APIRouter, Request, Depends, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings, CERTIFICATIONS, LEVELS, LEVEL_LABELS
from app.database import get_db
from app.dependencies import get_current_admin
from app.models.models import User, UserProgress, QuestionLog
from app.services import auth_service, email_service

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory="app/templates")


def _send_temp_password_email_safe(email: str, username: str, temp_password: str) -> None:
    try:
        login_url = f"{settings.APP_BASE_URL}/login"
        email_service.send_temp_password_email(email, username, temp_password, login_url)
    except Exception:
        pass


@router.get("", response_class=HTMLResponse)
def admin_users_list(
    request: Request,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    users = db.query(User).order_by(User.created_at.desc()).all()

    rows = []
    for u in users:
        total_answered = sum(p.total_answered for p in u.progress_entries)
        rows.append({
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "phone_number": u.phone_number,
            "email_verified": u.email_verified,
            "is_admin": u.is_admin,
            "must_change_password": u.must_change_password,
            "created_at": u.created_at,
            "total_answered": total_answered,
        })

    return templates.TemplateResponse(
        "admin_users.html",
        {"request": request, "admin": admin, "users": rows},
    )


@router.get("/users/{user_id}", response_class=HTMLResponse)
def admin_user_detail(
    request: Request,
    user_id: int,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return RedirectResponse("/admin", status_code=302)

    progress_by_lang = {p.language: p for p in user.progress_entries}
    languages_data = []
    for lang_key, cert in CERTIFICATIONS.items():
        p = progress_by_lang.get(lang_key)
        languages_data.append({
            "key": lang_key,
            "label": cert["label"],
            "current_level_label": LEVEL_LABELS[p.current_level] if p else LEVEL_LABELS["trainee"],
            "total_answered": p.total_answered if p else 0,
            "total_correct": p.total_correct if p else 0,
            "last_reasoning": p.last_evaluation_reasoning if p else None,
        })

    recent_logs = (
        db.query(QuestionLog)
        .filter(QuestionLog.user_id == user.id)
        .order_by(QuestionLog.created_at.desc())
        .limit(15)
        .all()
    )

    # Mensagem "flash" de uma senha temporária recém-gerada (mostrada uma única vez)
    flashed_temp_password = request.session.pop(f"admin_temp_pw_{user.id}", None)
    flashed_temp_password_emailed = request.session.pop(f"admin_temp_pw_emailed_{user.id}", None)

    return templates.TemplateResponse(
        "admin_user_detail.html",
        {
            "request": request,
            "admin": admin,
            "user": user,
            "languages": languages_data,
            "recent_logs": recent_logs,
            "error": None,
            "success": None,
            "flashed_temp_password": flashed_temp_password,
            "flashed_temp_password_emailed": flashed_temp_password_emailed,
            "email_configured": settings.EMAIL_CONFIGURED,
        },
    )


@router.post("/users/{user_id}/update", response_class=HTMLResponse)
def admin_update_user(
    request: Request,
    user_id: int,
    username: str = Form(...),
    email: str = Form(...),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return RedirectResponse("/admin", status_code=302)

    error = auth_service.update_user_credentials(db, user, new_username=username, new_email=email)

    if error:
        # Recarrega a tela de detalhe com a mensagem de erro, sem perder o resto do contexto
        progress_by_lang = {p.language: p for p in user.progress_entries}
        languages_data = []
        for lang_key, cert in CERTIFICATIONS.items():
            p = progress_by_lang.get(lang_key)
            languages_data.append({
                "key": lang_key,
                "label": cert["label"],
                "current_level_label": LEVEL_LABELS[p.current_level] if p else LEVEL_LABELS["trainee"],
                "total_answered": p.total_answered if p else 0,
                "total_correct": p.total_correct if p else 0,
                "last_reasoning": p.last_evaluation_reasoning if p else None,
            })
        recent_logs = (
            db.query(QuestionLog)
            .filter(QuestionLog.user_id == user.id)
            .order_by(QuestionLog.created_at.desc())
            .limit(15)
            .all()
        )
        return templates.TemplateResponse(
            "admin_user_detail.html",
            {
                "request": request,
                "admin": admin,
                "user": user,
                "languages": languages_data,
                "recent_logs": recent_logs,
                "error": error,
                "success": None,
                "flashed_temp_password": None,
                "flashed_temp_password_emailed": None,
                "email_configured": settings.EMAIL_CONFIGURED,
            },
            status_code=400,
        )

    return RedirectResponse(f"/admin/users/{user_id}", status_code=302)


@router.post("/users/{user_id}/reset-password")
def admin_reset_password(
    request: Request,
    user_id: int,
    background_tasks: BackgroundTasks,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return RedirectResponse("/admin", status_code=302)

    temp_password = auth_service.reset_password_with_temp(db, user)

    if settings.EMAIL_CONFIGURED:
        background_tasks.add_task(
            _send_temp_password_email_safe, user.email, user.username, temp_password
        )
        request.session[f"admin_temp_pw_emailed_{user.id}"] = True
    else:
        # Sem SMTP configurado: não fingimos que foi enviado — mostramos a senha
        # temporária diretamente pro admin repassar manualmente (uma única vez).
        request.session[f"admin_temp_pw_{user.id}"] = temp_password
        request.session[f"admin_temp_pw_emailed_{user.id}"] = False

    return RedirectResponse(f"/admin/users/{user_id}", status_code=302)
