#!/bin/bash

# 快速测试Trace ID功能
echo "🔍 快速测试Trace ID功能"
echo "=" * 50

BASE_URL="http://localhost:5001"
CUSTOM_TRACE_ID="test$(date +%s)"

echo "测试环境: $BASE_URL"
echo "自定义Trace ID: $CUSTOM_TRACE_ID"
echo ""

# 1. 测试自动生成的Trace ID
echo "1️⃣ 测试自动生成的Trace ID"
echo ""

response1=$(curl -s -I "$BASE_URL/api/file-types")
auto_trace_id=$(echo "$response1" | grep -i "x-trace-id" | cut -d' ' -f2 | tr -d '\r')

if [ -n "$auto_trace_id" ]; then
    echo "✅ 自动生成的Trace ID: $auto_trace_id"
else
    echo "❌ 未找到自动生成的Trace ID"
fi

echo ""

# 2. 测试自定义Trace ID
echo "2️⃣ 测试自定义Trace ID传递"
echo ""

response2=$(curl -s -I "$BASE_URL/api/file-types" -H "X-Trace-ID: $CUSTOM_TRACE_ID")
returned_trace_id=$(echo "$response2" | grep -i "x-trace-id" | cut -d' ' -f2 | tr -d '\r')

if [ "$returned_trace_id" = "$CUSTOM_TRACE_ID" ]; then
    echo "✅ 自定义Trace ID传递成功: $returned_trace_id"
else
    echo "❌ 自定义Trace ID传递失败"
    echo "   发送: $CUSTOM_TRACE_ID"
    echo "   返回: $returned_trace_id"
fi

echo ""

# 3. 测试多个并发请求
echo "3️⃣ 测试并发请求的Trace ID隔离"
echo ""

for i in {1..3}; do
    trace_id="batch${i}"
    response=$(curl -s -I "$BASE_URL/api/file-types" -H "X-Trace-ID: $trace_id")
    returned_id=$(echo "$response" | grep -i "x-trace-id" | cut -d' ' -f2 | tr -d '\r')
    
    if [ "$returned_id" = "$trace_id" ]; then
        echo "✅ 请求 $i: $trace_id -> $returned_id"
    else
        echo "❌ 请求 $i: $trace_id -> $returned_id"
    fi
done

echo ""

# 4. 检查日志文件
echo "4️⃣ 检查日志文件中的Trace ID"
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
        
        # 查找最近的trace ID
        recent_traces=$(tail -20 "$log_file" | grep -o '\[[a-z0-9]\{8\}\]' | tail -5)
        
        if [ -n "$recent_traces" ]; then
            echo "✅ 最近的Trace IDs:"
            echo "$recent_traces" | while read trace; do
                echo "   $trace"
            done
        else
            echo "❌ 未找到Trace ID格式的日志"
        fi
        
        log_found=true
        break
    fi
done

if [ "$log_found" = false ]; then
    echo "❌ 未找到日志文件"
fi

echo ""

# 5. 测试POST请求
echo "5️⃣ 测试POST请求的Trace ID"
echo ""

post_trace_id="post$(date +%s)"
response3=$(curl -s -I "$BASE_URL/api/file-upload-backup" \
    -X POST \
    -H "X-Trace-ID: $post_trace_id" \
    -H "Userid: test_user" \
    -H "Content-Type: application/json" \
    -d '{}')

post_returned_id=$(echo "$response3" | grep -i "x-trace-id" | cut -d' ' -f2 | tr -d '\r')

if [ "$post_returned_id" = "$post_trace_id" ]; then
    echo "✅ POST请求Trace ID传递成功: $post_returned_id"
else
    echo "❌ POST请求Trace ID传递失败"
    echo "   发送: $post_trace_id"
    echo "   返回: $post_returned_id"
fi

echo ""

echo "📋 测试完成！"
echo ""
echo "🔍 结果分析:"
echo "- 如果所有测试都显示✅，说明Trace ID功能正常工作"
echo "- 如果有❌，请检查服务器是否正在运行，或查看详细错误信息"
echo ""
echo "📝 下一步:"
echo "1. 查看日志文件确认Trace ID正确记录"
echo "2. 在代码中使用 get_trace_logger() 替换普通logger"
echo "3. 在客户端请求中添加 X-Trace-ID 头进行调试"
echo ""
echo "📚 详细文档: docs/system/REQUEST_TRACING_SYSTEM.md"
