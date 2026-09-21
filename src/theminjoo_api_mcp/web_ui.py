DASHBOARD_HTML = r"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>민주당 브리핑 · 모두발언</title>
<style>
:root{
  color-scheme:light;
  --bg:#f6f8fb;
  --card:#fff;
  --text:#18212f;
  --muted:#667085;
  --line:#e5e7eb;
  --accent:#1769e0;
  --accent2:#0f56bb;
}
*{box-sizing:border-box}
body{margin:0;font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:var(--bg);color:var(--text)}
.wrap{max-width:980px;margin:0 auto;padding:28px 18px 60px}
.hero{background:linear-gradient(135deg,#0f56bb,#1769e0);color:#fff;border-radius:22px;padding:28px;box-shadow:0 12px 30px rgba(23,105,224,.18)}
.hero h1{margin:0 0 8px;font-size:28px}
.hero p{margin:0;opacity:.9;line-height:1.55}
.toolbar{display:grid;grid-template-columns:1fr auto;gap:12px;margin:18px 0}
.search{display:flex;gap:10px}
input{width:100%;border:1px solid var(--line);border-radius:12px;padding:13px 14px;font-size:15px;background:#fff}
button,.btn{border:0;border-radius:12px;padding:12px 15px;font-weight:700;cursor:pointer;text-decoration:none;display:inline-flex;align-items:center;justify-content:center}
.primary{background:var(--accent);color:#fff}
.primary:hover{background:var(--accent2)}
.secondary{background:#fff;color:var(--text);border:1px solid var(--line)}
.tabs{display:flex;gap:8px;margin:18px 0}
.tab{background:#fff;border:1px solid var(--line);color:var(--muted)}
.tab.active{background:var(--accent);color:#fff;border-color:var(--accent)}
.actions{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px}
#status{color:var(--muted);font-size:14px;margin:12px 2px}
.list{display:grid;gap:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:18px;box-shadow:0 2px 8px rgba(16,24,40,.04)}
.meta{font-size:13px;color:var(--muted);margin-bottom:7px}
.title{font-size:17px;font-weight:800;line-height:1.45;margin-bottom:12px}
.card-actions{display:flex;gap:8px;flex-wrap:wrap}
.card-actions a,.card-actions button{font-size:13px;padding:8px 11px}
.detail{margin-top:18px;background:#fff;border:1px solid var(--line);border-radius:16px;padding:20px;display:none}
.detail h2{font-size:21px;margin-top:0}
.detail pre{white-space:pre-wrap;font-family:inherit;line-height:1.7;margin:0}
.note{margin-top:18px;color:var(--muted);font-size:13px;line-height:1.6}
@media(max-width:720px){.toolbar{grid-template-columns:1fr}.search{flex-direction:column}.hero h1{font-size:23px}}
</style>
</head>
<body>
<div class="wrap">
  <section class="hero">
    <h1>민주당 논평·브리핑 / 모두발언</h1>
    <p>더불어민주당 공식 홈페이지 공개 게시물을 빠르게 검색하고 읽을 수 있는 비공식 뷰어입니다.</p>
  </section>

  <div class="tabs">
    <button class="tab active" data-board="11">논평·브리핑</button>
    <button class="tab" data-board="230">모두발언</button>
  </div>

  <div class="toolbar">
    <div class="search">
      <input id="q" placeholder="제목 검색어 입력">
      <button id="searchBtn" class="primary">검색</button>
    </div>
    <button id="latestBtn" class="secondary">최신 글</button>
  </div>

  <div class="actions">
    <a id="mdLink" class="btn secondary" target="_blank">AI용 Markdown 열기</a>
    <button id="copyPromptBtn" class="secondary">ChatGPT용 질문 복사</button>
  </div>

  <div id="status">불러오는 중...</div>
  <div id="list" class="list"></div>

  <section id="detail" class="detail">
    <h2 id="detailTitle"></h2>
    <div id="detailMeta" class="meta"></div>
    <pre id="detailBody"></pre>
  </section>

  <p class="note">
    이 서비스는 공식 당 사이트의 공개 자료를 읽어 보여주는 비공식 도구입니다.
    원문 및 저작권은 원 출처에 따릅니다.
  </p>
</div>

<script>
let board = 11;
const listEl = document.getElementById('list');
const statusEl = document.getElementById('status');
const qEl = document.getElementById('q');
const mdLink = document.getElementById('mdLink');

function esc(s){
  return String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
function dateText(v){
  if(!v) return '';
  try{return new Date(v).toLocaleString('ko-KR')}catch{return v}
}
function updateLinks(){
  mdLink.href = '/v1/markdown?board=' + board + '&limit=30';
}
async function loadLatest(){
  statusEl.textContent='불러오는 중...';
  document.getElementById('detail').style.display='none';
  const res = await fetch('/v1/posts?board=' + board + '&offset=0&limit=30');
  if(!res.ok){statusEl.textContent='불러오지 못했습니다.';return}
  const data = await res.json();
  render(data.items || []);
}
async function search(){
  const q=qEl.value.trim();
  if(!q){loadLatest();return}
  statusEl.textContent='검색 중...';
  document.getElementById('detail').style.display='none';
  const res=await fetch('/v1/search?board='+board+'&pages=5&q='+encodeURIComponent(q));
  if(!res.ok){statusEl.textContent='검색하지 못했습니다.';return}
  render(await res.json());
}
function render(items){
  statusEl.textContent = items.length + '건';
  listEl.innerHTML = items.map(x => `
    <article class="card">
      <div class="meta">${esc(x.board_label)} · ${esc(x.category || '')} ${x.published_at ? '· ' + esc(dateText(x.published_at)) : ''}</div>
      <div class="title">${esc(x.title)}</div>
      <div class="card-actions">
        <button class="primary" onclick="openDetail(${x.board},${x.post_id})">본문 보기</button>
        <a class="btn secondary" target="_blank" href="${esc(x.url)}">공식 원문</a>
        <a class="btn secondary" target="_blank" href="/v1/markdown/${x.board}/${x.post_id}">AI용 본문</a>
      </div>
    </article>
  `).join('');
}
async function openDetail(b,id){
  const detail=document.getElementById('detail');
  detail.style.display='block';
  document.getElementById('detailTitle').textContent='불러오는 중...';
  document.getElementById('detailBody').textContent='';
  detail.scrollIntoView({behavior:'smooth',block:'start'});
  const res=await fetch('/v1/posts/'+b+'/'+id);
  if(!res.ok){document.getElementById('detailTitle').textContent='본문을 불러오지 못했습니다.';return}
  const x=await res.json();
  document.getElementById('detailTitle').textContent=x.title;
  document.getElementById('detailMeta').textContent=(x.published_at?dateText(x.published_at)+' · ':'')+(x.author||'');
  document.getElementById('detailBody').textContent=x.content||'';
}
document.querySelectorAll('.tab').forEach(btn=>{
  btn.addEventListener('click',()=>{
    document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));
    btn.classList.add('active');
    board=Number(btn.dataset.board);
    updateLinks();
    loadLatest();
  });
});
document.getElementById('searchBtn').addEventListener('click',search);
document.getElementById('latestBtn').addEventListener('click',loadLatest);
qEl.addEventListener('keydown',e=>{if(e.key==='Enter')search()});
document.getElementById('copyPromptBtn').addEventListener('click',async()=>{
  const url=location.origin + '/v1/markdown?board=' + board + '&limit=30';
  const label=board===11?'민주당 최신 논평·브리핑':'민주당 최신 모두발언';
  const prompt='이 공개 URL을 읽고 '+label+'을 핵심 내용, 인물, 날짜, 원문 링크 중심으로 요약해줘: '+url;
  await navigator.clipboard.writeText(prompt);
  const btn=document.getElementById('copyPromptBtn');
  const old=btn.textContent; btn.textContent='복사 완료'; setTimeout(()=>btn.textContent=old,1200);
});
updateLinks();
loadLatest();
</script>
</body>
</html>
"""
