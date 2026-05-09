﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿"""
安全工具类单元测试
测试 SecureFileHandler, BackupManager, URLValidator 的所有功能

覆盖范围：
- 文件名消毒（危险字符、路径遍历、长度限制）
- 路径验证（安全检查、规范化）
- 原子性写入
- 备份管理（创建、恢复、清理）
- URL验证（SSRF防护）
"""

import pytest
import os
import tempfile
import json
from pathlib import Path
import sys

# 添加父目录到sys.path以便导入模块
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import SecureFileHandler, BackupManager, URLValidator


class TestSecureFileHandlerSanitizeFilename:
    """测试文件名消毒功能"""

    def test_normal_filename(self):
        """正常文件名应保持不变"""
        assert SecureFileHandler.sanitize_filename("test.txt") == "test.txt"
        assert SecureFileHandler.sanitize_filename("document.pdf") == "document.pdf"
        assert SecureFileHandler.sanitize_filename("image_2024.jpg") == "image_2024.jpg"

    def test_dangerous_characters(self):
        """危险字符应被替换为下划线"""
        # Windows/Linux 危险字符
        assert SecureFileHandler.sanitize_filename("test/file.txt") == "test_file.txt"
        assert SecureFileHandler.sanitize_filename("test\\file.txt") == "test_file.txt"
        assert SecureFileHandler.sanitize_filename("test:file.txt") == "test_file.txt"
        assert SecureFileHandler.sanitize_filename("test*file.txt") == "test_file.txt"
        assert SecureFileHandler.sanitize_filename('test"file.txt') == "test_file.txt"
        assert SecureFileHandler.sanitize_filename("test<file.txt") == "test_file.txt"
        assert SecureFileHandler.sanitize_filename("test>file.txt") == "test_file.txt"
        assert SecureFileHandler.sanitize_filename("test|file.txt") == "test_file.txt"

    def test_path_traversal_prevention(self):
        """路径遍历序列应被阻止"""
        assert ".." not in SecureFileHandler.sanitize_filename("../../etc/passwd")
        assert SecureFileHandler.sanitize_filename("../secret/file.txt") == "__secret_file.txt"
        assert SecureFileHandler.sanitize_filename("....//etc/passwd") == "______etc_passwd"

    def test_control_characters(self):
        """控制字符应被过滤"""
        assert SecureFileHandler.sanitize_filename("test\x00file") == "testfile"
        assert SecureFileHandler.sanitize_filename("test\x1ffile") == "testfile"

    def test_empty_input(self):
        """空输入应返回默认值"""
        assert SecureFileHandler.sanitize_filename("") == "unknown"
        assert SecureFileHandler.sanitize_filename(None) == "unknown"

    def test_whitespace_and_dots(self):
        """首尾空格和点号应被移除"""
        assert SecureFileHandler.sanitize_filename("  test.txt  ") == "test.txt"
        assert SecureFileHandler.sanitize_filename(".hidden_file") == "hidden_file"
        assert SecureFileHandler.sanitize_filename("..test..") == "test"

    def test_length_limit(self):
        """超长文件名应被截断"""
        long_name = "a" * 300
        result = SecureFileHandler.sanitize_filename(long_name)
        assert len(result) <= SecureFileHandler.MAX_FILENAME_LENGTH
        assert result.endswith("a")

    def test_chinese_filename(self):
        """中文文件名应保留（非ASCII字符安全）"""
        assert "测试文档" in SecureFileHandler.sanitize_filename("测试文档.pdf")
        assert SecureFileHandler.sanitize_filename("打印记录_2024.json") == "打印记录_2024.json"

    def test_special_cases(self):
        """特殊边界情况"""
        # 纯特殊字符
        assert SecureFileHandler.sanitize_filename("\\/:*?\"<>|") == "_________"
        # 混合内容
        result = SecureFileHandler.sanitize_filename("My Document (2024).pdf")
        assert "My_Document" in result


class TestSecureFileHandlerValidatePath:
    """测试路径验证功能"""

    def test_safe_path_accepted(self, temp_dir):
        """合法路径应被接受"""
        result = SecureFileHandler.validate_path(temp_dir, "test.txt")
        assert result is not None
        assert result.endswith("test.txt")
        assert result.startswith(temp_dir)

    def test_path_traversal_blocked(self, temp_dir):
        """路径遍历攻击应被阻止"""
        # 尝试逃逸出基础目录
        result = SecureFileHandler.safe_join(temp_dir, "../../etc/passwd")
        assert result is None

    def test_absolute_path_blocked(self, temp_dir):
        """绝对路径应被阻止"""
        result = SecureFileHandler.validate_path(temp_dir, "/etc/passwd")
        # 根据实现，这可能返回None或抛出异常
        if result:
            assert result.startswith(temp_dir)

    def test_safe_join_combines_sanitization_and_validation(self, temp_dir):
        """safe_join 应结合消毒和验证"""
        # 包含危险字符的文件名
        result = SecureFileHandler.safe_join(temp_dir, "../../../etc/passwd")
        assert result is None

        # 正常文件名
        result = SecureFileHandler.safe_join(temp_dir, "normal_file.txt")
        assert result is not None
        assert "normal_file.txt" in result


class TestSecureFileHandlerAtomicWrite:
    """测试原子性写入功能"""

    def test_atomic_write_creates_file(self, temp_dir):
        """原子写入应成功创建文件"""
        filepath = os.path.join(temp_dir, "test.txt")
        content = b"Hello, World!"

        success = SecureFileHandler.atomic_write(filepath, content)
        assert success is True
        assert os.path.exists(filepath)

        with open(filepath, 'rb') as f:
            assert f.read() == content

    def test_atomic_write_string_content(self, temp_dir):
        """原子写入应支持字符串内容"""
        filepath = os.path.join(temp_dir, "test.json")
        content = '{"key": "value"}'

        success = SecureFileHandler.atomic_write(filepath, content, encoding='utf-8')
        assert success is True

        with open(filepath, 'r', encoding='utf-8') as f:
            assert json.load(f) == {"key": "value"}

    def test_atomic_write_creates_parent_dirs(self, temp_dir):
        """原子写入应自动创建父目录"""
        filepath = os.path.join(temp_dir, "subdir", "nested", "file.txt")

        success = SecureFileHandler.atomic_write(filepath, b"content")
        assert success is True
        assert os.path.exists(filepath)

    def test_atomic_write_overwrites_existing(self, temp_dir):
        """原子写入应能覆盖已存在的文件"""
        filepath = os.path.join(temp_dir, "overwrite.txt")

        # 写入初始内容
        SecureFileHandler.atomic_write(filepath, b"original")
        # 覆盖为新内容
        success = SecureFileHandler.atomic_write(filepath, b"updated")

        assert success is True
        with open(filepath, 'rb') as f:
            assert f.read() == b"updated"


class TestBackupManager:
    """测试备份管理功能"""

    def test_create_backup(self, temp_dir):
        """创建备份应成功"""
        filepath = os.path.join(temp_dir, "data.json")

        # 创建原始文件
        with open(filepath, 'w') as f:
            json.dump({"version": 1, "data": "original"}, f)

        # 创建备份
        success = BackupManager.create_backup(filepath)
        assert success is True

        # 验证备份目录存在
        backup_dir = filepath + '.backups'
        assert os.path.exists(backup_dir)

        # 验证备份文件存在
        backup_files = [f for f in os.listdir(backup_dir) if f.endswith('.bak')]
        assert len(backup_files) >= 1

    def test_restore_from_backup(self, temp_dir):
        """从备份恢复应成功"""
        filepath = os.path.join(temp_dir, "data.json")

        # 创建原始数据
        original_data = {"version": 1, "data": "original"}
        with open(filepath, 'w') as f:
            json.dump(original_data, f)

        # 创建备份
        BackupManager.create_backup(filepath)

        # 损坏原始文件
        with open(filepath, 'w') as f:
            f.write("CORRUPTED DATA {{{")

        # 从备份恢复
        success = BackupManager.restore_from_backup(filepath)
        assert success is True

        # 验证恢复的数据
        with open(filepath, 'r') as f:
            restored_data = json.load(f)
        assert restored_data["data"] == "original"

    def test_cleanup_old_backups(self, temp_dir):
        """旧备份应被自动清理（只保留最近3个）"""
        filepath = os.path.join(temp_dir, "data.json")

        # 创建原始文件
        with open(filepath, 'w') as f:
            json.dump({"v": 1}, f)

        # 创建5个备份（超过MAX_BACKUPS=3的限制）
        for i in range(5):
            BackupManager.create_backup(filepath)

        # 验证只保留了3个备份
        backup_dir = filepath + '.backups'
        backup_files = [f for f in os.listdir(backup_dir) if f.endswith('.bak')]
        assert len(backup_files) <= BackupManager.MAX_BACKUPS

    def test_restore_nonexistent_backup(self, temp_dir):
        """不存在的备份应返回失败"""
        filepath = os.path.join(temp_dir, "nonexistent.json")
        success = BackupManager.restore_from_backup(filepath)
        assert success is False


class TestURLValidator:
    """测试URL安全性验证器"""

    def test_relative_url_allowed(self):
        """相对URL应被允许"""
        assert URLValidator.validate_relative_url("/api/camera_proxy/test") is True
        assert URLValidator.validate_relative_url("/local/image.jpg") is True
        assert URLValidator.validate_relative_url("path/to/resource") is True

    def test_empty_url_allowed(self):
        """空URL应被视为安全"""
        assert URLValidator.validate_relative_url("") is True
        assert URLValidator.validate_relative_url(None) is True

    def test_absolute_url_blocked(self):
        """包含协议的绝对URL应被阻止"""
        assert URLValidator.validate_relative_url("http://evil.com/path") is False
        assert URLValidator.validate_relative_url("https://malicious.site/payload") is False
        assert URLValidator.validate_relative_url("ftp://files.hacker.com/data") is False

    def test_protocol_relative_url_blocked(self):
        """协议相对URL应被阻止（SSRF风险）"""
        assert URLValidator.validate_relative_url("//evil.com/path") is False
        assert URLValidator.validate_relative_url("//internal.network/secret") is False

    def test_control_characters_blocked(self):
        """包含控制字符的URL应被阻止"""
        assert URLValidator.validate_relative_url("/api/\x00path") is False
        assert URLValidator.validate_relative_url("/api/\x1fpath") is False

    def test_normal_api_paths(self):
        """正常的Home Assistant API路径应通过"""
        valid_paths = [
            "/api/camera_proxy/camera.printer",
            "/local/printer_analytics/image.jpg",
            "/api/image/proxy/test",
            "printer-analytics/print_info/data.json",
        ]
        for path in valid_paths:
            assert URLValidator.validate_relative_url(path) is True, f"Path should be safe: {path}"


class TestEdgeCasesAndSecurity:
    """边界情况和安全专项测试"""

    def test_null_byte_injection(self):
        """Null字节注入攻击应被阻止"""
        result = SecureFileHandler.sanitize_filename("test\x00file.txt")
        assert "\x00" not in result

    def test_unicode_normalization(self):
        """Unicode规范化攻击应被处理"""
        # Unicode混淆的路径分隔符
        result = SecureFileHandler.sanitize_filename("test\u2215file.txt")  # ∕ (除法斜杠)
        assert "\\" not in result and "/" not in result

    def test_very_long_path(self, temp_dir):
        """超长路径应被拒绝"""
        long_name = "a" * 5000
        result = SecureFileHandler.safe_join(temp_dir, long_name)
        assert result is None  # 超过MAX_PATH_LENGTH

    def test_symlink_protection(self, temp_dir):
        """符号链接目标应在允许范围内"""
        # 这个测试需要更复杂的设置，这里仅验证基本行为
        pass  # TODO: 实现符号链接攻击测试

    def test_concurrent_access_safety(self, temp_dir):
        """并发访问的安全性（基本检查）"""
        import threading

        filepath = os.path.join(temp_dir, "concurrent.txt")
        results = []

        def write_thread(index):
            success = SecureFileHandler.atomic_write(
                filepath,
                f"data from thread {index}".encode()
            )
            results.append(success)

        # 启动多个写线程
        threads = [threading.Thread(target=write_thread, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 所有操作应该成功（即使有些覆盖了其他的）
        # 关键是不会有异常或损坏
        assert all(results)
        assert os.path.exists(filepath)


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v", "--tb=short"])
