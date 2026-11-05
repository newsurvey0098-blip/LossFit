/** @vitest-environment jsdom */
import React from 'react';
import {afterEach,expect,it,vi} from 'vitest';
import {cleanup,fireEvent,render,screen} from '@testing-library/react';
import AssistantProposal,{Proposal} from './AssistantProposal';
import {api} from './api';
vi.mock('./api',()=>({api:vi.fn()}));
afterEach(()=>{cleanup();vi.resetAllMocks()});
const water:Proposal={id:'a'.repeat(32),action:'log_water',status:'pending',expires_at:new Date(Date.now()+600000).toISOString(),preview:{water_ml:250,today_total_before_ml:100,today_total_after_ml:350},result:null};
it('requires a click to confirm a proposed entry and displays server confirmation',async()=>{
 vi.mocked(api).mockResolvedValue({...water,status:'confirmed',result:{water_ml:250}});
 render(<AssistantProposal proposal={water}/>);
 expect(api).not.toHaveBeenCalled();expect(screen.getByText('Nothing has been logged. Confirm to save this entry.')).toBeTruthy();
 fireEvent.click(screen.getByRole('button',{name:'Confirm proposed entry'}));
 await screen.findByText('Entry confirmed and saved.');
 expect(api).toHaveBeenCalledWith(`/assistant/actions/${water.id}/confirm`,{method:'POST'});
 expect(screen.queryByRole('button',{name:'Confirm proposed entry'})).toBeNull();
});
it('disables expired proposals and permits cancelling a pending proposal',async()=>{
 const {unmount}=render(<AssistantProposal proposal={{...water,expires_at:'2000-01-01T00:00:00Z'}}/>);
 expect(screen.queryByRole('button',{name:'Confirm proposed entry'})).toBeNull();unmount();
 vi.mocked(api).mockResolvedValue(undefined);render(<AssistantProposal proposal={water}/>);
 fireEvent.click(screen.getByRole('button',{name:'Cancel proposal'}));
 await screen.findByText('Proposal canceled.');
 expect(api).toHaveBeenCalledWith(`/assistant/actions/${water.id}/cancel`,{method:'POST'});
});
