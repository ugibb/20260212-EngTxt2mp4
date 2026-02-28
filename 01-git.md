# Git 提交至 GitHub 流程

---

## 流程概要（按顺序执行）

1. **先更新 README**：在「更新记录」顶部加当日日期与条目，在「TODO-list」中勾选本迭代已完成项。
2. **提交到 GitHub**：已有仓库则 `add → commit → push`；未初始化则先 `git init`、配 `.gitignore`、`remote add` 再推送。
3. **禁止同步内容（非常重要）**：以下目录/文件必须写入 `.gitignore`，不得提交到远程。

---

## 禁止同步的内容（必须写入 .gitignore）

```
00-req/
doc/
input/
log/
output/
.env
```

说明：原始需求(00-req)、设计文档(doc)、输入(input)、日志(log)、输出(output)、敏感配置(.env) 仅保留本地，不推送到 GitHub。

---

## 操作步骤

### 1. 首次：初始化 + 禁止同步 + 推送

1. 进入项目根目录：`git init`，分支可改为 `main`：`git branch -m main`。
2. 创建 `.gitignore`（**禁止同步**，必配）：

   ```bash
   cat > .gitignore << 'EOF'
   # 禁止同步（重要）
   00-req/
   doc/
   input/
   log/
   output/
   .env
   # Python / IDE / OS
   .venv/
   __pycache__/
   *.pyc
   .idea/
   .vscode/
   .DS_Store
   EOF
   ```

3. 提交并推送：`git add .` → `git commit -m "feat: 初始化项目，完成基础功能搭建"` → `git remote add origin https://github.com/ugibb/20260212-EngTxt2mp4.git` → `git push -u origin main`。

### 2. 日常：先更新 README，再提交

1. **先做**：更新 README「更新记录」（当日日期 + 条目）、「TODO-list」（已完成项勾选 `[x]`）。
2. 提交代码：`git add .`（或按文件）→ `git commit -m "类型: 描述"`（如 `docs: 更新记录与 TODO-list（YYYY-MM-DD）`、`feat: xxx`）。
3. 推送：`git push origin main`。

---

## 常见问题

- **remote origin already exists**：`git remote rm origin` 后再 `git remote add origin <url>`。
- **忽略项曾被提交过**：`git rm -r --cached 目录名`，再 `commit`、`push`，确保 `.gitignore` 已包含该目录。
