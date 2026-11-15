#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
行迹 · 一键部署到 GitHub Pages

只需要一个 GitHub Token：不用装 git、不用 git 登录、不用打开 GitHub 网页、
不用配 SSH、不用 pip 装任何依赖（仅 Python 3.8+ 标准库）。

做的事：
  1. 用 Token 校验身份，自动取用户名
  2. 仓库不存在就自动创建（默认名 xingji-studio）
  3. 把本目录的静态文件通过 Git Data API 合成「一次提交」推到 main
     —— 逐文件比对 Git blob SHA，只上传真正变化的文件；上传走多路并发
     （默认 12 路，可用 XJ_WORKERS / --workers 调），仍然只触发一次 Actions
  4. 自动把 Pages 的 Source 设为 GitHub Actions，并主动触发一次部署
  5. 打印最终网址

Token 只存在于内存 / 本机 token.txt / 环境变量，绝不写进仓库、绝不打印、绝不进日志。

用法（双击 deploy.bat 即可，通常什么都不用输）：
  set GITHUB_TOKEN=ghp_xxx        # 可选：免输入
  set GITHUB_REPO=owner/my-repo   # 可选：换仓库名，默认 <你>/xingji-studio
  python deploy.py --dry-run      # 只看要传哪些文件，不联网
  python deploy.py --repo owner/name
  python deploy.py --include-single   # 连 9MB 的单文件预览版一起传（默认跳过）
  set XJ_WORKERS=8                   # 可选：网络不稳降到 8 路，快就设 16（默认 12）
"""
from __future__ import annotations

import argparse
import base64
import datetime
import getpass
import hashlib
import json
import os
import posixpath
import random
import socket
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

VERSION = '1.4'
ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_REPO_NAME = 'xingji-studio'
DEFAULT_BRANCH = 'main'
MAX_BLOB = 8 * 1024 * 1024          # 超过这个体积走 API 不稳，默认跳过（单文件版可用 --include-single 显式放行）
SINGLE_FILE = '旅行灵感工作台.html'   # 本地双击用，Pages 不需要，默认跳过

# GitHub 对「一次提交上千条目录项」容易回 502 / 网关超时：拆成小批，用 base_tree 逐级叠加。
TREE_CHUNK = 100
RETRY_STATUS = {429, 500, 502, 503, 504}
# 短时间内大量写请求触发的 secondary rate limit 是 403 而不是 429，
# 旧版没把它算进可重试，一次就整单中止。权限类 403 仍立即失败，不做无意义重试。
RATE_LIMIT_WORDS = ('rate limit', 'abuse', 'secondary rate', 'too many requests',
                    'please wait', 'retry after')
RETRY_MAX = 6
RETRY_BASE = float(os.environ.get('XJ_RETRY_BASE', '0.8'))
STATE_FILE = '.deploy_state.json'    # 本机断点续传记录，绝不上传

# 站点跑起来不需要这些文件：默认不上传（--include-tests 可放行）；
# 万一某个真传失败了，也只跳过它，不再让整站跟着不提交。
DEFAULT_SKIP_DIRS = ('tests/',)
DEFAULT_SKIP_MARKERS = ('验收', '核查', '修复说明', '硬证据', '十套底色',
                        'vX_', 'vY_', '最终解压')
# 失败隔离用的「非必需」范围更宽：文档、字幕、生成脚本、顶层截图都不该阻塞上线。
OPTIONAL_DIRS = ('tests/', 'tools/', 'docs/')
OPTIONAL_EXTS = ('.md', '.srt', '.vtt')

# 首次部署约 2900 个文件（其中 2460 张分镜 PNG）。逐文件串行 POST 每个都要等一次
# 跨国往返，是慢的唯一根因；改成多路并发，同样一次 commit、同样只触发一次 Actions。
WORKERS_DEFAULT = 12
WORKERS_MIN, WORKERS_MAX = 1, 32

SKIP_DIRS = {'.git', '__pycache__', 'node_modules', '.pytest_cache',
             'media/_build_tmp', '.idea', '.vscode'}
# deploy.bat / deploy.py 本身也随站点上传：从 Pages 打开 TOKEN_GUIDE.html 时
# 能直接拿到同一套脚本。真正不能传的只有本机凭据。
SKIP_NAMES = {'token.txt', 'repo.txt', 'deploy.log', '.deploy_state.json',
              '.DS_Store', 'Thumbs.db'}
SKIP_EXTS = {'.pyc', '.pyo', '.log', '.tmp', '.bak', '.swp'}
SKIP_SUFFIX = ('~',)

# 站点必需文件，少了任何一个都会上线失败，脚本会主动拦住
REQUIRED = (
    'index.html',
    'film.html',
    'admin.html',
    'config.js',
    'libretts-bridge.js',
    'data/cities.js',
    'data/cities.full.js',
    'data/national-cities.js',
    'data/plan-config.js',
    'vendor/mp4-muxer.js',
    '.nojekyll',
    # 站点是纯静态，Actions 里只保留这一个部署工作流，不需要任何构建输入
    '.github/workflows/pages.yml',
    'tools/validate_full_data.py',
    'tools/validate_plan_config.py',
)

# 站点是纯静态，Actions 里只允许这一个工作流。其它任何 .github/workflows/*.yml
# 都是早期「制作包 JSON → CI 重建」流程的残留，不管叫什么名字（build.yml、
# build-film.yml、ci.yml …），既不上传，远端已有的也随本次提交一并清掉；
# 否则 push 会额外触发一个红色任务，报「缺少 media/source/project.json」。
ALLOWED_WORKFLOWS = {'.github/workflows/pages.yml'}

# 旧版「制作包 JSON → CI 重建静态成品」整套已下线：浏览器里直接逐帧导出成片，
# 不需要 media/source/project.json。
LEGACY_PATHS = {
    'tools/build_film.py',
    'media/source/README.md',
}
LEGACY_PREFIXES = ('media/source/',)


def is_legacy(path: str) -> bool:
    if path.startswith('.github/workflows/') and path.lower().endswith(('.yml', '.yaml')):
        return path not in ALLOWED_WORKFLOWS
    return path in LEGACY_PATHS or any(path.startswith(p) for p in LEGACY_PREFIXES)


def is_default_skip(path: str) -> bool:
    """默认不随站点上传的测试脚本 / 验收材料（可用 --include-tests 放行）。"""
    if is_legacy(path):
        return True
    if path in REQUIRED:
        return False
    if any(path.startswith(d) for d in DEFAULT_SKIP_DIRS):
        return True
    name = posixpath.basename(path)
    return any(m in name for m in DEFAULT_SKIP_MARKERS)


def is_optional(path: str) -> bool:
    """上传失败时能否安全跳过：站点必需文件一律不许跳过。"""
    if is_legacy(path):
        return True
    if path in REQUIRED:
        return False
    p = path.lower()
    if any(p.startswith(d) for d in OPTIONAL_DIRS):
        return True
    if p.endswith(OPTIONAL_EXTS):
        return True
    name = posixpath.basename(path)
    if any(m in name for m in DEFAULT_SKIP_MARKERS):
        return True
    # 顶层验收截图不是画面素材；assets/ 下的 png/svg 是分镜配图，不能算可选
    if name.lower().endswith(('.png', '.jpg', '.jpeg')) and not p.startswith('assets/'):
        return True
    return False


class DeployError(Exception):
    pass


_LAST_TOKEN = ''
PROGRESS = {'total': 0, 'ready': 0, 'uploaded': 0, 'reused': 0, 'skipped': 0}


def say(msg: str = '') -> None:
    print(msg, flush=True)


def redact(text: str, token: str) -> str:
    if token and text:
        return text.replace(token, '***TOKEN***')
    return text or ''


def git_blob_sha(data: bytes) -> str:
    """本地算出与 GitHub 完全一致的 blob SHA，用来判断文件是否真的变了。"""
    h = hashlib.sha1()
    h.update(b'blob ' + str(len(data)).encode('ascii') + b'\0')
    h.update(data)
    return h.hexdigest()


# --------------------------------------------------------------------------
# 文件收集
# --------------------------------------------------------------------------
def collect(include_single: bool, include_tests: bool = False):
    items, skipped = {}, []
    deferred = []
    legacy_local = []
    for base, dirs, names in os.walk(ROOT):
        rel_dir = os.path.relpath(base, ROOT).replace(os.sep, '/')
        if rel_dir == '.':
            rel_dir = ''
        dirs[:] = [d for d in dirs
                   if (posixpath.join(rel_dir, d) if rel_dir else d) not in SKIP_DIRS
                   and d not in SKIP_DIRS]
        for name in sorted(names):
            rel = posixpath.join(rel_dir, name) if rel_dir else name
            low = name.lower()
            # 旧版构建流程残留：既不上传，也不作为「远端已有则保留」的候选
            if is_legacy(rel):
                legacy_local.append(rel)
                continue
            if not include_tests and is_default_skip(rel):
                deferred.append(rel)
                continue
            if name in SKIP_NAMES or name.startswith('~') or name.endswith(SKIP_SUFFIX):
                continue
            if os.path.splitext(low)[1] in SKIP_EXTS:
                continue
            if rel in SKIP_DIRS or any(rel.startswith(d + '/') for d in SKIP_DIRS):
                continue
            if name == SINGLE_FILE and not include_single:
                skipped.append('%s（%.1f MB，本地双击用，加 --include-single 才上传）'
                               % (name, os.path.getsize(os.path.join(base, name)) / 1048576))
                continue
            full = os.path.join(base, name)
            if not os.path.isfile(full):
                continue
            size = os.path.getsize(full)
            # 单文件预览版约 9 MB，只有显式 --include-single 才走大 blob 路径
            if size > MAX_BLOB and not (name == SINGLE_FILE and include_single):
                skipped.append('%s（%.1f MB，超过安全上限，未上传）' % (rel, size / 1048576))
                continue
            with open(full, 'rb') as f:
                data = f.read()
            items[rel] = {'data': data, 'sha': git_blob_sha(data), 'size': size}
    if deferred:
        skipped.append('测试脚本 / 验收材料 %d 个（站点运行不需要，默认不上传；'
                       '加 --include-tests 可放行）' % len(deferred))
    if legacy_local:
        wf = [p for p in legacy_local if p.startswith('.github/workflows/')]
        skipped.append('⚑ 本地解压目录里还留着旧包残留 %d 个（已忽略，不会上传；'
                       '建议删掉整个旧文件夹重新解压）。其中工作流：%s'
                       % (len(legacy_local), '、'.join(wf) if wf else '无'))
    return items, skipped, deferred


# --------------------------------------------------------------------------
# GitHub REST
# --------------------------------------------------------------------------
class GitHub:
    def __init__(self, token: str, api_base: str):
        self.token = token
        self.api_base = api_base.rstrip('/')
        self.calls = []
        self._lock = threading.Lock()
        self._throttle = 0.0      # 并发下遇到 429 自动加一点间隔，避免持续撞二级限流
        self.limit_hit = False    # 本轮是否撞过限流：触发后用 1 路低速补传

    @staticmethod
    def _limit_word(raw: bytes) -> bool:
        try:
            msg = json.loads(raw.decode('utf-8', 'replace')).get('message', '')
        except Exception:
            msg = raw.decode('utf-8', 'replace')
        low = (msg or '').lower()
        return any(w in low for w in RATE_LIMIT_WORDS)

    def _retryable(self, status: int, raw: bytes) -> bool:
        if status in RETRY_STATUS:
            return True
        # secondary rate limit 是 403；权限不足也是 403，但重试没有意义
        return status == 403 and self._limit_word(raw)

    def _pace(self) -> None:
        with self._lock:
            delay = self._throttle
        if delay:
            time.sleep(delay)

    def _relax(self) -> None:
        with self._lock:
            if self._throttle > 0:
                self._throttle = max(0.0, self._throttle - 0.02)

    def slow_down(self, delay: float = 0.6) -> None:
        """收尾补传时主动放慢，避免刚被限流又立刻撞上去。"""
        with self._lock:
            self._throttle = max(self._throttle, delay)

    def call(self, method: str, path: str, body=None, allow=(200, 201),
             want_headers=False, retry_max: int = 0):
        url = self.api_base + path
        payload = None
        headers = {
            'Authorization': 'Bearer ' + self.token,
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
            'User-Agent': 'xingji-deploy/' + VERSION,
        }
        if body is not None:
            payload = json.dumps(body, ensure_ascii=False).encode('utf-8')
            headers['Content-Type'] = 'application/json'

        attempt = 0
        limit = retry_max or RETRY_MAX
        while True:
            attempt += 1
            self._pace()
            req = urllib.request.Request(url, data=payload, headers=headers, method=method)
            self.calls.append((method, path))
            try:
                with urllib.request.urlopen(req, timeout=90) as resp:
                    raw = resp.read()
                    status, hdrs = resp.status, dict(resp.headers)
                if self._retryable(status, raw) and attempt <= limit:
                    self._backoff(status, hdrs, attempt, path, limit=limit)
                    continue
                if status not in allow:
                    self._raise(status, path, raw, attempt)
            except urllib.error.HTTPError as e:
                raw = e.read()
                status, hdrs = e.code, dict(e.headers)
                if self._retryable(status, raw) and attempt <= limit:
                    self._backoff(status, hdrs, attempt, path, limit=limit)
                    continue
                if status not in allow:
                    self._raise(status, path, raw, attempt)
            except (urllib.error.URLError, socket.timeout, ConnectionResetError, OSError) as e:
                if attempt <= limit:
                    self._backoff(0, {}, attempt, path, redact(str(e), self.token), limit=limit)
                    continue
                raise DeployError(
                    '连不上 GitHub API（%s），已重试 %d 次。检查网络 / 代理；如在受限网络，可设 '
                    'GITHUB_API_BASE 指向可达的镜像或本机桥。原始错误：%s'
                    % (self.api_base, limit, redact(str(e), self.token)))

            # 204（如 workflow dispatch）没有任何响应体，data 必须先初始化
            data = None
            # 404 被显式允许时（探测仓库 / ref / pages 是否存在）统一返回 None，
            # 不能把 GitHub 的 {"message":"Not Found"} 当成「存在」。
            if status == 404 and 404 in allow:
                data = None
            elif raw:
                try:
                    data = json.loads(raw.decode('utf-8'))
                except (ValueError, UnicodeDecodeError):
                    data = None
            self._relax()
            return (data, hdrs, status) if want_headers else data

    def _backoff(self, status: int, hdrs: dict, attempt: int, path: str,
                 extra: str = '', limit: int = 0):
        if status == 429 or status == 403:
            # 一旦撞限流，所有并发线程立刻一起放慢，并记下「收尾要降到 1 路」
            with self._lock:
                self._throttle = min(1.2, self._throttle + 0.25)
                self.limit_hit = True
        delay = RETRY_BASE * (2 ** (attempt - 1))
        ra = hdrs.get('Retry-After') or hdrs.get('retry-after') or ''
        if ra:
            try:
                delay = max(delay, min(float(ra), 60))
            except ValueError:
                pass
        delay = min(delay + random.uniform(0, 0.5), 30)
        say('  ⏳ GitHub %s（%s）· 第 %d/%d 次重试，%.1fs 后继续%s'
            % (status or '网络中断', path.rsplit('/', 1)[-1], attempt, limit or RETRY_MAX,
               delay, ('：' + extra[:80]) if extra else ''))
        time.sleep(delay)

    def _raise(self, status: int, path: str, raw: bytes, attempts: int = 0):
        msg = ''
        try:
            msg = json.loads(raw.decode('utf-8')).get('message', '')
        except Exception:
            pass
        msg = redact(msg or raw.decode('utf-8', 'replace')[:300], self.token)
        if status == 401:
            raise DeployError('Token 无效或已过期（401）。请重新生成一个，勾 repo + workflow。')
        if status == 403:
            if any(w in msg.lower() for w in RATE_LIMIT_WORDS):
                raise DeployError(
                    'GitHub 二级限流（403：短时间内写请求太多），已自动降速并重试 %d 次仍未放行。\n'
                    '这不是 Token 失效，也不是文件有问题；换 Token 通常没用。\n'
                    '等 1–2 分钟，或先把并发调低：set XJ_WORKERS=4 再双击 deploy.bat。\n'
                    '已上传的文件都记在本机断点里，重跑只补没成功的那几个，不会从头再传。'
                    % (attempts or RETRY_MAX))
            if 'workflow' in msg.lower() or 'refusing' in msg.lower():
                raise DeployError('Token 缺少 workflow 权限（403）。classic Token 请勾 workflow；'
                                  'fine-grained 请给 Workflows: read/write。GitHub 原话：' + msg)
            raise DeployError('没有权限（403）：' + msg)
        if status == 404 and path.startswith('/repos/'):
            raise DeployError('仓库不存在且 Token 无权自动创建（404）：' + msg)
        if status == 422:
            raise DeployError('GitHub 拒绝这次提交（422）：' + msg)
        if status in RETRY_STATUS:
            raise DeployError(
                'GitHub 服务端暂时不可用（%s · %s），已自动重试 %d 次仍未恢复。\n'
                '这不是 Token、权限或本地文件的问题，多为 GitHub 瞬时故障；'
                '目录树已拆成每批 %d 条分批提交，不会因条目过多被网关掐断。\n'
                '稍等 1–2 分钟再双击 deploy.bat 即可，已上传的文件会自动跳过、不会重复上传；'
                '也可到 https://www.githubstatus.com 看服务状态。'
                % (status, path, attempts or RETRY_MAX, TREE_CHUNK))
        raise DeployError('GitHub 返回 %s %s：%s' % (status, path, msg))


# --------------------------------------------------------------------------
# 主流程
# --------------------------------------------------------------------------
def get_token(need: bool) -> str:
    for key in ('GITHUB_TOKEN', 'GH_TOKEN'):
        v = os.environ.get(key, '').strip()
        if v:
            return v
    p = os.path.join(ROOT, 'token.txt')
    if os.path.isfile(p):
        with open(p, 'r', encoding='utf-8-sig') as f:
            v = f.read().strip()
        if v:
            return v
    if not need:
        return ''
    if not sys.stdin.isatty():
        raise DeployError('没有 Token：请设 GITHUB_TOKEN 环境变量，或把 Token 存进同目录 token.txt。')
    v = getpass.getpass('粘贴 GitHub Token（输入不显示，回车确认）: ').strip()
    if not v:
        raise DeployError('Token 为空，已取消。')
    return v


def resolve_repo(cli_repo: str, login: str) -> tuple[str, str]:
    raw = (cli_repo or os.environ.get('GITHUB_REPO', '')
           or os.environ.get('GH_REPO', '')).strip()
    if not raw:
        p = os.path.join(ROOT, 'repo.txt')
        if os.path.isfile(p):
            with open(p, 'r', encoding='utf-8-sig') as f:
                raw = f.read().strip()
    if not raw:
        return login, DEFAULT_REPO_NAME
    if '/' in raw:
        owner, name = raw.split('/', 1)
        return owner.strip(), name.strip()
    return login, raw


def site_url(owner: str, repo: str) -> str:
    if repo.lower() == (owner + '.github.io').lower():
        return 'https://' + repo + '/'
    return 'https://%s.github.io/%s/' % (owner, repo)


def api_paths(owner: str, repo: str) -> str:
    return '/repos/%s/%s' % (urllib.parse.quote(owner), urllib.parse.quote(repo))


def remote_tree(gh: GitHub, base: str, head: str) -> dict:
    """返回 {path: blob_sha}，用来做增量比对。"""
    commit = gh.call('GET', base + '/git/commits/' + head)
    tree_sha = commit['tree']['sha']
    tree = gh.call('GET', base + '/git/trees/' + tree_sha + '?recursive=1')
    return {e['path']: e['sha'] for e in tree.get('tree', []) if e.get('type') == 'blob'}


def resolve_workers(cli: int) -> int:
    """并发路数：命令行 > XJ_WORKERS 环境变量 > 默认；网络差可调到 4。"""
    raw = cli
    if not raw:
        try:
            raw = int(os.environ.get('XJ_WORKERS', '0') or 0)
        except ValueError:
            raw = 0
    return max(WORKERS_MIN, min(WORKERS_MAX, raw or WORKERS_DEFAULT))


def load_state() -> dict:
    """本机断点记录：失败后重跑时，已上传的 blob 不必再传一遍。"""
    try:
        with open(os.path.join(ROOT, STATE_FILE), 'r', encoding='utf-8') as f:
            obj = json.load(f)
        return obj if isinstance(obj, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(state: dict) -> None:
    try:
        with open(os.path.join(ROOT, STATE_FILE), 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=1)
    except OSError:
        pass


def create_tree_chunked(gh: GitHub, base: str, entries: list) -> str:
    """把整棵目录树拆成 ≤TREE_CHUNK 条的小批，用 base_tree 逐级叠加。

    第一批不带 base_tree，等于「从空树开始」：远端多余文件不会混进最终 tree，
    站点仍然一次提交就干净；后续批次只叠加，单次请求体很小，不会撞网关 502。
    """
    if not entries:
        return gh.call('POST', base + '/git/trees', {'tree': []})['sha']
    tree_sha = None
    batches = (len(entries) + TREE_CHUNK - 1) // TREE_CHUNK
    for idx, start in enumerate(range(0, len(entries), TREE_CHUNK), 1):
        body = {'tree': entries[start:start + TREE_CHUNK]}
        if tree_sha:
            body['base_tree'] = tree_sha
        tree_sha = gh.call('POST', base + '/git/trees', body)['sha']
        if batches > 1 and (idx == 1 or idx % 5 == 0 or idx == batches):
            say('  ⚙ 组装目录树 %d/%d 批（每批 %d 条）' % (idx, batches, TREE_CHUNK))
    return tree_sha


def update_ref(gh: GitHub, base: str, branch: str, commit: str, head) -> None:
    """更新分支指针；重试/响应丢失时先查一次 ref，避免 422 误报失败。"""
    ref_path = base + '/git/ref/heads/' + urllib.parse.quote(branch)
    cur = gh.call('GET', ref_path, allow=(200, 404))
    if cur and (cur.get('object') or {}).get('sha') == commit:
        return
    if head:
        gh.call('PATCH', base + '/git/refs/heads/' + urllib.parse.quote(branch),
                {'sha': commit, 'force': False})
    else:
        gh.call('POST', base + '/git/refs',
                {'ref': 'refs/heads/' + branch, 'sha': commit})


def deploy(args):
    items, skipped, deferred_paths = collect(args.include_single, args.include_tests)
    missing = [p for p in REQUIRED if p not in items]
    if missing:
        raise DeployError('缺少上线必需文件，已停止：' + '、'.join(missing)
                          + '\n请确认把压缩包完整解压到同一个文件夹，index.html 在根目录。')
    total = sum(v['size'] for v in items.values())

    say('行迹 · 一键部署 v%s' % VERSION)
    say('本地文件 %d 个 / %.2f MB' % (len(items), total / 1048576))
    for s in skipped:
        say('  ⊘ 跳过 ' + s)
    if args.include_single and SINGLE_FILE in items:
        say('  ⚠ %s 约 %.1f MB，将走大 blob 通道；若 GitHub 拒收会自动跳过，不影响其它文件。'
            % (SINGLE_FILE, items[SINGLE_FILE]['size'] / 1048576))

    if args.dry_run:
        say('\n[dry-run] 不联网、不读取 Token。将要上传：')
        for p in sorted(items):
            say('  %-52s %8d B  %s' % (p, items[p]['size'], items[p]['sha'][:8]))
        say('\n[dry-run] 全部 %d 个文件检查通过，站点必需文件齐全。' % len(items))
        say('[dry-run] 旧版「制作包 JSON → CI 重建」工作流与输入已排除；'
            'Actions 只会剩「Deploy GitHub Pages」，不需要 project.json。')
        return 0

    global _LAST_TOKEN
    token = get_token(True)
    _LAST_TOKEN = token
    gh = GitHub(token, args.api_base)

    # 1) 身份
    user, hdrs, _ = gh.call('GET', '/user', want_headers=True)
    login = (user or {}).get('login') or ''
    if not login:
        raise DeployError('Token 有效但没取到用户名，换一个 classic Token 再试。')
    scopes = (hdrs.get('x-oauth-scopes') or hdrs.get('X-OAuth-Scopes') or '')
    # classic token 明确给了 scopes 却没 workflow —— 推 .github/workflows 一定被拒，提前说清
    if scopes.strip() and 'workflow' not in scopes.lower():
        raise DeployError('Token 没勾 workflow，推 .github/workflows/pages.yml 会被 GitHub 拒绝。'
                          '\n到 GitHub → Settings → Developer settings → Personal access tokens '
                          '重新生成，勾上 repo 和 workflow，再跑一次即可（不用登录、不用 git）。')
    owner, repo = resolve_repo(args.repo, login)
    base = api_paths(owner, repo)
    url = site_url(owner, repo)
    say('\n身份：%s   目标仓库：%s/%s' % (login, owner, repo))
    say('上线后：%s' % url)

    # 2) 仓库不存在就建
    r = gh.call('GET', base, allow=(200, 404))
    if r is None:
        say('仓库不存在，正在自动创建…')
        gh.call('POST', '/user/repos', {
            'name': repo, 'private': False, 'auto_init': False,
            'has_issues': False, 'has_projects': False, 'has_wiki': False,
            'description': '行迹 · 行程规划与成片工作台（GitHub Pages 静态站）',
        })
        gh.call('GET', base)
        say('已创建。')

    info = gh.call('GET', base)
    branch = info.get('default_branch') or DEFAULT_BRANCH

    # 3) 拿 HEAD
    ref = gh.call('GET', base + '/git/ref/heads/' + urllib.parse.quote(branch),
                  allow=(200, 404))
    head = (ref or {}).get('object', {}).get('sha') if ref else None
    old = remote_tree(gh, base, head) if head else {}

    changed = [p for p, v in items.items() if old.get(p) != v['sha']]
    # 默认不上传的测试/验收材料：本地不传、远端已有的也原样留着，不误删
    removed = sorted(set(old) - set(items) - set(deferred_paths))
    unchanged = len(items) - len(changed)
    say('\n比对结果：新增/修改 %d · 未变 %d · 远端多余 %d' % (len(changed), unchanged, len(removed)))
    legacy_remote = sorted(p for p in old if is_legacy(p))
    if legacy_remote:
        say('  ⚑ 将清理旧版 CI 残留 %d 项（不需要 project.json 的构建流程已下线）：' % len(legacy_remote))
        for p in legacy_remote[:6]:
            say('      − ' + p)
        if len(legacy_remote) > 6:
            say('      − …另有 %d 个' % (len(legacy_remote) - 6))
    for p in removed[:8]:
        say('  − %s' % p)
    if len(removed) > 8:
        say('  − …另有 %d 个' % (len(removed) - 8))

    if head and not changed and not removed:
        say('\n没有变化，跳过提交（不会触发一次空的 Actions）。')
        _ensure_pages(gh, base, url)
        return 0

    # 4) 只给变化的文件建 blob；本机断点记录让「失败后重跑」不再重复上传
    state = load_state()
    cache = state.setdefault('blobs', {}).setdefault(owner + '/' + repo, {})

    def upload_blobs(force: bool = False, workers: int = WORKERS_DEFAULT):
        """多路并发上传；单个文件失败不再让整站不提交。

        并发一轮 → 失败项降到 1 路低速补传 → 仍失败的按「是否站点必需」分类：
        非必需文件跳过（远端已有版本原样保留），只有必需文件才阻断提交。
        无论走哪条分支都把已成功的 blob 落盘，重跑只补没成功的那几个。
        """
        sha_map, reused, uploaded = {}, 0, 0
        todo = [p for p in changed if p in items]
        # 大文件先走，避免最后几个慢请求拖住整体收尾
        todo.sort(key=lambda p: -items[p]['size'])
        lock = threading.Lock()
        errors, skipped_big = [], []

        def post_one(path, retry_max=0):
            body = {'content': base64.b64encode(items[path]['data']).decode('ascii'),
                    'encoding': 'base64'}
            reply = gh.call('POST', base + '/git/blobs', body, retry_max=retry_max)
            return reply['sha']

        def one(path):
            want = items[path]['sha']
            if not force:
                with lock:
                    if cache.get(path) == want:
                        return path, want, 'reused', ''
            try:
                return path, post_one(path), 'uploaded', ''
            except DeployError as e:
                # 大文件偶发 413/422 不该拖垮整站：跳过它，其余照常上线
                if items[path]['size'] > 1024 * 1024:
                    return path, None, 'skip', str(e)
                return path, None, 'error', str(e)

        def eta_text(sec):
            sec = int(sec)
            return '%d 秒' % sec if sec < 60 else '%d 分 %d 秒' % (sec // 60, sec % 60)

        t0 = time.time()
        last_show = [0.0]

        def show(done, total):
            now = time.time()
            if done < total and now - last_show[0] < 1.2:
                return
            last_show[0] = now
            spent = max(now - t0, 0.001)
            speed = done / spent
            left = (total - done) / speed if speed > 0 else 0
            say('  ↑ 已完成 %d/%d（%.0f%%）· %.0f 个/秒 · 约剩 %s'
                % (done, total, done * 100.0 / max(total, 1), speed, eta_text(left)))

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(one, p) for p in todo]
            for i, fut in enumerate(as_completed(futures), 1):
                path, sha, kind, msg = fut.result()
                if kind == 'reused':
                    reused += 1
                    sha_map[path] = sha
                elif kind == 'uploaded':
                    uploaded += 1
                    sha_map[path] = sha
                    with lock:
                        cache[path] = sha
                elif kind == 'skip':
                    skipped_big.append(path)
                    say('  ⚠ %s 上传被拒，已跳过（不影响其它文件）：%s' % (path, msg))
                else:
                    errors.append((path, msg))
                if i % 200 == 0:
                    with lock:
                        save_state(state)
                show(i, len(todo))

        optional_skipped = list(skipped_big)
        for path in skipped_big:
            items.pop(path, None)

        # 第一轮没成功的：降到 1 路、放慢节奏，单独再试一次（短重试，不空等）
        if errors:
            say('  ⚠ %d 个文件第一次没成功，降到 1 路低速补传；其余 %d 个已就绪'
                % (len(errors), len(todo) - len(errors)))
            gh.slow_down(0.6)
            still = []
            for path, _first in errors:
                try:
                    sha = post_one(path, retry_max=2)
                    sha_map[path] = sha
                    with lock:
                        cache[path] = sha
                    uploaded += 1
                    say('  ✓ 补传成功：%s' % path)
                except DeployError as e:
                    still.append((path, str(e)))
            errors = still

        blocked = []
        for path, msg in errors:
            if is_optional(path):
                optional_skipped.append(path)
                items.pop(path, None)
                say('  ⊘ 跳过非必需文件 %s（站点照常上线）：%s'
                    % (path, msg.splitlines()[0][:110]))
            else:
                blocked.append((path, msg))

        PROGRESS.update(total=len(todo), ready=len(sha_map), uploaded=uploaded,
                        reused=reused, skipped=len(optional_skipped))
        # 异常路径也必须落盘，否则最后一批已传文件在重跑时会被重复上传
        save_state(state)
        if optional_skipped:
            say('  ⊘ 本次跳过 %d 个非必需文件；其余 %d 个照常提交，站点不受影响。'
                % (len(optional_skipped), len(items)))
        if blocked:
            raise DeployError(
                '站点必需文件 %s 上传失败：%s\n'
                '其余 %d 个文件已经就绪并写入本机断点；重跑只补这些必需文件，不用从头再传。'
                % (blocked[0][0], blocked[0][1], len(sha_map)))
        return sha_map, reused, uploaded, optional_skipped

    committed_paths = set()

    def build_tree(sha_map, skipped_paths=()):
        nonlocal committed_paths
        entries = [{'path': p, 'mode': '100644', 'type': 'blob',
                    'sha': sha_map.get(p) or old.get(p) or items[p]['sha']}
                   for p in sorted(items) if not is_legacy(p)]
        have = {e['path'] for e in entries}
        # 跳过的非必需文件：远端已有版本原样保留，别因为一次上传失败把它删掉；
        # 但旧版构建流程残留一律不回填，否则 Actions 里又会多出红色任务。
        for p in skipped_paths:
            if is_legacy(p):
                continue
            if p not in have and p in old:
                entries.append({'path': p, 'mode': '100644', 'type': 'blob', 'sha': old[p]})
                have.add(p)
        entries.sort(key=lambda e: e['path'])
        committed_paths = {e['path'] for e in entries}
        # 第一批不带 base_tree → 远端多余文件不会进最终目录，站点一次提交就干净
        return create_tree_chunked(gh, base, entries)

    workers = resolve_workers(args.workers)
    say('\n⚡ 并发 %d 路同时上传（不是每批 25 个，25 只是旧版的打印节奏）' % workers)
    say('   调快慢：set XJ_WORKERS=8 再双击，或 python deploy.py --workers 8；'
        '遇 429 / 403 限流会自动降速，单个文件失败不再拖垮整站。')
    if not changed:
        say('  ↩ 本次没有要上传的文件（仅清理远端多余条目）。')
    blob_sha, reused, uploaded, optional_skipped = upload_blobs(workers=workers)
    save_state(state)   # 即使后面的建树失败，已上传的文件也已落盘
    if reused:
        say('  ↩ 复用上次已上传文件 %d 个；本次新传 %d 个' % (reused, uploaded))

    keep_remote = tuple(p for p in tuple(optional_skipped) + tuple(deferred_paths)
                        if not is_legacy(p))
    try:
        new_tree = build_tree(blob_sha, keep_remote)
    except DeployError as e:
        # 断点记录里的 blob 万一在远端不可见（换仓库 / 仓库重建），整体重传一次再建树
        if '422' in str(e) and cache:
            say('  ⚠ 上次记录的部分文件在远端不可见，重新上传一次…')
            cache.clear()
            blob_sha, reused, uploaded, optional_skipped = upload_blobs(force=True, workers=workers)
            save_state(state)
            new_tree = build_tree(blob_sha, tuple(p for p in
                                 tuple(optional_skipped) + tuple(deferred_paths)
                                 if not is_legacy(p)))
        else:
            raise

    stamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    msg = 'deploy: 行迹静态站 %s（%d 文件 / +%d -%d）' % (stamp, len(items), len(changed), len(removed))
    payload = {'message': msg, 'tree': new_tree}
    if head:
        payload['parents'] = [head]
    commit = gh.call('POST', base + '/git/commits', payload)['sha']

    update_ref(gh, base, branch, commit, head)
    say('\n已提交：%s（一次提交，只触发一次 Actions）' % msg)

    # 复核：commit 的 tree 就是仓库此刻的完整文件集（不带 base_tree 指向远端旧树），
    # 因此远端残留的构建型 workflow 在这次提交里已经被删除。用本次提交的
    # 文件集做判据，比再查一次远端更可靠——接口短暂延迟不会造成误报。
    extra_wf = sorted(p for p in committed_paths
                      if p.startswith('.github/workflows/')
                      and p.lower().endswith(('.yml', '.yaml'))
                      and p not in ALLOWED_WORKFLOWS)
    if extra_wf:
        say('  ⚠ 本次提交仍带其它工作流，可能触发红色 build：')
        for p in extra_wf[:6]:
            say('      ! ' + p)
    else:
        say('  ✓ 工作流复核通过：本次提交只有 pages.yml，'
            '不会再出现需要 project.json 的 build 任务。')

    _ensure_pages(gh, base, url)

    # 主动触发一次部署，避免 push 事件未触发时站点停在旧版
    try:
        gh.call('POST', base + '/actions/workflows/pages.yml/dispatches',
                {'ref': branch}, allow=(204, 200, 201, 404, 422))
        say('已触发「Deploy GitHub Pages」。')
    except DeployError as e:
        say('（主动触发未成功，push 事件通常已触发部署；可到 Actions 页手动 Run workflow）')
        say('  ' + str(e))

    say('\n完成。等 1–3 分钟后打开：' + url)
    say('   Actions 状态：https://github.com/%s/%s/actions' % (owner, repo))
    say('   以后改完文件，双击 deploy.bat 再跑一次即可；Token 存好就不用再登录。')
    say('   想换仓库名：set GITHUB_REPO=用户名/别的名字  或  python deploy.py --repo 用户名/别的名字')
    return 0


def _ensure_pages(gh: GitHub, base: str, url: str):
    pages = gh.call('GET', base + '/pages', allow=(200, 404))
    body = {'build_type': 'workflow'}
    try:
        if pages:
            gh.call('PUT', base + '/pages', body)
        else:
            gh.call('POST', base + '/pages', body, allow=(200, 201, 204, 409))
        say('Pages Source 已设为 GitHub Actions。')
    except DeployError as e:
        say('Pages Source 自动设置没成功（不影响文件已上传）：' + str(e))
        say('  请到仓库 Settings → Pages → Build and deployment → Source 手动选 GitHub Actions。')
    say('  站点地址：' + url)


def main():
    ap = argparse.ArgumentParser(description='行迹 · 只需 Token 的 GitHub Pages 一键部署')
    ap.add_argument('--repo', default='', help='仓库 owner/name，默认 <用户名>/xingji-studio')
    ap.add_argument('--dry-run', action='store_true', help='只列文件、不联网、不读 Token')
    ap.add_argument('--include-single', action='store_true', help='连单文件预览版一起上传')
    ap.add_argument('--include-tests', action='store_true',
                    help='连 tests/ 与验收材料一起上传（默认不传，站点运行不需要）')
    ap.add_argument('--workers', type=int, default=0,
                    help='并发上传路数，默认 12（也可用 XJ_WORKERS；网络差设 4，好就设 16）')
    ap.add_argument('--api-base', default=os.environ.get('GITHUB_API_BASE', 'https://api.github.com'),
                    help='GitHub API 根地址（受限网络可指向镜像 / 本机桥）')
    args = ap.parse_args()
    try:
        return deploy(args)
    except DeployError as e:
        say('\n✗ ' + redact(str(e), _LAST_TOKEN))
        p = PROGRESS
        if p['total']:
            say('  没有上传任何半成品（分支指针未动，仓库保持原样）；本次已就绪 %d/%d 个文件'
                '（新传 %d · 复用 %d · 跳过 %d），断点已写入 .deploy_state.json。'
                % (p['ready'], p['total'], p['uploaded'], p['reused'], p['skipped']))
            say('  重跑只补没成功的那几个，不会从头再传。')
        else:
            say('  没有上传任何半成品（分支指针未动，仓库保持原样）。')
        say('  若是限流：等 1–2 分钟，或 set XJ_WORKERS=4 再双击 deploy.bat（换 Token 通常没用）。')
        return 1
    except KeyboardInterrupt:
        say('\n已取消。')
        return 130


if __name__ == '__main__':
    sys.exit(main())
