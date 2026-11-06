import React from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Search } from 'lucide-react';
import { api, jsonBody } from './api';

type Item = {
  food_id?: number;
  snapshot_id?: string;
  name?: string;
  food?: string;
  state?: string;
  grams: number;
  portion_label?: string | null;
  per100?: Record<string, number | null>;
  verification?: string;
  source?: string | null;
};
type Meal = {
  id: number;
  name: string;
  meal_type: string;
  eaten_at: string;
  items: Item[];
  kcal: number | null;
  protein: number | null;
  carbs: number | null;
  fat: number | null;
};
type CatalogFood = {
  id: number;
  name: string;
  state: string;
  kcal: number | null;
  protein: number | null;
  carbs: number | null;
  fat: number | null;
  servings: { id: number; label: string; grams: number }[];
};

export function NewMealPage() {
  const navigate = useNavigate();
  const searchInput = React.useRef<HTMLInputElement>(null);
  const servingInput = React.useRef<HTMLSelectElement>(null);
  const amountInput = React.useRef<HTMLInputElement>(null);
  const pickerWasOpen = React.useRef(false);
  const [name, setName] = React.useState('');
  const [mealType, setMealType] = React.useState('breakfast');
  const [query, setQuery] = React.useState('');
  const [results, setResults] = React.useState<CatalogFood[]>([]);
  const [searching, setSearching] = React.useState(false);
  const [items, setItems] = React.useState<Item[]>([]);
  const [picked, setPicked] = React.useState<CatalogFood | null>(null);
  const [grams, setGrams] = React.useState(100);
  const [serving, setServing] = React.useState('');
  const [error, setError] = React.useState('');
  const [busy, setBusy] = React.useState(false);

  React.useEffect(() => {
    if (picked) {
      pickerWasOpen.current = true;
      (servingInput.current ?? amountInput.current)?.focus();
    } else if (pickerWasOpen.current) {
      pickerWasOpen.current = false;
      searchInput.current?.focus();
    }
  }, [picked]);

  React.useEffect(() => {
    let active = true; setSearching(true);
    const timer = window.setTimeout(() => {
      api<CatalogFood[]>(`/foods?q=${encodeURIComponent(query)}`)
        .then((data) => active && setResults(data))
        .catch((e: Error) => active && setError(e.message))
        .finally(() => active && setSearching(false));
    }, 180);
    return () => { active = false; window.clearTimeout(timer); };
  }, [query]);

  function selectFood(food: CatalogFood) {
    const defaultServing = food.servings.find((value) => value.label === '100 g') ?? food.servings[0];
    setPicked(food); setGrams(defaultServing?.grams ?? 100); setServing(defaultServing?.label ?? 'Custom grams');
  }
  function addFood() {
    if (!picked) return;
    setItems((current) => [...current, {
      food_id: picked.id, name: picked.name, state: picked.state, grams,
      portion_label: serving === 'Custom grams' ? `${grams} g` : serving,
      per100: { kcal: picked.kcal, protein: picked.protein, carbs: picked.carbs, fat: picked.fat },
    }]);
    setPicked(null); setServing('');
  }
  async function submit(e: React.FormEvent) {
    e.preventDefault(); setError('');
    if (!name.trim()) { setError('Add a meal name.'); return; }
    if (!items.length) { setError('Add at least one food to this meal.'); return; }
    setBusy(true);
    try {
      const meal = await api<{id:number}>('/meals', { method: 'POST', body: jsonBody('add_meal_api_v1_meals_post', { name, meal_type: mealType, items }) });
      navigate(`/meals/${meal.id}`);
    } catch (e: any) { setError(e.message); setBusy(false); }
  }

  return <>
    <p className="eyebrow">MEAL LOG</p><h1>Create a meal</h1>
    <form className="card manualform" onSubmit={submit}>
      <label>Meal name<input required maxLength={160} value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Yogurt and fruit" /></label>
      <label>Meal assignment<select value={mealType} onChange={(e) => setMealType(e.target.value)}>{['breakfast','lunch','dinner','snack'].map((value) => <option key={value}>{value}</option>)}</select></label>
      <h2>Foods and portions</h2>
      {items.map((item, index) => <article className="meal card" key={`${item.food_id}-${index}`}>
        <div className="mealcontent"><h3>{item.name}</h3><label>Portion in grams<input type="number" min="1" max="10000" value={item.grams} onChange={(e) => setItems((current) => current.map((v, i) => i === index ? { ...v, grams: Math.max(1, Number(e.target.value) || 1), portion_label: null } : v))} /></label>
          <p className="muted">{item.per100?.kcal == null ? 'Calories unknown' : `${(item.per100.kcal * item.grams / 100).toFixed(0)} kcal`} · {item.portion_label || `${item.grams} g`}</p>
        </div><button type="button" className="button" onClick={() => setItems((current) => current.filter((_, i) => i !== index))}>Remove</button>
      </article>)}
      <section className="food-picker" aria-label="Add foods to new meal">
        <label>Search foods<input ref={searchInput} aria-label="Search foods to add" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search food catalogue" /></label>
        {picked ? <>
          <p className="muted">Adding <b>{picked.name}</b></p>
          {picked.servings.length > 0 && <label>Serving<select ref={servingInput} value={serving} onChange={(e) => { setServing(e.target.value); const servingValue = picked.servings.find((value) => value.label === e.target.value); if (servingValue) setGrams(servingValue.grams); }}>
            {picked.servings.map((value) => <option key={value.id} value={value.label}>{value.label} ({value.grams} g)</option>)}<option>Custom grams</option>
          </select></label>}
          <label>Amount in grams<input ref={amountInput} type="number" min="1" max="10000" value={grams} onChange={(e) => { setServing('Custom grams'); setGrams(Math.max(1, Number(e.target.value) || 1)); }} /></label>
          <div className="actions"><button type="button" className="button primary" onClick={addFood}>Add item</button><button type="button" className="button" onClick={() => setPicked(null)}>Choose another</button></div>
        </> : searching ? <p className="muted" role="status">Searching foods…</p> : <div className="food-picker-results">
          {results.map((food) => <button type="button" className="card food-result" key={food.id} onClick={() => selectFood(food)}><span>{food.name} <small>{food.state}</small></span><span>{food.kcal == null ? '— kcal' : `${food.kcal} kcal / 100 g`}</span></button>)}
          {!results.length && <p className="muted">No matching foods. Add a personal food first.</p>}
        </div>}
      </section>
      {error && <p className="error" role="alert">{error}</p>}
      <div className="actions"><button className="button primary" disabled={busy}>{busy ? 'Saving…' : 'Save meal'}</button><Link className="button" to="/home">Cancel</Link></div>
    </form>
  </>;
}

function localDateTime(value: string) {
  const d = new Date(value);
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
}

export default function MealDetailPage() {
  const { mealId } = useParams();
  const navigate = useNavigate();
  const addFoodButton = React.useRef<HTMLButtonElement>(null);
  const pickerSearchInput = React.useRef<HTMLInputElement>(null);
  const pickerServingInput = React.useRef<HTMLSelectElement>(null);
  const pickerAmountInput = React.useRef<HTMLInputElement>(null);
  const pickerWasOpen = React.useRef(false);
  const [meal, setMeal] = React.useState<Meal | null>(null);
  const [error, setError] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const [saved, setSaved] = React.useState(false);
  const [picker, setPicker] = React.useState(false);
  const [query, setQuery] = React.useState('');
  const [results, setResults] = React.useState<CatalogFood[]>([]);
  const [searching, setSearching] = React.useState(false);
  const [picked, setPicked] = React.useState<CatalogFood | null>(null);
  const [grams, setGrams] = React.useState(100);
  const [serving, setServing] = React.useState('');

  React.useEffect(() => {
    let active = true;
    api<Meal>(`/meals/${mealId}`)
      .then((value) => active && setMeal(value))
      .catch((e: Error) => active && setError(e.message));
    return () => { active = false; };
  }, [mealId]);

  React.useEffect(() => {
    if (!picker) return;
    let active = true;
    setSearching(true);
    const timer = window.setTimeout(() => {
      api<CatalogFood[]>(`/foods?q=${encodeURIComponent(query)}`)
        .then((value) => active && setResults(value))
        .catch((e: Error) => active && setError(e.message))
        .finally(() => active && setSearching(false));
    }, 180);
    return () => { active = false; window.clearTimeout(timer); };
  }, [picker, query]);

  React.useEffect(() => {
    if (picked) {
      pickerWasOpen.current = true;
      (pickerServingInput.current ?? pickerAmountInput.current)?.focus();
    } else if (pickerWasOpen.current) {
      pickerWasOpen.current = false;
      if (picker) pickerSearchInput.current?.focus();
      else addFoodButton.current?.focus();
    }
  }, [picked, picker]);

  function updateItem(index: number, patch: Partial<Item>) {
    setMeal((current) => current ? {
      ...current,
      items: current.items.map((item, i) => i === index ? { ...item, ...patch } : item),
    } : current);
    setSaved(false);
  }

  async function save() {
    if (!meal) return;
    setBusy(true); setError('');
    try {
      const result = await api<Meal>(`/meals/${meal.id}`, {
        method: 'PUT',
        body: JSON.stringify({
          name: meal.name,
          meal_type: meal.meal_type,
          eaten_at: meal.eaten_at,
          items: meal.items,
        }),
      });
      setMeal(result); setSaved(true);
    } catch (e: any) { setError(e.message); }
    finally { setBusy(false); }
  }

  async function remove() {
    if (!meal || !window.confirm('Delete this meal and remove it from your nutrition history?')) return;
    setBusy(true); setError('');
    try { await api(`/meals/${meal.id}`, { method: 'DELETE' }); navigate('/home'); }
    catch (e: any) { setError(e.message); setBusy(false); }
  }

  async function removeItem(index: number) {
    if (!meal) return;
    setMeal({ ...meal, items: meal.items.filter((_, i) => i !== index) });
    setSaved(false);
  }

  function chooseFood(food: CatalogFood) {
    const standard = food.servings.find((value) => value.label === '100 g') ?? food.servings[0];
    setPicked(food); setGrams(standard?.grams ?? 100); setServing(standard?.label ?? 'Custom grams');
  }

  function addPicked() {
    if (!meal || !picked) return;
    const portion = serving === 'Custom grams' ? `${grams} g` : serving;
    setMeal({ ...meal, items: [...meal.items, {
      food_id: picked.id,
      name: picked.name,
      state: picked.state,
      grams,
      portion_label: portion,
      per100: { kcal: picked.kcal, protein: picked.protein, carbs: picked.carbs, fat: picked.fat },
    }] });
    setPicked(null); setServing(''); setPicker(false); setSaved(false);
  }

  const nutrient = (key: string) => {
    if (!meal || meal.items.some((item) => item.per100?.[key] == null)) return '—';
    return meal.items.reduce((sum, item) => sum + Number(item.per100?.[key]) * item.grams / 100, 0).toFixed(1);
  };

  if (error && !meal) return <section className="card simple"><h1>Meal unavailable</h1><p className="error" role="alert">{error}</p><Link className="button primary" to="/home">Back to today</Link></section>;
  if (!meal) return <p role="status">Loading meal…</p>;

  return <>
    <p className="eyebrow">MEAL DETAIL</p>
    <h1>{meal.name}</h1>
    <p className="muted">Edit the meal and portions. Logged nutrition values remain tied to the original food records.</p>
    <section className="card manualform">
      <label>Meal name<input value={meal.name} maxLength={160} onChange={(e) => setMeal({ ...meal, name: e.target.value })} /></label>
      <div className="formgrid">
        <label>Meal assignment<select value={meal.meal_type} onChange={(e) => setMeal({ ...meal, meal_type: e.target.value })}>{['breakfast', 'lunch', 'dinner', 'snack'].map((value) => <option key={value}>{value}</option>)}</select></label>
        <label>Date and time<input type="datetime-local" value={localDateTime(meal.eaten_at)} onChange={(e) => { if (e.target.value) setMeal({ ...meal, eaten_at: new Date(e.target.value).toISOString() }); }} /></label>
      </div>
      <h2>Food items</h2>
      {meal.items.length === 0 ? <p className="muted">This meal has no items.</p> : meal.items.map((item, index) => <article className="meal card" key={item.snapshot_id ?? index}>
        <div className="mealemoji" aria-hidden="true">🍽️</div>
        <div className="mealcontent">
          <h3>{item.name || item.food || `Food ${index + 1}`}</h3>
          <label>Portion in grams<input type="number" min="1" max="10000" value={item.grams} onChange={(e) => updateItem(index, { grams: Math.max(1, Number(e.target.value) || 1), portion_label: null })} /></label>
          <p className="muted">{item.per100?.kcal == null ? 'Calories unknown' : `${(item.per100.kcal * item.grams / 100).toFixed(0)} kcal`} · {item.per100?.protein == null ? 'Protein unknown' : `${(item.per100.protein * item.grams / 100).toFixed(1)}g protein`} · {item.verification?.replace('_', ' ') ?? 'nutrition snapshot'}</p>
          {item.source && <small className="muted">Source: {item.source}</small>}
        </div>
        <button className="button" aria-label={`Remove ${item.name || item.food || 'food'}`} onClick={() => removeItem(index)}>Remove</button>
      </article>)}
      <button ref={addFoodButton} className="button" type="button" onClick={() => { setPicker((value) => !value); setPicked(null); setError(''); }}><Search size={16} /> Add food to this meal</button>
      {picker && <section className="food-picker" aria-label="Add food picker">
        <label>Search foods<input ref={pickerSearchInput} autoFocus aria-label="Search foods to add to this meal" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search your catalogue" /></label>
        {picked ? <>
          <p className="muted">Adding <b>{picked.name}</b></p>
          {picked.servings.length > 0 && <label>Serving<select ref={pickerServingInput} value={serving} onChange={(e) => { setServing(e.target.value); const value = picked.servings.find((item) => item.label === e.target.value); if (value) setGrams(value.grams); }}>
            {picked.servings.map((value) => <option key={value.id} value={value.label}>{value.label} ({value.grams} g)</option>)}<option>Custom grams</option>
          </select></label>}
          <label>Amount in grams<input ref={pickerAmountInput} type="number" min="1" max="10000" value={grams} onChange={(e) => { setServing('Custom grams'); setGrams(Math.max(1, Number(e.target.value) || 1)); }} /></label>
          <div className="actions"><button type="button" className="button primary" onClick={addPicked}>Add item</button><button type="button" className="button" onClick={() => setPicked(null)}>Choose another</button></div>
        </> : searching ? <p className="muted" role="status">Searching foods…</p> : <div className="food-picker-results">
          {results.map((food) => <button type="button" className="card food-result" key={food.id} onClick={() => chooseFood(food)}><span>{food.name} <small>{food.state}</small></span><span>{food.kcal == null ? '— kcal' : `${food.kcal} kcal / 100 g`}</span></button>)}
          {!results.length && <p className="muted">No matching foods. Add a personal food first.</p>}
        </div>}
      </section>}
      <div className="nutrients large"><span><b>{nutrient('kcal')}</b> kcal</span><span><b>{nutrient('protein')}</b> protein</span><span><b>{nutrient('carbs')}</b> carbs</span><span><b>{nutrient('fat')}</b> fat</span></div>
      {error && <p className="error" role="alert">{error}</p>}
      {saved && <p role="status" className="success">Meal changes saved.</p>}
      <div className="actions"><button className="button primary" onClick={save} disabled={busy}>{busy ? 'Saving…' : 'Save changes'}</button><button className="button danger" onClick={remove} disabled={busy}>Delete meal</button><Link className="button" to="/foods">Open foods</Link></div>
    </section>
  </>;
}
