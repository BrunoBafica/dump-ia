from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.database import Base, engine, run_lightweight_migrations, SessionLocal
from app.dependencies import NotAuthenticatedError, MustChangePasswordError, NotAdminError
from app.routers import auth_router, dashboard_router, quiz_router, admin_router
from app.services.auth_service import seed_default_admin

# Cria as tabelas do banco de dados, se ainda não existirem
Base.metadata.create_all(bind=engine)
# Adiciona colunas novas em bancos já existentes (sem apagar dados salvos)
run_lightweight_migrations()

# Cria o usuário admin/admin na primeira execução (idempotente — não recria
# se já existir algum admin). A senha É admin/admin, como solicitado, mas a
# troca é OBRIGATÓRIA no primeiro login (ver MustChangePasswordError abaixo).
_db = SessionLocal()
try:
    seed_default_admin(_db)
finally:
    _db.close()

if not settings.EMAIL_CONFIGURED:
    print(
        "\n"
        "=====================================================================\n"
        "  ⚠️  AVISO: SMTP não configurado (SMTP_HOST/SMTP_USER/SMTP_PASSWORD)\n"
        "  Confirmação de cadastro: os usuários não receberão o e-mail.\n"
        "  Recuperação de senha: fica BLOQUEADA até configurar o SMTP no .env.\n"
        "  Veja o README.md, seção 'Configurando o envio de e-mails'.\n"
        "=====================================================================\n"
    )

print(
    "\n"
    "=====================================================================\n"
    "  🔑 Painel admin: usuário 'admin', senha 'admin' (troca obrigatória\n"
    "     no primeiro login). Acesse em /admin depois de entrar.\n"
    "=====================================================================\n"
)

app = FastAPI(title="DumpAI - Plataforma de Estudo para Certificações")

app.add_middleware(SessionMiddleware, secret_key=settings.SESSION_SECRET)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(auth_router.router)
app.include_router(dashboard_router.router)
app.include_router(quiz_router.router)
app.include_router(admin_router.router)


@app.exception_handler(NotAuthenticatedError)
def not_authenticated_handler(request: Request, exc: NotAuthenticatedError):
    """
    Em vez de devolver um 401 em JSON cru, manda o usuário de volta para o
    login (sua sessão expirou ou nunca existiu).
    """
    return RedirectResponse("/login", status_code=302)


@app.exception_handler(MustChangePasswordError)
def must_change_password_handler(request: Request, exc: MustChangePasswordError):
    """Conta com senha temporária/admin padrão: obriga trocar antes de mais nada."""
    return RedirectResponse("/account/change-password", status_code=302)


@app.exception_handler(NotAdminError)
def not_admin_handler(request: Request, exc: NotAdminError):
    """Usuário logado, mas sem permissão de admin — manda para o dashboard normal."""
    return RedirectResponse("/dashboard", status_code=302)


@app.get("/")
def root(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse("/dashboard", status_code=302)
    return RedirectResponse("/login", status_code=302)


@app.get("/health")
def health():
    return {"status": "ok"}
