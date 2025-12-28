#!/bin/bash

# 测试邮箱验证修复
USER_ID="LtXQ0x62DpOB88r1x3TL329FbHk1"
BASE_URL="http://localhost:5001"
EMAIL="aihehe123@gmail.com"

echo "🧪 测试邮箱验证修复"
echo "用户ID: $USER_ID"
echo "邮箱: $EMAIL"
echo ""

# 1. 确保有验证记录
echo "1️⃣ 开始验证流程..."
curl -s -X POST "$BASE_URL/api/verification/start" \
  -H "Userid: $USER_ID" \
  -H "Content-Type: application/json" \
  -d '{"user_type": "job_seeker"}' | jq '.success' || echo "已存在"

echo ""

# 2. 更新基本信息
echo "2️⃣ 更新基本信息..."
curl -s -X POST "$BASE_URL/api/verification/update-step" \
  -H "Userid: $USER_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "step": "basic_info",
    "data": {
      "full_name": "张三",
      "current_role": "研究员",
      "current_title": "博士研究生"
    },
    "advance_to_next": true
  }' | jq '.success' || echo "更新完成"

echo ""

# 3. 发送邮箱验证 (修复后)
echo "3️⃣ 发送邮箱验证码..."
echo "curl -X POST \"$BASE_URL/api/verification/send-email-verification\" \\"
echo "  -H \"Userid: $USER_ID\" \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -d '{"
echo "    \"email\": \"$EMAIL\","
echo "    \"email_type\": \"edu_email\""
echo "  }'"
echo ""

RESULT=$(curl -s -X POST "$BASE_URL/api/verification/send-email-verification" \
  -H "Userid: $USER_ID" \
  -H "Content-Type: application/json" \
  -d "{
    \"email\": \"$EMAIL\",
    \"email_type\": \"edu_email\"
  }")

echo "响应结果:"
echo "$RESULT" | jq '.' || echo "$RESULT"

# 检查是否成功
SUCCESS=$(echo "$RESULT" | jq -r '.success' 2>/dev/null)
if [ "$SUCCESS" = "true" ]; then
    echo ""
    echo "✅ 邮箱验证码发送成功！"
    echo "📧 请检查邮箱: $EMAIL"
    echo ""
    echo "🔢 收到验证码后，使用以下命令验证:"
    echo "curl -X POST \"$BASE_URL/api/verification/verify-email\" \\"
    echo "  -H \"Userid: $USER_ID\" \\"
    echo "  -H \"Content-Type: application/json\" \\"
    echo "  -d '{"
    echo "    \"email\": \"$EMAIL\","
    echo "    \"email_type\": \"edu_email\","
    echo "    \"verification_code\": \"你收到的验证码\""
    echo "  }'"
else
    echo ""
    echo "❌ 邮箱验证码发送失败"
    echo "请检查服务器日志获取详细错误信息"
fi
