#!/bin/bash
# DINQ 快速重启脚本
# 用法: ./restart.sh [dev|prod]
# dev: 使用开发模式重启（使用 Flask 开发服务器）
# prod: 使用生产模式重启（调用 production_deploy.sh 更新并重启）

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置项
PROJECT_DIR="$(pwd)"
VENV_DIR="$PROJECT_DIR/venv"
LOG_DIR="$PROJECT_DIR/logs"
SERVER_SCRIPT="new_server.py"
LOG_FILE="$LOG_DIR/server.log"
PROD_DEPLOY_SCRIPT="./production_deploy.sh"
GIT_BRANCH="main"  # 默认分支

# 确保日志目录存在
mkdir -p "$LOG_DIR"

# 检查 production_deploy.sh 是否存在
check_prod_script() {
    if [ ! -f "$PROD_DEPLOY_SCRIPT" ]; then
        echo -e "${RED}错误: 生产部署脚本 $PROD_DEPLOY_SCRIPT 不存在${NC}"
        exit 1
    fi

    # 确保脚本有执行权限
    chmod +x "$PROD_DEPLOY_SCRIPT"
}

# 开发模式重启
dev_restart() {
    echo -e "${BLUE}使用开发模式重启服务器...${NC}"

    # 查找并终止现有的服务器进程
    echo -e "${BLUE}查找并终止现有的服务器进程...${NC}"
    pkill -f "$SERVER_SCRIPT" || true
    sleep 1

    # 激活虚拟环境
    echo -e "${BLUE}激活虚拟环境...${NC}"
    source "$VENV_DIR/bin/activate"

    # 启动服务器
    echo -e "${BLUE}启动服务器...${NC}"
    python "$SERVER_SCRIPT" > "$LOG_FILE" 2>&1 &

    # 显示启动信息
    echo -e "${GREEN}服务器已在后台启动 (开发模式)${NC}"
    echo -e "${BLUE}日志文件: $LOG_FILE${NC}"
    echo -e "${BLUE}查看日志: tail -f $LOG_FILE${NC}"
    echo -e "${YELLOW}提示: 使用 'pkill -f $SERVER_SCRIPT' 命令可以停止服务器${NC}"
}

# 生产模式重启
prod_restart() {
    echo -e "${BLUE}使用生产模式重启服务器...${NC}"

    # 检查生产部署脚本是否存在
    check_prod_script

    # 调用生产部署脚本更新代码并重启服务
    echo -e "${BLUE}调用生产部署脚本更新代码并重启服务...${NC}"

    # 检查是否需要 sudo
    if [ -f "/etc/systemd/system/dinq.service" ]; then
        echo -e "${YELLOW}检测到系统服务，需要使用 sudo 权限...${NC}"
        sudo "$PROD_DEPLOY_SCRIPT" update
    else
        # 如果没有安装为系统服务，则先停止当前运行的进程
        echo -e "${BLUE}停止当前运行的进程...${NC}"
        pkill -f "$SERVER_SCRIPT" || true
        pkill -f "gunicorn.*server.app:app" || true
        sleep 1

        # 然后执行更新代码的部分
        echo -e "${BLUE}更新代码...${NC}"
        "$PROD_DEPLOY_SCRIPT" setup

        # 使用 gunicorn 启动服务
        echo -e "${BLUE}使用 gunicorn 启动服务...${NC}"
        source "$VENV_DIR/bin/activate"
        gunicorn --bind 0.0.0.0:5001 --workers 4 --timeout 300 server.app:app > "$LOG_FILE" 2>&1 &

        echo -e "${GREEN}服务器已在后台启动 (生产模式)${NC}"
        echo -e "${BLUE}日志文件: $LOG_FILE${NC}"
        echo -e "${BLUE}查看日志: tail -f $LOG_FILE${NC}"
    fi
}

# 主函数
main() {
    # 根据参数选择重启模式
    case "$1" in
        dev)
            dev_restart
            ;;
        prod)
            prod_restart
            ;;
        *)
            # 默认使用开发模式
            echo -e "${YELLOW}未指定重启模式，默认使用生产模式${NC}"
            prod_restart
            ;;
    esac
}

# 执行主函数
main "$1"
