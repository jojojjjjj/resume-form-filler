# Resume Form Filler · 专属简历填写助手

导入自己的简历，建立本地资料，通过 AI 编程助手填写已经打开的招聘简历表单。保留「读全表 → 映射 → 补经历结构 → 逐模块填写 → 逐字段核对 → 每模块保存 → 读回验收 → 更新资料」的流程。

**不含任何作者个人简历、网站个人记录或预授权附件。** 每个项目独立保存使用者的资料，之后可以直接调用，不必每次重新提供简历。

## 安装

需要能执行 Python/终端并使用 Skills 的 AI 助手（例如 Codex），Python 3.9+，以及初次安装依赖的网络。浏览器填写需要本机 Chrome 或使用者提供的 CDP 接口。

```sh
git clone https://github.com/jojojjjjj/resume-form-filler.git
cd resume-form-filler
python3 tools/install.py --project /path/to/your-project
cd /path/to/your-project
python3 tools/resume-fill.py status
```

Windows 使用自己的 Python 命令，例如 `py -3 tools/install.py --project C:\path\to\project`；后文 python3 同理替换。默认只安装到目标项目 `.agents/skills/resume-form-filler`，写入短入口和 `.gitignore`；不会安装全局 Skill 或修改全局配置。新技能未被当前 AI 会话发现时，新开会话或直接指明 SKILL.md 路径。

首次命令自动检查并安装项目级依赖到 `.resume-form-filler/runtime/`；缺少 Python 3.12 时通过校验的 uv 自动下载项目内 Python。系统浏览器、旧版 Word 转换器和登录授权不会自动安装或代办。依赖齐全后不重复安装，只有版本要求变化或环境损坏时修复。

也可在源码目录直接运行 `python3 tools/resume-fill.py ...`，资料会留在该目录的 `.resume-form-filler/`。仅复制 SKILL.md 不够：需要完整 Skill 目录中的脚本和 references。

## 第一次使用

在 AI 助手里说：

```text
使用 $resume-form-filler，先导入 /path/to/my-resume.pdf，
然后填写我已经打开的 https://career.example.com/resume/edit 。
```

支持 PDF、LaTeX `.tex`、Word `.docx`；旧 `.doc` 使用现有 macOS textutil 或 LibreOffice。脚本本地抽取正文，当前 AI 助手整理教育、工作、项目等完整字段并对照原文核对，建立持久 profile。无需单独的 LLM API Key，不自动上传简历到解析服务。扫描 PDF 需要先 OCR；文本框或自定义宏需要对照原文检查，不能保证任意格式无损解析。

命令行步骤（语义解析仍由当前 AI 助手完成）：

```sh
python3 tools/resume-fill.py init --resume /path/to/my-resume.pdf
# 由 AI 助手读取本次 resume.txt/源文件，填入输出的 profile.draft.json 并核对
python3 tools/resume-fill.py review-profile --draft '输出的草稿路径' --reviewed --source '真实核对依据'
python3 tools/resume-fill.py doctor
python3 tools/resume-fill.py start --url 'https://career.example.com/resume/edit'
```

init 会输出提取警告和环境检查结果。浏览器需使用者启用 Chrome 远程调试许可并完成站点登录；普通 doctor 不接触浏览器，需要连接诊断时使用 doctor --browser。缺简历/未核对 profile 时，填写入口会停止，不回退到作者的资料或虚构内容。

## 以后直接调用

```text
使用 $resume-form-filler 填写我已打开的招聘简历页：完整编辑网址。
```

助手从本地资料与本站映射建立当前模块 plan，然后：

```sh
python3 tools/resume-fill.py apply --session DIR --plan module.json
python3 tools/resume-fill.py verify --session DIR --plan module.json
python3 tools/resume-fill.py checkpoint --session DIR --plan module.json --module '教育经历' --save-selector '#actual-save' --success-text '实际成功提示'
```

控件与提示必须来自当前页面，示例选择器不可直接照搬。每模块默认保存；用户本轮的只读/不保存指示优先。网页原有非空值冲突先确认，未知信息不猜，自动补全验证真正选中。上传仅复用**使用者已授权**的用途匹配附件，网站第一次使用仍需要适配其实际控件。

**不会自动投递岗位、勾选隐私条款或处理口令/MFA。** 保持用户招聘页在后台，不刷新或关闭用户编辑页。保存被必填校验阻挡时保留本地恢复记录；toast/跳转仅是保存动作证据，必须读回持久值才能报告持久化已验证。

## 资料、更新与隐私

```text
your-project/
├── .agents/skills/resume-form-filler/   # 可公开的代码和说明
├── tools/resume-fill.py                # 项目入口
└── .resume-form-filler/                # 私人状态，整个目录默认 Git 忽略
    ├── profile.md                     # 已核对事实、偏好、附件授权
    ├── imports/                       # 提取正文、候选结构、来源指纹
    ├── sites/                         # 使用者的本站映射
    ├── runs/                          # 页面快照、计划、核对与恢复记录
    ├── helpers/                       # 本次网页操作辅助脚本
    └── runtime/                       # 项目级依赖、浏览器工具状态
```

源简历、LaTeX include 变化会让旧计划失效：重新 init，对照新旧事实，review-profile --replace-reviewed 自动备份后替换。旧补充事实不能因新简历没写就删掉。重新调用 start 重建计划，不把历史网页保存状态当当前结果。

文件提取和持久化在本地，但将正文交给当前 AI 助手核对时，适用该助手自身的数据处理设置；这不是承诺模型本地运行。不要把 `.resume-form-filler/`、原始简历、照片、论文、浏览器 profile 或个人网站映射加入公开 Git。

升级：在源码目录 git pull，再运行 `tools/install.py --project /path/to/your-project --replace`，旧 Skill 备份到私人状态目录；不会删除 profile。卸载：移除目标项目的 `.agents/skills/resume-form-filler/` 和工具入口即可；私人状态保留，如需清除请先自行备份再删除 `.resume-form-filler/`。停止相关 Harness daemon 后再删除其 runtime，不影响其他项目浏览器状态。

## 开发与验证

```sh
python3 tools/resume-fill.py doctor       # 自动建立开发依赖
python3 tools/check.py                   # 公开文件/隐私模式/语法检查
python3 tools/test.py                    # 三种格式导入、资料状态、安装、工作流保护与浏览器离线夹具
python3 tools/package.py                 # 仅按 PUBLIC_FILES.txt 打包并生成 SHA-256
```

CI 在 macOS、Ubuntu、Windows 上运行离线测试；真实招聘站点需要使用者登录与一次控件映射，测试不证明任意站点均适配。具体发布验证范围看 [VALIDATION.md](VALIDATION.md)。

文档：[Skill](skills/resume-form-filler/SKILL.md) · [导入/资料](skills/resume-form-filler/references/profile.md) · [计划](skills/resume-form-filler/references/plan.md) · [浏览器](skills/resume-form-filler/references/browser.md) · [故障处理](skills/resume-form-filler/references/operations.md)。MIT 开源，第三方来源见 [THIRD_PARTY.md](THIRD_PARTY.md)。
