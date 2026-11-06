import React from 'react';
import { api } from './api';

type FoodOption = {
  id: number;
  name: string;
  state: string;
  kcal: number | null;
  protein: number | null;
  carbs: number | null;
  fat: number | null;
  verification: string;
};
type MealItem = {
  name: string;
  state: string;
  grams: number;
  per100: Record<string, number | null>;
  verification: string;
  source: string | null;
};
type Preview = { id: string; action: 'log_water' | 'log_meal'; status: string; preview: any; result: any };
type DraftMealItem = { id: string; foodId: string; grams: number };

function AssistantFoodPicker({
  index,
  item,
  onChange,
  onRemove,
  removable,
  focusNewRow,
  onFocused,
}: {
  index: number;
  item: DraftMealItem;
  onChange: (value: DraftMealItem) => void;
  onRemove: () => void;
  removable: boolean;
  focusNewRow: boolean;
  onFocused: () => void;
}) {
  const [query, setQuery] = React.useState('');
  const [foods, setFoods] = React.useState<FoodOption[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState('');
  const searchInput = React.useRef<HTMLInputElement>(null);
  const baseId = `assistant-meal-item-${index + 1}`;

  React.useEffect(() => {
    if (!focusNewRow) return;
    searchInput.current?.focus();
    searchInput.current?.scrollIntoView?.({ block: 'nearest' });
    onFocused();
  }, [focusNewRow, onFocused]);

  React.useEffect(() => {
    setFoods([]);
    setError('');
    if (query.trim().length < 2) {
      setLoading(false);
      return;
    }
    let active = true;
    setLoading(true);
    const timer = window.setTimeout(() => {
      api<FoodOption[]>(`/foods?q=${encodeURIComponent(query.trim())}`)
        .then((results) => active && setFoods(results))
        .catch((reason: unknown) => active && setError(reason instanceof Error ? reason.message : 'Food search failed.'))
        .finally(() => active && setLoading(false));
    }, 250);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [query]);

  const selected = foods.find((food) => String(food.id) === item.foodId);

  return (
    <fieldset className="assistant-food-item">
      <legend>Food {index + 1}</legend>
      {removable && (
        <button type="button" className="textlink assistant-food-remove" onClick={onRemove} aria-label={`Remove food ${index + 1}`}>
          Remove
        </button>
      )}
      <label htmlFor={`${baseId}-search`}>Search food {index + 1} in your catalogue
        <input
          ref={searchInput}
          id={`${baseId}-search`}
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            onChange({ ...item, foodId: '' });
          }}
          minLength={2}
          placeholder="e.g. cooked brown rice"
          required
        />
      </label>
      <label htmlFor={`${baseId}-select`}>Select catalogue food {index + 1}
        <select id={`${baseId}-select`} value={item.foodId} onChange={(event) => onChange({ ...item, foodId: event.target.value })} required>
          <option value="">Choose a matching food</option>
          {foods.map((food) => <option key={food.id} value={food.id}>{food.name} · {food.state}</option>)}
        </select>
      </label>
      {loading && <p className="muted" role="status">Searching foods…</p>}
      {error && <p className="error" role="alert">{error}</p>}
      {selected && <p className="muted food-pick-note">{selected.kcal == null ? 'Calories unavailable' : `${selected.kcal} kcal per 100 g`} · {selected.verification}</p>}
      <label htmlFor={`${baseId}-grams`}>Portion weight for food {index + 1} (g)
        <input
          id={`${baseId}-grams`}
          type="number"
          min={1}
          max={10000}
          step={1}
          value={item.grams}
          onChange={(event) => onChange({ ...item, grams: Number(event.target.value) })}
          required
        />
      </label>
    </fieldset>
  );
}

export default function AssistantActionPanel({ conversationId }: { conversationId: number }) {
  const [kind, setKind] = React.useState<'log_water' | 'log_meal'>('log_water');
  const [waterMl, setWaterMl] = React.useState(250);
  const [mealName, setMealName] = React.useState('Meal from assistant');
  const [mealType, setMealType] = React.useState('snack');
  const [mealItems, setMealItems] = React.useState<DraftMealItem[]>(() => [{ id: crypto.randomUUID(), foodId: '', grams: 100 }]);
  const [focusItemId, setFocusItemId] = React.useState<string | null>(null);
  const [preview, setPreview] = React.useState<Preview | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState('');
  const [notice, setNotice] = React.useState('');

  async function createPreview(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError('');
    setNotice('');
    const request = kind === 'log_water'
      ? { conversation_id: conversationId, action: kind, water_ml: waterMl, idempotency_key: crypto.randomUUID() }
      : {
          conversation_id: conversationId,
          action: kind,
          idempotency_key: crypto.randomUUID(),
          meal: { name: mealName, meal_type: mealType, items: mealItems.map((item) => ({ food_id: Number(item.foodId), grams: item.grams })) },
        };
    try {
      setPreview(await api<Preview>('/assistant/actions/preview', { method: 'POST', body: JSON.stringify(request) }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The action could not be prepared.');
    } finally {
      setBusy(false);
    }
  }

  async function confirm() {
    if (!preview) return;
    setBusy(true);
    setError('');
    try {
      const result = await api<Preview>(`/assistant/actions/${preview.id}/confirm`, { method: 'POST' });
      if (result.status !== 'confirmed') {
        setPreview(result);
        return;
      }
      if (result.action === 'log_water') setNotice(`Logged ${result.result.water_ml} ml. Today’s water total is ${(result.preview.today_total_after_ml / 1000).toFixed(1)} L.`);
      else setNotice(`${result.result.name} was added to your meal log. Calories: ${result.result.kcal == null ? 'unavailable' : `${Math.round(result.result.kcal)} kcal`}.`);
      setPreview(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The action could not be confirmed.');
      setPreview(null);
    } finally {
      setBusy(false);
    }
  }

  async function cancel() {
    if (!preview) return;
    setBusy(true);
    try {
      await api(`/assistant/actions/${preview.id}/cancel`, { method: 'POST' });
      setPreview(null);
      setError('');
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The proposal could not be canceled.');
    } finally {
      setBusy(false);
    }
  }

  function updateMealItem(index: number, value: DraftMealItem) {
    setMealItems((current) => current.map((item, itemIndex) => itemIndex === index ? value : item));
  }

  function addMealItem() {
    if (mealItems.length >= 10) return;
    const nextItem = { id: crypto.randomUUID(), foodId: '', grams: 100 };
    setFocusItemId(nextItem.id);
    setMealItems((current) => current.length < 10 ? [...current, nextItem] : current);
  }

  return (
    <section className="assistant-action" aria-label="Assistant actions">
      {notice && <p className="action-notice" role="status">{notice}</p>}
      {preview ? (
        <div className="action-preview" role="group" aria-label="Review action before confirmation">
          <div>
            <b>{preview.action === 'log_water' ? `Log ${preview.preview.water_ml} ml of water?` : `Add “${preview.preview.name}” to your meal log?`}</b>
            {preview.action === 'log_water' ? (
              <p className="muted">Today’s total will change from {preview.preview.today_total_before_ml} ml to {preview.preview.today_total_after_ml} ml ({preview.preview.local_date}).</p>
            ) : (
              <>
                <p className="muted">{preview.preview.meal_type} · {new Date(preview.preview.eaten_at).toLocaleString()}</p>
                <ul className="action-meal-items">
                  {(preview.preview.items as MealItem[]).map((item, index) => (
                    <li key={`${item.name}-${index}`}>{item.name} · {item.state} · {item.grams} g
                      <small>{item.per100.kcal == null ? 'Calories unavailable' : `${Math.round(item.per100.kcal * item.grams / 100)} kcal`} · {item.verification}</small>
                    </li>
                  ))}
                </ul>
                <p className="action-meal-total">Meal total: {preview.preview.totals.kcal == null ? '—' : `${Math.round(preview.preview.totals.kcal)} kcal`} · protein {preview.preview.totals.protein == null ? '—' : `${Math.round(preview.preview.totals.protein)} g`}</p>
              </>
            )}
          </div>
          <div className="actions">
            <button className="button primary" onClick={() => void confirm()} disabled={busy}>{busy ? 'Saving…' : 'Confirm log'}</button>
            <button className="button" onClick={() => void cancel()} disabled={busy}>Cancel</button>
          </div>
        </div>
      ) : (
        <>
          <div className="action-kind" role="group" aria-label="Choose an assistant action">
            <button className={`chip ${kind === 'log_water' ? 'selected' : ''}`} aria-pressed={kind === 'log_water'} onClick={() => setKind('log_water')}>Log water</button>
            <button className={`chip ${kind === 'log_meal' ? 'selected' : ''}`} aria-pressed={kind === 'log_meal'} onClick={() => setKind('log_meal')}>Log a meal</button>
          </div>
          {kind === 'log_water' ? (
            <form className="water-action-form" onSubmit={createPreview}>
              <label htmlFor="assistant-water-ml">Water amount</label>
              <input id="assistant-water-ml" type="number" min={50} max={2000} step={50} value={waterMl} onChange={(event) => setWaterMl(Number(event.target.value))}/>
              <span className="muted">ml</span>
              <button className="button" disabled={busy}>{busy ? 'Preparing…' : 'Preview'}</button>
            </form>
          ) : (
            <form className="meal-action-form" onSubmit={createPreview}>
              <label>Meal name<input value={mealName} onChange={(event) => setMealName(event.target.value)} maxLength={160} required/></label>
              <label>Meal type<select value={mealType} onChange={(event) => setMealType(event.target.value)}>{['breakfast', 'lunch', 'dinner', 'snack'].map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
              <div className="assistant-food-list">
                {mealItems.map((item, index) => (
                  <AssistantFoodPicker
                    key={item.id}
                    index={index}
                    item={item}
                    onChange={(value) => updateMealItem(index, value)}
                    onRemove={() => setMealItems((current) => current.filter((entry) => entry.id !== item.id))}
                    removable={mealItems.length > 1}
                    focusNewRow={focusItemId === item.id}
                    onFocused={() => setFocusItemId(null)}
                  />
                ))}
              </div>
              <button
                type="button"
                className="button assistant-add-food"
                onClick={addMealItem}
                disabled={mealItems.length >= 10}
              >Add another food{mealItems.length >= 10 ? ' (10 maximum)' : ''}</button>
              <button className="button primary" disabled={busy || mealItems.some((item) => !item.foodId)}>{busy ? 'Preparing…' : 'Preview meal'}</button>
            </form>
          )}
        </>
      )}
      {error && <p className="error" role="alert">{error}</p>}
    </section>
  );
}
