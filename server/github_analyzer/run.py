#!/usr/bin/env python3
"""
GitHub Analyzer Flask 应用启动脚本

使用方法:
    python run.py

环境变量配置:
    请确保设置了以下环境变量或创建 .env 文件:
    - GITHUB_TOKEN
    - OPENROUTER_API_KEY
    - CRAWLBASE_TOKEN
"""

import os
import sys

from server.github_analyzer.flask_app import create_app

def main():
    """启动 Flask 应用"""
    try:
        app = create_app()

        # 从环境变量获取配置
        host = os.getenv('FLASK_HOST', '0.0.0.0')
        port = int(os.getenv('FLASK_PORT', 5001))
        debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'

        print(f"🚀 Starting GitHub Analyzer API...")
        print(f"📍 Server: http://{host}:{port}")
        print(f"🔍 API Endpoint: http://{host}:{port}/api/github/analyze")
        print(f"❓ Help: http://{host}:{port}/api/github/analyze/help")
        print(f"💚 Health Check: http://{host}:{port}/api/health")

        app.run(
            host=host,
            port=port,
            debug=debug
        )

    except ValueError as e:
        print(f"❌ Configuration Error: {e}")
        print("Please check your environment variables or .env file")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
