/** @vitest-environment jsdom */
import {afterEach,expect,it,vi} from 'vitest';
import {api,responseError,upload,setAccessToken} from './api';
afterEach(()=>{vi.unstubAllGlobals();setAccessToken(null)});

it('renders structured field errors without including rejected inputs or validation context',async()=>{
 const response=new Response(JSON.stringify({detail:[{loc:['body','password'],msg:'String should have at least 10 characters',input:'private-secret',ctx:{secret:'hidden-context'}}]}),{status:422});
 vi.stubGlobal('fetch',vi.fn().mockResolvedValue(response));
 await expect(api('/auth/register',{method:'POST',body:'{}'})).rejects.toEqual(new Error('password: String should have at least 10 characters'));
});

it('uses the same readable error handling for uploads',async()=>{
 setAccessToken('test-access');
 vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify({detail:'Image exceeds the permitted dimensions'}),{status:422})));
 await expect(upload('/scans',new FormData())).rejects.toThrow('Image exceeds the permitted dimensions');
});

it('serializes refresh-token rotation with the browser-wide lock',async()=>{
 const lockRequest=vi.fn(async(_name:string,callback:()=>Promise<string|null>)=>callback());
 vi.stubGlobal('navigator',{locks:{request:lockRequest}});
 vi.stubGlobal('fetch',vi.fn(async(input:RequestInfo|URL)=>String(input).endsWith('/auth/refresh')
  ?new Response(JSON.stringify({access_token:'fresh-access'}),{status:200})
  :new Response(JSON.stringify({user:'ok'}),{status:200})));
 await expect(api('/auth/me')).resolves.toEqual({user:'ok'});
 expect(lockRequest).toHaveBeenCalledWith('lossfit-refresh-token',expect.any(Function));
});

it('handles non-JSON outages and unexpected detail objects without displaying raw response bodies',async()=>{
 const outage=await responseError(new Response('upstream internal diagnostics',{status:502}));
 expect(outage.message).toBe('Request failed (502). Please try again.');
 const malformed=await responseError(new Response(JSON.stringify({detail:{private:'not for display'}}),{status:500}));
 expect(malformed.message).toBe('Request failed (500). Please try again.');
});
