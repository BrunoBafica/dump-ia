# DumpAI

Plataforma de estudo adaptativo para certificações técnicas, com perguntas geradas e avaliadas por IA (**Google Gemini API — tier gratuito**).

Certificações cobertas:

| Linguagem | Certificação de referência |
|---|---|
| Java | Oracle Certified Professional: Java SE Programmer (OCP) |
| Angular | [Angular Certification — certificates.dev](https://certificates.dev/angular) |
| SQL | Oracle Database SQL Certified Associate |
| Git | GitHub Foundations Certification |
| Python | PCEP / PCAP (Python Institute) |

Cada certificação tem sua própria aba/progresso, com 4 níveis: **Trainee → Júnior → Pleno → Sênior**.

## Como conseguir sua chave gratuita do Gemini

1. Acesse **https://aistudio.google.com/apikey** (login com conta Google).
2. Clique em **Create API key**. Não pede cartão de crédito.
3. Copie a chave (começa com `AIza...`).
4. Cole no `.env` do projeto em `GEMINI_API_KEY`.

O modelo padrão configurado é o `gemini-2.5-flash`, que fica no **tier gratuito** do Google AI Studio (sem custo, sem necessidade de cartão). Os limites atuais giram em torno de ~1.500 requisições/dia — mais do que suficiente para uso pessoal de estudo. Um ponto de atenção: no tier gratuito, o Google pode usar os prompts/respostas para melhorar os modelos deles (não use dados sensíveis). Se um dia quiser mais volume ou privacidade total dos dados, é só ativar billing na mesma chave — mas para o uso que você descreveu isso não deve ser necessário.

## Como funciona a adaptação de nível

1. A cada pergunta respondida, o sistema registra acerto/erro (múltipla escolha é corrigida localmente; perguntas abertas são avaliadas pela IA com nota 0-100 e feedback).
2. A cada **N perguntas** (padrão: 5, configurável via `QUESTIONS_PER_EVALUATION`), a IA analisa o histórico recente daquela linguagem e decide:
   - **Promover** para o próximo nível (bom desempenho consistente),
   - **Manter** o nível atual (desempenho mediano),
   - **Rebaixar** para o nível anterior (dificuldade clara no nível atual).
3. A justificativa da IA fica visível para o usuário no dashboard e na tela de resultado.

## Rodando localmente (sem Docker)

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edite o .env e coloque sua GEMINI_API_KEY (gratuita, veja acima)

uvicorn app.main:app --reload
```

Acesse http://localhost:8000

## Rodando com Docker

```bash
cp .env.example .env
# edite o .env e coloque sua GEMINI_API_KEY

docker compose up --build
```

Acesse http://localhost:8000. O banco SQLite fica persistido em `./data/dumpai.db` (montado como volume).

## Migrando para PostgreSQL

1. Descomente o serviço `db` no `docker-compose.yml`.
2. Troque `DATABASE_URL` no `.env` para algo como:
   `postgresql+psycopg2://dumpai:dumpai@db:5432/dumpai`
3. Adicione `psycopg2-binary` ao `requirements.txt`.
4. Suba com `docker compose up --build` — as tabelas são criadas automaticamente na primeira execução (`Base.metadata.create_all`).

## Estrutura do projeto

```
dumpai/
  app/
    main.py                 # app FastAPI, monta rotas e middleware de sessão
    config.py                # configurações, certificações, níveis
    database.py               # engine/sessão SQLAlchemy
    dependencies.py            # get_current_user (via sessão)
    models/models.py            # User, UserProgress, QuestionLog
    services/
      auth_service.py           # hash de senha, criação/autenticação de usuário
      ai_engine.py                # geração de perguntas, avaliação, decisão de nível (Gemini)
      progress_service.py           # registra respostas, dispara reavaliação
    routers/
      auth_router.py               # login, registro, logout
      dashboard_router.py            # dashboard com abas por linguagem
      quiz_router.py                  # gera pergunta / recebe resposta
    templates/                        # Jinja2 + CSS custom (tema "build pipeline")
    static/css/style.css
  requirements.txt
  Dockerfile
  docker-compose.yml
  .env.example
```

## Próximos passos sugeridos

- Hospedar o container (Railway, Render, Fly.io, VPS com Docker).
- Migrar de SQLite para PostgreSQL em produção (ver seção acima).
- Adicionar rate-limiting nas chamadas à IA por usuário, para controlar custo de API.
- Adicionar tela de histórico detalhado de perguntas por linguagem.
