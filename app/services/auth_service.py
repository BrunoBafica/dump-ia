import secrets
import string
from datetime import datetime, timedelta

import bcrypt
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models.models import User


def hash_password(password: str) -> str:
    # bcrypt tem limite de 72 bytes; senhas maiores são truncadas de forma segura
    password_bytes = password.encode("utf-8")[:72]
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    password_bytes = plain_password.encode("utf-8")[:72]
    return bcrypt.checkpw(password_bytes, password_hash.encode("utf-8"))


def get_user_by_username(db: Session, username: str) -> User | None:
    """Busca por nome de usuário SEM diferenciar maiúsculas/minúsculas — evita
    que 'Bruno' e 'bruno' sejam tratados como usuários diferentes (duplicados
    disfarçados)."""
    return db.query(User).filter(func.lower(User.username) == username.strip().lower()).first()


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(func.lower(User.email) == email.strip().lower()).first()


def create_user(
    db: Session, username: str, email: str, password: str, phone_number: str | None = None
) -> User:
    user = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
        phone_number=phone_number or None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    user = get_user_by_username(db, username)
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def change_password(db: Session, user: User, new_password: str) -> None:
    user.password_hash = hash_password(new_password)
    user.must_change_password = False
    db.commit()


# --- Confirmação de cadastro por e-mail ---

def create_email_verification(db: Session, user: User) -> str:
    """Gera um token de confirmação de e-mail e salva no usuário. Retorna o token."""
    token = secrets.token_urlsafe(32)
    user.email_verification_token = token
    user.email_verification_expires_at = datetime.utcnow() + timedelta(
        minutes=settings.EMAIL_VERIFICATION_EXPIRE_MINUTES
    )
    db.commit()
    return token


def confirm_email_token(db: Session, token: str) -> bool:
    """Confirma o e-mail se o token existir e ainda for válido."""
    user = db.query(User).filter(User.email_verification_token == token).first()
    if not user:
        return False
    if not user.email_verification_expires_at or user.email_verification_expires_at < datetime.utcnow():
        return False
    user.email_verified = True
    user.email_verification_token = None
    user.email_verification_expires_at = None
    db.commit()
    return True


# --- Recuperação de senha (2º fator: código enviado por e-mail) ---

def create_password_reset_code(db: Session, user: User) -> str:
    """Gera um código numérico de 6 dígitos para recuperação de senha."""
    code = f"{secrets.randbelow(1_000_000):06d}"
    user.password_reset_code = code
    user.password_reset_expires_at = datetime.utcnow() + timedelta(
        minutes=settings.PASSWORD_RESET_CODE_EXPIRE_MINUTES
    )
    db.commit()
    return code


def verify_password_reset_code(db: Session, user: User, code: str) -> bool:
    if not user.password_reset_code or not user.password_reset_expires_at:
        return False
    if user.password_reset_expires_at < datetime.utcnow():
        return False
    return secrets.compare_digest(user.password_reset_code, code.strip())


def generate_temp_password(length: int = 10) -> str:
    """Gera uma senha temporária aleatória e legível (sem caracteres ambíguos)."""
    alphabet = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def reset_password_with_temp(db: Session, user: User) -> str:
    """
    Gera uma senha temporária NOVA (nunca a original — isso é irreversível pelo
    hash bcrypt), salva o hash dela e limpa o código de recuperação usado.
    Retorna a senha temporária em texto puro, só para ser enviada por e-mail
    (ou exibida ao admin) uma única vez — não fica salva em nenhum lugar.
    Também marca a conta para forçar a troca de senha no próximo login.
    """
    temp_password = generate_temp_password()
    user.password_hash = hash_password(temp_password)
    user.password_reset_code = None
    user.password_reset_expires_at = None
    user.must_change_password = True
    db.commit()
    return temp_password


# --- Administração ---

def seed_default_admin(db: Session) -> None:
    """
    Cria o usuário admin/admin na primeira vez que o app sobe, se ainda não
    existir nenhum administrador. A senha É a solicitada (admin/admin), mas
    a conta nasce com must_change_password=True — ou seja, o sistema OBRIGA
    a troca de senha no primeiro login, então o "admin/admin" nunca fica
    utilizável por mais que alguns segundos.
    """
    existing_admin = db.query(User).filter(User.is_admin == True).first()  # noqa: E712
    if existing_admin:
        return

    # Se por acaso já existir um usuário comum chamado "admin", não sobrescreve.
    if get_user_by_username(db, "admin"):
        return

    admin = User(
        username="admin",
        email="admin@dumpai.local",
        password_hash=hash_password("admin"),
        is_admin=True,
        email_verified=True,
        must_change_password=True,
    )
    db.add(admin)
    db.commit()


def update_user_credentials(
    db: Session, user: User, new_username: str | None = None, new_email: str | None = None
) -> str | None:
    """
    Atualiza usuário/e-mail de uma conta (uso do admin). Retorna uma mensagem
    de erro (string) se houver conflito de duplicidade, ou None se deu certo.
    """
    if new_username and new_username.strip().lower() != user.username.lower():
        conflict = get_user_by_username(db, new_username)
        if conflict and conflict.id != user.id:
            return "Já existe um usuário com esse nome."
        user.username = new_username.strip()

    if new_email and new_email.strip().lower() != user.email.lower():
        conflict = get_user_by_email(db, new_email)
        if conflict and conflict.id != user.id:
            return "Já existe um usuário com esse e-mail."
        user.email = new_email.strip()
        # Mudou o e-mail: precisa confirmar de novo.
        user.email_verified = False

    db.commit()
    return None
