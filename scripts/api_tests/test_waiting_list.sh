#!/bin/bash
# 等待列表 API 测试脚本
# 用法: ./test_waiting_list.sh [--host HOST] [--port PORT] [--user-id USER_ID] [--admin-id ADMIN_ID]

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 默认参数
HOST="localhost"
PORT="5001"
USER_ID="test_user_id"
ADMIN_ID="admin_user_id"

# 解析命令行参数
while [[ $# -gt 0 ]]; do
  case $1 in
    --host)
      HOST="$2"
      shift 2
      ;;
    --port)
      PORT="$2"
      shift 2
      ;;
    --user-id)
      USER_ID="$2"
      shift 2
      ;;
    --admin-id)
      ADMIN_ID="$2"
      shift 2
      ;;
    *)
      echo -e "${RED}未知参数: $1${NC}"
      exit 1
      ;;
  esac
done

# 检查 Python 是否安装
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}错误: 未找到 python3，请先安装 python3${NC}"
    exit 1
fi

# 检查 requests 库是否安装
if ! python3 -c "import requests" &> /dev/null; then
    echo -e "${YELLOW}警告: 未找到 requests 库，正在安装...${NC}"
    pip3 install requests

    # 检查安装是否成功
    if ! python3 -c "import requests" &> /dev/null; then
        echo -e "${RED}错误: 安装 requests 库失败，请手动安装: pip3 install requests${NC}"
        exit 1
    fi

    echo -e "${GREEN}requests 库安装成功${NC}"
fi

# 确保 Python 测试脚本有执行权限
chmod +x $(dirname "$0")/test_waiting_list_api.py

# 运行测试
echo -e "${BLUE}开始测试等待列表 API...${NC}"
echo -e "${BLUE}主机: ${HOST}, 端口: ${PORT}, 用户ID: ${USER_ID}, 管理员ID: ${ADMIN_ID}${NC}"
echo

python3 $(dirname "$0")/test_waiting_list_api.py --host "${HOST}" --port "${PORT}" --user-id "${USER_ID}" --admin-id "${ADMIN_ID}"

# 检查测试结果
if [ $? -eq 0 ]; then
    echo -e "\n${GREEN}测试完成${NC}"
else
    echo -e "\n${RED}测试失败${NC}"
fi
