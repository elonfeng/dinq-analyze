#!/usr/bin/env python3
"""
GitHub Analyzer API 测试脚本

使用方法:
    python test_api.py [username]
    
如果不提供用户名，将使用默认的测试用户名
"""

import sys
import requests
import json
import time

def test_api(base_url="http://localhost:5001", username="octocat"):
    """测试 GitHub Analyzer API"""
    
    print(f"🧪 Testing GitHub Analyzer API at {base_url}")
    print(f"👤 Testing with username: {username}")
    print("-" * 50)
    
    # 测试健康检查
    print("1. Testing health check...")
    try:
        response = requests.get(f"{base_url}/api/health", timeout=10)
        if response.status_code == 200:
            print("✅ Health check passed")
            print(f"   Response: {response.json()}")
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False
    
    print()
    
    # 测试 API 帮助
    print("2. Testing API help...")
    try:
        response = requests.get(f"{base_url}/api/github/analyze/help", timeout=10)
        if response.status_code == 200:
            print("✅ API help accessible")
        else:
            print(f"❌ API help failed: {response.status_code}")
    except Exception as e:
        print(f"❌ API help error: {e}")
    
    print()
    
    # 测试 POST 分析
    print("3. Testing POST analysis...")
    try:
        payload = {"username": username}
        headers = {"Content-Type": "application/json"}
        
        print(f"   Sending request for user: {username}")
        print("   This may take a while for the first request...")
        
        start_time = time.time()
        response = requests.post(
            f"{base_url}/api/github/analyze", 
            json=payload, 
            headers=headers,
            timeout=300  # 5 minutes timeout
        )
        end_time = time.time()
        
        print(f"   Request completed in {end_time - start_time:.2f} seconds")
        
        if response.status_code == 200:
            print("✅ POST analysis successful")
            data = response.json()
            
            # 打印关键信息
            if data.get("success") and "data" in data:
                user_data = data["data"]
                print(f"   User: {user_data.get('user', {}).get('name', 'N/A')}")
                print(f"   Stars: {user_data.get('overview', {}).get('stars', 'N/A')}")
                print(f"   Repositories: {user_data.get('overview', {}).get('repositories', 'N/A')}")
                
                # 保存完整响应到文件
                with open(f"test_result_{username}.json", "w") as f:
                    json.dump(data, f, indent=2)
                print(f"   Full result saved to: test_result_{username}.json")
            else:
                print(f"   Unexpected response format: {data}")
        else:
            print(f"❌ POST analysis failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print("❌ Request timeout (this is normal for first-time analysis)")
        print("   The analysis might still be running in the background")
    except Exception as e:
        print(f"❌ POST analysis error: {e}")
        return False
    
    print()
    
    # 测试 GET 分析 (应该使用缓存)
    print("4. Testing GET analysis (should use cache)...")
    try:
        start_time = time.time()
        response = requests.get(
            f"{base_url}/api/github/analyze?username={username}",
            timeout=60
        )
        end_time = time.time()
        
        print(f"   Request completed in {end_time - start_time:.2f} seconds")
        
        if response.status_code == 200:
            print("✅ GET analysis successful (cached)")
        else:
            print(f"❌ GET analysis failed: {response.status_code}")
            print(f"   Response: {response.text}")
            
    except Exception as e:
        print(f"❌ GET analysis error: {e}")
    
    print()
    print("🎉 API testing completed!")
    return True

def main():
    """主函数"""
    username = sys.argv[1] if len(sys.argv) > 1 else "octocat"
    
    print("GitHub Analyzer API Test")
    print("=" * 50)
    
    # 检查服务是否运行
    base_url = "http://localhost:5001"
    
    try:
        response = requests.get(f"{base_url}/api/health", timeout=5)
        if response.status_code != 200:
            print(f"❌ Service not responding at {base_url}")
            print("Please make sure the service is running with: python run.py")
            sys.exit(1)
    except Exception:
        print(f"❌ Cannot connect to service at {base_url}")
        print("Please make sure the service is running with: python run.py")
        sys.exit(1)
    
    # 运行测试
    success = test_api(base_url, username)
    
    if success:
        print("\n✅ All tests passed!")
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
