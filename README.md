﻿# Bambu Lab 打印历史导出工具

Bambu Lab 3D 打印机的历史记录导出与分析工具，支持全量/增量下载打印历史，提供多维度统计分析。

## 功能特性

- **登录认证**：支持手机号/邮箱 + 验证码或密码登录 Bambu Lab 账号
- **历史下载**：全量或增量下载打印历史记录
- **数据导出**：导出为 CSV / JSON 格式
- **统计分析**：
  - 打印状态分布（成功/失败/取消）
  - 打印时长统计与趋势
  - 活动热力图（GitHub 风格）
  - 喷嘴尺寸使用分布
  - 超 500g 模型占比
  - 切片模式分布（云切片/本地切片）
  - 多色模型占比
  - 颜色使用量对比
- **保存统计图**：一键保存统计页为图片（PNG + 剪贴板）
- **HA 集成**：配套 [Printer Analytics (HACS)](https://github.com/michaelggr/ha-printer-analytics) 插件

## 下载安装

从 [GitHub Releases](https://github.com/michaelggr/bambu-print-history-export/releases/latest) 下载最新版本：

| 平台 | 文件 |
|------|------|
| Windows | `Bambu打印历史导出-x.x.x-win.zip` |

## 开发

```bash
# 安装依赖
npm install

# 启动开发模式（前端 + 后端）
npm run dev

# 启动 Electron 开发模式
npm run electron:dev

# 构建
npm run build

# 打包 Windows 安装包
npm run dist:win
```

## 相关项目

- [Printer Analytics (HACS)](https://github.com/michaelggr/ha-printer-analytics) — Home Assistant 打印分析集成

## 交流反馈

- **QQ 交流群**：[拓竹玩机群](https://qm.qq.com/q/9paJFuZbCE)
- **GitHub Issues**：[提交问题](https://github.com/michaelggr/bambu-print-history-export/issues)

## 许可证

MIT
