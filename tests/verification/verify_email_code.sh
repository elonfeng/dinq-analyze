#!/bin/bash

# 验证邮箱验证码
USER_ID="LtXQ0x62DpOB88r1x3TL329FbHk1"
BASE_URL="http://localhost:5001"
EMAIL="aihehe123@gmail.com"

# 从命令行参数获取验证码
if [ -z "$1" ]; then
    echo "使用方法: $0 <验证码>"
    echo "例如: $0 123456"
    exit 1
fi

VERIFICATION_CODE="$1"

echo "🔢 验证邮箱验证码"
echo "用户ID: $USER_ID"
echo "邮箱: $EMAIL"
echo "验证码: $VERIFICATION_CODE"
echo ""

curl -X POST "$BASE_URL/api/verification/verify-email" \
  -H "Userid: $USER_ID" \
  -H "Content-Type: application/json" \
  -d "{
    \"email\": \"$EMAIL\",
    \"email_type\": \"edu_email\",
    \"verification_code\": \"$VERIFICATION_CODE\"
  }" | jq '.' || echo "验证完成"
