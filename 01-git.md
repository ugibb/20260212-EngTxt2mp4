# Git 代码提交至 GitHub 远程仓库全流程

含：初次提交、日常更新、忽略文件夹、固定 commit 信息、迭代收尾。

---

## 核心目标

1. 初始化本地 Git 仓库，配置 `.gitignore` 忽略指定文件夹
2. 将本地代码初次推送到 GitHub 远程仓库
3. 日常代码更新后，按固定格式提交并推送
4. 所有 commit 信息统一使用固定模板，忽略指定文件夹不提交
5. **迭代收尾**（日常提交时**先执行**）：先更新 README 的「更新记录」与「TODO-list」，再按更新记录为每个变更文件生成提交信息并提交到 GitHub

---

## 操作步骤

### 步骤 1：初始化本地仓库 + 配置忽略文件夹（仅初次提交需执行）

1. 进入项目根目录
2. 初始化 Git 仓库：

   ```bash
   git init
   ```

3. 创建并编辑 `.gitignore` 文件（添加需要忽略的文件夹/文件），任选一种方式：

   **方式一：直接创建并写入忽略规则（推荐）**

   ```bash
   cat > .gitignore << EOF
   # 通用忽略规则（可根据项目类型删减/添加）
   # 前端项目
   node_modules/
   dist/
   build/
   .env
   .env.local
   # 后端/Python项目
   venv/
   __pycache__/
   *.pyc
   # 编辑器/IDE配置
   .idea/
   .vscode/
   .DS_Store
   # 自定义需要忽略的文件夹
   - 原始需求目录：00-req/
   - 设计文档目录：doc/
   - 代码执行输入目录：input/
   - 代码执行日志目录：log/
   - 代码执行输出目录：output/
   - 敏感配置项文件：.env
   EOF
   ```

   **方式二：手动编辑 .gitignore**

   若上述命令不生效，可用 `vim .gitignore` 或编辑器打开并手动写入上述规则。

---

### 步骤 2：初次提交并推送到远程仓库

1. 将所有未忽略的文件加入暂存区：

   ```bash
   git add .
   ```

2. 提交代码（固定 commit 信息，可替换括号内的内容）：

   ```bash
   git commit -m "feat: 初始化项目，完成基础功能搭建"
   ```

3. 关联 GitHub 远程仓库（替换为你的仓库地址）：

   ```bash
   git remote add origin https://github.com/ugibb/20260212-EngTxt2mp4.git
   ```

4. 推送代码到 main 分支（若默认分支是 master，则替换为 master）：

   ```bash
   git push -u origin main
   ```

---

### 步骤 3：迭代收尾（先执行：先更新 README，再提交代码）

日常提交时**先执行本步骤**。在完成当日开发后，按以下顺序执行，保证文档与提交信息一致：**先完成 3.1、3.2 更新 README.md 内容，再执行 3.3 的代码提交。**

#### 3.1 汇总并总结今天的迭代内容

- 回顾今日修改过的所有文件与功能点
- 用简短条目归纳：修复/新增/调整了哪些模块、解决了什么问题、对外行为或配置有何变化
- 每条对应 README「更新记录」中一条 bullet，便于后续作为各文件 commit 信息的依据

#### 3.2 更新 README.md（先完成本步，再执行 3.3 提交）

- **更新记录**：在「更新记录」顶部新增当日日期小节（如 `### 2026-02-21`），将 3.1 的总结条目逐条写入，格式与现有条目一致（`- **模块/功能**：具体说明`）
- **TODO-list**：将本迭代中已完成的事项由 `[ ]` 改为 `[x]`，未完成项保持 `[ ]`

#### 3.3 按「更新记录」提交代码到 GitHub（在 3.2 完成后执行）

- **原则**：每个**代码文件**（含 `src/`、`template/`、`config` 等，不含 README）的提交信息，应来自本次迭代在「更新记录」中与该文件相关的描述；若某文件无直接对应条目，可用本条迭代的概括句或最相关的一条
- **操作步骤**：
  1. `git status` 查看本次变更文件列表
  2. 将变更分为两类：**README.md** 单独提交；**其余代码/配置/模板文件**按文件或按逻辑分组提交
  3. **先提交各代码文件**：根据 README 当日「更新记录」中与该文件相关的条目，写成一条 commit 信息（格式：`类型: 简短描述`，如 `fix: Step7 词汇 Day0X/DayX stem 兼容匹配`、`feat: run_all 支持 -f 指定单文件`），然后按文件或小分组依次：
     - `git add <文件或路径>`
     - `git commit -m "<对应本条更新记录的描述>"`
  4. **再提交 README.md**：`git add README.md`，commit 信息示例：`docs: 更新记录与 TODO-list（YYYY-MM-DD 迭代收尾）`
  5. 全部提交完成后执行：`git push origin main`

**说明**：若希望一次提交包含多个文件，可将同一更新记录条目下的多个文件一起 `git add` 后用一个 commit；若一条更新记录涉及多个文件，也可拆成多个 commit，每个 commit 信息都引用或概括同一条更新记录，以保持可追溯。

---

### 步骤 4：日常更新代码后提交（简单场景重复执行）

若无需按迭代收尾分文件提交，可直接使用本步骤一次性提交并推送：

1. 查看代码变更（可选，确认修改内容）：

   ```bash
   git status
   ```

2. 将更新的文件加入暂存区（`.` 表示所有变更，也可指定文件/文件夹）：

   ```bash
   git add .
   ```

3. 提交代码（固定 commit 格式，按场景替换描述）。常用 commit 类型：feat（新增功能）、fix（修复 bug）、docs（文档更新）、style（格式调整）、refactor（重构）：

   ```bash
   git commit -m "fix: 修复XX功能的XX问题 | docs: 更新接口文档 | feat: 新增XX模块"
   ```

4. 推送至远程仓库（初次推送后，后续可简化为 `git push`）：

   ```bash
   git push origin main
   ```

---

## 常见问题处理

### 1. 关联远程仓库提示 "remote origin already exists"

```bash
git remote rm origin   # 删除已关联的 origin，再重新执行 git remote add
```

### 2. 推送提示分支不存在

确认远程仓库默认分支是 main 还是 master，对应修改推送命令中的分支名。

### 3. 忽略文件夹仍被提交

检查 `.gitignore` 路径是否正确（需在项目根目录）。若文件已被提交过，需先删除缓存再提交：

```bash
git rm -r --cached 已提交的忽略文件夹名
git commit -m "docs: 移除已提交的忽略文件夹"
git push
```
