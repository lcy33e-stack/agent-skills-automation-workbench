# Agent Skills 自动化工作台

这个项目不是单一的“AI 热点检索工具”。它的目标是复刻那条评论里的核心效果：

通过 GitHub Actions 在云端定时运行一组 Agent Skills，自动抓取、分析、归档任意任务结果，再生成 HTML 报告并部署到 GitHub Pages；本地则提供一个桌面 App 直接查看和手动运行。

你可以把它配置成：

- 全网热点/选题日报
- GitHub 项目监控
- 竞品动态追踪
- 论文/RSS 摘要
- 产品灵感收集
- 投资、行业、内容、工具等任意主题观察

## 本地桌面 App

第一次运行需要安装依赖：

```bash
python -m pip install -r requirements.txt
npm install
```

启动：

```bash
npm run app
```

或者双击桌面的 `Agent Skills自动化工作台` / `AI热点雷达 App` 快捷方式。

## 配置任务

主要编辑：

```text
config/sources.yml
```

你可以修改：

- `workflow_name`：当前自动化任务名
- `workflow_goal`：这组 Skills 要完成的目标
- `keywords`：评分和分析关注的关键词
- `sources`：RSS、GitHub Search、X API 等来源

## AI 分析引擎

默认优先使用 OpenAI：

- `OPENAI_API_KEY`：保存于 `.env.local`
- `OPENAI_MODEL`：默认 `gpt-5.5`

如果 OpenAI API 项目没有额度或 billing 未开通，程序会自动回退到本地规则摘要，报告仍然可以生成。

也支持 Anthropic 备用：

- `ANTHROPIC_API_KEY`
- `ANTHROPIC_MODEL`

## 输出

- `public/index.html`：最新运行结果
- `public/data/latest.json`：结构化数据
- `public/archive/*.html`：历史归档

## GitHub 上线

本机目前还没有登录 GitHub CLI。登录后可以继续：

```bash
gh auth login
```

然后创建仓库、推送项目，并在仓库 Actions Secrets 添加：

- `OPENAI_API_KEY`
- `TWITTERAPI_KEY`，可选，只有启用 X 搜索时需要

Pages 设置里选择 `GitHub Actions`，之后 workflow 会每 6 小时自动运行一次。

## 和 n8n 思路的对应

| n8n 节点 | 本项目 |
| --- | --- |
| Cron/触发器 | GitHub Actions schedule |
| HTTP/RSS 节点 | `config/sources.yml` + Python 抓取 |
| 字段预处理 | 去重、关键词命中、热度评分 |
| AI 节点 | OpenAI / Anthropic / 本地规则 |
| 存档 | `public/data` 和 `public/archive` |
| 展示 | Electron 桌面 App + GitHub Pages |
