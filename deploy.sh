#!/bin/bash

# uStudy Backend 快速部署脚本
# 使用方法:
#   1. 上传此脚本到服务器: scp deploy.sh root@your-server-ip:/root/
#   2. SSH 登录服务器: ssh root@your-server-ip
#   3. 运行脚本: bash deploy.sh

set -e  # 遇到错误立即退出

echo "========================================="
echo "  uStudy Backend 服务器部署脚本"
echo "========================================="
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查是否为 root 用户
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}请使用 root 用户运行此脚本${NC}"
  echo "使用: sudo bash deploy.sh"
  exit 1
fi

# 1. 系统更新
echo -e "${GREEN}[1/8] 更新系统...${NC}"
apt update && apt upgrade -y
apt install -y curl wget git vim htop

# 2. 安装 Docker
echo -e "${GREEN}[2/8] 安装 Docker...${NC}"
if ! command -v docker &> /dev/null; then
    echo "正在安装 Docker..."
    curl -fsSL https://get.docker.com | bash
    systemctl enable docker
    systemctl start docker
    apt install -y docker-compose-plugin
else
    echo "Docker 已安装,跳过"
fi

docker --version
docker compose version

# 3. 创建部署目录
echo -e "${GREEN}[3/8] 创建部署目录...${NC}"
DEPLOY_DIR="/opt/ustudy-backend"
mkdir -p $DEPLOY_DIR
cd $DEPLOY_DIR

# 4. 克隆代码 (需要用户提供仓库地址)
echo -e "${GREEN}[4/8] 获取代码...${NC}"
echo -e "${YELLOW}请输入 Git 仓库地址 (例如: https://github.com/user/repo.git):${NC}"
read -r GIT_REPO

if [ -z "$GIT_REPO" ]; then
    echo -e "${RED}未输入仓库地址,跳过克隆步骤${NC}"
    echo -e "${YELLOW}请手动上传代码到 $DEPLOY_DIR${NC}"
else
    if [ -d ".git" ]; then
        echo "仓库已存在,拉取最新代码..."
        git pull
    else
        echo "克隆代码仓库..."
        git clone $GIT_REPO .
    fi
fi

# 5. 配置环境变量
echo -e "${GREEN}[5/8] 配置环境变量...${NC}"
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        echo -e "${YELLOW}已创建 .env 文件,请编辑配置:${NC}"
        echo "  nano .env"
        echo ""
        echo -e "${YELLOW}必须配置的变量:${NC}"
        echo "  - DB_PASSWORD"
        echo "  - SECRET_KEY"
        echo "  - JWT_SECRET_KEY"
        echo "  - OPENROUTER_API_KEY"
        echo "  - RESEND_API_KEY"
        echo ""
        echo -e "${YELLOW}是否现在编辑? (y/n):${NC}"
        read -r EDIT_ENV
        if [ "$EDIT_ENV" = "y" ]; then
            nano .env
        fi
    else
        echo -e "${RED}未找到 .env.example 文件${NC}"
        exit 1
    fi
else
    echo ".env 文件已存在,跳过"
fi

# 6. 启动服务
echo -e "${GREEN}[6/8] 启动服务...${NC}"
docker compose up -d

# 等待服务启动
echo "等待服务启动..."
sleep 10

# 7. 数据库初始化
echo -e "${GREEN}[7/8] 初始化数据库...${NC}"
echo -e "${YELLOW}是否运行数据库迁移? (y/n):${NC}"
read -r RUN_MIGRATION
if [ "$RUN_MIGRATION" = "y" ]; then
    docker compose exec -T backend alembic upgrade head
fi

# 8. 测试服务
echo -e "${GREEN}[8/8] 测试服务...${NC}"
sleep 5

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health)
if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ 服务启动成功!${NC}"
else
    echo -e "${RED}✗ 服务启动失败,请检查日志:${NC}"
    echo "  docker compose logs -f"
    exit 1
fi

# 显示容器状态
echo ""
echo -e "${GREEN}容器状态:${NC}"
docker compose ps

# 完成提示
echo ""
echo "========================================="
echo -e "${GREEN}部署完成!${NC}"
echo "========================================="
echo ""
echo "下一步操作:"
echo "  1. 访问 API 文档: http://$(curl -s ifconfig.me):8000/docs"
echo "  2. 查看日志: docker compose logs -f"
echo "  3. 配置 Nginx: 参考 deployment-checklist.md"
echo "  4. 配置 SSL: sudo certbot --nginx -d yourdomain.com"
echo ""
echo "日常维护命令:"
echo "  启动: docker compose up -d"
echo "  停止: docker compose down"
echo "  重启: docker compose restart"
echo "  日志: docker compose logs -f"
echo ""
