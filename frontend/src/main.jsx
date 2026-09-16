import React, {useEffect, useMemo, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {Copy, Heart, Link2, LockKeyhole, Sparkles, TriangleAlert} from 'lucide-react';
import './styles.css';

const API = import.meta.env.VITE_API_URL || ''; // production: same origin as FastAPI
const qs = new URLSearchParams(location.search);
const initialToken = qs.get('token') || '';

async function api(path, options={}) {
  const headers = {'Content-Type':'application/json', ...(options.headers||{})};
  const token = sessionStorage.getItem('uself-token') || initialToken;
  if (token) headers['X-Participant-Token'] = token;
  const r = await fetch(API+path, {...options, headers});
  if (!r.ok) throw new Error((await r.json().catch(()=>({}))).detail || 'Ошибка запроса');
  return r.json();
}

function App(){
  const [token,setToken]=useState(initialToken);
  const [created,setCreated]=useState(null);
  const [me,setMe]=useState(null);
  const [questions,setQuestions]=useState([]);
  const [idx,setIdx]=useState(0);
  const [results,setResults]=useState(null);
  const [error,setError]=useState('');
  const [aliases,setAliases]=useState({creator_alias:'Я',partner_alias:'Партнёр'});

  useEffect(()=>{ if(initialToken){sessionStorage.setItem('uself-token',initialToken); setToken(initialToken);} },[]);
  useEffect(()=>{ if(token) load(); },[token]);
  async function load(){
    try{ setError(''); const m=await api('/me'); setMe(m); const q=await api('/questions'); setQuestions(q); const first=q.findIndex(x=>!x.answer); setIdx(first>=0?first:Math.max(0,q.length-1)); if(m.status==='completed') setResults(await api('/results')); }
    catch(e){setError(e.message)}
  }
  async function create(){
    try{ setError(''); const d=await api('/sessions',{method:'POST',body:JSON.stringify(aliases)}); const origin=window.location.origin; setCreated({...d, creator_url:new URL(d.creator_url, origin).toString(), partner_url:new URL(d.partner_url, origin).toString()}); }
    catch(e){setError(e.message)}
  }
  async function answer(value){
    const q=questions[idx]; if(!q) return;
    try{ await api('/answers',{method:'PUT',body:JSON.stringify({session_question_id:q.id,value})}); const next=[...questions]; next[idx]={...q,answer:value}; setQuestions(next); if(idx<next.length-1) setIdx(idx+1); setMe(m=>({...m,answered:new Set(next.filter(x=>x.answer).map(x=>x.id)).size})); }
    catch(e){setError(e.message)}
  }
  async function submit(){ try{await api('/submit',{method:'POST',body:JSON.stringify({confirm:true})}); await load();}catch(e){setError(e.message)} }
  if(!token) return <Landing aliases={aliases} setAliases={setAliases} create={create} created={created} error={error}/>;
  if(!me) return <Shell><p>Загрузка…</p>{error&&<Error text={error}/>}</Shell>;
  if(me.status==='completed') return <Results data={results} reload={async()=>setResults(await api('/results'))}/>;
  const q=questions[idx];
  const progress=me.total?Math.round((me.answered/me.total)*100):0;
  return <Shell>
    <div className="topline"><span>{me.alias}</span><span>{me.answered}/{me.total}</span></div>
    <div className="progress"><i style={{width:progress+'%'}}/></div>
    {q && <div className="question-card">
      <div className="eyebrow">{q.category}{q.block?` · ${q.block}`:''}</div>
      <h1>{q.text}</h1>
      {q.direction && <div className="direction">{q.direction}</div>}
      {q.safety_note && <div className="warning"><TriangleAlert size={18}/><span>{q.safety_note}</span></div>}
      <div className="answers">
        <button className={q.answer==='yes'?'selected':''} onClick={()=>answer('yes')}>Да</button>
        <button className={q.answer==='maybe'?'selected':''} onClick={()=>answer('maybe')}>Возможно</button>
        <button className={q.answer==='no'?'selected':''} onClick={()=>answer('no')}>Нет</button>
      </div>
      <div className="nav"><button disabled={idx===0} onClick={()=>setIdx(i=>i-1)}>← Назад</button><button disabled={idx===questions.length-1} onClick={()=>setIdx(i=>i+1)}>Дальше →</button></div>
    </div>}
    {me.answered===me.total && me.total>0 && <button className="submit" onClick={submit}>Завершить и ждать совпадения</button>}
    {error&&<Error text={error}/>} 
  </Shell>
}

function Landing({aliases,setAliases,create,created,error}){
  return <Shell wide>
    <div className="hero"><div className="brand"><Sparkles size={18}/> USelf · prototype 0.1</div><h1>Узнайте, что вам обоим действительно интересно.</h1><p>Отвечайте независимо. Мы не показываем ваши «нет» друг другу — в результате видны только взаимные интересы и зоны, которые можно обсудить.</p></div>
    {!created ? <div className="panel"><div className="privacy"><LockKeyhole/> Приватные ответы · только совпадения</div><label>Как назвать тебя?<input value={aliases.creator_alias} onChange={e=>setAliases({...aliases,creator_alias:e.target.value})}/></label><label>Как назвать второго участника?<input value={aliases.partner_alias} onChange={e=>setAliases({...aliases,partner_alias:e.target.value})}/></label><button className="primary" onClick={create}>Создать совместный тест</button></div> : <div className="panel"><h2>Комната создана</h2><Share title="Твоя приватная ссылка" url={created.creator_url}/><Share title="Ссылка для партнёра" url={created.partner_url}/><a className="primary linkbutton" href={created.creator_url}>Начать свой тест</a><small>Не пересылай свою ссылку партнёру: она даёт доступ именно к твоим ответам.</small></div>}
    {error&&<Error text={error}/>} 
  </Shell>
}
function Share({title,url}){return <div className="share"><span>{title}</span><div><input readOnly value={url}/><button onClick={()=>navigator.clipboard.writeText(url)}><Copy size={18}/></button></div></div>}
function Results({data,reload}){
  if(!data) return <Shell><p>Загрузка результатов…</p></Shell>;
  if(!data.ready) return <Shell><div className="result-wait"><Heart/><h1>Твоя часть готова</h1><p>{data.message}</p><button className="primary" onClick={reload}>Проверить ещё раз</button></div></Shell>;
  return <Shell wide><div className="hero compact"><div className="brand"><Heart size={18}/> Совпадения</div><h1>{data.match_count} взаимных интересов</h1><p>Здесь нет чужих отказов. Только то, где оба ответили «Да» или «Возможно».</p></div>{data.categories.map(cat=><section className="result-section" key={cat.name}><h2>{cat.name}<span>{cat.matches.length}</span></h2>{cat.matches.map(m=><article className={`match ${m.strength}`} key={m.id}><div><b>{m.strength==='strong'?'Совпало':m.strength==='explore'?'Стоит обсудить':'Оба допускаете'}</b>{m.block&&<small>{m.block}</small>}</div><p>{m.text}</p>{m.direction&&<em>{m.direction}</em>}{m.safety_note&&<div className="warning"><TriangleAlert size={16}/>{m.safety_note}</div>}</article>)}</section>)}</Shell>
}
function Shell({children,wide=false}){return <main className={wide?'shell wide':'shell'}>{children}<footer>USelf · исследуйте желания бережно и по взаимному согласию</footer></main>}
function Error({text}){return <div className="error">{text}</div>}
createRoot(document.getElementById('root')).render(<App/>);
