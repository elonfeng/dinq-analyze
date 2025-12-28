# 产品演示请求 API 文档

本文档提供了产品演示请求 API 接口的详细信息，这些接口允许用户：
1. 获取演示请求表单所需的信息（包括国家列表等）
2. 提交演示请求
3. 查询用户的演示请求历史

## 目录

- [API 接口](#api-接口)
  - [获取表单信息](#获取表单信息)
  - [提交演示请求](#提交演示请求)
  - [获取我的演示请求](#获取我的演示请求)
- [数据模型](#数据模型)
  - [演示请求](#演示请求)
  - [国家信息](#国家信息)

## API 接口

### 获取表单信息

获取填写演示请求表单所需的信息，包括国家列表、职位选项和联系原因选项。

**URL**: `/api/demo-form/info`

**方法**: `GET`

**需要认证**: 否

**请求参数**: 无

**响应**:

```json
{
  "success": true,
  "data": {
    "countries": [
      {
        "name_zh": "阿富汗",
        "name_en": "Afghanistan",
        "code": "AF",
        "continent": "亚洲",
        "region": "西亚",
        "domain": ".af",
        "phone_code": "+93"
      },
      // ... more countries
    ],
    "job_titles": [
      "Professor",
      "Associate Professor",
      "Assistant Professor",
      "Researcher",
      "Research Scientist",
      "Data Scientist",
      "Software Engineer",
      "Product Manager",
      "Student",
      "Other"
    ],
    "contact_reasons": [
      "Academic research",
      "Commercial use",
      "Educational purposes",
      "Partnership opportunity",
      "General inquiry",
      "Other"
    ],
    "required_fields": [
      "email",
      "affiliation",
      "country",
      "job_title",
      "contact_reason"
    ],
    "optional_fields": [
      "additional_details",
      "marketing_consent"
    ]
  }
}
```

**错误响应**:

```json
{
  "success": false,
  "message": "发生错误: [错误信息]"
}
```

### 提交演示请求

提交用户的新演示请求。

**URL**: `/api/demo-request`

**方法**: `POST`

**需要认证**: 是（需要经过验证的用户）

**请求头**:
- `Content-Type: application/json`
- `Authorization: Bearer [令牌]` 或 `userid: [用户ID]`

**请求体**:

```json
{
  "email": "user@example.com",
  "affiliation": "University of Example",
  "country": "US",
  "job_title": "Researcher",
  "contact_reason": "Academic research",
  "additional_details": "I'm interested in using your product for my research project on AI ethics.",
  "marketing_consent": true
}
```

**必填字段**:
- `email`: 联系电子邮箱
- `affiliation`: 组织或机构
- `country`: 请求者所在国家（ISO 3166-1 alpha-2 代码）
- `job_title`: 请求者的职位
- `contact_reason`: 请求演示的原因

**可选字段**:
- `additional_details`: 关于请求的额外详细信息
- `marketing_consent`: 用户是否同意接收营销通讯（布尔值，默认为 false）

**响应**:

```json
{
  "success": true,
  "message": "Demo request submitted successfully",
  "data": {
    "id": 1,
    "user_id": "gAckWxWYazcI5k95n627hRBHB712",
    "email": "user@example.com",
    "affiliation": "University of Example",
    "country": "US",
    "job_title": "Researcher",
    "contact_reason": "Academic research",
    "additional_details": "I'm interested in using your product for my research project on AI ethics.",
    "marketing_consent": true,
    "status": "pending",
    "created_at": "2025-04-18T22:02:55",
    "updated_at": "2025-04-18T22:02:55"
  }
}
```

**错误响应**:

```json
{
  "success": false,
  "message": "缺少必填字段: email, affiliation"
}
```

```json
{
  "success": false,
  "message": "需要认证"
}
```

```json
{
  "success": false,
  "message": "数据库错误: [错误信息]"
}
```

### 获取我的演示请求

获取当前用户提交的所有演示请求。

**URL**: `/api/demo-request/my-requests`

**方法**: `GET`

**需要认证**: 是（需要经过验证的用户）

**请求头**:
- `Authorization: Bearer [令牌]` 或 `userid: [用户ID]`

**请求参数**: 无

**响应**:

```json
{
  "success": true,
  "data": {
    "requests": [
      {
        "id": 1,
        "user_id": "gAckWxWYazcI5k95n627hRBHB712",
        "email": "user@example.com",
        "affiliation": "University of Example",
        "country": "US",
        "job_title": "Researcher",
        "contact_reason": "Academic research",
        "additional_details": "I'm interested in using your product for my research project on AI ethics.",
        "marketing_consent": true,
        "status": "pending",
        "created_at": "2025-04-18T22:02:55",
        "updated_at": "2025-04-18T22:02:55"
      },
      // ... more requests
    ]
  }
}
```

**错误响应**:

```json
{
  "success": false,
  "message": "需要认证"
}
```

```json
{
  "success": false,
  "message": "发生错误: [错误信息]"
}
```

## 数据模型

### 演示请求

| 字段 | 类型 | 描述 | 是否必需 |
|-------|------|-------------|----------|
| id | 整数 | 演示请求的唯一标识符 | 自动生成 |
| user_id | 字符串 | 提交请求的用户ID | 是 |
| email | 字符串 | 联系电子邮箱 | 是 |
| affiliation | 字符串 | 组织或机构 | 是 |
| country | 字符串 | 请求者所在国家（ISO 3166-1 alpha-2 代码） | 是 |
| job_title | 字符串 | 请求者的职位 | 是 |
| contact_reason | 字符串 | 请求演示的原因 | 是 |
| additional_details | 字符串 | 关于请求的额外详细信息 | 否 |
| marketing_consent | 布尔值 | 用户是否同意接收营销通讯 | 否（默认为 false） |
| status | 字符串 | 请求状态（pending、contacted、completed） | 自动设置为 "pending" |
| created_at | 日期时间 | 请求创建时间 | 自动生成 |
| updated_at | 日期时间 | 请求最后更新时间 | 自动生成 |

### 国家信息

| 字段 | 类型 | 描述 |
|-------|------|-------------|
| name_zh | 字符串 | 国家的中文名称 |
| name_en | 字符串 | 国家的英文名称 |
| code | 字符串 | ISO 3166-1 alpha-2 代码 |
| continent | 字符串 | 国家所在的洲 |
| region | 字符串 | 洲内的区域 |
| domain | 字符串 | 互联网域名后缀 |
| phone_code | 字符串 | 国际电话区号 |

## 使用示例

### 前端表单实现

以下是使用这些 API 实现演示请求表单的示例：

1. 当表单组件加载时，获取表单信息：

```javascript
// 获取表单信息
async function fetchFormInfo() {
  try {
    const response = await fetch('http://localhost:5002/api/demo-form/info');
    const data = await response.json();

    if (data.success) {
      // 使用接收到的数据填充下拉菜单
      populateCountryDropdown(data.data.countries);
      populateJobTitleDropdown(data.data.job_titles);
      populateContactReasonDropdown(data.data.contact_reasons);
    } else {
      console.error('获取表单信息错误:', data.message);
    }
  } catch (error) {
    console.error('错误:', error);
  }
}
```

2. 当用户提交表单时，发送演示请求：

```javascript
// 提交演示请求
async function submitDemoRequest(formData) {
  try {
    const response = await fetch('http://localhost:5002/api/demo-request', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${userToken}` // 或 'userid': userId
      },
      body: JSON.stringify(formData)
    });

    const data = await response.json();

    if (data.success) {
      // 显示成功消息
      showSuccessMessage('演示请求提交成功！');
    } else {
      // 显示错误消息
      showErrorMessage(`错误: ${data.message}`);
    }
  } catch (error) {
    console.error('错误:', error);
    showErrorMessage('提交请求时发生错误。');
  }
}
```

3. 显示用户之前的演示请求：

```javascript
// 获取用户的演示请求
async function fetchMyDemoRequests() {
  try {
    const response = await fetch('http://localhost:5002/api/demo-request/my-requests', {
      headers: {
        'Authorization': `Bearer ${userToken}` // 或 'userid': userId
      }
    });

    const data = await response.json();

    if (data.success) {
      // 显示用户的演示请求
      displayDemoRequests(data.data.requests);
    } else {
      console.error('获取演示请求错误:', data.message);
    }
  } catch (error) {
    console.error('错误:', error);
  }
}
```
