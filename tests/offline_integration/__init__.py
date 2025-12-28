"""
Offline integration tests (CI-friendly).

特点：
- 不依赖外部 API/网站/云 DB
- 通过 compose 启动本地 Postgres（以及可选 MailHog）
- 关键外部依赖用 stub/mock/fixture 替代
"""

