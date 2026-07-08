import json

from fastapi import APIRouter, Request, Depends, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal
from app.config import CERTIFICATIONS, LEVEL_LABELS
from app.dependencies import get_current_user
from app.models.models import User
from app.services import ai_engine, question_cache
from app.services.progress_service import (
    get_or_create_progress,
    get_recent_history,
    register_answer,
    maybe_evaluate_level,
)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _prefetch_next_question(user_id: int, language: str) -> None:
    """
    Roda em segundo plano logo depois que o usuário responde uma pergunta:
    gera a PRÓXIMA pergunta (já considerando o nível atualizado pós-avaliação)
    e guarda no cache, para a próxima tela carregar na hora.
    Abre sua própria sessão de banco, já que roda fora do ciclo da requisição original.
    """
    db = SessionLocal()
    try:
        progress = get_or_create_progress(db, user_id, language)
        history = get_recent_history(db, user_id, language)
        question = ai_engine.generate_question(language, progress.current_level, history)
        question_cache.set_question(user_id, language, question)
    except Exception:
        # Se der erro (ex: rate limit), simplesmente não deixamos nada no cache;
        # a próxima tela vai gerar a pergunta na hora, como antes.
        question_cache.clear_question(user_id, language)
    finally:
        db.close()


@router.get("/quiz/{language}", response_class=HTMLResponse)
def new_question(
    request: Request,
    language: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if language not in CERTIFICATIONS:
        return RedirectResponse("/dashboard", status_code=302)

    progress = get_or_create_progress(db, user.id, language)

    # Se já tem uma pergunta pré-carregada em background, usa ela na hora
    # (sem esperar a IA). Senão, gera na hora mesmo, como antes.
    question = question_cache.pop_question(user.id, language)
    if question is None:
        history = get_recent_history(db, user.id, language)
        try:
            question = ai_engine.generate_question(language, progress.current_level, history)
        except Exception as exc:
            return templates.TemplateResponse(
                "quiz.html",
                {
                    "request": request,
                    "error": f"Erro ao gerar pergunta via IA: {exc}",
                    "language": language,
                    "cert": CERTIFICATIONS[language],
                    "level_label": LEVEL_LABELS[progress.current_level],
                },
                status_code=502,
            )

    # Guarda a pergunta pendente na sessão para conferência na hora de responder
    request.session[f"pending_{language}"] = json.dumps(question)

    return templates.TemplateResponse(
        "quiz.html",
        {
            "request": request,
            "error": None,
            "language": language,
            "cert": CERTIFICATIONS[language],
            "level_label": LEVEL_LABELS[progress.current_level],
            "question": question,
        },
    )


@router.post("/quiz/{language}/answer", response_class=HTMLResponse)
def submit_answer(
    request: Request,
    language: str,
    background_tasks: BackgroundTasks,
    answer: str = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if language not in CERTIFICATIONS:
        return RedirectResponse("/dashboard", status_code=302)

    pending_raw = request.session.get(f"pending_{language}")
    if not pending_raw:
        return RedirectResponse(f"/quiz/{language}", status_code=302)

    question = json.loads(pending_raw)
    progress = get_or_create_progress(db, user.id, language)

    if question["type"] == "multiple_choice":
        is_correct = answer.strip() == str(question.get("correct_answer", "")).strip()
        score = 100.0 if is_correct else 0.0
        feedback = "Resposta correta!" if is_correct else (
            f"Resposta incorreta. A alternativa correta era: {question.get('correct_answer')}"
        )
    else:
        try:
            evaluation = ai_engine.evaluate_open_answer(
                language,
                progress.current_level,
                question["question"],
                question.get("correct_answer", ""),
                answer,
            )
        except Exception as exc:
            return templates.TemplateResponse(
                "quiz.html",
                {
                    "request": request,
                    "error": f"Erro ao avaliar resposta via IA: {exc}",
                    "language": language,
                    "cert": CERTIFICATIONS[language],
                    "level_label": LEVEL_LABELS[progress.current_level],
                    "question": question,
                },
                status_code=502,
            )
        is_correct = bool(evaluation.get("is_correct"))
        score = float(evaluation.get("score", 0))
        feedback = evaluation.get("feedback", "")

    progress = register_answer(
        db=db,
        user_id=user.id,
        language=language,
        level=progress.current_level,
        question_type=question["type"],
        question_text=question["question"],
        options_json=json.dumps(question.get("options")) if question.get("options") else None,
        correct_answer=str(question.get("correct_answer", "")),
        user_answer=answer,
        is_correct=is_correct,
        score=score,
        ai_feedback=feedback,
    )

    request.session.pop(f"pending_{language}", None)

    level_evaluation = None
    try:
        level_evaluation = maybe_evaluate_level(db, user.id, language)
    except Exception as exc:
        level_evaluation = {"error": str(exc)}

    # Já dispara a geração da próxima pergunta em segundo plano, considerando
    # o nível (possivelmente atualizado) — quando o usuário clicar em
    # "Próxima pergunta", ela deve estar pronta no cache.
    background_tasks.add_task(_prefetch_next_question, user.id, language)

    return templates.TemplateResponse(
        "quiz_result.html",
        {
            "request": request,
            "language": language,
            "cert": CERTIFICATIONS[language],
            "question": question,
            "user_answer": answer,
            "is_correct": is_correct,
            "score": score,
            "feedback": feedback,
            "current_level_label": LEVEL_LABELS[progress.current_level],
            "level_evaluation": level_evaluation,
            "level_labels": LEVEL_LABELS,
        },
    )
