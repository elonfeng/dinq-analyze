# GitHub Analyzer 部署指南

本文档提供了将 GitHub Analyzer 部署到不同环境的详细指南。

## 本地开发部署

### 1. 环境准备

```bash
# 克隆或复制项目文件
cd github_analyzer

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.template .env
# 编辑 .env 文件，填入你的 API 密钥
```

### 2. 启动服务

```bash
python run.py
```

服务将在 `http://localhost:5001` 启动。

### 3. 测试

```bash
python test_api.py
```

## Docker 部署

### 1. 创建 Dockerfile

```dockerfile
FROM python:3.9-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 暴露端口
EXPOSE 5000

# 启动命令
CMD ["python", "run.py"]
```

### 2. 构建和运行

```bash
# 构建镜像
docker build -t github-analyzer .

# 运行容器
docker run -d \
  --name github-analyzer \
  -p 5000:5000 \
  -e GITHUB_TOKEN=your_token \
  -e OPENROUTER_API_KEY=your_key \
  -e CRAWLBASE_TOKEN=your_token \
  github-analyzer
```

### 3. 使用 docker-compose

创建 `docker-compose.yml`:

```yaml
version: '3.8'

services:
  github-analyzer:
    build: .
    ports:
      - "5000:5000"
    environment:
      - GITHUB_TOKEN=${GITHUB_TOKEN}
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
      - CRAWLBASE_TOKEN=${CRAWLBASE_TOKEN}
      - FLASK_HOST=0.0.0.0
      - FLASK_PORT=5000
    volumes:
      - ./data:/app/data  # 持久化数据库
    restart: unless-stopped
```

启动：

```bash
docker-compose up -d
```

## 云平台部署

### Heroku 部署

1. 创建 `Procfile`:

```
web: python run.py
```

2. 创建 `runtime.txt`:

```
python-3.9.16
```

3. 部署命令:

```bash
# 登录 Heroku
heroku login

# 创建应用
heroku create your-app-name

# 设置环境变量
heroku config:set GITHUB_TOKEN=your_token
heroku config:set OPENROUTER_API_KEY=your_key
heroku config:set CRAWLBASE_TOKEN=your_token
heroku config:set FLASK_HOST=0.0.0.0
heroku config:set FLASK_PORT=$PORT

# 部署
git add .
git commit -m "Deploy to Heroku"
git push heroku main
```

### AWS EC2 部署

1. 启动 EC2 实例 (Ubuntu 20.04)

2. 安装依赖:

```bash
sudo apt update
sudo apt install python3 python3-pip nginx -y

# 安装应用
git clone your-repo
cd github_analyzer
pip3 install -r requirements.txt
```

3. 配置环境变量:

```bash
sudo nano /etc/environment
# 添加你的环境变量
```

4. 创建 systemd 服务:

```bash
sudo nano /etc/systemd/system/github-analyzer.service
```

```ini
[Unit]
Description=GitHub Analyzer API
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/github_analyzer
ExecStart=/usr/bin/python3 run.py
Restart=always
Environment=FLASK_HOST=127.0.0.1
Environment=FLASK_PORT=5000

[Install]
WantedBy=multi-user.target
```

5. 启动服务:

```bash
sudo systemctl daemon-reload
sudo systemctl enable github-analyzer
sudo systemctl start github-analyzer
```

6. 配置 Nginx:

```bash
sudo nano /etc/nginx/sites-available/github-analyzer
```

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/github-analyzer /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### Google Cloud Run 部署

1. 创建 `cloudbuild.yaml`:

```yaml
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'gcr.io/$PROJECT_ID/github-analyzer', '.']
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'gcr.io/$PROJECT_ID/github-analyzer']
  - name: 'gcr.io/cloud-builders/gcloud'
    args:
      - 'run'
      - 'deploy'
      - 'github-analyzer'
      - '--image'
      - 'gcr.io/$PROJECT_ID/github-analyzer'
      - '--region'
      - 'us-central1'
      - '--platform'
      - 'managed'
      - '--allow-unauthenticated'
```

2. 部署:

```bash
gcloud builds submit --config cloudbuild.yaml
```

## 生产环境配置

### 1. 安全配置

- 使用 HTTPS
- 设置适当的 CORS 策略
- 实施 API 速率限制
- 使用环境变量管理敏感信息

### 2. 性能优化

- 使用 Gunicorn 作为 WSGI 服务器
- 配置负载均衡
- 实施缓存策略
- 监控和日志记录

### 3. Gunicorn 配置

创建 `gunicorn.conf.py`:

```python
bind = "0.0.0.0:5000"
workers = 4
worker_class = "sync"
worker_connections = 1000
timeout = 300
keepalive = 2
max_requests = 1000
max_requests_jitter = 100
preload_app = True
```

启动命令:

```bash
gunicorn -c gunicorn.conf.py "github_analyzer.flask_app:create_app()"
```

### 4. 监控和日志

使用工具如：
- Prometheus + Grafana (监控)
- ELK Stack (日志)
- Sentry (错误追踪)

## 故障排除

### 常见问题

1. **端口冲突**: 确保端口 5000 未被占用
2. **依赖问题**: 检查 Python 版本和依赖安装
3. **API 限制**: 监控 API 使用量和限制
4. **内存不足**: 增加服务器内存或优化代码

### 日志查看

```bash
# 查看服务日志
sudo journalctl -u github-analyzer -f

# 查看 Nginx 日志
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

## 维护

### 定期任务

1. 清理过期缓存
2. 更新依赖包
3. 备份数据库
4. 监控系统资源

### 更新部署

```bash
# 拉取最新代码
git pull origin main

# 重启服务
sudo systemctl restart github-analyzer
```

## 扩展

### 水平扩展

- 使用负载均衡器
- 部署多个实例
- 共享数据库和缓存

### 垂直扩展

- 增加 CPU 和内存
- 优化数据库查询
- 使用更快的存储
