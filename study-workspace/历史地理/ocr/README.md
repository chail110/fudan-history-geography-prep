# OCR 文本归档

本目录是 `D:\workspace\历史地理\ocr` 的完整归档，供私密 GitHub 仓库中的审计 AI 直接读取。

## 内容

- `archive/`：按 D 盘原始目录结构完整复制，包含 DSH 输出、逐页 TXT、JSON/JSONL、DOCX、脚本、日志、交叉校验和复扫结果。
- `sources/`：与 DSH OCR 队列及交叉校验对应的 41 份原始 PDF，按 SHA-256 前 16 位分目录保存，并由 Git LFS 管理；`sources/manifest.jsonl` 保留原文件名、来源路径、页数、大小和校验值。

本次归档共 24,337 个文件，约 124.19 MB。来源文件的 SHA-256、原始文件名、页码和复扫状态保留在相应 JSON/JSONL 中。

## 归档边界

这里归档的是 D 盘 OCR 工作区及其对应的原始 PDF。只纳入 DSH 主队列和交叉校验实际使用的 41 份文件；Downloads 中与本次 OCR 队列无关的其他 PDF 不纳入仓库。

## 使用边界

这些 OCR 结果尚未经过 Universal ExamPrep 的正式摄取、逐条事实核验或课程编译。空文本页按用户确认视为空白内容，不再重复扫描；任何讲义、标准答案或 Engram 卡片都必须在资料层核验后生成。

原始 DSH 输出仍保留在本机：

`D:\workspace\历史地理\ocr\deepseek-harness`
