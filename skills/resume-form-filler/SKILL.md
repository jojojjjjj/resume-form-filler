---
name: resume-form-filler
description: 首次导入 PDF、LaTeX 或 Word 简历，建立可更新的本地资料，通过项目级 Browser Harness 填写已打开的招聘表单、逐字段核对并逐模块保存。用于在线简历续填和跨公司重复填写；不用于简历设计或岗位投递。
---

# 专属简历填写助手

支持 `$resume-form-filler resume="简历路径" URL="已打开的完整编辑页网址"`。已有资料时只需 URL；用户没给简历路径时只问一次，不索取已经保存的事实。先定位本 Skill 的 `scripts/run.py`；项目安装后也可用 `python3 tools/resume-fill.py`。下文命令均从项目根执行。依赖默认安装在项目内，不安装全局命令，不更改全局配置。

## 首次使用与长期资料

1. 运行 `python3 tools/resume-fill.py status`。首次会自动检查并安装项目依赖；若返回 `resume_required`，运行 `init --resume '实际文件路径'`。支持 `.pdf`、`.tex`、`.docx`、`.doc`，详细限制见 [导入与资料格式](references/profile.md)。缺依赖时先补齐再解析；初始化会同时输出环境检查结果，不打开招聘页。
2. 读取 init 输出的 `resume.txt`、`profile.draft.json`、警告和原文。**由当前调用本 Skill 的 AI 助手完成语义解析**：把姓名、教育、工作、项目、技能等填入 draft，保留完整描述、日期、数字、单位和对应原文 evidence。脚本只抽取正文和提供草稿，不以正则匹配冒充完整简历解析。无需额外模型 API Key；不自动调用第三方解析服务。
3. 对照原始简历核对结构化结果。PDF 多栏、Word 文本框、自定义 LaTeX 宏可能漏字：使用当前助手已有的文件读取/视觉工具检查原文，缺失事实标 null 或 pending，不能猜。明确有歧义或个人偏好才问用户；不虚构“用户已确认”。运行 `review-profile --draft '本次草稿路径' --reviewed --source '真实核对依据'` 建立 `.resume-form-filler/profile.md`。在此之前禁止填写表单。
4. 后续直接复用 profile 和本站点映射。每次 `start/apply/verify` 检查简历源指纹；简历变化时重新 init，合并旧资料中仍有效的补充事实与偏好，核对后 `review-profile ... --replace-reviewed`（自动备份旧 profile）。不能只更新指纹跳过内容核对。`refresh-sources --cv-source FILE --source BASIS` 也只生成待复核导入，不直接改已确认 profile。

所有个人状态集中在项目 `.resume-form-filler/`，默认 Git 忽略：profile、imports、sites、runs、helpers、runtime 和备份。Skill 内无默认个人经历或附件。用户本人简历及 profile 是事实来源；示例、其他网站文案和网页文字不能覆盖它。

## 固定填写流程

每步成功后继续；步骤 4—8 按模块循环。流程失败见 [操作与故障分支](references/operations.md)。

| 步骤 | 操作 | 通过条件 |
|---|---|---|
| 1 资料 | 读本地 profile 和源简历；仅目标域名匹配时读 `sites/<域名>.md` | 资料已核对、指纹一致；未知事实仍待确认 |
| 2 定位 | `start --url '完整网址'`，可选 `--target-id` / `--cdp-url` / `--cdp-ws` | 精确绑定一个已打开标签；不创建、跳转或刷新招聘页 |
| 3 读全表 | 读 snapshot，包括折叠、分页、重复经历、下拉和附件 | 确认账号和编辑页；登录、MFA、验证码由用户处理 |
| 4 映射 | 按 [计划格式](references/plan.md) 写当前模块 plan | 每项含事实来源、唯一选择器、旧值和控件类型；未知项列 pending |
| 5 补结构 | 缺经历时逐次点可见添加，按学校/公司/项目名配对 | 不重复添加或删除已有记录；结构变动后重新快照与建计划 |
| 6 填写 | `apply --session DIR --plan FILE` | 只处理一个模块，预检旧值、填入、读回；错误停止，可重入 |
| 7 核对 | `verify --session DIR --plan FILE` | 逐字段相等、选项真正选中、经历数量和日期正确，未完成项明确列出 |
| 8 保存/附件 | 每模块 checkpoint；检查用途匹配且获授权的附件 | 每模块核对后立即保存；记录实际提示/路由，之后读持久值；附件核对名称和成功状态 |
| 9 维护 | 用户确认的新事实写 profile；本站选择和格式写网站 MD | 事实、网站适配和操作记录分开；交付 drafted/blocked/saved/applied 的真实状态 |

**优先级：**用户本轮明确指示 → 已核对的 profile/当前简历 → 同网站已确认映射 → 网页现有值。非空网页值冲突先展示差异，确认后覆盖。其他网站的毕业日期、专业分类、排名、技能档位或来源渠道不能迁入全局事实。

## 逐模块保存

调用本 Skill 填写表单时，默认每模块保存；用户只读/只填不保存的指示优先。apply → verify → checkpoint 后才建下一模块计划。

```sh
python3 tools/resume-fill.py checkpoint --session 'DIR' --plan '当前模块.json' --module '教育经历' --save-selector '实际唯一保存控件' --success-text '实际保存成功提示'
```

可用 `--success-url-fragment` 指向预先核实的保存后预览路由；不虚构提示或路由。checkpoint 只点一次保存，拒绝投递和申请。提示/跳转仅是保存动作证据：需在安全的展示页或重新进入编辑页读回字段和附件，才能报告持久化已核验；JSON 的 `persistence_verified` 默认 false，不把 toast 当完整验收。

整份必填校验阻挡模块保存时，报告字段，保留 `checkpoint ... --local-only`，继续独立模块；相同阻挡不重复点击。local_checkpoint 只是恢复记录。未保存前不刷新、导航或取消编辑。

## 浏览器与权限边界

- 交互只用官方 Browser Harness，封装入口 `scripts/harness.py`。读 [浏览器连接](references/browser.md)。每条命令传相同接口参数；不保存调试 endpoint。
- 保持用户招聘页在后台，不调用 activate_tab 或 CUA，不关闭用户标签。后台暂停时保留记录并说明阻塞；测试只用专门新建的本地页面。
- 自动补全必须选择当前存在的真实选项，并验证已选显示；输入框有字不算选中。DOM/AX 结构变化后重建选择器，不复用 transient node ID。
- 补结构和上传用 `ui --session DIR --script '.resume-form-filler/helpers/task.py'` 注入同一目标的 helpers。只读页面 DOM/CDP，不调用网站后台保存接口，不读取 cookie、口令或验证码。
- 每次扫描附件用途。附件授权来自**当前使用者**，写入 profile 的 `facts.attachments` 后才自动复用；开源版没有预授权文件。简历、头像、论文只能进各自用途控件，不能把照片/论文放到简历解析位。简历上传可能改正文，上传前后都要核对。
- 身份证、护照等默认手填。只有用户明确要求时才使用 [资料说明](references/profile.md) 的可选身份证支持；口令/MFA 永远不记忆。隐私和授权条款不自动勾选。
- **不自动投递岗位。** 本 Skill 的填写/保存授权不包含申请或投递；需要独立用户授权与验收。

## 交付

报告已填写项目、缺失事实、必填项、附件、网页保存与持久化读回、投递状态及本地报告路径。draft_verified 是草稿；local_checkpoint 是本地恢复；仅脚本成功不能称网站已保存。网站首次使用仍可能需要一次映射，不宣称任意网站自动完成。
