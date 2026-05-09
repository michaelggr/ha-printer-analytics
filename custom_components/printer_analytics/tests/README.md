﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿# Printer Analytics 测试套件

本目录包含 Printer Analytics 插件的全面测试覆盖：

## 📁 测试结构

```
tests/
├── __init__.py                 # 测试初始化
├── conftest.py                # pytest fixtures 和共享配置
├── test_utils.py              # 安全工具类测试
├── test_coordinator.py         # 协调器核心逻辑测试
├── test_sensor.py             # 传感器实体测试
├── test_performance.py        # 性能基准测试
└── test_integration.py        # 集成测试
```

## 🧪 测试类型说明

### 1. 单元测试 (Unit Tests)
- **目标**: 验证单个函数/类的正确性
- **范围**: utils.py, coordinator.py 的独立方法
- **运行**: `pytest tests/test_utils.py -v`

### 2. 集成测试 (Integration Tests)
- **目标**: 验证模块间协作和数据流完整性
- **范围**: 完整的打印生命周期（开始→结束→统计）
- **运行**: `pytest tests/test_integration.py -v`

### 3. 性能测试 (Performance Tests)
- **目标**: 验证性能优化效果和资源使用
- **范围**: 统计计算速度、内存占用、响应时间
- **运行**: `pytest tests/test_performance.py -v`

## 🔧 运行测试

### 前置要求
```bash
pip install pytest pytest-asyncio pytest-cov aiohttp
```

### 运行全部测试
```bash
cd custom_components/printer_analytics
pytest tests/ -v --cov=. --cov-report=html
```

### 运行特定测试
```bash
# 只运行安全工具类测试
pytest tests/test_utils.py -v

# 只运行性能测试
pytest tests/test_performance.py -v

# 生成覆盖率报告
pytest tests/ --cov=. --cov-report=term-missing
```

## ✅ 测试覆盖目标

| 模块 | 目标覆盖率 | 当前状态 |
|------|-----------|---------|
| utils.py | ≥95% | ⏳ 待测试 |
| coordinator.py | ≥90% | ⏳ 待测试 |
| sensor.py | ≥85% | ⏳ 待测试 |

## 📊 性能基线

测试将验证以下性能指标：
- 统计计算时间 (2000条记录) < 50ms
- 内存占用增长 < 10MB/1000条记录
- 前端渲染时间 (100个数据点) < 100ms

## 🐛 调试测试失败

如果测试失败：
1. 查看详细错误信息：`pytest tests/ -v --tb=long`
2. 进入调试模式：`pytest tests/ --pdb`
3. 只运行失败的测试：`pytest tests/ --lf`
