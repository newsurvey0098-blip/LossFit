import React from 'react';
import {api} from './api';
import {displayWeight,storedWeight,weightLabel,Units} from './units';

type Entry={id:number;weight_kg:number;recorded_at:string};
export default function WeightPage(){
 const [items,setItems]=React.useState<Entry[]>([]);const [units,setUnits]=React.useState<Units>('metric');
 const [error,setError]=React.useState('');const [busy,setBusy]=React.useState(false);const [loading,setLoading]=React.useState(true);const [saved,setSaved]=React.useState(false);
 React.useEffect(()=>{let active=true;Promise.all([api<Entry[]>('/weight'),api('/auth/me')]).then(([rows,user])=>{if(active){setItems(rows);setUnits(user.preferences?.units??'metric')}}).catch(e=>active&&setError(e.message)).finally(()=>active&&setLoading(false));return()=>{active=false}},[]);
 async function submit(e:React.FormEvent<HTMLFormElement>){e.preventDefault();const target=e.currentTarget;setBusy(true);setSaved(false);setError('');const form=new FormData(target);try{await api('/weight',{method:'POST',body:JSON.stringify({weight_kg:storedWeight(Number(form.get('weight')),units)})});setItems(await api<Entry[]>('/weight'));setSaved(true);target.reset()}catch(e){setError(e instanceof Error?e.message:'Could not save weight')}finally{setBusy(false)}}
 return <><p className="eyebrow">PROGRESS</p><h1>Weight history</h1><p className="muted">Daily weight can fluctuate. Look at trends over time instead of individual readings.</p>
 {loading?<p role="status">Loading measurements…</p>:<form className="card manualform" onSubmit={submit}><label>Weight ({units==='imperial'?'lb':'kg'})<input name="weight" type="number" min={displayWeight(20,units)} max={displayWeight(350,units)} step="any" required/></label>{saved&&<p className="success" role="status">Weight entry saved.</p>}<button className="button primary" disabled={busy}>{busy?'Saving…':'Log weight'}</button></form>}
 {error&&<p className="error" role="alert">{error}</p>}
 <section className="card manualform"><h2>Recent entries</h2>{items.length?items.map(i=><div className="weight-row" key={i.id}><strong>{weightLabel(i.weight_kg,units)}</strong><span className="muted">{new Date(i.recorded_at).toLocaleString()}</span></div>):!loading&&<p className="muted">No weight entries yet.</p>}</section></>;
}
