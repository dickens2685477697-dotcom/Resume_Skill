# Resume Tailor 可编辑工作流程图

本目录根据以下实际实现文件整理：

- `SKILL.md`
- `references/workflow.md`
- `references/workspace-schema.md`
- `references/scoring-writing-audit.md`
- `scripts/init_workspace.py`
- `scripts/validate_workspace.py`

## 图表清单

1. [`01-full-workflow.mmd`](01-full-workflow.mmd)：Skill 的完整端到端工作流。
2. [`02-resume-input-flow.mmd`](02-resume-input-flow.mmd)：用户输入简历或其他个人材料后的默认运行流程。
3. [`03-jd-input-flow.mmd`](03-jd-input-flow.mmd)：用户输入 JD 后，分析、匹配和生成的条件分支。

## 16:9 SVG 版本

- [`svg/resume-tailor-full-workflow.svg`](svg/resume-tailor-full-workflow.svg)：完整项目流程。
- [`svg/resume-input-workflow.svg`](svg/resume-input-workflow.svg)：输入简历或个人材料后的流程。
- [`svg/jd-input-workflow.svg`](svg/jd-input-workflow.svg)：输入 JD 后的流程。

SVG 使用分组图形、可编辑文字和矢量连线，可在 Figma、Adobe Illustrator、Affinity Designer、Inkscape 或支持 SVG 的演示文稿软件中继续编辑。颜色、描边和文字样式均使用元素级属性，避免 Figma 导入时忽略 CSS 样式。重新生成时运行 `node export_flowchart_svgs.mjs <visualization.html> svg`。

三个 `.mmd` 文件都是 Mermaid 源文件，可以直接用文本编辑器修改，也可以粘贴到 Mermaid Live Editor、支持 Mermaid 的 Markdown 编辑器或 diagrams.net 的 Mermaid 导入功能中继续编辑。

最简单的编辑方法：打开任一 `.mmd` 文件，修改方括号、花括号或圆括号中的中文节点文字；用 `A --> B` 增加连线，用 `A -- 条件 --> B` 增加带条件的分支。节点 ID（例如 `START`、`MATCH`）应保持唯一。

## 流程图符号

| 符号 | Mermaid 写法 | 含义 |
|---|---|---|
| 圆角终止符 | `([开始/结束])` | 流程开始或结束 |
| 平行四边形 | `[/输入或输出/]` | 用户输入、文件输入或结果输出 |
| 矩形 | `[处理步骤]` | 系统处理、分析或写入动作 |
| 菱形 | `{判断条件?}` | 条件判断与分支 |
| 圆柱体 | `[(数据存储)]` | Workspace、结构化记录或输出目录 |
| 双边框矩形 | `[[子流程]]` | 已定义的阶段或可复用子流程 |

## 关键运行语义

- 个人材料的默认触发模式是 `ingest`，默认执行阶段 1–4；除非用户同时要求匹配或生成，否则不会自动进入定向简历生成。
- JD 输入先登记和分析。只有用户要求继续匹配或生成，并且已有可用的个人证据库，才进入阶段 7 之后的流程。
- 用户明确要求“只分析、不保存”时，不初始化或更新 Workspace。
- `inferred`、`conflicting` 和 `unsupported` 证据不得直接写入最终简历；可以向用户确认、降级措辞或排除。
- 硬性条件单独判断，不能被综合匹配分数抵消。
- 完整运行只有在主要声明可追溯、目标与结果区分、个人与团队边界清楚且审计完成后，才标记为 `complete`。
- Skill 不会自动投递职位或发送简历。

## 预览

下面的代码块引用与 `.mmd` 文件相同的 Mermaid 语法。部分 Markdown 编辑器不会自动加载外部 Mermaid 文件，因此建议直接打开各 `.mmd` 文件编辑和预览。
