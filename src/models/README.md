# 数据库模型

本目录包含DINQ项目的数据库模型定义。

## 模型说明

### Scholar模型

`Scholar`模型用于缓存从Google Scholar获取的学者信息，以提高查询效率。

主要字段：
- `id`: 主键
- `scholar_id`: Google Scholar ID，唯一索引
- `name`: 学者姓名
- `affiliation`: 所属机构
- `email`: 电子邮件
- `research_fields`: 研究领域（JSON格式）
- `total_citations`: 总引用次数
- `h_index`: h指数
- `i10_index`: i10指数
- `profile_data`: 完整个人资料数据（JSON格式）
- `publications_data`: 发表论文数据（JSON格式）
- `coauthors_data`: 合作者数据（JSON格式）
- `report_data`: 生成的报告数据（JSON格式）
- `last_updated`: 最后更新时间
- `created_at`: 创建时间

## 使用方法

### 初始化数据库

在使用数据库功能前，需要先初始化数据库表：

```python
from src.utils.db_utils import create_tables

# 创建所有表
create_tables()
```

### 基本CRUD操作

可以使用`ScholarRepository`类进行基本的CRUD操作：

```python
from src.utils.scholar_repository import scholar_repo

# 创建记录
scholar_data = {
    'scholar_id': 'ABCDEF123',
    'name': 'John Doe',
    'affiliation': 'Example University',
    'total_citations': 1000,
    'h_index': 20
}
scholar = scholar_repo.create(scholar_data)

# 通过ID获取记录
scholar = scholar_repo.get_by_id(1)

# 通过Scholar ID获取记录
scholar = scholar_repo.get_by_scholar_id('ABCDEF123')

# 更新记录
scholar_repo.update(1, {'total_citations': 1500})

# 删除记录
scholar_repo.delete(1)
```

### 使用缓存功能

可以使用`scholar_cache.py`中的函数来简化缓存操作：

```python
from src.utils.scholar_cache import get_cached_scholar, cache_scholar_data

# 从缓存获取学者信息
scholar_data = get_cached_scholar('ABCDEF123')

# 缓存学者信息
cache_data = {
    'scholar_id': 'ABCDEF123',
    'name': 'John Doe',
    'affiliation': 'Example University',
    'total_citations': 1000,
    'h_index': 20,
    'report_data': {...}  # 完整的报告数据
}
cache_scholar_data(cache_data)
```

## 配置数据库连接

数据库连接配置位于`src/utils/db_utils.py`文件中的`DB_CONFIG`字典：

```python
DB_CONFIG = {
    'host': '157.230.67.105',  # 可以使用IP地址或域名
    'user': 'devuser',
    'password': 'devpassword',
    'database': 'devfun',
    'port': 3306,
    'allow_local_infile': True,  # 允许加载本地文件
    'use_pure': True,  # 使用纯Python实现，提高兼容性
    'auth_plugin': 'mysql_native_password'  # 使用原生密码认证
}
```

可以根据实际环境修改这些配置。
