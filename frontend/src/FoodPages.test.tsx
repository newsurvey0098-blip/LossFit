// @vitest-environment jsdom
import {afterEach,describe,expect,it,vi} from 'vitest';
import {cleanup,render,screen,waitFor} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {MemoryRouter,Route,Routes} from 'react-router-dom';

vi.mock('./api',()=>({api:vi.fn(),authenticatedFetch:vi.fn(),jsonBody:vi.fn(),upload:vi.fn()}));
import {api} from './api';
import {FoodDetailPage,FoodsPage} from './FoodPages';

afterEach(()=>{cleanup();vi.clearAllMocks();window.history.replaceState(null,'','/')});

describe('food detail meal logging',()=>{
 it('shows progress and prevents a rapid repeat write',async()=>{
  const food={id:42,name:'Oat bowl',state:'cooked',verification:'user_provided',kcal:150,protein:5,carbs:27,fat:3,servings:[{id:1,label:'100 g',grams:100,source:'user'}]};
  let finishWrite:(value:unknown)=>void=()=>{};
  vi.mocked(api).mockImplementation((path:string,init?:RequestInit)=>{
   if(path==='/foods/42')return Promise.resolve(food) as never;
   if(path==='/foods/42/recent')return Promise.resolve({}) as never;
   if(path==='/meals'&&init?.method==='POST')return new Promise(resolve=>{finishWrite=resolve}) as never;
   return Promise.resolve([]) as never;
  });
  window.history.pushState(null,'','/foods/42');
  const user=userEvent.setup();
  render(<MemoryRouter initialEntries={['/foods/42']}><Routes><Route path="/foods/:foodId" element={<FoodDetailPage/>}/></Routes></MemoryRouter>);
  await user.selectOptions(await screen.findByLabelText('Choose a serving'),'100 g');
  const add=await screen.findByRole('button',{name:'Add to meal'});
  await user.dblClick(add);
  const busy=await screen.findByRole('button',{name:'Adding…'});
  expect(busy.hasAttribute('disabled')).toBe(true);
  expect(vi.mocked(api).mock.calls.filter(([path,init])=>path==='/meals'&&init?.method==='POST')).toHaveLength(1);
  finishWrite({id:99});
  expect(await screen.findByRole('status')).toBeTruthy();
  expect(screen.getByText('Added to your meal log.')).toBeTruthy();
 });

 it('announces a failed write and allows retry',async()=>{
  const food={id:42,name:'Oat bowl',state:'cooked',verification:'user_provided',kcal:150,protein:5,carbs:27,fat:3,servings:[]};
  let mealWrites=0;
  vi.mocked(api).mockImplementation((path:string,init?:RequestInit)=>{
   if(path==='/foods/42')return Promise.resolve(food) as never;
   if(path==='/foods/42/recent')return Promise.resolve({}) as never;
   if(path==='/meals'&&init?.method==='POST'){
    mealWrites++;
    return mealWrites===1?Promise.reject(new Error('Meal save failed')) as never:Promise.resolve({id:100}) as never;
   }
   return Promise.resolve([]) as never;
  });
  window.history.pushState(null,'','/foods/42');
  const user=userEvent.setup();
  render(<MemoryRouter initialEntries={['/foods/42']}><Routes><Route path="/foods/:foodId" element={<FoodDetailPage/>}/></Routes></MemoryRouter>);
  await user.click(await screen.findByRole('button',{name:'Add to meal'}));
  const alert=await screen.findByRole('alert');
  expect(alert.textContent).toContain('Meal save failed');
  const retry=screen.getByRole('button',{name:'Add to meal'});
  expect((retry as HTMLButtonElement).disabled).toBe(false);
  await user.click(retry);
  expect(await screen.findByText('Added to your meal log.')).toBeTruthy();
  expect(mealWrites).toBe(2);
 });
});

describe('USDA branded catalogue search',()=>{
 it('searches, imports privately and links to the saved food',async()=>{
  const hit={fdc_id:123456,name:'Unsweetened oat drink',brand:'North Farm',package_serving:'240 g',nutrients:{kcal:null,protein:1.2,carbs:6.5,fat:1.5},source_url:'https://fdc.nal.usda.gov/food-details/123456/nutrients'};
  const saved={id:81,name:hit.name,state:'prepared',brand:hit.brand,verification:'imported',kcal:42,protein:1.2,carbs:6.5,fat:1.5};
  vi.mocked(api).mockImplementation(async(path:string,init?:RequestInit)=>{
   if(path==='/food-sources/usda-branded/status')return {available:true} as never;
   if(path.startsWith('/food-sources/usda-branded/search'))return [hit] as never;
   if(path==='/food-sources/usda-branded/123456/import'&&init?.method==='POST')return saved as never;
   if(path.startsWith('/foods?q='))return [] as never;
   return [] as never;
  });
  const user=userEvent.setup();render(<MemoryRouter><FoodsPage/></MemoryRouter>);
  await screen.findByText('Search USDA branded foods');
  await user.type(screen.getByRole('textbox',{name:'Product name or brand'}),'oat drink');
  await user.click(screen.getByRole('button',{name:'Search USDA'}));
  expect(await screen.findByRole('heading',{name:'Unsweetened oat drink'})).toBeTruthy();
  expect(screen.getByText('Calories unavailable')).toBeTruthy();
  await user.click(screen.getByRole('button',{name:'Save Unsweetened oat drink privately'}));
  expect((await screen.findByText(/Saved privately\./)).textContent).toContain('Saved privately.');
  expect(screen.getByRole('link',{name:'Open Unsweetened oat drink'}).getAttribute('href')).toBe('/foods/81');
  expect(api).toHaveBeenCalledWith('/food-sources/usda-branded/123456/import',{method:'POST'});
 });

 it('explains the missing key and keeps manual food entry available',async()=>{
  vi.mocked(api).mockImplementation(async(path:string)=>{
   if(path==='/food-sources/usda-branded/status')return {available:false,message:'USDA Branded search needs a server-side FDC_API_KEY. Barcode lookup and manual entry remain available.'} as never;
   return [] as never;
  });
  render(<MemoryRouter><FoodsPage/></MemoryRouter>);
  expect(await screen.findByText(/server-side FDC_API_KEY/)).toBeTruthy();
  expect(screen.getAllByRole('link',{name:/Add manually/}).some(link=>link.getAttribute('href')==='/foods/new')).toBe(true);
 });
});
