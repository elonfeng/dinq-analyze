# 学者姓名查询 API

该接口用于根据学者姓名查询学者的基本信息，包括 Google Scholar ID、照片 URL 和所属机构等。

## 接口信息

- **URL**: `{API_BASE_URL}/api/scholar/by-name`
- **方法**: GET 或 POST
- **认证要求**: 需要验证用户身份

## 请求参数

### GET 请求

| 参数名 | 类型 | 必填 | 描述 |
|-------|-----|------|------|
| name | string | 是 | 学者姓名，可以包含机构信息 |
| max_length | integer | 否 | 输入名称的最大长度限制，默认为 2000 |
| max_retries | integer | 否 | 最大重试次数，默认为 3 |

### POST 请求

请求体 (JSON):

```json
{
  "name": "学者姓名，可以包含机构信息"
}
```

## 输入格式说明

`name` 参数支持以下几种格式:

1. **仅学者姓名**（例如：`Timo Aila`）
2. **学者姓名和机构**（例如：`qiang wang, apple ai`）
3. **学者姓名、机构和其他信息**（例如：`qiang wang, apple ai, computer vision researcher`）

对于常见姓名，建议添加机构信息以提高匹配准确性。

## 响应格式

```json
{
  "scholar_id": "Google Scholar ID",
  "photo": "照片 URL",
  "name": "学者姓名",
  "affiliation": "所属机构"
}
```

如果查询失败，响应将包含错误信息：

```json
{
  "scholar_id": null,
  "photo": null,
  "name": "输入的学者姓名",
  "affiliation": "输入的机构信息（如果有）",
  "error": "错误信息"
}
```

## 示例

### 请求示例 (GET)

```
GET /api/scholar/by-name?name=qiang%20wang%2C%20apple%20ai
```

### 请求示例 (POST)

```
POST /api/scholar/by-name
Content-Type: application/json

{
  "name": "qiang wang, apple ai"
}
```

### 成功响应示例

```json
{
  "scholar_id": "Y-ql3zMAAAAJ",
  "photo": "https://scholar.googleusercontent.com/citations?view_op=view_photo&user=Y-ql3zMAAAAJ&citpid=3",
  "name": "Qiang Wang",
  "affiliation": "Apple AI"
}
```

### 失败响应示例

```json
{
  "scholar_id": null,
  "photo": null,
  "name": "John Smith",
  "affiliation": "MIT",
  "error": "No profiles found"
}
```

## 错误码

| 状态码 | 描述 |
|-------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 401 | 未授权 |
| 500 | 服务器内部错误 |

## 注意事项

1. 该接口需要用户认证，请在请求头中包含 `userid` 或 `Userid` 字段。
2. 对于常见姓名，建议添加机构信息以提高匹配准确性。
3. 该接口使用 OpenRouter API 调用多种 AI 模型来查找学者信息，可能需要一些时间来处理请求。
4. 如果多个模型都无法找到匹配的学者信息，将返回错误信息。
