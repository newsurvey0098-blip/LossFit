/** @vitest-environment jsdom */
import React from 'react';
import {afterEach,expect,it,vi} from 'vitest';
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {MemoryRouter,Route,Routes} from 'react-router-dom';
import AssistantPage from './AssistantPage';
import {api} from './api';
vi.mock('./api',()=>({api:vi.fn()}));
vi.mock('./AssistantActions',()=>({default:()=>null}));
afterEach(()=>{cleanup();vi.resetAllMocks()});
const list=[{id:1,title:'First'},{id:2,title:'Second'}];
const history=(content:string)=>({messages:[{id:1,role:'assistant',content}]});
function mount(){render(<MemoryRouter initialEntries={['/assistant/1']}><Routes><Route path='/assistant/:conversationId' element={<AssistantPage/>}/></Routes></MemoryRouter>)}

it('keeps composing disabled until failed history loading is retried successfully',async()=>{
 let attempts=0;
 vi.mocked(api).mockImplementation(async(path)=>{
  if(path==='/assistant/conversations')return list;
  if(++attempts===1)throw new Error('History service unavailable');
  return history('Recovered history');
 });
 mount();await screen.findByRole('alert');
 expect((screen.getByRole('textbox') as HTMLTextAreaElement).disabled).toBe(true);
 fireEvent.click(screen.getByRole('button',{name:'Retry history'}));
 await screen.findByText('Recovered history');
 expect((screen.getByRole('textbox') as HTMLTextAreaElement).disabled).toBe(false);
});

it('never displays a late response from the previously selected conversation',async()=>{
 let finish!:(value:unknown)=>void;const slow=new Promise(resolve=>{finish=resolve});
 vi.mocked(api).mockImplementation(async(path)=>path==='/assistant/conversations'?list:path.endsWith('/1')?slow:history('Second history'));
 mount();fireEvent.click(await screen.findByRole('link',{name:'Second'}));
 await screen.findByText('Second history');
 await act(async()=>finish(history('First private history')));
 expect(screen.queryByText('First private history')).toBeNull();
 expect(screen.getByText('Second history')).toBeTruthy();
});

it('retains the idempotency key when stopping a reply and retrying',async()=>{
 const keys:string[]=[];
 vi.mocked(api).mockImplementation(async(path,init)=>{
  if(path==='/assistant/conversations')return list;
  if(path==='/assistant'){
   keys.push(JSON.parse(String(init?.body)).idempotency_key);
   if(keys.length===1)return new Promise((_,reject)=>init?.signal?.addEventListener('abort',()=>reject(new DOMException('Aborted','AbortError'))));
   return {message:'Recovered reply'};
  }
  return history('Existing history');
 });
 mount();await screen.findByText('Existing history');
 fireEvent.change(screen.getByRole('textbox'),{target:{value:'Explain my lunch'}});
 fireEvent.click(screen.getByRole('button',{name:'Send message'}));
 fireEvent.click(await screen.findByRole('button',{name:'Stop waiting'}));
 await screen.findByRole('alert');
 fireEvent.click(screen.getByRole('button',{name:'Retry'}));
 await waitFor(()=>expect(keys).toHaveLength(2));
 expect(keys[1]).toBe(keys[0]);
});

it('keeps the unsent message and retries with the same key after a provider outage',async()=>{
 const keys:string[]=[];let sends=0;
 vi.mocked(api).mockImplementation(async(path,init)=>{
  if(path==='/assistant/conversations')return list;
  if(path==='/assistant/conversations/1')return history(sends>1?'Recovered after provider outage':'Existing history');
  if(path==='/auth/me')return {preferences:{units:'metric'}};
  if(path==='/assistant'){
   keys.push(JSON.parse(String(init?.body)).idempotency_key);
   sends++;
   if(sends===1)throw new Error('The AI provider is unavailable or returned an invalid response. Your message was not saved; please retry.');
   return {message:'Recovered reply'};
  }
  return undefined;
 });
 mount();await screen.findByText('Existing history');
 const composer=screen.getByRole('textbox');
 fireEvent.change(composer,{target:{value:'Can you explain my lunch?'}});
 fireEvent.click(screen.getByRole('button',{name:'Send message'}));
 expect((await screen.findByRole('alert')).textContent).toContain('Your message was not saved');
 expect((composer as HTMLTextAreaElement).value).toBe('Can you explain my lunch?');
 fireEvent.click(screen.getByRole('button',{name:'Retry'}));
 await screen.findByText('Recovered after provider outage');
 expect(keys).toHaveLength(2);
 expect(keys[1]).toBe(keys[0]);
 expect((composer as HTMLTextAreaElement).value).toBe('');
});
