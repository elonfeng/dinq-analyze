# Axiom 日志集成

本文档介绍了 DINQ 项目中的 Axiom 日志集成功能，包括配置、使用方法和最佳实践。

## 概述

DINQ 项目集成了 [Axiom](https://axiom.co/) 日志平台，用于集中收集、存储和分析应用程序日志。Axiom 提供了强大的日志搜索、可视化和告警功能，使开发团队能够更好地监控应用程序状态和排查问题。

## 配置

### 环境变量

在 `.env` 文件中配置以下环境变量：

```
# Axiom 日志配置
# Axiom API 令牌
AXIOM_TOKEN=your-axiom-token
# Axiom 数据集名称
AXIOM_DATASET=dinq_logs
# 是否启用 Axiom 日志 (true/false)
AXIOM_ENABLED=true
```

### 参数说明

- `AXIOM_TOKEN`：Axiom API 令牌，用于认证
- `AXIOM_DATASET`：Axiom 数据集名称，用于存储日志
- `AXIOM_ENABLED`：是否启用 Axiom 日志，可设置为 `true`、`false`、`yes`、`no`、`1`、`0`、`on`、`off`

## 使用方法

### 基本用法

项目的日志系统已经集成了 Axiom，只要启用了 Axiom 日志功能，所有通过标准日志记录器记录的日志都会自动发送到 Axiom 平台。

```python
import logging

# 获取日志记录器
logger = logging.getLogger(__name__)

# 记录日志
logger.info("这是一条信息日志")
logger.warning("这是一条警告日志")
logger.error("这是一条错误日志")
```

### 带上下文的日志记录

为了更好地利用 Axiom 的搜索和分析功能，可以使用带上下文的日志记录方法：

```python
from server.utils.axiom_logger import info, warning, error, debug

# 获取日志记录器
logger = logging.getLogger(__name__)

# 记录带上下文的日志
info(logger, "用户登录成功", {
    "user_id": "user_123",
    "ip_address": "192.168.1.1",
    "login_method": "password"
})

error(logger, "数据库连接失败", {
    "db_host": "db.example.com",
    "error_code": "CONNECTION_REFUSED"
}, exc_info=True)  # 包含异常堆栈
```

### 自定义数据集

默认情况下，所有日志都会发送到 `AXIOM_DATASET` 环境变量指定的数据集。对于模块特定的日志，系统会自动创建格式为 `{AXIOM_DATASET}_{module_name}` 的数据集。

## 最佳实践

### 结构化日志

为了充分利用 Axiom 的搜索和分析功能，建议使用结构化日志：

```python
from server.utils.axiom_logger import info

# 不推荐
logger.info(f"用户 {user_id} 执行了 {action} 操作，结果：{result}")

# 推荐
info(logger, f"用户操作", {
    "user_id": user_id,
    "action": action,
    "result": result,
    "duration_ms": duration
})
```

### 日志级别

- `DEBUG`：详细的调试信息，仅在开发环境使用
- `INFO`：常规信息，记录正常操作
- `WARNING`：警告信息，表示可能的问题
- `ERROR`：错误信息，表示操作失败
- `CRITICAL`：严重错误，表示应用程序可能无法继续运行

### 敏感信息处理

避免在日志中包含敏感信息，如密码、令牌、个人身份信息等。如果必须记录，请确保进行适当的脱敏处理。

## 查看日志

登录 [Axiom 控制台](https://app.axiom.co/)，选择相应的数据集，即可查看和搜索日志。

## 测试 Axiom 日志

项目提供了一个测试脚本，用于验证 Axiom 日志集成是否正常工作：

```bash
python tools/test_axiom_logging.py
```

运行此脚本后，可以在 Axiom 控制台查看生成的测试日志。

## 故障排除

### 日志未发送到 Axiom

1. 检查 `AXIOM_TOKEN` 是否正确
2. 检查 `AXIOM_ENABLED` 是否设置为 `true`
3. 检查网络连接是否正常
4. 查看应用程序日志中是否有 Axiom 相关的错误信息

### 批处理延迟

Axiom 日志处理器使用批处理机制，日志可能不会立即显示在 Axiom 控制台。默认情况下，日志会在以下情况下发送：

- 批处理大小达到 100 条
- 自上次发送后经过 5 秒

如果需要立即查看日志，可以等待几秒钟或增加日志数量。
