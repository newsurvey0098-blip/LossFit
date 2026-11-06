// @vitest-environment jsdom
import {afterEach,describe,expect,it,vi} from 'vitest';
import {cleanup,render,screen,waitFor} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {MemoryRouter} from 'react-router-dom';

vi.mock('./api',()=>({api:vi.fn(),authenticatedFetch:vi.fn(),jsonBody:vi.fn(),upload:vi.fn()}));
import {api} from './api';
import {FoodsPage} from './FoodPages';

afterEach(()=>{cleanup();vi.clearAllMocks()});

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
  expect(screen.getByRole('link',{name:/Add manually/}).getAttribute('href')).toBe('/foods/new');
 });
});
