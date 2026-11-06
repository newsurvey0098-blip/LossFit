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
 it('previews a weight without writing and saves it only after confirmation',async()=>{
  fetchMock.mockImplementation(async(input:RequestInfo|URL)=>{
   const path=String(input);
   if(path.endsWith('/assistant/actions/preview'))return jsonResponse({id:'weight-action-123456789012345678',action:'log_weight',status:'pending',preview:{weight_kg:68.4,previous_weight_kg:70,previous_recorded_at:'2026-11-05T12:00:00+00:00',recorded_at:'2026-11-06T12:00:00+00:00',unit:'kg'},result:null});
   if(path.endsWith('/assistant/actions/weight-action-123456789012345678/confirm'))return jsonResponse({id:'weight-action-123456789012345678',action:'log_weight',status:'confirmed',preview:{weight_kg:68.4},result:{weight_id:51,weight_kg:68.4}});
   throw new Error(`Unexpected fetch ${path}`);
  });
  const user=userEvent.setup();render(<AssistantActionPanel conversationId={9}/>);
  await user.click(screen.getByRole('button',{name:'Log weight'}));
  fireEvent.change(screen.getByLabelText('Weight (kg)'),{target:{value:'68.4'}});
  await user.click(screen.getByRole('button',{name:'Preview'}));
  expect(await screen.findByText(/Latest entry: 70\.0 kg/)).toBeTruthy();
  expect(fetchMock).toHaveBeenCalledTimes(1);
  const request=JSON.parse(String((fetchMock.mock.calls[0][1] as RequestInit).body));
  expect(request).toMatchObject({action:'log_weight',weight_kg:68.4});
  await user.click(screen.getByRole('button',{name:'Confirm log'}));
  expect((await screen.findByRole('status')).textContent).toContain('Logged 68.4 kg. Your weight history and profile were updated.');
  expect(fetchMock).toHaveBeenCalledTimes(2);
 });

 it('shows imperial units and submits a canonical kilogram weight',async()=>{
  fetchMock.mockImplementation(async(input:RequestInfo|URL)=>{
   const path=String(input);
   if(path.endsWith('/assistant/actions/preview'))return jsonResponse({id:'imperial-weight-action-123456',action:'log_weight',status:'pending',preview:{weight_kg:68.4,previous_weight_kg:70,recorded_at:'2026-11-06T12:00:00+00:00'},result:null});
   if(path.endsWith('/assistant/actions/imperial-weight-action-123456/confirm'))return jsonResponse({id:'imperial-weight-action-123456',action:'log_weight',status:'confirmed',preview:{weight_kg:68.4},result:{weight_id:52,weight_kg:68.4}});
   throw new Error(`Unexpected fetch ${path}`);
  });
  const user=userEvent.setup();render(<AssistantActionPanel conversationId={10} units="imperial"/>);
  await user.click(screen.getByRole('button',{name:'Log weight'}));
  const input=screen.getByLabelText('Weight (lb)') as HTMLInputElement;
  expect(input.value).toBe('154.3');
  fireEvent.change(input,{target:{value:'150.8'}});
  await user.click(screen.getByRole('button',{name:'Preview'}));
  expect(await screen.findByText('Log 150.8 lb?')).toBeTruthy();
  expect(screen.getByText(/Latest entry: 154\.3 lb/)).toBeTruthy();
  const request=JSON.parse(String((fetchMock.mock.calls[0][1] as RequestInit).body));
  expect(request.weight_kg).toBeCloseTo(68.4017294,5);
  await user.click(screen.getByRole('button',{name:'Confirm log'}));
  expect((await screen.findByRole('status')).textContent).toContain('Logged 150.8 lb.');
 });

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

 it('previews and confirms a multi-food meal with server-calculated nutrition',async()=>{
  fetchMock.mockImplementation(async(input:RequestInfo|URL,init?:RequestInit)=>{
   const path=String(input);
   if(path.includes('/foods?q=')&&path.includes('spinach'))return jsonResponse([{id:85,name:'Spinach, raw',state:'raw',kcal:23,protein:2.9,carbs:3.6,fat:0.4,verification:'reviewed'}]);
   if(path.includes('/foods?q='))return jsonResponse([{id:84,name:'Brown rice, cooked',state:'cooked',kcal:123,protein:2.7,carbs:25.6,fat:1,verification:'reviewed'}]);
   if(path.endsWith('/assistant/actions/preview'))return jsonResponse({id:'meal-action-12345678901234567890',action:'log_meal',status:'pending',preview:{name:'Lunch',meal_type:'lunch',eaten_at:'2026-11-06T10:00:00+00:00',items:[{name:'Brown rice, cooked',state:'cooked',grams:150,per100:{kcal:123,protein:2.7,carbs:25.6,fat:1},verification:'reviewed',source:'USDA'},{name:'Spinach, raw',state:'raw',grams:50,per100:{kcal:23,protein:2.9,carbs:3.6,fat:0.4},verification:'reviewed',source:'USDA'}],totals:{kcal:196,protein:5.5,carbs:40.2,fat:1.7}},result:null});
   if(path.endsWith('/assistant/actions/meal-action-12345678901234567890/confirm'))return jsonResponse({id:'meal-action-12345678901234567890',action:'log_meal',status:'confirmed',preview:{name:'Lunch',items:[],totals:{kcal:196}},result:{meal_id:19,name:'Lunch',kcal:196}});
   throw new Error(`Unexpected fetch ${path} ${init?.method??'GET'}`);
  });
  const user=userEvent.setup();render(<AssistantActionPanel conversationId={12}/>);
  await user.click(screen.getByRole('button',{name:'Log a meal'}));
  fireEvent.change(screen.getByLabelText('Meal name'),{target:{value:'Lunch'}});
  fireEvent.change(screen.getByLabelText('Search food 1 in your catalogue'),{target:{value:'brown rice'}});
  await waitFor(()=>expect(fetchMock).toHaveBeenCalledTimes(1));
  await user.selectOptions(await screen.findByLabelText('Select catalogue food 1'),'84');
  fireEvent.change(screen.getByLabelText('Portion weight for food 1 (g)'),{target:{value:'150'}});
  await user.click(screen.getByRole('button',{name:'Add another food'}));
  fireEvent.change(screen.getByLabelText('Search food 2 in your catalogue'),{target:{value:'spinach'}});
  await waitFor(()=>expect(fetchMock).toHaveBeenCalledTimes(2));
  await user.selectOptions(await screen.findByLabelText('Select catalogue food 2'),'85');
  fireEvent.change(screen.getByLabelText('Portion weight for food 2 (g)'),{target:{value:'50'}});
  await user.click(screen.getByRole('button',{name:'Preview meal'}));
  expect((await screen.findByText(/Meal total:/)).textContent).toContain('196 kcal');
  expect(fetchMock).toHaveBeenCalledTimes(3);
  await user.click(screen.getByRole('button',{name:'Confirm log'}));
  expect((await screen.findByRole('status')).textContent).toContain('Lunch was added to your meal log. Calories: 196 kcal.');
  expect(fetchMock).toHaveBeenCalledTimes(4);
  const previewInit=fetchMock.mock.calls[2][1] as RequestInit;
  const request=JSON.parse(String(previewInit.body));
  expect(request.action).toBe('log_meal');
  expect(request.meal.items).toEqual([{food_id:84,grams:150},{food_id:85,grams:50}]);
 });

 it('focuses each added food and prevents adding more than ten',async()=>{
  const user=userEvent.setup();render(<AssistantActionPanel conversationId={14}/>);
  await user.click(screen.getByRole('button',{name:'Log a meal'}));
  const addButton=screen.getByRole('button',{name:'Add another food'});
  await user.click(addButton);
  const secondSearch=screen.getByLabelText('Search food 2 in your catalogue');
  expect(document.activeElement).toBe(secondSearch);
  for(let index=2;index<10;index++)await user.click(screen.getByRole('button',{name:'Add another food'}));
  expect(screen.getAllByRole('group',{name:/^Food \d+$/})).toHaveLength(10);
  const cappedButton=screen.getByRole('button',{name:'Add another food (10 maximum)'});
  expect((cappedButton as HTMLButtonElement).disabled).toBe(true);
  await user.click(screen.getByRole('button',{name:'Remove food 10'}));
  expect(screen.getAllByRole('group',{name:/^Food \d+$/})).toHaveLength(9);
  expect((screen.getByRole('button',{name:'Add another food'}) as HTMLButtonElement).disabled).toBe(false);
 });
});
