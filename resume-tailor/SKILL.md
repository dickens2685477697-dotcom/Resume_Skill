---
name: resume-tailor
description: 根据个人简历、项目、工作经历和目标 JD 建立可追溯的经历库，完成证据匹配、岗位定向润色、简历生成及审计。适用于导入求职材料、补全经历、根据 JD 改写简历、筛选项目和分析岗位匹配；上传个人材料后调用时默认导入保存。不用于虚构经历或自动投递。
---

# 定向简历

把岗位要求映射到个人证据，再选择事实、组织岗位叙事并生成简历。

## 事实与存储边界

- 默认使用任务目录的 `workspace/`；用户指定路径时遵循该路径。Skill 目录只保存规则、模板和脚本。
- 保留原件、来源定位和变更记录；结构化数据用脚本幂等更新和原子替换，不用行级补丁修改已有 Workspace JSON。新 staging 文件可用补丁创建。
- 最终声明只使用 `verified`（材料明确记载）或 `user_confirmed`（用户明确确认）的事实。不能编造数字、工具、职责、资历或结果。
- 区分个人与团队、实际结果与目标/估算/计划；措辞强度不能超过证据。缺结果时用真实行动、交付或验证发现收束。
- 冲突和未确认推断不得进入最终简历。用户已确认没有的数据标为 `missing_confirmed`，停止重复提问。
- 岗位表达保存在 `jobs/` 和 `outputs/`，不反写通用经历；不自动投递或发送简历。

## 识别任务与加载规则

上传个人材料后调用且未指定阶段，执行 `ingest`；明确“只分析、不保存”时不写 Workspace。未提供材料时检查已有输入，不凭空创建经历。

只执行请求所需阶段。按下表读取参考，同一运行中已读且未变化的参考和数据直接复用。完整 schema 仅用于材料维护或紧凑契约无法解释的错误。

| 模式 | 所需参考与操作 |
|---|---|
| `initialize` | 运行 `scripts/init_workspace.py --root <workspace>`，随后 `scripts/validate_workspace.py --root <workspace>`；无需参考 |
| `ingest` / `validate` / `update` | [workflow.md](references/workflow.md) 与 [workspace-schema.md](references/workspace-schema.md)；只执行材料相关阶段 |
| `analyze-job` / `match` | [job-match-workflow.md](references/job-match-workflow.md) |
| `polish` | [jd-experience-polishing.md](references/jd-experience-polishing.md) 与 [generation-contract.md](references/generation-contract.md) |
| `generate` | [generation-contract.md](references/generation-contract.md)；仅在需要执行润色时再读 [jd-experience-polishing.md](references/jd-experience-polishing.md) |
| `audit` | [generation-contract.md](references/generation-contract.md)；审查现有简历，不强制创建润色结果 |
| `full-run` | 按阶段依次加载；复用已有且有效的上游结果 |

检查输入后，用脚本记录 `state/run-manifest.json` 的任务、模式、岗位、输入、计划阶段、已完成阶段、状态和限制。匹配使用 `apply_match_bundle.py start`；其他模式沿用 Workspace 更新流程，契约见 `assets/templates/run-manifest.json`。

## 上下文与执行预算

- 匹配先读取紧凑证据卡，默认每批最多 16,000 字符。读完卡片分页再筛选，初次展开 3–4 项候选；高优先级要求覆盖不足时增量补充。
- 省略标记表示未读取，不表示事实不存在。写入声明前必须核对其完整事实和来源。
- 连续执行匹配、润色、规划、生成和审计时共享已读上下文，无需每阶段重新盘点目录或复述规则。
- 由脚本负责确定性计分、校验和写入。成功 apply 已包含前后校验，默认无需另做 dry-run 或立即重复校验；排错或用户要求预览时使用 dry-run。

## 交付范围

- `polish`：保存岗位润色结果，交付所选段落、能力对应和必要限制。
- `generate` / `full-run`：保存简历正文、来源映射和必要的岗位中间数据，执行审计；最终回复简述结果与剩余风险。
- 独立审计报告、缺口报告和面试题只在用户要求相应产物或“完整报告”时生成。完整流程不等于全部报告。
- DOCX/PDF 按用户指定格式调用相应文档技能并渲染检查，同时保留 Markdown 内容源。默认一页，遵循用户语言、页数和模板要求。

缺少非关键信息时完成可支持版本。只集中询问会改变事实、项目选择或职责判断的具体问题；允许“没有/无法确认”。完成状态取决于所请求产物已完成、主要声明可追溯、审计通过且限制已明确。
