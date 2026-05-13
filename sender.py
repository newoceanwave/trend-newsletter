"""
HTML 대시보드 생성 + 이메일 발송.

대시보드 기능:
- 등록 키워드 칩으로 표시 (제거 가능)
- 검색창에서 새 키워드 추가
- 추천 키워드 칩 클릭으로 한 번에 등록
- 변경사항을 keywords.json 파일로 다운로드 (수동으로 repo에 업로드)
- 등록 키워드 칩 클릭으로 in-page 필터 토글
- 모든 상태는 localStorage에 임시 저장 (다운로드 전 임시 변경 가능)
"""

import os
import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Dict


CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Apple SD Gothic Neo', 'Pretendard', 'Segoe UI', sans-serif;
  background: #f9fafb;
  color: #191f28;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}
.container {
  max-width: 720px;
  margin: 0 auto;
  padding: 32px 20px 80px;
}
.header { margin-bottom: 32px; }
.header-top-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.header-date { font-size: 13px; color: #8b95a1; font-weight: 500; }
.nav-link {
  font-size: 13px;
  color: #3182f6;
  text-decoration: none;
  font-weight: 500;
  padding: 6px 12px;
  border-radius: 8px;
  transition: background 0.15s ease;
}
.nav-link:hover { background: #e8f3ff; }
.header-title { font-size: 28px; font-weight: 700; color: #191f28; margin-bottom: 8px; letter-spacing: -0.02em; }
.header-subtitle { font-size: 15px; color: #4e5968; }

.kw-panel {
  background: #ffffff;
  border: 1px solid #f2f4f6;
  border-radius: 16px;
  padding: 20px 24px;
  margin-bottom: 24px;
}
.kw-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}
.kw-panel-title { font-size: 15px; font-weight: 600; color: #191f28; }
.kw-panel-hint { font-size: 12px; color: #8b95a1; }

.kw-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 14px;
  min-height: 32px;
}
.kw-empty { font-size: 13px; color: #8b95a1; padding: 6px 0; }

.kw-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: #e8f3ff;
  color: #3182f6;
  padding: 6px 6px 6px 12px;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 500;
  border: 1px solid transparent;
  cursor: pointer;
  transition: all 0.15s ease;
  user-select: none;
}
.kw-chip:hover { background: #d3e7ff; }
.kw-chip.active {
  background: #3182f6;
  color: #ffffff;
}
.kw-chip-remove {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: rgba(0,0,0,0.06);
  color: inherit;
  font-size: 14px;
  line-height: 1;
  cursor: pointer;
}
.kw-chip.active .kw-chip-remove { background: rgba(255,255,255,0.25); }
.kw-chip-remove:hover { background: rgba(0,0,0,0.12); }

.kw-add-row {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
.kw-input {
  flex: 1;
  height: 38px;
  padding: 0 14px;
  border: 1px solid #e5e8eb;
  border-radius: 10px;
  font-size: 14px;
  font-family: inherit;
  color: #191f28;
  background: #ffffff;
  outline: none;
  transition: border-color 0.15s ease;
}
.kw-input:focus { border-color: #3182f6; }
.kw-add-btn {
  height: 38px;
  padding: 0 16px;
  background: #191f28;
  color: #ffffff;
  border: none;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s ease;
}
.kw-add-btn:hover { background: #333d4b; }
.kw-add-btn:disabled { background: #d1d6db; cursor: not-allowed; }

.kw-suggested-section {
  margin-top: 12px;
  padding-top: 14px;
  border-top: 1px dashed #e5e8eb;
}
.kw-suggested-label {
  font-size: 12px;
  color: #6b7684;
  margin-bottom: 8px;
  font-weight: 500;
}
.kw-suggested {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.kw-suggest-chip {
  background: #f2f4f6;
  color: #4e5968;
  padding: 5px 12px;
  border-radius: 16px;
  font-size: 12px;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all 0.15s ease;
  user-select: none;
}
.kw-suggest-chip:hover { background: #e5e8eb; color: #191f28; }
.kw-suggest-chip:before { content: "+ "; color: #8b95a1; }

.save-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 12px;
  border-top: 1px dashed #e5e8eb;
  font-size: 12px;
  color: #8b95a1;
}
.save-bar.dirty { color: #c08401; }
.save-btn {
  padding: 8px 14px;
  background: #ffffff;
  color: #191f28;
  border: 1px solid #d1d6db;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}
.save-btn:hover { background: #f9fafb; }
.save-btn:disabled { color: #b0b8c1; cursor: not-allowed; background: #f9fafb; }
.save-help {
  margin-top: 8px;
  font-size: 11px;
  color: #8b95a1;
  line-height: 1.5;
}
.save-help code {
  background: #f2f4f6;
  padding: 1px 6px;
  border-radius: 4px;
  font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono', monospace;
  font-size: 10px;
}

.filter-status {
  margin: 0 0 16px;
  padding: 12px 16px;
  background: #fff5e0;
  color: #c08401;
  border-radius: 10px;
  font-size: 13px;
  display: none;
  align-items: center;
  justify-content: space-between;
}
.filter-status.show { display: flex; }
.filter-clear {
  background: transparent;
  color: #c08401;
  border: 1px solid #c08401;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  font-weight: 500;
}
.filter-clear:hover { background: rgba(192, 132, 1, 0.1); }

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #4e5968;
  margin: 32px 0 16px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.section-title .count {
  background: #f2f4f6;
  color: #6b7684;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 500;
}

.paper-card {
  background: #ffffff;
  border: 1px solid #f2f4f6;
  border-radius: 16px;
  padding: 20px 24px;
  margin-bottom: 12px;
  transition: border-color 0.15s ease;
}
.paper-card:hover { border-color: #d1d6db; }
.paper-card.hidden { display: none; }
.paper-rank {
  display: inline-block;
  width: 24px;
  height: 24px;
  background: #f2f4f6;
  color: #4e5968;
  font-size: 12px;
  font-weight: 600;
  border-radius: 8px;
  text-align: center;
  line-height: 24px;
  margin-bottom: 12px;
}
.paper-title {
  font-size: 17px;
  font-weight: 600;
  color: #191f28;
  margin-bottom: 8px;
  letter-spacing: -0.01em;
  line-height: 1.4;
}
.paper-title a { color: inherit; text-decoration: none; }
.paper-title a:hover { color: #3182f6; }
.paper-summary {
  font-size: 14px;
  color: #4e5968;
  line-height: 1.6;
  margin-bottom: 12px;
}
.paper-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  font-size: 12px;
}
.tag {
  background: #f2f4f6;
  color: #6b7684;
  padding: 4px 10px;
  border-radius: 6px;
  font-weight: 500;
}
.tag.matched { background: #e8f3ff; color: #3182f6; }
.tag.trending { background: #fff5e0; color: #c08401; }
.paper-links { margin-left: auto; display: flex; gap: 12px; }
.paper-links a { color: #6b7684; text-decoration: none; font-size: 12px; font-weight: 500; }
.paper-links a:hover { color: #3182f6; }
.empty {
  background: #ffffff;
  border: 1px solid #f2f4f6;
  border-radius: 16px;
  padding: 40px 24px;
  text-align: center;
  color: #8b95a1;
  font-size: 14px;
}
.footer {
  margin-top: 60px;
  padding-top: 24px;
  border-top: 1px solid #f2f4f6;
  font-size: 12px;
  color: #8b95a1;
  text-align: center;
  line-height: 1.6;
}
"""


def _format_paper_card(paper: Dict, rank: int) -> str:
    title = paper.get("title", "").replace("<", "&lt;").replace(">", "&gt;")
    summary = paper.get("summary_ko", "").replace("<", "&lt;").replace(">", "&gt;")
    arxiv_url = paper.get("arxiv_url", "#")
    pdf_url = paper.get("pdf_url", "#")
    hf_url = paper.get("hf_url", "")
    likes = paper.get("hf_likes", 0)
    matched = paper.get("matched_keywords", [])
    categories = paper.get("categories", [])

    tags_html = ""
    for kw in matched[:3]:
        tags_html += f'<span class="tag matched">{kw}</span>'
    if likes > 0:
        tags_html += f'<span class="tag trending" title="Hugging Face Daily Papers에서 받은 좋아요 수 — ML 연구자들의 큐레이션 신호">🔥 HF {likes}</span>'
    for cat in categories[:2]:
        tags_html += f'<span class="tag">{cat}</span>'

    links = f'<a href="{arxiv_url}" target="_blank">arXiv</a><a href="{pdf_url}" target="_blank">PDF</a>'
    if hf_url:
        links += f'<a href="{hf_url}" target="_blank">HF</a>'

    matched_data = json.dumps([k.lower() for k in matched])

    return f"""
    <div class="paper-card" data-matched='{matched_data}'>
      <div class="paper-rank">{rank}</div>
      <h3 class="paper-title"><a href="{arxiv_url}" target="_blank">{title}</a></h3>
      <p class="paper-summary">{summary}</p>
      <div class="paper-meta">
        {tags_html}
        <div class="paper-links">{links}</div>
      </div>
    </div>
    """


def _build_kw_management_js(initial_keywords: List[str], suggested: List[str]) -> str:
    initial_json = json.dumps(initial_keywords)
    suggested_json = json.dumps(suggested)

    return f"""
(function() {{
  const INITIAL_KEYWORDS = {initial_json};
  const SUGGESTED_KEYWORDS = {suggested_json};
  const STORAGE_KEY = 'trend_newsletter_keywords';
  const PAT_KEY = 'trend_newsletter_github_pat';
  const REPO_KEY = 'trend_newsletter_repo';  // "username/reponame"

  function loadKeywords() {{
    try {{
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) return JSON.parse(stored);
    }} catch (e) {{}}
    return INITIAL_KEYWORDS.slice();
  }}

  function saveKeywords(keywords) {{
    localStorage.setItem(STORAGE_KEY, JSON.stringify(keywords));
  }}

  let keywords = loadKeywords();
  let activeFilters = new Set();

  function isDirty() {{
    const a = keywords.slice().sort().join('|');
    const b = INITIAL_KEYWORDS.slice().sort().join('|');
    return a !== b;
  }}

  async function commitToGitHub() {{
    const pat = localStorage.getItem(PAT_KEY);
    const repo = localStorage.getItem(REPO_KEY);

    if (!pat || !repo) {{
      const wantSetup = confirm('GitHub API 자동 commit을 설정하시겠어요?\\n\\nGitHub Personal Access Token을 한 번만 등록하면, 이후 키워드 추가/제거가 즉시 적용됩니다.\\n\\n계속하시려면 OK, 다운로드로 돌아가려면 Cancel.');
      if (!wantSetup) {{
        downloadKeywords();
        return;
      }}
      const repoInput = prompt('GitHub repo 입력 (형식: 사용자명/repo명)\\n예: newoceanwave/trend-newsletter');
      if (!repoInput) return;
      const patInput = prompt('GitHub Personal Access Token (ghp_... 또는 github_pat_...)\\n\\n생성: https://github.com/settings/tokens?type=beta\\n권한: Contents - Read and write (해당 repo만)');
      if (!patInput) return;
      localStorage.setItem(REPO_KEY, repoInput);
      localStorage.setItem(PAT_KEY, patInput);
      alert('설정 완료! 다시 시도합니다.');
      return commitToGitHub();
    }}

    const btn = document.getElementById('save-btn');
    btn.disabled = true;
    btn.textContent = '커밋 중...';

    try {{
      const newContent = JSON.stringify({{
        keywords: keywords,
        updated_at: new Date().toISOString().split('T')[0]
      }}, null, 2);

      // 1. 기존 파일 sha 가져오기 (있으면)
      let sha = null;
      try {{
        const getResp = await fetch(`https://api.github.com/repos/${{repo}}/contents/keywords.json`, {{
          headers: {{ 'Authorization': `Bearer ${{pat}}`, 'Accept': 'application/vnd.github+json' }}
        }});
        if (getResp.ok) {{
          const data = await getResp.json();
          sha = data.sha;
        }}
      }} catch (e) {{}}

      // 2. PUT (생성 또는 업데이트)
      const putBody = {{
        message: `Update keywords (${{keywords.length}} keywords)`,
        content: btoa(unescape(encodeURIComponent(newContent))),
      }};
      if (sha) putBody.sha = sha;

      const putResp = await fetch(`https://api.github.com/repos/${{repo}}/contents/keywords.json`, {{
        method: 'PUT',
        headers: {{
          'Authorization': `Bearer ${{pat}}`,
          'Accept': 'application/vnd.github+json',
          'Content-Type': 'application/json'
        }},
        body: JSON.stringify(putBody)
      }});

      if (!putResp.ok) {{
        const err = await putResp.json();
        throw new Error(err.message || 'API 호출 실패');
      }}

      // 3. workflow_dispatch 트리거 (즉시 실행)
      const triggerResp = await fetch(`https://api.github.com/repos/${{repo}}/actions/workflows/daily.yml/dispatches`, {{
        method: 'POST',
        headers: {{
          'Authorization': `Bearer ${{pat}}`,
          'Accept': 'application/vnd.github+json',
          'Content-Type': 'application/json'
        }},
        body: JSON.stringify({{ ref: 'main' }})
      }});

      if (triggerResp.ok) {{
        alert('✅ 키워드 업데이트 완료!\\n\\nGitHub Actions가 자동 실행됩니다 (2-3분 후 새 데이터 반영). Actions 탭에서 진행 확인 가능.');
      }} else {{
        alert('✅ keywords.json 업데이트 완료!\\n\\n⚠️ 자동 실행 실패. Actions 탭에서 수동으로 "Run workflow" 클릭하세요.');
      }}

      // INITIAL_KEYWORDS 업데이트해서 dirty 상태 해제
      INITIAL_KEYWORDS.length = 0;
      INITIAL_KEYWORDS.push(...keywords);
      render();
    }} catch (e) {{
      alert('❌ 실패: ' + e.message + '\\n\\n토큰 권한 확인하거나, 파일로 다운로드 후 수동 업로드해주세요.');
      console.error(e);
    }} finally {{
      btn.disabled = false;
      btn.textContent = '키워드 즉시 적용';
    }}
  }}

  function downloadKeywords() {{
    const data = {{
      keywords: keywords,
      updated_at: new Date().toISOString().split('T')[0]
    }};
    const blob = new Blob([JSON.stringify(data, null, 2)], {{ type: 'application/json' }});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'keywords.json';
    a.click();
    URL.revokeObjectURL(url);
  }}

  function render() {{
    const list = document.getElementById('kw-list');
    const suggBox = document.getElementById('kw-suggested');
    const saveBar = document.getElementById('save-bar');
    const dirtyMsg = document.getElementById('dirty-msg');
    const saveBtn = document.getElementById('save-btn');

    list.innerHTML = '';
    if (keywords.length === 0) {{
      list.innerHTML = '<div class="kw-empty">아직 등록된 키워드가 없어요. 아래에서 추가해보세요.</div>';
    }} else {{
      keywords.forEach(kw => {{
        const chip = document.createElement('span');
        chip.className = 'kw-chip' + (activeFilters.has(kw.toLowerCase()) ? ' active' : '');
        chip.innerHTML = kw + '<span class="kw-chip-remove" title="제거">&times;</span>';

        chip.addEventListener('click', (e) => {{
          if (e.target.classList.contains('kw-chip-remove')) {{
            keywords = keywords.filter(k => k !== kw);
            activeFilters.delete(kw.toLowerCase());
            saveKeywords(keywords);
            render();
            applyFilter();
          }} else {{
            const lo = kw.toLowerCase();
            if (activeFilters.has(lo)) activeFilters.delete(lo);
            else activeFilters.add(lo);
            render();
            applyFilter();
          }}
        }});
        list.appendChild(chip);
      }});
    }}

    suggBox.innerHTML = '';
    const notRegistered = SUGGESTED_KEYWORDS.filter(
      kw => !keywords.map(k => k.toLowerCase()).includes(kw.toLowerCase())
    );
    if (notRegistered.length === 0) {{
      document.getElementById('kw-suggested-section').style.display = 'none';
    }} else {{
      document.getElementById('kw-suggested-section').style.display = 'block';
      notRegistered.forEach(kw => {{
        const chip = document.createElement('span');
        chip.className = 'kw-suggest-chip';
        chip.textContent = kw;
        chip.addEventListener('click', () => {{
          if (!keywords.map(k => k.toLowerCase()).includes(kw.toLowerCase())) {{
            keywords.push(kw);
            saveKeywords(keywords);
            render();
          }}
        }});
        suggBox.appendChild(chip);
      }});
    }}

    if (isDirty()) {{
      saveBar.classList.add('dirty');
      dirtyMsg.textContent = '변경됨 — 즉시 적용 또는 다운로드';
      saveBtn.disabled = false;
    }} else {{
      saveBar.classList.remove('dirty');
      dirtyMsg.textContent = '변경 없음';
      saveBtn.disabled = true;
    }}
  }}

  function applyFilter() {{
    const filterStatus = document.getElementById('filter-status');
    const filterLabel = document.getElementById('filter-label');
    const cards = document.querySelectorAll('.paper-card');
    let visibleCount = 0;

    if (activeFilters.size === 0) {{
      cards.forEach(c => c.classList.remove('hidden'));
      filterStatus.classList.remove('show');
      return;
    }}

    cards.forEach(card => {{
      const matched = JSON.parse(card.dataset.matched || '[]');
      const hasOverlap = matched.some(m => activeFilters.has(m.toLowerCase()));
      if (hasOverlap) {{
        card.classList.remove('hidden');
        visibleCount++;
      }} else {{
        card.classList.add('hidden');
      }}
    }});

    const filterArr = Array.from(activeFilters);
    filterLabel.textContent = filterArr.join(', ') + ' 필터 적용 중 — ' + visibleCount + '편 표시';
    filterStatus.classList.add('show');
  }}

  function addKeyword() {{
    const input = document.getElementById('kw-input');
    const value = input.value.trim();
    if (!value) return;
    if (!keywords.map(k => k.toLowerCase()).includes(value.toLowerCase())) {{
      keywords.push(value);
      saveKeywords(keywords);
      render();
    }}
    input.value = '';
    input.focus();
  }}

  function clearFilters() {{
    activeFilters.clear();
    render();
    applyFilter();
  }}

  document.addEventListener('DOMContentLoaded', () => {{
    document.getElementById('kw-add-btn').addEventListener('click', addKeyword);
    document.getElementById('kw-input').addEventListener('keydown', (e) => {{
      if (e.key === 'Enter') addKeyword();
    }});
    document.getElementById('save-btn').addEventListener('click', commitToGitHub);
    document.getElementById('save-btn-download').addEventListener('click', downloadKeywords);
    document.getElementById('filter-clear').addEventListener('click', clearFilters);
    render();
  }});
}})();
"""


def generate_dashboard_html(papers, date_str, user_keywords, suggested_keywords=None):
    suggested_keywords = suggested_keywords or []
    has_papers = bool(papers)

    if has_papers:
        cards_html = "\n".join(
            _format_paper_card(p, i + 1) for i, p in enumerate(papers)
        )
        papers_html = f'<div class="section-title">오늘의 추천 <span class="count">{len(papers)}</span></div>{cards_html}'
    else:
        papers_html = '<div class="empty">오늘은 키워드에 매칭되는 논문이 없어요.<br>키워드를 더 추가하거나 범위를 넓혀보세요.</div>'

    js_code = _build_kw_management_js(user_keywords, suggested_keywords)

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI 트렌드 뉴스레터 — {date_str}</title>
  <style>{CSS}</style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="header-top-row">
        <div class="header-date">{date_str}</div>
        <a href="trending.html" class="nav-link">온라인 트렌딩 →</a>
      </div>
      <h1 class="header-title">AI 트렌드 뉴스레터</h1>
      <p class="header-subtitle">arXiv + Hugging Face Daily Papers에서 어제자 큐레이션</p>
    </div>

    <div class="kw-panel">
      <div class="kw-panel-header">
        <div class="kw-panel-title">내 키워드</div>
        <div class="kw-panel-hint">클릭해서 필터 · ×로 제거</div>
      </div>

      <div class="kw-list" id="kw-list"></div>

      <div class="kw-add-row">
        <input type="text" class="kw-input" id="kw-input" placeholder="키워드 추가 (예: diffusion model)" />
        <button class="kw-add-btn" id="kw-add-btn">추가</button>
      </div>

      <div class="kw-suggested-section" id="kw-suggested-section">
        <div class="kw-suggested-label">추천 키워드 (오늘 자주 등장)</div>
        <div class="kw-suggested" id="kw-suggested"></div>
      </div>

      <div class="save-bar" id="save-bar">
        <span id="dirty-msg">변경 없음</span>
        <div style="display:flex;gap:6px">
          <button class="save-btn" id="save-btn-download" title="파일로 다운로드 (수동 업로드)">📥 파일</button>
          <button class="save-btn" id="save-btn" disabled style="background:#3182f6;color:#fff;border-color:#3182f6">키워드 즉시 적용</button>
        </div>
      </div>
      <div class="save-help">
        <strong>즉시 적용</strong>: GitHub API로 자동 commit + workflow 실행 (PAT 1회 등록). <strong>파일</strong>: 수동 업로드용 다운로드.
      </div>
    </div>

    <div class="filter-status" id="filter-status">
      <span id="filter-label"></span>
      <button class="filter-clear" id="filter-clear">필터 해제</button>
    </div>

    {papers_html}

    <div class="footer">
      <strong>출처:</strong> arXiv (cs.LG, cs.IR, cs.DB, cs.CL, cs.AI) · Hugging Face Daily Papers<br>
      Generated by trend-newsletter
    </div>
  </div>
  <script>{js_code}</script>
</body>
</html>
"""


def save_dashboard(papers, date_str, user_keywords, suggested_keywords, output_dir):
    html = generate_dashboard_html(papers, date_str, user_keywords, suggested_keywords)

    posts_dir = os.path.join(output_dir, "posts")
    os.makedirs(posts_dir, exist_ok=True)

    daily_path = os.path.join(posts_dir, f"{date_str}.html")
    with open(daily_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  ✓ {daily_path}")

    update_index(output_dir, date_str, papers, user_keywords, suggested_keywords)


def update_index(output_dir, latest_date, papers, user_keywords, suggested_keywords):
    posts_dir = os.path.join(output_dir, "posts")
    files = sorted(
        [f for f in os.listdir(posts_dir) if f.endswith(".html")],
        reverse=True,
    )

    archive_links = "\n".join(
        '<li style="padding:6px 0"><a href="posts/' + f + '" style="color:#3182f6;text-decoration:none">' + f.replace(".html", "") + '</a></li>'
        for f in files[:30]
    )

    latest_html = generate_dashboard_html(papers, latest_date, user_keywords, suggested_keywords)

    archive_section = f"""
    <div class="section-title" style="margin-top:48px">아카이브</div>
    <div class="paper-card">
      <ul style="list-style:none;padding:0;margin:0">{archive_links}</ul>
    </div>
    """
    latest_with_archive = latest_html.replace(
        '<div class="footer">',
        archive_section + '<div class="footer">',
    )

    index_path = os.path.join(output_dir, "index.html")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(latest_with_archive)
    print(f"  ✓ {index_path}")


def generate_trending_html(trending: Dict, date_str: str,
                            rank_changes: Dict = None,
                            aggregate: List[Dict] = None,
                            user_keywords: List[str] = None) -> str:
    """
    온라인 트렌딩 키워드 페이지.
    4개 섹션: 종합 / arXiv / HF / PwC.
    각 키워드에 등록 버튼 + 순위 변화 (▲ ▼) 표시.
    """
    rank_changes = rank_changes or {"arxiv": {}, "hf": {}, "pwc": {}}
    user_keywords = user_keywords or []
    user_kw_lower = set(k.lower() for k in user_keywords)

    def format_change(change):
        """순위 변화를 HTML로."""
        if change == "new":
            return '<span class="change-new">NEW</span>'
        if change == 0 or change is None:
            return '<span class="change-flat">–</span>'
        if change > 0:
            return f'<span class="change-up">▲{change}</span>'
        return f'<span class="change-down">▼{abs(change)}</span>'

    def format_register_btn(kw):
        """키워드 등록 버튼."""
        if kw.lower() in user_kw_lower:
            return f'<span class="kw-registered" title="이미 등록됨">✓</span>'
        return f'<button class="kw-register" data-kw="{kw}" title="내 키워드에 추가">＋</button>'

    def format_paper(p):
        title = p.get("title", "").replace("<", "&lt;").replace(">", "&gt;")
        title_ko = p.get("title_ko", "").replace("<", "&lt;").replace(">", "&gt;")
        abs_text = p.get("abstract", "")[:240].replace("<", "&lt;").replace(">", "&gt;")
        if len(p.get("abstract", "")) > 240:
            abs_text += "..."
        abstract_ko = p.get("abstract_ko", "").replace("<", "&lt;").replace(">", "&gt;")
        arxiv_url = p.get("arxiv_url", "#")
        likes = p.get("likes", 0)
        likes_badge = f'<span class="paper-likes" title="Hugging Face Daily Papers에서 받은 좋아요 수">🔥 HF {likes}</span>' if likes > 0 else ""

        # 한국어 번역이 있으면 함께 표시
        title_ko_html = f'<div class="trend-paper-title-ko">{title_ko}</div>' if title_ko else ""
        abstract_ko_html = f'<p class="trend-paper-abs-ko">{abstract_ko}</p>' if abstract_ko else ""

        return f"""
        <div class="trend-paper">
          <a href="{arxiv_url}" target="_blank" class="trend-paper-title">{title}</a>
          {likes_badge}
          {title_ko_html}
          <p class="trend-paper-abs">{abs_text}</p>
          {abstract_ko_html}
        </div>
        """

    def format_row(kw_data, idx, src_key, show_sources=False):
        kw = kw_data["keyword"]
        count = kw_data.get("paper_count", len(kw_data.get("papers", [])))
        max_score = format_row._cur_max  # 외부에서 set

        if show_sources:
            scores = kw_data.get("scores", {})
            score_display = f'<span class="trend-source-mini">A {int(scores.get("arxiv", 0))}</span><span class="trend-source-mini">H {int(scores.get("hf", 0))}</span><span class="trend-source-mini">P {int(scores.get("pwc", 0))}</span>'
            bar_pct = max(15, int((kw_data.get("aggregate_score", 0) / max_score) * 100))
        else:
            score_display = f'<span class="trend-count">{count}편</span>'
            bar_pct = max(15, int((kw_data.get("score", 0) / max_score) * 100))

        change = rank_changes.get(src_key, {}).get(kw) if not show_sources else None
        change_html = format_change(change) if change is not None else ""

        papers_html = "".join(format_paper(p) for p in kw_data.get("papers", [])[:10])
        if not papers_html:
            papers_html = '<div class="trend-paper" style="color:#8b95a1;font-size:13px">관련 논문 미수집</div>'

        return f"""
        <div class="trend-row">
          <div class="trend-row-head" data-target="papers-{src_key}-{idx}">
            <div class="trend-row-left">
              <span class="trend-rank">{idx + 1}</span>
              {change_html}
              <span class="trend-kw">{kw}</span>
            </div>
            <div class="trend-row-right">
              {score_display}
              <span class="trend-bar"><span class="trend-bar-fill" style="width: {bar_pct}%"></span></span>
              {format_register_btn(kw)}
              <span class="trend-toggle">▾</span>
            </div>
          </div>
          <div class="trend-papers" id="papers-{src_key}-{idx}">
            {papers_html}
          </div>
        </div>
        """

    sections_html = ""

    # 종합 탭 (aggregate)
    if aggregate:
        max_agg = max((k["aggregate_score"] for k in aggregate), default=1.0)
        format_row._cur_max = max_agg
        rows = "".join(format_row(k, i, "agg", show_sources=True) for i, k in enumerate(aggregate))
        sections_html += f"""
        <div class="trend-section" id="section-agg">
          <div class="trend-section-header">
            <h2 class="trend-section-title">종합 ranking</h2>
            <p class="trend-section-desc">3개 출처 점수를 정규화해서 평균 · 여러 출처에서 등장하면 가중치 +</p>
            <div class="trend-legend">
              <span class="trend-source-mini">A</span> arXiv 7일
              <span class="trend-source-mini">H</span> Hugging Face
              <span class="trend-source-mini">P</span> Papers with Code
            </div>
          </div>
          <div class="trend-list">{rows}</div>
        </div>
        """

    # 출처별 섹션
    sources = [
        ("arxiv", "arXiv 최근 7일", "submission 빈도 — 학계 활동 그 자체"),
        ("hf", "Hugging Face Daily", "전문가 큐레이션 + likes — 신호 강도 높음"),
        ("pwc", "Papers with Code", "코드 공개된 — 재현 가능성 신호"),
    ]
    for src_key, src_label, src_desc in sources:
        keywords = trending.get(src_key, [])
        if not keywords:
            sections_html += f"""
            <div class="trend-section" id="section-{src_key}">
              <div class="trend-section-header">
                <h2 class="trend-section-title">{src_label}</h2>
                <p class="trend-section-desc">{src_desc}</p>
              </div>
              <div class="empty">데이터를 가져오지 못했습니다.</div>
            </div>
            """
            continue

        max_score = max((k["score"] for k in keywords), default=1.0)
        format_row._cur_max = max_score
        rows = "".join(format_row(k, i, src_key) for i, k in enumerate(keywords))
        sections_html += f"""
        <div class="trend-section" id="section-{src_key}">
          <div class="trend-section-header">
            <h2 class="trend-section-title">{src_label}</h2>
            <p class="trend-section-desc">{src_desc}</p>
          </div>
          <div class="trend-list">{rows}</div>
        </div>
        """

    extra_css = """
    .trend-section { margin-bottom: 40px; }
    .trend-section-header { margin-bottom: 16px; }
    .trend-section-title { font-size: 18px; font-weight: 700; color: #191f28; margin-bottom: 4px; letter-spacing: -0.01em; }
    .trend-section-desc { font-size: 13px; color: #8b95a1; }
    .trend-legend { font-size: 11px; color: #8b95a1; margin-top: 8px; display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
    .trend-list { background: #ffffff; border: 1px solid #f2f4f6; border-radius: 16px; overflow: hidden; }
    .trend-row { border-bottom: 1px solid #f2f4f6; }
    .trend-row:last-child { border-bottom: none; }
    .trend-row-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 12px 20px;
      cursor: pointer;
      transition: background 0.15s ease;
      gap: 12px;
    }
    .trend-row-head:hover { background: #f9fafb; }
    .trend-row-left { display: flex; align-items: center; gap: 12px; flex: 1; min-width: 0; }
    .trend-row-right { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
    .trend-rank {
      display: inline-block;
      width: 22px;
      height: 22px;
      background: #f2f4f6;
      color: #6b7684;
      font-size: 11px;
      font-weight: 600;
      border-radius: 6px;
      text-align: center;
      line-height: 22px;
      flex-shrink: 0;
    }
    .trend-kw { font-size: 14px; font-weight: 600; color: #191f28; }
    .trend-count { font-size: 12px; color: #8b95a1; min-width: 32px; text-align: right; }
    .trend-source-mini {
      display: inline-block;
      font-size: 10px;
      color: #6b7684;
      background: #f2f4f6;
      padding: 2px 6px;
      border-radius: 4px;
      font-weight: 500;
      letter-spacing: 0.3px;
    }
    .trend-bar {
      display: inline-block;
      width: 60px;
      height: 6px;
      background: #f2f4f6;
      border-radius: 3px;
      overflow: hidden;
    }
    .trend-bar-fill { display: block; height: 100%; background: #3182f6; border-radius: 3px; }
    .trend-toggle { color: #8b95a1; font-size: 12px; transition: transform 0.2s ease; }
    .trend-row.open .trend-toggle { transform: rotate(180deg); }
    .trend-papers { max-height: 0; overflow: hidden; transition: max-height 0.3s ease; background: #f9fafb; }
    .trend-row.open .trend-papers { max-height: 2500px; }
    .trend-paper { padding: 12px 20px 14px; border-top: 1px solid #f2f4f6; }
    .trend-paper-title { font-size: 14px; font-weight: 600; color: #191f28; text-decoration: none; display: inline-block; margin-bottom: 6px; }
    .trend-paper-title:hover { color: #3182f6; }
    .trend-paper-title-ko {
      font-size: 13px;
      color: #3182f6;
      margin-bottom: 8px;
      line-height: 1.4;
      font-weight: 500;
    }
    .paper-likes { display: inline-block; background: #fff5e0; color: #c08401; padding: 2px 8px; border-radius: 6px; font-size: 11px; font-weight: 500; margin-left: 8px; vertical-align: middle; }
    .trend-paper-abs { font-size: 13px; color: #4e5968; line-height: 1.6; margin: 0; }
    .trend-paper-abs-ko {
      font-size: 13px;
      color: #6b7684;
      line-height: 1.6;
      margin: 6px 0 0 0;
      padding: 8px 12px;
      background: #f2f4f6;
      border-radius: 8px;
    }
    .change-up { color: #f04452; font-size: 11px; font-weight: 600; }
    .change-down { color: #3182f6; font-size: 11px; font-weight: 600; }
    .change-flat { color: #d1d6db; font-size: 11px; font-weight: 600; }
    .change-new { color: #f7931a; font-size: 10px; font-weight: 700; background: #fff5e0; padding: 2px 6px; border-radius: 4px; letter-spacing: 0.5px; }
    .kw-register {
      width: 24px;
      height: 24px;
      border-radius: 6px;
      border: 1px solid #d1d6db;
      background: #ffffff;
      color: #4e5968;
      font-size: 14px;
      font-weight: 500;
      cursor: pointer;
      transition: all 0.15s ease;
      padding: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }
    .kw-register:hover { background: #3182f6; color: #ffffff; border-color: #3182f6; }
    .kw-register.added { background: #00c896; color: #ffffff; border-color: #00c896; cursor: default; }
    .kw-registered {
      width: 24px;
      height: 24px;
      border-radius: 6px;
      background: #00c896;
      color: #ffffff;
      font-size: 12px;
      font-weight: 700;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }
    .trend-tabs {
      display: flex;
      gap: 4px;
      margin-bottom: 24px;
      border-bottom: 1px solid #f2f4f6;
    }
    .trend-tab {
      padding: 10px 16px;
      background: transparent;
      border: none;
      color: #8b95a1;
      font-size: 14px;
      font-weight: 500;
      cursor: pointer;
      border-bottom: 2px solid transparent;
      transition: all 0.15s ease;
      font-family: inherit;
    }
    .trend-tab:hover { color: #4e5968; }
    .trend-tab.active {
      color: #191f28;
      border-bottom-color: #191f28;
      font-weight: 600;
    }
    .trend-section { display: none; }
    .trend-section.active { display: block; }

    .save-floating {
      margin-top: 24px;
      padding: 14px 18px;
      background: #fff5e0;
      border-radius: 12px;
      display: none;
      align-items: center;
      justify-content: space-between;
      font-size: 13px;
      color: #c08401;
    }
    .save-floating.show { display: flex; }
    .save-floating-btn {
      padding: 8px 14px;
      background: #c08401;
      color: #ffffff;
      border: none;
      border-radius: 8px;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
    }
    .save-floating-btn:hover { background: #a87000; }
    """

    initial_kw_json = json.dumps(user_keywords)
    trending_js = f"""
    (function() {{
      const STORAGE_KEY = 'trend_newsletter_keywords';
      const INITIAL_KEYWORDS = {initial_kw_json};

      function loadKeywords() {{
        try {{
          const stored = localStorage.getItem(STORAGE_KEY);
          if (stored) return JSON.parse(stored);
        }} catch (e) {{}}
        return INITIAL_KEYWORDS.slice();
      }}
      function saveKeywords(kws) {{ localStorage.setItem(STORAGE_KEY, JSON.stringify(kws)); }}
      function isDirty(kws) {{
        return kws.slice().sort().join('|') !== INITIAL_KEYWORDS.slice().sort().join('|');
      }}

      let keywords = loadKeywords();

      function refreshSaveBar() {{
        const bar = document.getElementById('save-floating');
        if (isDirty(keywords)) bar.classList.add('show');
        else bar.classList.remove('show');
      }}

      document.addEventListener('DOMContentLoaded', () => {{
        document.querySelectorAll('.trend-row-head').forEach(head => {{
          head.addEventListener('click', (e) => {{
            if (e.target.closest('.kw-register')) return;
            const row = head.closest('.trend-row');
            row.classList.toggle('open');
          }});
        }});

        document.querySelectorAll('.kw-register').forEach(btn => {{
          btn.addEventListener('click', (e) => {{
            e.stopPropagation();
            const kw = btn.dataset.kw;
            if (!keywords.map(k => k.toLowerCase()).includes(kw.toLowerCase())) {{
              keywords.push(kw);
              saveKeywords(keywords);
            }}
            btn.classList.add('added');
            btn.textContent = '✓';
            btn.disabled = true;
            refreshSaveBar();
          }});
        }});

        document.querySelectorAll('.trend-tab').forEach(tab => {{
          tab.addEventListener('click', () => {{
            const target = tab.dataset.tab;
            document.querySelectorAll('.trend-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            document.querySelectorAll('.trend-section').forEach(s => s.classList.remove('active'));
            document.getElementById('section-' + target).classList.add('active');
          }});
        }});

        document.getElementById('save-floating-btn').addEventListener('click', () => {{
          const data = {{
            keywords: keywords,
            updated_at: new Date().toISOString().split('T')[0]
          }};
          const blob = new Blob([JSON.stringify(data, null, 2)], {{ type: 'application/json' }});
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = 'keywords.json';
          a.click();
          URL.revokeObjectURL(url);
        }});

        refreshSaveBar();
      }});
    }})();
    """

    # 탭 (agg가 있을 때만)
    tabs_html = ""
    if aggregate:
        tabs_html += '<button class="trend-tab active" data-tab="agg">종합</button>'
    first_src_tab = not aggregate  # agg 없으면 arxiv가 첫 탭
    for src_key, src_label, _ in sources:
        cls = "active" if first_src_tab else ""
        first_src_tab = False
        tabs_html += f'<button class="trend-tab {cls}" data-tab="{src_key}">{src_label}</button>'

    # 초기 active 섹션: aggregate 있으면 agg, 없으면 arxiv
    initial_active = "agg" if aggregate else "arxiv"

    return _render_trending_page(date_str, tabs_html, sections_html, aggregate, sources, extra_css, trending_js, initial_active)


def _render_trending_page(date_str, tabs_html, sections_html, aggregate, sources, extra_css, trending_js, initial_active):
    """trending 페이지의 최종 HTML 조립. 섹션 id 부여 + active 클래스 설정."""
    # agg 섹션에 active 적용
    if aggregate and initial_active == "agg":
        sections_html = sections_html.replace(
            '<div class="trend-section" id="section-agg">',
            '<div class="trend-section active" id="section-agg">',
            1,
        )

    # 출처별 섹션에 active 적용
    for src_key, _, _ in sources:
        if src_key == initial_active:
            sections_html = sections_html.replace(
                f'<div class="trend-section" id="section-{src_key}">',
                f'<div class="trend-section active" id="section-{src_key}">',
                1,
            )

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>온라인 트렌딩 — AI 트렌드 뉴스레터</title>
  <style>{CSS}{extra_css}</style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="header-top-row">
        <div class="header-date">수집: {date_str}</div>
        <a href="index.html" class="nav-link">← 내 키워드</a>
      </div>
      <h1 class="header-title">온라인 트렌딩</h1>
      <p class="header-subtitle">전 세계 학계에서 지금 자주 언급되는 키워드 · ▲▼는 어제 대비 순위 변화</p>
    </div>

    <div class="trend-tabs">{tabs_html}</div>

    {sections_html}

    <div class="save-floating" id="save-floating">
      <span>키워드가 추가됐어요 — 다운로드해서 repo에 업로드하면 다음 실행부터 적용됩니다</span>
      <button class="save-floating-btn" id="save-floating-btn">keywords.json 다운로드</button>
    </div>

    <div class="footer" style="margin-top:40px">
      <strong>출처:</strong> arXiv 최근 7일 · Hugging Face Daily Papers · Papers with Code trending<br>
      ＋ 버튼으로 키워드 등록 · 클릭하면 관련 논문 펼쳐짐
    </div>
  </div>
  <script>{trending_js}</script>
</body>
</html>
"""


def save_trending_page(trending: Dict, date_str: str, output_dir: str,
                       rank_changes: Dict = None,
                       aggregate: List[Dict] = None,
                       user_keywords: List[str] = None):
    """trending.html 저장."""
    html = generate_trending_html(trending, date_str, rank_changes, aggregate, user_keywords)
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, "trending.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  ✓ {path}")


def generate_email_html(papers, date_str, user_keywords):
    if papers:
        cards = "\n".join(_format_paper_card(p, i + 1) for i, p in enumerate(papers))
        body = f'<div class="section-title">오늘의 추천 <span class="count">{len(papers)}</span></div>{cards}'
    else:
        body = '<div class="empty">오늘은 매칭되는 논문이 없어요.</div>'

    kw_text = ", ".join(user_keywords) if user_keywords else "(설정 안 됨)"

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <title>AI 트렌드 — {date_str}</title>
  <style>{CSS}</style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="header-date">{date_str}</div>
      <h1 class="header-title">AI 트렌드 뉴스레터</h1>
      <p class="header-subtitle">arXiv + Hugging Face Daily Papers에서 어제자 큐레이션</p>
    </div>
    {body}
    <div class="footer">
      <strong>키워드:</strong> {kw_text}<br>
      <strong>출처:</strong> arXiv · Hugging Face Daily Papers
    </div>
  </div>
</body>
</html>
"""


def send_email(papers, date_str, user_keywords, suggested_keywords, email_config):
    if not email_config.get("enabled"):
        print("  ℹ 이메일 발송 비활성화 (config)")
        return

    password = os.environ.get("EMAIL_PASSWORD")
    if not password:
        print("  ⚠ EMAIL_PASSWORD 환경변수 없음 — 이메일 발송 건너뜀")
        return

    sender = email_config["sender"]
    recipient = email_config["recipient"]

    html = generate_email_html(papers, date_str, user_keywords)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"AI 트렌드 — {date_str} ({len(papers)}편)"
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        with smtplib.SMTP(email_config["smtp_host"], email_config["smtp_port"]) as server:
            server.starttls()
            server.login(sender, password)
            server.send_message(msg)
        print(f"  ✓ 이메일 발송 → {recipient}")
    except Exception as e:
        print(f"  ✗ 이메일 발송 실패: {e}")