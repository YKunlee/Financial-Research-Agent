# Docker 部署指南 / Docker Deployment Guide

## 中文说明

### 📋 前提条件

- 已安装 Docker Desktop（Mac/Windows）或 Docker Engine（Linux）
- 已安装 Docker Compose（通常随 Docker Desktop 自动安装）

### 🚀 快速启动

#### 方式一：使用 Docker Compose（推荐）

这种方式会自动启动 Redis 和金融研究应用，最简单方便。

```bash
# 1. 配置环境变量
cp .env.example .env

# 2. 编辑 .env 文件，至少需要设置：
#    OPENAI_API_KEY=your_openai_key_here

# 3. 启动所有服务
docker-compose up -d

# 4. 查看服务状态
docker-compose ps

# 5. 查看日志
docker-compose logs -f finresearch
```

启动成功后，访问 **http://localhost:8501** 即可使用 Web 界面。

#### 方式二：单独构建和运行

如果你想更灵活地控制容器，可以单独构建镜像：

```bash
# 1. 构建镜像
docker build -t finresearch-agent:latest .

# 2. 启动 Redis（如果还没运行）
docker run -d --name redis \
  -p 6379:6379 \
  redis:7-alpine

# 3. 运行金融研究应用
docker run -d --name finresearch \
  -p 8501:8501 \
  -e REDIS_URL=redis://host.docker.internal:6379/0 \
  -e OPENAI_API_KEY=your_key \
  finresearch-agent:latest

# 4. 查看日志
docker logs -f finresearch
```

### 🔧 命令行工具使用

如果你想在容器内运行命令行工具（而不是 Web 界面）：

```bash
# 分析某个股票
docker-compose run --rm finresearch \
  finresearch --query "Apple" --as-of 2025-12-31

# 生成 IPO 报告
docker-compose run --rm finresearch \
  finresearch-ipo --input /app/data/hk_ipos.json

# 进入容器交互式终端
docker-compose exec finresearch /bin/bash
```

### 🛑 停止和清理

```bash
# 停止服务
docker-compose stop

# 停止并删除容器
docker-compose down

# 停止、删除容器并清理数据卷
docker-compose down -v
```

### 📝 环境变量说明

在 `.env` 文件中可以配置以下变量：

| 变量名 | 必需 | 说明 | 默认值 |
|--------|------|------|--------|
| `REDIS_URL` | 否 | Redis 连接地址 | `redis://redis:6379/0` |
| `OPENAI_API_KEY` | 是 | OpenAI API 密钥 | 无 |
| `OPENAI_MODEL` | 否 | 使用的模型 | `gpt-4o-mini` |
| `MARKET_DATA_PROVIDER` | 否 | 市场数据提供商 | `stooq` |
| `ALPHAVANTAGE_API_KEY` | 否 | Alpha Vantage API 密钥 | 无 |
| `NEWSAPI_KEY` | 否 | NewsAPI 密钥 | 无 |

### 🔍 故障排查

#### 问题：无法连接到 Redis

检查 Redis 服务是否正常运行：

```bash
docker-compose ps redis
docker-compose logs redis
```

#### 问题：端口被占用

如果 8501 或 6379 端口已被占用，可以修改 `docker-compose.yml`：

```yaml
ports:
  - "8502:8501"  # 改用 8502 端口
```

#### 问题：查看应用日志

```bash
docker-compose logs -f finresearch
```

---

## English Documentation

### 📋 Prerequisites

- Docker Desktop (Mac/Windows) or Docker Engine (Linux) installed
- Docker Compose installed (usually comes with Docker Desktop)

### 🚀 Quick Start

#### Option 1: Using Docker Compose (Recommended)

This will automatically start both Redis and the financial research application.

```bash
# 1. Copy environment variables
cp .env.example .env

# 2. Edit .env file, at least set:
#    OPENAI_API_KEY=your_openai_key_here

# 3. Start all services
docker-compose up -d

# 4. Check service status
docker-compose ps

# 5. View logs
docker-compose logs -f finresearch
```

Once started, visit **http://localhost:8501** to access the web interface.

#### Option 2: Build and Run Separately

For more control over containers:

```bash
# 1. Build image
docker build -t finresearch-agent:latest .

# 2. Start Redis (if not already running)
docker run -d --name redis \
  -p 6379:6379 \
  redis:7-alpine

# 3. Run financial research application
docker run -d --name finresearch \
  -p 8501:8501 \
  -e REDIS_URL=redis://host.docker.internal:6379/0 \
  -e OPENAI_API_KEY=your_key \
  finresearch-agent:latest

# 4. View logs
docker logs -f finresearch
```

### 🔧 CLI Tools Usage

To run command-line tools inside the container (instead of web UI):

```bash
# Analyze a stock
docker-compose run --rm finresearch \
  finresearch --query "Apple" --as-of 2025-12-31

# Generate IPO report
docker-compose run --rm finresearch \
  finresearch-ipo --input /app/data/hk_ipos.json

# Enter interactive shell
docker-compose exec finresearch /bin/bash
```

### 🛑 Stop and Cleanup

```bash
# Stop services
docker-compose stop

# Stop and remove containers
docker-compose down

# Stop, remove containers and clean up volumes
docker-compose down -v
```

### 📝 Environment Variables

Configure these variables in your `.env` file:

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `REDIS_URL` | No | Redis connection URL | `redis://redis:6379/0` |
| `OPENAI_API_KEY` | Yes | OpenAI API key | None |
| `OPENAI_MODEL` | No | Model to use | `gpt-4o-mini` |
| `MARKET_DATA_PROVIDER` | No | Market data provider | `stooq` |
| `ALPHAVANTAGE_API_KEY` | No | Alpha Vantage API key | None |
| `NEWSAPI_KEY` | No | NewsAPI key | None |

### 🔍 Troubleshooting

#### Issue: Cannot connect to Redis

Check if Redis service is running:

```bash
docker-compose ps redis
docker-compose logs redis
```

#### Issue: Port already in use

If port 8501 or 6379 is already in use, modify `docker-compose.yml`:

```yaml
ports:
  - "8502:8501"  # Use port 8502 instead
```

#### Issue: View application logs

```bash
docker-compose logs -f finresearch
```

### 🎯 Benefits of Docker Deployment

✅ **Cross-platform**: Same image works on Mac, Windows, and Linux  
✅ **Consistent environment**: No Python version or dependency conflicts  
✅ **One-click startup**: Redis and application auto-configured  
✅ **Easy distribution**: Push to Docker Hub for others to use  
✅ **Isolated**: Doesn't interfere with system Python installation
