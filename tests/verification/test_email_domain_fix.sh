#!/bin/bash

# 测试邮箱域名环境变量修复
USER_ID="LtXQ0x62DpOB88r1x3TL329FbHk1"
BASE_URL="http://localhost:5001"
EMAIL="aihehe123@gmail.com"

echo "🧪 测试邮箱域名环境变量修复"
echo "用户ID: $USER_ID"
echo "邮箱: $EMAIL"
echo "当前BASE_URL: $BASE_URL"
echo ""

# 测试不同的环境变量设置
echo "📋 测试场景:"
echo "1. 默认环境 (localhost:5001)"
echo "2. 生产环境 (dinq.io)"
echo ""

# 1. 确保有验证记录
echo "1️⃣ 准备测试数据..."
curl -s -X POST "$BASE_URL/api/verification/start" \
  -H "Userid: $USER_ID" \
  -H "Content-Type: application/json" \
  -d '{"user_type": "job_seeker"}' > /dev/null

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

echo "✅ 测试数据准备完成"
echo ""

# 2. 测试默认环境 (localhost)
echo "2️⃣ 测试默认环境 (localhost:5001)..."
echo "发送验证邮件..."

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
    echo "🔗 邮件中的链接应该使用: http://localhost:5001"
else
    echo ""
    echo "❌ 邮箱验证码发送失败"
fi

echo ""
echo "🔧 环境变量说明:"
echo "- DINQ_API_DOMAIN: 控制邮件中链接的域名"
echo "- 默认值: http://localhost:5001"
echo "- 生产环境应设置为: https://dinq.io"
echo ""
echo "📝 设置生产环境的方法:"
echo "export DINQ_API_DOMAIN=https://dinq.io"
echo ""
echo "🌐 邮件链接格式:"
echo "验证链接: {DINQ_API_DOMAIN}/verify-email?code=XXXXXX&email=$EMAIL&type=edu_email&user_id=$USER_ID"
echo "仪表板链接: {DINQ_API_DOMAIN}/dashboard"
echo ""
echo "🎯 修复内容:"
echo "1. 添加了环境变量 DINQ_API_DOMAIN 支持"
echo "2. 邮件模板中的链接现在使用动态域名"
echo "3. 支持开发环境和生产环境的自动切换"
echo "4. 在服务初始化时记录当前使用的BASE_URL"
