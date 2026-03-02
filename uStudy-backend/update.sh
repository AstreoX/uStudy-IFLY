#!/bin/bash

# uStudy Backend 更新部署脚本
# 使用方法 (在服务器上执行):
#   cd /opt/ustudy-backend
#   bash update.sh
#   bash update.sh --full-rebuild
#   bash update.sh --skip-migrate

set -euo pipefail

echo "========================================="
echo "  uStudy Backend 更新部署"
echo "========================================="
echo ""

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 参数解析
FULL_REBUILD=false
SKIP_MIGRATE=false

for arg in "$@"; do
    case "$arg" in
        --full-rebuild)
            FULL_REBUILD=true
            ;;
        --skip-migrate)
            SKIP_MIGRATE=true
            ;;
        *)
            echo -e "${YELLOW}未知参数: $arg${NC}"
            echo "可用参数: --full-rebuild --skip-migrate"
            exit 1
            ;;
    esac
done

# 1. 拉取最新代码
echo -e "${GREEN}[1/5] 拉取最新代码...${NC}"
git pull --ff-only

# 2. 构建/更新服务
if [ "$FULL_REBUILD" = true ]; then
    echo -e "${GREEN}[2/5] 全量重建镜像（无缓存）...${NC}"
    docker compose build --no-cache
    echo -e "${GREEN}[3/5] 启动服务...${NC}"
    docker compose up -d
else
    echo -e "${GREEN}[2/5] 增量构建并更新服务...${NC}"
    docker compose up -d --build
fi

# 3. 等待服务启动
echo -e "${GREEN}[3/5] 等待服务启动...${NC}"
sleep 6

# 4. 运行数据库迁移（可跳过）
if [ "$SKIP_MIGRATE" = true ]; then
    echo -e "${YELLOW}[4/5] 跳过数据库迁移 (--skip-migrate)${NC}"
else
    echo -e "${GREEN}[4/5] 运行数据库迁移...${NC}"
    docker compose exec -T backend alembic upgrade head
fi

# 测试服务
echo ""
echo -e "${GREEN}[5/5] 测试服务...${NC}"
sleep 3

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health)
if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ 更新成功!${NC}"
else
    echo -e "${YELLOW}⚠ 服务可能未启动,请检查日志:${NC}"
    echo "  docker compose logs -f"
fi

# 显示容器状态
echo ""
echo -e "${GREEN}容器状态:${NC}"
docker compose ps

echo ""
echo "========================================="
echo -e "${GREEN}更新完成!${NC}"
echo "========================================="
echo ""
echo "查看日志: docker compose logs -f backend"
echo ""
