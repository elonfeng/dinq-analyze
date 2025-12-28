#!/usr/bin/env python3
"""
每日Twitter监控运行脚本

这个脚本用于每天运行一次Twitter监控，获取当天新发的人才流动信息。
可以通过cron job或其他定时任务工具来调用。
"""

import sys
import os
import logging
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('twitter_monitor_daily.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def main():
    """主函数"""
    try:
        logger.info("=== 开始每日Twitter监控 ===")
        
        # 导入并运行监控
        from talent_transfer_agent.twitter_monitor import run_once
        
        # 运行一次监控
        processed_count = run_once()
        
        logger.info(f"=== 每日监控完成，处理了 {processed_count} 条人才流动信息 ===")
        
        return 0
        
    except Exception as e:
        logger.error(f"每日监控运行失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 