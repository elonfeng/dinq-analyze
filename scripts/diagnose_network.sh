#!/bin/bash

# 网络连接诊断脚本
# 用于诊断Supabase数据库连接问题

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔍 开始网络连接诊断...${NC}"
echo "=================================================="

# 1. 检查基本网络连接
echo -e "\n${YELLOW}1. 检查基本网络连接${NC}"
echo "测试连接到Google DNS..."
if ping -c 3 8.8.8.8 > /dev/null 2>&1; then
    echo -e "${GREEN}✅ 基本网络连接正常${NC}"
else
    echo -e "${RED}❌ 基本网络连接失败${NC}"
    exit 1
fi

# 2. 检查DNS解析
echo -e "\n${YELLOW}2. 检查DNS解析${NC}"
SUPABASE_HOST="db.kqfpikinqkcujlzrsaad.supabase.co"

echo "解析 $SUPABASE_HOST..."
if nslookup $SUPABASE_HOST > /dev/null 2>&1; then
    echo -e "${GREEN}✅ DNS解析成功${NC}"
    echo "IP地址信息:"
    nslookup $SUPABASE_HOST | grep -A 2 "Name:"
else
    echo -e "${RED}❌ DNS解析失败${NC}"
    echo "尝试使用不同的DNS服务器..."
    
    # 尝试使用Google DNS
    echo "使用Google DNS (8.8.8.8) 解析..."
    nslookup $SUPABASE_HOST 8.8.8.8
fi

# 3. 检查端口连接
echo -e "\n${YELLOW}3. 检查端口连接${NC}"
echo "测试连接到 $SUPABASE_HOST:5432..."

if command -v telnet > /dev/null 2>&1; then
    timeout 10 telnet $SUPABASE_HOST 5432 2>/dev/null && echo -e "${GREEN}✅ 端口5432连接成功${NC}" || echo -e "${RED}❌ 端口5432连接失败${NC}"
elif command -v nc > /dev/null 2>&1; then
    if nc -z -w5 $SUPABASE_HOST 5432 2>/dev/null; then
        echo -e "${GREEN}✅ 端口5432连接成功${NC}"
    else
        echo -e "${RED}❌ 端口5432连接失败${NC}"
    fi
else
    echo -e "${YELLOW}⚠️ telnet和nc都不可用，跳过端口测试${NC}"
fi

# 4. 检查防火墙和路由
echo -e "\n${YELLOW}4. 检查路由信息${NC}"
echo "追踪到 $SUPABASE_HOST 的路由..."
if command -v traceroute > /dev/null 2>&1; then
    traceroute -m 10 $SUPABASE_HOST 2>/dev/null || echo -e "${YELLOW}⚠️ traceroute失败或超时${NC}"
elif command -v tracepath > /dev/null 2>&1; then
    tracepath $SUPABASE_HOST 2>/dev/null || echo -e "${YELLOW}⚠️ tracepath失败或超时${NC}"
else
    echo -e "${YELLOW}⚠️ traceroute和tracepath都不可用${NC}"
fi

# 5. 检查系统信息
echo -e "\n${YELLOW}5. 系统信息${NC}"
echo "操作系统: $(uname -a)"
echo "当前用户: $(whoami)"
echo "网络接口:"
ip addr show 2>/dev/null || ifconfig 2>/dev/null || echo "无法获取网络接口信息"

# 6. 检查环境变量
echo -e "\n${YELLOW}6. 检查相关环境变量${NC}"
echo "HTTP_PROXY: ${HTTP_PROXY:-未设置}"
echo "HTTPS_PROXY: ${HTTPS_PROXY:-未设置}"
echo "NO_PROXY: ${NO_PROXY:-未设置}"

# 7. 测试替代连接方法
echo -e "\n${YELLOW}7. 测试替代连接方法${NC}"

# 尝试使用curl测试HTTPS连接
echo "测试HTTPS连接到Supabase..."
if curl -s --connect-timeout 10 https://kqfpikinqkcujlzrsaad.supabase.co > /dev/null 2>&1; then
    echo -e "${GREEN}✅ HTTPS连接成功${NC}"
else
    echo -e "${RED}❌ HTTPS连接失败${NC}"
fi

# 8. 建议解决方案
echo -e "\n${BLUE}💡 可能的解决方案:${NC}"
echo "1. 检查服务器防火墙设置，确保允许出站连接到端口5432"
echo "2. 检查网络代理设置"
echo "3. 联系服务器管理员检查网络策略"
echo "4. 考虑使用Supabase的连接池或代理"
echo "5. 检查Supabase项目是否暂停或有地域限制"

echo -e "\n${BLUE}🔧 临时解决方案:${NC}"
echo "1. 使用本地数据库进行开发"
echo "2. 配置SSH隧道通过本地机器连接"
echo "3. 使用Supabase的REST API而不是直接数据库连接"

echo -e "\n=================================================="
echo -e "${BLUE}诊断完成${NC}"
