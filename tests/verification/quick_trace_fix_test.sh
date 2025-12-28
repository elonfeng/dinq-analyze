#!/bin/bash

# 快速测试Trace ID修复效果
echo "🔧 快速测试Trace ID修复效果"
echo "=" * 50

BASE_URL="http://localhost:5001"
CUSTOM_TRACE_ID="fix$(date +%s)"

echo "测试环境: $BASE_URL"
echo "自定义Trace ID: $CUSTOM_TRACE_ID"
echo ""

# 1. 测试scholar查询API（这是出现no-trace问题的地方）
echo "1️⃣ 测试Scholar查询API"
echo ""

echo "发送scholar查询请求..."
response=$(curl -s -X POST "$BASE_URL/api/stream" \
    -H "Content-Type: application/json" \
    -H "Userid: test_user" \
    -H "X-Trace-ID: $CUSTOM_TRACE_ID" \
    -d '{"query": "yigHzW8AAAAJ"}' \
    --max-time 10)

if [ $? -eq 0 ]; then
    echo "✅ 请求发送成功"
    echo "响应长度: $(echo "$response" | wc -c) 字符"
else
    echo "❌ 请求发送失败"
fi

echo ""

# 2. 等待一段时间让日志写入
echo "2️⃣ 等待日志写入..."
sleep 3
echo ""

# 3. 检查日志文件中的trace ID
echo "3️⃣ 检查日志文件中的Trace ID"
echo ""

log_files=(
    "logs/dinq_allin_one.log"
    "../logs/dinq_allin_one.log"
    "../../logs/dinq_allin_one.log"
)

log_found=false
for log_file in "${log_files[@]}"; do
    if [ -f "$log_file" ]; then
        echo "📁 找到日志文件: $log_file"
        
        # 查找我们的trace ID
        trace_lines=$(grep "\[$CUSTOM_TRACE_ID\]" "$log_file" | tail -10)
        
        if [ -n "$trace_lines" ]; then
            echo "✅ 找到包含自定义Trace ID的日志:"
            echo "$trace_lines" | while IFS= read -r line; do
                echo "   $line"
            done
        else
            echo "❌ 未找到包含自定义Trace ID的日志"
        fi
        
        # 检查是否还有no-trace日志
        no_trace_lines=$(tail -50 "$log_file" | grep "\[no-trace\]" | tail -5)
        
        if [ -n "$no_trace_lines" ]; then
            echo "⚠️  仍然发现no-trace日志:"
            echo "$no_trace_lines" | while IFS= read -r line; do
                echo "   $line"
            done
        else
            echo "✅ 未发现新的no-trace日志"
        fi
        
        log_found=true
        break
    fi
done

if [ "$log_found" = false ]; then
    echo "❌ 未找到日志文件"
fi

echo ""

# 4. 测试其他API端点
echo "4️⃣ 测试其他API端点的Trace ID"
echo ""

endpoints=(
    "/api/file-types"
    "/api/top-talents"
)

for endpoint in "${endpoints[@]}"; do
    trace_id="test_${endpoint//\//_}_$(date +%s)"
    
    echo "测试端点: $endpoint"
    response=$(curl -s -I "$BASE_URL$endpoint" -H "X-Trace-ID: $trace_id")
    returned_id=$(echo "$response" | grep -i "x-trace-id" | cut -d' ' -f2 | tr -d '\r')
    
    if [ "$returned_id" = "$trace_id" ]; then
        echo "  ✅ Trace ID传递正常: $returned_id"
    else
        echo "  ❌ Trace ID传递异常: 发送 $trace_id, 返回 $returned_id"
    fi
done

echo ""

# 5. 运行Python测试脚本
echo "5️⃣ 运行详细的Python测试"
echo ""

if [ -f "test_trace_id_fix.py" ]; then
    echo "运行详细测试脚本..."
    python test_trace_id_fix.py
else
    echo "⚠️  未找到详细测试脚本 test_trace_id_fix.py"
fi

echo ""

echo "📋 测试完成！"
echo ""
echo "🔍 结果分析:"
echo "- 如果看到包含自定义Trace ID的日志，说明修复有效"
echo "- 如果仍有no-trace日志，可能需要进一步检查"
echo "- 检查scholar相关的模块是否正确使用了trace logger"
echo ""
echo "📝 下一步:"
echo "1. 如果修复有效，可以部署到生产环境"
echo "2. 如果仍有问题，检查具体的模块和线程创建"
echo "3. 监控生产环境的trace ID使用情况"
echo ""
echo "📚 详细文档: docs/system/TRACE_ID_LOSS_FIX.md"
