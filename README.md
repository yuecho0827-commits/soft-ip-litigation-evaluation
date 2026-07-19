# Soft IP 主诉评估系统

商标侵权案件诉前评估 Demo。当前版本默认以真实 Demo 模式运行，Mock 仅作为开发调试兜底。

## 快速启动

### Windows

```powershell
cd soft-ip-litigation-evaluation
copy .env.example .env
./start.ps1
```

### macOS / Linux

```bash
cd soft-ip-litigation-evaluation
cp .env.example .env
bash start.sh
```

## 运行模式

### 真实 Demo 模式（默认）

```env
USE_MOCK=False
DEEPSEEK_API_KEY=your_real_api_key
QCC_API_TOKEN=your_qcc_token
PKULAW_API_TOKEN=your_pkulaw_token
```

特性：
- 评估页会明确区分“已完成”和“部分完成”。
- 结果页默认只展示缓存检索结果，不自动重复调用北大法宝/企查查。
- 缺少 DeepSeek 必要配置时会在页面和侧边栏直接提示，并阻断真实评估。
- 缺少企查查或北大法宝 Token 时，对应外部检索链路会自动跳过，并给出明确提示。

### Mock 模式（仅调试）

```env
USE_MOCK=True
```

特性：
- 不调用真实外部检索。
- 可完整跑通案件创建、评估、报告生成链路。
- 仅用于开发演示，不代表真实检索或真实结论。

## 本轮修复点

- 外部调用失败时改为失败态展示，不再静默落默认高分。
- 综合评分和建议受数据完整性约束，关键维度缺失时显示“评估未完成”。
- 北大法宝、企查查结果统一缓存，结果页默认读缓存，可手动“刷新外部检索”。
- PDF 导出补充 Windows 中文字体兜底，并关闭 Streamlit usage stats。
- 新增 `start.ps1`，适配 Windows 本地启动。

## 常见路径

默认会优先写入当前用户的数据目录，而不是程序安装目录：

- Windows：`%LOCALAPPDATA%\SoftIpLitigationEvaluation\`
- 数据库：`runtime\soft_ip.db`
- 评估缓存：`runtime\eval_results_<case_id>.json`
- 检索缓存：`runtime\pkulaw_results_<case_id>.json`
- 报告：`runtime\reports\`

如果默认用户目录不可写，系统会自动回退到安装目录下的 `.user_data\`，并在系统配置页与侧边栏提示当前实际生效目录。

## 免责声明

本系统为 AI 辅助评估工具，结果仅供内部决策参考，不构成正式法律意见。
