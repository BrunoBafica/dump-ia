from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.database import Base, engine
from app.routers import auth_router, dashboard_router, quiz_router

# Cria as tabelas do banco de dados, se ainda não existirem
Base.metadata.create_all(bind=engine)

app = FastAPI(title="DumpAI - Plataforma de Estudo para Certificações")

app.add_middleware(SessionMiddleware, secret_key=settings.SESSION_SECRET)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(auth_router.router)
app.include_router(dashboard_router.router)
app.include_router(quiz_router.router)


@app.get("/")
def root(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse("/dashboard", status_code=302)
    return RedirectResponse("/login", status_code=302)


@app.get("/health")
def health():
    return {"status": "ok"}
