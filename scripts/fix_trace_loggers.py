#!/usr/bin/env python3
"""
批量修复项目中的日志记录器以支持trace ID

这个脚本会扫描项目中的Python文件，找到使用普通logger的地方，
并将它们替换为支持trace ID的logger。
"""

import os
import re
import sys
from pathlib import Path

def find_python_files(directory):
    """查找目录中的所有Python文件"""
    python_files = []
    for root, dirs, files in os.walk(directory):
        # 跳过一些不需要处理的目录
        dirs[:] = [d for d in dirs if d not in ['.git', '__pycache__', '.pytest_cache', 'node_modules']]
        
        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))
    
    return python_files

def analyze_logger_usage(file_path):
    """分析文件中的logger使用情况"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 查找logger定义
        logger_patterns = [
            r'logger\s*=\s*logging\.getLogger\([^)]*\)',
            r'logger\s*=\s*logging\.getLogger\(\s*__name__\s*\)',
            r'logger\s*=\s*logging\.getLogger\(\s*[\'"][^\'"]*[\'"]\s*\)',
        ]
        
        logger_definitions = []
        for pattern in logger_patterns:
            matches = re.finditer(pattern, content, re.MULTILINE)
            for match in matches:
                logger_definitions.append({
                    'match': match.group(),
                    'start': match.start(),
                    'end': match.end(),
                    'line_num': content[:match.start()].count('\n') + 1
                })
        
        # 检查是否已经使用了trace logger
        has_trace_import = 'get_trace_logger' in content
        
        return {
            'file_path': file_path,
            'logger_definitions': logger_definitions,
            'has_trace_import': has_trace_import,
            'content': content
        }
        
    except Exception as e:
        print(f"Error analyzing {file_path}: {e}")
        return None

def fix_logger_in_file(analysis):
    """修复文件中的logger定义"""
    if not analysis or analysis['has_trace_import']:
        return False  # 已经修复过或无需修复
    
    if not analysis['logger_definitions']:
        return False  # 没有logger定义
    
    content = analysis['content']
    file_path = analysis['file_path']
    
    # 为每个logger定义创建修复
    fixes = []
    for logger_def in analysis['logger_definitions']:
        original = logger_def['match']
        
        # 提取logger名称
        name_match = re.search(r'logging\.getLogger\(([^)]*)\)', original)
        if name_match:
            logger_name = name_match.group(1)
            
            # 创建新的logger定义
            new_definition = f"""# 设置日志记录器（支持trace ID）
try:
    from server.utils.trace_context import get_trace_logger
    logger = get_trace_logger({logger_name})
except ImportError:
    # Fallback to regular logger if trace context is not available
    logger = logging.getLogger({logger_name})"""
            
            fixes.append({
                'original': original,
                'new': new_definition,
                'start': logger_def['start'],
                'end': logger_def['end']
            })
    
    if not fixes:
        return False
    
    # 应用修复（从后往前，避免位置偏移）
    new_content = content
    for fix in reversed(fixes):
        new_content = new_content[:fix['start']] + fix['new'] + new_content[fix['end']:]
    
    # 写回文件
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return True
    except Exception as e:
        print(f"Error writing to {file_path}: {e}")
        return False

def main():
    """主函数"""
    print("🔧 批量修复Trace Logger工具")
    print("=" * 50)
    
    # 获取项目根目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    
    print(f"项目根目录: {project_root}")
    
    # 需要处理的目录
    target_directories = [
        os.path.join(project_root, 'server'),
        # 可以添加其他目录
    ]
    
    all_files = []
    for directory in target_directories:
        if os.path.exists(directory):
            files = find_python_files(directory)
            all_files.extend(files)
            print(f"找到 {len(files)} 个Python文件在 {directory}")
    
    print(f"总共找到 {len(all_files)} 个Python文件")
    print()
    
    # 分析和修复
    fixed_files = []
    skipped_files = []
    error_files = []
    
    for file_path in all_files:
        print(f"处理: {os.path.relpath(file_path, project_root)}")
        
        analysis = analyze_logger_usage(file_path)
        if not analysis:
            error_files.append(file_path)
            print("  ❌ 分析失败")
            continue
        
        if analysis['has_trace_import']:
            skipped_files.append(file_path)
            print("  ✅ 已经使用trace logger")
            continue
        
        if not analysis['logger_definitions']:
            skipped_files.append(file_path)
            print("  ⏭️  没有logger定义")
            continue
        
        # 尝试修复
        if fix_logger_in_file(analysis):
            fixed_files.append(file_path)
            print(f"  🔧 已修复 ({len(analysis['logger_definitions'])} 个logger)")
        else:
            error_files.append(file_path)
            print("  ❌ 修复失败")
    
    print()
    print("📊 处理结果统计")
    print("=" * 50)
    print(f"总文件数: {len(all_files)}")
    print(f"已修复: {len(fixed_files)}")
    print(f"已跳过: {len(skipped_files)}")
    print(f"错误: {len(error_files)}")
    
    if fixed_files:
        print(f"\n✅ 已修复的文件:")
        for file_path in fixed_files:
            print(f"  - {os.path.relpath(file_path, project_root)}")
    
    if error_files:
        print(f"\n❌ 处理失败的文件:")
        for file_path in error_files:
            print(f"  - {os.path.relpath(file_path, project_root)}")
    
    print(f"\n📝 下一步:")
    print("1. 检查修复的文件确保语法正确")
    print("2. 测试应用程序确保功能正常")
    print("3. 查看日志文件确认trace ID正常显示")
    print("4. 如有问题，可以使用git恢复文件")

if __name__ == "__main__":
    main()
