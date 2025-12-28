#!/bin/bash
# 远程服务器重启脚本
# 用法: ./remote_restart.sh [dev|prod]

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置项
REMOTE_HOST="rdigui"
REMOTE_DIR="/home/user/code/DINQ"
RESTART_MODE="${1:-prod}"  # 默认使用生产模式

echo -e "${BLUE}连接到远程服务器 ${REMOTE_HOST} 并重启服务...${NC}"

# 使用 SSH 连接到远程服务器，执行命令，并保持连接以查看日志
ssh -t ${REMOTE_HOST} "
    echo -e '${BLUE}进入目录 ${REMOTE_DIR}...${NC}'
    cd ${REMOTE_DIR} || { echo -e '${RED}无法进入目录 ${REMOTE_DIR}${NC}'; exit 1; }
    
    echo -e '${BLUE}运行 restart.sh 脚本 (模式: ${RESTART_MODE})...${NC}'
    ./restart.sh ${RESTART_MODE}
    
    echo -e '${GREEN}服务已重启，正在查看日志...${NC}'
    echo -e '${YELLOW}按 Ctrl+C 退出日志查看${NC}'
    tail -f logs/server.log
"

# 如果 SSH 连接中断，显示提示信息
echo -e "${BLUE}SSH 连接已关闭${NC}"
echo -e "${YELLOW}如需再次查看日志，请运行:${NC}"
echo -e "  ssh ${REMOTE_HOST} \"cd ${REMOTE_DIR} && tail -f logs/server.log\""
