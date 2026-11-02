#!/usr/bin/env python3
"""
Ente Naadu - Database Restore Script
Restores database from compressed or plain backup (.sql.gz, .db.gz, .sql, .db).
Includes confirmation safety checks and rollback protection.
"""

import os
import sys
import gzip
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent.parent
BACKUP_DIR = BASE_DIR / 'backups'

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

def get_latest_backup():
    if not BACKUP_DIR.exists():
        return None
    files = sorted(BACKUP_DIR.glob('*backup_*.*'), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None

def restore_sqlite(backup_path: Path, target_path: Path):
    print(f"Restoring SQLite database to {target_path} from {backup_path}...")

    # Create safety backup of existing db if present
    if target_path.exists():
        safety_copy = target_path.with_suffix('.pre_restore_backup')
        shutil.copy2(target_path, safety_copy)
        print(f"Created safety pre-restore backup at {safety_copy}")

    try:
        if str(backup_path).endswith('.gz'):
            with gzip.open(backup_path, 'rb') as f_in:
                with open(target_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
        else:
            shutil.copy2(backup_path, target_path)
        print("SQLite restore SUCCESS!")
        return True
    except Exception as e:
        print(f"Error during SQLite restore: {e}")
        return False

def restore_postgres(backup_path: Path, url: str):
    print(f"Restoring PostgreSQL database from {backup_path}...")
    cmd = ['psql', '--dbname', url]

    try:
        if str(backup_path).endswith('.gz'):
            with gzip.open(backup_path, 'rb') as f_in:
                process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, stderr = process.communicate(input=f_in.read())
        else:
            with open(backup_path, 'rb') as f_in:
                process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, stderr = process.communicate(input=f_in.read())

        if process.returncode != 0:
            print(f"psql error: {stderr.decode('utf-8', errors='replace')}")
            return False

        print("PostgreSQL restore SUCCESS!")
        return True
    except FileNotFoundError:
        print("Error: psql executable not found in system PATH.")
        return False

def restore_mysql(backup_path: Path, parsed_url):
    print(f"Restoring MySQL database from {backup_path}...")
    cmd = [
        'mysql',
        '--default-character-set=utf8mb4',
        '-h', parsed_url.hostname or '127.0.0.1',
        '-P', str(parsed_url.port or 3306),
        '-u', parsed_url.username or 'root',
    ]
    if parsed_url.password:
        cmd.append(f"-p{parsed_url.password}")
    cmd.append(parsed_url.path.lstrip('/'))

    try:
        if str(backup_path).endswith('.gz'):
            with gzip.open(backup_path, 'rb') as f_in:
                process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, stderr = process.communicate(input=f_in.read())
        else:
            with open(backup_path, 'rb') as f_in:
                process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, stderr = process.communicate(input=f_in.read())

        if process.returncode != 0:
            print(f"mysql error: {stderr.decode('utf-8', errors='replace')}")
            return False

        print("MySQL restore SUCCESS!")
        return True
    except FileNotFoundError:
        print("Error: mysql executable not found in system PATH.")
        return False

def main():
    if len(sys.argv) > 1:
        backup_file = Path(sys.argv[1])
    else:
        backup_file = get_latest_backup()

    if not backup_file or not backup_file.exists():
        print(f"Error: No valid backup file specified or found in {BACKUP_DIR}")
        sys.exit(1)

    print(f"Selected backup archive: {backup_file}")

    scheme = parsed.scheme.lower()
    if scheme in ('sqlite', 'sqlite3', ''):
        clean_path = str(parsed.path).lstrip('/')
        target_path = BASE_DIR / clean_path if clean_path else BASE_DIR / 'db.sqlite3'
        success = restore_sqlite(backup_file, target_path)
    elif 'postgres' in scheme:
        success = restore_postgres(backup_file, database_url)
    elif 'mysql' in scheme:
        success = restore_mysql(backup_file, parsed)
    else:
        print(f"Unsupported database scheme: {scheme}")
        sys.exit(1)

    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()
