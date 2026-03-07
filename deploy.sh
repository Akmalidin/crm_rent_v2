#!/bin/bash
# ============================================
# CRM Rent Deploy Script — Ubuntu 24.04
# Timeweb Cloud — root@46.149.68.65
# ============================================

set -e

APP_NAME="crm_rent"
APP_USER="crm"
APP_DIR="/home/$APP_USER/crm_rent_v2"
VENV_DIR="$APP_DIR/venv"
REPO_URL="https://github.com/Akmalidin/crm_rent_v2.git"
SERVER_IP="46.149.68.65"
PYTHON_VER="python3.12"

echo "=========================================="
echo "  CRM Rent — Production Deploy"
echo "=========================================="

# ── 1. System packages ──────────────────────
echo ""
echo "[1/8] Installing system packages..."
apt update -y
apt install -y \
    python3.12 python3.12-venv python3.12-dev \
    python3-pip \
    nginx \
    git \
    build-essential \
    libcairo2-dev libpango1.0-dev libgdk-pixbuf2.0-dev libffi-dev \
    libxml2-dev libxslt1-dev \
    libjpeg-dev zlib1g-dev libfreetype6-dev \
    pkg-config \
    curl wget \
    fonts-dejavu-core \
    supervisor

# ── 2. Create app user ──────────────────────
echo ""
echo "[2/8] Creating app user '$APP_USER'..."
if ! id "$APP_USER" &>/dev/null; then
    useradd -m -s /bin/bash "$APP_USER"
    echo "User $APP_USER created."
else
    echo "User $APP_USER already exists."
fi

# ── 3. Clone / update repo ──────────────────
echo ""
echo "[3/8] Cloning repository..."
if [ -d "$APP_DIR" ]; then
    echo "Directory exists, pulling latest..."
    cd "$APP_DIR"
    git pull origin main
else
    git clone "$REPO_URL" "$APP_DIR"
    cd "$APP_DIR"
fi
chown -R $APP_USER:$APP_USER "$APP_DIR"

# ── 4. Virtual environment + dependencies ───
echo ""
echo "[4/8] Setting up Python virtual environment..."
sudo -u $APP_USER $PYTHON_VER -m venv "$VENV_DIR"
sudo -u $APP_USER "$VENV_DIR/bin/pip" install --upgrade pip
sudo -u $APP_USER "$VENV_DIR/bin/pip" install -r "$APP_DIR/requirements.txt"

# ── 5. Environment variables ────────────────
echo ""
echo "[5/8] Creating .env file..."
ENV_FILE="$APP_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
    SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))")
    cat > "$ENV_FILE" << ENVEOF
SECRET_KEY=$SECRET
DEBUG=False
ALLOWED_HOSTS=$SERVER_IP,localhost,127.0.0.1
TELEGRAM_BOT_TOKEN=8276509481:AAGhKOhn45P8l5belorDsEqqetqGNgHoG3s
TELEGRAM_ADMIN_CHAT_ID=1289894304
ENVEOF
    chown $APP_USER:$APP_USER "$ENV_FILE"
    chmod 600 "$ENV_FILE"
    echo ".env created with new SECRET_KEY"
else
    echo ".env already exists, skipping."
fi

# ── 6. Django setup ─────────────────────────
echo ""
echo "[6/8] Running Django setup..."
cd "$APP_DIR"

# Load env vars
export $(grep -v '^#' "$ENV_FILE" | xargs)

sudo -u $APP_USER -E "$VENV_DIR/bin/python" manage.py migrate --noinput
sudo -u $APP_USER -E "$VENV_DIR/bin/python" manage.py collectstatic --noinput

# Create superuser if needed
echo ""
echo "Creating admin superuser (if not exists)..."
sudo -u $APP_USER -E "$VENV_DIR/bin/python" manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(is_superuser=True, is_staff=True).exists():
    User.objects.create_superuser('admin', 'admin@crm.local', 'admin123')
    print('Superuser admin created (password: admin123)')
else:
    print('Superuser already exists, skipping.')
"

# ── 7. Gunicorn systemd service ─────────────
echo ""
echo "[7/8] Configuring Gunicorn..."

cat > /etc/systemd/system/crm_rent.service << SVCEOF
[Unit]
Description=CRM Rent Gunicorn Service
After=network.target

[Service]
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
ExecStart=$VENV_DIR/bin/gunicorn config.wsgi:application \
    --bind 127.0.0.1:8000 \
    --workers 3 \
    --timeout 120 \
    --access-logfile /var/log/crm_rent_access.log \
    --error-logfile /var/log/crm_rent_error.log
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
SVCEOF

systemctl daemon-reload
systemctl enable crm_rent
systemctl restart crm_rent
echo "Gunicorn service started."

# ── 8. Nginx config ─────────────────────────
echo ""
echo "[8/8] Configuring Nginx..."

cat > /etc/nginx/sites-available/crm_rent << NGXEOF
server {
    listen 80;
    server_name $SERVER_IP;

    client_max_body_size 20M;

    # Static files (served by whitenoise, but nginx caches)
    location /static/ {
        alias $APP_DIR/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Media files (uploads)
    location /media/ {
        alias $APP_DIR/media/;
        expires 7d;
    }

    # Proxy to Gunicorn
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 60;
        proxy_read_timeout 120;
    }
}
NGXEOF

# Enable site
ln -sf /etc/nginx/sites-available/crm_rent /etc/nginx/sites-enabled/crm_rent
rm -f /etc/nginx/sites-enabled/default

# Test and reload nginx
nginx -t && systemctl reload nginx
systemctl enable nginx

echo ""
echo "=========================================="
echo "  DEPLOY COMPLETE!"
echo "=========================================="
echo ""
echo "  Site: http://$SERVER_IP"
echo "  Admin: http://$SERVER_IP/admin/"
echo ""
echo "  Useful commands:"
echo "    systemctl status crm_rent    — check app status"
echo "    systemctl restart crm_rent   — restart app"
echo "    journalctl -u crm_rent -f    — view logs"
echo "    tail -f /var/log/crm_rent_error.log"
echo ""
echo "  To update code:"
echo "    cd $APP_DIR && git pull origin main"
echo "    $VENV_DIR/bin/python manage.py migrate"
echo "    $VENV_DIR/bin/python manage.py collectstatic --noinput"
echo "    systemctl restart crm_rent"
echo ""
