#!/usr/bin/env bash
# Script de deploy do DumpAI. Roda DENTRO da VPS (chamado pelo GitHub Actions via SSH,
# ou manualmente se você quiser atualizar sem esperar o CI).
#
# Pressupõe que:
# - O repositório já foi clonado uma vez nessa pasta (git clone ...)
# - O arquivo .env já existe nessa pasta, com GEMINI_API_KEY, SESSION_SECRET etc.
# - Docker e Docker Compose (plugin) já estão instalados na VPS.

set -euo pipefail

echo "==> Entrando na pasta do projeto"
cd "$(dirname "$0")"

echo "==> Buscando alterações do repositório (main)"
git fetch origin main
git reset --hard origin/main

echo "==> Subindo containers atualizados (o volume do banco de dados NÃO é afetado)"
docker compose up -d --build

echo "==> Limpando imagens antigas não usadas (economiza espaço em disco)"
docker image prune -f

echo "==> Deploy concluído."
docker compose ps
