from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings

connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Colunas que foram adicionadas depois da primeira versão do banco. Como o
# projeto não usa Alembic (seria overkill para esse porte), fazemos aqui uma
# migração simples: para cada tabela/coluna nova, se ela ainda não existe,
# adicionamos com ALTER TABLE. Isso preserva 100% dos dados já salvos —
# nunca recriamos ou apagamos a tabela.
_NEW_COLUMNS = {
    "users": [
        ("phone_number", "VARCHAR(30)"),
        ("email_verified", "BOOLEAN DEFAULT 0"),
        ("email_verification_token", "VARCHAR(64)"),
        ("email_verification_expires_at", "DATETIME"),
        ("password_reset_code", "VARCHAR(10)"),
        ("password_reset_expires_at", "DATETIME"),
        ("is_admin", "BOOLEAN DEFAULT 0"),
        ("must_change_password", "BOOLEAN DEFAULT 0"),
    ],
}


def run_lightweight_migrations() -> None:
    """Adiciona colunas novas em tabelas já existentes, sem apagar dados."""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as conn:
        for table, columns in _NEW_COLUMNS.items():
            if table not in existing_tables:
                continue  # tabela será criada do zero pelo create_all, já com tudo
            existing_columns = {col["name"] for col in inspector.get_columns(table)}
            for col_name, col_type in columns:
                if col_name not in existing_columns:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}"))
