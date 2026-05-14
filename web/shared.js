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
        '<div class="topbar-brand">AI 트렌드 뉴스레터</div>' +
        '<nav class="topbar-nav">' + navHtml + '</nav>' +
        '<div class="topbar-user">' +
          '<span class="topbar-username">' + escapeHtml(userName) + '</span>' +
          '<button class="topbar-logout" id="__logout_btn">로그아웃</button>' +
        '</div>' +
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
  gap: 24px;
}
.topbar-brand {
  font-size: 15px;
  font-weight: 700;
  color: #191f28;
  white-space: nowrap;
}
.topbar-nav {
  display: flex;
  gap: 4px;
  flex: 1;
}
.nav-item {
  font-size: 14px;
  color: #6b7684;
  text-decoration: none;
  padding: 8px 12px;
  border-radius: 8px;
  font-weight: 500;
  transition: all 0.15s ease;
}
.nav-item:hover { background: #f2f4f6; color: #191f28; }
.nav-item.active { color: #3182f6; font-weight: 600; }
.topbar-user {
  display: flex;
  align-items: center;
  gap: 10px;
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
@media (max-width: 640px) {
  .topbar-inner { gap: 12px; }
  .topbar-nav { overflow-x: auto; }
  .topbar-username { display: none; }
}
`;
