from fastapi import APIRouter, Request, Depends, Form, BackgroundTasks
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.models import User
from app.services import auth_service, email_service

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _send_verification_email_safe(email: str, username: str, token: str) -> None:
    """Roda em background; se o SMTP falhar, não derruba o cadastro do usuário."""
    try:
        verify_url = f"{settings.APP_BASE_URL}/verify-email/{token}"
        email_service.send_verification_email(email, username, verify_url)
    except Exception:
        pass  # usuário ainda pode pedir reenvio depois, em "Minha conta"


def _send_reset_code_email_safe(email: str, username: str, code: str) -> None:
    try:
        email_service.send_password_reset_code_email(email, username, code)
    except Exception:
        pass


def _send_temp_password_email_safe(email: str, username: str, temp_password: str) -> None:
    try:
        login_url = f"{settings.APP_BASE_URL}/login"
        email_service.send_temp_password_email(email, username, temp_password, login_url)
    except Exception:
        pass


# --------------------------------------------------------------------------
# Login / logout
# --------------------------------------------------------------------------

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse("/dashboard", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": None, "info": None})


@router.post("/login", response_class=HTMLResponse)
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = auth_service.authenticate_user(db, username, password)
    if not user:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Usuário ou senha inválidos.", "info": None},
            status_code=401,
        )
    request.session["user_id"] = user.id
    request.session["username"] = user.username
    request.session["is_admin"] = user.is_admin
    return RedirectResponse("/dashboard", status_code=302)


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=302)


# --------------------------------------------------------------------------
# Cadastro + confirmação de e-mail
# --------------------------------------------------------------------------

@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse("/dashboard", status_code=302)
    return templates.TemplateResponse(
        "register.html",
        {"request": request, "error": None, "email_configured": settings.EMAIL_CONFIGURED},
    )


@router.post("/register", response_class=HTMLResponse)
def register_submit(
    request: Request,
    background_tasks: BackgroundTasks,
    username: str = Form(...),
    email: str = Form(...),
    phone_number: str = Form(""),
    password: str = Form(...),
    password_confirm: str = Form(...),
    db: Session = Depends(get_db),
):
    if password != password_confirm:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "As senhas não coincidem.", "email_configured": settings.EMAIL_CONFIGURED},
            status_code=400,
        )
    if len(password) < 6:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "A senha deve ter ao menos 6 caracteres.", "email_configured": settings.EMAIL_CONFIGURED},
            status_code=400,
        )
    if auth_service.get_user_by_username(db, username):
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Nome de usuário já existe.", "email_configured": settings.EMAIL_CONFIGURED},
            status_code=400,
        )
    if auth_service.get_user_by_email(db, email):
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "E-mail já cadastrado.", "email_configured": settings.EMAIL_CONFIGURED},
            status_code=400,
        )

    user = auth_service.create_user(db, username, email, password, phone_number.strip() or None)

    # Só tenta gerar/enviar a confirmação se o SMTP estiver de fato configurado.
    # Sem isso, o token ficaria pendente para sempre e o e-mail nunca chegaria —
    # melhor deixar claro (banner no dashboard) do que fingir que foi enviado.
    if settings.EMAIL_CONFIGURED:
        token = auth_service.create_email_verification(db, user)
        background_tasks.add_task(_send_verification_email_safe, user.email, user.username, token)

    request.session["user_id"] = user.id
    request.session["username"] = user.username
    request.session["is_admin"] = user.is_admin
    return RedirectResponse("/dashboard", status_code=302)


@router.get("/verify-email/{token}", response_class=HTMLResponse)
def verify_email(request: Request, token: str, db: Session = Depends(get_db)):
    ok = auth_service.confirm_email_token(db, token)
    return templates.TemplateResponse(
        "verify_email_result.html",
        {"request": request, "success": ok},
    )


@router.post("/account/resend-verification")
def resend_verification(
    request: Request,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not user.email_verified and settings.EMAIL_CONFIGURED:
        token = auth_service.create_email_verification(db, user)
        background_tasks.add_task(_send_verification_email_safe, user.email, user.username, token)
    return RedirectResponse("/dashboard", status_code=302)


# --------------------------------------------------------------------------
# Esqueci minha senha (2 passos: código por e-mail -> senha temporária)
# --------------------------------------------------------------------------
#
# IMPORTANTE: esse fluxo depende inteiramente de conseguir enviar e-mail.
# Se o SMTP não estiver configurado, NÃO fingimos que o código foi enviado —
# isso seria enganoso (o usuário ficaria esperando um e-mail que nunca chega)
# e inseguro (daria a falsa sensação de que a recuperação está funcionando).
# Em vez disso, bloqueamos o fluxo com uma mensagem clara.

@router.get("/forgot-password", response_class=HTMLResponse)
def forgot_password_page(request: Request):
    if not settings.EMAIL_CONFIGURED:
        return templates.TemplateResponse(
            "forgot_password.html",
            {"request": request, "error": None, "blocked": True},
        )
    return templates.TemplateResponse(
        "forgot_password.html", {"request": request, "error": None, "blocked": False}
    )


@router.post("/forgot-password", response_class=HTMLResponse)
def forgot_password_submit(
    request: Request,
    background_tasks: BackgroundTasks,
    username_or_email: str = Form(...),
    db: Session = Depends(get_db),
):
    if not settings.EMAIL_CONFIGURED:
        return templates.TemplateResponse(
            "forgot_password.html",
            {"request": request, "error": None, "blocked": True},
            status_code=503,
        )

    user = auth_service.get_user_by_username(db, username_or_email) or \
        auth_service.get_user_by_email(db, username_or_email)

    # Por segurança, não revelamos se o usuário existe ou não — a tela
    # seguinte é a mesma em ambos os casos.
    if user:
        code = auth_service.create_password_reset_code(db, user)
        background_tasks.add_task(_send_reset_code_email_safe, user.email, user.username, code)
        request.session["reset_user_id"] = user.id

    return templates.TemplateResponse(
        "forgot_password_verify.html", {"request": request, "error": None}
    )


@router.post("/forgot-password/verify", response_class=HTMLResponse)
def forgot_password_verify(
    request: Request,
    background_tasks: BackgroundTasks,
    code: str = Form(...),
    db: Session = Depends(get_db),
):
    user_id = request.session.get("reset_user_id")
    user = db.query(User).filter(User.id == user_id).first() if user_id else None

    if not settings.EMAIL_CONFIGURED:
        return templates.TemplateResponse(
            "forgot_password.html",
            {"request": request, "error": None, "blocked": True},
            status_code=503,
        )

    if not user or not auth_service.verify_password_reset_code(db, user, code):
        return templates.TemplateResponse(
            "forgot_password_verify.html",
            {"request": request, "error": "Código inválido ou expirado. Tente pedir um novo."},
            status_code=400,
        )

    temp_password = auth_service.reset_password_with_temp(db, user)
    background_tasks.add_task(
        _send_temp_password_email_safe, user.email, user.username, temp_password
    )
    request.session.pop("reset_user_id", None)

    return templates.TemplateResponse("forgot_password_done.html", {"request": request})


# --------------------------------------------------------------------------
# Minha conta: troca de senha
# --------------------------------------------------------------------------

@router.get("/account/change-password", response_class=HTMLResponse)
def change_password_page(
    request: Request,
    user: User = Depends(get_current_user),
):
    return templates.TemplateResponse(
        "change_password.html",
        {
            "request": request,
            "user": user,
            "pw_error": None,
            "pw_success": False,
            "profile_error": None,
            "profile_success": False,
        },
    )


@router.post("/account/update-profile", response_class=HTMLResponse)
def update_profile_submit(
    request: Request,
    background_tasks: BackgroundTasks,
    username: str = Form(...),
    email: str = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    email_changed = email.strip().lower() != user.email.lower()

    error = auth_service.update_user_credentials(db, user, new_username=username, new_email=email)

    if error:
        return templates.TemplateResponse(
            "change_password.html",
            {
                "request": request,
                "user": user,
                "pw_error": None,
                "pw_success": False,
                "profile_error": error,
                "profile_success": False,
            },
            status_code=400,
        )

    # Nome de usuário na sessão pode ter mudado — atualiza pra refletir na topbar
    request.session["username"] = user.username

    # Se o e-mail mudou, precisa confirmar de novo (update_user_credentials já
    # marcou email_verified=False) — dispara um novo e-mail de confirmação.
    if email_changed and settings.EMAIL_CONFIGURED:
        token = auth_service.create_email_verification(db, user)
        background_tasks.add_task(_send_verification_email_safe, user.email, user.username, token)

    return templates.TemplateResponse(
        "change_password.html",
        {
            "request": request,
            "user": user,
            "pw_error": None,
            "pw_success": False,
            "profile_error": None,
            "profile_success": True,
        },
    )


@router.post("/account/change-password", response_class=HTMLResponse)
def change_password_submit(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    new_password_confirm: str = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not auth_service.verify_password(current_password, user.password_hash):
        return templates.TemplateResponse(
            "change_password.html",
            {
                "request": request,
                "user": user,
                "pw_error": "Senha atual incorreta.",
                "pw_success": False,
                "profile_error": None,
                "profile_success": False,
            },
            status_code=400,
        )
    if new_password != new_password_confirm:
        return templates.TemplateResponse(
            "change_password.html",
            {
                "request": request,
                "user": user,
                "pw_error": "As senhas novas não coincidem.",
                "pw_success": False,
                "profile_error": None,
                "profile_success": False,
            },
            status_code=400,
        )
    if len(new_password) < 6:
        return templates.TemplateResponse(
            "change_password.html",
            {
                "request": request,
                "user": user,
                "pw_error": "A senha deve ter ao menos 6 caracteres.",
                "pw_success": False,
                "profile_error": None,
                "profile_success": False,
            },
            status_code=400,
        )

    auth_service.change_password(db, user, new_password)
    return templates.TemplateResponse(
        "change_password.html",
        {
            "request": request,
            "user": user,
            "pw_error": None,
            "pw_success": True,
            "profile_error": None,
            "profile_success": False,
        },
    )
