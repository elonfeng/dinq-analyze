# dinq 重构部署检查清单

## 部署前验证 (本地)

### 1. 代码检查
- [x] 运行 `python3 test_refactoring.py` - 所有测试通过
- [x] 检查 Python 语法: `python3 -m py_compile server/analyze/handlers/**/*.py`
- [ ] 检查导入: `python3 -c "from server.analyze.handlers.registry import get_global_registry; print('OK')"`

### 2. 向后兼容性验证
- [ ] 确认 legacy code path 仍然存在 (未注册 handler 的 cards)
- [ ] 检查 `pipeline.py` 中 handler 分发后有 fallback 到旧逻辑

### 3. 备份
```bash
# 在服务器上创建备份
ssh root@74.48.107.93 "cd /root/dinq-dev && git stash"
ssh root@74.48.107.93 "cd /root/dinq-dev && git branch backup-before-refactoring-$(date +%Y%m%d)"
```

---

## 部署步骤

### Step 1: 提交到 Git
```bash
cd /mnt/d/dev/dinq-work/dinq

# 检查状态
git status

# 添加所有新文件
git add server/analyze/meta_utils.py
git add server/analyze/handlers/
git add REFACTORING_SUMMARY.md
git add DEPLOYMENT_CHECKLIST.md
git add test_refactoring.py

# 添加修改的文件
git add server/tasks/scheduler.py
git add server/analyze/pipeline.py
git add server/analyze/resources/github.py
git add server/analyze/resources/linkedin.py
git add server/analyze/resources/scholar.py

# 提交
git commit -m "Refactor: Fix card output issues + CardHandler architecture

Phase 1 (Emergency Fixes):
- Restrict prune_empty to internal cards only
- Force Quality Gate fallback instead of failing cards
- Standardize _meta.preserve_empty across all sources

Phase 2 (Architecture):
- Implement CardHandler base class + ExecutionContext
- Migrate GitHub handlers (repos, role_model, roast, summary)
- Migrate LinkedIn handlers (colleagues_view, life_well_being)
- Integrate handlers into pipeline.py with legacy fallback

Performance:
- Document existing parallelization capabilities
- Add optimization recommendations in REFACTORING_SUMMARY.md

Testing:
- All smoke tests pass (test_refactoring.py)
- Backward compatible (handlers are opt-in)

See REFACTORING_SUMMARY.md for full details."

# 推送到远程
git push origin main
```

### Step 2: 部署到生产服务器
```bash
# SSH 到服务器
ssh root@74.48.107.93

# 进入项目目录
cd /root/dinq-dev

# 拉取最新代码
git fetch origin
git pull --rebase origin main

# 检查是否有冲突
git status

# 重启服务
systemctl restart dinq-dev

# 检查服务状态
systemctl status dinq-dev
```

### Step 3: 验证部署
```bash
# 检查服务是否运行
curl http://127.0.0.1:8080/health

# 查看最近日志
journalctl -u dinq-dev -n 100 --no-pager

# 检查是否有错误
journalctl -u dinq-dev -n 500 | grep -i "error\|exception\|failed" | tail -20
```

---

## 部署后监控 (前 48 小时)

### 关键指标

1. **Card 完成率**
```bash
# 检查是否有 card.failed 事件
journalctl -u dinq-dev --since "1 hour ago" | grep "card.failed" | wc -l
# 应该接近 0

# 检查 card.completed 事件
journalctl -u dinq-dev --since "1 hour ago" | grep "card.completed" | wc -l
# 应该 > 0
```

2. **Fallback 使用频率**
```bash
# 检查 fallback 警告
journalctl -u dinq-dev --since "1 hour ago" | grep "Quality gate retry exhausted"
# 少量是正常的（LLM 偶尔失败）

# 检查 handler 执行
journalctl -u dinq-dev --since "1 hour ago" | grep "has_handler"
```

3. **错误日志**
```bash
# 查看所有错误
journalctl -u dinq-dev --since "1 hour ago" -p err
# 不应该有新的错误类型

# 查看 Python traceback
journalctl -u dinq-dev --since "1 hour ago" | grep -A 10 "Traceback"
```

### 功能测试

测试关键路径（通过 API 或前端）：

1. **GitHub 分析**
   - [ ] 测试用户: `torvalds`
   - [ ] 验证 repos card 有内容
   - [ ] 验证 role_model card 有内容
   - [ ] 验证 roast card 有内容

2. **LinkedIn 分析**
   - [ ] 测试一个 LinkedIn URL
   - [ ] 验证 colleagues_view card 不是空 `{}`
   - [ ] 验证 life_well_being card 不是空 `{}`

3. **Scholar 分析**
   - [ ] 测试一个 scholar_id
   - [ ] 验证所有 cards 正常完成（legacy path）

### 性能监控

```bash
# 检查平均响应时间
journalctl -u dinq-dev --since "1 hour ago" | grep "duration_ms" | \
  awk '{print $NF}' | sed 's/[^0-9]//g' | \
  awk '{sum+=$1; count++} END {print "Avg:", sum/count "ms"}'

# 检查 job 完成率
journalctl -u dinq-dev --since "1 hour ago" | grep "job.completed" | wc -l
```

---

## 回滚计划

### 如果出现严重问题

```bash
# Step 1: SSH 到服务器
ssh root@74.48.107.93

cd /root/dinq-dev

# Step 2: 回滚到上一个版本
git log --oneline -5  # 找到重构前的 commit
git reset --hard <commit-sha-before-refactoring>

# Step 3: 重启服务
systemctl restart dinq-dev

# Step 4: 验证
curl http://127.0.0.1:8080/health
journalctl -u dinq-dev -n 50
```

### 如果只是小问题（例如某个 handler 有 bug）

可以通过热修复：

```bash
# 在本地修复 handler
vim server/analyze/handlers/github/repos.py

# 提交
git add server/analyze/handlers/github/repos.py
git commit -m "Hotfix: Fix GitHubReposHandler validation"
git push origin main

# 部署
ssh root@74.48.107.93 "cd /root/dinq-dev && git pull && systemctl restart dinq-dev"
```

---

## 成功标准

部署被认为成功如果：

1. **稳定性**
   - [ ] 前 24 小时无 P0 错误
   - [ ] Card 失败率 < 1% (之前 ~5%)
   - [ ] 无服务崩溃或重启

2. **功能性**
   - [ ] GitHub repos/role_model/roast/summary cards 正常输出
   - [ ] LinkedIn colleagues_view/life_well_being cards 不再返回 `{}`
   - [ ] Scholar analysis 保持现有功能（legacy path）

3. **性能**
   - [ ] P50 响应时间无明显增加（< +10%）
   - [ ] Cache 命中率保持稳定
   - [ ] 并发处理能力无下降

---

## 联系人

如有问题，联系：
- 开发者: (你的联系方式)
- 服务器: root@74.48.107.93
- 代码仓库: (你的 Git repo URL)

---

## 参考文档

- 重构详情: `REFACTORING_SUMMARY.md`
- 测试脚本: `test_refactoring.py`
- 服务管理: `systemctl status dinq-dev`
- 日志: `journalctl -u dinq-dev -f`
