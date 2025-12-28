# 邮件域名环境变量修复

## 🐛 问题描述

邮件模板中的验证链接使用了硬编码的域名：
```html
<a href="http://localhost:5001/verify-email?...">
```

这导致在生产环境中，用户收到的邮件链接仍然指向localhost，无法正常访问。

## 🔧 修复方案

### 1. 添加环境变量支持

**文件**: `server/services/email_service.py`

```python
from server.config.env_loader import get_env_var

# Get base URL from environment variables
BASE_URL = get_env_var('DINQ_API_DOMAIN', 'http://localhost:5001')
```

### 2. 修改邮件模板

#### 验证邮件链接
```html
<!-- 修改前 -->
<a href="http://localhost:5001/verify-email?code={verification_code}&email={to_email}&type={email_type}&user_id={user_id}">

<!-- 修改后 -->
<a href="{BASE_URL}/verify-email?code={verification_code}&email={to_email}&type={email_type}&user_id={user_id}">
```

#### 欢迎邮件链接
```html
<!-- 修改前 -->
<a href="https://dinq.io/dashboard" class="button">

<!-- 修改后 -->
<a href="{BASE_URL}/dashboard" class="button">
```

### 3. 添加日志记录

在EmailService初始化时记录当前使用的BASE_URL：
```python
def __init__(self):
    resend.api_key = RESEND_API_KEY
    logger.info("Email service initialized with Resend")
    logger.info(f"Using BASE_URL: {BASE_URL}")
```

## ✅ 环境配置

### 开发环境
```bash
# 不设置环境变量，使用默认值
# DINQ_API_DOMAIN 默认为 http://localhost:5001
```

### 生产环境
```bash
# 设置环境变量
export DINQ_API_DOMAIN=https://dinq.io

# 或在 .env 文件中
DINQ_API_DOMAIN=https://dinq.io
```

### 测试环境
```bash
# 可以设置为测试域名
export DINQ_API_DOMAIN=https://test.dinq.io
```

## 🧪 测试方法

### 方法1: 使用测试脚本
```bash
cd tests/verification
chmod +x test_email_domain_fix.sh
./test_email_domain_fix.sh
```

### 方法2: 手动测试不同环境

#### 测试默认环境
```bash
# 不设置环境变量
python new_server.py
# 发送邮件，检查链接是否为 http://localhost:5001
```

#### 测试生产环境
```bash
# 设置生产环境变量
export DINQ_API_DOMAIN=https://dinq.io
python new_server.py
# 发送邮件，检查链接是否为 https://dinq.io
```

### 方法3: 检查服务器日志
启动服务器时会看到：
```
INFO - Email service initialized with Resend
INFO - Using BASE_URL: http://localhost:5001
```

## 🎯 修复效果

### 修复前
- ❌ 邮件链接硬编码为localhost
- ❌ 生产环境用户无法访问链接
- ❌ 需要手动修改代码部署

### 修复后
- ✅ 邮件链接根据环境动态生成
- ✅ 支持开发/测试/生产环境
- ✅ 通过环境变量轻松配置
- ✅ 服务启动时显示当前配置

## 📧 邮件链接示例

### 开发环境
```
验证链接: http://localhost:5001/verify-email?code=123456&email=user@example.com&type=edu_email&user_id=user123
仪表板链接: http://localhost:5001/dashboard
```

### 生产环境
```
验证链接: https://dinq.io/verify-email?code=123456&email=user@example.com&type=edu_email&user_id=user123
仪表板链接: https://dinq.io/dashboard
```

## 🚀 部署指南

### 1. 开发环境部署
```bash
# 无需额外配置，使用默认值
python new_server.py
```

### 2. 生产环境部署
```bash
# 设置环境变量
export DINQ_API_DOMAIN=https://dinq.io

# 或在部署脚本中
echo "DINQ_API_DOMAIN=https://dinq.io" >> .env

# 启动服务
python new_server.py
```

### 3. Docker部署
```dockerfile
# Dockerfile
ENV DINQ_API_DOMAIN=https://dinq.io
```

```yaml
# docker-compose.yml
environment:
  - DINQ_API_DOMAIN=https://dinq.io
```

## 🔍 验证修复

### 1. 检查环境变量加载
```python
from server.config.env_loader import get_env_var
print(get_env_var('DINQ_API_DOMAIN', 'http://localhost:5001'))
```

### 2. 检查邮件服务配置
```python
from server.services.email_service import email_service
# 查看日志中的 "Using BASE_URL: ..." 信息
```

### 3. 发送测试邮件
```bash
curl -X POST "http://localhost:5001/api/verification/send-email-verification" \
  -H "Userid: test_user" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "email_type": "edu_email"
  }'
```

## 📝 注意事项

### 环境变量优先级
1. 系统环境变量
2. .env 文件
3. 默认值 (http://localhost:5001)

### 安全考虑
- 生产环境必须使用HTTPS
- 确保域名配置正确
- 验证SSL证书有效

### 兼容性
- 向后兼容，不影响现有功能
- 默认值保持开发环境可用
- 支持所有邮件类型

## 🎉 总结

通过这次修复，邮件服务现在支持：

1. **环境感知** - 根据部署环境自动调整链接
2. **配置灵活** - 通过环境变量轻松配置
3. **部署友好** - 无需修改代码即可适配不同环境
4. **调试便利** - 启动时显示当前配置

现在可以在任何环境中部署，用户都能收到正确的验证链接！🚀
