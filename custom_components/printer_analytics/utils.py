from __future__ import annotations

import logging
import os
import re
import shutil
from pathlib import Path
from typing import Optional

LOGGER = logging.getLogger(__name__)


class SecureFileHandler:
    """安全的文件操作处理器 - 防止路径遍历和文件注入攻击"""

    # 危险字符黑名单（覆盖Windows和Linux）
    DANGEROUS_CHAR_PATTERN = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
    # URL不安全字符（%会导致URL编码解析失败，逗号/空格/中文在某些服务器上有问题）
    URL_UNSAFE_PATTERN = re.compile(r'[%,;#\s]')
    # 路径遍历检测模式
    PATH_TRAVERSAL_PATTERN = re.compile(r'\.\.')
    # 文件名长度限制（防止超长文件名导致系统问题）
    MAX_FILENAME_LENGTH = 200
    # 完整路径长度限制
    MAX_PATH_LENGTH = 4096

    @classmethod
    def sanitize_filename(cls, filename: str) -> str:
        if not filename:
            return 'unknown'
        safe = cls.DANGEROUS_CHAR_PATTERN.sub('_', filename)
        safe = cls.URL_UNSAFE_PATTERN.sub('_', safe)
        safe = cls.PATH_TRAVERSAL_PATTERN.sub('_', safe)
        safe = safe.strip(' ._')
        # 合并连续下划线
        safe = re.sub(r'_+', '_', safe)
        if len(safe) > cls.MAX_FILENAME_LENGTH:
            safe = safe[:cls.MAX_FILENAME_LENGTH]
        return safe or 'unknown'

    @classmethod
    def validate_path(cls, base_dir: str, filepath: str) -> Optional[str]:
        """
        验证目标路径是否在允许的基础目录内
        防止通过符号链接或相对路径逃逸出沙箱

        Args:
            base_dir: 允许的基础目录（绝对路径）
            filepath: 目标文件相对路径

        Returns:
            规范化后的绝对路径（如果安全），否则返回None
        """
        try:
            # 将基础目录转换为绝对路径并规范化（解析 .. 和符号链接）
            base = Path(base_dir).resolve()
            # 拼接目标路径
            target = (base / filepath).resolve()

            # 关键安全检查：确保最终路径在base目录内
            # 使用字符串比较确保路径前缀匹配且以分隔符结尾
            target_str = str(target)
            base_str = str(base) + os.sep

            if not target_str.startswith(base_str):
                LOGGER.warning(
                    "Path traversal attempt detected: %s (base: %s)",
                    target_str,
                    base_str,
                )
                return None

            # 检查路径总长度是否合理
            if len(target_str) > cls.MAX_PATH_LENGTH:
                LOGGER.warning("Path too long: %d chars", len(target_str))
                return None

            return target_str
        except (ValueError, OSError) as err:
            LOGGER.error("Path validation error: %s", err)
            return None

    @classmethod
    def safe_join(cls, base_dir: str, filename: str) -> Optional[str]:
        """
        安全的路径拼接组合：先消毒文件名，再验证路径安全性

        Args:
            base_dir: 允许的基础目录
            filename: 原始文件名

        Returns:
            安全的完整路径，如果不安全则返回None
        """
        safe_name = cls.sanitize_filename(filename)
        return cls.validate_path(base_dir, safe_name)

    @classmethod
    def atomic_write(cls, filepath: str, content: bytes | str, encoding: str = 'utf-8') -> bool:
        """
        原子性写入文件（防止写入过程中崩溃导致文件损坏）

        实现原理：
        1. 先写入临时文件
        2. 刷新缓冲区确保数据落盘
        3. 原子重命名替换原文件（rename在大多数文件系统上是原子操作）

        Args:
            filepath: 目标文件路径
            content: 要写入的内容（bytes或str）
            encoding: 字符编码（仅对str有效）

        Returns:
            是否写入成功
        """
        try:
            dir_path = os.path.dirname(filepath)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)

            temp_path = f"{filepath}.tmp"

            # 写入临时文件
            with open(temp_path, 'wb' if isinstance(content, bytes) else 'w',
                      encoding=None if isinstance(content, bytes) else encoding) as f:
                f.write(content)
                f.flush()  # 强制刷新缓冲区
                os.fsync(f.fileno())  # 确保数据写入磁盘

            # 原子重命名（在POSIX系统上是原子操作）
            os.replace(temp_path, filepath)
            return True
        except Exception as err:
            LOGGER.error("Atomic write failed for %s: %s", filepath, err)
            # 清理临时文件（如果存在）
            temp_path = f"{filepath}.tmp"
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            return False


class BackupManager:
    """备份管理器 - 为重要数据提供备份恢复机制"""

    MAX_BACKUPS = 3  # 最大备份数量

    @classmethod
    def create_backup(cls, filepath: str) -> bool:
        """
        创建文件的备份（保留最近N个版本）

        Args:
            filepath: 要备份的文件路径

        Returns:
            是否备份成功
        """
        if not os.path.exists(filepath):
            return False

        try:
            # 创建备份目录
            backup_dir = os.path.dirname(filepath) + '.backups'
            os.makedirs(backup_dir, exist_ok=True)

            # 生成带时间戳的备份文件名
            from datetime import datetime, timezone
            timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
            basename = os.path.basename(filepath)
            backup_name = f"{basename}.{timestamp}.bak"
            backup_path = os.path.join(backup_dir, backup_name)

            # 复制文件到备份位置
            shutil.copy2(filepath, backup_path)
            LOGGER.info("Created backup: %s", backup_path)

            # 清理旧备份（只保留最近的N个）
            cls._cleanup_old_backups(backup_dir, basename)

            return True
        except Exception as err:
            LOGGER.error("Failed to create backup for %s: %s", filepath, err)
            return False

    @classmethod
    def restore_from_backup(cls, filepath: str) -> bool:
        """
        从最新的备份恢复文件

        Args:
            filepath: 要恢复的目标文件路径

        Returns:
            是否恢复成功
        """
        backup_dir = os.path.dirname(filepath) + '.backups'
        if not os.path.exists(backup_dir):
            return False

        try:
            basename = os.path.basename(filepath)
            # 查找所有备份文件
            backups = [
                f for f in os.listdir(backup_dir)
                if f.startswith(basename) and f.endswith('.bak')
            ]

            if not backups:
                return False

            # 按时间戳排序（最新的在后）
            backups.sort()
            latest_backup = os.path.join(backup_dir, backups[-1])

            # 从备份恢复
            shutil.copy2(latest_backup, filepath)
            LOGGER.info("Restored from backup: %s -> %s", latest_backup, filepath)
            return True
        except Exception as err:
            LOGGER.error("Failed to restore backup for %s: %s", filepath, err)
            return False

    @classmethod
    def _cleanup_old_backups(cls, backup_dir: str, prefix: str) -> None:
        """清理旧备份文件，只保留最近的N个"""
        try:
            backups = [
                f for f in os.listdir(backup_dir)
                if f.startswith(prefix) and f.endswith('.bak')
            ]

            # 按时间排序（旧的在前）
            backups.sort()

            # 删除超出数量限制的旧备份
            while len(backups) > cls.MAX_BACKUPS:
                old_backup = os.path.join(backup_dir, backups.pop(0))
                os.remove(old_backup)
                LOGGER.debug("Removed old backup: %s", old_backup)
        except Exception as err:
            LOGGER.warning("Failed to cleanup old backups: %s", err)


class URLValidator:
    """URL安全性验证器 - 防止SSRF攻击"""

    ALLOWED_SCHEMES = {'', '/'}  # 只允许相对路径（无scheme表示相对URL）

    @classmethod
    def validate_relative_url(cls, url: str) -> bool:
        """
        验证URL是否为安全的相对路径（防止SSRF攻击）

        SSRF（Server-Side Request Forgery）攻击原理：
        攻击者通过构造特殊URL（如 //evil.com/path），
        使服务器访问内部网络或外部恶意服务器。

        Args:
            url: 要验证的URL字符串

        Returns:
            URL是否安全
        """
        if not url:
            return True  # 空URL是安全的

        # 检查是否包含协议方案（http://, https://, ftp://等）
        if '://' in url:
            LOGGER.warning("Absolute URL detected (potential SSRF): %s", url[:50])
            return False

        # 检查是否以 // 开头（协议相对URL，可被浏览器用于SSRF）
        if url.startswith('//'):
            LOGGER.warning("Protocol-relative URL detected: %s", url[:50])
            return False

        # 检查是否包含控制字符（ASCII 0x00-0x1F）
        if re.search(r'[\x00-\x1f]', url):
            LOGGER.warning("URL contains control characters")
            return False

        return True
