# Workspace 文件契约

## 目录

- [目录结构](#目录结构)
- [标识与来源](#标识与来源)
- [证据状态](#证据状态)
- [核心文件](#核心文件)
- [项目与经历记录](#项目与经历记录)
- [岗位记录](#岗位记录)
- [输出记录](#输出记录)
- [更新规则](#更新规则)

## 目录结构

```text
workspace/
├── inbox/                  # 未处理原始材料
├── sources/
│   ├── extracted/          # 保留定位信息的提取文本
│   ├── source-catalog.json
│   └── ingestion-report.md
├── profile/
│   ├── candidate-profile.json
│   ├── education.json
│   ├── skills.json
│   ├── awards.json
│   ├── preferences.json
│   ├── completeness-report.md
│   └── pending-questions.json
├── experiences/            # 工作、实习、研究经历；一项一个 JSON
├── projects/               # 项目；一个项目一个 JSON
├── jobs/<job-id>/
│   ├── jd-original.md
│   ├── job-metadata.json
│   ├── company-research.md
│   ├── jd-analysis.json
│   ├── jd-analysis-summary.md
│   ├── evidence-matrix.json
│   └── resume-plan.json
├── outputs/<job-id>/
│   ├── resume.md
│   ├── resume-source-map.json
│   ├── resume-review.md
│   ├── missing-information.md
│   └── interview-questions.md
└── state/
    ├── workspace-manifest.json
    ├── run-manifest.json
    ├── change-log.jsonl
    └── templates/
```

## 标识与来源

- 使用小写 ASCII、数字和连字符生成稳定的 `project_id`、`experience_id` 与 `job_id`。标识创建后不要因展示名称变化而修改。
- 使用 `src-001` 形式生成 `source_id`；从现有最大编号递增，不复用已删除或失败来源的编号。
- `source_refs` 应尽量包含 `source_id`、页码/段落/章节、原文定位和必要的短摘录。短摘录只用于核验，不替代原始材料。
- 保留原始文件路径。复制到 `inbox/` 时也记录最初提供的文件名和路径。
- 来源冲突时同时保留两条证据，并把相关字段标为 `conflicting`。

推荐来源目录结构：

```json
{
  "sources": [
    {
      "source_id": "src-001",
      "source_type": "portfolio_pdf",
      "file_name": "portfolio.pdf",
      "path": "workspace/inbox/portfolio.pdf",
      "parse_status": "complete",
      "related_projects": ["sample-project"],
      "version_of": null,
      "notes": ""
    }
  ]
}
```

## 证据状态

对会进入简历的重要字段使用以下状态：

- `verified`：原始材料明确出现。
- `user_confirmed`：用户明确确认。
- `inferred`：从材料合理推断但尚未确认；不得当作事实写入最终简历。
- `conflicting`：不同来源冲突；确认前不得使用有争议表述。
- `missing`：缺少信息，可提出一次具体问题。
- `missing_confirmed`：用户确认没有、不记得或无法确认；停止重复询问。
- `unsupported`：没有证据或证据否定该表述；不得使用。

`field_evidence` 的每个键对应一个字段或字段项：

```json
{
  "results[0]": {
    "status": "verified",
    "source_refs": [
      {"source_id": "src-001", "location": "p. 8"}
    ],
    "notes": ""
  }
}
```

## 核心文件

`workspace-manifest.json` 至少记录：

```json
{
  "schema_version": "1.1",
  "created_at": "ISO-8601",
  "workspace_root": "absolute-or-user-selected-path",
  "status": "initialized"
}
```

`run-manifest.json` 每次运行都更新：

```json
{
  "task": "",
  "mode": "initialize|ingest|validate|analyze-job|match|generate|audit|update|full-run",
  "target_job_id": null,
  "available_inputs": [],
  "missing_inputs": [],
  "planned_stages": [],
  "completed_stages": [],
  "status": "in_progress|needs_confirmation|complete|partial",
  "limitations": [],
  "updated_at": "ISO-8601"
}
```

候选人文件分别保存基础信息、教育、技能、奖项与偏好。奖项统一写入 `awards.json`。不要把针对某个岗位的关键词反写为通用技能。技能和奖项只有在来源支持时才进入对应文件。

## 项目与经历记录

项目与工作经历复用事实字段，但使用不同的身份字段：项目使用 `project_id`、`project_name`，工作/实习/研究经历使用 `experience_id`、`experience_name`。不要在 `experiences/` 中使用项目标识。

项目记录：

```json
{
  "project_id": "sample-project",
  "project_name": "Sample Project",
  "experience_type": "internship|employment|research|course|personal|volunteer",
  "organization": "",
  "role": "",
  "time_range": "",
  "background": [],
  "business_goal": [],
  "user_problem": [],
  "task": [],
  "actions": [],
  "deliverables": [],
  "results": [],
  "metrics": [],
  "decisions": [],
  "tradeoffs": [],
  "collaboration": [],
  "skills": [],
  "tools": [],
  "source_refs": [],
  "field_evidence": {},
  "star_completeness": {
    "situation": "missing",
    "task": "missing",
    "action": "missing",
    "result": "missing"
  },
  "status": "draft|complete|usable_with_gaps|insufficient",
  "updated_at": ""
}
```

经历记录结构与上例相同，但开头替换为：

```json
{
  "experience_id": "sample-experience",
  "experience_name": "Sample Experience",
  "experience_type": "internship|employment|research|course|personal|volunteer"
}
```

文件名必须与对应 ID 相同，例如 `projects/sample-project.json` 和 `experiences/sample-experience.json`。需要跨类型引用时使用 `{ "record_type": "project|experience", "record_id": "..." }`，避免用 `project_id` 指代工作经历。

把指标表示为结构化对象，避免把目标和实际值混在一句文本中：

```json
{
  "name": "task completion rate",
  "value": "",
  "unit": "%",
  "measurement_type": "actual|target|baseline|estimate",
  "timeframe": "",
  "scope": "",
  "evidence_status": "missing",
  "source_refs": []
}
```

## 岗位记录

`job-metadata.json` 记录 `job_id`、公司、岗位、地点、来源 URL、是否为用户版本、是否经网络核验、访问日期、语言和页数要求。`jd-original.md` 保持原文，不做润色。可从 `assets/templates/job-metadata.json` 复制初始结构。

`jd-analysis.json`：

```json
{
  "role_objective": [],
  "responsibilities": [],
  "must_have": [],
  "nice_to_have": [],
  "competencies": [],
  "keywords": [],
  "hard_constraints": [],
  "inferred_requirements": [],
  "priority_weights": []
}
```

每项隐含要求包含 `type: "inferred_requirement"`、推断依据和置信度，不与 JD 明文要求混合。

`evidence-matrix.json` 使用数组容器，每个要求可匹配多个证据：

```json
{
  "job_id": "sample-role",
  "requirements": [
    {
      "requirement": "产品需求分析",
      "priority": 5,
      "matched_records": [
        {"record_type": "project", "record_id": "sample-project"}
      ],
      "evidence": [],
      "source_refs": [],
      "evidence_status": "verified",
      "score_breakdown": {},
      "match_score": 0,
      "resume_recommendation": "include|supporting|exclude|confirm",
      "risk": "",
      "interview_follow_up": []
    }
  ],
  "record_ranking": [],
  "uncovered_requirements": [],
  "weak_evidence": []
}
```

`resume-plan.json`：

```json
{
  "target_language": "zh-CN",
  "page_limit": 1,
  "selected_experiences": [],
  "selected_projects": [],
  "bullet_plan": [],
  "section_order": [],
  "excluded_items": [],
  "coverage_summary": {},
  "known_gaps": []
}
```

## 输出记录

`resume-source-map.json` 必须按简历声明映射，并用 `record_type` 区分项目与经历：

```json
{
  "job_id": "sample-role",
  "claims": [
    {
      "claim_id": "experience-1-bullet-1",
      "text": "",
      "record_type": "project",
      "record_id": "sample-project",
      "field_paths": ["actions[0]", "deliverables[0]"],
      "source_refs": [],
      "evidence_status": "verified",
      "transform_notes": ""
    }
  ]
}
```

`missing-information.md` 分为“申请前必须确认”“建议补充”“没有数据也可以继续”和“未来项目建议追踪的指标”。最后一类绝不能写成现有成果。

## 更新规则

1. 判断新信息属于候选人通用资料、项目事实还是单岗位表达，再写入对应层级。
2. 新证据覆盖旧推断时，更新证据状态并向 `state/change-log.jsonl` 追加变更；不要无痕覆盖。
3. 针对一个 JD 的措辞只保存在 `jobs/` 或 `outputs/`，不改变项目原始事实。
4. 材料冲突时标记字段与来源，等待用户确认。
5. 只重新运行受影响的完整性、匹配、规划、生成和审计阶段。
