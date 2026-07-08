"""
Motor de IA do DumpAI, agora usando a API gratuita do Google Gemini
(google-genai SDK) em vez da API paga da Anthropic.

Três responsabilidades principais:
1. generate_question       -> gera uma pergunta nova (múltipla escolha ou aberta)
                               adequada à linguagem/certificação e ao nível do usuário.
2. evaluate_open_answer     -> avalia uma resposta dissertativa (0-100) com feedback.
3. evaluate_level_progress  -> a cada N perguntas, decide se o usuário deve ser
                               promovido, mantido ou rebaixado de nível, com justificativa.
"""
from typing import Optional, Literal

from google import genai
from google.genai import types
from pydantic import BaseModel

from app.config import settings, CERTIFICATIONS, LEVELS, LEVEL_LABELS

_client: Optional[genai.Client] = None


def get_client() -> genai.Client:
    global _client
    if _client is None:
        if not settings.GEMINI_API_KEY:
            raise RuntimeError(
                "GEMINI_API_KEY não configurada. Defina no arquivo .env "
                "(chave gratuita em https://aistudio.google.com/apikey)."
            )
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


# --- Schemas de resposta estruturada (o Gemini garante JSON válido nesse formato) ---

class QuestionSchema(BaseModel):
    type: Literal["multiple_choice", "open_ended"]
    topic: str
    question: str
    options: Optional[list[str]] = None
    correct_answer: str


class EvaluationSchema(BaseModel):
    score: float
    is_correct: bool
    feedback: str


class LevelDecisionSchema(BaseModel):
    decision: Literal["promote", "maintain", "demote"]
    reasoning: str


def generate_question(language: str, level: str, recent_history: list[dict]) -> dict:
    """
    Gera uma pergunta adequada ao nível/certificação.
    Retorna dict com: type ('multiple_choice'|'open_ended'), question,
    options (lista, se multiple_choice), correct_answer, topic.
    """
    cert = CERTIFICATIONS[language]
    level_label = LEVEL_LABELS[level]

    history_summary = "\n".join(
        f"- [{h['level']}] {h['question'][:100]} -> {'acertou' if h.get('is_correct') else 'errou/avaliado'}"
        for h in recent_history[-8:]
    ) or "Nenhum histórico ainda."

    system_prompt = (
        "Você é um gerador de questões para uma plataforma de estudo para certificações técnicas."
    )

    user_prompt = f"""
Gere UMA pergunta de estudo para a certificação: {cert['cert_name']} ({cert['label']}).
Nível de dificuldade alvo: {level_label} (escala: Trainee < Júnior < Pleno < Sênior).

Contexto de perguntas recentes do usuário (para evitar repetição de tópicos):
{history_summary}

Regras:
- Alterne entre perguntas de múltipla escolha ("multiple_choice") e dissertativas ("open_ended"),
  favorecendo múltipla escolha para níveis mais baixos e dissertativas para níveis mais altos.
- Para "multiple_choice": forneça exatamente 4 alternativas plausíveis em "options" e coloque a
  alternativa correta (texto idêntico a uma das options) em "correct_answer".
- Para "open_ended": deixe "options" nulo/vazio e coloque em "correct_answer" um gabarito de
  referência resumido.
- O conteúdo deve ser tecnicamente correto e coerente com o nível de dificuldade pedido.
- Evite repetir tópicos já cobertos no histórico recente.
"""

    client = get_client()
    response = client.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            response_schema=QuestionSchema,
            # Desliga o "thinking" estendido do Gemini: para uma tarefa estruturada
            # como essa, o raciocínio extra não melhora a qualidade o suficiente
            # para justificar o tempo extra de resposta.
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    data: QuestionSchema = response.parsed
    return data.model_dump()


def evaluate_open_answer(language: str, level: str, question: str, correct_reference: str, user_answer: str) -> dict:
    """
    Avalia uma resposta dissertativa. Retorna dict com: score (0-100), is_correct (bool),
    feedback (texto curto e construtivo).
    """
    cert = CERTIFICATIONS[language]
    system_prompt = "Você é um avaliador técnico rigoroso, mas didático."
    user_prompt = f"""
Certificação: {cert['cert_name']} ({cert['label']}) - Nível: {LEVEL_LABELS[level]}

Pergunta feita ao usuário:
{question}

Gabarito de referência (guia, não precisa ser idêntico):
{correct_reference}

Resposta do usuário:
{user_answer}

Avalie a resposta do usuário de 0 a 100 quanto à correção técnica e completude,
considerando o nível de dificuldade esperado. is_correct deve ser true se score >= 60.
Dê um feedback curto (2-4 frases), construtivo, apontando o que estava certo e o que pode melhorar.
"""
    client = get_client()
    response = client.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            response_schema=EvaluationSchema,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    data: EvaluationSchema = response.parsed
    return data.model_dump()


def evaluate_level_progress(language: str, current_level: str, recent_history: list[dict]) -> dict:
    """
    Decide se o usuário deve ser promovido, mantido ou rebaixado de nível.
    Retorna dict com: decision ('promote'|'maintain'|'demote'), new_level, reasoning.
    """
    cert = CERTIFICATIONS[language]
    history_lines = "\n".join(
        f"- Nível: {h['level']}, tipo: {h['type']}, "
        f"{'correto' if h.get('is_correct') else 'incorreto'}"
        + (f", score: {h['score']}" if h.get("score") is not None else "")
        for h in recent_history
    )

    idx = LEVELS.index(current_level)
    can_promote = idx < len(LEVELS) - 1
    can_demote = idx > 0

    system_prompt = "Você é um avaliador pedagógico especializado em progressão de aprendizado técnico."
    user_prompt = f"""
Certificação: {cert['cert_name']} ({cert['label']})
Nível atual do usuário: {LEVEL_LABELS[current_level]}
Pode ser promovido: {can_promote}
Pode ser rebaixado: {can_demote}

Desempenho nas últimas {len(recent_history)} perguntas:
{history_lines}

Com base nesse desempenho, decida se o usuário deve:
- ser PROMOVIDO ao próximo nível (bom desempenho consistente, domina o nível atual),
- ser MANTIDO no nível atual (desempenho mediano, ainda precisa praticar),
- ser REBAIXADO ao nível anterior (desempenho fraco, sinaliza dificuldade no nível atual).

Se can_promote for false, nunca escolha "promote". Se can_demote for false, nunca escolha "demote".
Seja criterioso: promoção exige consistência (ex: >= 80% de acertos), rebaixamento só se
desempenho for claramente fraco (ex: <= 40% de acertos).
"""
    client = get_client()
    response = client.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            response_schema=LevelDecisionSchema,
        ),
    )
    result: LevelDecisionSchema = response.parsed

    decision = result.decision
    if decision == "promote" and can_promote:
        new_level = LEVELS[idx + 1]
    elif decision == "demote" and can_demote:
        new_level = LEVELS[idx - 1]
    else:
        decision = "maintain"
        new_level = current_level

    return {
        "decision": decision,
        "new_level": new_level,
        "reasoning": result.reasoning,
    }
