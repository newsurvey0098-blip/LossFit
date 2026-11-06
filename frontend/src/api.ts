const base='/api/v1';
let accessToken:string|null=null;
let refreshFlight:Promise<string|null>|null=null;

export function setAccessToken(token:string|null){accessToken=token;}
export function getAccessToken(){return accessToken;}

export async function responseError(response:Response):Promise<Error>{
 const body:unknown=await response.json().catch(()=>null);
 const detail=body&&typeof body==='object'&&'detail' in body?body.detail:null;
 if(typeof detail==='string'&&detail.trim())return new Error(detail);
 if(Array.isArray(detail)){
  const messages=detail.slice(0,5).flatMap(issue=>{
   if(!issue||typeof issue!=='object'||typeof issue.msg!=='string')return [];
   const field=Array.isArray(issue.loc)?issue.loc.filter((part:unknown)=>typeof part==='string'&&!['body','query','path'].includes(part)).join(' → '):'';
   return [field?`${field}: ${issue.msg}`:issue.msg];
  });
  if(messages.length)return new Error(messages.join('; '));
 }
 return new Error(`Request failed (${response.status}). Please try again.`);
}

function csrfHeaders():Record<string,string>{
 const csrf=document.cookie.split('; ').find(value=>value.startsWith('lf_csrf='))?.slice(8);
 return csrf?{'X-CSRF-Token':decodeURIComponent(csrf)}:{};
}

async function refreshToken():Promise<string|null>{
 if(refreshFlight)return refreshFlight;
 refreshFlight=(async()=>{
  try{
   const rotate=async()=>{
    const response=await fetch(`${base}/auth/refresh`,{method:'POST',credentials:'include',headers:csrfHeaders()});
    if(!response.ok){accessToken=null;return null;}
    const result=await response.json();accessToken=result.access_token;return accessToken;
   };
   // The in-module promise coalesces requests in one document. A Web Lock also
   // serializes rotations across reloads and same-origin tabs, where separate
   // JS contexts otherwise could replay the same single-use refresh cookie.
   if(navigator.locks?.request)return await navigator.locks.request('lossfit-refresh-token',rotate);
   return await rotate();
  }catch{accessToken=null;return null;}
  finally{refreshFlight=null;}
 })();
 return refreshFlight;
}

const noRefreshPaths=['/auth/login','/auth/register','/auth/forgot-password','/auth/reset-password','/auth/refresh','/auth/logout'];
function shouldRefresh(path:string){return !noRefreshPaths.some(route=>path===route||path.startsWith(route+'?'));}

export async function authenticatedFetch(path:string,init:RequestInit={}):Promise<Response>{
 if(!accessToken&&shouldRefresh(path))await refreshToken();
 const send=()=>fetch(base+path,{...init,credentials:'include',headers:{...(init.body instanceof FormData?{}:{'Content-Type':'application/json'}),...csrfHeaders(),...(accessToken?{Authorization:`Bearer ${accessToken}`} : {}),...init.headers}});
 let response=await send();
 if(response.status===401&&accessToken&&shouldRefresh(path)){
  const refreshed=await refreshToken();
  if(refreshed)response=await send();
 }
 if(response.ok&&(['/auth/logout','/auth/reset-password','/account'].includes(path)))accessToken=null;
 return response;
}

export async function api<T=any>(path:string,init:RequestInit={}):Promise<T>{
 const response=await authenticatedFetch(path,init);
 if(!response.ok)throw await responseError(response);
 return response.status===204?undefined as T:response.json();
}

export async function upload<T=any>(path:string,body:FormData):Promise<T>{
 const response=await authenticatedFetch(path,{method:'POST',body});
 if(!response.ok)throw await responseError(response);
 return response.json();
}
