from flask import Flask, request, jsonify
import logging
import re

from .config import load_config
from .analyzer import GitHubAnalyzer


def create_app() -> Flask:
    """创建 Flask 应用"""
    app = Flask(__name__)

    # 配置日志
    logging.basicConfig(level=logging.INFO)

    # 加载配置
    try:
        config = load_config()
    except ValueError as e:
        logging.error(f"Configuration error: {e}")
        raise

    # 初始化分析器
    analyzer = GitHubAnalyzer(config)

    @app.route('/api/github/analyze', methods=['POST'])
    def analyze_github_user():
        """分析 GitHub 用户的 API 端点"""
        try:
            # 获取请求数据
            data = request.get_json()
            if not data or 'username' not in data:
                return jsonify({
                    'error': 'Missing username in request body',
                    'message': 'Please provide a GitHub username in the request body as {"username": "github_username"}'
                }), 400

            username = data['username'].strip()
            if re.match(r"^\w+://", username):
                matched = re.match(r"^https://github.com/(\w+)", username)
                if matched:
                    username = matched.group(1)
                else:
                    username = None
            if not username:
                return jsonify({
                    'error': 'Invalid username',
                    'message': 'Username cannot be empty'
                }), 400

            logging.info(f"Analyzing GitHub user: {username}")

            # 执行分析
            result = analyzer.get_result(username)

            if result is None:
                return jsonify({
                    'error': 'User not found',
                    'message': f'GitHub user "{username}" does not exist or is not accessible'
                }), 404

            return jsonify({
                'success': True,
                'username': username,
                'data': result
            })

        except Exception as e:
            logging.error(f"Error analyzing user: {str(e)}", exc_info=True)
            return jsonify({
                'error': 'Internal server error',
                'message': 'An error occurred while analyzing the user'
            }), 500

    @app.route('/api/github/analyze', methods=['GET'])
    def analyze_github_user_get():
        """通过 GET 请求分析 GitHub 用户"""
        try:
            username = request.args.get('username')
            if not username:
                return jsonify({
                    'error': 'Missing username parameter',
                    'message': 'Please provide a GitHub username as a query parameter: ?username=github_username'
                }), 400

            username = username.strip()
            if re.match(r"^\w+://", username):
                matched = re.match(r"^https://github.com/(\w+)", username)
                if matched:
                    username = matched.group(1)
                else:
                    username = None
            if not username:
                return jsonify({
                    'error': 'Invalid username',
                    'message': 'Username cannot be empty'
                }), 400

            logging.info(f"Analyzing GitHub user: {username}")

            # 执行分析
            result = analyzer.get_result(username)

            if result is None:
                return jsonify({
                    'error': 'User not found',
                    'message': f'GitHub user "{username}" does not exist or is not accessible'
                }), 404

            return jsonify({
                'success': True,
                'username': username,
                'data': result
            })

        except Exception as e:
            logging.error(f"Error analyzing user: {str(e)}", exc_info=True)
            return jsonify({
                'error': 'Internal server error',
                'message': 'An error occurred while analyzing the user'
            }), 500

    @app.route('/api/health', methods=['GET'])
    def health_check():
        """健康检查端点"""
        return jsonify({
            'status': 'healthy',
            'service': 'GitHub Analyzer API'
        })

    @app.route('/api/github/analyze/help', methods=['GET'])
    def api_help():
        """API 使用说明"""
        return jsonify({
            'service': 'GitHub Analyzer API',
            'endpoints': {
                'POST /api/github/analyze': {
                    'description': 'Analyze a GitHub user',
                    'body': {'username': 'github_username'},
                    'example': 'curl -X POST -H "Content-Type: application/json" -d \'{"username":"octocat"}\' http://localhost:5000/api/github/analyze'
                },
                'GET /api/github/analyze': {
                    'description': 'Analyze a GitHub user via query parameter',
                    'parameters': {'username': 'github_username'},
                    'example': 'curl http://localhost:5000/api/github/analyze?username=octocat'
                },
                'GET /api/health': {
                    'description': 'Health check endpoint'
                }
            },
            'required_environment_variables': [
                'GITHUB_TOKEN',
                'OPENROUTER_API_KEY',
                'CRAWLBASE_TOKEN'
            ]
        })

    # 错误处理
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            'error': 'Not found',
            'message': 'The requested endpoint does not exist'
        }), 404

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({
            'error': 'Internal server error',
            'message': 'An unexpected error occurred'
        }), 500

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
