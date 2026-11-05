import React from 'react';
import {api} from './api';

type FoodOption={id:number;name:string;state:string;kcal:number|null;protein:number|null;carbs:number|null;fat:number|null;verification:string};
type MealItem={name:string;state:string;grams:number;per100:Record<string,number|null>;verification:string;source:string|null};
type Preview={id:string;action:'log_water'|'log_meal';status:string;preview:any;result:any};

export default function AssistantActionPanel({conversationId}:{conversationId:number}){
 const [kind,setKind]=React.useState<'log_water'|'log_meal'>('log_water');const [waterMl,setWaterMl]=React.useState(250);
 const [mealName,setMealName]=React.useState('Meal from assistant');const [mealType,setMealType]=React.useState('snack');const [query,setQuery]=React.useState('');const [foods,setFoods]=React.useState<FoodOption[]>([]);const [foodId,setFoodId]=React.useState('');const [grams,setGrams]=React.useState(100);
 const [preview,setPreview]=React.useState<Preview|null>(null);const [busy,setBusy]=React.useState(false);const [error,setError]=React.useState('');const [notice,setNotice]=React.useState('');
 React.useEffect(()=>{
  setFoods([]);setFoodId('');
  if(query.trim().length<2)return;
  let active=true;const timer=window.setTimeout(()=>api<FoodOption[]>(`/foods?q=${encodeURIComponent(query.trim())}`).then(results=>{if(active){setFoods(results);setFoodId(current=>results.some(food=>String(food.id)===current)?current:'')}}).catch(e=>active&&setError(e.message)),250);
  return()=>{active=false;window.clearTimeout(timer)};
 },[query]);
 async function createPreview(e:React.FormEvent<HTMLFormElement>){
  e.preventDefault();setBusy(true);setError('');setNotice('');
  const request=kind==='log_water'?{conversation_id:conversationId,action:kind,water_ml:waterMl,idempotency_key:crypto.randomUUID()}:{conversation_id:conversationId,action:kind,idempotency_key:crypto.randomUUID(),meal:{name:mealName,meal_type:mealType,items:[{food_id:Number(foodId),grams}]}};
  try{setPreview(await api<Preview>('/assistant/actions/preview',{method:'POST',body:JSON.stringify(request)}))}catch(e:any){setError(e.message)}finally{setBusy(false)}
 }
 async function confirm(){if(!preview)return;setBusy(true);setError('');try{const result=await api<Preview>(`/assistant/actions/${preview.id}/confirm`,{method:'POST'});if(result.status!=='confirmed'){setPreview(result);return}if(result.action==='log_water')setNotice(`Logged ${result.result.water_ml} ml. Today’s water total is ${(result.preview.today_total_after_ml/1000).toFixed(1)} L.`);else setNotice(`${result.result.name} was added to your meal log. Calories: ${result.result.kcal==null?'unavailable':Math.round(result.result.kcal)+' kcal'}.`);setPreview(null)}catch(e:any){setError(e.message);setPreview(null)}finally{setBusy(false)}}
 async function cancel(){if(!preview)return;setBusy(true);try{await api(`/assistant/actions/${preview.id}/cancel`,{method:'POST'});setPreview(null);setError('')}catch(e:any){setError(e.message)}finally{setBusy(false)}}
 const selected=foods.find(food=>String(food.id)===foodId);
 return <section className="assistant-action" aria-label="Assistant actions">
  {notice&&<p className="action-notice" role="status">{notice}</p>}
  {preview?<div className="action-preview" role="group" aria-label="Review action before confirmation">
   <div><b>{preview.action==='log_water'?`Log ${preview.preview.water_ml} ml of water?`:`Add “${preview.preview.name}” to your meal log?`}</b>
    {preview.action==='log_water'?<p className="muted">Today’s total will change from {preview.preview.today_total_before_ml} ml to {preview.preview.today_total_after_ml} ml ({preview.preview.local_date}).</p>:<><p className="muted">{preview.preview.meal_type} · {new Date(preview.preview.eaten_at).toLocaleString()}</p><ul className="action-meal-items">{(preview.preview.items as MealItem[]).map((item,index)=><li key={`${item.name}-${index}`}>{item.name} · {item.state} · {item.grams} g <small>{item.per100.kcal==null?'Calories unavailable':`${Math.round(item.per100.kcal*item.grams/100)} kcal`} · {item.verification}</small></li>)}</ul><p className="action-meal-total">Meal total: {preview.preview.totals.kcal==null?'—':`${Math.round(preview.preview.totals.kcal)} kcal`} · protein {preview.preview.totals.protein==null?'—':`${Math.round(preview.preview.totals.protein)} g`}</p></>}
   </div><div className="actions"><button className="button primary" onClick={confirm} disabled={busy}>{busy?'Saving…':'Confirm log'}</button><button className="button" onClick={cancel} disabled={busy}>Cancel</button></div>
  </div>:<><div className="action-kind" role="group" aria-label="Choose an assistant action"><button className={`chip ${kind==='log_water'?'selected':''}`} aria-pressed={kind==='log_water'} onClick={()=>setKind('log_water')}>Log water</button><button className={`chip ${kind==='log_meal'?'selected':''}`} aria-pressed={kind==='log_meal'} onClick={()=>setKind('log_meal')}>Log a meal</button></div>
   {kind==='log_water'?<form className="water-action-form" onSubmit={createPreview}><label htmlFor="assistant-water-ml">Water amount</label><input id="assistant-water-ml" type="number" min={50} max={2000} step={50} value={waterMl} onChange={e=>setWaterMl(Number(e.target.value))}/><span className="muted">ml</span><button className="button" disabled={busy}>{busy?'Preparing…':'Preview'}</button></form>:<form className="meal-action-form" onSubmit={createPreview}><label>Meal name<input value={mealName} onChange={e=>setMealName(e.target.value)} maxLength={160} required/></label><label>Meal type<select value={mealType} onChange={e=>setMealType(e.target.value)}>{['breakfast','lunch','dinner','snack'].map(value=><option key={value} value={value}>{value}</option>)}</select></label><label>Search your food catalogue<input value={query} onChange={e=>setQuery(e.target.value)} minLength={2} placeholder="e.g. cooked brown rice" required/></label><label>Select food<select value={foodId} onChange={e=>setFoodId(e.target.value)} required><option value="">Choose a matching food</option>{foods.map(food=><option key={food.id} value={food.id}>{food.name} · {food.state}</option>)}</select></label>{selected&&<p className="muted food-pick-note">{selected.kcal==null?'Calories unavailable':`${selected.kcal} kcal per 100 g`} · {selected.verification}</p>}<label>Portion weight<input type="number" min={1} max={10000} step={1} value={grams} onChange={e=>setGrams(Number(e.target.value))} required/></label><button className="button" disabled={busy||!foodId}>{busy?'Preparing…':'Preview meal'}</button></form>}
  </>}
  {error&&<p className="error" role="alert">{error}</p>}
 </section>
}
