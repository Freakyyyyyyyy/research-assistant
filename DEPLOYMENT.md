# 本地部署指南

本文档适用于 Windows 10/11 和 Linux/WSL 本地演示环境。

## 1. 环境要求

- Python `>=3.9,<3.13`
- Node.js `>=18`
- Git
- Tesseract OCR（可选）
- 阿里云百炼 API Key

检查版本：

```powershell
python --version
node --version
npm --version
git --version
```

## 2. 获取代码

```powershell
git clone https://github.com/Freakyyyyyyyy/research-assistant.git
cd research-assistant
```

## 3. Python 环境

推荐使用独立虚拟环境。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e "backend[test]"
```

Linux/WSL 激活命令：

```bash
source .venv/bin/activate
```

## 4. 后端配置

```powershell
Copy-Item backend\.env.example backend\.env
```

编辑 `backend/.env`：

```dotenv
DASHSCOPE_API_KEY=replace-with-your-api-key
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen3.7-plus

ROUTER_API_KEY=
ROUTER_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
ROUTER_MODEL=deepseek-v4-flash
ROUTER_DISABLE_THINKING=1

DATABASE_PATH=data/app.sqlite3
UPLOAD_DIR=data/uploads
```

`ROUTER_API_KEY` 为空时复用 `DASHSCOPE_API_KEY`。

### OCR（可选）

```dotenv
TESSERACT_EXECUTABLE=C:\Program Files\Tesseract-OCR\tesseract.exe
OCR_LANGUAGE=chi_sim+eng
```

### 隐私配置（可选）

```dotenv
PRIVACY_PII_SCRUB=1
PRIVACY_LOCAL_ONLY=0
PRIVACY_DATA_TTL_DAYS=0
```

## 5. 前端依赖

```powershell
cd frontend
npm install
cd ..
```

## 6. 启动与停止

### Windows 脚本

```powershell
.\dev-start.bat
```

停止：

```powershell
.\dev-stop.bat
```

`dev-start.bat` 默认使用当前环境中的 `python`。如需指定解释器：

```powershell
$env:PYTHON_EXE="C:\path\to\python.exe"
.\dev-start.bat
```

### 手动启动

终端 1：

```powershell
python -m uvicorn research_agent.main:app --app-dir backend/src --host 127.0.0.1 --port 8000
```

终端 2：

```powershell
cd frontend
npm run dev
```

## 7. 访问地址

- 前端：`http://127.0.0.1:5173`
- 健康检查：`http://127.0.0.1:8000/api/health`
- API 文档：`http://127.0.0.1:8000/docs`

## 8. 验证

```powershell
python -m pytest backend\tests -q

cd frontend
npm test
npm run build
```

演示前建议检查：

1. 健康检查返回 `status: ok`。
2. 普通对话可流式输出。
3. 文献检索可返回 arXiv 论文。
4. 收藏后的论文可在论文库中查看。
5. PDF 上传或导入后可打开原文。
6. 成果可查看、编辑和导出。

## 9. 数据目录

```text
data/app.sqlite3
data/uploads/
```

`backend/.env`、`data/`、`frontend/node_modules/` 和 `frontend/dist/` 不应随源码复制或提交。

## 10. 常见问题

### Python 版本不兼容

使用 Python 3.9–3.12 重建虚拟环境。

### 模型不可用

检查 `DASHSCOPE_API_KEY`、`QWEN_BASE_URL` 和模型名称，修改后重启后端。

### 扫描型 PDF 没有可检索文本

安装 Tesseract，设置 `TESSERACT_EXECUTABLE` 和 `OCR_LANGUAGE`，然后重新导入 PDF。

### 端口被占用

先运行 `dev-stop.bat`，或修改启动命令中的端口。
