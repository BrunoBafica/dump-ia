from sqlalchemy.orm import Session

from app.config import settings
from app.models.models import UserProgress, QuestionLog
from app.services import ai_engine


def get_or_create_progress(db: Session, user_id: int, language: str) -> UserProgress:
    progress = (
        db.query(UserProgress)
        .filter(UserProgress.user_id == user_id, UserProgress.language == language)
        .first()
    )
    if not progress:
        progress = UserProgress(user_id=user_id, language=language, current_level="trainee")
        db.add(progress)
        db.commit()
        db.refresh(progress)
    return progress


def get_recent_history(db: Session, user_id: int, language: str, limit: int = 8) -> list[dict]:
    logs = (
        db.query(QuestionLog)
        .filter(QuestionLog.user_id == user_id, QuestionLog.language == language)
        .order_by(QuestionLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "level": log.level,
            "type": log.question_type,
            "question": log.question_text,
            "is_correct": log.is_correct,
            "score": log.score,
        }
        for log in reversed(logs)
    ]


def register_answer(
    db: Session,
    user_id: int,
    language: str,
    level: str,
    question_type: str,
    question_text: str,
    options_json: str | None,
    correct_answer: str | None,
    user_answer: str,
    is_correct: bool,
    score: float | None,
    ai_feedback: str | None,
) -> UserProgress:
    """Registra o log da pergunta e atualiza os contadores de progresso do usuário."""
    log = QuestionLog(
        user_id=user_id,
        language=language,
        level=level,
        question_type=question_type,
        question_text=question_text,
        options_json=options_json,
        correct_answer=correct_answer,
        user_answer=user_answer,
        is_correct=is_correct,
        score=score,
        ai_feedback=ai_feedback,
    )
    db.add(log)

    progress = get_or_create_progress(db, user_id, language)
    progress.total_answered += 1
    progress.answered_since_last_eval += 1
    if is_correct:
        progress.total_correct += 1
        progress.correct_since_last_eval += 1

    db.commit()
    db.refresh(progress)
    return progress


def maybe_evaluate_level(db: Session, user_id: int, language: str) -> dict | None:
    """
    Se o usuário atingiu o número de perguntas configurado desde a última avaliação,
    chama a IA para decidir promoção/manutenção/rebaixamento de nível.
    Retorna o resultado da avaliação (ou None se ainda não é hora de avaliar).
    """
    progress = get_or_create_progress(db, user_id, language)

    if progress.answered_since_last_eval < settings.QUESTIONS_PER_EVALUATION:
        return None

    recent_history = get_recent_history(
        db, user_id, language, limit=settings.QUESTIONS_PER_EVALUATION
    )
    result = ai_engine.evaluate_level_progress(language, progress.current_level, recent_history)

    old_level = progress.current_level
    progress.current_level = result["new_level"]
    progress.last_evaluation_reasoning = result["reasoning"]
    progress.answered_since_last_eval = 0
    progress.correct_since_last_eval = 0

    db.commit()
    db.refresh(progress)

    return {
        "old_level": old_level,
        "new_level": progress.current_level,
        "decision": result["decision"],
        "reasoning": result["reasoning"],
    }
