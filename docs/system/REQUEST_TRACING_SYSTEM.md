# 请求追踪系统 (Request Tracing System)

## 🎯 概述

DINQ项目现在支持全局请求追踪功能，为每个HTTP请求分配唯一的Trace ID，并在所有日志中自动包含这个ID。这个系统帮助开发者更容易地追踪和调试跨多个组件的请求流程。

## ✨ 主要特性

### 🔍 自动Trace ID生成
- 每个HTTP请求自动获得8位唯一Trace ID
- 支持客户端传递自定义Trace ID
- 线程安全，支持并发请求

### 📝 日志集成
- 所有日志自动包含Trace ID
- 支持请求上下文信息（用户ID、HTTP方法、路径等）
- 兼容现有日志系统

### 🌐 HTTP集成
- 支持`X-Trace-ID`请求头
- 响应头自动返回Trace ID
- 跨服务追踪支持

### 🧵 线程支持
- 自动处理线程切换
- 支持异步操作
- Context变量传播

## 🏗️ 系统架构

### 核心组件

#### 1. TraceContext (`server/utils/trace_context.py`)
```python
class TraceContext:
    @staticmethod
    def generate_trace_id() -> str
    @staticmethod
    def set_trace_id(trace_id: str) -> None
    @staticmethod
    def get_trace_id() -> Optional[str]
    @staticmethod
    def clear_trace_id() -> None
```

#### 2. TraceFormatter (`server/utils/logging_config.py`)
```python
class TraceFormatter(logging.Formatter):
    def format(self, record):
        # 自动添加trace ID和请求上下文到日志记录
```

#### 3. Flask中间件 (`server/app.py`)
```python
@app.before_request
def setup_request_tracing():
    # 为每个请求设置trace ID

@app.after_request
def finalize_request_and_add_headers(response):
    # 添加trace ID到响应头并记录请求完成
```

## 📋 日志格式

### 新的日志格式
```
2024-05-25 10:30:45,123 - [a1b2c3d4] - server.app - INFO - Request started: POST /api/upload-image [user:user123 | POST /api/upload-image]
2024-05-25 10:30:45,456 - [a1b2c3d4] - server.api.image_upload - INFO - File upload request from user: user123
2024-05-25 10:30:45,789 - [a1b2c3d4] - server.app - INFO - Request completed: POST /api/upload-image - Status: 200 [user:user123 | POST /api/upload-image]
```

### 格式说明
- `[a1b2c3d4]` - 8位Trace ID
- `[user:user123 | POST /api/upload-image]` - 请求上下文信息

## 🚀 使用方法

### 1. 在代码中使用Trace Logger

#### 基本使用
```python
from server.utils.trace_context import get_trace_logger

# 获取trace-aware logger
logger = get_trace_logger(__name__)

# 记录日志（自动包含trace ID）
logger.info("处理用户请求")
logger.error("发生错误", exc_info=True)
```

#### 在现有代码中替换
```python
# 原来的代码
import logging
logger = logging.getLogger(__name__)
logger.info("消息")

# 新的代码
from server.utils.trace_context import get_trace_logger
logger = get_trace_logger(__name__)
logger.info("消息")  # 自动包含trace ID
```

### 2. 客户端传递Trace ID

#### JavaScript示例
```javascript
// 生成或获取trace ID
const traceId = generateTraceId(); // 自定义函数

// 在请求中包含trace ID
fetch('/api/upload-image', {
    method: 'POST',
    headers: {
        'X-Trace-ID': traceId,
        'Userid': userId
    },
    body: formData
});

// 从响应中获取trace ID
response.headers.get('X-Trace-ID');
```

#### cURL示例
```bash
# 发送带有自定义trace ID的请求
curl -X POST "http://localhost:5001/api/upload-image" \
  -H "X-Trace-ID: custom123" \
  -H "Userid: user123" \
  -F "file=@document.pdf"

# 查看响应头中的trace ID
curl -I "http://localhost:5001/api/file-types"
```

### 3. 在多线程环境中使用

#### 线程传播
```python
from server.utils.trace_context import propagate_trace_to_thread
import threading

def worker_function():
    logger = get_trace_logger(__name__)
    logger.info("在新线程中工作")  # 自动包含原始trace ID

# 启动新线程并传播trace context
thread = threading.Thread(
    target=propagate_trace_to_thread(worker_function)
)
thread.start()
```

#### 手动管理
```python
from server.utils.trace_context import TraceContext

def background_task():
    # 在新线程中手动设置trace ID
    current_trace_id = TraceContext.get_trace_id()
    if current_trace_id:
        TraceContext.set_trace_id(current_trace_id)
    
    # 执行任务
    logger = get_trace_logger(__name__)
    logger.info("后台任务执行")
```

## 🔧 配置选项

### 环境变量
```bash
# 日志级别
LOG_LEVEL=INFO

# 日志目录
LOG_DIR=/var/log/dinq

# Axiom日志（可选）
AXIOM_ENABLED=true
AXIOM_DATASET=dinq
```

### 自定义Trace ID格式
```python
# 在server/utils/trace_context.py中修改
@staticmethod
def generate_trace_id() -> str:
    # 自定义格式：时间戳 + 随机数
    import time
    timestamp = str(int(time.time()))[-4:]  # 最后4位时间戳
    random_part = str(uuid.uuid4())[:4]     # 4位随机数
    return f"{timestamp}{random_part}"
```

## 🧪 测试和验证

### 运行测试脚本
```bash
cd tests/verification
python test_trace_id_functionality.py
```

### 手动测试
```bash
# 1. 启动服务器
python server/app.py

# 2. 发送测试请求
curl -X GET "http://localhost:5001/api/file-types" \
  -H "X-Trace-ID: test123" \
  -v

# 3. 检查日志文件
tail -f logs/dinq_allin_one.log | grep "test123"
```

### 验证清单
- [ ] 每个请求都有唯一的trace ID
- [ ] 日志中正确显示trace ID
- [ ] 响应头包含trace ID
- [ ] 自定义trace ID正确传递
- [ ] 并发请求trace ID隔离
- [ ] 线程切换时trace ID保持

## 📊 监控和分析

### 日志分析
```bash
# 查找特定trace ID的所有日志
grep "\[a1b2c3d4\]" logs/dinq_allin_one.log

# 统计每个trace ID的日志数量
grep -o "\[[a-z0-9]\{8\}\]" logs/dinq_allin_one.log | sort | uniq -c

# 查找错误相关的trace ID
grep "ERROR" logs/dinq_allin_one.log | grep -o "\[[a-z0-9]\{8\}\]"
```

### 性能监控
```python
# 在关键路径添加性能日志
import time
from server.utils.trace_context import get_trace_logger

logger = get_trace_logger(__name__)

start_time = time.time()
# 执行操作
operation_time = time.time() - start_time

logger.info(f"操作完成，耗时: {operation_time:.3f}秒")
```

## 🔍 故障排查

### 常见问题

#### 1. Trace ID未出现在日志中
**原因**: 使用了普通的logger而不是trace logger
**解决**: 使用`get_trace_logger(__name__)`

#### 2. 线程中trace ID丢失
**原因**: 新线程没有继承trace context
**解决**: 使用`propagate_trace_to_thread()`包装函数

#### 3. 自定义trace ID未生效
**原因**: 请求头名称错误或格式不正确
**解决**: 确保使用`X-Trace-ID`头，值为字符串

### 调试技巧

#### 1. 启用详细日志
```python
# 临时启用DEBUG级别
import logging
logging.getLogger('server.utils.trace_context').setLevel(logging.DEBUG)
```

#### 2. 检查trace context状态
```python
from server.utils.trace_context import TraceContext

# 在任何地方检查当前trace ID
current_id = TraceContext.get_trace_id()
print(f"当前Trace ID: {current_id}")
```

#### 3. 手动设置trace ID进行测试
```python
from server.utils.trace_context import TraceContext

# 设置测试trace ID
TraceContext.set_trace_id("debug123")

# 执行需要调试的代码
# ...

# 清除trace ID
TraceContext.clear_trace_id()
```

## 🚀 最佳实践

### 1. 日志记录
```python
# ✅ 推荐：使用trace logger
from server.utils.trace_context import get_trace_logger
logger = get_trace_logger(__name__)
logger.info("用户操作", extra={'action': 'upload', 'file_size': 1024})

# ❌ 不推荐：使用普通logger
import logging
logger = logging.getLogger(__name__)
logger.info("用户操作")  # 缺少trace ID
```

### 2. 错误处理
```python
try:
    # 执行操作
    result = process_request()
except Exception as e:
    logger = get_trace_logger(__name__)
    logger.error(f"请求处理失败: {str(e)}", exc_info=True)
    # trace ID会自动包含在错误日志中
```

### 3. 性能监控
```python
import time
from server.utils.trace_context import get_trace_logger

logger = get_trace_logger(__name__)

def monitored_function():
    start_time = time.time()
    try:
        # 执行操作
        result = expensive_operation()
        
        duration = time.time() - start_time
        logger.info(f"操作成功完成，耗时: {duration:.3f}秒")
        return result
        
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"操作失败，耗时: {duration:.3f}秒，错误: {str(e)}")
        raise
```

### 4. 外部服务调用
```python
import requests
from server.utils.trace_context import TraceContext, get_trace_logger

logger = get_trace_logger(__name__)

def call_external_service(url, data):
    # 获取当前trace ID
    trace_id = TraceContext.get_trace_id()
    
    # 传递给外部服务
    headers = {'X-Trace-ID': trace_id} if trace_id else {}
    
    logger.info(f"调用外部服务: {url}")
    
    try:
        response = requests.post(url, json=data, headers=headers)
        logger.info(f"外部服务响应: {response.status_code}")
        return response
    except Exception as e:
        logger.error(f"外部服务调用失败: {str(e)}")
        raise
```

## 📈 扩展功能

### 1. 分布式追踪
```python
# 未来可以扩展支持OpenTelemetry
from opentelemetry import trace
from server.utils.trace_context import TraceContext

def create_span(operation_name):
    trace_id = TraceContext.get_trace_id()
    # 创建span并关联trace ID
    # ...
```

### 2. 指标收集
```python
# 收集trace相关的指标
from collections import defaultdict
import time

trace_metrics = defaultdict(list)

def record_trace_metric(operation, duration):
    trace_id = TraceContext.get_trace_id()
    trace_metrics[trace_id].append({
        'operation': operation,
        'duration': duration,
        'timestamp': time.time()
    })
```

### 3. 自定义上下文
```python
# 扩展trace context包含更多信息
class ExtendedTraceContext(TraceContext):
    @staticmethod
    def set_user_context(user_id, user_role):
        # 设置用户上下文信息
        # ...
    
    @staticmethod
    def set_request_context(method, path, params):
        # 设置请求上下文信息
        # ...
```

## 📝 总结

请求追踪系统为DINQ项目提供了强大的调试和监控能力：

### 主要优势
1. **问题定位** - 通过trace ID快速定位问题
2. **性能分析** - 追踪请求的完整生命周期
3. **并发调试** - 区分并发请求的日志
4. **分布式支持** - 为未来的微服务架构做准备

### 使用建议
1. **统一使用** - 在所有新代码中使用trace logger
2. **逐步迁移** - 将现有代码逐步迁移到trace logger
3. **监控集成** - 结合监控系统使用trace ID
4. **文档维护** - 保持trace ID相关文档的更新

通过合理使用这个请求追踪系统，开发团队可以显著提高问题排查效率和系统可观测性！🚀

---

**最后更新**: 2024-05-25  
**版本**: 1.0  
**维护者**: 开发团队
