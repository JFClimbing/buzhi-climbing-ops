# 不止攀岩 · 运营数据自动化（buzhi-climbing-ops）

抖音「不止攀岩」+ 小红书「Neverest 不止攀岩」的**数据采集 + 复盘 + 飞书日报**工具集。
本仓库用于**复现**整套流程：抓数 → 统一格式 → 复盘分析 → 写入飞书多维表格。

> 隐私：`data/` 里是工作室自己的内容数据（标题、播放、赞藏），**请保持仓库为 Private**。

---

## 一、这套东西能干什么

| 环节 | 脚本 | 产出 |
|---|---|---|
| 抓抖音后台 | `collector/dy_review.py` | `data/douyin/dy_works_<date>.json`（作品 + 全部指标） |
| 抓抖音账号级 | `collector/dy_fans_check.py` | 粉丝/获赞/关注 |
| 抓小红书后台 | `collector/xhs_login.py` | `data/xiaohongshu/xhs_notes_<date>.json` |
| 复盘分析 | （见 `reports/`） | 复盘报告 + 指标底稿 |
| 日报写飞书 | `agent/daily_job.py` | 飞书两张表（素材明细 + 每日汇总）+ AI 风格小结 |

**合规**：全部走平台自己的后台页面/导出，不用爬虫、不抓包、不调私有接口。
详见 `agent/官方API申请清单.md`。

---

## 二、快速复现（5 分钟，不需要任何平台账号）

只想验证「解析 → 写飞书 → 生成日报」这条链路是否可跑通：

```bash
cd agent

# 1) 用仓库里的真实快照造一份「平台导出 CSV」
python make_sample_exports.py

# 2) dry-run：不碰飞书，只把要写入的内容落盘到 dryrun/
python daily_job.py --dry-run --date 2026-09-30
cat dryrun/*_1.json   # 素材明细 payload
cat dryrun/*_2.json   # 每日汇总 payload（含 AI 风格「每日小结」）
```

预期输出（2026-09-30 那条，两个平台各 1 条）：

```
抖音：解析 1 条
小红书：解析 1 条
素材写入成功 2 条
汇总行写入成功（2026-09-30：2 条 / 曝光 2191 / 正常）
```

每日小结示例：

> 今日发布 2 条素材（抖音 1、小红书 1）。表现最好的是《攀岩主锁的型or形？一篇视频讲清楚》，曝光 2,145、赞 79、藏 19。两平台合计曝光 2,191、互动 127、新增粉丝 43。咨询线索：今天还没填（私信数/报名意向需人工补录）。建议：抖音曝光远高于小红书，小红书那条可换更吸引人的首图再发一次。

---

## 三、接入真实的飞书（30 分钟）

1. 飞书开放平台建「企业自建应用」→ 开通 `bitable:app` → 发布版本
2. 复制凭据：`app_id` / `app_secret`；多维表格 URL 里取 `app_token`
3. 配置：
   ```bash
   cd agent
   cp config.example.json config.json
   # 填 feishu.app_id / app_secret / app_token
   ```
4. 自动建表建字段（幂等，可重复跑）：
   ```bash
   python setup_tables.py --yes
   # 把打印的 table_id 填回 config.json 的 table_material / table_daily
   ```
5. 真跑一次：
   ```bash
   python daily_job.py --date 2026-09-30
   ```
6. 每天自动（Windows）：
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\agent\register_task.ps1   # 每天 08:30
   # 或双击 agent\启动每日任务.bat
   ```

> ⚠️ `setup_tables.py` 只新建「新媒体-素材明细」「新媒体-每日汇总」两张独立表，
> 不会碰排班表、装备出入库表。异常只写在自己那行，不打断其他表。

---

## 四、重新抓一次最新数据（需要登录态）

> 登录态目录（`.auth-edge` / `.auth-xhs`）**等同账号密码，绝不能提交**，已在 `.gitignore` 里排除。

```bash
# 抖音：会弹出 Edge，扫一次码后长期复用
cd collector
python dy_review.py            # 作品数据 → data/douyin/dy_works_<今天>.json
python dy_fans_check.py        # 账号级数据

# 小红书
python xhs_login.py            # → data/xiaohongshu/xhs_notes_<今天>.json
```

依赖：`pip install playwright`（不需要 `playwright install`，直接用系统 Edge）。

---

## 五、复盘结论（2026-11-18）

完整内容见 [`reports/复盘报告_2026-11-18.md`](reports/复盘报告_2026-11-18.md)，三条核心：

1. **25 天粉丝 355 → 589（+66%）**，作品 9 → 17，累计播放 6.1 万 → 11.4 万。
2. **大播放 ≠ 涨粉**：「辅助管式保护器」2.1 万播放只涨 11 粉（5.2/万），
   而「主锁型or形」2,541 播放涨 46 粉（181/万）——**单点判断题比大而全的测评更吸粉**。
3. **小红书是收藏场**：赞看比 3.15% vs 抖音 1.91%，藏看比 1.34% vs 0.36%；
   「失效/避坑」类在小红书比抖音还高（179%），但长视频（裁绳）只有抖音的 12.6% → 小红书该做图文。

---

## 六、目录结构

```
buzhi-climbing-ops/
├─ README.md                     # 本文件（复现指南）
├─ requirements.txt
├─ .gitignore
├─ agent/                        # 新媒体数据 Agent（飞书写入 + 日报）
│  ├─ daily_job.py               # 主流程
│  ├─ feishu.py                  # 飞书客户端（token 缓存/批量/重试/dry-run）
│  ├─ setup_tables.py            # 一键建表建字段
│  ├─ make_sample_exports.py     # 用快照造样例导出 CSV
│  ├─ sources/                   # 两平台解析器 + 官方 API 骨架
│  ├─ 字段配置清单.md / 字段映射说明.md / 定时任务说明.md / 官方API申请清单.md
│  └─ 导出说明_抖音.md / 导出说明_小红书.md
├─ collector/                    # 抓数脚本（playwright + 系统 Edge）
│  ├─ dy_review.py               # 抖音作品数据
│  ├─ dy_fans_check.py           # 抖音账号级
│  └─ xhs_login.py               # 小红书笔记数据
├─ data/
│  ├─ douyin/                    # dy_works_2026-10-19 / 10-24 / 11-18 + 粉丝快照
│  └─ xiaohongshu/               # xhs_notes_2026-10-13 / 11-18
└─ reports/
   ├─ 复盘报告_2026-11-18.md      # 人看的复盘
   ├─ 复盘指标_2026-11-18.md      # 机器算的指标底稿
   └─ 复盘对比数据_2026-11-18.json # 结构化的多快照对比
```

---

## 七、口径说明（对比数据时必看）

- 抖音「播放/赞/藏/吸粉」= **作品发布以来累计值**，不是当日新增；
- 小红书「观看」同为累计值；
- 跨平台只比**比例**（赞/播、藏/播、每万播放吸粉），不比绝对值；
- 抖音主页粉丝数、总获赞是**账号级实时值**，与作品累计不可直接相加。

---

## 八、还没做的（下一步）

- [ ] 飞书应用凭据接入（需要工作室自己的飞书账号）
- [ ] 私信/咨询/报名意向人工补录 → 才能算「内容→报名」转化
- [ ] 定时自动抓数（目前是手动运行 `dy_review.py` / `xhs_login.py`）
- [ ] 小红书图文版内容（把长视频拆成步骤图）
