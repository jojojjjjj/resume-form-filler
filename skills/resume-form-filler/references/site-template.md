# 本站映射

仅在目标域名匹配时使用 `.resume-form-filler/sites/<hostname>.md`，唯一 JSON block：

```json
{
  "host": "career.example.com",
  "verified_at": "YYYY-MM-DD",
  "overrides": {},
  "pending": [],
  "state": "drafted"
}
```

overrides 使用语义 key，例如 `education.0.degree_choice`，值只能是当前使用者确认过的本站选项/文案。plan 使用 `site:<完整key>` 引用。近似专业分类、排名档位和日期格式只在本站生效；不能改写源事实。

非“保存/Save”文案的整份简历保存控件，只能在 `confirmed_mappings.completion` 记录并同时匹配 `button_text`、`data_test`、`route` 后放行；必须观察其确为保存简历操作。投递、申请按钮和申请路由仍拒绝。

正文记录依据、适用页面和未完成项，不记录身份证、口令、调试接口、坐标、transient node ID 或历史简历正文。网站文件可能包含私人选项，默认留在本地，不打包发布。
