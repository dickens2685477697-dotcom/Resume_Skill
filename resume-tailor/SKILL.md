---
name: resume-tailor
description: 面向定向求职的简历证据管理与生成 Skill。读取用户提供的简历、项目经历、作品集、研究材料和目标岗位 JD，建立可追溯的个人经历库，检查 STAR 与业务证据缺口，完成 JD 分析、经历匹配、项目筛选、简历改写、事实审计和面试问题预测。用户上传个人材料后选择或调用 `$resume-tailor` 时，默认自动导入、拆解并保存材料；适用于“根据 JD 修改简历”“选择最相关项目”“补全项目经历”“生成一页简历”“分析岗位匹配度”“resume tailoring”“JD matching”等任务。不用于脱离用户真实材料的虚构简历、批量自动投递或仅提供泛化职业建议。
---

# 定向简历证据管理与生成

把目标岗位要求映射到可追溯的个人证据，再据此选择项目和生成简历。以真实性、职责边界和来源可核查性优先于关键词密度。

## 核心约束

1. 把当前任务目录下的 `workspace/` 作为个人资料和生成结果的唯一事实来源。用户指定其他目录时使用其指定路径。
2. 只把流程、规则、模板和脚本保存在 Skill 目录。绝不把用户经历、JD 或生成结果写入 Skill。
3. 只使用原始材料明确记载、用户直接陈述、用户明确确认，或已标为待确认推断的信息。最终简历不得包含未确认推断。
4. 不编造用户数量、增长、收入、效率、上线状态、团队规模、职责、工具、学校、奖项或技能。
5. 区分目标、建议、计划指标与已经发生的结果；区分个人贡献与团队成果。
6. 缺少数据时继续完成可支持的版本：降低措辞强度，改用过程、交付物、测试结果或定性反馈，并记录限制。
7. 不覆盖或删除用户原始文件。所有写入保持幂等；更新结构化记录时保留来源与变更痕迹。
8. 不自动投递职位或发送简历。

## 默认触发与运行模式

用户在本次任务中上传个人材料并选择或调用 `$resume-tailor` 时，除非用户明确要求“只分析、不保存”或指定其他阶段，否则自动执行 `ingest`：

1. 在任务目录初始化 `workspace/`（如尚未存在）。
2. 登记和解析本次上传的全部个人材料。
3. 拆解并保存个人资料、项目记录与工作/实习/研究经历。
4. 生成导入报告、完整性检查和少量高优先级待确认问题。

这是一项默认写入操作：保留原件、保持幂等、绝不覆盖或删除用户原始文件。未上传材料时不要凭空初始化或生成经历；询问用户所需材料或按其指定阶段运行。

根据用户请求只运行必要阶段，并检查上游输入：

- `initialize`：创建 Workspace。
- `ingest`：登记并解析个人材料。
- `validate`：检查项目、STAR 和证据完整性。
- `analyze-job`：登记并分析目标岗位。
- `match`：匹配岗位要求与个人证据。
- `generate`：规划并生成定向简历。
- `audit`：审查现有简历的事实、相关性、重复性、篇幅和风险。
- `update`：用用户补充、新材料或反馈更新经历库。
- `full-run`：从已有材料运行完整流程。

不要因用户只要求一个阶段而强制执行全流程。缺少非关键输入时先产出可用结果和缺口清单；只有不确认会造成事实错误、选错项目或严重误判职责时才提问。

## 每次运行

1. 检查 Workspace、现有资料、目标 JD 和历史状态。
2. 使用脚本创建或更新 `workspace/state/run-manifest.json`，记录任务、模式、目标岗位、已有输入、缺失输入、执行阶段与状态；不要用行级补丁修改已有结构化文件。
3. 按阶段只读取下列参考文件：
   - `initialize`：直接运行初始化和校验脚本，不读取参考文件。
   - `analyze-job`、`match`：读取 [job-match-workflow.md](references/job-match-workflow.md) 与 [scoring-writing-audit.md](references/scoring-writing-audit.md)。不要读取完整 Workspace schema，除非脚本报告本文件未解释的契约错误。
   - `ingest`、`validate`、`update`：读取 [workflow.md](references/workflow.md) 与 [workspace-schema.md](references/workspace-schema.md)。
   - `generate`、`audit`：读取 [workflow.md](references/workflow.md)、[workspace-schema.md](references/workspace-schema.md) 与 [scoring-writing-audit.md](references/scoring-writing-audit.md)。
   - `full-run`：按进入的阶段读取对应参考，不要在开始时一次性加载全部参考。
4. 只读取当前阶段需要的 Workspace 数据。岗位匹配先读取紧凑证据卡，再展开候选记录；不要打印全部 JSON、完整目录内容或已经读取过的记录。
5. 使用 staging bundle 和确定性脚本更新已有 JSON。不要把新文件创建、来源目录更新、运行清单更新和变更日志追加混在一个大补丁中。
6. 写入结果前执行证据与措辞检查；让脚本完成 schema 校验、总分计算、幂等 upsert 和原子替换。
7. 在最终回复中列出生成文件、关键匹配结论、未解决风险和需要用户确认的少量高优先级问题。

## 初始化 Workspace

优先运行：

```bash
python3 <skill-dir>/scripts/init_workspace.py --root <task-dir>/workspace
```

该脚本只创建缺失目录和空白文件，不覆盖已有内容。初始化后用以下命令做结构校验：

```bash
python3 <skill-dir>/scripts/validate_workspace.py --root <task-dir>/workspace
```

Workspace 固定包含：`inbox/`、`sources/`、`profile/`、`experiences/`、`projects/`、`jobs/`、`outputs/` 和 `state/`。`state/staging/` 只保存本次生成、尚未应用的中间 bundle；成功应用后可由脚本清理。把新上传、尚未处理的材料放入 `inbox/`；保留原件。

## 导入与规范化材料

1. 为每份来源创建稳定且唯一的 `source_id`，登记文件名、类型、原路径、解析状态、相关项目与必要的页码/段落定位。
2. 使用适合文件格式的读取工具提取文字；PDF、DOCX 或图片应保留页码或可回指的位置。无法读取时标记失败原因，不猜测内容。
3. 检查重复版本；不要因内容相似而删除来源。记录版本关系和冲突。
4. 把教育、技能、奖项和偏好分别写入 `profile/education.json`、`skills.json`、`awards.json` 和 `preferences.json`；把工作、实习、研究和项目分别写入 `experiences/` 或 `projects/`。
5. 将背景、目标、用户问题、任务、行动、决策、权衡、协作、交付物、结果和指标拆成独立字段。为重要字段记录 `field_evidence` 与 `source_refs`。
6. 对证据使用 `verified`、`user_confirmed`、`inferred`、`conflicting`、`missing` 或 `unsupported`。用户确认没有数据时使用 `missing_confirmed`，并停止重复询问。

## 分析岗位与匹配证据

严格按 [job-match-workflow.md](references/job-match-workflow.md) 执行：

1. 原样保存 JD 并拆分目标、职责、条件、能力、关键词、资历与硬约束。
2. 运行 `scripts/prepare_match_context.py` 读取紧凑证据卡，只展开可能匹配的候选记录。
3. 对高优先级要求匹配行动、产出、结果、责任范围和来源；关键词相同不能替代能力证据。
4. 在新 staging 目录一次性生成岗位与匹配 bundle；不要直接修改已有 Workspace JSON。
5. 运行 `scripts/apply_match_bundle.py` 做 dry-run、确定性计分、schema 校验和原子应用。
6. 输出项目与经历排名、未覆盖要求、重复记录、弱证据和面试追问风险。

## 规划与生成简历

1. 根据证据矩阵选择最相关经历，明确每段保留的 bullet 数、每条要证明的能力和排除理由。
2. 默认控制为一页，但遵循用户指定的语言、页数和模板。优先删除弱相关内容，不通过缩小字号或堆砌文字解决篇幅。
3. 灵活使用 STAR、CAR 或“行动—产出—影响”。优先采用“行动动词 + 对象/问题 + 方法/关键决策 + 交付物 + 真实结果/影响”。不要强制每条包含数字。
4. 为每条主要声明生成 `resume-source-map.json`，使用 `record_type` 与 `record_id` 区分项目和经历，并记录字段、来源和证据状态。
5. 用户要求 DOCX 或 PDF 时，使用相应文档技能生成并做渲染检查；Markdown 版本仍保留为可审计的内容源。

## 审计与交付

依次检查：

- 事实：每个声明和数字是否有来源，是否夸大职责、结果或上线状态。
- 相关性：是否优先覆盖高价值岗位能力，是否只有关键词没有证据。
- 重复性：项目、能力、动词和结果是否重复。
- 篇幅：是否符合页数，bullet 是否过长或过度压缩。
- 风险：冲突、弱证据、待确认推断和容易被追问的责任边界。

先在不改变事实的前提下自动修订，再输出审计报告。完整运行至少生成：

- `workspace/outputs/<job-id>/resume.md`
- `workspace/outputs/<job-id>/resume-source-map.json`
- `workspace/outputs/<job-id>/resume-review.md`
- `workspace/jobs/<job-id>/evidence-matrix.json`
- `workspace/outputs/<job-id>/missing-information.md`
- `workspace/outputs/<job-id>/interview-questions.md`
- `workspace/state/run-manifest.json`

只有主要简历声明均可追溯、目标与实际结果已区分、个人与团队贡献未混淆、审计已完成且限制已明确时，才把完整运行标记为完成。

## 提问规则

集中提出少量、具体且影响最大的事实问题，并说明影响哪段简历。例如询问实际用户/被试数、个人或团队决策、前后变化、指标是目标还是结果。允许用户回答“没有”“不记得”或“无法确认”。不要问“请补充更多信息”这类泛化问题，也不要重复已经回答的问题。
