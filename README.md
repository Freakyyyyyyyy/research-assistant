# Research Assistant

本地运行的学术研究工作台，支持选题指导、文献检索、PDF 解析、论文精读、框架搭建和研究成果管理。

## 主要功能

- **选题指导**：逐轮明确研究对象、问题、价值和方法，最终方案可保存为选题卡片。
- **论文框架搭建**：基于苏格拉底式提问形成研究问题、论证逻辑、方法和章节结构。
- **文献检索**：将主题转换为英文检索计划，对宽泛主题执行多方向检索，使用 RRF 融合 arXiv 结果。
- **论文库**：管理收藏或上传的论文，支持 PDF 导入、文本解析、OCR、证据检索、快速分析和论文对比。
- **论文精读**：在对话旁查看 PDF 原文，围绕指定论文进行有证据的逐轮讨论。
- **成果管理**：查看、编辑、删除和导出文献卡片、选题方案、论文框架、精读笔记和对比报告。

检索结果不会自动进入论文库；只有收藏或上传的论文才会纳入项目论文库。

## 技术架构

```text
React 18 + TypeScript + Vite + Ant Design + Zustand
                         │ HTTP / SSE
FastAPI + Pydantic + SQLAlchemy
                         ├─ OpenAI-compatible 模型网关
                         ├─ arXiv API
                         ├─ SQLite FTS5
                         └─ PyMuPDF / Tesseract OCR
```

- 主模型用于对话、精读、分析、对比和成果整理。
- 快速模型用于意图分类和会话标题。
- SQLite 保存项目、会话、论文、证据块和成果。
- SSE 用于模型文本的流式输出。

## 环境要求

- Python `>=3.9,<3.13`
- Node.js `>=18`
- 阿里云百炼 API Key
- Tesseract OCR（可选，用于扫描型 PDF）

## 本地启动

### 1. 获取代码

```powershell
git clone https://github.com/Freakyyyyyyyy/research-assistant.git
cd research-assistant
```

### 2. 安装后端

```powershell
python -m pip install -e "backend[test]"
Copy-Item backend\.env.example backend\.env
```

编辑 `backend/.env`，至少填写 `DASHSCOPE_API_KEY`。

### 3. 安装前端

```powershell
cd frontend
npm install
cd ..
```

### 4. 启动

Windows：

```powershell
.\dev-start.bat
```

手动启动后端：

```powershell
python -m uvicorn research_agent.main:app --app-dir backend/src --host 127.0.0.1 --port 8000
```

另开终端启动前端：

```powershell
cd frontend
npm run dev
```

访问 `http://127.0.0.1:5173`。API 文档位于 `http://127.0.0.1:8000/docs`。

## 验证

```powershell
python -m pytest backend\tests -q

cd frontend
npm test
npm run build
```

## 配置

完整参数见 [`backend/.env.example`](backend/.env.example)。

| 变量 | 用途 |
|---|---|
| `DASHSCOPE_API_KEY` | 主模型 API Key |
| `QWEN_MODEL` | 主内容生成模型 |
| `ROUTER_MODEL` | 意图分类和会话标题模型 |
| `DATABASE_PATH` | SQLite 数据库路径 |
| `UPLOAD_DIR` | PDF 存储目录 |
| `TESSERACT_EXECUTABLE` | Tesseract 可执行文件路径 |
| `PRIVACY_PII_SCRUB` | 模型调用前的 PII 模式替换 |
| `PRIVACY_LOCAL_ONLY` | 禁用远程模型调用 |
| `PRIVACY_DATA_TTL_DAYS` | 本地消息和会话保留天数 |

## 数据与隐私

以下内容只保存在本机，且已加入 `.gitignore`：

- `backend/.env`
- `data/app.sqlite3`
- `data/uploads/`
- 解析文本、日志和导出文件

不要将真实 API Key、用户论文或本地数据库提交到版本库。

## 目录

```text
backend/                 FastAPI 后端与 pytest 测试
frontend/                React 前端
docs/                    使用文档
dev-start.bat/.sh        启动脚本
dev-stop.bat/.ps1        Windows 停止脚本
DEPLOYMENT.md            本地部署说明
PROJECT_CURRENT.md       架构与维护说明
```

## 文档

- [本地部署](DEPLOYMENT.md)
- [架构与维护](PROJECT_CURRENT.md)
- [后端 API 与运行说明](backend/README.md)
