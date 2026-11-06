import React from 'react';
import { Link } from 'react-router-dom';
import { api } from './api';

type ReminderSlot = 'breakfast' | 'lunch' | 'dinner' | 'snack';
const slots: ReminderSlot[] = ['breakfast', 'lunch', 'dinner', 'snack'];

function zonedParts(timeZone: string) {
  const values = new Intl.DateTimeFormat('en-GB', {
    timeZone,
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
  }).formatToParts(new Date());
  const part = (type: string) => values.find(value => value.type === type)?.value ?? '';
  return { date: `${part('year')}-${part('month')}-${part('day')}`, time: `${part('hour')}:${part('minute')}` };
}

export default function ReminderNotice() {
  const [notice, setNotice] = React.useState<{ userId: number; date: string; slot: ReminderSlot } | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;
    api('/auth/me').then((user: any) => {
      if (cancelled) return;
      const check = () => {
        if (cancelled || !user.preferences?.meal_reminders?.enabled) return;
        const zone = user.preferences?.timezone || 'UTC';
        try {
          const now = zonedParts(zone);
          const times = user.preferences?.meal_reminders?.times || {};
          for (const slot of slots) {
            if (times[slot] !== now.time) continue;
            const key = `lossfit:reminder:${user.id}:${now.date}:${slot}`;
            if (localStorage.getItem(key)) continue;
            localStorage.setItem(key, 'shown');
            setNotice({ userId: user.id, date: now.date, slot });
            break;
          }
        } catch {
          // A stale or invalid saved time zone must not break the signed-in shell.
        }
      };
      check();
      timer = window.setInterval(check, 15_000);
    }).catch(() => undefined);
    return () => { cancelled = true; if (timer !== undefined) window.clearInterval(timer); };
  }, []);

  if (!notice) return null;
  const label = notice.slot[0].toUpperCase() + notice.slot.slice(1);
  return <section className="reminder-notice" role="status" aria-label="Meal reminder">
    <p><strong>It’s time for {label.toLowerCase()}.</strong> Your meal reminder is set for today.</p>
    <div className="actions"><Link className="button primary" to="/meals/new">Log a meal</Link><button className="button" onClick={() => setNotice(null)}>Dismiss</button></div>
  </section>;
}
