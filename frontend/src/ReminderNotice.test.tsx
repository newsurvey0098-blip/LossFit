/** @vitest-environment jsdom */
import React from 'react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { api } from './api';
import ReminderNotice from './ReminderNotice';

vi.mock('./api', () => ({ api: vi.fn() }));
const mockedApi = vi.mocked(api);

function currentUtcMinute() {
  const parts = new Intl.DateTimeFormat('en-GB', { timeZone: 'UTC', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).formatToParts(new Date());
  const get = (name: string) => parts.find(part => part.type === name)?.value ?? '';
  return `${get('hour')}:${get('minute')}`;
}

beforeEach(() => { localStorage.clear(); vi.clearAllMocks(); });
afterEach(() => cleanup());

it('shows one due in-app meal notice with a meal action and dismiss control', async () => {
  mockedApi.mockResolvedValue({ id: 42, preferences: { timezone: 'UTC', meal_reminders: { enabled: true, times: { breakfast: currentUtcMinute() } } } } as never);
  const user = userEvent.setup();
  render(<MemoryRouter><ReminderNotice /></MemoryRouter>);

  const notice = await screen.findByRole('status', { name: 'Meal reminder' });
  expect(notice.textContent).toContain('It’s time for breakfast.');
  expect(screen.getByRole('link', { name: 'Log a meal' }).getAttribute('href')).toBe('/meals/new');
  await user.click(screen.getByRole('button', { name: 'Dismiss' }));
  expect(screen.queryByRole('status', { name: 'Meal reminder' })).toBeNull();
});

it('does not show notices when reminders are disabled', async () => {
  mockedApi.mockResolvedValue({ id: 42, preferences: { timezone: 'UTC', meal_reminders: { enabled: false, times: { breakfast: currentUtcMinute() } } } } as never);
  render(<MemoryRouter><ReminderNotice /></MemoryRouter>);
  await vi.waitFor(() => expect(mockedApi).toHaveBeenCalledWith('/auth/me'));
  expect(screen.queryByRole('status', { name: 'Meal reminder' })).toBeNull();
});
