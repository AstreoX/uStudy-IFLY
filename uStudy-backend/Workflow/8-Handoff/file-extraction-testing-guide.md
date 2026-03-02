# 文件内容提取功能 - 测试指南

## 功能概述

现在 AI 可以理解和分析用户上传的文档内容（PDF、DOCX、TXT）。当用户上传文件并发送消息时，系统会：

1. 自动提取文件的文本内容
2. 将提取的文本格式化为 `[file_1: filename.pdf]\n<content>\n[end_file_1]`
3. 发送给 AI 进行分析

---

## 如何测试

### 前提条件

1. ✅ 数据库迁移已执行（`alembic upgrade head`）
2. ✅ 后端服务正在运行
3. ✅ 前端应用正常连接

### 测试场景 1：单个 PDF 文件

**步骤**：
1. 打开快速对话功能
2. 点击附件按钮，上传一个 PDF 文件（建议 5-10 页）
3. 在消息框输入："总结这个文档的主要内容"
4. 发送消息
5. 观察 AI 的响应

**预期结果**：
- ✅ AI 能准确总结 PDF 文档内容
- ✅ 后端日志显示文本提取成功
- ✅ 数据库中 `message_attachments` 表的 `extracted_text` 字段已填充

**验证命令**（查看数据库）：
```sql
SELECT
    original_filename,
    LENGTH(extracted_text) as text_length,
    extraction_metadata->>'token_count' as token_count,
    extraction_metadata->>'truncated' as truncated
FROM message_attachments
WHERE extracted_text IS NOT NULL
ORDER BY created_at DESC
LIMIT 5;
```

### 测试场景 2：多个文件（PDF + DOCX + 图片）

**步骤**：
1. 上传 3 个附件：
   - 1 个 PDF 文件
   - 1 个 DOCX 文件
   - 1 张图片
2. 输入消息："对比前两个文档的内容，并说明图片是否相关"
3. 发送消息

**预期结果**：
- ✅ AI 能分析两个文档的内容并进行对比
- ✅ AI 能识别图片内容（通过 Vision API）
- ✅ 消息格式正确：文件内容 → 用户文本 → 图片

### 测试场景 3：大文件截断

**步骤**：
1. 上传一个很大的 PDF 文件（50+ 页，预计 30000+ tokens）
2. 发送消息："总结这个文档"

**预期结果**：
- ✅ 提取成功，但内容被截断到 10,000 tokens
- ✅ 提取的文本末尾包含截断提示：`[Content truncated: showing first 10000 tokens of 30000]`
- ✅ 数据库中 `extraction_metadata->>'truncated'` = `true`

### 测试场景 4：提取失败（损坏文件）

**步骤**：
1. 创建一个假的 PDF 文件（文本文件改名为 .pdf）
2. 上传并发送消息

**预期结果**：
- ✅ 消息仍然发送成功（不阻塞）
- ✅ AI 收到的消息包含：`[file_1: fake.pdf - extraction failed]`
- ✅ 数据库中 `extraction_metadata->>'extraction_error'` 非空

### 测试场景 5：缓存验证

**步骤**：
1. 上传一个文件并发送第一条消息
2. 等待 AI 响应完成
3. 使用**相同的文件**（不重新上传）发送第二条消息
4. 观察后端日志

**预期结果**：
- ✅ 第一次：后端日志显示 "Extracting text from file: ..."
- ✅ 第二次：无提取日志（直接使用缓存）
- ✅ 第二次响应速度更快

---

## 后端日志关键信息

启动后端后，观察以下日志：

### 成功提取
```
INFO - Extracting text from file: uploads/attachments/files/document.pdf
INFO - Extracted 3245 tokens from document.pdf
```

### 截断警告
```
WARNING - Text truncated from 25000 to 10000 tokens
```

### 提取失败
```
WARNING - Text extraction timeout after 30s for file: large_document.pdf
ERROR - Extraction failed: [error details] for file: broken.pdf
```

---

## 数据库查询示例

### 查看最近提取的文件
```sql
SELECT
    original_filename,
    attachment_type,
    mime_type,
    LENGTH(extracted_text) as text_length,
    extraction_metadata
FROM message_attachments
ORDER BY created_at DESC
LIMIT 10;
```

### 查看提取失败的文件
```sql
SELECT
    original_filename,
    extraction_metadata->>'extraction_error' as error
FROM message_attachments
WHERE extraction_metadata->>'extraction_error' IS NOT NULL;
```

### 查看被截断的文件
```sql
SELECT
    original_filename,
    extraction_metadata->>'token_count' as token_count,
    extraction_metadata->>'truncated' as truncated
FROM message_attachments
WHERE (extraction_metadata->>'truncated')::boolean = true;
```

---

## 单元测试

运行自动化测试：

```bash
cd uStudy-backend
python -m pytest tests/chat/test_text_extractor.py -v
```

**预期输出**：
```
test_extract_text_from_attachment_image_type PASSED
test_extract_text_timeout PASSED
test_extract_text_unsupported_format PASSED
test_extract_text_file_not_found PASSED
test_truncate_by_tokens PASSED
test_truncate_by_tokens_no_truncation PASSED
test_extract_text_success_metadata PASSED
test_extract_text_integration SKIPPED
```

---

## 性能基准

### 预期提取时间
- **小文件**（1-5 页，< 2000 tokens）: < 1 秒
- **中等文件**（10-20 页，< 5000 tokens）: 1-3 秒
- **大文件**（50+ 页，> 10000 tokens）: 3-10 秒（会被截断）

### 超时限制
- **配置**: 30 秒（可在 `.env` 中修改 `ATTACHMENT_TEXT_TIMEOUT_SECONDS`）
- 超时后自动回退，不阻塞消息发送

---

## 支持的文件格式

| 格式 | MIME 类型 | 解析器 | 状态 |
|------|-----------|--------|------|
| PDF | `application/pdf` | PyMuPDF | ✅ 支持 |
| DOCX | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | python-docx | ✅ 支持 |
| DOC | `application/msword` | python-docx | ✅ 支持 |
| TXT | `text/plain` | chardet | ✅ 支持 |
| 图片 | `image/*` | Vision API | ✅ 支持（不提取文本） |

**不支持的格式**：
- Excel (`.xlsx`, `.xls`)
- PowerPoint (`.pptx`, `.ppt`)
- 其他格式会记录错误，但不阻塞消息发送

---

## 常见问题

### Q: AI 没有理解文档内容？
**A**: 检查：
1. 后端日志是否显示提取成功
2. 数据库中 `extracted_text` 是否为空
3. `extraction_metadata` 中是否有错误信息

### Q: 提取速度很慢？
**A**: 可能原因：
1. 文件过大（检查文件大小和页数）
2. 复杂的 PDF 排版
3. 服务器性能

**解决方案**：
- 调整 `ATTACHMENT_TEXT_MAX_TOKENS` 降低提取上限
- 启用上传时预提取（未实现，可选功能）

### Q: 扫描版 PDF 无法提取？
**A**: 当前不支持 OCR。扫描版 PDF 会提取失败，AI 只能看到文件名。

**未来优化方向**：集成 OCR 引擎（如 Tesseract）

### Q: 如何调整 token 限制？
**A**: 修改 `.env` 文件：
```env
ATTACHMENT_TEXT_MAX_TOKENS=15000  # 增加到 15000 tokens
```
重启后端服务生效。

---

## 环境变量配置

在 `.env` 文件中添加（可选，有默认值）：

```env
# 附件文本提取配置
ATTACHMENT_TEXT_MAX_TOKENS=10000        # 每个文件最大 token 数
ATTACHMENT_TEXT_TIMEOUT_SECONDS=30      # 提取超时（秒）
ATTACHMENT_CACHE_EXTRACTED_TEXT=true    # 是否缓存到数据库
```

---

## 监控建议

### 关键指标
1. **提取成功率**：监控 `extraction_metadata->>'extraction_error'` 非空的比例
2. **平均提取时间**：从日志中统计
3. **缓存命中率**：`extracted_text IS NOT NULL` 的比例
4. **截断频率**：`extraction_metadata->>'truncated' = true` 的比例

### 告警阈值
- 提取失败率 > 10% → 检查文件质量或服务器性能
- 平均提取时间 > 10 秒 → 考虑优化或降低 token 限制
- 截断频率 > 30% → 考虑增加 `ATTACHMENT_TEXT_MAX_TOKENS`

---

## 下一步优化（可选）

1. **上传时预提取**：在文件上传成功后立即提取，减少首次消息延迟
2. **并行提取**：使用 `asyncio.gather()` 并行处理多个文件
3. **OCR 支持**：集成 Tesseract 处理扫描版 PDF
4. **更多格式**：支持 Excel、PowerPoint、Markdown、HTML
5. **前端增强**：显示 token 数、截断警告、提取失败提示

---

**功能状态**: ✅ 核心功能已完成，可以开始测试
**文档版本**: 2026-02-13
**联系人**: 开发团队
