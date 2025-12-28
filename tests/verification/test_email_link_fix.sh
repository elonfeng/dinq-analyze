#!/bin/bash

# 测试邮箱链接验证修复
USER_ID="LtXQ0x62DpOB88r1x3TL329FbHk1"
BASE_URL="http://localhost:5001"
EMAIL="aihehe123@gmail.com"

echo "🧪 测试邮箱链接验证修复"
echo "用户ID: $USER_ID"
echo "邮箱: $EMAIL"
echo ""

# 1. 确保有验证记录
echo "1️⃣ 开始验证流程..."
curl -s -X POST "$BASE_URL/api/verification/start" \
  -H "Userid: $USER_ID" \
  -H "Content-Type: application/json" \
  -d '{"user_type": "job_seeker"}' > /dev/null

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
  }' > /dev/null

echo "3️⃣ 发送邮箱验证码..."
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
    echo "🔗 邮件中的链接现在应该包含用户ID，可以直接点击验证"
    echo ""
    echo "📋 邮件链接格式应该是:"
    echo "http://localhost:5001/verify-email?code=XXXXXX&email=$EMAIL&type=edu_email&user_id=$USER_ID"
    echo ""
    echo "🌐 你也可以直接访问验证页面测试:"
    echo "http://localhost:5001/verify-email?code=123456&email=$EMAIL&type=edu_email&user_id=$USER_ID"
else
    echo ""
    echo "❌ 邮箱验证码发送失败"
    echo "请检查服务器日志获取详细错误信息"
fi

echo ""
echo "🔧 修复内容:"
echo "1. 邮件模板中的链接现在包含用户ID"
echo "2. 创建了专门的邮箱验证页面 (/verify-email)"
echo "3. 添加了通过邮箱查找验证码的方法"
echo "4. 验证页面会自动验证邮箱并显示结果"
