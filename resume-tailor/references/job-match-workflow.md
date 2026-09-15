# 岗位分析与证据匹配

仅在 `analyze-job`、`match` 或 `full-run` 的岗位匹配阶段读取本文件。不要同时读取完整 `workspace-schema.md`；只有脚本报告契约错误且本文件无法解释时才读取它。

## 目标

保留完整匹配范围，同时限制模型上下文和写入失败：

1. 用紧凑证据卡筛选候选记录。
2. 只展开候选记录的详细证据。
3. 在新的 staging 目录生成一次 bundle。
4. 由脚本校验、计算分数并更新已有 Workspace 文件。

不要用行级 `apply_patch` 修改已有的 Workspace JSON，不要在一个补丁中混合新增岗位文件与修改 `source-catalog.json`、`run-manifest.json` 或 `change-log.jsonl`。

## 1. 初始化并开始运行

仅在 Workspace 尚未初始化或目录缺失时运行 init；已有完整 Workspace 直接 start。脚本保持幂等，不覆盖已有文件：

```bash
python3 <skill-dir>/scripts/init_workspace.py --root <workspace>
python3 <skill-dir>/scripts/apply_match_bundle.py start \
  --root <workspace> \
  --job-id <job-id> \
  --mode match \
  --task "<本次任务>"
```

第二个命令返回唯一 `bundle_dir`，同时以原子写入把 `run-manifest.json` 标为 `in_progress`。后续只在该目录创建 bundle 文件。

## 2. 解析并登记 JD

保留用户提供的 JD 原文。只有用户提供链接、要求核验或当前官方信息会影响判断时才访问官方来源。截图和文件需保留原始路径、来源 ID 与可回指位置。

分析：

- 岗位核心目标和成功定义；
- 主要职责和工作产出；
- 硬性条件、加分项和硬约束；
- 产品、研究、交互、技术协作、数据业务、跨团队和行业能力；
- ATS 关键词、责任级别和资历；
- 有依据且单独标注的隐含要求。

## 3. 用证据卡筛选

不要打印完整项目目录或完整 JSON。运行：

```bash
python3 <skill-dir>/scripts/prepare_match_context.py --root <workspace>
```

输出包含去除联系方式、重复来源位置和大段 `field_evidence` 的候选人资料与证据卡。证据卡中的 `*_omitted_count` 表示该字段仍有未展开内容，不能据此判断内容不存在。

先根据岗位要求筛选候选记录，再只展开可能进入匹配矩阵的记录：

```bash
python3 <skill-dir>/scripts/prepare_match_context.py \
  --root <workspace> \
  --record experience:<experience-id> \
  --record project:<project-id>
```

详细模式默认只返回证据卡中省略的 `*_continuation`、完整 `field_evidence`、来源与 STAR 状态，避免重复已在上下文中的内容。只有没有先读取证据卡的独立调试才使用 `--full-details`。

默认每页预算 16,000 字符。`next_offset` 非空时，用相同参数加 `--offset <next_offset>` 续读；卡片全部读完后再筛选，不能把未读记录视为不相关。详情分页也须续读。`omitted_record_count` 表示剩余记录。

通常先展开 3–4 项候选；高优先级要求覆盖不足时再补充。详情保留完整来源和事实，单条超预算会报所需大小，按提示提高该次 `--max-output-chars`。卡片文本含省略号时，最终使用前用 `--full-details` 核对原文。续读期间数据变化应重新读取卡片。

## 4. 完成匹配判断

对每项高优先级要求：

1. 找到行动、决策、交付物和结果。
2. 核对本人责任范围、证据状态与来源。
3. 记录一个或多个 `{record_type, record_id}`。
4. 输出六项原始分数；不要自行计算或反复微调总分。
5. 标记 `include`、`supporting`、`exclude` 或 `confirm`。
6. 写出风险与具体面试追问。

证据状态只能使用：

- `verified`
- `user_confirmed`
- `inferred`
- `conflicting`
- `missing`
- `missing_confirmed`
- `unsupported`

`inferred`、`conflicting` 或 `unsupported` 的关键声明不能因总分高而直接进入最终简历。

`score_breakdown` 必须包含 0–100 的六项原始分数：

```json
{
  "jd_relevance": 0,
  "evidence_strength": 0,
  "candidate_ownership": 0,
  "result_impact": 0,
  "differentiation": 0,
  "keyword_coverage": 0
}
```

上述六项分别评估职责/成功目标对应程度、来源与事实可靠性、本人责任边界、真实结果或交付影响、相对其他经历的独特能力、自然且有证据的岗位词汇。应用脚本按 35%、25%、15%、10%、10%、5% 计算并覆盖 `match_score`，使用四舍五入到整数。不要在模型侧修正一分误差。硬条件单独标明满足、不满足或未知，不用总分抵消。

## 5. 创建 staging bundle

仅在 `start` 命令返回的空目录中新增以下文件：

```text
<bundle-dir>/
├── manifest.json
├── jd-original.md
├── job-metadata.json
├── jd-analysis.json
├── jd-analysis-summary.md
└── evidence-matrix.json
```

这些都是新文件，可以在一个 `apply_patch` 中创建；不要在同一补丁中修改 Workspace 目标文件。

`manifest.json`：

```json
{
  "schema_version": "match-bundle-1.0",
  "job_id": "sample-role",
  "mode": "match",
  "source_catalog_upserts": [
    {
      "source_id": "src-001",
      "source_type": "job_description",
      "file_name": "job.png",
      "path": "workspace/inbox/job.png",
      "parse_status": "complete",
      "related_projects": [],
      "version_of": null,
      "notes": ""
    }
  ],
  "run_manifest_patch": {
    "available_inputs": [],
    "missing_inputs": [],
    "planned_stages": ["analyze-job", "match"],
    "completed_stages": ["analyze-job", "match"],
    "status": "complete",
    "limitations": []
  },
  "change_log_entries": [
    {
      "timestamp": "ISO-8601",
      "operation": "analyze-job-and-match",
      "job_id": "sample-role"
    }
  ]
}
```

仅执行 `analyze-job` 时，把 `start` 和 `manifest.json` 的 mode 改为 `analyze-job`，省略 `evidence-matrix.json`，并把计划与完成阶段设为 `["analyze-job"]`。

`evidence-matrix.json` 的每项 requirement 必须包含：

```json
{
  "requirement": "",
  "priority": 5,
  "matched_records": [],
  "evidence": [],
  "source_refs": [],
  "evidence_status": "verified",
  "score_breakdown": {},
  "match_score": 0,
  "resume_recommendation": "include",
  "risk": "",
  "interview_follow_up": []
}
```

`match_score` 可先写 `0`；应用脚本会确定性计算。`job-metadata.json`、`jd-analysis.json` 和 `evidence-matrix.json` 中的 `job_id` 必须与 bundle 一致。

## 6. 校验并应用

默认直接应用，脚本包含前后校验及失败恢复。仅排错或用户要求预览时先做只读校验：

```bash
python3 <skill-dir>/scripts/apply_match_bundle.py apply \
  --root <workspace> \
  --bundle-dir <bundle-dir> \
  --dry-run
```

校验通过后应用并清理生成的 staging 文件：

```bash
python3 <skill-dir>/scripts/apply_match_bundle.py apply \
  --root <workspace> \
  --bundle-dir <bundle-dir> \
  --consume
```

脚本会：

- 在写入前检查所有 bundle 文件；
- 校验证据状态、recommendation、记录引用和分项分数；
- 自动计算 `match_score`；
- 按 `source_id` 幂等 upsert 来源；
- 合并运行清单并去重完全相同的变更日志；
- 所有内容验证通过后才原子替换目标文件；
- 最终 Workspace 校验失败时恢复原文件。

若校验失败，只修改错误指向的 staging 文件。成功 apply 后无需立即再运行全量校验。不要重新生成整个 bundle，也不要回退到直接补丁修改已有 Workspace JSON。

## 7. 交付

输出岗位目标、最高价值证据、硬约束、未覆盖要求、弱证据与少量高优先级待确认问题。列出 `jd-analysis-summary.md`、`evidence-matrix.json`、JD 原文和运行记录。
