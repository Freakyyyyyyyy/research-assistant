# Backend

FastAPI 后端，负责项目数据、流式对话、文献检索、PDF 解析、证据索引和研究成果。

## 安装

在仓库根目录运行：

```powershell
python -m pip install -e "backend[test]"
Copy-Item backend\.env.example backend\.env
```

填写 `backend/.env` 中的 `DASHSCOPE_API_KEY`。其他配置见 `.env.example`。

## 启动

```powershell
python -m uvicorn research_agent.main:app --app-dir backend/src --host 127.0.0.1 --port 8000 --reload
```

- API 文档：`http://127.0.0.1:8000/docs`
- 健康检查：`http://127.0.0.1:8000/api/health`

## 会话 API

```text
POST /api/chat/stream
Content-Type: application/json
```

请求示例：

```json
{
  "content": "帮我检索启发式算法相关论文"
}
```

SSE 事件：

| 事件 | 内容 |
|---|---|
| `mode` | 会话模式 |
| `metadata` | 项目、会话和标题 |
| `search_results` | 文献检索结果 |
| `evidence` | 论文证据页码 |
| `artifact` | 已生成成果 |
| `framework_card_offer` | 论文框架保存入口 |
| `topic_guidance_card_offer` | 选题方案保存入口 |
| `guided_reading_card_offer` | 精读笔记保存入口 |
| `token` | 流式文本 |
| `done` | 完成 |
| `error` | 脱敏错误 |

## 会话模式

- `other`：普通研究问答
- `topic_guidance`：选题指导
- `framework_building`：论文框架搭建
- `literature_discovery`：文献检索
- `paper_reading`：指定论文精读

意图分类使用 `ROUTER_MODEL`，主内容使用 `QWEN_MODEL`。`mode_override` 可显式指定模式。

## 文献检索

`LiteratureDiscoveryService` 执行以下步骤：

1. 判断主题粒度并生成英文检索计划。
2. 对宽泛主题生成 4–7 条互补子检索式。
3. 执行 arXiv 检索。
4. 按 arXiv ID 去重，使用加权 Reciprocal Rank Fusion 排序。
5. 从融合候选中生成推荐。

arXiv 客户端对共享连接加锁，保留库自带的请求间隔控制。检索阶段只读取题录和摘要，不下载 PDF。

## PDF 与证据

```text
POST /api/papers/upload
POST /api/papers/{paper_id}/import-pdf
GET  /api/papers/{paper_id}/pdf
GET  /api/papers/{paper_id}/evidence?q=<query>
```

默认限制：

- PDF 最大 10 MB
- 最多解析 60 页
- 优先读取 PDF 文本层
- 文本过少时使用 Tesseract OCR（需配置）

解析结果写入 SQLite FTS5 证据索引，记录页码、章节、文本和 OCR 标记。

## 论文分析与成果

```text
POST /api/papers/{paper_id}/quick-analysis
POST /api/papers/compare
POST /api/chat/framework/card
POST /api/chat/topic/card
POST /api/chat/guided-reading/card
GET  /api/projects/{project_id}/artifacts
GET  /api/artifacts/{artifact_id}
PATCH /api/artifacts/{artifact_id}
DELETE /api/artifacts/{artifact_id}
GET  /api/artifacts/{artifact_id}/markdown
```

快速分析和论文对比只使用已解析的论文文本。论文对比接受同一项目内 2–3 篇论文。

## 任务

```text
GET  /api/tasks/{task_id}
POST /api/tasks/{task_id}/cancel
POST /api/tasks/{task_id}/retry
```

PDF 上传和导入使用后台任务。应用启动时，遗留的 `pending` 和 `processing` 任务会标记为 `interrupted`。

## 运行设置与诊断

```text
GET  /api/system/settings
POST /api/system/check-storage
POST /api/system/check-ocr
POST /api/system/check-model
POST /api/system/wipe-data
```

设置和诊断接口不返回 API Key、完整异常、论文文本或模型输出。

## 数据位置

```text
data/app.sqlite3
data/uploads/
```

路径可通过 `DATABASE_PATH` 和 `UPLOAD_DIR` 修改。

## 测试

```powershell
python -m pytest backend\tests -q
```

测试使用本地假网关和假检索提供器，不调用真实模型或 arXiv。
