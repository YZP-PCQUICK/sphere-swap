#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
import zipfile
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent              # swapweb/swap
PROJECT_ROOT = BASE_DIR.parent                          # swapweb/（swap同级目录）


def _prepare_and_backup():
    """启动前自动准备：
    1. data目录不存在时自动创建（数据库与媒体文件目录）
    2. 自动执行数据库迁移（SQLite库文件随迁移自动创建）
    3. 自动备份data文件夹为zip到 swap_buckup/，最多保留3份，超出删除最旧
    """
    data_dir = PROJECT_ROOT / 'data'
    data_dir.mkdir(parents=True, exist_ok=True)

    import django
    django.setup()
    from django.core.management import call_command

    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    # 手动执行migrate时不再重复迁移；其余命令（含runserver）自动迁移
    if cmd != 'migrate':
        call_command('migrate', interactive=False, verbosity=0)

    # 每次运行自动备份data文件夹
    try:
        backup_dir = PROJECT_ROOT / 'swap_buckup'
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        zip_path = backup_dir / f'data_{stamp}.zip'
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for p in sorted(data_dir.rglob('*')):
                if p.is_file():
                    # 压缩包内保留 data/ 前缀，解压后即得data文件夹
                    zf.write(p, p.relative_to(PROJECT_ROOT))

        # 最多同时存在3份备份，超出删除最旧的
        backups = sorted(backup_dir.glob('data_*.zip'))
        for old in backups[:-3]:
            try:
                old.unlink()
            except OSError:
                pass
    except OSError as e:
        print(f'[警告] 数据库备份失败，不影响服务启动: {e}')


def main():
    """Run administrative tasks."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "swapweb.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc

    # runserver自动重载的子进程（RUN_MAIN=true）不重复执行，保证每次启动只准备/备份一次
    if os.environ.get('RUN_MAIN') != 'true':
        _prepare_and_backup()

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
