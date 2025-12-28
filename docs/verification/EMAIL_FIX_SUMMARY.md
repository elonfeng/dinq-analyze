# 邮箱验证错误修复总结

## 🐛 问题描述

在发送邮箱验证时出现错误：
```
Error sending verification email to aihehe123@gmail.com: name 'to_email' is not defined
```

## 🔍 问题原因

在`server/services/email_service.py`的`_get_verification_email_content`方法中，HTML模板使用了`{to_email}`变量，但该变量没有传递给方法。

**问题代码位置**：
- 文件：`server/services/email_service.py`
- 行号：208
- 问题：HTML模板中使用`{to_email}`但方法参数中没有这个变量

## 🔧 修复方案

### 1. 修改方法签名
```python
# 修改前
def _get_verification_email_content(self, verification_code: str, email_type: str, user_name: str = None) -> tuple[str, str]:

# 修改后  
def _get_verification_email_content(self, verification_code: str, email_type: str, user_name: str = None, to_email: str = None) -> tuple[str, str]:
```

### 2. 更新方法调用
```python
# 修改前
subject, html_content = self._get_verification_email_content(
    verification_code, email_type, user_name
)

# 修改后
subject, html_content = self._get_verification_email_content(
    verification_code, email_type, user_name, to_email
)
```

## ✅ 修复后的完整流程

现在邮箱验证流程应该正常工作：

1. **发送验证码** → 生成6位数字验证码并发送邮件
2. **用户收到邮件** → 包含验证码的美观HTML邮件
3. **验证邮箱** → 用户输入验证码完成验证

## 🧪 测试方法

### 方法1: 使用HTML测试页面
```bash
# 在浏览器中打开
open test_email_verification.html
```

### 方法2: 使用JavaScript控制台
```javascript
// 在浏览器控制台中运行
// 1. 加载测试脚本
// 2. 运行: testEmailOnly()
```

### 方法3: 使用CURL脚本
```bash
# 测试邮箱验证修复
chmod +x test_email_fix.sh
./test_email_fix.sh

# 验证收到的验证码
chmod +x verify_email_code.sh
./verify_email_code.sh 123456  # 替换为实际验证码
```

### 方法4: 手动CURL命令

#### 发送验证码
```bash
curl -X POST "http://localhost:5001/api/verification/send-email-verification" \
  -H "Userid: LtXQ0x62DpOB88r1x3TL329FbHk1" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "aihehe123@gmail.com",
    "email_type": "edu_email"
  }'
```

#### 验证邮箱
```bash
curl -X POST "http://localhost:5001/api/verification/verify-email" \
  -H "Userid: LtXQ0x62DpOB88r1x3TL329FbHk1" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "aihehe123@gmail.com",
    "email_type": "edu_email",
    "verification_code": "你收到的验证码"
  }'
```

## 📧 邮箱类型说明

确保使用正确的邮箱类型：

- `edu_email`: 教育邮箱（求职者）
- `company_email`: 公司邮箱（求职者）
- `recruiter_company_email`: 招聘方公司邮箱

## 🎯 预期结果

修复后应该看到：

1. **发送验证码成功**：
```json
{
  "success": true,
  "data": {
    "message": "Verification email sent successfully.",
    "email": "aihehe123@gmail.com",
    "email_type": "edu_email"
  }
}
```

2. **收到邮件**：美观的HTML邮件包含6位数字验证码

3. **验证成功**：
```json
{
  "success": true,
  "data": {
    "message": "Email verified successfully.",
    "email": "aihehe123@gmail.com",
    "email_type": "edu_email",
    "verified": true
  }
}
```

## 🚀 完整测试流程

使用Fetch API的完整测试流程：

```javascript
// 1. 开始验证
await fetch('http://localhost:5001/api/verification/start', {
  method: 'POST',
  headers: {
    'Userid': 'LtXQ0x62DpOB88r1x3TL329FbHk1',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({ user_type: 'job_seeker' })
});

// 2. 更新基本信息
await fetch('http://localhost:5001/api/verification/update-step', {
  method: 'POST',
  headers: {
    'Userid': 'LtXQ0x62DpOB88r1x3TL329FbHk1',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    step: 'basic_info',
    data: {
      full_name: '张三',
      current_role: '研究员',
      current_title: '博士研究生'
    },
    advance_to_next: true
  })
});

// 3. 发送邮箱验证
await fetch('http://localhost:5001/api/verification/send-email-verification', {
  method: 'POST',
  headers: {
    'Userid': 'LtXQ0x62DpOB88r1x3TL329FbHk1',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    email: 'aihehe123@gmail.com',
    email_type: 'edu_email'
  })
});

// 4. 验证邮箱（使用收到的验证码）
await fetch('http://localhost:5001/api/verification/verify-email', {
  method: 'POST',
  headers: {
    'Userid': 'LtXQ0x62DpOB88r1x3TL329FbHk1',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    email: 'aihehe123@gmail.com',
    email_type: 'edu_email',
    verification_code: '你收到的验证码'
  })
});
```

现在邮箱验证功能应该完全正常工作了！🎉
