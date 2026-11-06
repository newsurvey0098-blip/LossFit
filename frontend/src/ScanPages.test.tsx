/** @vitest-environment jsdom */
import React from 'react';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {MemoryRouter,Route,Routes} from 'react-router-dom';
import {NutritionLabelPage,ScannerPage,ScannerReviewPage} from './ScanPages';
import {api,authenticatedFetch,upload} from './api';
vi.mock('./api',()=>({api:vi.fn(),authenticatedFetch:vi.fn(),upload:vi.fn()}));
beforeEach(()=>{vi.resetAllMocks();URL.createObjectURL=vi.fn(()=> 'blob:private-photo');URL.revokeObjectURL=vi.fn()});
afterEach(cleanup);

it('offers retry when scanner availability fails and keeps analysis disabled',async()=>{
 vi.mocked(api).mockRejectedValueOnce(new Error('Service unavailable')).mockResolvedValueOnce({available:false});
 render(<MemoryRouter><ScannerPage/></MemoryRouter>);
 expect((await screen.findByRole('alert')).textContent).toContain('Service unavailable');
 expect((screen.getByRole('button',{name:'Analyze meal'}) as HTMLButtonElement).disabled).toBe(true);
 fireEvent.click(screen.getByRole('button',{name:'Retry scanner check'}));
 await waitFor(()=>expect(screen.getByRole('status').textContent).toContain('not configured'));
});

it('searches beyond initial foods and preserves a selected match through later searches',async()=>{
 const food={id:90,name:'Rare cooked lentils',state:'cooked',verification:'reviewed',kcal:116,servings:[]};
 vi.mocked(api).mockImplementation(async(path)=>path==='/scans/4'?{id:4,status:'needs_review',candidates:[{id:'0',name:'lentils',grams:120,matches:[]}]}:path.includes('rare')?[food]:[]);
 vi.mocked(authenticatedFetch).mockResolvedValue({ok:true,blob:async()=>new Blob(['photo'])} as Response);
 render(<MemoryRouter initialEntries={['/scan/review/4']}><Routes><Route path='/scan/review/:scanId' element={<ScannerReviewPage/>}/></Routes></MemoryRouter>);
 const search=await screen.findByLabelText('Search the full food catalogue');
 fireEvent.change(search,{target:{value:'rare'}});
 await screen.findAllByRole('option',{name:'Rare cooked lentils · cooked'});
 fireEvent.change(screen.getByLabelText('Match a catalogue food'),{target:{value:'90'}});
 fireEvent.change(search,{target:{value:'another'}});
 await waitFor(()=>expect(api).toHaveBeenCalledWith('/foods?q=another'));
 expect((screen.getByLabelText('Match a catalogue food') as HTMLSelectElement).value).toBe('90');
 expect((screen.getByRole('button',{name:'Add reviewed meal'}) as HTMLButtonElement).disabled).toBe(false);
});

it('reviews and edits AI label extraction before saving per-serving values',async()=>{
 vi.mocked(api).mockImplementation(async(path)=>path==='/labels/status'?{available:true}:path==='/foods/from-label'?{id:42}:{});
 vi.mocked(upload).mockResolvedValue({name:'Browser label granola',brand:'Test',serving_label:'1 bar',serving_grams:125,basis:'per_serving',kcal:100,protein:8,carbs:12,fat:null});
 render(<MemoryRouter><NutritionLabelPage/></MemoryRouter>);
 const image=new File([new Uint8Array([1,2,3])],'label.png',{type:'image/png'});
 fireEvent.change(screen.getByLabelText('Package label photo'),{target:{files:[image]}});
 fireEvent.click(await screen.findByRole('button',{name:'Read label with AI'}));
 await screen.findByDisplayValue('Browser label granola');
 expect((screen.getByLabelText('Calories (kcal)') as HTMLInputElement).value).toBe('100');
 expect((screen.getByLabelText('Fat (g)') as HTMLInputElement).value).toBe('');
 fireEvent.change(screen.getByLabelText('Calories (kcal)'),{target:{value:'125'}});
 fireEvent.click(screen.getByRole('button',{name:'Save reviewed label food'}));
 await waitFor(()=>expect(api).toHaveBeenCalledWith('/foods/from-label',expect.objectContaining({method:'POST'})));
 const payload=JSON.parse(vi.mocked(api).mock.calls.find(([path])=>path==='/foods/from-label')![1]!.body as string);
 expect(payload).toMatchObject({name:'Browser label granola',brand:'Test',serving_grams:125,basis:'per_serving',kcal:125,protein:8,carbs:12,fat:null});
});
