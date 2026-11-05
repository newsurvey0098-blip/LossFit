/** @vitest-environment jsdom */
import React from 'react';
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {createMemoryRouter,RouterProvider} from 'react-router-dom';
import PrivateRoute from './PrivateRoute';
import {authenticatedFetch,setAccessToken} from './api';

vi.mock('./api',()=>({authenticatedFetch:vi.fn(),setAccessToken:vi.fn()}));
const authRequest=vi.mocked(authenticatedFetch);

function renderRoutes(){
 const router=createMemoryRouter([
  {element:<PrivateRoute/>,children:[{path:'/foods',element:<h1>Private catalogue</h1>}]},
  {path:'/login',element:<h1>Sign in</h1>},
 ],{initialEntries:['/foods']});
 return render(<RouterProvider router={router}/>);
}

describe('private route session gate',()=>{
 beforeEach(()=>authRequest.mockReset());
 afterEach(()=>cleanup());

 it('redirects signed-out users to login and clears an expired access token',async()=>{
  authRequest.mockResolvedValue(new Response(null,{status:401}));
  renderRoutes();
  expect(await screen.findByRole('heading',{name:'Sign in'})).toBeTruthy();
  expect(setAccessToken).toHaveBeenCalledWith(null);
 });

 it('shows private content only after the server verifies the session',async()=>{
  authRequest.mockResolvedValue(new Response(null,{status:200}));
  renderRoutes();
  expect(await screen.findByRole('heading',{name:'Private catalogue'})).toBeTruthy();
 });

 it('offers retry after a transient session check failure',async()=>{
  authRequest.mockResolvedValueOnce(new Response(null,{status:503})).mockResolvedValueOnce(new Response(null,{status:200}));
  renderRoutes();
  expect((await screen.findByRole('alert')).textContent).toContain('Session check failed (503)');
  fireEvent.click(screen.getByRole('button',{name:'Try again'}));
  expect(await screen.findByRole('heading',{name:'Private catalogue'})).toBeTruthy();
  await waitFor(()=>expect(authRequest).toHaveBeenCalledTimes(2));
 });
});
