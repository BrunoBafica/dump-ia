from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Boolean, Float, DateTime, ForeignKey, Text
)
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(80), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Celular: coletado no cadastro, informativo (sem verificação por SMS,
    # que teria custo por mensagem — ver decisão registrada na conversa).
    phone_number = Column(String(30), nullable=True)

    # --- Confirmação de cadastro por e-mail ---
    email_verified = Column(Boolean, default=False)
    email_verification_token = Column(String(64), nullable=True)
    email_verification_expires_at = Column(DateTime, nullable=True)

    # --- Recuperação de senha (2º fator = código enviado ao e-mail) ---
    password_reset_code = Column(String(10), nullable=True)
    password_reset_expires_at = Column(DateTime, nullable=True)

    # --- Administração ---
    is_admin = Column(Boolean, default=False)
    # Força a troca de senha no próximo login (usado no admin padrão admin/admin,
    # e também quando um admin gera senha temporária para outro usuário).
    must_change_password = Column(Boolean, default=False)

    progress_entries = relationship(
        "UserProgress", back_populates="user", cascade="all, delete-orphan"
    )
    question_logs = relationship(
        "QuestionLog", back_populates="user", cascade="all, delete-orphan"
    )


class UserProgress(Base):
    """Progresso do usuário em uma linguagem/certificação específica."""
    __tablename__ = "user_progress"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    language = Column(String(50), nullable=False)  # java, angular, sql, git, python

    current_level = Column(String(20), default="trainee")  # trainee/junior/pleno/senior

    # Contadores usados para decidir promoção/manutenção/rebaixamento
    total_answered = Column(Integer, default=0)
    total_correct = Column(Integer, default=0)
    answered_since_last_eval = Column(Integer, default=0)
    correct_since_last_eval = Column(Integer, default=0)

    last_evaluation_reasoning = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="progress_entries")


class QuestionLog(Base):
    """Histórico de perguntas respondidas, usado como contexto para a IA."""
    __tablename__ = "question_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    language = Column(String(50), nullable=False)
    level = Column(String(20), nullable=False)

    question_type = Column(String(20), nullable=False)  # multiple_choice / open_ended
    question_text = Column(Text, nullable=False)
    options_json = Column(Text, nullable=True)  # JSON com alternativas, se houver
    correct_answer = Column(Text, nullable=True)  # gabarito, se multiple_choice

    user_answer = Column(Text, nullable=True)
    is_correct = Column(Boolean, nullable=True)
    score = Column(Float, nullable=True)  # 0-100, usado em respostas abertas
    ai_feedback = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="question_logs")
