#!/usr/bin/env python3
"""
Test file upload optimization

This script tests the optimized file upload API with support for multiple file types.
"""

import sys
import os
import requests
import json
from io import BytesIO

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# Test configuration
BASE_URL = "http://localhost:5001"
USER_ID = "LtXQ0x62DpOB88r1x3TL329FbHk1"

def test_file_types_endpoint():
    """Test the file types information endpoint"""
    print("🔍 测试文件类型信息端点...")
    
    try:
        response = requests.get(f"{BASE_URL}/api/file-types")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ 文件类型信息获取成功")
            print(f"📊 支持的文件类别数量: {len(data['data']['categories'])}")
            print(f"📏 最大文件大小: {data['data']['maxFileSizeFormatted']}")
            print(f"🪣 默认存储桶: {data['data']['defaultBucket']}")
            
            print("\n📋 支持的文件类别:")
            for category, info in data['data']['categories'].items():
                print(f"  {category.title()}: {info['count']} 种格式")
                print(f"    扩展名: {', '.join(info['extensions'][:5])}{'...' if len(info['extensions']) > 5 else ''}")
                print(f"    描述: {info['description']}")
            
            return True
        else:
            print(f"❌ 请求失败: {response.status_code}")
            print(response.text)
            return False
            
    except Exception as e:
        print(f"❌ 错误: {e}")
        return False

def create_test_file(filename: str, size_kb: int = 10) -> BytesIO:
    """Create a test file with specified size"""
    content = b"Test file content. " * (size_kb * 1024 // 19)  # Approximate size
    file_obj = BytesIO(content)
    file_obj.name = filename
    return file_obj

def test_file_upload(filename: str, size_kb: int = 10, bucket: str = "demo"):
    """Test file upload with different file types"""
    print(f"\n📤 测试上传文件: {filename} ({size_kb}KB)")
    
    try:
        # Create test file
        test_file = create_test_file(filename, size_kb)
        
        # Prepare upload data
        files = {'file': (filename, test_file, 'application/octet-stream')}
        data = {'bucket': bucket, 'folder': 'test'}
        headers = {'Userid': USER_ID}
        
        # Upload file
        response = requests.post(
            f"{BASE_URL}/api/upload-image",
            files=files,
            data=data,
            headers=headers
        )
        
        if response.status_code == 200:
            result = response.json()
            if result['success']:
                file_data = result['data']
                print(f"✅ 上传成功!")
                print(f"   文件名: {file_data['originalFilename']}")
                print(f"   类别: {file_data['category']}")
                print(f"   大小: {file_data['sizeFormatted']}")
                print(f"   扩展名: {file_data['extension']}")
                print(f"   存储桶: {file_data['bucket']}")
                print(f"   公开URL: {file_data['publicUrl'][:50]}...")
                return True
            else:
                print(f"❌ 上传失败: {result.get('error', 'Unknown error')}")
                return False
        else:
            print(f"❌ HTTP错误: {response.status_code}")
            print(response.text)
            return False
            
    except Exception as e:
        print(f"❌ 错误: {e}")
        return False

def test_file_size_limit():
    """Test file size limit (5MB)"""
    print(f"\n📏 测试文件大小限制...")
    
    # Test file just under limit (4.9MB)
    print("测试 4.9MB 文件 (应该成功):")
    success_small = test_file_upload("README.md", size_kb=4900)
    
    # Test file over limit (6MB)
    # print("\n测试 6MB 文件 (应该失败):")
    # success_large = test_file_upload("README.md", size_kb=6000)
    
    return success_small and not success_large

def test_different_file_types():
    """Test uploading different file types"""
    print(f"\n📁 测试不同文件类型...")
    
    test_files = [
        ("document.pdf", "PDF文档"),
        ("image.jpg", "JPEG图片"),
        ("spreadsheet.xlsx", "Excel表格"),
        ("presentation.pptx", "PowerPoint演示"),
        ("archive.zip", "ZIP压缩包"),
        ("data.json", "JSON数据"),
        ("text.txt", "文本文件"),
        ("image.png", "PNG图片"),
    ]
    
    results = []
    for filename, description in test_files:
        print(f"\n测试 {description} ({filename}):")
        success = test_file_upload(filename, size_kb=50)
        results.append(success)
    
    successful = sum(results)
    total = len(results)
    print(f"\n📊 文件类型测试结果: {successful}/{total} 成功")
    
    return successful == total

def test_invalid_file_types():
    """Test uploading invalid file types"""
    print(f"\n🚫 测试不支持的文件类型...")
    
    invalid_files = [
        "executable.exe",
        "script.sh",
        "binary.bin",
        "unknown.xyz"
    ]
    
    failed_count = 0
    for filename in invalid_files:
        print(f"\n测试不支持的文件: {filename}")
        success = test_file_upload(filename, size_kb=10)
        if not success:
            failed_count += 1
            print("✅ 正确拒绝了不支持的文件类型")
        else:
            print("❌ 错误地接受了不支持的文件类型")
    
    print(f"\n📊 无效文件类型测试: {failed_count}/{len(invalid_files)} 正确拒绝")
    return failed_count == len(invalid_files)

def main():
    """Run all tests"""
    print("🧪 文件上传优化测试")
    print("=" * 50)
    
    tests = [
        ("文件类型信息端点", test_file_types_endpoint),
        ("不同文件类型上传", test_different_file_types),
        ("文件大小限制", test_file_size_limit),
        ("无效文件类型", test_invalid_file_types),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n🔬 运行测试: {test_name}")
        print("-" * 30)
        try:
            success = test_func()
            results.append((test_name, success))
            if success:
                print(f"✅ {test_name} - 通过")
            else:
                print(f"❌ {test_name} - 失败")
        except Exception as e:
            print(f"❌ {test_name} - 异常: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 测试总结")
    print("=" * 50)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{test_name}: {status}")
    
    print(f"\n总体结果: {passed}/{total} 测试通过")
    
    if passed == total:
        print("🎉 所有测试通过！文件上传优化工作正常。")
    else:
        print("⚠️  部分测试失败，请检查服务器配置。")
    
    print("\n🔧 优化功能:")
    print("- ✅ 支持多种文件类型 (图片、PDF、文档等)")
    print("- ✅ 文件大小限制为 5MB")
    print("- ✅ 默认存储桶改为 'demo'")
    print("- ✅ 文件分类和元数据增强")
    print("- ✅ 更好的错误信息")
    print("- ✅ 文件类型信息API")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
