#!/usr/bin/env python3
"""
Ente Naadu - Automated Database Backup Script
Supports: SQLite (hot atomic backup), PostgreSQL (pg_dump), MySQL/MariaDB (mysqldump with utf8mb4)
Zero-cost, standalone, suitable for Cron or scheduled tasks.
"""

import os
import sys
import gzip
import shutil
import subprocess
import sqlite3
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

# Setup paths
BASE_DIR = Path(__file__).resolve().parent.parent
BACKUP_DIR = BASE_DIR / 'backups'
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

# Load environment
env_file = BASE_DIR / '.env'
if env_file.exists():
    with open(env_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip())

database_url = os.environ.get('DATABASE_URL', f"sqlite:///{BASE_DIR / 'db.sqlite3'}")
parsed = urlparse(database_url)
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

def backup_sqlite(db_path: Path):
    if not db_path.exists():
        print(f"Error: SQLite database file not found at {db_path}")
        return False

    target_gz = BACKUP_DIR / f"sqlite_backup_{timestamp}.db.gz"
    temp_backup = BACKUP_DIR / f"temp_{timestamp}.db"

    print(f"Starting atomic SQLite hot backup from {db_path}...")
    try:
        # Atomic hot backup using SQLite Online Backup API
        src_conn = sqlite3.connect(str(db_path))
        dst_conn = sqlite3.connect(str(temp_backup))
        with dst_conn:
            src_conn.backup(dst_conn)
        dst_conn.close()
        src_conn.close()

        # Compress with gzip
        with open(temp_backup, 'rb') as f_in:
            with gzip.open(target_gz, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)

        temp_backup.unlink()
        size_kb = target_gz.stat().st_size / 1024
        print(f"Backup SUCCESS: {target_gz} ({size_kb:.2f} KB)")
        return True
    except Exception as e:
        if temp_backup.exists():
            temp_backup.unlink()
        print(f"SQLite backup failed: {e}")
        return False

def backup_postgres(url: str):
    target_gz = BACKUP_DIR / f"postgres_backup_{timestamp}.sql.gz"
    print(f"Starting PostgreSQL backup to {target_gz}...")

    cmd = [
        'pg_dump',
        '--dbname', url,
        '--no-owner',
        '--no-privileges',
        '--clean',
        '--if-exists',
    ]

    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        with gzip.open(target_gz, 'wb') as f_out:
            shutil.copyfileobj(process.stdout, f_out)

        _, stderr = process.communicate()
        if process.returncode != 0:
            print(f"pg_dump error: {stderr.decode('utf-8', errors='replace')}")
            if target_gz.exists():
                target_gz.unlink()
            return False

        size_kb = target_gz.stat().st_size / 1024
        print(f"PostgreSQL backup SUCCESS: {target_gz} ({size_kb:.2f} KB)")
        return True
    except FileNotFoundError:
        print("Error: pg_dump executable not found in system PATH.")
        return False

def backup_mysql(parsed_url):
    target_gz = BACKUP_DIR / f"mysql_backup_{timestamp}.sql.gz"
    print(f"Starting MySQL backup (utf8mb4) to {target_gz}...")

    cmd = [
        'mysqldump',
        '--single-transaction',
        '--quick',
        '--default-character-set=utf8mb4',
        '--add-drop-table',
        '-h', parsed_url.hostname or '127.0.0.1',
        '-P', str(parsed_url.port or 3306),
        '-u', parsed_url.username or 'root',
    ]
    if parsed_url.password:
        cmd.append(f"-p{parsed_url.password}")

    db_name = parsed_url.path.lstrip('/')
    cmd.append(db_name)

    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        with gzip.open(target_gz, 'wb') as f_out:
            shutil.copyfileobj(process.stdout, f_out)

        _, stderr = process.communicate()
        if process.returncode != 0:
            print(f"mysqldump error: {stderr.decode('utf-8', errors='replace')}")
            if target_gz.exists():
                target_gz.unlink()
            return False

        size_kb = target_gz.stat().st_size / 1024
        print(f"MySQL backup SUCCESS: {target_gz} ({size_kb:.2f} KB)")
        return True
    except FileNotFoundError:
        print("Error: mysqldump executable not found in system PATH.")
        return False

def cleanup_old_backups(keep_count=14):
    """Keep the most recent N backup files and prune older ones."""
    backups = sorted(BACKUP_DIR.glob('*backup_*.*'), key=lambda p: p.stat().st_mtime, reverse=True)
    if len(backups) > keep_count:
        for old in backups[keep_count:]:
            print(f"Pruning expired backup: {old.name}")
            old.unlink()

def main():
    scheme = parsed.scheme.lower()
    success = False

    if scheme in ('sqlite', 'sqlite3', ''):
        sqlite_file = Path(parsed.path) if parsed.path else BASE_DIR / 'db.sqlite3'
        if not sqlite_file.is_absolute():
            # If path starts with / on windows (e.g. /db.sqlite3), strip it
            clean_path = str(parsed.path).lstrip('/')
            sqlite_file = BASE_DIR / clean_path
        success = backup_sqlite(sqlite_file)
    elif 'postgres' in scheme:
        success = backup_postgres(database_url)
    elif 'mysql' in scheme:
        success = backup_mysql(parsed)
    else:
        print(f"Unsupported database scheme: {scheme}")
        sys.exit(1)

    if success:
        cleanup_old_backups(keep_count=14)
        print("Backup process completed successfully.")
        sys.exit(0)
    else:
        print("Backup process failed.")
        sys.exit(1)

if __name__ == '__main__':
    main()
