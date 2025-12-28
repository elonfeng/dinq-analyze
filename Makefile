.PHONY: help unit offline smoke perf scorecard key-status compose-up compose-up-mailhog compose-down

help:
	@echo "Targets:"
	@echo "  unit        - 离线单测（CI/本地）"
	@echo "  offline     - 离线集成测试（需要 docker compose）"
	@echo "  compose-up  - 启动本地依赖（Postgres）"
	@echo "  compose-up-mailhog - 启动本地邮件收件箱（MailHog，可选）"
	@echo "  compose-down- 关闭并清理本地依赖"
	@echo "  smoke       - 在线 smoke（需 DINQ_RUN_ONLINE_SMOKE=true）"
	@echo "  perf        - 本地性能微基准（不联网）"
	@echo "  scorecard   - 导出测试&性能评分卡（reports/scorecard/）"
	@echo "  key-status  - 输出 env/key 状态（脱敏）"

unit:
	./scripts/ci/test_unit.sh

offline:
	./scripts/ci/test_offline_integration.sh

smoke:
	./scripts/ci/test_online_smoke.sh

perf:
	PYTHONPATH=. python3 bench/sse_bench.py --events 2000

scorecard:
	python3 scripts/ci/scorecard.py

key-status:
	PYTHONPATH=. python3 scripts/ci/key_status.py

compose-up:
	docker compose up -d postgres

compose-up-mailhog:
	docker compose up -d mailhog

compose-down:
	docker compose down -v
