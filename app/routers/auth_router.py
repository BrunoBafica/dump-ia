from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import auth_service

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse("/dashboard", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


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
            {"request": request, "error": "Usuário ou senha inválidos."},
            status_code=401,
        )
    request.session["user_id"] = user.id
    request.session["username"] = user.username
    return RedirectResponse("/dashboard", status_code=302)


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse("/dashboard", status_code=302)
    return templates.TemplateResponse("register.html", {"request": request, "error": None})


@router.post("/register", response_class=HTMLResponse)
def register_submit(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    db: Session = Depends(get_db),
):
    if password != password_confirm:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "As senhas não coincidem."},
            status_code=400,
        )
    if len(password) < 6:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "A senha deve ter ao menos 6 caracteres."},
            status_code=400,
        )
    if auth_service.get_user_by_username(db, username):
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Nome de usuário já existe."},
            status_code=400,
        )
    if auth_service.get_user_by_email(db, email):
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "E-mail já cadastrado."},
            status_code=400,
        )

    user = auth_service.create_user(db, username, email, password)
    request.session["user_id"] = user.id
    request.session["username"] = user.username
    return RedirectResponse("/dashboard", status_code=302)


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=302)
