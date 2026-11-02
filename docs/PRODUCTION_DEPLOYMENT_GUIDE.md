# Ente Naadu (എന്റെ നാട്) – Production Deployment & Operations Guide

> **Zero-Cost Hyperlocal Platform for Kerala Panchayats & Municipalities**  
> **Production Target**: 100% Zero Recurring SaaS Cost (₹0/month) with Enterprise Security.

---

## 1. Production Architecture Overview

```
                      [ Citizens & Merchants (Flutter Android & Web) ]
                                            │
                                     (HTTPS Port 443)
                                            ▼
                           [ Cloudflare CDN / Let's Encrypt ]
                                            │
                                            ▼
                       [ Nginx Reverse Proxy (SSL Termination) ]
                                            │
                                      (Unix Socket)
                                            ▼
                      [ Gunicorn WSGI Server (Uvicorn / Gevent) ]
                                            │
                      [ Django 5.1+ Application (Ente Naadu) ]
                       ├── Apps: Accounts, Shops, Orders, Chat,
                       │         Complaints, Directory, Events, AI
                       ├── Static Assets: WhiteNoise + Brotli Caching
                       └── Media Uploads: Local Persistent Disk / Cloudflare R2
                                            │
               ┌────────────────────────────┴────────────────────────────┐
               ▼                                                         ▼
     [ MySQL 8.0+ / Neon Postgres ]                            [ Sentry Error APM ]
     (utf8mb4 Malayalam Collation)                            (Filtered / Scrubbed PII)
```

---

## 2. Server & Domain Setup (Ubuntu 22.04 / 24.04 LTS VPS or Cloud VM)

### 2.1 Domain & DNS Records
Point your Panchayat domain or subdomain to the server IP:
- `A` record: `entenaadu.kerala.gov.in` ➔ `<SERVER_PUBLIC_IPV4>`
- `A` record: `api.entenaadu.in` ➔ `<SERVER_PUBLIC_IPV4>`
- `CNAME` record: `www.entenaadu.kerala.gov.in` ➔ `entenaadu.kerala.gov.in`

### 2.2 System Packages Installation
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv python3-dev \
    mysql-server libmysqlclient-dev default-libmysqlclient-dev \
    nginx certbot python3-certbot-nginx git curl ufw
```

### 2.3 Firewall Configuration (UFW)
```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

---

## 3. MySQL 8.0+ Production Database Setup

Kerala Malayalam script and emojis in complaints, product names, and chat messages require explicit `utf8mb4` encoding and `utf8mb4_unicode_ci` collation.

### 3.1 Configure MySQL Server (`/etc/mysql/conf.d/entenaadu.cnf`)
Create `/etc/mysql/conf.d/entenaadu.cnf`:
```ini
[client]
default-character-set = utf8mb4

[mysql]
default-character-set = utf8mb4

[mysqld]
character-set-client-handshake = FALSE
character-set-server = utf8mb4
collation-server = utf8mb4_unicode_ci
sql_mode = STRICT_TRANS_TABLES,NO_ENGINE_SUBSTITUTION
max_connections = 150
innodb_buffer_pool_size = 512M
```
Restart MySQL:
```bash
sudo systemctl restart mysql
```

### 3.2 Create Database & Dedicated User
```bash
sudo mysql -u root -p
```
```sql
CREATE DATABASE entenaadu_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE USER 'entenaadu_user'@'localhost' IDENTIFIED BY 'StrongAndSecurePassword2026!';
GRANT ALL PRIVILEGES ON entenaadu_db.* TO 'entenaadu_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

---

## 4. Backend Application Deployment

### 4.1 Clone Repository & Setup Virtualenv
```bash
sudo mkdir -p /var/www/entenaadu
sudo chown -R $USER:$USER /var/www/entenaadu
cd /var/www/entenaadu
git clone https://github.com/your-repo/entenaadu.git .

cd backend
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 4.2 Production Environment Variables (`.env`)
Create `/var/www/entenaadu/backend/.env`:
```ini
SECRET_KEY=y0ur-50-ch@r-cryp70gr@ph1c@lly-53cur3-p455w0rd-k3y-h3r3
DEBUG=False
ALLOWED_HOSTS=entenaadu.kerala.gov.in,api.entenaadu.in,localhost,127.0.0.1
SECURE_SSL_REDIRECT=True

# Database Connection (MySQL)
DATABASE_URL=mysql://entenaadu_user:StrongAndSecurePassword2026!@127.0.0.1:3306/entenaadu_db
DB_CONN_MAX_AGE=600

# CORS & CSRF
CORS_ALLOWED_ORIGINS=https://entenaadu.kerala.gov.in,https://api.entenaadu.in
CSRF_TRUSTED_ORIGINS=https://entenaadu.kerala.gov.in,https://api.entenaadu.in

# Storage (Set to True if using Cloudflare R2 / AWS S3)
USE_S3=False

# Error Monitoring (Sentry Free Tier)
SENTRY_DSN=https://examplePublicKey@o0.ingest.sentry.io/0
ENVIRONMENT=production
DJANGO_LOG_LEVEL=INFO
```
Lock `.env` permissions:
```bash
chmod 600 /var/www/entenaadu/backend/.env
```

### 4.3 Database Migrations & Static Files
```bash
cd /var/www/entenaadu/backend
source venv/bin/activate
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check --deploy
```

---

## 5. Gunicorn Systemd Service

Create `/etc/systemd/system/entenaadu.service`:
```ini
[Unit]
Description=Ente Naadu Gunicorn WSGI Daemon
After=network.target mysql.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/entenaadu/backend
Environment="PATH=/var/www/entenaadu/backend/venv/bin"
ExecStart=/var/www/entenaadu/backend/venv/bin/gunicorn \
    --workers 3 \
    --threads 2 \
    --worker-class gthread \
    --timeout 60 \
    --keep-alive 5 \
    --bind unix:/run/entenaadu.sock \
    entenaadu.wsgi:application

Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```
Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable entenaadu
sudo systemctl start entenaadu
sudo systemctl status entenaadu
```

---

## 6. Nginx Reverse Proxy & Let's Encrypt HTTPS

Create `/etc/nginx/sites-available/entenaadu`:
```nginx
upstream entenaadu_app {
    server unix:/run/entenaadu.sock fail_timeout=0;
}

server {
    listen 80;
    server_name entenaadu.kerala.gov.in api.entenaadu.in;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name entenaadu.kerala.gov.in api.entenaadu.in;

    # SSL Certificates managed by Certbot Let's Encrypt
    # ssl_certificate /etc/letsencrypt/live/entenaadu.kerala.gov.in/fullchain.pem;
    # ssl_certificate_key /etc/letsencrypt/live/entenaadu.kerala.gov.in/privkey.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;

    client_max_body_size 15M; # Allows high-res complaint and product images

    # Static files served directly by Nginx (backed by WhiteNoise caching headers)
    location /static/ {
        alias /var/www/entenaadu/backend/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, no-transform";
    }

    # Media uploads
    location /media/ {
        alias /var/www/entenaadu/backend/media/;
        expires 7d;
        add_header Cache-Control "public";
    }

    location / {
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_redirect off;
        proxy_pass http://entenaadu_app;
    }
}
```

Enable site and acquire SSL:
```bash
sudo ln -s /etc/nginx/sites-available/entenaadu /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
sudo certbot --nginx -d entenaadu.kerala.gov.in -d api.entenaadu.in
```

---

## 7. Automated Database Backups & Restore Testing

### 7.1 Automated Nightly Cron
Ente Naadu provides `backend/scripts/backup_db.py`, which performs zero-cost, compressed, timestamped backups and maintains a 14-day rolling retention policy.

Add to crontab (`crontab -e`):
```bash
0 2 * * * /var/www/entenaadu/backend/venv/bin/python /var/www/entenaadu/backend/scripts/backup_db.py >> /var/log/entenaadu_backup.log 2>&1
```

### 7.2 Manual Backup
```bash
cd /var/www/entenaadu/backend
source venv/bin/activate
python scripts/backup_db.py
```

### 7.3 Restore Verification Test
```bash
cd /var/www/entenaadu/backend
source venv/bin/activate
# Restores latest backup with automatic pre-restore safety copy:
python scripts/restore_db.py
```

---

## 8. Android Flutter Production Release Build

### 8.1 Keystore Generation
```bash
keytool -genkey -v -keystore mobile/android/app/entenaadu-release.jks \
    -keyalg RSA -keysize 2048 -validity 10000 \
    -alias entenaadu
```

### 8.2 Create `mobile/android/key.properties`
```properties
storePassword=YourSecretStorePasswordHere
keyPassword=YourSecretKeyPasswordHere
keyAlias=entenaadu
storeFile=entenaadu-release.jks
```

### 8.3 Verify ProGuard / R8 Rules
`mobile/android/app/proguard-rules.pro` has been configured to protect Flutter serialization, models, and prevent stripping of network/API handlers.

### 8.4 Generate Signed Android App Bundle (.aab)
```bash
cd mobile
flutter clean
flutter pub get
flutter build appbundle --release
```
The production bundle will be generated at:
`mobile/build/app/outputs/bundle/release/app-release.aab`

---

## 9. Google Play Store Release Checklist

| Step | Requirement | Action |
|------|-------------|--------|
| 1 | **Target SDK Level** | Ensure `targetSdkVersion 34` (Android 14) configured in `build.gradle` |
| 2 | **Privacy Policy URL** | Host public privacy policy explaining GPS on-demand use at `https://entenaadu.kerala.gov.in/privacy/` |
| 3 | **Background Location** | **Never request background location permission**. Ente Naadu uses strictly foreground, on-demand GPS (`ACCESS_FINE_LOCATION`) only when users open nearby maps or geotag complaints. |
| 4 | **Data Safety Form** | Declare: Location (Approximate/Precise, collected on-demand, not shared with 3rd parties, ephemeral), Personal Info (Phone number, Name for account creation). |
| 5 | **App Category & Content Rating** | Category: Local / Social / Community Directory. Content Rating: Everyone (complete IARC questionnaire). |
| 6 | **Demo Account** | Provide Google Reviewers test phone number: `9876543210` with password `DemoReviewerPass123` in Play Console App Access section. |
| 7 | **Signing Key** | Enroll in Google Play App Signing (upload `app-release.aab`). |

---

## 10. API Performance Benchmark & Load Testing

Run the included standalone load testing tool against your deployment:
```bash
python backend/scripts/load_test.py https://api.entenaadu.in 200 25
```
*Tests 200 requests across Public Directory, Shops, and Notices with 25 concurrent connections, providing latency percentiles (p50, p95, p99) and requests/second.*

---

## 11. Rollback & Disaster Recovery Plan

If a deployment introduces regressions:
1. **Revert Git Code**:
   ```bash
   cd /var/www/entenaadu
   git checkout <PREVIOUS_COMMIT_TAG>
   ```
2. **Revert Database Migrations**:
   ```bash
   cd backend && source venv/bin/activate
   python manage.py showmigrations
   python manage.py migrate <app_name> <previous_migration_number>
   ```
3. **Restore Database from Snapshot** (if schema was corrupted):
   ```bash
   python scripts/restore_db.py backups/mysql_backup_YYYYMMDD_HHMMSS.sql.gz
   ```
4. **Restart Services**:
   ```bash
   sudo systemctl restart entenaadu
   sudo systemctl restart nginx
   ```

---

## 12. Known Limitations & ₹0 Scalability Trade-offs

1. **Lightweight Chat Polling vs. WebSockets**:
   - Ente Naadu uses lightweight HTTP polling (`/api/v1/chat/conversations/<id>/poll/?after=<last_id>`) rather than persistent Redis WebSockets or paid Pusher/Ably channels.
   - *Advantage*: ₹0 hosting cost, zero memory overhead on free/budget servers.
   - *Trade-off*: Chat updates occur every 3-5 seconds rather than millisecond real-time. Perfectly acceptable for community messaging.
2. **Map Tiles**:
   - Uses raster OpenStreetMap tiles (`https://tile.openstreetmap.org/{z}/{x}/{y}.png`).
   - *Limitation*: Complies with standard OSM Fair Use policy. High-traffic Panchayats (>100k requests/day) should place a free Cloudflare cache worker in front of tiles.
3. **AI Assistant**:
   - Google Gemini 1.5 Flash free tier (15 requests/min) provides ₹0 AI answering. If quota is exceeded, Ente Naadu automatically falls back to local intelligent keywords search.
