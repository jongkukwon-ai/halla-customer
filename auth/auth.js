/* 고객사 로그인 — 판매처 코드 확인 + 접속 유지 + 화면 잠금.
 *
 * 쓰는 곳
 *   - 각 화면(<head> 끝):  <script src="auth/customers.js"></script><script src="auth/auth.js"></script>
 *       → 로그인 안 했으면 login.html 로 보내고, 했으면 화면을 보여 주고 아래 쪽에 「업체명 · 로그아웃」 표시
 *   - login.html: window.HALLA_LOGIN_PAGE = true 를 먼저 선언 → 화면 잠금 없이 HallaAuth 만 제공
 *
 * 주의: 정적 사이트(GitHub Pages)용 가벼운 잠금장치이다. 화면 주소를 직접 아는 사람까지 막는 서버 인증이 아니다.
 * 코드 원문·업체명은 customers.js 에 남지 않는다(auth/tools/make_customers.py 설명 참고).
 */
(function () {
  'use strict';

  var D = window.HALLA_CUSTOMERS || { list: [] };
  var KEY = 'halla_customer_session';
  var TTL = 30 * 24 * 3600 * 1000;                      // 로그인 유지 기간: 30일
  var script = document.currentScript;
  var BASE = script.src.slice(0, script.src.lastIndexOf('auth/'));   // 사이트 맨 위 주소(끝에 /)

  /* ── 접속 정보 저장(localStorage → 막혀 있으면 sessionStorage) ── */
  function stores() {
    var a = [];
    try { a.push(window.localStorage); } catch (e) { /* 시크릿 모드 등 */ }
    try { a.push(window.sessionStorage); } catch (e) { /* ignore */ }
    return a;
  }
  function save(s) {
    var raw = JSON.stringify(s);
    for (var st of stores()) { try { st.setItem(KEY, raw); return; } catch (e) { /* 다음 저장소 */ } }
  }
  function clear() { stores().forEach(function (st) { try { st.removeItem(KEY); } catch (e) { /* ignore */ } }); }

  function session() {
    for (var st of stores()) {
      try {
        var raw = st.getItem(KEY);
        if (!raw) continue;
        var s = JSON.parse(raw);
        if (!s || !s.i || !s.t || Date.now() - s.t > TTL || s.t > Date.now() + 60000) continue;   // 만료·시계 이상
        if (!D.list.some(function (e) { return e.i === s.i; })) continue;                         // 목록에서 빠진 고객사
        return s;
      } catch (e) { /* 깨진 값은 무시 */ }
    }
    return null;
  }

  /* ── 코드 확인: 코드 → PBKDF2 → (조회 번호 16B, 업체명 복호화 키 32B) ── */
  function normalize(code) { return String(code == null ? '' : code).replace(/\s+/g, '').toUpperCase(); }
  function b64(s) { return Uint8Array.from(atob(s), function (c) { return c.charCodeAt(0); }); }
  function hex(u8) { return Array.prototype.map.call(u8, function (b) { return ('0' + b.toString(16)).slice(-2); }).join(''); }

  async function login(input) {
    var code = normalize(input);
    if (!code) return null;
    if (!(window.crypto && crypto.subtle)) throw new Error('secure-context');   // http(비보안) 주소에서는 사용 불가
    var km = await crypto.subtle.importKey('raw', new TextEncoder().encode(code), 'PBKDF2', false, ['deriveBits']);
    var dk = new Uint8Array(await crypto.subtle.deriveBits(
      { name: 'PBKDF2', hash: 'SHA-256', salt: b64(D.salt), iterations: D.iter }, km, 512));
    var idx = hex(dk.slice(0, 16));
    var entry = D.list.find(function (e) { return e.i === idx; });
    if (!entry) return null;
    var name;
    try {
      var key = await crypto.subtle.importKey('raw', dk.slice(32, 64), 'AES-GCM', false, ['decrypt']);
      name = new TextDecoder().decode(await crypto.subtle.decrypt({ name: 'AES-GCM', iv: b64(entry.v) }, key, b64(entry.c)));
    } catch (e) { return null; }
    save({ i: idx, n: name, t: Date.now() });
    return { name: name };
  }

  function logout() { clear(); location.replace(BASE + 'login.html'); }

  window.HallaAuth = { login: login, logout: logout, session: session, base: BASE };

  if (window.HALLA_LOGIN_PAGE) return;

  /* ── 화면 잠금 ── */
  var s = session();
  if (!s) {
    document.documentElement.style.visibility = 'hidden';            // 이동하는 동안 내용이 비치지 않게
    var rel = location.href.slice(BASE.length);
    var next = (rel === '' || rel === 'index.html') ? '' : '?next=' + encodeURIComponent(rel);
    location.replace(BASE + 'login.html' + next);
    return;
  }

  /* ── 「업체명 · 로그아웃」 표시 ── */
  document.addEventListener('DOMContentLoaded', function () {
    var st = document.createElement('style');
    st.textContent =
      '#halla-auth-chip{position:fixed;left:14px;bottom:14px;z-index:150;display:flex;align-items:center;gap:8px;' +
      'max-width:calc(100vw - 28px);padding:6px 6px 6px 13px;border-radius:50px;font:12px/1.2 "Pretendard","Noto Sans KR",sans-serif;' +
      'color:#e9f3ec;background:rgba(10,13,12,.86);border:1px solid rgba(120,205,120,.4);box-shadow:0 4px 14px rgba(0,0,0,.28)}' +
      '#halla-auth-chip span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}' +
      '#halla-auth-chip button{flex:none;cursor:pointer;font:inherit;color:#A6DD62;background:rgba(120,205,90,.1);' +
      'border:1px solid rgba(120,205,90,.5);border-radius:50px;padding:4px 11px}' +
      '#halla-auth-chip button:hover{background:rgba(120,205,90,.22)}' +
      '@media print{#halla-auth-chip{display:none}}';
    document.head.appendChild(st);
    var chip = document.createElement('div');
    chip.id = 'halla-auth-chip';
    var label = document.createElement('span');
    label.textContent = s.n;
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.textContent = '로그아웃';
    btn.addEventListener('click', logout);
    chip.appendChild(label);
    chip.appendChild(btn);
    document.body.appendChild(chip);
  });

  document.documentElement.style.visibility = '';
})();
