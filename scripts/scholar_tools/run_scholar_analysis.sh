#!/bin/bash
# 运行Google Scholar学者个人资料获取和分析脚本
# 该脚本会获取学者的完整个人资料，包括最多500篇论文
# 优化的获取方式：第一页获取完整个人资料，后续页面只获取论文信息

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 默认参数
SCHOLAR_ID="0VAe-TQAAAAJ"
MAX_PAPERS=500
OUTPUT_FILE="scholar_profile.json"
USE_CRAWLBASE=true
API_TOKEN=""

# 显示帮助信息
show_help() {
    echo -e "${BLUE}Google Scholar学者个人资料获取和分析脚本${NC}"
    echo
    echo "用法: $0 [选项]"
    echo
    echo "选项:"
    echo "  -h, --help                显示帮助信息"
    echo "  -i, --id SCHOLAR_ID       指定Google Scholar ID (默认: 0VAe-TQAAAAJ)"
    echo "  -m, --max-papers NUMBER   最大论文数量 (默认: 500)"
    echo "  -o, --output FILE         输出文件名 (默认: scholar_profile.json)"
    echo "  -n, --no-crawlbase        不使用Crawlbase API"
    echo "  -t, --token TOKEN         指定Crawlbase API令牌"
    echo
}

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -i|--id)
            SCHOLAR_ID="$2"
            shift 2
            ;;
        -m|--max-papers)
            MAX_PAPERS="$2"
            shift 2
            ;;
        -o|--output)
            OUTPUT_FILE="$2"
            shift 2
            ;;
        -n|--no-crawlbase)
            USE_CRAWLBASE=false
            shift
            ;;
        -t|--token)
            API_TOKEN="$2"
            shift 2
            ;;
        *)
            echo -e "${RED}未知参数: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# 检查Python是否安装
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}错误: 未找到python3，请先安装python3${NC}"
    exit 1
fi

# 检查必要的Python包是否安装
echo -e "${BLUE}检查必要的Python包...${NC}"
REQUIRED_PACKAGES=("requests" "beautifulsoup4" "matplotlib")
MISSING_PACKAGES=()

for package in "${REQUIRED_PACKAGES[@]}"; do
    if ! python3 -c "import $package" &> /dev/null; then
        MISSING_PACKAGES+=("$package")
    fi
done

if [ ${#MISSING_PACKAGES[@]} -gt 0 ]; then
    echo -e "${YELLOW}以下Python包未安装:${NC}"
    for package in "${MISSING_PACKAGES[@]}"; do
        echo "  - $package"
    done

    echo -e "${YELLOW}正在安装缺失的包...${NC}"
    pip3 install "${MISSING_PACKAGES[@]}"

    # 检查安装是否成功
    for package in "${MISSING_PACKAGES[@]}"; do
        if ! python3 -c "import $package" &> /dev/null; then
            echo -e "${RED}错误: 安装 $package 失败，请手动安装: pip3 install $package${NC}"
            exit 1
        fi
    done

    echo -e "${GREEN}所有必要的包已成功安装${NC}"
fi

# 构建命令行参数
FETCH_ARGS="$SCHOLAR_ID --max-papers $MAX_PAPERS --output $OUTPUT_FILE"

if [ "$USE_CRAWLBASE" = false ]; then
    FETCH_ARGS="$FETCH_ARGS --no-crawlbase"
fi

if [ -n "$API_TOKEN" ]; then
    FETCH_ARGS="$FETCH_ARGS --api-token $API_TOKEN"
fi

# 运行获取脚本
echo -e "${BLUE}开始获取学者个人资料 (ID: $SCHOLAR_ID)...${NC}"
echo -e "${BLUE}最大论文数量: $MAX_PAPERS${NC}"
echo -e "${BLUE}输出文件: $OUTPUT_FILE${NC}"
echo -e "${BLUE}使用Crawlbase API: $USE_CRAWLBASE${NC}"
echo

python3 $(dirname "$0")/fetch_full_scholar_profile.py $FETCH_ARGS

# 检查获取是否成功
if [ ! -f "$OUTPUT_FILE" ]; then
    echo -e "${RED}错误: 获取个人资料失败，未生成输出文件${NC}"
    exit 1
fi

# 运行分析脚本
echo -e "\n${BLUE}开始分析学者个人资料...${NC}"
python3 $(dirname "$0")/analyze_scholar_profile.py "$OUTPUT_FILE"

echo -e "\n${GREEN}分析完成!${NC}"
echo -e "${BLUE}个人资料已保存到: $OUTPUT_FILE${NC}"
echo -e "${BLUE}可视化结果已保存到: visualizations/目录${NC}"
