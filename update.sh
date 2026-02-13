#!/bin/bash

# uStudy Backend 更新部署脚本
# 使用方法 (在服务器上执行):
#   cd /opt/ustudy-backend
#   bash update.sh

set -e

echo "========================================="
echo "  uStudy Backend 更新部署"
echo "========================================="
echo ""

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 1. 拉取最新代码
echo -e "${GREEN}[1/5] 拉取最新代码...${NC}"
git pull

# 2. 停止服务
echo -e "${GREEN}[2/5] 停止当前服务...${NC}"
docker compose down

# 3. 重新构建镜像
echo -e "${GREEN}[3/5] 重新构建镜像...${NC}"
docker compose build --no-cache

# 4. 启动服务
echo -e "${GREEN}[4/5] 启动服务...${NC}"
docker compose up -d

# 等待服务启动
echo "等待服务启动..."
sleep 10

# 5. 运行数据库迁移
echo -e "${GREEN}[5/5] 运行数据库迁移...${NC}"
docker compose exec -T backend alembic upgrade head

# 测试服务
echo ""
echo -e "${GREEN}测试服务...${NC}"
sleep 5

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
