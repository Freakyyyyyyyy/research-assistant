# 架构与维护说明

## 产品边界

系统以研究项目为数据边界，每个项目包含会话、论文库和研究成果。

当前功能：

- 普通研究问答
- 选题指导
- 论文框架搭建
- arXiv 文献检索与收藏
- PDF 上传、导入、解析与 OCR
- 论文精读、快速分析和论文对比
- 成果查看、编辑、删除、来源回链和 Markdown 导出

文献检索结果只保存题录缓存；收藏或上传后才进入项目论文库。论文精读必须指定 `paper_id`，不在会话中推测目标论文。

## 后端结构

```text
backend/src/research_agent/
├─ api/                    HTTP 和 SSE 路由
├─ db/                     SQLAlchemy 模型与 SQLite 引擎
├─ repositories/           数据访问
├─ schemas/                Pydantic 请求和响应模型
└─ services/
   ├─ conversations.py     会话编排与模式路由
   ├─ intent_classifier.py 意图分类与会话标题
   ├─ literature.py        检索计划、RRF 融合与推荐
   ├─ arxiv_search.py      arXiv 检索适配
   ├─ pdf_processing.py    PDF 文本与 OCR
   ├─ guided_reading.py    论文精读
   ├─ topic_guidance.py    选题指导
   ├─ framework_building.py 论文框架搭建
   ├─ paper_analysis.py    快速分析与论文对比
   └─ privacy.py           脱敏、TTL 与本地数据清理
```

## 前端结构

```text
frontend/src/
├─ api/                     API 与 SSE 客户端
├─ components/              通用组件
├─ layouts/AppShell.tsx     应用布局与项目选择
├─ pages/ChatPage.tsx       对话工作台
├─ pages/PaperReadingPage.tsx 论文精读
├─ pages/PapersPage.tsx     论文库
├─ pages/ArtifactsPage.tsx  成果列表
├─ store/                   Zustand 状态
└─ utils/                   会话合并、任务状态等工具
```

## 模型分工

- `QWEN_MODEL`：对话、选题、框架、精读、分析、对比和成果整理。
- `ROUTER_MODEL`：意图分类和首条会话标题。
- `ROUTER_DISABLE_THINKING=1`：关闭快速模型的思考模式。

`ROUTER_API_KEY` 为空时复用 `DASHSCOPE_API_KEY`。

## 数据模型

主要实体：

- Project
- Session / Message
- Paper / EvidenceChunk
- Artifact
- Task
- ModelCallLog

会话消息按 `sequence` 排序。后台任务使用 `pending` / `processing` / `completed` / `failed` / `cancelled` / `interrupted` 状态。

## 维护原则

- 新功能复用现有项目、会话、论文和成果模型。
- 前端状态以后端持久化数据为准，不建立平行数据源。
- 不向界面暴露模型推理、内部阶段事件或调试信息。
- 结构化模型输出必须通过 Pydantic 验证；不伪造检索或论文分析结果。
- 不提交 `.env`、数据库、上传论文、解析文本、日志和构建产物。
- 清理文件前先确认绝对路径和引用关系，不使用宽泛的 `git clean -fdX`。

## 验证

```powershell
python -m pytest backend\tests -q

cd frontend
npm test
npm run build
```
