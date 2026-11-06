import AppBootstrapScreen from './AppBootstrapScreen';
import React from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { authenticatedFetch, setAccessToken } from './api';

export default function PrivateRoute() {
  const location=useLocation();
  const [state,setState]=React.useState<'checking'|'ready'|'signed-out'|'error'>('checking');
  const [error,setError]=React.useState('');
  const verify=React.useCallback(async()=>{
    setState('checking');setError('');
    try{
      const response=await authenticatedFetch('/auth/me');
      if(response.status===401){setAccessToken(null);setState('signed-out');return;}
      if(!response.ok)throw new Error(`Session check failed (${response.status})`);
      setState('ready');
    }catch(reason){setError(reason instanceof Error?reason.message:'Session check failed');setState('error');}
  },[]);
  React.useEffect(()=>{void verify();},[verify]);
  if(state==='checking')return <AppBootstrapScreen/>;
  if(state==='error')return <main id="main-content" tabIndex={-1}><section className="card simple"><h1>Can’t verify your session</h1><p role="alert" className="error">{error}</p><button type="button" className="button primary" onClick={()=>void verify()}>Try again</button></section></main>;
  if(state==='signed-out')return <Navigate to="/login" replace state={{from:location.pathname}}/>;
  return <Outlet/>;
}
