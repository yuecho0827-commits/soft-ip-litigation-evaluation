# Soft IP 主诉评估系统

MVP 版本 - 商标侵权案件诉前评估工具

## 快速启动

### 1. 安装依赖

```bash
cd soft-ip-evaluation
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env`：

```bash
cp .env.example .env
```

**Mock 模式（推荐先使用）**：
```
USE_MOCK=True
```
→ 使用模拟数据，无需 API key

**生产模式（接入 DeepSeek API）**：
```
USE_MOCK=False
DEEPSEEK_API_KEY=your_real_api_key
```

### 3. 启动应用

```bash
streamlit run app.py
```

应用会自动在浏览器打开：`http://localhost:8501`

## 使用流程

1. **新建案件** (`📝 新建案件`)
   - 填写案件名称、业务目标
   - 描述案情（越详细越好）
   - 点击"创建案件并开始评估"

2. **评估分析** (`🔍 评估分析`)
   - 系统自动进行：
     - ✅ 案情事实提取
     - ✅ 红线风险检查（6 条规则）
     - ✅ 法律要件分析
     - ✅ 三维评分计算
     - ✅ 评估报告生成

3. **查看报告** (`📄 评估报告`)
   - 查看完整评估报告
   - 下载 Markdown 或 PDF 版本

## 项目结构

```
soft-ip-evaluation/
├── app.py                 # Streamlit 主程序
├── config.py              # 配置文件
├── database.py           # 数据库模型
├── mock_llm.py          # Mock LLM 模块
├── legal_rules.py        # 规则引擎
├── scoring.py            # 评分逻辑
├── report_generator.py   # 报告生成
├── data/                 # 数据目录
│   ├── soft_ip.db      # SQLite 数据库
│   └── reports/         # 生成的报告
├── requirements.txt       # Python 依赖
├── .env.example         # 环境变量模板
└── README.md           # 本文件
```

## 技术栈

- **前端**: Streamlit
- **后端**: Python
- **数据库**: SQLite + SQLAlchemy
- **LLM**: DeepSeek API（可切换）
- **报告**: Markdown + ReportLab (PDF)

## MVP 功能范围

### ✅ 已实现

- [x] 商标侵权案件评估
- [x] 案情事实提取（Mock）
- [x] 红线风险检查（6 条规则）
- [x] 法律要件分析
- [x] 三维评分（法律 × 业务 × 证据）
- [x] 评估报告生成（Markdown + PDF）
- [x] 案件管理（创建、列表）

### 🚧 后续规划

- [ ] 接入真实 DeepSeek API
- [ ] 证据文件上传与解析
- [ ] 法律数据库对接（法规、案例）
- [ ] 模拟法庭（多 Agent）
- [ ] 著作权、不正当竞争案由扩展
- [ ] 用户权限管理

## 常见问题

### Q: 运行报错 `ModuleNotFoundError`

**A**: 请确保已安装依赖：

```bash
pip install -r requirements.txt
```

### Q: 如何切换到真实 LLM API？

**A**: 修改 `.env` 文件：

```
USE_MOCK=False
DEEPSEEK_API_KEY=your_api_key
```

### Q: 数据库文件在哪里？

**A**: `data/soft_ip.db`（SQLite 文件）

### Q: 如何查看评估报告？

**A**: 评估完成后，前往「📄 评估报告」页面查看和下载

## 联系方式

- 产品: [你的名字]
- 技术: [研发者名字]

---

**免责声明**: 本系统为 AI 辅助工具，评估结果仅供内部决策参考，不构成正式法律意见。
