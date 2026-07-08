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

## Configurando o envio de e-mails (confirmação de cadastro e recuperação de senha)

O app envia e-mails em duas situações: **confirmação de cadastro** (link) e **recuperação de senha** (código de verificação). Isso exige um servidor SMTP configurado.

### Como conseguir SMTP gratuito (Brevo — recomendado)

1. Crie uma conta em **https://www.brevo.com** (sem cartão de crédito). O tier gratuito permite **300 e-mails/dia para sempre**.
2. No painel: **Settings → SMTP & API → SMTP** — copie o **login SMTP** e gere uma **chave SMTP** (não é a senha da sua conta).
3. Cole no `.env`:
   ```
   SMTP_HOST=smtp-relay.brevo.com
   SMTP_PORT=587
   SMTP_USER=seu-login-smtp-da-brevo
   SMTP_PASSWORD=sua-chave-smtp-gerada
   EMAIL_FROM=no-reply@seudominio.com
   ```
   Obs: o `EMAIL_FROM` idealmente deve ser um domínio que você verificou na Brevo (evita cair em spam). Para testes, qualquer endereço funciona, mas a entrega pode ser menos confiável.
4. Defina também `APP_BASE_URL` com a URL real onde o app está publicado (ex: `https://dumpai.seudominio.com`) — é usada para montar o link de confirmação de e-mail.

Sem essas variáveis configuradas, o cadastro e o login continuam funcionando normalmente — só o envio de e-mail falha silenciosamente (o usuário pode pedir reenvio depois em "Minha conta").

## Segurança de conta: confirmação de e-mail e recuperação de senha

- **Cadastro:** ao criar a conta, o usuário já entra normalmente, mas recebe um e-mail com um link de confirmação (válido por 24h). Enquanto não confirmar, aparece um aviso no dashboard com opção de reenviar.
- **Esqueci minha senha (2 fatores):**
  1. Usuário informa usuário/e-mail em `/forgot-password`.
  2. Sistema envia um **código de 6 dígitos** para o e-mail cadastrado (válido por 10 min) — esse é o segundo fator, prova que a pessoa tem acesso à caixa de entrada.
  3. Ao confirmar o código, o sistema gera uma **senha temporária nova e aleatória** e envia por e-mail.
  4. **Importante:** a senha original nunca é reenviada — isso seria impossível (fica salva como hash bcrypt, irreversível por design) e também seria uma prática insegura mesmo que fosse possível. Por isso sempre geramos uma senha nova.
  5. Depois de entrar com a senha temporária, o usuário pode trocá-la em **Minha conta → Trocar senha**.
- **Celular:** coletado no cadastro como campo informativo, sem verificação por SMS (nenhuma API de SMS/WhatsApp tem tier realmente gratuito — ver decisão registrada no histórico do projeto).

## Painel administrativo

Acessível em **`/admin`** para o usuário com `is_admin=True`.

- **Usuário/senha inicial: `admin` / `admin`** — criado automaticamente na primeira vez que o app sobe (não é recriado se já existir um admin).
- **Troca de senha obrigatória:** por segurança, a conta `admin/admin` nasce marcada para forçar a troca de senha. No primeiro login, qualquer tentativa de acessar outra página (dashboard, admin, etc.) redireciona automaticamente para "Trocar senha" — o `admin/admin` literalmente não dá pra usar além desse primeiro passo. **Troque assim que possível, principalmente se o app estiver publicado numa VPS.**
- **O que dá pra fazer no painel:**
  - Ver todos os usuários cadastrados: e-mail, celular, status de confirmação, progresso por certificação, últimas perguntas respondidas.
  - Editar o nome de usuário e o e-mail de qualquer conta (com validação de duplicidade).
  - Gerar uma senha temporária nova para qualquer usuário ("Redefinir senha") — mesma lógica segura do "esqueci minha senha": nunca reenvia a senha original. Se o SMTP estiver configurado, envia por e-mail; senão, mostra a senha na tela (uma única vez) para você repassar manualmente.
- Usuários sem `is_admin=True` que tentarem acessar `/admin` são redirecionados de volta ao dashboard normal, sem erro feio.

## Validação de nome de usuário duplicado

O cadastro (e a edição pelo admin) rejeita nomes de usuário e e-mails já existentes — inclusive variações de **maiúsculas/minúsculas** (`Bruno` e `bruno` contam como o mesmo usuário, evitando duplicados disfarçados).

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

Acesse http://localhost:8000. O banco SQLite fica persistido num **volume Docker nomeado** (`dumpai_data`) — ou seja, vive fora da pasta do projeto. Atualizar o código (`git pull` + rebuild) nunca apaga os dados dos usuários. Para inspecionar/fazer backup dele:

```bash
docker volume inspect dumpai_data          # mostra onde o Docker guarda os arquivos
docker run --rm -v dumpai_data:/data -v $(pwd):/backup alpine \
  cp /data/dumpai.db /backup/dumpai-backup.db   # copia o banco para a pasta atual
```

## Deploy numa VPS com atualização automática a cada push

O objetivo: você dá `git push`, e alguns segundos depois a versão nova já está no ar na VPS, **sem perder o banco de dados**.

### Passo 1 — Preparar a VPS (uma vez só)

Via SSH na VPS:

```bash
# instalar Docker + Docker Compose (Ubuntu/Debian)
curl -fsSL https://get.docker.com | sh

# clonar o projeto (troque pela URL do seu repositório)
git clone https://github.com/BrunoBafica/dump-ia.git /opt/dumpai
cd /opt/dumpai

# criar o .env com sua chave real (isso NUNCA vai pro Git)
cp .env.example .env
nano .env    # cole sua GEMINI_API_KEY e um SESSION_SECRET fixo

# deixar o script de deploy executável
chmod +x deploy.sh

# primeiro deploy manual, pra validar que builda certo
./deploy.sh
```

### Passo 2 — Criar uma chave SSH só para o deploy automático

Ainda na VPS:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/dumpai_deploy -N ""
cat ~/.ssh/dumpai_deploy.pub >> ~/.ssh/authorized_keys
cat ~/.ssh/dumpai_deploy          # copie essa chave PRIVADA inteira, vai usar no próximo passo
```

### Passo 3 — Configurar os "Secrets" no GitHub

No repositório: **Settings → Secrets and variables → Actions → New repository secret**. Crie estes 4:

| Nome do secret | Valor |
|---|---|
| `VPS_HOST` | IP da sua VPS (ex: `123.45.67.89`) |
| `VPS_USER` | usuário SSH usado na VPS (ex: `root` ou `ubuntu`) |
| `VPS_SSH_KEY` | conteúdo da chave **privada** gerada no passo 2 (`~/.ssh/dumpai_deploy`) |
| `VPS_PROJECT_PATH` | caminho onde clonou o projeto na VPS (ex: `/opt/dumpai`) |

O workflow já está pronto em `.github/workflows/deploy.yml` — ele vai rodar sozinho a cada `git push` na branch `main`, entrar na VPS via SSH e executar o `deploy.sh`.

### Passo 4 — Testar

```bash
git add .
git commit -m "algum ajuste"
git push
```

Acompanhe em **Actions** (aba do GitHub) — deve aparecer o workflow "Deploy DumpAI" rodando. Se der erro de permissão SSH, confira se a chave pública foi mesmo adicionada ao `authorized_keys` do usuário certo.

**Importante:** como o banco fica num volume Docker separado (não na pasta do projeto), o `git reset --hard` que o `deploy.sh` faz para sincronizar o código **não afeta os dados salvos**.

## Migrando para PostgreSQL

1. Descomente o serviço `db` no `docker-compose.yml`.
2. Troque `DATABASE_URL` no `.env` para algo como:
   `postgresql+psycopg2://dumpai:dumpai@db:5432/dumpai`
3. Adicione `psycopg2-binary` ao `requirements.txt`.
4. Suba com `docker compose up --build` — as tabelas são criadas automaticamente na primeira execução (`Base.metadata.create_all`).

## Estrutura do projeto

```
dumpai/
  .github/workflows/deploy.yml    # CI/CD: deploy automático via SSH a cada push na main
  app/
    main.py                 # app FastAPI, monta rotas e middleware de sessão
    config.py                # configurações, certificações, níveis
    database.py               # engine/sessão SQLAlchemy
    dependencies.py            # get_current_user (via sessão)
    models/models.py            # User, UserProgress, QuestionLog
    services/
      auth_service.py           # hash de senha, criação/autenticação, tokens/códigos de verificação
      email_service.py           # envio de e-mail (confirmação de cadastro, recuperação de senha)
      ai_engine.py                # geração de perguntas, avaliação, decisão de nível (Gemini)
      progress_service.py           # registra respostas, dispara reavaliação
      question_cache.py              # cache em memória p/ pré-carregar a próxima pergunta
    routers/
      auth_router.py               # login, registro, logout, confirmação de e-mail, esqueci senha
      dashboard_router.py            # dashboard com abas por linguagem
      quiz_router.py                  # gera pergunta / recebe resposta
      admin_router.py                  # painel admin: usuários, edição, reset de senha
    templates/                        # Jinja2 + CSS custom (tema "build pipeline")
    static/css/style.css
  requirements.txt
  Dockerfile
  docker-compose.yml
  deploy.sh                # script executado na VPS a cada deploy
  .env.example
```

## Próximos passos sugeridos

- Hospedar o container (Railway, Render, Fly.io, VPS com Docker).
- Migrar de SQLite para PostgreSQL em produção (ver seção acima).
- Adicionar rate-limiting nas chamadas à IA por usuário, para controlar custo de API.
- Adicionar tela de histórico detalhado de perguntas por linguagem.
