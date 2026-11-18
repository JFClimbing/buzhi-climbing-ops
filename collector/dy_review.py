#!/usr/bin/env python3
"""抖音作品数据 · Windows 一键抓取（Playwright + 系统 Edge）

用法:
  python tools/dy_review_windows.py               # 抓取 + 存快照 + 表格 + 增量 + 对答案
  python tools/dy_review_windows.py --login-only  # 只打开浏览器让你登录，不抓取
  python tools/dy_review_windows.py --diff        # 只看与上次快照的播放增量
  python tools/dy_review_windows.py --table       # 打印全量表格

依赖:
  pip install playwright
  使用系统浏览器（Windows 默认 Edge，macOS/Linux 默认 Chrome），
无需 playwright install 下载 Chromium。可用 DSH_BROWSER_CHANNEL 覆盖。

首次运行会打开 Edge，你需要扫码/验证码登录抖音创作者中心一次；
登录态持久化到 .auth-edge/（已 gitignore），之后可复用，过期需重登。
"""
import json
import os
import re
import sys
import glob
import time
import datetime

# Windows 默认控制台编码 GBK 遇到 emoji 会抛 UnicodeEncodeError，统一转 UTF-8 输出
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass

try:
    from playwright.sync_api import sync_playwright


except ImportError:
    print("❌ 缺少 playwright。请先运行：pip install playwright")
    sys.exit(1)

# 浏览器 channel：跨平台探测。Windows 的 Edge 叫 msedge，macOS / Linux 上
# 一般用 Chrome。可用 DSH_BROWSER_CHANNEL 覆盖（如 chromium / chrome / msedge）。
CHANNEL = os.environ.get("DSH_BROWSER_CHANNEL") or (
    "msedge" if os.name == "nt" else "chrome")


def launch(pw, user_data, headless=False):
    """统一的持久化上下文启动器 —— 全部抓取脚本共用，避免各自复制 channel 逻辑。"""
    return pw.chromium.launch_persistent_context(
        user_data, channel=CHANNEL, headless=headless,
        viewport=None, args=["--start-maximized"],
    )

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                      # 仓库根
DATA = os.path.join(ROOT, "data")
REG = os.path.join(DATA, "prediction_registry.json")
USER_DATA = os.path.join(ROOT, ".auth-edge")      # 本账号独立登录态（与另一个号隔离，gitignore）
URL = "https://creator.douyin.com/creator-micro/content/manage"
os.makedirs(DATA, exist_ok=True)
os.makedirs(USER_DATA, exist_ok=True)

# ⚠️ 字段名会随创作者中心改版变化。实测（2026-10-09）当前版本暴露的是：
#     播放 / 点赞 / 评论 / 分享 / 收藏 / 完播率 / 2秒跳出率 / 吸粉量
# 旧版的「划走率 / 文案展开率 / 平均浏览图片数」已经不存在了 —— 旧字段名会让
# 整列抓成 "-"。改版后再跑 --table，若某列变 "-" 就是又改名了。
METRIC_ORDER = ["播放", "点赞", "评论", "分享", "收藏", "完播率",
                "2秒跳出率", "吸粉量"]

# 滚动加载列表：Douyin 作品列表是懒加载的自定义滚动容器，必须滚它才出卡片
SCROLL_JS = """
() => {
  const list = document.querySelector('div[class*="list-scroll"]')
             || document.querySelector('div[class*="scroll"]');
  if (list) {
    list.scrollTop += 800;
    return list.scrollTop;
  }
  window.scrollBy(0, 800);
  return -1;
}
"""

# 抓取：从卡片提取标题 + 指标标签/值（选择器沿用 ops-manual/数据复盘自动化.md 的结论）
EXTRACT_JS = """
() => {
  const out = [];
  const cards = document.querySelectorAll('div[class*="video-card-content"]');
  for (const c of cards) {
    const titleEl = c.querySelector('[class*="title"]');
    const metrics = {};
    const items = c.querySelectorAll('div[class*="metric-item-container"]');
    for (const it of items) {
      const lab = it.querySelector('div[class*="metric-label"]');
      const val = it.querySelector('div[class*="metric-value"], div[class*="value"]');
      if (lab && val) metrics[lab.innerText.trim()] = val.innerText.trim();
    }
    const head = c.innerText.split('\\n').map(s => s.trim()).filter(Boolean).slice(0, 12);
    const all = c.innerText.split('\\n').map(s => s.trim()).filter(Boolean);
    // 卡片第一行是时长（02:07），日期行形如「2026年10月08日 19:30」
    const duration = all.find(s => /^\\d{1,2}:\\d{2}$/.test(s)) || '';
    const pub = all.find(s => /\\d{4}\\u5e74\\d{1,2}\\u6708\\d{1,2}\\u65e5/.test(s)) || '';
    // 标题元素里混入了「编辑作品/设置权限/删除作品」等悬停菜单文字，只取第一行
    const titleText = (titleEl ? titleEl.innerText : c.innerText).split('\\n')[0].trim();
    out.push({ title: titleText, head: head, metrics: metrics,
               duration: duration, publish_date: pub });
  }
  return { count: cards.length, cards: out };
}
"""


def num(v):
    """创作者中心原始文本 → 数字。

    ⚠️ 不能用 `replace("万", "0000")`：`'3.3万'` 会变成 `'3.30000'`，解析成 **3.3**，
    整整小 10000 倍 —— 播放增量、对答案偏差%、区间判定会全部失真。
    这里改成「后缀乘数」解析，支持 亿 / 万 / w / k（大小写），并容忍逗号、百分号、"+"。
    """
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(",", "").replace("%", "").replace("+", "")
    if not s or s in {"-", "--", "—"}:
        return None
    mult = 1.0
    for suffix, m in (("亿", 1e8), ("万", 1e4), ("w", 1e4), ("W", 1e4),
                      ("k", 1e3), ("K", 1e3)):
        if s.endswith(suffix):
            s = s[:-len(suffix)].strip()
            mult = m
            break
    try:
        return float(s) * mult
    except ValueError:
        return None


# 登录界面判据：只要还停在扫码/验证码界面，就**绝不能**导航 —— 会打断扫码、二维码失效
LOGIN_UI_JS = """
() => {
  const t = (document.body ? document.body.innerText : '') || '';
  for (const k of ['扫码登录', '验证码登录', '手机号登录', '密码登录',
                   '请使用抖音扫码', '二维码已失效', '登录后查看更多']) {
    if (t.includes(k)) return true;
  }
  return !!document.querySelector(
    '[class*="login-panel"], [class*="login_panel"], [class*="login-modal"],' +
    '[class*="qrcode"], [class*="qr-code"]');
}
"""

# 「已登录」的正面证据：创作者中心外壳（左侧导航）——登录页没有这套导航。
# 用页面内容而不是 URL 判断"是否已登录"，才不会在用户还没扫码时就抢跑导航。
SHELL_JS = """
() => {
  const t = (document.body ? document.body.innerText : '') || '';
  return t.includes('内容管理') &&
         (t.includes('收入变现') || t.includes('创作服务') || t.includes('数据中心'));
}
"""


def _probe(page, js, default):
    """跑一段 JS，出错一律返回 default（页面正在跳转时 evaluate 会抛）。"""
    try:
        return bool(page.evaluate(js))
    except Exception:                                     # noqa: BLE001
        return default


def _wait_login(page, timeout=360, renav_gap=4.0, max_renav=30):
    """等待登录完成（浏览器可见，用户扫码/验证码）。

    坑一：登录成功后抖音会跳到创作者中心**首页**，而不是我们请求的作品管理页，
    只在原地等作品卡片的 selector，会白等到超时。
    坑二（2026-10-12 实测）：原版用一次性的 `reentered` 标志 + 判据
    `"creator.douyin.com" in url and "login" not in url`。可这个判据在**还没登录**
    时就成立（登录浮层同样在 creator.douyin.com、URL 里也没有 "login"）→ 它在用户
    扫码之前就抢跑一次导航；等用户真正登录、落到首页之后，循环再也不会重新导航，
    于是必然超时。实测证据：那次运行报「等待登录超时」，但 `.auth-edge` 里
    `sessionid` / `sid_tt` / `uid_tt` / `x_tt_token` 全套都在 —— 登录其实成功了。
    修法：① 在登录界面（LOGIN_UI_JS 命中）里**绝不导航**，不打断扫码；
    ② 只有拿到「已登录」的正面证据（SHELL_JS 命中创作者中心外壳）且人不在作品
       管理页时，才**周期性**导航回去（不再是一次性）。
    """
    print("⏳ 请在弹出的 Edge 里完成抖音创作者中心登录（扫码 / 验证码）…",
          flush=True)
    deadline = time.time() + timeout
    target = URL.rstrip("/")
    last_nav = 0.0
    navs = 0
    hits = 0
    announced = False
    while time.time() < deadline:
        if page.query_selector('div[class*="video-card-content"]') or \
           page.query_selector('div[class*="list-scroll"]'):
            # 容器出现 ≠ 内容渲染完：SPA 换页时容器会先出现，卡片随后才挂上。
            # 要求连续两次看到，避免"刚报成功就抓到 0 条"。
            hits += 1
            if hits >= 2:
                print("✅ 已进入作品管理页", flush=True)
                return True
            time.sleep(1.5)
            continue
        hits = 0
        url = (page.url or "").split("#")[0].rstrip("/")
        # 已经在作品管理页：原地等卡片渲染（此时重载只会打断加载）
        if "creator.douyin.com" in url and url != target:
            # 页面正在跳转时读不到 → 一律当作"登录中"，宁可不动作
            on_login_ui = _probe(page, LOGIN_UI_JS, True)
            logged_in = _probe(page, SHELL_JS, False)
            if logged_in and not on_login_ui and time.time() - last_nav >= renav_gap:
                if not announced:
                    print("✅ 检测到已登录，重新进入作品管理页…", flush=True)
                    announced = True
                try:
                    page.goto(URL, wait_until="domcontentloaded", timeout=90000)
                except Exception as exc:                  # noqa: BLE001
                    print(f"   ⚠️ 重新导航失败：{exc}", flush=True)
                last_nav = time.time()
                navs += 1
                if navs >= max_renav:                     # 兜底：别无限刷页面
                    print("   ⚠️ 重新导航次数过多，放弃。", flush=True)
                    return False
                time.sleep(3)
                continue
        time.sleep(2)
    return False


def scrape(page, rounds=25):
    """真实滚轮滚动 + 抓取，直到卡片数量稳定。

    注意：此列表是自定义滚动容器，window.scrollBy / scrollTop 均无效，
    必须用真实滚轮事件（等价于 minis-browser-use 的 scroll 命令）。
    """
    last = -1
    stable = 0
    for _ in range(rounds):
        vw = page.viewport_size or {"width": 1280, "height": 720}
        page.mouse.move(vw["width"] // 2, vw["height"] // 2)
        page.mouse.wheel(0, 900)
        time.sleep(0.8)
        r = page.evaluate(EXTRACT_JS)
        n = r.get("count", 0)
        if n == last:
            stable += 1
            if stable >= 3 and n > 0:
                break
        else:
            stable = 0
        last = n
    return page.evaluate(EXTRACT_JS)


def parse(cards):
    """卡片 → 快照条目。

    ⚠️ 平台对**不同年龄**的视频显示**不同指标组**（2026-10-12 实测）：
      · 新视频（发布约 48h 内）：弹幕 / 封面点击率 / **平均播放占比**
      · 老视频：完播率 / 2秒跳出率
    因此除了 `raw`（只留 METRIC_ORDER 这 8 键，保持向后兼容：print_table /
    print_diff / auto_check 都读它），另存一份 `metrics_all` = 卡片上抓到的全部
    标签。**「平均播放占比」就是判断"这条是不是太长了"的那个后台指标**
    （平均观看时长 ÷ 视频总长），旧版 parse() 会把它丢掉 → 时长问题就没数据可答。
    """
    out = []
    for c in cards:
        title = (c.get("title") or "").split("\n")[0].strip()
        allm = dict(c.get("metrics", {}) or {})
        m = {k: allm.get(k, "-") for k in METRIC_ORDER}
        out.append({"title": title[:120], "raw": m, "metrics_all": allm,
                    "images": None,
                    "date": c.get("publish_date", ""), "duration": c.get("duration", ""),
                    "sched": "", "status": "published", "pinned": False})
    return out


def save(posts):
    today = datetime.date.today().isoformat()
    p = os.path.join(DATA, f"dy_works_{today}.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=1)
    print(f"   💾 已存 {p}")
    return p


def last_snapshot(exclude=None):
    fs = sorted(glob.glob(os.path.join(DATA, "dy_works_*.json")))
    fs = [f for f in fs if f != exclude]
    if not fs:
        return None
    with open(fs[-1], encoding="utf-8") as f:
        return json.load(f)


def print_table(posts):
    print(f"\n{'时长':>6} {'标题':<22}{'播放':>7}{'赞':>6}{'评':>5}{'享':>5}{'藏':>5}"
          f"{'完播率':>9}{'2秒跳出':>9}{'吸粉':>6}  发布日期")
    for p in posts:
        r = p["raw"]
        print(f"{p.get('duration', ''):>6} {p['title'][:22]:<22}{r['播放']:>7}{r['点赞']:>6}"
              f"{r['评论']:>5}{r['分享']:>5}{r['收藏']:>5}"
              f"{r['完播率']:>9}{r['2秒跳出率']:>9}{r['吸粉量']:>6}  {p.get('date', '')}")
        # 新视频那组指标（弹幕 / 封面点击率 / 平均播放占比）不在 METRIC_ORDER 里，
        # 单独缩进一行打印 —— 不撑宽上面的固定表头，也让「平均播放占比」可见。
        extra = [f"{k} {v}" for k, v in (p.get("metrics_all") or {}).items()
                 if k not in METRIC_ORDER]
        if extra:
            print("       ↳ " + " · ".join(extra))


def key(p):
    return (p["title"] or "")[:16]


def print_diff(old, new):
    om = {key(p): p for p in old}
    print("\n" + "=" * 72)
    print("📈 与上次快照的差异（播放增量）")
    print("=" * 72)
    for p in new:
        k = key(p)
        if k in om:
            a, b = num(om[k]["raw"]["播放"]), num(p["raw"]["播放"])
            if a is not None and b is not None and b != a:
                print(f"  {p['title'][:26]:<28} {a:>7.0f} → {b:>7.0f}  ({b - a:+.0f})")
        else:
            print(f"  🆕 {p['title'][:30]}  播放 {p['raw']['播放']}")


def auto_check(posts, force=False):
    if not os.path.exists(REG):
        return
    with open(REG, encoding="utf-8") as f:
        reg = json.load(f)
    today = datetime.date.today().isoformat()
    due = [it for it in reg.get("items", [])
           if it["status"] == "pending" and (force or it["check_at"] <= today)]
    if not due:
        return
    print("\n" + "=" * 72)
    print("🎯 自动对答案")
    print("=" * 72)
    for it in due:
        hit = None
        for p in posts:
            if it.get("match") and it["match"] in p["title"]:
                hit = p
                break
        if not hit:
            print(f"\n⏳ {it['title']}  —— 还没发（计划 {it['published']}）")
            continue
        print(f"\n📌 {it['title']}   （对答案日 {it['check_at']}）")
        for mk, pred in it.get("metrics", {}).items():
            act = hit["raw"].get(mk, "-")
            an = num(act)
            ok = ""
            if isinstance(pred, (int, float)) and an is not None:
                dev = (an - pred) / pred * 100
                ok = f"  偏差 {dev:+.1f}%"
                rng = (it.get("range") or {}).get(mk)
                if rng:
                    ok += "  ❌ 出区间" if not (rng[0] <= an <= rng[1]) else "  ✅ 在区间"
            print(f"     {mk:<8} 预测 {str(pred):<8} 实测 {str(act):<8}{ok}")


def main():
    args = sys.argv[1:]
    login_only = "--login-only" in args

    with sync_playwright() as pw:
        ctx = launch(pw, USER_DATA, headless=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(URL, wait_until="domcontentloaded", timeout=90000)

        if not _wait_login(page):
            print("❌ 等待登录超时（6 分钟）。请重跑本脚本并完成登录。")
            ctx.close()
            sys.exit(1)

        if login_only:
            print("✅ 已登录。登录态已保存，浏览器保持打开，可手动关闭。")
            ctx.close()
            return

        print("📡 正在抓取抖音创作者中心…")
        inner = scrape(page)
        posts = parse(inner["cards"])
        print(f"   ✅ 抓到 {len(posts)} 条作品")
        if not posts:
            print("⚠️ 抓到 0 条 —— 可能登录态过期或页面结构变化，请重登后重试。")
            ctx.close()
            sys.exit(1)

        path = save(posts)

        if "--table" in args or True:
            print_table(posts)

        auto_check(posts, force="--force-check" in args)

        old = last_snapshot(exclude=path)
        if old:
            print_diff(old, posts)

        ctx.close()


if __name__ == "__main__":
    main()
