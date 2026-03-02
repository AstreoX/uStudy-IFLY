# uStudy IFLY Showcase

讯飞比赛评委展示仓库。该仓库是与生产环境隔离的实验版，聚焦固定“数据结构”课程、空间内 AI 学习、测验、RAG 和教师教学看板。

## 目录

- `uStudy-backend/`：FastAPI、PostgreSQL/pgvector、SSE 和 AI 工具链
- `uStudy-web-demo/`：uni-app Vue 3 H5 前端
- `Workflow/`：实验说明、部署交接和验证报告

## 实验边界

- 用户通过阿里云 SMTP 完成邮箱注册和密码找回。
- 实验账号获得永久 `ALPHA` 访问权限。
- 用户进入固定“数据结构”课程；教师拥有只读教学看板。
- 支付、激活码、钱包、邀请、Quick Chat 和非认证通知邮件均已移除。

## 历史

为便于评审，Git 历史从 2026-03-02 的精选基线开始，来源和后续实验提交见 [`docs/history-map.md`](docs/history-map.md)。

## 本地验证

后端：在 `uStudy-backend/` 创建私有 `.env` 后运行 `pytest -m "not e2e"`。

前端：在 `uStudy-web-demo/` 安装依赖后运行 `node scripts/verify-experiment-config.js`，再使用 HBuilderX 构建 H5。
