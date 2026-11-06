/** @vitest-environment jsdom */
import React from 'react';
import {afterEach,expect,it,vi} from 'vitest';
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {MemoryRouter,Route,Routes} from 'react-router-dom';
import LearningPage from './LearningPage';
import {api} from './api';

vi.mock('./api',()=>({api:vi.fn()}));
afterEach(()=>{cleanup();vi.resetAllMocks()});

const lesson=(detailed=false)=>({slug:'balanced-plate',title:'Build a balanced plate',category:'Everyday nutrition',minutes:4,version:1,summary:'A practical guide.',content:detailed?'Long explanation with more evidence.':'Short explanation.',sources:[{title:'Nutrition source',organization:'Public health agency',url:'https://example.com/nutrition',version:'2026'}],quiz:{question:'What is a useful first step?',options:['Add a variety of foods','Skip a meal']},progress:null});
function mount(){render(<MemoryRouter initialEntries={['/learn/balanced-plate']}><Routes><Route path="/learn/:slug" element={<LearningPage/>}/></Routes></MemoryRouter>)}

it('announces a loaded lesson and announces the selected explanation after updating it',async()=>{
 vi.mocked(api).mockImplementation(async(path)=>path.includes('detailed=true')?lesson(true):lesson());
 mount();
 await screen.findByText('Short explanation.');
 expect((await screen.findByRole('status')).textContent).toContain('Lesson loaded: Build a balanced plate.');
 fireEvent.click(screen.getByRole('button',{name:'More detail'}));
 await screen.findByText('Long explanation with more evidence.');
 await waitFor(()=>expect(screen.getByRole('status').textContent).toContain('Lesson updated to more detail.'));
 expect(screen.getByRole('group',{name:'Explanation detail'})).toBeTruthy();
 expect(screen.getByRole('button',{name:'More detail'}).getAttribute('aria-pressed')).toBe('true');
});

it('marks lesson content busy while the selected explanation loads',async()=>{
 let complete!:(value:ReturnType<typeof lesson>)=>void;
 vi.mocked(api).mockImplementation(async(path)=>path.includes('detailed=true')?new Promise(resolve=>{complete=resolve}):lesson());
 mount();await screen.findByText('Short explanation.');
 fireEvent.click(screen.getByRole('button',{name:'More detail'}));
 const section=screen.getByText('Short explanation.').closest('.lesson-content');
 expect(section?.getAttribute('aria-busy')).toBe('true');
 complete(lesson(true));
 await screen.findByText('Long explanation with more evidence.');
 expect(section?.getAttribute('aria-busy')).toBe('false');
});

it('keeps the active explanation selected when loading another level fails',async()=>{
 vi.mocked(api).mockImplementation(async(path)=>{if(path.includes('detailed=true'))throw new Error('Lesson service unavailable');return lesson()});
 mount();await screen.findByText('Short explanation.');
 fireEvent.click(screen.getByRole('button',{name:'More detail'}));
 await screen.findByRole('alert');
 expect(screen.getByRole('button',{name:'Quick read'}).getAttribute('aria-pressed')).toBe('true');
 expect(screen.getByRole('button',{name:'More detail'}).getAttribute('aria-pressed')).toBe('false');
 expect(screen.getByRole('status').textContent).toContain('Lesson detail could not be updated.');
});
