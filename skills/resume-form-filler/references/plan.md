# 计划与字段核对

从 start 创建的 plan.json 开始，保留 interface_id、url、target_id、profile_sha256、site_sha256。一个 plan 只处理一个模块；当前快照和控件才是选择器依据。

```json
{
  "interface_id": "local",
  "url": "https://career.example.com/resume/edit",
  "target_id": "从本次 start 复制",
  "profile_sha256": "从本次 start 复制",
  "site_sha256": null,
  "fields": [
    {"key": "basic.name", "selector": "#name", "label": "姓名", "kind": "text", "value_from": "profile:basic.name", "expected": ""}
  ],
  "pending": [],
  "reviewed_full_form": false
}
```

value_from 仅允许 `profile:<facts下的路径>` 或 `site:<overrides的完整key>`；不在计划硬编码 value。资料数组顺序与网页顺序分开，按学校/公司/项目名配对。pending 记录未知事实、必填、附件、隐藏分页和待确认映射，不能因为当前 fields 全通过就清空。只有看完所有折叠、分页、重复经历后才将 reviewed_full_form 设 true。

| kind | selector | 额外字段 |
|---|---|---|
| text | 唯一 input/textarea | 超 maxLength 停止，不静默截断 |
| date | 可输入日期 | 可选 month_start/month_end；仅用于网站需要日但原文只有月的格式适配，不改原始日期事实 |
| select | 原生 select | 按 option 可见文本精确匹配 |
| custom | 下拉打开控件 | option_selector、selected_selector 必填 |
| autocomplete | 搜索 input | option_selector、selected_selector 必填；必须核对选中显示 |
| checkbox/radio | 原生 checkbox/radio | 事实值须为 bool；已确认的“是/否”可 boolean_yes_no 转换 |

自动补全若只能用输入框作为 selected_selector，必须增加独立 `selection_evidence: {selector, value_from}`，例如选中条目后出现的标准编码，不能将搜索字串当选中成功。expected 是快照中的实际值（bool 或可见选中文本）。脚本先对所有字段预检，再逐项写入并读回；正确项跳过，可重入。

网页非空值不同会停止。只有真实确认覆盖后才能加 `overwrite_confirmed: true` 和 `confirmation_source: "实际用户授权依据"`。旧快照、其他网站或解析候选不能当覆盖授权。ui helper 只能补稳定映射之外的实际页面操作，操作后仍须 verify。

`draft_verified` 不代表网站保存；当前模块全通过也不代表整份表完成。保存后按原文/资料验收经历数量、成对日期、全文数字/单位与附件，并读回持久值。
