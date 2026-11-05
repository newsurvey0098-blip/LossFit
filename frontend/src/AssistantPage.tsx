import React from 'react';
import {Link,useNavigate,useParams} from 'react-router-dom';
import {Plus,Trash2,Send,Sparkles,RotateCw,MessageCircle} from 'lucide-react';
import {api} from './api';
import AssistantActionPanel from './AssistantActions';

type Conversation={id:number;title:string;updated_at:string};
type Message={id:number;role:'user'|'assistant';content:string;citations?:{ref:string;title:string;organization:string;url:string;version:number}[];created_at:string};

export default function AssistantPage(){const {conversationId}=useParams();return <AssistantConversation key={conversationId??'new'}/>;}

function AssistantConversation(){
 const {conversationId}=useParams();const nav=useNavigate();
 const [list,setList]=React.useState<Conversation[]>([]);const [messages,setMessages]=React.useState<Message[]>([]);
 const [text,setText]=React.useState('');const [error,setError]=React.useState('');const [busy,setBusy]=React.useState(false);
 const [historyLoading,setHistoryLoading]=React.useState(Boolean(conversationId));const [historyFailed,setHistoryFailed]=React.useState(false);const [historyRetry,setHistoryRetry]=React.useState(0);const replyController=React.useRef<AbortController|null>(null);
 React.useEffect(()=>()=>replyController.current?.abort(),[]);
 const [pending,setPending]=React.useState<{prompt:string;key:string}|null>(null);
 async function refreshList(){try{setList(await api('/assistant/conversations'))}catch(e:any){setError(e.message)}}
 React.useEffect(()=>{void refreshList()},[]);
 React.useEffect(()=>{
  let active=true;const controller=new AbortController();setHistoryLoading(Boolean(conversationId));setHistoryFailed(false);
  if(conversationId){api<any>(`/assistant/conversations/${conversationId}`,{signal:controller.signal}).then(c=>{if(active){setMessages(c.messages);setError('')}}).catch(e=>{if(active){setError(e.message);setHistoryFailed(true)}}).finally(()=>active&&setHistoryLoading(false))}
  else setMessages([]);
  return()=>{active=false;controller.abort()};
 },[conversationId,historyRetry]);
 async function create(){try{const c=await api<Conversation>('/assistant/conversations',{method:'POST'});await refreshList();nav(`/assistant/${c.id}`)}catch(e:any){setError(e.message)}}
 async function send(){
  if(!conversationId||!text.trim()||busy||historyLoading||historyFailed)return;
  const prompt=text.trim();const request=pending?.prompt===prompt?pending:{prompt,key:crypto.randomUUID()};
  const controller=new AbortController();replyController.current=controller;setPending(request);setBusy(true);setError('');
  try{await api('/assistant',{method:'POST',body:JSON.stringify({conversation_id:Number(conversationId),message:prompt,idempotency_key:request.key}),signal:controller.signal});setMessages(await api<Message[]>(`/assistant/conversations/${conversationId}`,{signal:controller.signal}).then((x:any)=>x.messages));setText('');setPending(null);await refreshList()}
  catch(e:any){setError(controller.signal.aborted?'Stopped waiting for the reply. The server may still finish it; Retry checks the same request without duplicating it.':e.message)}finally{setBusy(false);replyController.current=null}
 }
 async function remove(id:number){if(!window.confirm('Delete this conversation and its messages?'))return;try{await api(`/assistant/conversations/${id}`,{method:'DELETE'});await refreshList();if(String(id)===conversationId)nav('/assistant')}catch(e:any){setError(e.message)}}
 async function clearAll(){if(!window.confirm('Delete all of your assistant conversations?'))return;try{await api('/assistant/conversations',{method:'DELETE'});setList([]);setMessages([]);nav('/assistant')}catch(e:any){setError(e.message)}}
 return <div className="assistant-layout">
  <aside className="card conversation-list"><div className="sectionhead"><h2>Conversations</h2><button className="icon" aria-label="New conversation" onClick={create}><Plus size={18}/></button></div><button className="button primary newchat" onClick={create}><Plus size={16}/> New conversation</button>{list.length>0&&<button className="textlink clearchat" onClick={clearAll}><Trash2 size={14}/> Clear all</button>}<div className="conversation-items">{list.map(c=><div className={`conversation-item ${String(c.id)===conversationId?'selected':''}`} key={c.id}><Link to={`/assistant/${c.id}`}><MessageCircle size={15}/><span>{c.title}</span></Link><button aria-label={`Delete ${c.title}`} onClick={()=>remove(c.id)}><Trash2 size={14}/></button></div>)}</div></aside>
  <section className="card assistant-chat"><header><span className="watericon"><Sparkles size={18}/></span><div><h2>Nutrition assistant</h2><small className="muted">Personalized using your logged nutrition</small></div></header>
   <div className="chat-messages" aria-live="polite">{historyLoading?<p role="status">Loading conversation history…</p>:historyFailed?<button className="button" onClick={()=>setHistoryRetry(v=>v+1)}>Retry history</button>:!conversationId?<div className="chat-empty"><Sparkles size={26}/><h2>Ask about your nutrition</h2><p className="muted">Create a conversation to ask about today’s food log or learn a nutrition concept.</p><button className="button primary" onClick={create}>Start a conversation</button></div>:messages.length===0?<div className="chat-empty"><Sparkles size={24}/><h2>How can I help?</h2><p className="muted">I can explain your nutrition log and help you log food or water.</p></div>:messages.map(m=><article key={m.id} className={`bubble ${m.role}`}><span className="bubble-label">{m.role==='user'?'You':'LossFit'}</span><p>{m.content}</p>{Boolean(m.citations?.length)&&<ul className="chat-citations" aria-label="Sources for this answer">{m.citations!.map(source=><li key={`${source.ref}-${source.url}`}><a href={source.url} target="_blank" rel="noreferrer">[{source.ref}] {source.title}</a><small>{source.organization} · source version {source.version}</small></li>)}</ul>}</article>)}</div>
   {conversationId&&!historyLoading&&!historyFailed&&<AssistantActionPanel key={conversationId} conversationId={Number(conversationId)}/>}
   {error&&<div className="chat-error" role="alert">{error}{text&&<button className="button" onClick={send} disabled={busy}><RotateCw size={14}/> Retry</button>}</div>}
   {busy&&<button type="button" className="button" onClick={()=>replyController.current?.abort()}>Stop waiting</button>}
   {conversationId&&<form className="chat-compose" onSubmit={e=>{e.preventDefault();void send()}}><textarea disabled={busy||historyLoading||historyFailed} aria-label="Message the nutrition assistant" rows={2} maxLength={4000} value={text} onChange={e=>setText(e.target.value)} placeholder="Ask about your food and nutrition…"/><button className="button primary" disabled={busy||historyLoading||historyFailed||!text.trim()} aria-label={busy?'Assistant is replying':'Send message'}>{busy?'…':<Send size={17}/>}</button></form>}
  </section>
 </div>
}
