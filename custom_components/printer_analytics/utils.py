from __future__ import annotations

import logging
import os
import re
import shutil
from pathlib import Path
from typing import Optional

LOGGER = logging.getLogger(__name__)


class SecureFileHandler:
    DANGEROUS_CHAR_PATTERN = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
    URL_UNSAFE_PATTERN = re.compile(r'[%,;#\s]')
    PATH_TRAVERSAL_PATTERN = re.compile(r'\.\.')
    MAX_FILENAME_LENGTH = 200
    MAX_PATH_LENGTH = 4096

    @classmethod
    def sanitize_filename(cls, filename: str) -> str:
        if not filename:
            return 'unknown'
        safe = cls.DANGEROUS_CHAR_PATTERN.sub('_', filename)
        safe = cls.URL_UNSAFE_PATTERN.sub('_', safe)
        safe = cls.PATH_TRAVERSAL_PATTERN.sub('_', safe)
        safe = safe.strip(' ._')
        safe = re.sub(r'_+', '_', safe)
        if len(safe) > cls.MAX_FILENAME_LENGTH:
            safe = safe[:cls.MAX_FILENAME_LENGTH]
        return safe or 'unknown'

    @classmethod
    def validate_path(cls, base_dir: str, filepath: str) -> Optional[str]:
        try:
            base = Path(base_dir).resolve()
            target = (base / filepath).resolve()
            target_str = str(target)
            base_str = str(base) + os.sep
            if not target_str.startswith(base_str):
                LOGGER.warning("Path traversal attempt detected: %s (base: %s)", target_str, base_str)
                return None
            if len(target_str) > cls.MAX_PATH_LENGTH:
                LOGGER.warning("Path too long: %d chars", len(target_str))
                return None
            return target_str
        except (ValueError, OSError) as err:
            LOGGER.error("Path validation error: %s", err)
            return None

    @classmethod
    def safe_join(cls, base_dir: str, filename: str) -> Optional[str]:
        safe_name = cls.sanitize_filename(filename)
        return cls.validate_path(base_dir, safe_name)

    @classmethod
    def atomic_write(cls, filepath: str, content: bytes | str, encoding: str = 'utf-8') -> bool:
        try:
            dir_path = os.path.dirname(filepath)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)
            temp_path = f"{filepath}.tmp"
            with open(temp_path, 'wb' if isinstance(content, bytes) else 'w',
                      encoding=None if isinstance(content, bytes) else encoding) as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, filepath)
            return True
        except Exception as err:
            LOGGER.error("Atomic write failed for %s: %s", filepath, err)
            temp_path = f"{filepath}.tmp"
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            return False


class BackupManager:
    MAX_BACKUPS = 3

    @classmethod
    def create_backup(cls, filepath: str) -> bool:
        if not os.path.exists(filepath):
            return False
        try:
            backup_dir = os.path.dirname(filepath) + '.backups'
            os.makedirs(backup_dir, exist_ok=True)
            from datetime import datetime, timezone
            timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
            basename = os.path.basename(filepath)
            backup_name = f"{basename}.{timestamp}.bak"
            backup_path = os.path.join(backup_dir, backup_name)
            shutil.copy2(filepath, backup_path)
            LOGGER.info("Created backup: %s", backup_path)
            cls._cleanup_old_backups(backup_dir, basename)
            return True
        except Exception as err:
            LOGGER.error("Failed to create backup for %s: %s", filepath, err)
            return False

    @classmethod
    def restore_from_backup(cls, filepath: str) -> bool:
        backup_dir = os.path.dirname(filepath) + '.backups'
        if not os.path.exists(backup_dir):
            return False
        try:
            basename = os.path.basename(filepath)
            backups = [f for f in os.listdir(backup_dir) if f.startswith(basename) and f.endswith('.bak')]
            if not backups:
                return False
            backups.sort()
            latest_backup = os.path.join(backup_dir, backups[-1])
            shutil.copy2(latest_backup, filepath)
            LOGGER.info("Restored from backup: %s -> %s", latest_backup, filepath)
            return True
        except Exception as err:
            LOGGER.error("Failed to restore backup for %s: %s", filepath, err)
            return False

    @classmethod
    def _cleanup_old_backups(cls, backup_dir: str, prefix: str) -> None:
        try:
            backups = [f for f in os.listdir(backup_dir) if f.startswith(prefix) and f.endswith('.bak')]
            backups.sort()
            while len(backups) > cls.MAX_BACKUPS:
                old_backup = os.path.join(backup_dir, backups.pop(0))
                os.remove(old_backup)
                LOGGER.debug("Removed old backup: %s", old_backup)
        except Exception as err:
            LOGGER.warning("Failed to cleanup old backups: %s", err)


class URLValidator:
    ALLOWED_SCHEMES = {'', '/'}

    @classmethod
    def validate_relative_url(cls, url: str) -> bool:
        if not url:
            return True
        if '://' in url:
            LOGGER.warning("Absolute URL detected (potential SSRF): %s", url[:50])
            return False
        if url.startswith('//'):
            LOGGER.warning("Protocol-relative URL detected: %s", url[:50])
            return False
        if re.search(r'[\x00-\x1f]', url):
            LOGGER.warning("URL contains control characters")
            return False
        return True
