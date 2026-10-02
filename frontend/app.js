const app = document.querySelector('#app');
const params = new URLSearchParams(location.search);
const token = params.get('token') || '';
const state = { themes: [], selected: new Set(), me: null, questions: [], results: null };

const esc = (v='') => String(v ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const api = async (path, options={}) => {
  const headers = {'Content-Type':'application/json', ...(options.headers||{})};
  if (token) headers['X-Participant-Token'] = token;
  const res = await fetch(path, {...options, headers});
  let data = {};
  try { data = await res.json(); } catch {}
  if (!res.ok) throw new Error(data.detail || 'Не удалось выполнить запрос');
  return data;
};
const button = (text, cls='primary', attrs='') => `<button class="${cls}" ${attrs}>${text}</button>`;
const page = (inner, cls='') => { app.className = `app-shell ${cls}`; app.innerHTML = `<header class="top"><a href="/" class="logo">USelf</a><span>alpha</span></header>${inner}<footer>USelf · желания, границы и разговор без догадок</footer>`; };
const errorBox = e => `<div class="notice error">${esc(e.message || e)}</div>`;

async function start(){
  try {
    if (!token) return renderCreatorStart();
    state.me = await api('/api/me');
    if (!state.me.profile_complete) return renderInvite();
    if (state.me.status === 'completed') return loadResults();
    await loadQuestions();
  } catch(e) { page(`<section class="card"><h1>Что-то пошло не так</h1>${errorBox(e)}</section>`); }
}

async function renderCreatorStart(){
  try { state.themes = (await api('/api/themes')).themes; } catch(e) { return page(errorBox(e)); }
  page(`<main class="narrow">
    <div class="kicker">Совместный тест</div>
    <h1>Создай тест для вас двоих</h1>
    <p class="lead">Сначала укажи свои данные, затем выбери темы. После этого мы дадим отдельную ссылку для партнёра.</p>
    <section class="card form-card">
      <div class="step">01 · Твои данные</div>
      <label>Имя или псевдоним<input id="creator-name" maxlength="50" autocomplete="name" placeholder="Например, Тимур"></label>
      <label>Возраст<input id="creator-age" type="number" min="18" max="99" inputmode="numeric" placeholder="30"></label>
      ${button('Дальше →','primary','id="to-themes"')}
    </section>
  </main>`);
  document.querySelector('#to-themes').onclick = () => {
    const name = document.querySelector('#creator-name').value.trim();
    const age = Number(document.querySelector('#creator-age').value);
    if (!name || age < 18 || age > 99) return inlineError('Укажи имя и возраст от 18 до 99 лет.');
    state.creator = {name, age}; renderThemePicker();
  };
}

function renderThemePicker(){
  page(`<main>
    <button class="text-btn" id="back-start">← Назад</button>
    <div class="kicker">02 · Темы</div>
    <h1>Что войдёт в ваш тест?</h1>
    <p class="lead">Партнёр получит ровно тот же набор вопросов. Для первого прогона можно выбрать 1–2 темы, чтобы не делать тест слишком длинным.</p>
    <div class="theme-grid">${state.themes.map(t => `<button class="theme ${state.selected.has(t.slug)?'selected':''}" data-theme="${t.slug}"><span>${esc(t.title)}</span><b>${t.question_count}</b><small>вопросов</small></button>`).join('')}</div>
    <div class="sticky-action"><div><b id="selected-count">${selectedQuestionCount()}</b><span> вопросов выбрано</span></div>${button('Создать тест →','primary','id="create-room"')}</div>
  </main>`);
  document.querySelector('#back-start').onclick = renderCreatorStart;
  document.querySelectorAll('[data-theme]').forEach(el => el.onclick = () => {
    const slug = el.dataset.theme;
    state.selected.has(slug) ? state.selected.delete(slug) : state.selected.add(slug);
    renderThemePicker();
  });
  document.querySelector('#create-room').onclick = createRoom;
}
function selectedQuestionCount(){ return state.themes.filter(t=>state.selected.has(t.slug)).reduce((n,t)=>n+t.question_count,0); }
async function createRoom(){
  if (!state.selected.size) return inlineError('Выбери хотя бы одну тему.');
  const btn = document.querySelector('#create-room'); btn.disabled = true; btn.textContent = 'Создаём…';
  try {
    const data = await api('/api/sessions',{method:'POST',body:JSON.stringify({creator_alias:state.creator.name,creator_age:state.creator.age,theme_slugs:[...state.selected]})});
    const creatorUrl = new URL(data.creator_url, location.origin).toString();
    const partnerUrl = new URL(data.partner_url, location.origin).toString();
    page(`<main class="narrow"><div class="kicker">03 · Готово</div><h1>Ссылка для партнёра</h1><p class="lead">Отправь именно эту ссылку. По ней партнёр сам укажет имя и возраст, а затем ответит на те же ${data.question_count} вопросов.</p>
      <section class="card"><div class="share"><input id="partner-link" readonly value="${esc(partnerUrl)}">${button('Копировать','secondary','id="copy-link"')}</div><p class="muted">Свою ссылку не пересылай: она открывает твою часть теста.</p>${button('Начать свою часть →','primary','id="own-link"')}</section></main>`);
    document.querySelector('#copy-link').onclick=async()=>{await navigator.clipboard.writeText(partnerUrl); document.querySelector('#copy-link').textContent='Скопировано ✓';};
    document.querySelector('#own-link').onclick=()=>location.href=creatorUrl;
  } catch(e) { btn.disabled=false; btn.textContent='Создать тест →'; inlineError(e.message); }
}

function renderInvite(){
  page(`<main class="narrow invite"><div class="kicker">Приглашение от ${esc(state.me.creator_alias || 'партнёра')}</div><h1>Тебя пригласили пройти совместный тест.</h1>
    <p class="invite-copy">Человеку, который прислал тебе эту ссылку, <strong>не всё равно на твои чувства, желания и границы.</strong></p>
    <div class="soft-rule"></div>
    <p class="lead">После завершения вы увидите ответы и комментарии друг друга. Любой вопрос можно пропустить — отвечать на всё необязательно.</p>
    <section class="card form-card"><label>Твоё имя или псевдоним<input id="partner-name" maxlength="50" placeholder="Как тебя называть?"></label><label>Возраст<input id="partner-age" type="number" min="18" max="99" inputmode="numeric" placeholder="25"></label>${button('Перейти к тесту →','primary','id="join"')}</section></main>`);
  document.querySelector('#join').onclick = async()=>{
    const alias=document.querySelector('#partner-name').value.trim(); const age=Number(document.querySelector('#partner-age').value);
    if(!alias || age<18 || age>99) return inlineError('Укажи имя и возраст от 18 до 99 лет.');
    try { await api('/api/profile',{method:'PUT',body:JSON.stringify({alias,age})}); state.me=await api('/api/me'); await loadQuestions(); } catch(e){inlineError(e.message);}
  };
}

async function loadQuestions(){
  try { state.questions=(await api('/api/questions')).questions; renderQuiz(); } catch(e){ page(errorBox(e)); }
}

function renderQuiz(){
  const answered=state.questions.filter(q=>q.answer).length;
  const comments=state.questions.filter(q=>q.comment).length;
  let lastTheme='', lastBlock='';
  const rows=state.questions.map(q=>{
    let heads='';
    if(q.theme_title!==lastTheme){ lastTheme=q.theme_title; lastBlock=''; heads+=`<div class="theme-head"><span>Тема</span><h2>${esc(q.theme_title)}</h2></div>`; }
    if(q.block_title!==lastBlock){ lastBlock=q.block_title; heads+=`<div class="block-head"><h3>${esc(q.block_title)}</h3>${q.block_intro?`<p>${esc(q.block_intro)}</p>`:''}</div>`; }
    return heads + questionCard(q);
  }).join('');
  page(`<main class="quiz"><section class="quiz-intro card"><div class="kicker">Как отвечать</div><h1>Отвечай про вас двоих</h1><p>Указывай то, чего <strong>тебе хотелось бы именно с этим партнёром</strong>. Не пытайся угадать его ответы и не выбирай то, что «правильно» по твоему мнению.</p><div class="legend"><span><b>Да</b> — интересно / нравится</span><span><b>Возможно</b> — готов_а рассмотреть, если партнёру тоже интересно</span><span><b>Нет</b> — мне это не подходит</span></div><p class="muted">Без ответа = пропущено. Пропуск не считается «Нет».</p></section>
    <div class="quiz-status"><span>${esc(state.me.alias)}</span><b>${answered}/${state.questions.length}</b><small>${comments} комментариев</small></div>
    ${rows}
    <section class="finish card"><h2>Готово?</h2><p>Можно завершить тест даже с пропущенными вопросами. После завершения ответы изменить нельзя.</p>${button('Завершить свою часть','primary danger','id="submit-test"')}</section>
  </main>`);
  document.querySelectorAll('[data-answer]').forEach(b=>b.onclick=()=>setAnswer(Number(b.dataset.q),b.dataset.answer));
  document.querySelectorAll('[data-comment-open]').forEach(b=>b.onclick=()=>toggleComment(Number(b.dataset.commentOpen)));
  document.querySelectorAll('[data-comment-save]').forEach(b=>b.onclick=()=>saveComment(Number(b.dataset.commentSave)));
  document.querySelector('#submit-test').onclick=submitTest;
}
function questionCard(q){
  const att=q.attention_note?`<div class="attention">⚠ ${esc(q.attention_note)}</div>`:'';
  return `<article class="question" id="q-${q.id}"><div class="q-meta"><span>${q.position}</span>${q.side_label?`<em>${esc(q.side_label)}</em>`:''}</div><p class="q-text">${esc(q.text)}</p>${att}<div class="answers">${['yes','maybe','no'].map(v=>`<button data-answer="${v}" data-q="${q.id}" class="answer ${q.answer===v?'active':''} ${v}">${v==='yes'?'Да':v==='maybe'?'Возможно':'Нет'}</button>`).join('')}</div><div class="comment-wrap">${q.comment?commentEditor(q,true):`<button class="comment-link" data-comment-open="${q.id}">＋ Оставить пояснение</button>`}</div></article>`;
}
function commentEditor(q,existing=false){ return `<div class="comment-editor"><textarea id="comment-${q.id}" maxlength="1000" placeholder="Например: что именно нравится, при каких условиях или что важно учесть">${esc(q.comment||'')}</textarea><div>${button(existing?'Обновить':'Сохранить','mini','data-comment-save="'+q.id+'"')}<button class="mini ghost" data-comment-open="${q.id}">Отмена</button></div></div>`; }
function toggleComment(id){
  const q=state.questions.find(x=>x.id===id); const wrap=document.querySelector(`#q-${id} .comment-wrap`); if(!q||!wrap)return;
  if(wrap.querySelector('textarea') && !q.comment){ wrap.innerHTML=`<button class="comment-link" data-comment-open="${id}">＋ Оставить пояснение</button>`; wrap.querySelector('button').onclick=()=>toggleComment(id); return; }
  wrap.innerHTML=commentEditor(q,!!q.comment); wrap.querySelectorAll('[data-comment-open]').forEach(b=>b.onclick=()=>toggleComment(id)); wrap.querySelectorAll('[data-comment-save]').forEach(b=>b.onclick=()=>saveComment(id)); wrap.querySelector('textarea').focus();
}
async function setAnswer(id,value){
  const q=state.questions.find(x=>x.id===id); if(!q)return; const next=q.answer===value?null:value; q.answer=next;
  try{ await saveResponse(q); renderQuiz(); location.hash=`q-${id}`; }catch(e){inlineError(e.message);}
}
async function saveComment(id){ const q=state.questions.find(x=>x.id===id); const ta=document.querySelector(`#comment-${id}`); if(!q||!ta)return; q.comment=ta.value.trim()||null; try{await saveResponse(q);renderQuiz();location.hash=`q-${id}`;}catch(e){inlineError(e.message);} }
async function saveResponse(q){ return api('/api/responses',{method:'PUT',body:JSON.stringify({session_question_id:q.id,value:q.answer||null,comment:q.comment||null})}); }
async function submitTest(){
  if(!confirm('Завершить свою часть теста? После этого ответы нельзя будет изменить.')) return;
  try{await api('/api/submit',{method:'POST',body:JSON.stringify({confirm:true})});state.me=await api('/api/me');loadResults();}catch(e){inlineError(e.message);}
}

async function loadResults(){ try{state.results=await api('/api/results');renderResults();}catch(e){page(errorBox(e));} }
function renderResults(){
  const d=state.results;
  if(!d.ready) return page(`<main class="narrow waiting"><div class="orb">♡</div><h1>Твоя часть готова</h1><p class="lead">${esc(d.message)}</p>${button('Проверить ещё раз','primary','id="reload-results"')}</main>`), document.querySelector('#reload-results').onclick=loadResults;
  const labels={green:'Да + Да',blue:'Есть «Возможно»',red:'Есть «Нет»',neutral:'Есть пропуск'};
  const items=d.items.map(item=>`<article class="result-row ${item.status}"><div class="result-main"><span class="result-cloud ${item.status}">${labels[item.status]}</span><div><small>${esc(item.theme_title)}${item.block_title?' · '+esc(item.block_title):''}</small><p>${esc(item.text)}</p>${item.side_label?`<em>${esc(item.side_label)}</em>`:''}</div></div><div class="pair"><div><b>${esc(item.creator.alias)}</b><strong>${esc(item.creator.answer_label)}</strong>${item.creator.comment?`<p>“${esc(item.creator.comment)}”</p>`:''}</div><div><b>${esc(item.partner.alias)}</b><strong>${esc(item.partner.answer_label)}</strong>${item.partner.comment?`<p>“${esc(item.partner.comment)}”</p>`:''}</div></div></article>`).join('');
  page(`<main class="results"><div class="kicker">Ваши результаты</div><h1>${esc(d.creator.alias)} + ${esc(d.partner.alias)}</h1><div class="result-summary"><span class="green">${d.counts.green} совпадений</span><span class="blue">${d.counts.blue} возможно</span><span class="red">${d.counts.red} с «Нет»</span><span class="neutral">${d.counts.neutral} пропущено</span></div><p class="lead">Это не оценка совместимости. Здесь просто видно, что каждый из вас выбрал и пояснил.</p>${items}</main>`);
}
function inlineError(text){ document.querySelector('.inline-error')?.remove(); const el=document.createElement('div');el.className='notice error inline-error';el.textContent=text; const main=document.querySelector('main')||app;main.prepend(el);el.scrollIntoView({behavior:'smooth',block:'center'}); }
start();
