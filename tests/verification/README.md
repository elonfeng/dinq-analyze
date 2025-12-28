# 用户验证系统测试

这个目录包含用户验证系统的所有测试文件。

## 📁 文件说明

### 🧪 测试脚本

- **`test_verification_curl.sh`** - 完整的CURL测试脚本（交互式）
- **`run_verification_tests.sh`** - 自动化API测试脚本
- **`test_email_fix.sh`** - 邮箱验证功能测试
- **`test_email_link_fix.sh`** - 邮箱链接验证测试
- **`test_email_domain_fix.sh`** - 邮箱域名环境变量测试
- **`verify_email_code.sh`** - 验证邮箱验证码脚本
- **`test_env_vars.py`** - 环境变量加载测试
- **`test_file_upload_optimization.py`** - 文件上传优化测试

### 🌐 HTML测试页面

- **`test_email_verification.html`** - 邮箱验证测试页面
- **`test_verify_link.html`** - 邮箱链接测试页面

## 🚀 使用方法

### 1. 运行完整测试
```bash
cd tests/verification
chmod +x run_verification_tests.sh
./run_verification_tests.sh
```

### 2. 测试邮箱验证
```bash
cd tests/verification
chmod +x test_email_fix.sh
./test_email_fix.sh
```

### 3. 使用HTML测试页面
```bash
# 在浏览器中打开
open tests/verification/test_email_verification.html
```

### 4. 测试邮箱域名环境变量
```bash
cd tests/verification
chmod +x test_email_domain_fix.sh
./test_email_domain_fix.sh
```

### 5. 测试环境变量加载
```bash
cd tests/verification
python test_env_vars.py
```

### 6. 测试文件上传优化
```bash
cd tests/verification
python test_file_upload_optimization.py
```

### 7. 验证收到的验证码
```bash
cd tests/verification
chmod +x verify_email_code.sh
./verify_email_code.sh 123456  # 替换为实际验证码
```

## 📋 测试前准备

1. **启动服务器**：
   ```bash
   python new_server.py
   ```

2. **确保数据库表已创建**：
   ```bash
   python scripts/verification/create_verification_tables.py
   ```

3. **配置环境变量**：
   - Resend API密钥
   - MySQL数据库连接
   - Firebase认证
   - DINQ_API_DOMAIN (可选，默认为 http://localhost:5001)

## 🎯 测试用户

所有测试脚本使用以下测试用户：
- **用户ID**: `LtXQ0x62DpOB88r1x3TL329FbHk1`
- **测试邮箱**: `aihehe123@gmail.com`

## 📊 测试覆盖

- ✅ 获取验证状态
- ✅ 开始验证流程
- ✅ 更新验证步骤
- ✅ 发送邮箱验证码
- ✅ 验证邮箱
- ✅ 完成验证流程
- ✅ 获取统计信息
- ✅ 邮箱链接验证
- ✅ 环境变量配置
- ✅ 动态域名支持
- ✅ 文件上传功能
- ✅ 多文件类型支持
- ✅ 文件大小限制

## 🔧 故障排除

如果测试失败，请检查：

1. **服务器是否运行**：`http://localhost:5001`
2. **数据库连接**：检查MySQL配置
3. **邮件服务**：检查Resend API密钥
4. **用户认证**：检查Firebase配置

## 📝 添加新测试

要添加新的测试脚本：

1. 在此目录创建新的测试文件
2. 添加执行权限：`chmod +x your_test.sh`
3. 更新此README文件
4. 遵循现有的测试模式和用户ID
