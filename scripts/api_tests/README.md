# API 测试工具

这个目录包含了用于测试 DINQ 系统各种 API 的工具。

## 等待列表 API 测试

### 脚本说明

1. **test_waiting_list_api.py** - Python 测试脚本，测试所有等待列表 API 功能
   - 加入等待列表
   - 获取等待列表状态
   - 获取等待列表条目
   - 更新等待列表条目状态

2. **test_waiting_list.sh** - Shell 脚本，用于运行 Python 测试脚本
   - 自动检查并安装必要的 Python 包
   - 支持各种命令行参数，如指定主机、端口等

### 使用方法

```bash
./test_waiting_list.sh
```

这将使用默认参数（主机: localhost，端口: 5001）运行测试。

### 自定义参数

```bash
./test_waiting_list.sh --host HOST --port PORT --user-id USER_ID --admin-id ADMIN_ID
```

参数说明：
- `--host HOST`: 指定 API 主机地址（默认: localhost）
- `--port PORT`: 指定 API 端口（默认: 5001）
- `--user-id USER_ID`: 指定测试用户 ID（默认: test_user_id）
- `--admin-id ADMIN_ID`: 指定管理员用户 ID（默认: admin_user_id）

## 依赖项

- Python 3.6+
- requests

`test_waiting_list.sh` 脚本会自动检查并安装这些依赖项。

## 注意事项

1. 确保 API 服务器正在运行，并且可以从运行测试的机器访问
2. 测试脚本会创建真实的等待列表条目，并将其状态更新为"已批准"
3. 如果你在生产环境中运行测试，请注意这一点
