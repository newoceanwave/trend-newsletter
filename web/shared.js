// ============================================
// shared.js — 모든 페이지가 공통으로 쓰는 코드
// Supabase 연결 + 로그인 상태 관리 + 공통 헬퍼
// ============================================

// ====== 본인 Supabase 값으로 채우세요 ======
const SUPABASE_URL = 'https://hgdpszpdszectdjtdpsb.supabase.co';
const SUPABASE_KEY = 'sb_publishable_LpJLL61i24FoB6V__a5-1g_F9qgvXhQ';
// ==========================================

// Supabase 클라이언트 (라이브러리의 window.supabase와 이름 충돌 피하려고 supabaseClient)
const supabaseClient = window.supabase.createClient(SUPABASE_URL, SUPABASE_KEY);

// ---- 현재 로그인 세션 가져오기 ----
async function getSession() {
  const { data: { session }, error } = await supabaseClient.auth.getSession();
  if (error) {
    console.error('세션 확인 에러:', error);
    return null;
  }
  return session;
}

// ---- 로그인 필수 페이지에서 호출: 로그인 안 됐으면 index로 보냄 ----
async function requireAuth() {
  const session = await getSession();
  if (!session) {
    window.location.href = 'index.html';
    return null;
  }
  return session;
}

// ---- 구글 로그인 시작 ----
async function loginWithGoogle(redirectPage) {
  const redirectTo = new URL(redirectPage || 'dashboard.html', window.location.href).href;
  const { error } = await supabaseClient.auth.signInWithOAuth({
    provider: 'google',
    options: { redirectTo }
  });
  if (error) alert('로그인 실패: ' + error.message);
}

// ---- 로그아웃 ----
async function logout() {
  await supabaseClient.auth.signOut();
  window.location.href = 'index.html';
}

// ---- 공통 헤더 렌더링 (로그인한 페이지 상단) ----
// containerId: 헤더를 넣을 div의 id
// active: 현재 페이지 ('dashboard' | 'trending' | 'search' | 'settings' | 'bookmarks')
async function renderHeader(containerId, active) {
  const session = await getSession();
  const container = document.getElementById(containerId);
  if (!container) return;

  const userName = session?.user?.user_metadata?.full_name
    || session?.user?.email
    || '사용자';

  const navItems = [
    { id: 'dashboard', label: '대시보드', href: 'dashboard.html' },
    { id: 'trending', label: '온라인 트렌딩', href: 'trending.html' },
    { id: 'conferences', label: '학회', href: 'conferences.html' },
    { id: 'search', label: '논문 검색', href: 'search.html' },
    { id: 'bookmarks', label: '북마크', href: 'bookmarks.html' },
    { id: 'settings', label: '설정', href: 'settings.html' },
  ];

  const navHtml = navItems.map(item =>
    '<a href="' + item.href + '" class="nav-item' +
    (item.id === active ? ' active' : '') + '">' + item.label + '</a>'
  ).join('');

  container.innerHTML =
    '<div class="topbar">' +
      '<div class="topbar-inner">' +
        '<div class="topbar-row1">' +
          '<a href="dashboard.html" class="topbar-brand">AI 트렌드 뉴스레터</a>' +
          '<div class="topbar-user">' +
            '<span class="topbar-username">' + escapeHtml(userName) + '</span>' +
            '<button class="topbar-logout" id="__logout_btn">로그아웃</button>' +
          '</div>' +
        '</div>' +
        '<nav class="topbar-nav">' + navHtml + '</nav>' +
      '</div>' +
    '</div>';

  document.getElementById('__logout_btn').addEventListener('click', logout);
}

// ---- HTML 이스케이프 (XSS 방지) ----
function escapeHtml(s) {
  return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// ---- 공통 헤더 CSS (각 페이지가 이 문자열을 <style>에 넣음) ----
const SHARED_HEADER_CSS = `
.topbar {
  background: #fff;
  border-bottom: 1px solid #f2f4f6;
  position: sticky;
  top: 0;
  z-index: 100;
}
.topbar-inner {
  max-width: 960px;
  margin: 0 auto;
  padding: 0 20px;
  height: 56px;
  display: flex;
  align-items: center;
  gap: 20px;
}
.topbar-brand {
  font-size: 15px;
  font-weight: 700;
  color: #191f28;
  white-space: nowrap;
  text-decoration: none;
  transition: color 0.15s ease;
  flex-shrink: 0;
}
.topbar-brand:hover { color: #3182f6; }
.topbar-nav {
  display: flex;
  gap: 4px;
  flex: 1;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
}
.topbar-nav::-webkit-scrollbar { display: none; }
.nav-item {
  font-size: 14px;
  color: #6b7684;
  text-decoration: none;
  padding: 8px 12px;
  border-radius: 8px;
  font-weight: 500;
  transition: all 0.15s ease;
  white-space: nowrap;
}
.nav-item:hover { background: #f2f4f6; color: #191f28; }
.nav-item.active { color: #3182f6; font-weight: 600; }
.topbar-user {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}
.topbar-username {
  font-size: 13px;
  color: #8b95a1;
  white-space: nowrap;
}
.topbar-logout {
  font-size: 12px;
  padding: 6px 12px;
  background: #f2f4f6;
  border: none;
  border-radius: 8px;
  color: #4e5968;
  cursor: pointer;
  font-weight: 600;
  white-space: nowrap;
}
.topbar-logout:hover { background: #e5e8eb; }

/* 모바일: 헤더를 2층으로 — 위(로고+로그아웃) / 아래(메뉴 가로스크롤) */
@media (max-width: 640px) {
  .topbar-inner {
    height: auto;
    flex-direction: column;
    align-items: stretch;
    gap: 0;
    padding: 0;
  }
  .topbar-row1 {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 16px;
  }
  .topbar-nav {
    border-top: 1px solid #f2f4f6;
    padding: 6px 12px;
    gap: 2px;
  }
  .topbar-username { display: none; }
  .nav-item { font-size: 13px; padding: 8px 10px; }
}
/* 데스크탑에선 row1 래퍼가 그냥 투명하게 펼쳐짐 */
@media (min-width: 641px) {
  .topbar-row1 {
    display: contents;
  }
}
`;

// ============================================
// 연구 분야 목록 (settings.html에서 사용)
// Phase 6에서 확장 예정 — 지금은 8개
// ============================================
const RESEARCH_FIELDS = [
  { id: 'data-mining', label: '데이터 마이닝 / Knowledge Discovery', desc: 'KDD, CIKM, WSDM, SIGIR, ICDM, WWW', cats: ['cs.IR','cs.DB','cs.LG','cs.AI'] },
  { id: 'ml-general', label: 'Machine Learning (일반)', desc: 'NeurIPS, ICML, ICLR', cats: ['cs.LG','stat.ML','cs.AI'] },
  { id: 'nlp', label: '자연어처리 (NLP)', desc: 'ACL, EMNLP, NAACL', cats: ['cs.CL','cs.LG','cs.AI'] },
  { id: 'cv', label: '컴퓨터 비전 (Computer Vision)', desc: 'CVPR, ICCV, ECCV', cats: ['cs.CV','cs.LG','cs.AI'] },
  { id: 'speech', label: '음성 / 오디오', desc: 'INTERSPEECH, ICASSP', cats: ['cs.SD','eess.AS','cs.CL','cs.LG'] },
  { id: 'robotics', label: '로보틱스 / 강화학습', desc: 'RSS, CoRL, ICRA, IROS', cats: ['cs.RO','cs.LG','cs.AI'] },
  { id: 'database', label: '데이터베이스 / 시스템', desc: 'SIGMOD, VLDB, ICDE', cats: ['cs.DB','cs.LG','cs.DC'] },
  { id: 'security', label: 'AI 보안 / 프라이버시', desc: 'S&P, USENIX Security, CCS', cats: ['cs.CR','cs.LG','cs.AI'] },
  { id: 'multimodal', label: '멀티모달 / Vision-Language', desc: 'CVPR, ICCV, NeurIPS', cats: ['cs.CV','cs.CL','cs.LG'] },
  { id: 'graph-ml', label: '그래프 머신러닝', desc: 'LoG, NeurIPS, ICLR', cats: ['cs.LG','cs.SI','cs.AI'] },
  { id: 'theory', label: '머신러닝 이론 / 최적화', desc: 'COLT, NeurIPS theory', cats: ['cs.LG','stat.ML','math.OC','cs.DS'] },
  { id: 'hci', label: 'HCI / AI 인터랙션', desc: 'CHI, UIST, CSCW', cats: ['cs.HC','cs.AI'] },
  { id: 'software', label: '소프트웨어 공학 / AI4Code', desc: 'ICSE, FSE, ASE', cats: ['cs.SE','cs.PL','cs.LG'] },
  { id: 'bioinformatics', label: '바이오인포매틱스 / AI4Science', desc: 'ISMB, RECOMB', cats: ['q-bio.QM','cs.LG','cs.AI'] },
  { id: 'graphics', label: '컴퓨터 그래픽스 / 생성모델', desc: 'SIGGRAPH, Eurographics', cats: ['cs.GR','cs.CV','cs.LG'] },
]

// ============================================
// Supabase 데이터 헬퍼 — 키워드
// ============================================

// 내 키워드 전체 가져오기
async function fetchMyKeywords() {
  const { data, error } = await supabaseClient
    .from('user_keywords')
    .select('id, keyword')
    .order('created_at', { ascending: true });
  if (error) { console.error('키워드 조회 실패:', error); return []; }
  return data || [];
}

// 키워드 추가
async function addKeyword(userId, keyword) {
  const { data, error } = await supabaseClient
    .from('user_keywords')
    .insert({ user_id: userId, keyword: keyword })
    .select()
    .single();
  if (error) {
    if (error.code === '23505') throw new Error('이미 등록된 키워드예요.');
    throw new Error(error.message);
  }
  return data;
}

// 키워드 삭제
async function deleteKeyword(keywordId) {
  const { error } = await supabaseClient
    .from('user_keywords')
    .delete()
    .eq('id', keywordId);
  if (error) throw new Error(error.message);
}

// ============================================
// Supabase 데이터 헬퍼 — 연구 분야
// ============================================

// 내 분야 전체 가져오기
async function fetchMyFields() {
  const { data, error } = await supabaseClient
    .from('user_fields')
    .select('id, field_id')
    .order('created_at', { ascending: true });
  if (error) { console.error('분야 조회 실패:', error); return []; }
  return data || [];
}

// 분야 추가
async function addField(userId, fieldId) {
  const { data, error } = await supabaseClient
    .from('user_fields')
    .insert({ user_id: userId, field_id: fieldId })
    .select()
    .single();
  if (error) {
    if (error.code === '23505') return null; // 이미 있음 — 조용히 무시
    throw new Error(error.message);
  }
  return data;
}

// 분야 삭제
async function deleteField(fieldRowId) {
  const { error } = await supabaseClient
    .from('user_fields')
    .delete()
    .eq('id', fieldRowId);
  if (error) throw new Error(error.message);
}

// ============================================
// Supabase 데이터 헬퍼 — 북마크
// ============================================

// 내 북마크 전체 가져오기 (최신순)
async function fetchMyBookmarks() {
  const { data, error } = await supabaseClient
    .from('bookmarks')
    .select('*')
    .order('created_at', { ascending: false });
  if (error) { console.error('북마크 조회 실패:', error); return []; }
  return data || [];
}

// 내가 북마크한 paper_id 집합 (빠른 확인용)
async function fetchMyBookmarkIds() {
  const { data, error } = await supabaseClient
    .from('bookmarks')
    .select('paper_id');
  if (error) { console.error('북마크 ID 조회 실패:', error); return new Set(); }
  return new Set((data || []).map(b => b.paper_id));
}

// 북마크 추가
// paper: { paper_id, title, abstract, arxiv_url, summary_ko }
async function addBookmark(userId, paper) {
  const { data, error } = await supabaseClient
    .from('bookmarks')
    .insert({
      user_id: userId,
      paper_id: paper.paper_id,
      title: paper.title || '',
      abstract: paper.abstract || '',
      arxiv_url: paper.arxiv_url || '',
      summary_ko: paper.summary_ko || '',
    })
    .select()
    .single();
  if (error) {
    if (error.code === '23505') throw new Error('이미 북마크한 논문이에요.');
    throw new Error(error.message);
  }
  return data;
}

// 북마크 삭제 (paper_id로)
async function deleteBookmarkByPaperId(userId, paperId) {
  const { error } = await supabaseClient
    .from('bookmarks')
    .delete()
    .eq('user_id', userId)
    .eq('paper_id', paperId);
  if (error) throw new Error(error.message);
}

// 북마크 삭제 (행 id로)
async function deleteBookmarkById(rowId) {
  const { error } = await supabaseClient
    .from('bookmarks')
    .delete()
    .eq('id', rowId);
  if (error) throw new Error(error.message);
}

// 북마크 메모 수정
async function updateBookmarkNote(rowId, note) {
  const { error } = await supabaseClient
    .from('bookmarks')
    .update({ note: note })
    .eq('id', rowId);
  if (error) throw new Error(error.message);
}

// ============================================
// Supabase 데이터 헬퍼 — 대시보드 추천 결과
// ============================================

// 가장 최근 배치 실행 날짜 가져오기
async function fetchLatestRunDate() {
  const { data, error } = await supabaseClient
    .from('daily_papers')
    .select('run_date')
    .order('run_date', { ascending: false })
    .limit(1);
  if (error || !data || data.length === 0) return null;
  return data[0].run_date;
}

// 특정 날짜의 내 추천 결과 + 논문 정보를 합쳐서 가져오기
// 반환: { picks: [...], new: [...], field: [...] }
async function fetchMyRecommendations(runDate) {
  // 1) 내 추천 매핑 (rec_type, paper_id, rank, matched_keywords)
  const { data: recs, error: recErr } = await supabaseClient
    .from('user_recommendations')
    .select('rec_type, paper_id, rank, matched_keywords')
    .eq('run_date', runDate)
    .order('rank', { ascending: true });
  if (recErr) { console.error('추천 조회 실패:', recErr); return { picks: [], new: [], field: [] }; }
  if (!recs || recs.length === 0) return { picks: [], new: [], field: [] };

  // 2) 그 날짜의 논문 풀 전체 (paper_id로 매칭)
  const { data: papers, error: paperErr } = await supabaseClient
    .from('daily_papers')
    .select('*')
    .eq('run_date', runDate);
  if (paperErr) { console.error('논문 조회 실패:', paperErr); return { picks: [], new: [], field: [] }; }

  // paper_id → 논문 정보 맵
  const paperMap = {};
  (papers || []).forEach(p => { paperMap[p.paper_id] = p; });

  // 3) rec_type별로 묶기 + 논문 정보 합치기
  const result = { picks: [], new: [], field: [] };
  recs.forEach(rec => {
    const paper = paperMap[rec.paper_id];
    if (!paper) return;
    const merged = Object.assign({}, paper, {
      rank: rec.rank,
      matched_keywords: rec.matched_keywords || [],
    });
    if (result[rec.rec_type]) result[rec.rec_type].push(merged);
  });
  return result;
}

// ============================================
// Supabase 데이터 헬퍼 — 트렌딩
// ============================================

// 가장 최근 트렌딩 날짜
async function fetchLatestTrendingDate() {
  const { data, error } = await supabaseClient
    .from('daily_trending')
    .select('run_date')
    .order('run_date', { ascending: false })
    .limit(1);
  if (error || !data || data.length === 0) return null;
  return data[0].run_date;
}

// 특정 날짜의 트렌딩 데이터를 소스별로 묶어서 반환
// 반환: { arxiv: [{keyword, count, rank}], hf: [...], active: [...] }
async function fetchTrending(runDate) {
  const { data, error } = await supabaseClient
    .from('daily_trending')
    .select('source, keyword, count, rank')
    .eq('run_date', runDate)
    .order('rank', { ascending: true });
  if (error) { console.error('트렌딩 조회 실패:', error); return { arxiv: [], hf: [], active: [] }; }

  const result = { arxiv: [], hf: [], active: [] };
  (data || []).forEach(row => {
    if (result[row.source]) {
      result[row.source].push({
        keyword: row.keyword,
        count: row.count,
        rank: row.rank,
      });
    }
  });
  return result;
}

// ============================================
// 분야별 OpenReview venue 매핑 (conferences.html에서 사용)
// OpenReview의 content.venue 값과 정확히 일치해야 함
// OpenReview 안 쓰는 학회(KDD, SIGIR 등)는 포함 불가 — 한계
// venue 문자열은 OpenReview 정책에 따라 조정 필요할 수 있음
// ============================================
const FIELD_VENUES = {
  'ml-general': [
    'ICLR 2026', 'ICLR 2025', 'ICLR 2024',
    'NeurIPS 2025', 'NeurIPS 2024',
    'ICML 2025', 'ICML 2024',
  ],
  'nlp': [
    'COLM 2025', 'COLM 2024',
    'ICLR 2026', 'ICLR 2025',
    'NeurIPS 2025', 'NeurIPS 2024',
  ],
  'cv': [
    'ICLR 2026', 'ICLR 2025',
    'NeurIPS 2025', 'NeurIPS 2024',
    'ICML 2025',
  ],
  'data-mining': [
    'ICLR 2026', 'ICLR 2025',
    'NeurIPS 2025', 'NeurIPS 2024',
  ],
  'robotics': [
    'CoRL 2024', 'CoRL 2025',
    'ICLR 2025', 'NeurIPS 2024',
  ],
  'graph-ml': [
    'LoG 2024', 'LoG 2025',
    'ICLR 2025', 'NeurIPS 2024',
  ],
  'theory': [
    'ICLR 2025', 'NeurIPS 2024', 'ICML 2025',
  ],
  'multimodal': [
    'ICLR 2026', 'ICLR 2025', 'NeurIPS 2025',
  ],
  'ml-general-rl': [
    'RLC 2024', 'RLC 2025',
  ],
  // OpenReview를 거의 안 쓰는 분야들 (결과 빈약할 수 있음)
  'speech': ['ICLR 2025', 'NeurIPS 2024'],
  'database': ['ICLR 2025', 'NeurIPS 2024'],
  'security': ['ICLR 2025', 'NeurIPS 2024'],
  'hci': ['ICLR 2025'],
  'software': ['ICLR 2025', 'NeurIPS 2024'],
  'bioinformatics': ['ICLR 2025', 'NeurIPS 2024'],
  'graphics': ['ICLR 2025', 'NeurIPS 2024'],
};

// 내 분야들에 매핑된 venue 목록 (중복 제거)
function getVenuesForFields(fieldIds) {
  const venueSet = new Set();
  (fieldIds || []).forEach(fid => {
    // custom: 분야는 OpenReview venue 없음 — 스킵
    if (fid.startsWith('custom:')) return;
    const venues = FIELD_VENUES[fid] || [];
    venues.forEach(v => venueSet.add(v));
  });
  return Array.from(venueSet);
}

// ============================================
// 학회 논문 — Supabase에서 읽기 (batch.py가 OpenReview에서 미리 수집)
// 브라우저가 OpenReview를 직접 호출하면 CORS로 막히므로 이 방식 사용
// ============================================

// 가장 최근 학회 데이터 날짜
async function fetchLatestConferenceDate() {
  const { data, error } = await supabaseClient
    .from('daily_conferences')
    .select('run_date')
    .order('run_date', { ascending: false })
    .limit(1);
  if (error || !data || data.length === 0) return null;
  return data[0].run_date;
}

// 특정 venue의 논문 목록 (Supabase에서)
async function fetchVenueePapers(venue, limit) {
  const { data, error } = await supabaseClient
    .from('daily_conferences')
    .select('paper_id, title, authors, venue, url')
    .eq('venue', venue)
    .limit(limit || 200);
  if (error) {
    console.warn('학회 조회 실패 (' + venue + '):', error);
    return [];
  }
  return (data || []).map(r => ({
    paper_id: r.paper_id,
    title: r.title || '',
    authors: r.authors || '',
    venue: r.venue || venue,
    url: r.url || '#',
  }));
}

// ============================================
// 옵션 A: 클라이언트 측 즉시 필터링
// 오늘 daily_papers 풀을 가져와 최신 키워드/분야로 브라우저에서 필터
// arXiv/LLM 재호출 없음 — 비용 0, 즉시
// ============================================

// 특정 날짜의 daily_papers 전체 가져오기 (논문 풀)
async function fetchDailyPaperPool(runDate) {
  const { data, error } = await supabaseClient
    .from('daily_papers')
    .select('*')
    .eq('run_date', runDate);
  if (error) { console.error('논문 풀 조회 실패:', error); return []; }
  return data || [];
}

// 논문 1편이 키워드 목록 중 몇 개에 매칭되는지 + 매칭된 키워드 반환
function matchPaperKeywords(paper, keywords) {
  const haystack = ((paper.title || '') + ' ' + (paper.abstract || '')).toLowerCase();
  const matched = [];
  keywords.forEach(kw => {
    const k = kw.toLowerCase().trim();
    if (k && haystack.includes(k)) matched.push(kw);
  });
  return matched;
}

// 풀 + 내 키워드/분야 → { picks, new, field } 즉시 계산
// keywords: 문자열 배열, fieldIds: 분야 id 배열
function buildClientRecommendations(pool, keywords, fieldIds, topN) {
  topN = topN || 10;

  // picks: 키워드 매칭 (매칭 개수 많은 순 → hf_likes 순)
  let picks = [];
  if (keywords.length > 0) {
    picks = pool
      .map(p => {
        const m = matchPaperKeywords(p, keywords);
        return { paper: p, matched: m, score: m.length };
      })
      .filter(x => x.score > 0)
      .sort((a, b) => (b.score - a.score) || ((b.paper.hf_likes || 0) - (a.paper.hf_likes || 0)))
      .slice(0, topN)
      .map(x => Object.assign({}, x.paper, { matched_keywords: x.matched }));
  }

  // new: 24시간 이내 + 키워드 매칭
  let newPapers = [];
  if (keywords.length > 0) {
    newPapers = pool
      .filter(p => p.is_recent_24h)
      .map(p => {
        const m = matchPaperKeywords(p, keywords);
        return { paper: p, matched: m, score: m.length };
      })
      .filter(x => x.score > 0)
      .sort((a, b) => (b.score - a.score) || ((b.paper.hf_likes || 0) - (a.paper.hf_likes || 0)))
      .slice(0, topN)
      .map(x => Object.assign({}, x.paper, { matched_keywords: x.matched }));
  }

  // field: 분야 arxiv 카테고리 매칭 (키워드 매칭에 안 든 것 중에서)
  let fieldPapers = [];
  if (fieldIds.length > 0) {
    // 분야 → 카테고리 집합
    const catSet = new Set();
    fieldIds.forEach(fid => {
      if (fid.startsWith('custom:')) {
        catSet.add(fid.replace('custom:', ''));
      } else {
        const f = RESEARCH_FIELDS.find(x => x.id === fid);
        if (f && f.cats) f.cats.forEach(c => catSet.add(c));
      }
    });
    const usedIds = new Set([...picks, ...newPapers].map(p => p.paper_id));
    fieldPapers = pool
      .filter(p => !usedIds.has(p.paper_id))
      .filter(p => (p.categories || []).some(c => catSet.has(c)))
      .sort((a, b) => (b.hf_likes || 0) - (a.hf_likes || 0))
      .slice(0, topN);
  }

  return { picks: picks, new: newPapers, field: fieldPapers };
}