#!/bin/bash
# ════════════════════════════════════════════════════════════════
#  setup.sh — Configuração inicial do servidor Debian para a API
#  Testado em: Debian 11 (Bullseye) e 12 (Bookworm)
#  Execução: sudo bash setup.sh
# ════════════════════════════════════════════════════════════════

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()    { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERR]${NC}   $*"; exit 1; }

[[ $EUID -ne 0 ]] && error "Execute como root: sudo bash setup.sh"

APP_DIR="/opt/whatsapp-api"
SERVICE_USER="whatsapp"

# ── 1. Atualizar sistema ──────────────────────────────────────────────────────
info "Atualizando pacotes..."
apt-get update -qq
apt-get upgrade -y -qq

# ── 2. Dependências base ──────────────────────────────────────────────────────
info "Instalando dependências base..."
apt-get install -y -qq \
    curl ca-certificates gnupg lsb-release \
    nginx ufw git

# ── 3. Docker ────────────────────────────────────────────────────────────────
info "Instalando Docker..."
if ! command -v docker &>/dev/null; then
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/debian/gpg \
        | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg

    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/debian $(lsb_release -cs) stable" \
        > /etc/apt/sources.list.d/docker.list

    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin
    systemctl enable --now docker
    info "Docker instalado: $(docker --version)"
else
    info "Docker já instalado: $(docker --version)"
fi

# ── 4. Usuário de serviço ─────────────────────────────────────────────────────
info "Configurando usuário '$SERVICE_USER'..."
if ! id "$SERVICE_USER" &>/dev/null; then
    useradd -r -m -s /bin/bash "$SERVICE_USER"
fi
usermod -aG docker "$SERVICE_USER"

# ── 5. Diretório da aplicação ─────────────────────────────────────────────────
info "Criando diretório $APP_DIR..."
mkdir -p "$APP_DIR"
chown "$SERVICE_USER:$SERVICE_USER" "$APP_DIR"

# ── 6. Nginx ──────────────────────────────────────────────────────────────────
info "Configurando Nginx..."
NGINX_CONF="/etc/nginx/sites-available/whatsapp-api"

cat > "$NGINX_CONF" <<'NGINX'
server {
    listen 80;
    server_name _;          # Substitua pelo seu domínio ou IP

    # Segurança básica
    add_header X-Frame-Options       DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection      "1; mode=block";

    # Limite de tamanho (10 MB para mídia futura)
    client_max_body_size 10M;

    location / {
        proxy_pass         http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
        proxy_connect_timeout 10s;
    }
}
NGINX

ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/whatsapp-api
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
info "Nginx configurado"

# ── 7. Systemd service ────────────────────────────────────────────────────────
info "Criando serviço systemd..."
cat > /etc/systemd/system/whatsapp-api.service <<SERVICE
[Unit]
Description=WhatsApp API (Docker Compose)
Requires=docker.service
After=docker.service network-online.target

[Service]
Type=simple
User=${SERVICE_USER}
WorkingDirectory=${APP_DIR}
ExecStart=/usr/bin/docker compose up --remove-orphans
ExecStop=/usr/bin/docker compose down
Restart=on-failure
RestartSec=10s
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SERVICE

systemctl daemon-reload
systemctl enable whatsapp-api.service
info "Serviço systemd registrado"

# ── 8. Firewall (UFW) ─────────────────────────────────────────────────────────
info "Configurando firewall..."
ufw --force reset > /dev/null
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 'Nginx HTTP'
ufw --force enable
info "Firewall configurado (SSH + HTTP liberados)"

# ── 9. Resumo ─────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}══════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Setup concluído com sucesso!${NC}"
echo -e "${GREEN}══════════════════════════════════════════════${NC}"
echo ""
echo "Próximos passos:"
echo "  1. Copie os arquivos do projeto para: $APP_DIR"
echo "       rsync -avz ./ ${SERVICE_USER}@<ip>:${APP_DIR}/"
echo ""
echo "  2. Configure o .env:"
echo "       cp $APP_DIR/.env.example $APP_DIR/.env"
echo "       nano $APP_DIR/.env"
echo ""
echo "  3. Inicie a aplicação:"
echo "       sudo systemctl start whatsapp-api"
echo ""
echo "  4. Verifique o status:"
echo "       sudo systemctl status whatsapp-api"
echo "       sudo journalctl -u whatsapp-api -f"
echo ""
echo "  5. Escaneie o QR Code:"
echo "       curl -H 'X-API-Key: SUA_CHAVE' http://localhost/api/v1/session/qr/image > qr.png"
echo ""
warn "Para HTTPS (recomendado): sudo apt install certbot python3-certbot-nginx && sudo certbot --nginx"
