#!/bin/bash
# DINQ 生产环境部署脚本
# 用法: ./production_deploy.sh [install|start|stop|restart|status|update|uninstall]

# 配置项
APP_NAME="dinq"
USER=$(whoami)
PROJECT_DIR="$(pwd)"
VENV_DIR="$PROJECT_DIR/venv"
LOG_DIR="$PROJECT_DIR/logs"
SERVER_SCRIPT="new_server.py"
PID_FILE="$PROJECT_DIR/.server.pid"
LOG_FILE="$LOG_DIR/server.log"
ERROR_LOG_FILE="$LOG_DIR/server_error.log"
GIT_BRANCH="main"  # 默认分支
SERVICE_FILE="/etc/systemd/system/$APP_NAME.service"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 确保日志目录存在
mkdir -p "$LOG_DIR"

# 检查是否以root用户运行
check_root() {
    if [ "$EUID" -ne 0 ]; then
        echo -e "${RED}请以root用户运行此脚本 (sudo $0 $1)${NC}"
        exit 1
    fi
}

# 检查并创建虚拟环境
setup_venv() {
    echo -e "${BLUE}检查虚拟环境...${NC}"

    # 检查虚拟环境是否存在
    if [ ! -d "$VENV_DIR" ]; then
        echo -e "${YELLOW}虚拟环境不存在，正在创建...${NC}"

        # 检查python3是否安装
        if ! command -v python3 &> /dev/null; then
            echo -e "${RED}未找到python3，请先安装python3${NC}"
            exit 1
        fi

        # 检查venv模块是否可用
        if ! python3 -m venv --help &> /dev/null; then
            echo -e "${YELLOW}python3-venv模块未安装，尝试安装...${NC}"

            # 检测操作系统类型并安装venv
            if command -v apt-get &> /dev/null; then
                # Debian/Ubuntu
                apt-get update
                apt-get install -y python3-venv
            elif command -v yum &> /dev/null; then
                # CentOS/RHEL
                yum install -y python3-venv
            elif command -v dnf &> /dev/null; then
                # Fedora
                dnf install -y python3-venv
            elif command -v pacman &> /dev/null; then
                # Arch Linux
                pacman -S python-virtualenv
            elif command -v brew &> /dev/null; then
                # macOS with Homebrew
                brew install python
            else
                echo -e "${RED}无法自动安装python3-venv，请手动安装后重试${NC}"
                exit 1
            fi
        fi

        # 创建虚拟环境
        python3 -m venv "$VENV_DIR"

        if [ $? -ne 0 ]; then
            echo -e "${RED}创建虚拟环境失败${NC}"
            exit 1
        fi

        echo -e "${GREEN}虚拟环境创建成功${NC}"
    else
        echo -e "${GREEN}虚拟环境已存在${NC}"
    fi
}

# 创建systemd服务文件
create_service_file() {
    check_root

    echo -e "${BLUE}创建systemd服务文件...${NC}"

    cat > "$SERVICE_FILE" << EOF
[Unit]
Description=DINQ Scholar Analysis Service
After=network.target

[Service]
User=$USER
WorkingDirectory=$PROJECT_DIR
ExecStart=$VENV_DIR/bin/gunicorn --bind 0.0.0.0:5001 --workers 4 --timeout 300 server.app:app
Restart=always
RestartSec=5
StandardOutput=append:$LOG_FILE
StandardError=append:$ERROR_LOG_FILE
Environment="PATH=$VENV_DIR/bin:/usr/local/bin:/usr/bin:/bin"

[Install]
WantedBy=multi-user.target
EOF

    # 重新加载systemd配置
    systemctl daemon-reload

    echo -e "${GREEN}服务文件创建成功: $SERVICE_FILE${NC}"
}

# 安装服务
install_service() {
    check_root

    echo -e "${BLUE}安装DINQ服务...${NC}"

    # 检查虚拟环境是否存在
    if [ ! -d "$VENV_DIR" ]; then
        echo -e "${YELLOW}虚拟环境不存在，正在设置...${NC}"
        setup_venv
        activate_venv
        install_dependencies
    fi

    # 创建服务文件
    create_service_file

    # 启用服务（开机自启）
    systemctl enable $APP_NAME

    echo -e "${GREEN}DINQ服务安装成功并已设置为开机自启${NC}"
    echo -e "${BLUE}使用以下命令管理服务:${NC}"
    echo -e "  ${YELLOW}sudo systemctl start $APP_NAME${NC} - 启动服务"
    echo -e "  ${YELLOW}sudo systemctl stop $APP_NAME${NC} - 停止服务"
    echo -e "  ${YELLOW}sudo systemctl restart $APP_NAME${NC} - 重启服务"
    echo -e "  ${YELLOW}sudo systemctl status $APP_NAME${NC} - 查看服务状态"
}

# 卸载服务
uninstall_service() {
    check_root

    echo -e "${BLUE}卸载DINQ服务...${NC}"

    # 停止服务
    systemctl stop $APP_NAME

    # 禁用服务
    systemctl disable $APP_NAME

    # 删除服务文件
    rm -f "$SERVICE_FILE"

    # 重新加载systemd配置
    systemctl daemon-reload

    echo -e "${GREEN}DINQ服务已卸载${NC}"
}

# 启动服务
start_service() {
    check_root

    echo -e "${BLUE}启动DINQ服务...${NC}"
    systemctl start $APP_NAME
    sleep 2

    # 检查服务状态
    if systemctl is-active --quiet $APP_NAME; then
        echo -e "${GREEN}DINQ服务已启动${NC}"
    else
        echo -e "${RED}DINQ服务启动失败，请检查日志${NC}"
        systemctl status $APP_NAME
    fi
}

# 停止服务
stop_service() {
    check_root

    echo -e "${BLUE}停止DINQ服务...${NC}"
    systemctl stop $APP_NAME
    sleep 2

    # 检查服务状态
    if ! systemctl is-active --quiet $APP_NAME; then
        echo -e "${GREEN}DINQ服务已停止${NC}"
    else
        echo -e "${RED}DINQ服务停止失败，请检查日志${NC}"
        systemctl status $APP_NAME
    fi
}

# 重启服务
restart_service() {
    check_root

    echo -e "${BLUE}重启DINQ服务...${NC}"
    systemctl restart $APP_NAME
    sleep 2

    # 检查服务状态
    if systemctl is-active --quiet $APP_NAME; then
        echo -e "${GREEN}DINQ服务已重启${NC}"
    else
        echo -e "${RED}DINQ服务重启失败，请检查日志${NC}"
        systemctl status $APP_NAME
    fi
}

# 显示服务状态
show_status() {
    echo -e "${BLUE}DINQ服务状态:${NC}"
    systemctl status $APP_NAME
}

# 拉取最新代码
update_code() {
    echo -e "${BLUE}拉取最新代码 (分支: $GIT_BRANCH)...${NC}"
    git fetch
    git checkout $GIT_BRANCH
    git pull origin $GIT_BRANCH

    # 检查是否有冲突
    if [ $? -ne 0 ]; then
        echo -e "${RED}拉取代码时出现错误，请手动解决冲突${NC}"
        exit 1
    fi

    echo -e "${GREEN}代码更新成功${NC}"
}

# 激活虚拟环境
activate_venv() {
    echo -e "${BLUE}激活虚拟环境...${NC}"
    source "$VENV_DIR/bin/activate"
}

# 安装/更新依赖
install_dependencies() {
    echo -e "${BLUE}安装/更新依赖...${NC}"

    # 确保虚拟环境已激活
    if [[ "$VIRTUAL_ENV" != "$VENV_DIR" ]]; then
        activate_venv
    fi

    # 升级pip
    echo -e "${BLUE}升级pip...${NC}"
    pip install --upgrade pip

    # 安装wheel（避免某些包安装问题）
    echo -e "${BLUE}安装wheel...${NC}"
    pip install wheel

    # 安装项目依赖
    echo -e "${BLUE}安装项目依赖...${NC}"
    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt

        if [ $? -ne 0 ]; then
            echo -e "${YELLOW}部分依赖安装失败，尝试单独安装每个依赖...${NC}"
            # 读取requirements.txt文件，逐行安装依赖
            while read -r requirement; do
                # 跳过空行和注释行
                if [[ -z "$requirement" || "$requirement" == \#* ]]; then
                    continue
                fi
                echo -e "${BLUE}安装: $requirement${NC}"
                pip install "$requirement" || echo -e "${RED}安装失败: $requirement${NC}"
            done < requirements.txt
        fi
    else
        echo -e "${RED}未找到requirements.txt文件${NC}"
        exit 1
    fi

    echo -e "${GREEN}依赖安装完成${NC}"
}

# 完整更新流程
update_and_restart() {
    echo -e "${BLUE}开始更新和重启流程...${NC}"

    # 备份当前日志
    if [ -f "$LOG_FILE" ]; then
        backup_file="$LOG_DIR/server_$(date +%Y%m%d_%H%M%S).log"
        cp "$LOG_FILE" "$backup_file"
        echo -e "${BLUE}已备份日志到: $backup_file${NC}"
    fi

    # 更新代码
    update_code

    # 检查并创建虚拟环境
    setup_venv

    # 激活虚拟环境
    activate_venv

    # 安装/更新依赖
    install_dependencies

    # 重启服务
    restart_service

    echo -e "${GREEN}更新和重启完成${NC}"
}

# 初始化环境
setup_environment() {
    echo -e "${BLUE}初始化环境...${NC}"

    # 检查并创建虚拟环境
    setup_venv

    # 激活虚拟环境
    activate_venv

    # 安装依赖
    install_dependencies

    echo -e "${GREEN}环境初始化完成${NC}"
    echo -e "${YELLOW}提示: 现在可以使用 '$0 install' 安装为系统服务${NC}"
}

# 显示帮助信息
show_help() {
    echo -e "${BLUE}DINQ 生产环境部署脚本${NC}"
    echo -e "用法: ./production_deploy.sh [命令]"
    echo -e "\n命令:"
    echo -e "  ${GREEN}setup${NC}     - 初始化环境（创建虚拟环境和安装依赖）"
    echo -e "  ${GREEN}install${NC}   - 安装DINQ服务（需要root权限）"
    echo -e "  ${GREEN}start${NC}     - 启动DINQ服务（需要root权限）"
    echo -e "  ${GREEN}stop${NC}      - 停止DINQ服务（需要root权限）"
    echo -e "  ${GREEN}restart${NC}   - 重启DINQ服务（需要root权限）"
    echo -e "  ${GREEN}status${NC}    - 显示DINQ服务状态"
    echo -e "  ${GREEN}update${NC}    - 更新代码并重启服务（需要root权限）"
    echo -e "  ${GREEN}uninstall${NC} - 卸载DINQ服务（需要root权限）"
    echo -e "  ${GREEN}help${NC}      - 显示此帮助信息"
}

# 主函数
main() {
    case "$1" in
        setup)
            setup_environment
            ;;
        install)
            # 确保环境已经设置好
            if [ ! -d "$VENV_DIR" ]; then
                echo -e "${YELLOW}虚拟环境不存在，请先运行 '$0 setup'${NC}"
                exit 1
            fi
            install_service
            ;;
        start)
            start_service
            ;;
        stop)
            stop_service
            ;;
        restart)
            restart_service
            ;;
        status)
            show_status
            ;;
        update)
            # 确保环境已经设置好
            if [ ! -d "$VENV_DIR" ]; then
                echo -e "${YELLOW}虚拟环境不存在，请先运行 '$0 setup'${NC}"
                exit 1
            fi
            update_and_restart
            ;;
        uninstall)
            uninstall_service
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            echo -e "${YELLOW}未知命令: $1${NC}"
            show_help
            exit 1
            ;;
    esac
}

# 如果没有参数，显示帮助信息
if [ $# -eq 0 ]; then
    show_help
    exit 0
fi

# 执行主函数
main "$1"
