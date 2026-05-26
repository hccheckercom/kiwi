"""S3 Backup Module — Integrated into Kiwi for seamless backup from anywhere."""
import boto3
import sys
from datetime import datetime
from pathlib import Path
from botocore.config import Config

# S3 Vietnix credentials
ENDPOINT = 'https://s3.vn-hcm-1.vietnix.cloud'
ACCESS_KEY = 'd67971143b8f53eaD99R'
SECRET_KEY = 'wOabV9BcCYa3eOtrgHbIlqYoXfwevd5D9BIXQyCq'
BUCKET = 'wezone01'

# Auto-detect project root
def find_project_root():
    """Find wezone project root by looking for .claude/kiwi/."""
    current = Path.cwd()
    for parent in [current] + list(current.parents):
        if (parent / '.claude' / 'kiwi').exists():
            return parent
    raise RuntimeError("Not in wezone project. Cannot find .claude/kiwi/")

ROOT_DIR = find_project_root()

# Backup subdirs
BACKUP_SUBDIRS = [
    'webstore-vn',
    'wezone-plugins',
    'docs',
    'scripts',
    'nginx-configs',
    'ssl',
    '.claude',
]

# Root files
BACKUP_ROOT_FILES = [
    '.gitignore',
    'backup_s3.py',
    'package.json',
    'package-lock.json',
    'GEMINI.md',
]

# Extra dirs
WP_LOCAL_ROOT = Path(r'C:\Users\Windows\Local Sites\wezone-dev\app\public')
EXTRA_DIRS = [
    {
        'path': WP_LOCAL_ROOT / 'wp-content' / 'themes',
        'prefix': 'wordpress-local/wp-content/themes',
    },
    {
        'path': WP_LOCAL_ROOT / 'wp-content' / 'uploads',
        'prefix': 'wordpress-local/wp-content/uploads',
    },
    {
        'path': ROOT_DIR / '1-tài liệu dự án',
        'prefix': '1-tai-lieu-du-an',
    },
]

WP_LOCAL_FILES = ['wp-config.php', '.htaccess']

LOG_FILE = ROOT_DIR / 'backup_s3.log'

SKIP_DIRS = {'.next', 'node_modules', '.git', '__pycache__', '.cache', 'dist', 'build',
             '.aider.tags.cache.v4', '.claude', '.zencoder', '.zenflow', '2-demo',
             'vendor', '.phpunit.cache'}
SKIP_EXTS = {'.pyc', '.log'}


def log(msg, f=None):
    line = datetime.now().strftime('%Y-%m-%d %H:%M:%S') + '  ' + msg
    try:
        print(line)
    except UnicodeEncodeError:
        print(line.encode('ascii', errors='replace').decode('ascii'))
    if f:
        f.write(line + '\n')
        f.flush()


def should_skip(path):
    for part in path.parts:
        if part in SKIP_DIRS:
            return True
    return path.suffix in SKIP_EXTS


def collect_files(base):
    return [p for p in base.rglob('*') if p.is_file() and not should_skip(p.relative_to(base))]


def guess_ct(path):
    return {
        '.html': 'text/html', '.css': 'text/css',
        '.js': 'application/javascript', '.mjs': 'application/javascript',
        '.ts': 'text/plain', '.tsx': 'text/plain', '.jsx': 'text/plain',
        '.json': 'application/json', '.md': 'text/markdown',
        '.txt': 'text/plain', '.sql': 'text/plain', '.lock': 'text/plain',
        '.svg': 'image/svg+xml', '.png': 'image/png',
        '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.ico': 'image/x-icon',
    }.get(path.suffix.lower(), 'application/octet-stream')


def make_client():
    cfg = Config(
        signature_version='s3v4',
        request_checksum_calculation='when_required',
        response_checksum_validation='when_required',
    )
    return boto3.client(
        's3',
        endpoint_url=ENDPOINT,
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        config=cfg,
        region_name='us-east-1',
    )


def backup():
    """Run full backup to S3."""
    date_str = datetime.now().strftime('%Y-%m-%d')
    base_prefix = 'backups/' + date_str + '/'

    with open(LOG_FILE, 'a', encoding='utf-8') as logf:
        log('=' * 60, logf)
        log('KIWI BACKUP - START', logf)
        log('Date   : ' + date_str, logf)
        log('Prefix : s3://' + BUCKET + '/' + base_prefix, logf)
        log('Source : ' + str(ROOT_DIR), logf)
        log('=' * 60, logf)

        s3 = make_client()

        try:
            s3.head_bucket(Bucket=BUCKET)
            log('[OK] Bucket "' + BUCKET + '" connected', logf)
        except Exception as e:
            log('[ERR] Cannot connect: ' + str(e), logf)
            sys.exit(1)

        all_files = []

        # 1) Backup subdirs
        for subdir_name in BACKUP_SUBDIRS:
            subdir = ROOT_DIR / subdir_name
            if not subdir.exists():
                log('[WARN] Skip missing dir: ' + subdir_name, logf)
                continue
            dir_files = collect_files(subdir)
            for f in dir_files:
                rel = f.relative_to(ROOT_DIR)
                s3_key = base_prefix + rel.as_posix()
                all_files.append((f, s3_key))
            log('[INFO] ' + subdir_name + ': ' + str(len(dir_files)) + ' files', logf)

        # 2) Backup root files
        root_file_count = 0
        for fname in BACKUP_ROOT_FILES:
            fpath = ROOT_DIR / fname
            if fpath.exists() and fpath.is_file():
                s3_key = base_prefix + fname
                all_files.append((fpath, s3_key))
                root_file_count += 1
        for fpath in ROOT_DIR.glob('*.md'):
            if fpath.is_file():
                s3_key = base_prefix + fpath.name
                all_files.append((fpath, s3_key))
                root_file_count += 1
        for fpath in ROOT_DIR.glob('*.txt'):
            if fpath.is_file() and fpath.suffix != '.log':
                s3_key = base_prefix + fpath.name
                all_files.append((fpath, s3_key))
                root_file_count += 1
        log('[INFO] Root files: ' + str(root_file_count) + ' files', logf)

        # 3) Backup extra dirs
        for extra in EXTRA_DIRS:
            epath = extra['path']
            eprefix = extra['prefix']
            if not epath.exists():
                log('[WARN] Skip missing extra dir: ' + str(epath), logf)
                continue
            efiles = []
            try:
                for p in epath.rglob('*'):
                    try:
                        if p.is_file() and not should_skip(p.relative_to(epath)):
                            efiles.append(p)
                    except (OSError, FileNotFoundError):
                        pass
            except (OSError, FileNotFoundError) as e:
                log('[WARN] Error scanning ' + str(epath) + ': ' + str(e), logf)
            for ef in efiles:
                rel = ef.relative_to(epath)
                s3_key = base_prefix + eprefix + '/' + rel.as_posix()
                all_files.append((ef, s3_key))
            log('[INFO] ' + eprefix + ': ' + str(len(efiles)) + ' files', logf)

        # 4) Backup WP local files
        wp_local_count = 0
        for fname in WP_LOCAL_FILES:
            fpath = WP_LOCAL_ROOT / fname
            if fpath.exists() and fpath.is_file():
                s3_key = base_prefix + 'wordpress-local/' + fname
                all_files.append((fpath, s3_key))
                wp_local_count += 1
        if wp_local_count:
            log('[INFO] wordpress-local root files: ' + str(wp_local_count) + ' files', logf)

        # Upload
        total = len(all_files)
        log('[INFO] TOTAL: ' + str(total) + ' files to upload', logf)

        ok = fail = 0
        for i, (local_path, s3_key) in enumerate(all_files, 1):
            try:
                with open(local_path, 'rb') as f:
                    body = f.read()
                s3.put_object(
                    Bucket=BUCKET,
                    Key=s3_key,
                    Body=body,
                    ContentType=guess_ct(local_path),
                )
                ok += 1
                if i % 100 == 0 or i == total:
                    log('  [' + str(i) + '/' + str(total) + '] OK  ' + s3_key, logf)
            except Exception as e:
                fail += 1
                log('  [' + str(i) + '/' + str(total) + '] ERR ' + s3_key + ' -> ' + str(e), logf)

        log('', logf)
        log('RESULT: OK=' + str(ok) + '  FAIL=' + str(fail) + '  TOTAL=' + str(total), logf)
        log('BACKUP ' + ('DONE' if fail == 0 else 'DONE WITH ERRORS'), logf)
        log('', logf)

        return fail == 0


if __name__ == '__main__':
    success = backup()
    sys.exit(0 if success else 1)
