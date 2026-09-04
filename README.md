# uStudy Development Repository

这是与生产环境隔离的实验开发版本，聚焦系统分配的课程学习空间、空间内 AI 学习、测验、RAG 和教师教学工具；“数据结构”仍作为默认课程空间保留。

## 目录

- `uStudy-backend/`：FastAPI、PostgreSQL/pgvector、SSE 和 AI 工具链
- `uStudy-web-demo/`：uni-app Vue 3 H5 前端

## 实验边界

- 用户通过阿里云 SMTP 完成邮箱注册和密码找回。
- 实验账号获得永久 `ALPHA` 访问权限。
- 用户登录后从首页进入已分配的一个或多个学习空间，不能自行新建空间。
- 教师可在各自拥有教师身份的课程空间之间切换教学看板、作业管理和教学助教。
- 支付、激活码、钱包、邀请、Quick Chat 和非认证通知邮件均已移除。

## 本地验证

后端：在 `uStudy-backend/` 创建私有 `.env` 后运行 `pytest -m "not e2e"`。

前端：在 `uStudy-web-demo/` 安装依赖后运行 `node scripts/verify-experiment-config.js`，再使用 HBuilderX 构建 H5。
