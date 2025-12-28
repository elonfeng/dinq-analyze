# Google Scholar 搜索指南

本指南解释了如何使用我们的系统搜索 Google Scholar 研究者信息，以及不同输入格式的处理方式。

## 输入格式

系统支持三种主要的输入格式：

1. **Google Scholar ID**（例如：`Y-ql3zMAAAAJ`）
   - 这是最准确的搜索方式
   - 直接从研究者的 Google Scholar 页面 URL 中提取

2. **Google Scholar URL**（例如：`https://scholar.google.com/citations?user=Y-ql3zMAAAAJ`）
   - 系统会自动提取 URL 中的 ID
   - 同样非常准确

3. **研究者姓名**（例如：`Daiheng Gao`）
   - 对于独特的名字，直接输入姓名通常足够
   - 对于常见名字，可能需要添加额外信息

## 最佳实践

根据我们的测试，以下是搜索研究者的最佳实践：

1. **优先使用 Scholar ID 或 URL**
   - 如果您知道研究者的 Google Scholar ID 或 URL，请直接使用它
   - 这是最准确的方法，可以避免同名问题

2. **使用准确的姓名**
   - 输入研究者的全名，确保拼写正确
   - 例如：`Daiheng Gao`、`Ian Goodfellow`

3. **添加机构信息（对于常见名字）**
   - 对于常见名字，可以尝试添加机构信息
   - 格式：`姓名,机构`（注意逗号后没有空格）
   - 例如：`Ian Goodfellow,DeepMind`

4. **避免使用不必要的修饰词**
   - 我们的测试表明，添加像 `,AI` 这样的领域标签可能会降低搜索准确性
   - 除非机构名称中确实包含这些词

## 特殊情况说明

在我们的测试中，我们发现一些有趣的情况：

1. **"Daiheng Gao" vs "Daiheng Gao,AI"**
   - 对于 Daiheng Gao 这个特定案例，直接使用姓名 `Daiheng Gao` 能成功找到正确的研究者
   - 而添加 `,AI` 后 (`Daiheng Gao,AI`) 反而无法找到匹配的作者
   - 这可能是因为 Google Scholar 将整个字符串作为一个整体进行搜索

2. **机构信息的格式**
   - 添加机构信息时，应使用 Google Scholar 上显示的准确机构名称
   - 例如：`Ian Goodfellow,DeepMind` 而不是 `Ian Goodfellow, Deep Mind`

## 故障排除

如果您无法找到特定研究者：

1. 尝试直接在 Google Scholar 上搜索该研究者
2. 从其 Google Scholar 页面复制 URL 或 ID
3. 使用该 ID 或 URL 进行搜索

## 示例

以下是一些有效的输入示例：

- `Y-ql3zMAAAAJ`（Daiheng Gao 的 Scholar ID）
- `https://scholar.google.com/citations?user=Y-ql3zMAAAAJ`
- `Daiheng Gao`
- `Ian Goodfellow,DeepMind`
