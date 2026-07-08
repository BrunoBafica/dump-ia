"""
Cache simples em memória para a próxima pergunta de cada usuário/linguagem.

Enquanto o usuário lê o feedback da pergunta que acabou de responder, disparamos
em segundo plano a geração da PRÓXIMA pergunta e guardamos aqui. Quando ele clica
em "Próxima pergunta", servimos direto do cache em vez de esperar a IA de novo.

Observação: isso é um cache por processo (dict em memória). Funciona bem para
uso pessoal/single-worker. Se um dia rodar com múltiplos workers/processos,
troque por algo compartilhado (ex: Redis) — o cache deixaria de "ver" o que
foi gerado por outro worker.
"""
import threading

_lock = threading.Lock()
_cache: dict[tuple[int, str], dict] = {}


def _key(user_id: int, language: str) -> tuple[int, str]:
    return (user_id, language)


def set_question(user_id: int, language: str, question: dict) -> None:
    with _lock:
        _cache[_key(user_id, language)] = question


def pop_question(user_id: int, language: str) -> dict | None:
    with _lock:
        return _cache.pop(_key(user_id, language), None)


def clear_question(user_id: int, language: str) -> None:
    with _lock:
        _cache.pop(_key(user_id, language), None)
