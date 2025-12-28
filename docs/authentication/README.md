# 认证系统文档

本仓库同时存在 **两套认证形态**：

1) **新架构（推荐，Gateway → dinq-dev）**
   - 前端只调 Gateway（`https://api.dinq.me`）
   - Gateway 校验 `Authorization: Bearer <jwt>`，并转发到 dinq（分析服务）时注入：
     - `X-User-ID`（必需）
     - `X-User-Tier`（可选）
   - dinq-dev **不再直接验证 Firebase/JWT**，仅信任上述 Header（见：`server/utils/auth.py`）

2) **旧架构（历史保留，dinq 直连）**
   - dinq 服务端自己验证 Firebase Token（本文档目录下的 Firebase 文档）

> 如果你在做本次“dinq 适配 gateway”的改造，请以 **新架构**为准；Firebase 文档仅用于旧服务维护。

## 📁 文档说明

### 🔐 核心认证文档

- **`FIREBASE_AUTHENTICATION_SYSTEM.md`** - Firebase认证系统完整文档
  - 系统架构和组件说明
  - 认证流程详解
  - 配置和部署指南
  - API使用说明
  - 安全考虑和最佳实践

## 🎯 认证系统概述

### 核心技术栈
- **Gateway JWT** - Gateway 对外统一认证（新架构）
- **X-User-ID / X-User-Tier** - Gateway → dinq 的用户上下文透传（新架构）
- **Firebase Authentication** - 旧架构认证（历史保留）

### 支持的认证方式
- 新架构：由 Gateway 决定（dinQ 不关心 token 形式）
- 旧架构：Firebase 支持邮箱密码、Google/GitHub OAuth 等

### 认证流程
#### 新架构（推荐）
1. **用户登录** - 前端获取 Gateway 的 JWT
2. **API 调用** - 前端对 Gateway 发送 `Authorization: Bearer <jwt>`
3. **Gateway 验证** - Gateway 校验 token 并解析出 `user_id/tier`
4. **转发到 dinq** - Gateway 注入 `X-User-ID/X-User-Tier`，并删除 `Authorization`
5. **dinq 授权** - dinq 仅校验 `X-User-ID` 是否存在，并将其写入 job.user_id，做 owner 校验

#### 旧架构（历史保留）
1. **用户登录** - 通过 Firebase 客户端 SDK 登录
2. **获取令牌** - 获取 Firebase ID Token
3. **API 调用** - 请求头携带 `Authorization: Bearer <firebase_token>`
4. **服务端验证** - dinq 使用 Firebase Admin SDK 验证
5. **用户识别** - 提取 user_id 并设置到请求上下文

## 🔧 快速开始

### 1. 环境配置
```bash
# 设置Firebase服务账户密钥
export FIREBASE_SERVICE_ACCOUNT_PATH=/path/to/service-account-key.json

# 或者设置密钥内容
export FIREBASE_SERVICE_ACCOUNT_KEY='{"type": "service_account", ...}'
```

### 2. 开发环境
```bash
# 开发环境可以跳过认证
export FIREBASE_SKIP_AUTH_IN_DEV=true
export ENVIRONMENT=development
```

### 3. 测试认证
```bash
# 测试认证端点
curl -X GET "http://localhost:5001/api/user/me" \
  -H "Authorization: Bearer YOUR_FIREBASE_TOKEN"

# 开发环境测试
curl -X GET "http://localhost:5001/api/user/me" \
  -H "Userid: test_user_123"
```

> 新架构下（dinq-dev behind gateway）请不要用上述 Firebase 示例直连 dinq。请用：
> - `Authorization: Bearer <gateway_jwt>` 调用 Gateway
> - 由 Gateway 负责注入 `X-User-ID` 给 dinq

## 📚 文档导航

### 🚀 快速入门
1. 阅读 `FIREBASE_AUTHENTICATION_SYSTEM.md` 了解整体架构
2. 查看配置说明设置开发环境
3. 参考API使用示例进行集成

### 🔍 深入了解
- **系统架构** - 了解认证系统的设计和实现
- **安全考虑** - 了解安全最佳实践
- **故障排除** - 解决常见的认证问题

### 💻 开发集成
- **客户端集成** - 前端如何集成Firebase认证
- **服务端集成** - 后端如何验证用户身份
- **API设计** - 如何设计需要认证的API

## 🔒 安全特性

### 令牌安全
- **自动过期** - ID Token默认1小时过期
- **签名验证** - 服务端验证令牌签名
- **权限控制** - 基于用户身份的权限控制

### 用户管理
- **用户注册** - 支持多种注册方式
- **邮箱验证** - 邮箱地址验证机制
- **密码安全** - Firebase处理密码安全

### 数据保护
- **传输加密** - HTTPS传输加密
- **存储安全** - Firebase安全存储用户数据
- **隐私保护** - 符合GDPR等隐私法规

## 🧪 测试和调试

### 测试工具
- **Firebase模拟器** - 本地测试Firebase功能
- **令牌生成器** - 生成测试用的ID Token
- **认证测试脚本** - 自动化认证测试

### 调试方法
- **日志分析** - 查看认证相关日志
- **令牌解析** - 解析和验证JWT令牌
- **错误排查** - 常见认证错误的解决方案

## 📊 监控和分析

### 认证指标
- **登录成功率** - 用户登录成功的比例
- **令牌验证时间** - 令牌验证的平均时间
- **认证错误分布** - 各种认证错误的分布

### 用户分析
- **活跃用户** - 活跃用户数量和趋势
- **登录方式** - 用户偏好的登录方式
- **地理分布** - 用户的地理分布情况

## 🚀 部署和运维

### 生产环境部署
- **环境变量配置** - 生产环境的环境变量设置
- **密钥管理** - 安全的密钥管理方案
- **监控告警** - 认证系统的监控和告警

### 维护和更新
- **密钥轮换** - 定期更新服务账户密钥
- **版本升级** - Firebase SDK的版本升级
- **安全补丁** - 及时应用安全补丁

## 🔄 文档维护

### 更新原则
- **及时更新** - 系统变更时及时更新文档
- **版本控制** - 记录文档的版本变更
- **准确性** - 确保文档与实际系统一致

### 贡献指南
- **问题反馈** - 发现文档问题及时反馈
- **内容补充** - 补充缺失的文档内容
- **最佳实践** - 分享认证相关的最佳实践

## 📞 支持和帮助

### 常见问题
- **认证失败** - 检查令牌是否有效
- **配置错误** - 检查环境变量设置
- **权限问题** - 检查用户权限配置

### 获取帮助
- **文档查阅** - 查阅详细的技术文档
- **日志分析** - 分析系统日志定位问题
- **社区支持** - 参考Firebase社区资源

Firebase认证系统为DINQ项目提供了安全、可靠、易用的用户认证解决方案！🔐
