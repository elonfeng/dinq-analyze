# 文件上传API优化

## 🎯 优化目标

将原本只支持图片的上传API扩展为支持多种文件类型，包括PDF、文档、表格等，同时优化文件大小限制和默认配置。

## 🔧 主要优化内容

### 1. 扩展支持的文件类型

#### 原来支持的类型
```python
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'}
```

#### 优化后支持的类型
```python
ALLOWED_EXTENSIONS = {
    # Images
    'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'bmp', 'tiff', 'ico',
    # Documents
    'pdf', 'doc', 'docx', 'txt', 'rtf', 'odt',
    # Spreadsheets
    'xls', 'xlsx', 'csv', 'ods',
    # Presentations
    'ppt', 'pptx', 'odp',
    # Archives
    'zip', 'rar', '7z', 'tar', 'gz',
    # Other
    'json', 'xml', 'yaml', 'yml'
}
```

### 2. 文件分类系统

添加了文件分类功能，便于组织和管理：

```python
FILE_CATEGORIES = {
    'images': {'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'bmp', 'tiff', 'ico'},
    'documents': {'pdf', 'doc', 'docx', 'txt', 'rtf', 'odt'},
    'spreadsheets': {'xls', 'xlsx', 'csv', 'ods'},
    'presentations': {'ppt', 'pptx', 'odp'},
    'archives': {'zip', 'rar', '7z', 'tar', 'gz'},
    'data': {'json', 'xml', 'yaml', 'yml'}
}
```

### 3. 文件大小限制调整

```python
# 原来: 10MB
MAX_FILE_SIZE = 10 * 1024 * 1024

# 优化后: 5MB
MAX_FILE_SIZE = 5 * 1024 * 1024
```

### 4. 默认存储桶更改

```python
# 原来: 'images'
bucket_name = request.form.get('bucket', 'images')

# 优化后: 'demo'
bucket_name = request.form.get('bucket', 'demo')
```

### 5. 增强的响应数据

#### 原来的响应
```json
{
  "success": true,
  "data": {
    "path": "users/123/file.jpg",
    "publicUrl": "https://...",
    "originalFilename": "file.jpg",
    "size": 12345,
    "contentType": "image/jpeg"
  }
}
```

#### 优化后的响应
```json
{
  "success": true,
  "data": {
    "path": "users/123/file.pdf",
    "publicUrl": "https://...",
    "originalFilename": "document.pdf",
    "filename": "abc123.pdf",
    "extension": "pdf",
    "category": "documents",
    "size": 12345,
    "sizeFormatted": "12.1 KB",
    "contentType": "application/pdf",
    "folder": "documents",
    "uploadedBy": "user123"
  }
}
```

### 6. 新增工具函数

#### 文件分类函数
```python
def get_file_category(filename: str) -> str:
    """获取文件类别"""
```

#### 文件大小格式化函数
```python
def format_file_size(size_bytes: int) -> str:
    """格式化文件大小为人类可读格式"""
```

#### 分类描述函数
```python
def get_category_description(category: str) -> str:
    """获取文件分类的描述"""
```

### 7. 改进的错误信息

#### 原来的错误信息
```
File type not allowed. Allowed types: png, jpg, jpeg, gif, webp, svg
```

#### 优化后的错误信息
```
File type not allowed. Supported file types:
Images: bmp, gif, ico, jpeg, jpg, png, svg, tiff, webp
Documents: doc, docx, odt, pdf, rtf, txt
Spreadsheets: csv, ods, xls, xlsx
Presentations: odp, ppt, pptx
Archives: 7z, gz, rar, tar, zip
Data: json, xml, yaml, yml
```

### 8. 新增API端点

#### `/api/file-types` - 获取文件类型信息

**请求**:
```bash
GET /api/file-types
```

**响应**:
```json
{
  "success": true,
  "data": {
    "maxFileSize": 5242880,
    "maxFileSizeFormatted": "5.0 MB",
    "defaultBucket": "demo",
    "categories": {
      "images": {
        "extensions": ["bmp", "gif", "ico", "jpeg", "jpg", "png", "svg", "tiff", "webp"],
        "count": 9,
        "description": "Image files including photos, graphics, and icons"
      },
      "documents": {
        "extensions": ["doc", "docx", "odt", "pdf", "rtf", "txt"],
        "count": 6,
        "description": "Text documents and PDFs"
      }
    },
    "allExtensions": ["7z", "bmp", "csv", "doc", "docx", ...]
  }
}
```

## 🧪 测试方法

### 1. 运行自动化测试
```bash
cd tests/verification
python test_file_upload_optimization.py
```

### 2. 手动测试不同文件类型

#### 测试PDF上传
```bash
curl -X POST "http://localhost:5001/api/upload-image" \
  -H "Userid: LtXQ0x62DpOB88r1x3TL329FbHk1" \
  -F "file=@document.pdf" \
  -F "bucket=demo" \
  -F "folder=documents"
```

#### 测试Excel文件上传
```bash
curl -X POST "http://localhost:5001/api/upload-image" \
  -H "Userid: LtXQ0x62DpOB88r1x3TL329FbHk1" \
  -F "file=@spreadsheet.xlsx" \
  -F "bucket=demo" \
  -F "folder=spreadsheets"
```

### 3. 测试文件大小限制
```bash
# 创建一个6MB的测试文件 (应该失败)
dd if=/dev/zero of=large_file.pdf bs=1M count=6

curl -X POST "http://localhost:5001/api/upload-image" \
  -H "Userid: LtXQ0x62DpOB88r1x3TL329FbHk1" \
  -F "file=@large_file.pdf"
```

### 4. 获取文件类型信息
```bash
curl -X GET "http://localhost:5001/api/file-types"
```

## 📊 支持的文件类型详情

### 图片文件 (Images)
- **格式**: PNG, JPG, JPEG, GIF, WebP, SVG, BMP, TIFF, ICO
- **用途**: 头像、图标、照片、图表等
- **特点**: 支持各种常见图片格式

### 文档文件 (Documents)
- **格式**: PDF, DOC, DOCX, TXT, RTF, ODT
- **用途**: 简历、证书、报告、论文等
- **特点**: 支持主流文档格式

### 表格文件 (Spreadsheets)
- **格式**: XLS, XLSX, CSV, ODS
- **用途**: 数据表、统计报告、财务表格等
- **特点**: 支持Excel和开源格式

### 演示文件 (Presentations)
- **格式**: PPT, PPTX, ODP
- **用途**: 演示文稿、项目展示等
- **特点**: 支持PowerPoint和开源格式

### 压缩文件 (Archives)
- **格式**: ZIP, RAR, 7Z, TAR, GZ
- **用途**: 文件打包、批量上传等
- **特点**: 支持常见压缩格式

### 数据文件 (Data)
- **格式**: JSON, XML, YAML, YML
- **用途**: 配置文件、数据交换等
- **特点**: 支持结构化数据格式

## 🔒 安全考虑

### 1. 文件类型验证
- 基于文件扩展名验证
- 白名单机制，只允许预定义的文件类型
- 防止恶意文件上传

### 2. 文件大小限制
- 最大5MB限制，防止存储滥用
- 实时大小检查
- 人性化的错误提示

### 3. 用户隔离
- 文件按用户ID组织存储
- 用户只能访问自己的文件
- 路径安全检查

### 4. 文件名安全
- 使用UUID生成唯一文件名
- 防止文件名冲突
- 保留原始文件名用于显示

## 🚀 使用示例

### JavaScript前端集成

```javascript
// 上传PDF文件
async function uploadPDF(file) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('bucket', 'demo');
  formData.append('folder', 'documents');

  const response = await fetch('/api/upload-image', {
    method: 'POST',
    headers: {
      'Userid': userId
    },
    body: formData
  });

  const result = await response.json();
  
  if (result.success) {
    console.log('文件上传成功:', result.data);
    console.log('文件类别:', result.data.category);
    console.log('文件大小:', result.data.sizeFormatted);
    console.log('公开URL:', result.data.publicUrl);
  }
}

// 获取支持的文件类型
async function getSupportedFileTypes() {
  const response = await fetch('/api/file-types');
  const result = await response.json();
  
  if (result.success) {
    console.log('最大文件大小:', result.data.maxFileSizeFormatted);
    console.log('支持的分类:', Object.keys(result.data.categories));
  }
}
```

### React组件示例

```jsx
import React, { useState, useEffect } from 'react';

function FileUpload() {
  const [fileTypes, setFileTypes] = useState(null);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    // 获取支持的文件类型
    fetch('/api/file-types')
      .then(res => res.json())
      .then(data => setFileTypes(data.data));
  }, []);

  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    // 检查文件大小
    if (fileTypes && file.size > fileTypes.maxFileSize) {
      alert(`文件太大，最大允许 ${fileTypes.maxFileSizeFormatted}`);
      return;
    }

    setUploading(true);
    
    const formData = new FormData();
    formData.append('file', file);
    formData.append('bucket', 'demo');

    try {
      const response = await fetch('/api/upload-image', {
        method: 'POST',
        headers: { 'Userid': userId },
        body: formData
      });

      const result = await response.json();
      
      if (result.success) {
        console.log('上传成功:', result.data);
      } else {
        alert('上传失败: ' + result.error);
      }
    } catch (error) {
      alert('上传错误: ' + error.message);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div>
      <input 
        type="file" 
        onChange={handleFileUpload}
        disabled={uploading}
        accept={fileTypes ? fileTypes.allExtensions.map(ext => `.${ext}`).join(',') : ''}
      />
      {uploading && <p>上传中...</p>}
      {fileTypes && (
        <p>支持的文件类型: {fileTypes.allExtensions.join(', ')}</p>
      )}
    </div>
  );
}
```

## 📈 性能优化

### 1. 文件大小限制
- 5MB限制平衡了功能性和性能
- 减少服务器存储压力
- 提高上传速度

### 2. 分类组织
- 按文件类型自动分类
- 便于文件管理和检索
- 支持按类别过滤

### 3. 元数据增强
- 提供丰富的文件信息
- 支持前端展示优化
- 便于文件管理

## 🔄 向后兼容性

### API接口保持不变
- `/api/upload-image` 端点名称保持不变
- 请求参数格式保持兼容
- 响应结构向后兼容（只是增加了新字段）

### 默认行为
- 如果不指定bucket，默认使用'demo'
- 原有的图片上传功能完全保持
- 错误处理机制保持一致

## 🎉 总结

这次优化大大扩展了文件上传API的功能：

1. **支持更多文件类型** - 从6种图片格式扩展到30+种文件格式
2. **更好的组织结构** - 文件自动分类，便于管理
3. **优化的用户体验** - 更详细的错误信息和文件信息
4. **增强的安全性** - 严格的文件类型和大小验证
5. **丰富的元数据** - 提供文件分类、格式化大小等信息
6. **新的信息API** - 前端可以获取支持的文件类型信息

现在用户可以上传各种类型的文件，包括PDF文档、Excel表格、PowerPoint演示文稿等，大大提升了系统的实用性！🚀
