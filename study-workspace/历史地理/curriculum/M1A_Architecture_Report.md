# Milestone 1A｜课程架构交付与验收报告

> 状态：`DRAFT / WAITING_FOR_EXTERNAL_AUDIT`
>
> 本文件记录本轮课程工程化交付，不把架构草案冒充为已通过 Gate 的正式课程。

## 1. 控制边界

- 唯一考试范围裁决：`课程总纲.md` 与 `官方考查范围.md` 中登记的复旦 2024 版“历史地理基础”大纲。
- 当前选考分支：中国历史（120 分）；自然地理仍是 2024 大纲列示的另一选项，不被删除，但不进入当前中国史主线的时间优先级。
- 课程主体：历史地理学专业知识（180 分）+ 中国历史（120 分）。
- Universal ExamPrep：只负责后续编译，不负责决定 Course、Module、Lesson 或章节权重。
- 证据标签：`🟢 来自资料`、`🟡 AI补充，可能与你老师讲的不完全一致`、`⚠️ AI生成答案，非老师/教材提供`；本轮未把未核验内容放入标准答案。

## 2. 本轮交付物

| 交付物 | 路径 | 作用 | 当前状态 |
| --- | --- | --- | --- |
| Curriculum Master Map | `Curriculum_Master_Map.jsonl` | 30 个原子考点到课程、知识节点、证据和题型的唯一主映射 | 已建立；页码和逐题真题仍待补 |
| Course Taxonomy | `Course_Taxonomy_v1.md` | Course → Module → Lesson 结构及横贯能力标签 | 已建立；等待外部审计 |
| Knowledge Node Schema | `Knowledge_Node_Schema.json` | 知识节点、证据和教学状态的机器字段约束 | 已建立 |
| Knowledge Node Index | `Knowledge_Nodes_Index.jsonl` | 30 个考纲原子点的架构占位节点 | 已建立；不是正式讲义内容 |
| Evidence Coverage Matrix | `Evidence_Coverage_Matrix.jsonl` | 每个原子考点的教材、原典、地图、真题、复旦研究覆盖状态 | 已建立；整体仍为 `blocked_for_teaching` |
| Fudan Exam Style Profile | `Fudan_Exam_Style_Profile.md` | 区分官方事实、回忆真题观察和研究传统推断 | 已建立；逐题统计尚未完成 |
| Primary Source Corpus | `Primary_Source_Corpus.jsonl` | 原典目录级映射，不复制互联网古籍全文 | 已建立；底本/卷次页码待核 |
| 三节 Pilot Lesson | `pilots/` | 测试知识体系、原典、地图三种教学能力 | 已建立草案；不得进入标准答案或 Engram |

## 3. 覆盖计数（架构层，不等于证据通过）

| 指标 | 数量/状态 | 说明 |
| --- | ---: | --- |
| 官方原子考点 | 30 | 专业知识 21 + 中国历史 9；由官方大纲列出的组内条目拆分为可教学最小点 |
| Course | 2 | `COURSE-HG`、`COURSE-CN` |
| Module | 8 | 专业知识 4 个模块，中国历史 4 个模块 |
| Lesson 占位 | 53 | 35 个专业知识 Lesson + 18 个中国历史 Lesson |
| KnowledgeNode 占位 | 30 | 每个原子考点一个架构节点，可在后续拆成更细节点 |
| 2014—2025 真题逐题挂接 | 0% | 当前仍是回忆版 PDF/页级线索，未完成题目切分和不确定性标注 |
| 核心教材页码锚点 | 0%（M1A） | 书籍已拥有/可查，但扫描正文未进入活动材料集和 Universal 页级收据 |
| 原典目录挂接 | 30/30 有候选 | 当前多为 `edition_pending`，未因此生成标准答案 |
| 地图挂接 | 30/30 有需求判断或 `not_applicable` | 《中国历史地图集》图幅/册页索引尚未逐项建立 |
| 可授课 Lesson | 0 | 结构草案必须经独立审计及证据补齐后才可变为 `TEACHABLE` |

## 4. 阻断项

1. Universal 旧工作区通过 `validate_workspace.py` 的结果为 `blocked`：`workspace_not_registered`、`processing_mode_lightweight`；本轮不绕过该门禁重新摄取。
2. 六部核心书的扫描正文没有进入活动材料根目录 `materials/历史地理`，也没有产生正式页级 parser receipt；因此本轮不填写虚构教材页码。
3. 2014—2025 真题仍未逐题结构化；任何“频率”只保留为定性观察，不解释为命中概率。
4. 四份扫描题库仍是待结构化题源；OCR 输出虽已归档，但尚未完成题目切分、答案配对和来源复核。
5. 《（自编）名词解释》保持 `review_required`；不进入 Pilot 标准答案、正式讲义或 Engram。

## 5. 下一道 Gate

外部审计应先检查：

- 30 个原子考点是否完整覆盖 2024 大纲且没有扩大范围；
- Course/Module/Lesson 是否与《课程总纲》一致；
- B01—B06 的版本登记，尤其 B02 采用用户确认的 2001 年第一版；
- 任何 Pilot 的事实是否有证据、推断是否明确标记；
- 旧 Universal 是否被错误地当成新课程成品。

本轮到此停止批量生成；不恢复 Universal、不启动 Engram、不生成整套模拟题。
