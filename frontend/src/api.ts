const base='/api/v1';
let accessToken:string|null=null;
let refreshFlight:Promise<string|null>|null=null;

export function setAccessToken(token:string|null){accessToken=token;}
export function getAccessToken(){return accessToken;}

function csrfHeaders():Record<string,string>{
 const csrf=document.cookie.split('; ').find(value=>value.startsWith('lf_csrf='))?.slice(8);
 return csrf?{'X-CSRF-Token':decodeURIComponent(csrf)}:{};
}

async function refreshToken():Promise<string|null>{
 if(refreshFlight)return refreshFlight;
 refreshFlight=(async()=>{
  try{
   const response=await fetch(`${base}/auth/refresh`,{method:'POST',credentials:'include',headers:csrfHeaders()});
   if(!response.ok){accessToken=null;return null;}
   const result=await response.json();accessToken=result.access_token;return accessToken;
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
 if(!response.ok){const body=await response.json().catch(()=>({}));throw new Error(body.detail||`Request failed (${response.status})`)}
 return response.status===204?undefined as T:response.json();
}

export async function upload<T=any>(path:string,body:FormData):Promise<T>{
 const response=await authenticatedFetch(path,{method:'POST',body});
 if(!response.ok){const data=await response.json().catch(()=>({}));throw new Error(data.detail||`Upload failed (${response.status})`)}
 return response.json();
}
