# 🌐 TEM-4 备考系统 — 公网部署指南

项目已完全适配云平台部署，以下提供两种免费部署方案。

---

## 方案一：Render.com（推荐，永久免费地址）

### 步骤 1：推送代码到 GitHub

```bash
cd tem4-prep
git remote add origin https://github.com/你的用户名/tem4-prep.git
git branch -M main
git push -u origin main
```

### 步骤 2：在 Render.com 创建服务

1. 打开 https://render.com ，用 GitHub 账号登录
2. 点击 **"New"** → **"Web Service"**
3. 选择你的 `tem4-prep` 仓库
4. 配置如下：
   - **Name**: `tem4-prep`（自定义）
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn wsgi:app`
   - **Instance Type**: Free
5. 点击 **"Create Web Service"**

### 步骤 3：等待部署完成

约 2-3 分钟后，你会获得一个永久公网地址：
```
https://tem4-prep-xxxx.onrender.com
```

> ⚠️ 免费版服务会在 15 分钟无流量后休眠，首次访问需等待约 30 秒唤醒。

---

## 方案二：本地启动 + 内网穿透（临时公网地址）

### 使用 ngrok（需注册免费账号）

```bash
# 1. 注册 ngrok: https://dashboard.ngrok.com/signup
# 2. 获取 authtoken: https://dashboard.ngrok.com/get-started/your-authtoken
# 3. 安装并启动
ngrok config add-authtoken YOUR_TOKEN
cd tem4-prep
python app.py          # 终端1：启动 Flask
ngrok http 5000        # 终端2：启动隧道
```

ngrok 会显示一个公网地址如 `https://xxxx.ngrok-free.app`

### 使用 localtunnel（无需注册，需 Node.js）

```bash
cd tem4-prep
python app.py                          # 终端1
npx localtunnel --port 5000            # 终端2
```

localtunnel 会显示一个公网地址如 `https://xxxx.loca.lt`

---

## 项目已包含的部署文件

| 文件 | 用途 |
|---|---|
| `wsgi.py` | Gunicorn WSGI 入口 |
| `Procfile` | 云平台启动命令 |
| `requirements.txt` | Python 依赖（含 gunicorn） |
| `runtime.txt` | Python 版本声明 |
| `.gitignore` | Git 忽略规则 |
| `config.py` | 支持环境变量配置（DATABASE_URL, SECRET_KEY） |

---

## 环境变量（可选）

| 变量 | 说明 | 默认值 |
|---|---|---|
| `SECRET_KEY` | Flask 密钥 | `tem4-prep-dev-key-2026` |
| `DATABASE_URL` | SQLite 数据库路径 | `data/tem4.db` |
