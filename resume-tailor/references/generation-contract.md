# 润色、生成与审计的紧凑契约

## 输入与有效性

使用 `jobs/<job-id>/jd-analysis.json`、`evidence-matrix.json` 和入选记录的完整事实/来源。生成前检查 `experience-tailoring.json` 的 `source_evidence_matrix_sha256` 是否等于当前证据矩阵文件的 SHA-256；缺失或不一致时执行润色。已知 JD 或事实变化时先更新匹配，不仅检查旧矩阵哈希。

润色规则见 `jd-experience-polishing.md`，结构读取 `assets/templates/experience-tailoring.json`，无需完整 Workspace schema。必填要点：

- 顶层：`job_id`、`source_evidence_matrix_sha256`、`role_narrative`、`records`、`cross_record_strategy`、`unresolved_questions`、`updated_at`。
- 每项记录：`record_type`（`project`/`experience`）、`record_id`、定位、能力信号、要求引用、事实选择、bullet 候选和排除事实。
- 可用 bullet：唯一 `bullet_id`、`draft`、`primary_signal`、`requirement_refs`、`field_paths`、`source_refs`、`evidence_status`、`ownership`、`selection_status`。选入状态为 `selected`；事实只能为 `verified` 或 `user_confirmed`。
- 来源引用保留 `source_id` 和定位；字段路径指向原记录，如 `actions[0]`。不同主体、时间或范围的事实不能拼成虚假因果。

## 规划与生成

按 `assets/templates/resume-plan.json` 在 `jobs/<job-id>/resume-plan.json` 保存语言、页数、入选经历/项目、bullet 计划、模块顺序、排除理由、覆盖和缺口。bullet 计划引用已选 `bullet_id`，不重复抄写整套证据。

优先覆盖硬条件和高价值能力，各经历互补。先删除弱相关内容和重复，再压缩句子；默认一页，不靠极小字号或拥挤边距容纳内容。已有有效润色可直接用于规划；最终措辞若改变事实组合，重新核对来源。

保存 `outputs/<job-id>/resume.md` 和 `resume-source-map.json`。来源映射格式：

```json
{"job_id":"sample-role","claims":[{"claim_id":"bullet-1","text":"最终声明","record_type":"project","record_id":"sample-project","field_paths":["actions[0]"],"source_refs":[{"source_id":"src-001","location":"p. 1"}],"evidence_status":"verified","transform_notes":""}]}
```

教育、技能等主要声明也要核对其 profile 字段和来源，不只检查经历 bullet。

## 审计与完成

审查正文和来源映射：事实可追溯；数字的数值、单位、时间、范围和实际/目标属性准确；个人职责及上线/影响强度有依据；优先要求已覆盖或明确缺口；能力和句子不过度重复；语言、页数与可读性符合要求。

自动修复顺序、重复、过长句和过强措辞；不能补事实。无法安全修复的声明排除并记录限制。独立 `audit` 直接核对现有正文与证据，缺映射时回查来源，不强制先润色。

默认审计结论写入最终回复和运行清单的 `limitations`；用户要求报告时输出 `resume-review.md`。`missing-information.md`、`interview-questions.md` 也按需生成；详细报告写作参考 `scoring-writing-audit.md`。

更新运行清单并运行 `scripts/validate_workspace.py --root <workspace>`。校验通过只证明结构和部分引用约束，仍需上述语义审计。所请求交付完成且主要声明可追溯时标记 `complete`，其余标记 `partial` 或 `needs_confirmation`。
