# AI 热点雷达

这是一个把“n8n 热点捕捉器”的思路改造成桌面 App + GitHub Actions 自动报告的项目。

它现在有两种使用方式：

- 本地桌面 App：双击桌面快捷方式，直接在 App 里查看和刷新报告，不需要浏览器端口。
- GitHub Pages：推到 GitHub 后，由 Actions 定时运行并发布成网页。

## 本地桌面 App

第一次运行需要安装依赖：

```bash
python -m pip install -r requirements.txt
npm install
```

然后启动：

```bash
npm run app
```

或者双击桌面的 `AI热点雷达 App` 快捷方式。

## AI 分析引擎

默认优先使用 OpenAI：

- `OPENAI_API_KEY`：已写入 `.env.local`。
- `OPENAI_MODEL`：默认 `gpt-5.5`，可在 `.env.local` 或 `config/sources.yml` 修改。

如果 OpenAI API 项目没有额度或 billing 未开通，程序会自动回退到本地规则摘要，报告仍然可以生成。

也支持 Anthropic 备用：

- `ANTHROPIC_API_KEY`
- `ANTHROPIC_MODEL`

## 本地刷新报告

```bash
python scripts/run_pipeline.py
```

输出文件：

- `public/index.html`：最新报告。
- `public/data/latest.json`：结构化数据。
- `public/archive/*.html`：历史归档。

## GitHub 上线

1. 登录 GitHub CLI：`gh auth login`
2. 创建仓库并推送项目。
3. 在仓库 Actions Secrets 添加：
   - `OPENAI_API_KEY`
   - `TWITTERAPI_KEY`，可选，只有启用 X 搜索时需要。
4. 在仓库 Pages 设置里选择 `GitHub Actions`。
5. 手动运行一次 `AI Hotspot Radar Report` workflow。

之后它会每 6 小时自动运行并更新 GitHub Pages。

## 配置来源

编辑 `config/sources.yml`：

- RSS：YouTube 频道、博客、媒体站、FeedSpot 找到的订阅源。
- GitHub Search：监控开源项目。
- twitterapi_search：对应 X 热点 API，需要 `TWITTERAPI_KEY`。

## 和 n8n 思路的对应

| n8n 节点 | 本项目 |
| --- | --- |
| Cron/触发器 | GitHub Actions schedule |
| HTTP/RSS 节点 | `config/sources.yml` + Python 抓取 |
| 字段预处理 | 去重、关键词命中、热度评分 |
| AI 节点 | OpenAI / Anthropic / 本地规则 |
| 存档 | `public/data` 和 `public/archive` |
| 展示 | Electron 桌面 App + GitHub Pages |

