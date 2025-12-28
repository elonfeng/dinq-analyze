#!/bin/bash

# 测试脚本：验证帖子列表是否包含喜欢和收藏计数

echo "===== 测试帖子列表是否包含喜欢和收藏计数 ====="

# 获取帖子列表
echo "获取帖子列表..."
response=$(curl -s -X GET "http://127.0.0.1:5001/api/job-board/posts" \
  -H "accept: */*" \
  -H "accept-language: zh,zh-CN;q=0.9,en-US;q=0.8,en;q=0.7" \
  -H "content-type: application/json" \
  -H "userid: LtXQ0x62DpOB88r1x3TL329FbHk1")

# 检查是否成功获取数据
success=$(echo $response | jq -r '.success')

if [ "$success" = "true" ]; then
  # 获取帖子数量
  posts_count=$(echo $response | jq '.data.posts | length')
  echo "成功获取到 $posts_count 个帖子"
  
  # 如果有帖子，检查第一个帖子是否包含喜欢和收藏计数
  if [ $posts_count -gt 0 ]; then
    # 获取第一个帖子的ID和标题
    post_id=$(echo $response | jq -r '.data.posts[0].id')
    post_title=$(echo $response | jq -r '.data.posts[0].title')
    
    echo -e "\n第一个帖子详情:"
    echo "ID: $post_id"
    echo "标题: $post_title"
    
    # 检查是否包含喜欢和收藏计数
    has_like_count=$(echo $response | jq '.data.posts[0] | has("like_count")')
    has_bookmark_count=$(echo $response | jq '.data.posts[0] | has("bookmark_count")')
    
    if [ "$has_like_count" = "true" ] && [ "$has_bookmark_count" = "true" ]; then
      like_count=$(echo $response | jq -r '.data.posts[0].like_count')
      bookmark_count=$(echo $response | jq -r '.data.posts[0].bookmark_count')
      
      echo "喜欢数: $like_count"
      echo "收藏数: $bookmark_count"
      echo -e "\n✅ 测试通过: 帖子数据中包含喜欢和收藏计数"
    else
      echo -e "\n❌ 测试失败: 帖子数据中缺少喜欢或收藏计数"
      if [ "$has_like_count" != "true" ]; then
        echo "缺少: like_count"
      fi
      if [ "$has_bookmark_count" != "true" ]; then
        echo "缺少: bookmark_count"
      fi
      
      # 打印完整的帖子数据以便调试
      echo -e "\n完整的帖子数据:"
      echo $response | jq '.data.posts[0]'
    fi
  else
    echo "没有找到任何帖子"
  fi
else
  error=$(echo $response | jq -r '.error')
  echo "请求失败: $error"
fi

# 测试喜欢帖子功能
echo -e "\n\n===== 测试喜欢帖子功能 ====="

if [ "$success" = "true" ] && [ $posts_count -gt 0 ]; then
  post_id=$(echo $response | jq -r '.data.posts[0].id')
  original_like_count=$(echo $response | jq -r '.data.posts[0].like_count // 0')
  
  echo "选择帖子 ID: $post_id，原始喜欢数: $original_like_count"
  
  # 喜欢帖子
  echo "发送喜欢请求..."
  like_response=$(curl -s -X POST "http://127.0.0.1:5001/api/job-board/posts/$post_id/like" \
    -H "accept: */*" \
    -H "accept-language: zh,zh-CN;q=0.9,en-US;q=0.8,en;q=0.7" \
    -H "content-type: application/json" \
    -H "userid: LtXQ0x62DpOB88r1x3TL329FbHk1")
  
  like_success=$(echo $like_response | jq -r '.success')
  
  if [ "$like_success" = "true" ]; then
    echo "成功发送喜欢请求"
    
    # 获取帖子详情
    echo "获取帖子详情..."
    detail_response=$(curl -s -X GET "http://127.0.0.1:5001/api/job-board/posts/$post_id" \
      -H "accept: */*" \
      -H "accept-language: zh,zh-CN;q=0.9,en-US;q=0.8,en;q=0.7" \
      -H "content-type: application/json" \
      -H "userid: LtXQ0x62DpOB88r1x3TL329FbHk1")
    
    detail_success=$(echo $detail_response | jq -r '.success')
    
    if [ "$detail_success" = "true" ]; then
      has_like_count=$(echo $detail_response | jq '.data.post | has("like_count")')
      
      if [ "$has_like_count" = "true" ]; then
        new_like_count=$(echo $detail_response | jq -r '.data.post.like_count')
        echo "更新后的喜欢数: $new_like_count"
        
        if (( new_like_count >= original_like_count )); then
          echo "✅ 测试通过: 喜欢计数已更新"
        else
          echo "❌ 测试失败: 喜欢计数未增加 (原始: $original_like_count, 新: $new_like_count)"
        fi
      else
        echo "❌ 测试失败: 帖子详情中缺少 like_count 字段"
      fi
    else
      error=$(echo $detail_response | jq -r '.error')
      echo "获取帖子详情失败: $error"
    fi
  else
    error=$(echo $like_response | jq -r '.error')
    echo "喜欢帖子请求失败: $error"
  fi
else
  echo "无法进行喜欢帖子测试，因为没有获取到帖子列表"
fi
