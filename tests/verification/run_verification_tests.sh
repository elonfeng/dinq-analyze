#!/bin/bash

# 用户验证系统测试脚本
# 用户ID: LtXQ0x62DpOB88r1x3TL329FbHk1

BASE_URL="http://localhost:5001"
USER_ID="LtXQ0x62DpOB88r1x3TL329FbHk1"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 测试函数
test_api() {
    local test_name="$1"
    local method="$2"
    local endpoint="$3"
    local headers="$4"
    local data="$5"
    
    echo -e "\n${YELLOW}🧪 测试: ${test_name}${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    if [ "$method" = "GET" ]; then
        echo "curl -X GET \"${BASE_URL}${endpoint}\" ${headers}"
        response=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X GET "${BASE_URL}${endpoint}" ${headers})
    else
        echo "curl -X ${method} \"${BASE_URL}${endpoint}\" ${headers} -d '${data}'"
        response=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X ${method} "${BASE_URL}${endpoint}" ${headers} -d "${data}")
    fi
    
    # 分离响应体和状态码
    http_status=$(echo "$response" | grep "HTTP_STATUS:" | cut -d: -f2)
    response_body=$(echo "$response" | sed '/HTTP_STATUS:/d')
    
    echo -e "\n${BLUE}响应状态码:${NC} $http_status"
    echo -e "${BLUE}响应内容:${NC}"
    echo "$response_body" | jq '.' 2>/dev/null || echo "$response_body"
    
    if [ "$http_status" = "200" ] || [ "$http_status" = "201" ]; then
        echo -e "${GREEN}✅ 测试通过${NC}"
    else
        echo -e "${RED}❌ 测试失败${NC}"
    fi
    
    echo -e "\n${BLUE}按回车键继续下一个测试...${NC}"
    read
}

echo -e "${GREEN}🚀 用户验证系统 API 测试${NC}"
echo -e "${BLUE}用户ID: ${USER_ID}${NC}"
echo -e "${BLUE}服务地址: ${BASE_URL}${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# 测试1: 获取验证状态
test_api "获取验证状态" "GET" "/api/verification/status" "-H \"Userid: ${USER_ID}\"" ""

# 测试2: 开始验证流程
test_api "开始验证流程" "POST" "/api/verification/start" "-H \"Userid: ${USER_ID}\" -H \"Content-Type: application/json\"" '{"user_type": "job_seeker"}'

# 测试3: 更新基本信息
test_api "更新基本信息" "POST" "/api/verification/update-step" "-H \"Userid: ${USER_ID}\" -H \"Content-Type: application/json\"" '{
  "step": "basic_info",
  "data": {
    "full_name": "张三",
    "current_role": "研究员",
    "current_title": "博士研究生",
    "research_fields": ["机器学习", "计算机视觉"]
  },
  "advance_to_next": true
}'

# 测试4: 发送邮箱验证
test_api "发送邮箱验证码" "POST" "/api/verification/send-email-verification" "-H \"Userid: ${USER_ID}\" -H \"Content-Type: application/json\"" '{
  "email": "test@stanford.edu",
  "email_type": "edu_email"
}'

# 测试5: 更新教育信息
test_api "更新教育信息" "POST" "/api/verification/update-step" "-H \"Userid: ${USER_ID}\" -H \"Content-Type: application/json\"" '{
  "step": "education",
  "data": {
    "university_name": "斯坦福大学",
    "degree_level": "博士",
    "department_major": "计算机科学",
    "edu_email": "test@stanford.edu"
  },
  "advance_to_next": true
}'

# 测试6: 更新专业信息
test_api "更新专业信息" "POST" "/api/verification/update-step" "-H \"Userid: ${USER_ID}\" -H \"Content-Type: application/json\"" '{
  "step": "professional",
  "data": {
    "job_title": "研究助理",
    "company_org": "斯坦福AI实验室",
    "work_research_summary": "专注于深度学习和计算机视觉研究，发表多篇顶级会议论文。"
  },
  "advance_to_next": true
}'

# 测试7: 更新社交账号
test_api "更新社交账号" "POST" "/api/verification/update-step" "-H \"Userid: ${USER_ID}\" -H \"Content-Type: application/json\"" '{
  "step": "social_accounts",
  "data": {
    "github_username": "zhangsan_ai",
    "linkedin_url": "https://linkedin.com/in/zhangsan",
    "twitter_username": "zhangsan_research"
  }
}'

# 测试8: 完成验证
test_api "完成验证流程" "POST" "/api/verification/complete" "-H \"Userid: ${USER_ID}\"" ""

# 测试9: 获取最终状态
test_api "获取最终验证状态" "GET" "/api/verification/status" "-H \"Userid: ${USER_ID}\"" ""

# 测试10: 获取统计信息
test_api "获取验证统计信息" "GET" "/api/verification/stats" "" ""

echo -e "\n${GREEN}🎉 所有测试完成！${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
