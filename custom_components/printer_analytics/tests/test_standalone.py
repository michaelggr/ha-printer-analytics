"""
独立安全工具类测试 - 无需Home Assistant依赖
可直接在本地运行验证核心安全功能
"""

import pytest
import os
import tempfile
import json
from pathlib import Path

# 直接导入utils模块（避免通过__init__.py导入HA）
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

# 使用条件导入以支持无HA环境
try:
    from utils import SecureFileHandler, BackupManager, URLValidator
    UTILS_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  无法导入utils模块: {e}")
    UTILS_AVAILABLE = False


@pytest.mark.skipif(not UTILS_AVAILABLE, reason="utils模块不可用")
class TestSecureFileHandlerSanitizeFilename:
    """文件名消毒功能测试"""

    def test_normal_filename(self):
        """正常文件名应保持不变"""
        assert SecureFileHandler.sanitize_filename("test.txt") == "test.txt"
        assert SecureFileHandler.sanitize_filename("document.pdf") == "document.pdf"
        assert SecureFileHandler.sanitize_filename("image_2024.jpg") == "image_2024.jpg"

    def test_dangerous_characters_replaced(self):
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
        """路径遍历序列（..）应被阻止"""
        result = SecureFileHandler.sanitize_filename("../../etc/passwd")
        assert ".." not in result
        assert "/" not in result and "\\" not in result

        result2 = SecureFileHandler.sanitize_filename("../secret/file.txt")
        assert ".." not in result2

    def test_control_characters_filtered(self):
        """控制字符应被过滤"""
        assert SecureFileHandler.sanitize_filename("test\x00file") == "testfile"
        assert SecureFileHandler.sanitize_filename("test\x1ffile") == "testfile"

    def test_empty_input_returns_default(self):
        """空输入应返回'unknown'"""
        assert SecureFileHandler.sanitize_filename("") == "unknown"
        assert SecureFileHandler.sanitize_filename(None) == "unknown"

    def test_whitespace_and_dots_trimmed(self):
        """首尾空格和点号应被移除"""
        assert SecureFileHandler.sanitize_filename("  test.txt  ") == "test.txt"
        assert SecureFileHandler.sanitize_filename(".hidden_file") == "hidden_file"
        assert SecureFileHandler.sanitize_filename("..test..") == "test"

    def test_long_filename_truncated(self):
        """超长文件名应被截断到MAX_FILENAME_LENGTH"""
        long_name = "a" * 300
        result = SecureFileHandler.sanitize_filename(long_name)
        assert len(result) <= SecureFileHandler.MAX_FILENAME_LENGTH
        assert result.endswith("a")

    def test_chinese_filename_preserved(self):
        """中文等非ASCII字符应保留"""
        assert "测试文档" in SecureFileHandler.sanitize_filename("测试文档.pdf")
        assert SecureFileHandler.sanitize_filename("打印记录_2024.json") == "打印记录_2024.json"

    def test_all_special_chars_sanitized(self):
        """纯特殊字符字符串应全部被替换"""
        result = SecureFileHandler.sanitize_filename("\\/:*?\"<>|")
        assert all(c not in result for c in "\\/:*?\"<>|")


@pytest.mark.skipif(not UTILS_AVAILABLE, reason="utils模块不可用")
class TestSecureFileHandlerPathValidation:
    """路径验证功能测试"""

    def test_safe_path_accepted(self, temp_dir):
        """合法路径应被接受并返回规范化路径"""
        result = SecureFileHandler.validate_path(temp_dir, "test.txt")
        assert result is not None
        assert result.endswith("test.txt")
        assert result.startswith(temp_dir)

    def test_path_traversal_blocked(self, temp_dir):
        """路径遍历攻击（../）应被阻止"""
        result = SecureFileHandler.safe_join(temp_dir, "../../etc/passwd")
        assert result is None

    def test_safe_join_combines_checks(self, temp_dir):
        """safe_join应结合消毒和验证两步检查"""
        # 包含危险字符 + 路径遍历
        result = SecureFileHandler.safe_join(temp_dir, "../../../etc/passwd")
        assert result is None

        # 正常文件名应该通过
        result = SecureFileHandler.safe_join(temp_dir, "normal_file.txt")
        assert result is not None
        assert "normal_file.txt" in result


@pytest.mark.skipif(not UTILS_AVAILABLE, reason="utils模块不可用")
class TestSecureFileHandlerAtomicWrite:
    """原子性写入功能测试"""

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
        """原子写入应支持字符串内容（自动编码）"""
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

        SecureFileHandler.atomic_write(filepath, b"original")
        success = SecureFileHandler.atomic_write(filepath, b"updated")

        assert success is True
        with open(filepath, 'rb') as f:
            assert f.read() == b"updated"


@pytest.mark.skipif(not UTILS_AVAILABLE, reason="utils模块不可用")
class TestBackupManager:
    """备份管理功能测试"""

    def test_create_backup_success(self, temp_dir):
        """创建备份应成功"""
        filepath = os.path.join(temp_dir, "data.json")

        # 创建原始文件
        with open(filepath, 'w') as f:
            json.dump({"version": 1, "data": "original"}, f)

        # 创建备份
        success = BackupManager.create_backup(filepath)
        assert success is True

        # 验证备份目录和文件存在
        backup_dir = filepath + '.backups'
        assert os.path.exists(backup_dir)
        backup_files = [f for f in os.listdir(backup_dir) if f.endswith('.bak')]
        assert len(backup_files) >= 1

    def test_restore_from_backup(self, temp_dir):
        """从备份恢复应成功"""
        filepath = os.path.join(temp_dir, "data.json")

        # 创建原始数据并备份
        original_data = {"version": 1, "data": "important"}
        with open(filepath, 'w') as f:
            json.dump(original_data, f)
        BackupManager.create_backup(filepath)

        # 损坏原始文件
        with open(filepath, 'w') as f:
            f.write("CORRUPTED DATA {{{")

        # 从备份恢复
        success = BackupManager.restore_from_backup(filepath)
        assert success is True

        # 验证数据恢复正确
        with open(filepath, 'r') as f:
            restored_data = json.load(f)
        assert restored_data["data"] == "original"

    def test_old_backups_cleaned(self, temp_dir):
        """超过MAX_BACKUPS(3)的旧备份应被清理"""
        filepath = os.path.join(temp_dir, "data.json")
        with open(filepath, 'w') as f:
            json.dump({"v": 1}, f)

        # 创建5个备份
        for i in range(5):
            BackupManager.create_backup(filepath)

        # 验证只保留3个
        backup_dir = filepath + '.backups'
        if os.path.exists(backup_dir):
            backup_files = [f for f in os.listdir(backup_dir) if f.endswith('.bak')]
            assert len(backup_files) <= BackupManager.MAX_BACKUPS

    def test_restore_nonexistent_returns_false(self, temp_dir):
        """不存在的备份应返回False"""
        filepath = os.path.join(temp_dir, "nonexistent.json")
        success = BackupManager.restore_from_backup(filepath)
        assert success is False


@pytest.mark.skipif(not UTILS_AVAILABLE, reason="utils模块不可用")
class TestURLValidator:
    """URL安全性验证器测试 - SSRF防护"""

    def test_relative_urls_allowed(self):
        """相对URL路径应被允许"""
        assert URLValidator.validate_relative_url("/api/camera_proxy/test") is True
        assert URLValidator.validate_relative_url("/local/image.jpg") is True
        assert URLValidator.validate_relative_url("path/to/resource") is True

    def test_empty_url_allowed(self):
        """空URL应被视为安全"""
        assert URLValidator.validate_relative_url("") is True
        assert URLValidator.validate_relative_url(None) is True

    def test_absolute_urls_with_protocol_blocked(self):
        """包含协议方案的绝对URL应被阻止"""
        assert URLValidator.validate_relative_url("http://evil.com/path") is False
        assert URLValidator.validate_relative_url("https://malicious.site/payload") is False
        assert URLValidator.validate_relative_url("ftp://files.hacker.com/data") is False

    def test_protocol_relative_urls_blocked(self):
        """协议相对URL（//开头）应被阻止（SSRF风险）"""
        assert URLValidator.validate_relative_url("//evil.com/path") is False
        assert URLValidator.validate_relative_url("//internal.network/secret") is False

    def test_control_characters_in_url_blocked(self):
        """包含控制字符的URL应被阻止"""
        assert URLValidator.validate_relative_url("/api/\x00path") is False
        assert URLValidator.validate_relative_url("/api/\x1fpath") is False

    def test_normal_ha_api_paths_allowed(self):
        """正常的Home Assistant API路径应全部通过"""
        valid_paths = [
            "/api/camera_proxy/camera.printer",
            "/local/printer_analytics/image.jpg",
            "/api/image/proxy/test",
            "printer-analytics/print_info/data.json",
        ]
        for path in valid_paths:
            assert URLValidator.validate_relative_url(path) is True, \
                f"路径应被允许: {path}"


@pytest.mark.skipif(not UTILS_AVAILABLE, reason="utils模块不可用")
class TestSecurityEdgeCases:
    """边界情况和安全专项测试"""

    def test_null_byte_injection_prevented(self):
        """Null字节注入攻击应被阻止"""
        result = SecureFileHandler.sanitize_filename("test\x00file.txt")
        assert "\x00" not in result

    def test_very_long_path_rejected(self, temp_dir):
        """超长路径（>4096字符）应被拒绝"""
        long_name = "a" * 5000
        result = SecureFileHandler.safe_join(temp_dir, long_name)
        assert result is None  # 超过MAX_PATH_LENGTH限制

    def test_concurrent_writes_safety(self, temp_dir):
        """并发写入操作不应导致异常或损坏"""
        import threading

        filepath = os.path.join(temp_dir, "concurrent.txt")
        results = []

        def write_thread(index):
            try:
                success = SecureFileHandler.atomic_write(
                    filepath,
                    f"data from thread {index}".encode()
                )
                results.append(success)
            except Exception as e:
                results.append(False)

        threads = [threading.Thread(target=write_thread, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 所有操作应成功（即使有些覆盖了其他）
        assert all(results), "并发写入存在失败"
        assert os.path.exists(filepath)


def run_quick_validation():
    """快速验证函数 - 不需要pytest也能运行"""
    if not UTILS_AVAILABLE:
        print("❌ 错误：无法导入utils模块")
        return False
    
    print("=" * 60)
    print("🔒 Printer Analytics 安全工具类快速验证")
    print("=" * 60)
    
    tests_passed = 0
    tests_failed = 0
    
    # 测试1: 文件名消毒
    try:
        assert SecureFileHandler.sanitize_filename("../../etc/passwd") == "____etc_passwd"
        assert SecureFileHandler.sanitize_filename("test/file.txt") == "test_file.txt"
        assert SecureFileHandler.sanitize_filename("") == "unknown"
        print("✅ 文件名消毒: 通过 (3/3)")
        tests_passed += 1
    except AssertionError as e:
        print(f"❌ 文件名消毒: 失败 - {e}")
        tests_failed += 1
    
    # 测试2: URL验证
    try:
        assert URLValidator.validate_relative_url("/api/test") == True
        assert URLValidator.validate_relative_url("http://evil.com") == False
        assert URLValidator.validate_relative_url("//attack.com") == False
        print("✅ URL验证(SSRF防护): 通过 (3/3)")
        tests_passed += 1
    except AssertionError as e:
        print(f"❌ URL验证: 失败 - {e}")
        tests_failed += 1
    
    # 测试3: 原子写入
    try:
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            fp = os.path.join(tmpdir, "atomic_test.txt")
            assert SecureFileHandler.atomic_write(fp, b"test data") == True
            with open(fp, 'rb') as f:
                assert f.read() == b"test data"
        print("✅ 原子性写入: 通过 (1/1)")
        tests_passed += 1
    except Exception as e:
        print(f"❌ 原子写入: 失败 - {e}")
        tests_failed += 1
    
    # 测试4: 备份管理
    try:
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            fp = os.path.join(tmpdir, "backup_test.json")
            with open(fp, 'w') as f:
                json.dump({"test": "data"}, f)
            
            assert BackupManager.create_backup(fp) == True
            
            # 模拟损坏
            with open(fp, 'w') as f:
                f.write("CORRUPTED")
            
            assert BackupManager.restore_from_backup(fp) == True
            
            with open(fp, 'r') as f:
                data = json.load(f)
            assert data["test"] == "data"
        print("✅ 备份管理: 通过 (1/1)")
        tests_passed += 1
    except Exception as e:
        print(f"❌ 备份管理: 失败 - {e}")
        tests_failed += 1
    
    print("=" * 60)
    total = tests_passed + tests_failed
    print(f"\n📊 结果汇总:")
    print(f"   ✅ 通过: {tests_passed}/{total}")
    print(f"   ❌ 失败: {tests_failed}/{total}")
    
    if tests_failed == 0:
        print("\n🎉 所有核心安全功能验证通过！可以安全上传到服务器。")
        return True
    else:
        print("\n⚠️  存在失败的测试，请检查后再上传。")
        return False


if __name__ == "__main__":
    # 支持两种运行方式：
    # 1. python test_standalone.py (快速验证，无需pytest)
    # 2. pytest test_standalone.py -v (完整测试报告)
    import sys
    if '--quick' in sys.argv or len(sys.argv) == 1:
        success = run_quick_validation()
        sys.exit(0 if success else 1)
    else:
        pytest.main([__file__, "-v", "--tb=short"] + sys.argv[1:])
