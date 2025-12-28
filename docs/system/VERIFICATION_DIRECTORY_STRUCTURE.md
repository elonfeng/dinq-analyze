# 用户验证系统目录结构

为了更好地组织项目文件，我们已经将用户验证系统相关的文件重新整理到合适的目录中。

## 📁 新的目录结构

```
DINQ/
├── docs/verification/              # 📖 文档目录
│   ├── README.md                   # 文档导航
│   ├── USER_VERIFICATION_API.md    # API接口文档
│   ├── VERIFICATION_SYSTEM_SUMMARY.md  # 系统架构文档
│   ├── SESSION_FIX_SUMMARY.md      # 会话修复文档
│   ├── EMAIL_FIX_SUMMARY.md        # 邮件修复文档
│   └── EMAIL_LINK_FIX_SUMMARY.md   # 链接修复文档
│
├── tests/verification/             # 🧪 测试目录
│   ├── README.md                   # 测试说明
│   ├── test_verification_curl.sh   # CURL测试脚本
│   ├── run_verification_tests.sh   # 自动化测试
│   ├── test_email_fix.sh          # 邮箱测试
│   ├── test_email_link_fix.sh     # 链接测试
│   ├── verify_email_code.sh       # 验证码测试
│   ├── test_email_verification.html # HTML测试页面
│   └── test_verify_link.html      # 链接测试页面
│
├── scripts/verification/          # 🔧 脚本目录
│   ├── README.md                   # 脚本说明
│   ├── create_verification_tables.py # 数据库初始化
│   └── test_session_fix.py        # 会话测试
│
├── server/                        # 🖥️ 服务器代码
│   ├── api/
│   │   ├── user_verification_api.py
│   │   └── email_verification_page.py
│   ├── services/
│   │   ├── user_verification_service.py
│   │   └── email_service.py
│   ├── templates/
│   │   └── verify_email.html
│   └── utils/
│       └── database.py
│
└── src/models/                    # 📊 数据模型
    └── user_verification.py
```

## 🎯 目录用途

### 📖 docs/verification/
**用途**: 存放所有文档
- API接口文档
- 系统架构说明
- 技术问题修复记录
- 开发者指南

### 🧪 tests/verification/
**用途**: 存放所有测试文件
- 自动化测试脚本
- 手动测试工具
- HTML测试页面
- 测试数据和配置

### 🔧 scripts/verification/
**用途**: 存放管理和维护脚本
- 数据库初始化脚本
- 系统健康检查脚本
- 数据迁移工具
- 维护工具

## 🚀 快速开始

### 1. 查看文档
```bash
# 阅读系统概述
cat docs/verification/VERIFICATION_SYSTEM_SUMMARY.md

# 查看API文档
cat docs/verification/USER_VERIFICATION_API.md
```

### 2. 初始化系统
```bash
# 创建数据库表
python scripts/verification/create_verification_tables.py

# 测试系统
python scripts/verification/test_session_fix.py
```

### 3. 运行测试
```bash
# 运行完整测试
cd tests/verification
chmod +x run_verification_tests.sh
./run_verification_tests.sh

# 测试邮箱功能
chmod +x test_email_fix.sh
./test_email_fix.sh
```

### 4. 使用HTML测试页面
```bash
# 在浏览器中打开
open tests/verification/test_email_verification.html
```

## 📋 文件迁移记录

### 从根目录移动的文件

**测试文件** → `tests/verification/`:
- `test_verification_curl.sh`
- `run_verification_tests.sh`
- `test_email_fix.sh`
- `test_email_link_fix.sh`
- `verify_email_code.sh`
- `test_email_verification.html`
- `test_verify_link.html`

**文档文件** → `docs/verification/`:
- `USER_VERIFICATION_API.md`
- `VERIFICATION_SYSTEM_SUMMARY.md`
- `SESSION_FIX_SUMMARY.md`
- `EMAIL_FIX_SUMMARY.md`
- `EMAIL_LINK_FIX_SUMMARY.md`

**脚本文件** → `scripts/verification/`:
- `create_verification_tables.py`
- `test_session_fix.py`

**已删除的文件**:
- 重复的测试脚本
- 临时测试文件
- 过时的文档

## 🔄 使用指南

### 开发者
1. **查看文档**: `docs/verification/`
2. **运行测试**: `tests/verification/`
3. **维护脚本**: `scripts/verification/`

### 测试人员
1. **自动化测试**: `tests/verification/run_verification_tests.sh`
2. **手动测试**: `tests/verification/test_email_verification.html`
3. **特定功能测试**: 各种专门的测试脚本

### 运维人员
1. **系统初始化**: `scripts/verification/create_verification_tables.py`
2. **健康检查**: `scripts/verification/test_session_fix.py`
3. **问题排查**: `docs/verification/` 中的技术文档

## 📝 维护说明

### 添加新文件
- **文档**: 放入 `docs/verification/`
- **测试**: 放入 `tests/verification/`
- **脚本**: 放入 `scripts/verification/`

### 更新README
每个目录都有自己的README文件，添加新文件时请更新相应的README。

### 文件命名规范
- 测试文件: `test_*.sh` 或 `test_*.html`
- 脚本文件: 描述性名称，如 `create_*.py`
- 文档文件: 大写，如 `*_SUMMARY.md`

## 🎉 优势

### 组织性
- ✅ 文件分类清晰
- ✅ 易于查找和维护
- ✅ 避免根目录混乱

### 可维护性
- ✅ 每个目录有专门用途
- ✅ 相关文件集中管理
- ✅ 便于版本控制

### 可扩展性
- ✅ 易于添加新的测试
- ✅ 便于扩展文档
- ✅ 支持更多维护脚本

现在项目结构更加清晰，便于开发和维护！🚀
