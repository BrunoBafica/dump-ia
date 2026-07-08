from fastapi import Request, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import User

# Rotas que continuam acessíveis mesmo quando a conta precisa trocar de senha
# (senão o usuário ficaria preso num redirect em loop).
_ALLOWED_WHILE_MUST_CHANGE_PASSWORD = {
    "/account/change-password",
    "/logout",
}


class NotAuthenticatedError(Exception):
    """Levantada quando a rota exige login e não há sessão válida."""
    pass


class MustChangePasswordError(Exception):
    """
    Levantada quando a conta está marcada para troca obrigatória de senha
    (admin/admin inicial, ou senha temporária gerada por reset) e o usuário
    tenta acessar qualquer página além da troca de senha / logout.
    """
    pass


class NotAdminError(Exception):
    """Levantada quando uma rota exige admin e o usuário logado não é admin."""
    pass


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user_id = request.session.get("user_id")
    if not user_id:
        raise NotAuthenticatedError()
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        request.session.clear()
        raise NotAuthenticatedError()

    if user.must_change_password and request.url.path not in _ALLOWED_WHILE_MUST_CHANGE_PASSWORD:
        raise MustChangePasswordError()

    return user


def get_current_admin(request: Request, db: Session = Depends(get_db)) -> User:
    user = get_current_user(request, db)
    if not user.is_admin:
        raise NotAdminError()
    return user


def get_optional_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.query(User).filter(User.id == user_id).first()
