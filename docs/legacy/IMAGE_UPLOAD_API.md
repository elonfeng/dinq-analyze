# Image Upload API Documentation

这个API提供了图片上传到Supabase存储的功能，包括上传、删除和列表查看功能。

## 认证

所有API端点都需要用户认证。请在请求头中包含以下字段：

```
Userid: <user_id>
```

或

```
userid: <user_id>
```

## API 端点

### 1. 上传图片

**端点**: `POST /api/upload-image`

**描述**: 上传图片文件到Supabase存储

**请求格式**: `multipart/form-data`

**参数**:
- `file` (必需): 要上传的图片文件
- `bucket` (可选): 存储桶名称，默认为 'images'
- `folder` (可选): 文件夹路径

**支持的文件格式**: PNG, JPG, JPEG, GIF, WEBP, SVG

**文件大小限制**: 最大 10MB

**示例请求**:
```bash
curl -X POST http://localhost:5001/api/upload-image \
  -H "Userid: user123" \
  -F "file=@/path/to/image.png" \
  -F "bucket=demo" \
  -F "folder=profile"
```

**成功响应** (200):
```json
{
  "success": true,
  "data": {
    "id": "file_id",
    "path": "users/user123/profile/unique_filename.png",
    "fullPath": "images/users/user123/profile/unique_filename.png",
    "publicUrl": "https://rlkbxuuszlscnwagrsyx.supabase.co/storage/v1/object/public/images/users/user123/profile/unique_filename.png",
    "bucket": "images",
    "originalFilename": "image.png",
    "size": 12345,
    "contentType": "image/png",
    "uploadedBy": "user123"
  }
}
```

**错误响应**:
- `400`: 文件验证失败
- `500`: 服务器内部错误

### 2. 删除图片

**端点**: `DELETE /api/delete-image`

**描述**: 删除用户上传的图片

**请求格式**: `application/json`

**参数**:
- `path` (必需): 要删除的文件路径
- `bucket` (可选): 存储桶名称，默认为 'images'

**示例请求**:
```bash
curl -X DELETE http://localhost:5001/api/delete-image \
  -H "Userid: user123" \
  -H "Content-Type: application/json" \
  -d '{
    "path": "users/user123/profile/unique_filename.png",
    "bucket": "demo"
  }'
```

**成功响应** (200):
```json
{
  "success": true,
  "message": "File deleted successfully",
  "data": {
    "path": "users/user123/profile/unique_filename.png",
    "bucket": "demo"
  }
}
```

**错误响应**:
- `400`: 缺少必需参数
- `403`: 权限不足（只能删除自己的文件）
- `500`: 服务器内部错误

### 3. 列出图片

**端点**: `GET /api/list-images`

**描述**: 列出当前用户上传的图片

**查询参数**:
- `bucket` (可选): 存储桶名称，默认为 'images'
- `folder` (可选): 文件夹路径
- `limit` (可选): 返回文件数量限制，默认50，最大100

**示例请求**:
```bash
curl -X GET "http://localhost:5001/api/list-images?bucket=images&folder=profile&limit=20" \
  -H "Userid: user123"
```

**成功响应** (200):
```json
{
  "success": true,
  "data": {
    "files": [
      {
        "name": "unique_filename.png",
        "path": "users/user123/profile/unique_filename.png",
        "publicUrl": "https://rlkbxuuszlscnwagrsyx.supabase.co/storage/v1/object/public/images/users/user123/profile/unique_filename.png",
        "size": 12345,
        "contentType": "image/png",
        "lastModified": "2023-12-01T10:00:00Z",
        "created": "2023-12-01T10:00:00Z"
      }
    ],
    "count": 1,
    "bucket": "images",
    "path": "users/user123/profile"
  }
}
```

## 安全特性

1. **用户隔离**: 每个用户的文件存储在独立的目录中 (`users/{user_id}/`)
2. **权限控制**: 用户只能访问和删除自己的文件
3. **文件验证**: 检查文件类型和大小
4. **安全文件名**: 使用UUID生成唯一文件名，防止冲突和安全问题

## 文件组织结构

```
bucket/
└── users/
    └── {user_id}/
        ├── {folder}/
        │   └── {unique_filename}.{ext}
        └── {unique_filename}.{ext}
```

## 错误代码

- `400 Bad Request`: 请求参数错误或文件验证失败
- `403 Forbidden`: 权限不足
- `404 Not Found`: 文件不存在
- `429 Too Many Requests`: 请求过于频繁
- `500 Internal Server Error`: 服务器内部错误

## 使用示例

### JavaScript/前端示例

```javascript
// 上传图片
async function uploadImage(file, folder = '') {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('bucket', 'images');
  formData.append('folder', folder);

  const response = await fetch('/api/upload-image', {
    method: 'POST',
    headers: {
      'Userid': getCurrentUserId()
    },
    body: formData
  });

  return await response.json();
}

// 列出图片
async function listImages(folder = '', limit = 50) {
  const params = new URLSearchParams({
    bucket: 'images',
    folder: folder,
    limit: limit.toString()
  });

  const response = await fetch(`/api/list-images?${params}`, {
    headers: {
      'Userid': getCurrentUserId()
    }
  });

  return await response.json();
}

// 删除图片
async function deleteImage(filePath) {
  const response = await fetch('/api/delete-image', {
    method: 'DELETE',
    headers: {
      'Userid': getCurrentUserId(),
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      path: filePath,
      bucket: 'images'
    })
  });

  return await response.json();
}
```

### Python示例

```python
import requests

def upload_image(file_path, user_id, folder=''):
    with open(file_path, 'rb') as f:
        files = {'file': f}
        data = {'bucket': 'images', 'folder': folder}
        headers = {'Userid': user_id}
        
        response = requests.post(
            'http://localhost:5001/api/upload-image',
            files=files,
            data=data,
            headers=headers
        )
        
        return response.json()
```

## 注意事项

1. 确保Supabase存储桶已正确配置
2. 检查Supabase的存储策略和权限设置
3. 监控存储使用量，避免超出配额
4. 定期清理不需要的文件以节省存储空间
