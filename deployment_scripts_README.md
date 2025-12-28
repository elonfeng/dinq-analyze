# DINQ 部署脚本使用指南

本项目提供了三个部署脚本，用于不同场景下的部署和管理：

- `restart.sh`: 快速重启脚本，适用于本地开发
- `deploy.sh`: 通用部署脚本，适用于开发环境和简单的生产环境
- `production_deploy.sh`: 生产环境部署脚本，支持系统服务和自动重启

## 快速参考

### 快速重启 (restart.sh)

```bash
# 使用生产模式重启服务器（默认）
./restart.sh
# 或
./restart.sh prod

# 使用开发模式重启服务器
./restart.sh dev
```

### 通用部署 (deploy.sh)

```bash
# 启动服务器
./deploy.sh start

# 停止服务器
./deploy.sh stop

# 重启服务器
./deploy.sh restart

# 查看服务器状态
./deploy.sh status

# 更新代码并重启服务器
./deploy.sh update

# 实时查看日志
./deploy.sh logs
```

### 生产环境部署 (production_deploy.sh)

```bash
# 初始化环境（创建虚拟环境和安装依赖）
./production_deploy.sh setup

# 安装为系统服务（需要root权限）
sudo ./production_deploy.sh install

# 启动服务（需要root权限）
sudo ./production_deploy.sh start

# 停止服务（需要root权限）
sudo ./production_deploy.sh stop

# 重启服务（需要root权限）
sudo ./production_deploy.sh restart

# 查看服务状态
./production_deploy.sh status

# 更新代码并重启服务（需要root权限）
sudo ./production_deploy.sh update

# 卸载服务（需要root权限）
sudo ./production_deploy.sh uninstall
```

## 完整部署流程

在全新的服务器上部署 DINQ 应用的完整流程：

1. 克隆代码仓库
   ```bash
   git clone git@github.com:tomguluson92/DINQ.git
   cd DINQ
   ```

2. 初始化环境
   ```bash
   ./production_deploy.sh setup
   ```

3. 安装为系统服务
   ```bash
   sudo ./production_deploy.sh install
   ```

4. 启动服务
   ```bash
   sudo ./production_deploy.sh start
   ```

5. 查看服务状态
   ```bash
   ./production_deploy.sh status
   ```

更多详细信息，请参阅 [部署指南](deployment_guide.md)。
