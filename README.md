# 高质量精读视频 Txt2mp4

将英文短文快速转换为带 TTS 音频、歌词同步、录屏导出的雅思精读视频。

## 功能

- **Step 1 文本预处理**：`step1_format_text.py` 对 `input/YYYYMMDD/` 中的 txt 进行换行、去中文注释，输出至 `output/YYYYMMDD/01-txt/{文件名}.txt`
- **Step 2 词汇提取**：`step2_extract_vocab.py` 调用大模型提取核心词汇，保存至 `output/YYYYMMDD/02-vocabulary/{文件名}.md`
- **Step 3 TTS**：`step3_generate_tts.py` 从 MD 段落结构生成 `_en.txt` 并生成 TTS；支持多角色语音（在 input 或 MD 中按段标记角色，按段合成后合并为单一 mp3+json），详见 `doc/TTS角色语音技术方案.md`
- **Step 4 排版 HTML**：`step4_generate_pic_html.py` 根据模板生成排版 HTML，保存至 `output/YYYYMMDD/04-pic_html/{文件名}.html`
- **Step 5 播放页 HTML**：`step5_generate_mp4_html.py` 根据 `template-txt2mp4.html` 生成 TTS 播放页，保存至 `output/YYYYMMDD/05-mp4_html/{文件名}.html`
- **Step 6 录屏**：`step6_record_video.py` Playwright 全屏录屏，导出至 `output/YYYYMMDD/06-mp4/{文件名}.mp4`
- **Step 7 资源页面**：`step7_generate_resource_page.py` 仅更新全局 `output/resources.html`，聚合所有日期资源，三标签展示词汇 MD、排版 HTML、播放页 HTML

## 环境要求

- Python 3.10+
- Edge TTS（无需 API Key）
- Playwright（需 `playwright install chromium`）
- 可选：Kimi/OpenAI API Key（用于 step2_extract_vocab 词汇提取）
- 可选：ffmpeg（step3 多角色多段 TTS 合并、以及 webm 转 mp4）

## 安装

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

## 目录结构

input、output 按**日期**分子目录（格式 YYYYMMDD），便于多批次管理：

```
input/
  YYYYMMDD/         # 如 20260220，其下为当日 .txt 英文正文（可含中文翻译）
output/
  YYYYMMDD/         # 与 input 日期对应
    01-txt/         # 文本预处理（.txt 完整版）；_en.txt 由 step3 从 MD 段落结构生成
    02-vocabulary/  # 大模型生成的词汇 md
    03-mp3/         # TTS 音频 + 单词时间戳 json
    04-pic_html/    # 排版 HTML（template.html）
    05-mp4_html/    # TTS 播放页 HTML，样式从 template/styles/ 加载
    06-mp4/         # 导出的视频
  resources.html   # 资源索引页（step7 生成，在 output/ 下，三标签展示词汇/排版/播放页）
template/          # HTML 模板
log/                # 运行日志
```

## 输入格式

**input/YYYYMMDD/{name}.txt**：英文正文，可含中文翻译。支持 ^、「」、[]、【】、{} 人工手动标注核心词汇。**TTS 角色标记**：单独一行写 `[男]`/`[M]`、`[女]`/`[F]`、`[独白]`/`[N]`、`[童男]`/`[B]`、`[童女]`/`[G]`，表示紧跟其后的该段使用对应角色语音；详见 `doc/TTS角色语音技术方案.md`。

### 资料类型与 input 命名规则

- 通过**文件名前缀**识别资料名称，用于 mp4 播放页红框标签与资源页分组。
- 约定前缀（在 `src/utils/material_type.py` 中配置）：
  - `WH_` → 美国白宫新闻发布会（资料类型：新闻）
  - `BBC_` → BBC news（新闻）
  - `EIM_` → English in a Minute（娱乐）
  - `S900_` → 雅思口语必备900句（跟读）
  - `IELT50_` 或无前缀 → 50 篇英语短文搞定雅思阅读核心词汇（精读）
- 新增资料名称或资料类型时，在 `src/utils/material_type.py` 的 `MATERIAL_TYPES` / `MATERIAL_NAMES` 中增加配置即可，详见 `doc/资料类型功能设计.md`。

## 运行方式

**一键执行全流程：**

```bash
python src/run_all.py
```

**执行 input 下全部日期目录（逐日运行所选步骤）：**

```bash
python src/run_all.py --all   # 或 -a
```

**指定单日期目录（默认使用 .env 的 RUN_DATE 或 input 下最新日期文件夹）：**

```bash
python src/run_all.py --date 20260220           # 使用 input/20260220、output/20260220
python src/run_all.py -d 20260220 5 6           # 指定日期并仅执行 step5、step6
```

**按指定步骤执行：**

```bash
python src/run_all.py 5 6              # 仅执行 step5、step6
python src/run_all.py --steps 1 2 3   # 仅执行 step1、step2、step3
```

各步骤可独立运行（使用 .env 的 `RUN_DATE` 或 input 下最新日期目录）：

```bash
python src/step1_format_text.py
python src/step2_extract_vocab.py
python src/step3_generate_tts.py
python src/step4_generate_pic_html.py
python src/step5_generate_mp4_html.py
python src/step6_record_video.py
python src/step7_generate_resource_page.py
```

## 配置

- **src/utils/config.py**：`SKIP_IF_EXISTS`、`SKIP_EXISTING_FILES` 控制是否跳过已存在文件（默认 False，直接在此文件修改）
- **.env**：`RUN_DATE`（可选）指定运行日期目录，如 `RUN_DATE=20260220`，不设则使用 input 下最新日期文件夹；也可用 `run_all.py -d 20260220` 覆盖
- **.env**：`SILICONFLOW_API_KEY`（默认，硅基流动免费）或 `KIMI_API_KEY`/`OPENAI_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL`（step2_extract_vocab 词汇提取）
- **.env**：`LLM_REQUEST_TIMEOUT`（秒，默认 300）控制 LLM 请求超时；词汇提取输出较长时可能需 1–2 分钟才收到首 token
- **.env**：`LLM_MAX_TOKENS`（可选）不配置则不传 max_tokens；若词汇 MD 被截断可设 16384
- **src/utils/config.py**：`VIDEO_WIDTH`、`VIDEO_HEIGHT` 录屏尺寸（默认 1080x1920，移动端竖屏 9:16）
- **src/utils/material_type.py**：资料类型（icon/红框）与资料名称（resources.html 分组）、input 前缀匹配规则；扩展见 `doc/资料类型功能设计.md`

## 输出

- 视频路径：`output/YYYYMMDD/06-mp4/{文件名}.mp4`（需 ffmpeg）或 `.webm`
- 文件名中的空格、特殊字符会替换为 `_`

## 更新记录

### 2026-02-23

- **Step2 词汇提取**：LLM 输出因 token 限制截断导致 MD 无「段落结构」时，用 01-txt 的段落信息自动补全并追加，避免 Step3 报「MD 无段落结构」跳过；新增 `_build_paragraph_section`、扩展 `_ensure_paragraph_structure`；已存在 MD 再次运行 Step2 时会通过 `_fix_existing_md_paragraph_structure` 自动补全。
- **doc**：新增《LLM 输出截断与段落结构技术方案》（方案 A 已实现，B～E 为可选与推荐组合）；README 配置说明补充 `LLM_MAX_TOKENS` 建议。

### 2026-02-21

- **Step7 资源页**：解决部分播放页 HTML 未出现在 resources.html 的问题——词汇 MD 为 `Day02`、而 04/05 输出为 `Day2` 时 stem 不一致导致未匹配；新增 `_stem_variants_for_day()`，对 Day0X/DayX 做兼容变体匹配后再查找 pic/mp4 文件。
- **Step5 播放页 + 文本处理**：修复「多段被当成一行」的对齐问题。原因：MD 中 `word,word`（无空格）被解析成一个 token，LRC 为两词，对齐卡住后整段错位。方案 A：`_align_lrc_to_segments` 支持将多个 LRC 词拼接成一个与 MD token 匹配（如 myths+pointed→mythspointed）；方案 B：`text_processor.ensure_space_after_punctuation()` 对标点后补空格（如 `myths,pointed`→`myths, pointed`），step5 的 segments 构建时调用，从源头统一分词。
- **Step1**：开始处理前在 `^` 前补空格（`ensure_space_before_caret`），避免 `our^exploration` 等人为将两词合并为一个词，影响后续分词与 LRC 对齐。
- **run_all**：新增 `-f/--file NAME`，支持仅处理 input 目录下指定文件（文件名或 stem，可带或不带 `.txt`）。config 增加 `RUN_SINGLE_FILE` 与 `get_input_files_to_process()`，step1～6 改为使用该列表；step7 仍全量扫描以刷新 resources.html。示例：`python src/run_all.py -d 20260220 -f "IELT50_Day02：A Forest Exploration.txt"`。
- **Step3 对话男女 TTS**：实现多角色 TTS，支持在 input 或 MD 中按段标记 `[男]`/`[女]` 等角色，按段合成后合并为单一 mp3+json；新增 `src/utils/voice_role.py` 角色配置与解析，详见 `doc/TTS角色语音技术方案.md`。

### 2026-02-20

- **目录与配置**：input/output 按日期分子目录（`input/YYYYMMDD/`、`output/YYYYMMDD/01-txt/` 等）；默认运行 input 下最新日期；`RUN_DATE` 支持 `.env` 与 `run_all.py -d 20260220` 指定日期。
- **run_all**：每次执行自动包含 step7，保证资源页包含全部链接；新增 `-d/--date` 参数。
- **Step5 播放页**：修复 MD 段落与 LRC 对齐错位（句号后无空格如 `viral.I` 导致多段合并为一）；段落英文规范化（句号/问号/感叹号后加大写字母时补空格）。
- **Step7 资源页**：仅更新全局 `output/resources.html`，不再生成当日 `output/YYYYMMDD/resources.html`；扫描所有 `output/YYYYMMDD/` 聚合资源；链接为相对 `output/` 的路径（如 `20260220/02-vocabulary/xxx.md`）；资源按文件修改时间倒序排列。
- **资源索引模板**：默认展示「播放页 HTML」内容（与左侧默认 tab 一致）；新增 TODO-list 小节。
- **播放页样式**：模板样式链接改为 `../../../template/styles/styleN.css`，从项目 `template/styles/` 加载，step5 不再拷贝样式到 output。

## TODO-list（迭代任务）

便于记录与跟踪项目迭代，完成一项可勾选 `[x]`。

- [ ] （在此添加待办事项）
- [ ] 1、词汇+编号：由于md文件中的词汇跟短文中的英语单词输出技术方案，
- [x] 2、音标，极简；
- [ ] 3、内容块样式区分；
- [ ] 4、新增MP42MP4 功能，下载MP4格式的时政新闻，一键输出标准化后的雅思学习资料
- [x] 5、归类英文资料类型：「English in a Minute」、「雅思口语必备900句」、「50 篇英语短文搞定雅思阅读核心词汇」、「美国白宫新闻发布会」等
- [x] 6、设计并更新「mp4_html」的英文资料类型icon：英文资料类型会不定期增加，来丰富雅思学习资料，因此需要做一个资料类型功能设计，方便后续扩展资料类型，同时增对不同英文资料，需要做前端页面方便识别，需要针对不同类型的资料进行icon设计（目前是默认显示「新闻」，如附图中的红框内容）
- [x] 7、新增对话男女对话TTS
- [x] 8、「MP4_html」日期非系统日期，而是所在input 文件夹的日期
- [x] 9、「Run_all」增加执行全部input文件夹下所有日期的文件
- [ ] 9、资料类型更新为文章类型，文章类型与资料名称不做直接关联，主要针对雅思高频内容，直接由LLM 根据文章内容来确定文章类型，主要由以下六类问这个类型：1️⃣ 教育 2️⃣ 科技 3️⃣ 环境 4️⃣ 社会 5️⃣ 经济 6️⃣ 文化
- [ ] 10、新增MP32MP4功能，下载MP3 格式的音频文件，一键输出标准化后的雅思学习资料。
