const base='/api/v1';
export async function api<T=any>(path:string,init:RequestInit={}):Promise<T>{
 const csrf=document.cookie.split('; ').find(v=>v.startsWith('lf_csrf='))?.slice(8);
 const res=await fetch(base+path,{...init,credentials:'include',headers:{'Content-Type':'application/json',...(csrf?{'X-CSRF-Token':decodeURIComponent(csrf)}:{}),...init.headers}});
 if(!res.ok){const body=await res.json().catch(()=>({}));throw new Error(body.detail||`Request failed (${res.status})`)}
 return res.status===204?undefined as T:res.json();
}

export async function upload<T=any>(path:string,body:FormData):Promise<T>{
 const csrf=document.cookie.split('; ').find(v=>v.startsWith('lf_csrf='))?.slice(8);
 const headers:Record<string,string>={};if(csrf)headers['X-CSRF-Token']=decodeURIComponent(csrf);
 const res=await fetch(base+path,{method:'POST',body,credentials:'include',headers});
 if(!res.ok){const data=await res.json().catch(()=>({}));throw new Error(data.detail||`Upload failed (${res.status})`)}
 return res.json();
}
