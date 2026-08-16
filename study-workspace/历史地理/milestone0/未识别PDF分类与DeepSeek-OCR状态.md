# 未识别 PDF 分类与 DeepSeek OCR 状态

登记日期：2026-08-16

## 分类范围

本次只扫描**尚未出现在 Universal ExamPrep `.ingest/source_manifest.json` 的 PDF**：

- `tmp/universal-material-hold/专题补充资料/`：36 个补充资料 PDF；
- `C:\Users\30374\Desktop\历史地理` 中未登记的 4 个题库 PDF。

活动资料根目录中已经登记的 5 个 PDF 不重复计入本次“未识别”清单；Downloads 中的同名副本也不作为新的来源重复摄取。

## 二分类结果

| 类别 | 数量 | 处理状态 |
| --- | ---: | --- |
| 可直接读取正文文字 | 0 | 没有发现达到正文级提取标准的文件 |
| 无法提取正文文字 | 40 | 已写入 OCR 队列，等待 DeepSeek OCR 运行 |

判定规则：多页 PDF 至少有 2 页各含 20 个以上非空白字符，且总有效字符不少于 500；只有封面、页码或少量元数据的 PDF 仍归入“无法提取正文”。本次有少数文件只能提取到封面级字符，未被误判为可读正文。

## 未登记题库 PDF（4 个）

- `中国历史地理-名词解析简答.pdf`（12 页）
- `中国历史地理各种题.pdf`（59 页）
- `中国历史地理试题（简答题）.pdf`（11 页）
- `中国历史地理试题（选择题）.pdf`（4 页）

## DeepSeek Harness 状态

- 已安装技能：`deepseek-harness` v0.2.0；其内容是 DeepSeek V4 API 协议封装，不是 PDF/OCR 执行器。
- 已生成队列：`DeepSeek_Harness_OCR_队列.jsonl`，共 40 条，保留原文件路径、页数、SHA-256 和来源范围。
- 用户已在本轮明确授权将这些扫描页发送到 DeepSeek OCR；该授权只改变本轮 OCR 的对外处理范围，不代表 API 凭据已经存在。
- 当前环境没有 `DEEPSEEK_API_KEY`、`DEEPSEEK_OCR_API_KEY` 或 `MODELVERSE_API_KEY`，也没有已配置的 OCR endpoint。
- 尝试安装技能发现结果中的 `skills.volces.com@deepseek-ocr` 时，源地址不是可直接克隆的 Git 仓库，安装失败；不能把它当作已安装的 OCR 执行器。
- 因此本轮**没有向 DeepSeek 或其他外部服务上传 PDF/页面图像，也没有伪造 OCR 结果**；队列状态为 `queued_pending_deepseek_harness`。

## 机器可读产物

- `未识别PDF_文字提取分类.jsonl`：逐文件分类、页数、字符统计、SHA-256 和 OCR 标记；
- `DeepSeek_Harness_OCR_队列.jsonl`：40 个待 OCR 文件的最小队列。

取得可用的 DeepSeek-OCR 运行器、API endpoint 和 key 后，才能将队列逐页送识别；识别结果还必须经过页码、原图和出处复核后，才能重新摄取进 Universal 正式内容单元。
