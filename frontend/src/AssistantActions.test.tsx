// @vitest-environment jsdom
import React from 'react';
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AssistantActionPanel from './AssistantActions';
import {setAccessToken} from './api';

function jsonResponse(payload:unknown,status=200){return new Response(JSON.stringify(payload),{status,headers:{'Content-Type':'application/json'}})}
let fetchMock:ReturnType<typeof vi.fn>;

beforeEach(()=>{setAccessToken('frontend-test-token');fetchMock=vi.fn();vi.stubGlobal('fetch',fetchMock)});
afterEach(()=>{cleanup();setAccessToken(null);vi.unstubAllGlobals()});

describe('assistant action confirmation',()=>{
 it('previews water without writing, then confirms once',async()=>{
  fetchMock.mockImplementation(async(input:RequestInfo|URL,init?:RequestInit)=>{
   const path=String(input);
   if(path.endsWith('/assistant/actions/preview'))return jsonResponse({id:'water-action-12345678901234567890',action:'log_water',status:'pending',preview:{water_ml:250,today_total_before_ml:400,today_total_after_ml:650,local_date:'2026-11-06'},result:null});
   if(path.endsWith('/assistant/actions/water-action-12345678901234567890/confirm'))return jsonResponse({id:'water-action-12345678901234567890',action:'log_water',status:'confirmed',preview:{water_ml:250,today_total_before_ml:400,today_total_after_ml:650,local_date:'2026-11-06'},result:{water_entry_id:51,water_ml:250}});
   throw new Error(`Unexpected fetch ${path} ${init?.method??'GET'}`);
  });
  const user=userEvent.setup();render(<AssistantActionPanel conversationId={9}/>);
  await user.click(screen.getByRole('button',{name:'Preview'}));
  expect(await screen.findByRole('group',{name:'Review action before confirmation'})).toBeTruthy();
  expect(screen.getByText(/400 ml to 650 ml/)).toBeTruthy();
  expect(fetchMock).toHaveBeenCalledTimes(1);
  await user.click(screen.getByRole('button',{name:'Confirm log'}));
  expect((await screen.findByRole('status')).textContent).toContain('Logged 250 ml. Today’s water total is 0.7 L.');
  expect(fetchMock).toHaveBeenCalledTimes(2);
  const confirmInit=fetchMock.mock.calls[1][1] as RequestInit;
  expect(confirmInit.method).toBe('POST');
 });

 it('shows server-calculated meal nutrition and waits for confirmation',async()=>{
  fetchMock.mockImplementation(async(input:RequestInfo|URL,init?:RequestInit)=>{
   const path=String(input);
   if(path.includes('/foods?q='))return jsonResponse([{id:84,name:'Brown rice, cooked',state:'cooked',kcal:123,protein:2.7,carbs:25.6,fat:1,verification:'reviewed'}]);
   if(path.endsWith('/assistant/actions/preview'))return jsonResponse({id:'meal-action-12345678901234567890',action:'log_meal',status:'pending',preview:{name:'Lunch',meal_type:'lunch',eaten_at:'2026-11-06T10:00:00+00:00',items:[{name:'Brown rice, cooked',state:'cooked',grams:150,per100:{kcal:123,protein:2.7,carbs:25.6,fat:1},verification:'reviewed',source:'USDA'}],totals:{kcal:184.5,protein:4.05,carbs:38.4,fat:1.5}},result:null});
   if(path.endsWith('/assistant/actions/meal-action-12345678901234567890/confirm'))return jsonResponse({id:'meal-action-12345678901234567890',action:'log_meal',status:'confirmed',preview:{name:'Lunch',items:[],totals:{kcal:184.5}},result:{meal_id:19,name:'Lunch',kcal:184.5}});
   throw new Error(`Unexpected fetch ${path} ${init?.method??'GET'}`);
  });
  const user=userEvent.setup();render(<AssistantActionPanel conversationId={12}/>);
  await user.click(screen.getByRole('button',{name:'Log a meal'}));
  fireEvent.change(screen.getByLabelText('Meal name'),{target:{value:'Lunch'}});
  fireEvent.change(screen.getByLabelText('Search your food catalogue'),{target:{value:'brown rice'}});
  await waitFor(()=>expect(fetchMock).toHaveBeenCalledTimes(1));
  await user.selectOptions(await screen.findByLabelText('Select food'), '84');
  fireEvent.change(screen.getByLabelText('Portion weight'),{target:{value:'150'}});
  await user.click(screen.getByRole('button',{name:'Preview meal'}));
  expect((await screen.findByText(/Meal total:/)).textContent).toContain('185 kcal');
  expect(fetchMock).toHaveBeenCalledTimes(2);
  await user.click(screen.getByRole('button',{name:'Confirm log'}));
  expect((await screen.findByRole('status')).textContent).toContain('Lunch was added to your meal log. Calories: 185 kcal.');
  expect(fetchMock).toHaveBeenCalledTimes(3);
  const previewInit=fetchMock.mock.calls[1][1] as RequestInit;
  const request=JSON.parse(String(previewInit.body));
  expect(request.action).toBe('log_meal');expect(request.meal.items[0]).toMatchObject({food_id:84,grams:150});
 });
});
