#!/bin/bash

# 用户验证系统 CURL 测试脚本
# 使用用户ID: LtXQ0x62DpOB88r1x3TL329FbHk1

# 配置
BASE_URL="http://localhost:5001"
USER_ID="LtXQ0x62DpOB88r1x3TL329FbHk1"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印分隔线
print_separator() {
    echo -e "${BLUE}================================================${NC}"
}

# 打印步骤标题
print_step() {
    echo -e "\n${YELLOW}$1${NC}"
    print_separator
}

# 打印成功信息
print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

# 打印错误信息
print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# 等待用户按键
wait_for_key() {
    echo -e "\n${BLUE}按任意键继续...${NC}"
    read -n 1 -s
}

echo -e "${GREEN}🚀 用户验证系统 CURL 测试脚本${NC}"
echo -e "${BLUE}用户ID: ${USER_ID}${NC}"
echo -e "${BLUE}服务地址: ${BASE_URL}${NC}"
print_separator

# 1. 获取验证状态
print_step "1. 获取当前验证状态"
echo "curl -X GET \"${BASE_URL}/api/verification/status\" \\"
echo "  -H \"Userid: ${USER_ID}\" \\"
echo "  -H \"Content-Type: application/json\""
echo ""

curl -X GET "${BASE_URL}/api/verification/status" \
  -H "Userid: ${USER_ID}" \
  -H "Content-Type: application/json" \
  -w "\n\nHTTP Status: %{http_code}\n" \
  -s | jq '.' 2>/dev/null || echo "Response received (jq not available for formatting)"

wait_for_key

# 2. 开始验证流程 - 求职者
print_step "2. 开始验证流程 (求职者)"
echo "curl -X POST \"${BASE_URL}/api/verification/start\" \\"
echo "  -H \"Userid: ${USER_ID}\" \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -d '{\"user_type\": \"job_seeker\"}'"
echo ""

curl -X POST "${BASE_URL}/api/verification/start" \
  -H "Userid: ${USER_ID}" \
  -H "Content-Type: application/json" \
  -d '{"user_type": "job_seeker"}' \
  -w "\n\nHTTP Status: %{http_code}\n" \
  -s | jq '.' 2>/dev/null || echo "Response received (jq not available for formatting)"

wait_for_key

# 3. 更新基本信息
print_step "3. 更新基本信息步骤"
echo "curl -X POST \"${BASE_URL}/api/verification/update-step\" \\"
echo "  -H \"Userid: ${USER_ID}\" \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -d '{"
echo "    \"step\": \"basic_info\","
echo "    \"data\": {"
echo "      \"full_name\": \"张三\","
echo "      \"current_role\": \"研究员\","
echo "      \"current_title\": \"博士研究生\","
echo "      \"research_fields\": [\"机器学习\", \"计算机视觉\"]"
echo "    },"
echo "    \"advance_to_next\": true"
echo "  }'"
echo ""

curl -X POST "${BASE_URL}/api/verification/update-step" \
  -H "Userid: ${USER_ID}" \
  -H "Content-Type: application/json" \
  -d '{
    "step": "basic_info",
    "data": {
      "full_name": "张三",
      "current_role": "研究员",
      "current_title": "博士研究生",
      "research_fields": ["机器学习", "计算机视觉"]
    },
    "advance_to_next": true
  }' \
  -w "\n\nHTTP Status: %{http_code}\n" \
  -s | jq '.' 2>/dev/null || echo "Response received (jq not available for formatting)"

wait_for_key

# 4. 发送教育邮箱验证
print_step "4. 发送教育邮箱验证码"
echo "curl -X POST \"${BASE_URL}/api/verification/send-email-verification\" \\"
echo "  -H \"Userid: ${USER_ID}\" \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -d '{"
echo "    \"email\": \"test@stanford.edu\","
echo "    \"email_type\": \"edu_email\""
echo "  }'"
echo ""

curl -X POST "${BASE_URL}/api/verification/send-email-verification" \
  -H "Userid: ${USER_ID}" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@stanford.edu",
    "email_type": "edu_email"
  }' \
  -w "\n\nHTTP Status: %{http_code}\n" \
  -s | jq '.' 2>/dev/null || echo "Response received (jq not available for formatting)"

wait_for_key

# 5. 验证邮箱（模拟验证码）
print_step "5. 验证教育邮箱 (使用模拟验证码: 123456)"
echo "curl -X POST \"${BASE_URL}/api/verification/verify-email\" \\"
echo "  -H \"Userid: ${USER_ID}\" \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -d '{"
echo "    \"email\": \"test@stanford.edu\","
echo "    \"email_type\": \"edu_email\","
echo "    \"verification_code\": \"123456\""
echo "  }'"
echo ""

curl -X POST "${BASE_URL}/api/verification/verify-email" \
  -H "Userid: ${USER_ID}" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@stanford.edu",
    "email_type": "edu_email",
    "verification_code": "123456"
  }' \
  -w "\n\nHTTP Status: %{http_code}\n" \
  -s | jq '.' 2>/dev/null || echo "Response received (jq not available for formatting)"

wait_for_key

# 6. 更新教育信息
print_step "6. 更新教育信息步骤"
echo "curl -X POST \"${BASE_URL}/api/verification/update-step\" \\"
echo "  -H \"Userid: ${USER_ID}\" \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -d '{"
echo "    \"step\": \"education\","
echo "    \"data\": {"
echo "      \"university_name\": \"斯坦福大学\","
echo "      \"degree_level\": \"博士\","
echo "      \"department_major\": \"计算机科学\","
echo "      \"edu_email\": \"test@stanford.edu\""
echo "    },"
echo "    \"advance_to_next\": true"
echo "  }'"
echo ""

curl -X POST "${BASE_URL}/api/verification/update-step" \
  -H "Userid: ${USER_ID}" \
  -H "Content-Type: application/json" \
  -d '{
    "step": "education",
    "data": {
      "university_name": "斯坦福大学",
      "degree_level": "博士",
      "department_major": "计算机科学",
      "edu_email": "test@stanford.edu"
    },
    "advance_to_next": true
  }' \
  -w "\n\nHTTP Status: %{http_code}\n" \
  -s | jq '.' 2>/dev/null || echo "Response received (jq not available for formatting)"

wait_for_key

# 7. 更新专业信息
print_step "7. 更新专业信息步骤"
echo "curl -X POST \"${BASE_URL}/api/verification/update-step\" \\"
echo "  -H \"Userid: ${USER_ID}\" \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -d '{"
echo "    \"step\": \"professional\","
echo "    \"data\": {"
echo "      \"job_title\": \"研究助理\","
echo "      \"company_org\": \"斯坦福AI实验室\","
echo "      \"work_research_summary\": \"专注于深度学习和计算机视觉研究，发表多篇顶级会议论文。\""
echo "    },"
echo "    \"advance_to_next\": true"
echo "  }'"
echo ""

curl -X POST "${BASE_URL}/api/verification/update-step" \
  -H "Userid: ${USER_ID}" \
  -H "Content-Type: application/json" \
  -d '{
    "step": "professional",
    "data": {
      "job_title": "研究助理",
      "company_org": "斯坦福AI实验室",
      "work_research_summary": "专注于深度学习和计算机视觉研究，发表多篇顶级会议论文。"
    },
    "advance_to_next": true
  }' \
  -w "\n\nHTTP Status: %{http_code}\n" \
  -s | jq '.' 2>/dev/null || echo "Response received (jq not available for formatting)"

wait_for_key

# 8. 更新社交账号信息
print_step "8. 更新社交账号信息步骤"
echo "curl -X POST \"${BASE_URL}/api/verification/update-step\" \\"
echo "  -H \"Userid: ${USER_ID}\" \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -d '{"
echo "    \"step\": \"social_accounts\","
echo "    \"data\": {"
echo "      \"github_username\": \"zhangsan_ai\","
echo "      \"linkedin_url\": \"https://linkedin.com/in/zhangsan\","
echo "      \"twitter_username\": \"zhangsan_research\""
echo "    },"
echo "    \"advance_to_next\": false"
echo "  }'"
echo ""

curl -X POST "${BASE_URL}/api/verification/update-step" \
  -H "Userid: ${USER_ID}" \
  -H "Content-Type: application/json" \
  -d '{
    "step": "social_accounts",
    "data": {
      "github_username": "zhangsan_ai",
      "linkedin_url": "https://linkedin.com/in/zhangsan",
      "twitter_username": "zhangsan_research"
    },
    "advance_to_next": false
  }' \
  -w "\n\nHTTP Status: %{http_code}\n" \
  -s | jq '.' 2>/dev/null || echo "Response received (jq not available for formatting)"

wait_for_key

# 9. 完成验证
print_step "9. 完成验证流程"
echo "curl -X POST \"${BASE_URL}/api/verification/complete\" \\"
echo "  -H \"Userid: ${USER_ID}\" \\"
echo "  -H \"Content-Type: application/json\""
echo ""

curl -X POST "${BASE_URL}/api/verification/complete" \
  -H "Userid: ${USER_ID}" \
  -H "Content-Type: application/json" \
  -w "\n\nHTTP Status: %{http_code}\n" \
  -s | jq '.' 2>/dev/null || echo "Response received (jq not available for formatting)"

wait_for_key

# 10. 再次获取验证状态
print_step "10. 获取最终验证状态"
echo "curl -X GET \"${BASE_URL}/api/verification/status\" \\"
echo "  -H \"Userid: ${USER_ID}\" \\"
echo "  -H \"Content-Type: application/json\""
echo ""

curl -X GET "${BASE_URL}/api/verification/status" \
  -H "Userid: ${USER_ID}" \
  -H "Content-Type: application/json" \
  -w "\n\nHTTP Status: %{http_code}\n" \
  -s | jq '.' 2>/dev/null || echo "Response received (jq not available for formatting)"

wait_for_key

# 11. 获取验证统计信息
print_step "11. 获取验证统计信息"
echo "curl -X GET \"${BASE_URL}/api/verification/stats\" \\"
echo "  -H \"Content-Type: application/json\""
echo ""

curl -X GET "${BASE_URL}/api/verification/stats" \
  -H "Content-Type: application/json" \
  -w "\n\nHTTP Status: %{http_code}\n" \
  -s | jq '.' 2>/dev/null || echo "Response received (jq not available for formatting)"

print_separator
echo -e "${GREEN}🎉 测试完成！${NC}"
echo -e "${BLUE}如果所有接口都返回200状态码，说明验证系统工作正常。${NC}"
print_separator
