#!/bin/bash
# ════════════════════════════════════════════════════════════
#  deploy.sh — Atualiza e reinicia a aplicação sem downtime
#  Execução: bash deploy.sh
# ════════════════════════════════════════════════════════════

set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info() { echo -e "${GREEN}[deploy]${NC} $*"; }
warn() { echo -e "${YELLOW}[deploy]${NC} $*"; }

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR"

info "Iniciando deploy em: $APP_DIR"

# Rebuild das imagens e restart com zero-downtime
info "Fazendo build das imagens..."
docker compose build --pull

info "Subindo serviços..."
docker compose up -d --remove-orphans

# Aguarda o health check da API
info "Aguardando API ficar saudável..."
MAX=30; i=0
until curl -sf http://localhost:8000/health > /dev/null; do
    sleep 2; i=$((i+1))
    [[ $i -ge $MAX ]] && { warn "Timeout — verifique: docker compose logs api"; exit 1; }
done

info "API respondendo. Limpando imagens antigas..."
docker image prune -f > /dev/null

info "Deploy concluído!"
docker compose ps
