import React from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Link, Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom';
import { Activity, ArrowRight, CircleUserRound, Flame, Home, Plus, Sparkles, Utensils, Droplets, ChevronRight } from 'lucide-react';
import './style.css';
import AuthPage from './AuthPage';
import { api } from './api';
import { FoodsPage, ManualFoodPage, FoodDetailPage, EditFoodPage } from './FoodPages';
import ProfilePage from './ProfilePage';
import MealDetailPage, { NewMealPage } from './MealDetailPage';
import AssistantPage from './AssistantPage';
import OnboardingPage from './OnboardingPage';
import WeightPage from './WeightPage';
import { ForgotPasswordPage, ResetPasswordPage } from './PasswordPages';
import { AnalyticsPage, FoodLogPage } from './AnalyticsPages';
import { BarcodeScannerPage, NutritionLabelPage, ScannerPage, ScannerReviewPage } from './ScanPages';
import LearningPage from './LearningPage';
import ConnectedAccountsPage from './ConnectedAccountsPage';
import PrivateRoute from './PrivateRoute';
import LandingPage from './LandingPage';
import RecipePage from './RecipePage';
import ReminderNotice from './ReminderNotice';
import HelpPage from './HelpPage';

function usePageFocus(){const {pathname}=useLocation();React.useEffect(()=>{const main=document.getElementById('main-content');main?.focus({preventScroll:true});main?.scrollTo(0,0);window.scrollTo(0,0)},[pathname]);}
function PublicFrame(){usePageFocus();return <main className="public-frame" id="main-content" tabIndex={-1}><Outlet/></main>;}

function Shell({ children }: { children: React.ReactNode }) {
  const location = useLocation();usePageFocus();
  return <div className="app-shell">
    <header className="top">
      <Link to="/home" className="brand"><span className="mark"><Flame size={19} /></span>LossFit</Link>
      <div className="top-right"><Link className="icon" to="/assistant" aria-label="Ask the nutrition assistant"><Sparkles size={20}/></Link><span className="date">{new Date().toLocaleDateString(undefined,{weekday:'long',month:'short',day:'numeric'}).toUpperCase()}</span><Link className="avatar" to="/profile" aria-label="Profile settings">J</Link></div>
    </header>
    <main id="main-content" tabIndex={-1}>{children}</main>
    <nav className="bottom" aria-label="Main navigation">
      {[[Home,'Home','/home'],[Activity,'Insights','/analytics'],[Plus,'Add','/meals/new'],[Utensils,'Foods','/foods'],[CircleUserRound,'Profile','/profile']].map(([Icon,label,path]:any)=><Link key={label} aria-current={(location.pathname===path||(path==='/foods'&&location.pathname.startsWith('/foods/')))?'page':undefined} className={`navitem ${location.pathname===path?'active':''} ${label==='Add'?'addnav':''}`} to={path}><Icon size={label==='Add'?22:19}/><span>{label}</span></Link>)}
    </nav>

  </div>;
}

function PrivateShell(){return <Shell><ReminderNotice/><Outlet/></Shell>}

function Dashboard() {
  const [summary,setSummary]=React.useState<any>(null);
  const [recommendations,setRecommendations]=React.useState<any>(null);
  const [recommendationError,setRecommendationError]=React.useState('');
  const [name,setName]=React.useState('there');
  const [water,setWater]=React.useState(0);
  const [busy,setBusy]=React.useState(true);
  const [error,setError]=React.useState('');
  React.useEffect(()=>{
    let active=true;
    api('/recommendations/daily').then(value=>active&&setRecommendations(value)).catch((e:Error)=>active&&setRecommendationError(e.message));
    Promise.all([api('/analytics/daily'),api('/auth/me')]).then(([daily,user]:any[])=>{
      if(!active)return;setSummary(daily);setWater(daily.water_ml/1000);setName(user.name||'there');
    }).catch((e:Error)=>active&&setError(e.message)).finally(()=>active&&setBusy(false));
    return()=>{active=false};
  },[]);
  async function addWater(ml:number){try{await api('/water?ml='+ml,{method:'POST'});setWater(v=>v+ml/1000);setError('')}catch(e:any){setError(e.message)}}
  const goals=summary?.goals??{calories:2100,protein:140,carbs:220,fat:70};
  const totals=summary?.totals??{};
  const remaining=totals.kcal==null?null:Math.max(goals.calories-totals.kcal,0);
  const caloriesPct=totals.kcal==null?0:Math.min(totals.kcal/goals.calories*100,100);
  return <>
    <div className="welcome"><div><p className="eyebrow">YOUR DAILY SNAPSHOT</p><h1>Good morning, {name}<span className="green">.</span></h1><p className="muted">A steady day starts with small choices.</p></div><div className="actions"><Link className="textlink" to="/log">Today’s log <ArrowRight size={15}/></Link><Link className="textlink" to="/learn">Learn <ArrowRight size={15}/></Link><Link className="button primary" to="/meals/new">Log a meal</Link></div></div>
    {error&&<p role="alert" className="error">{error} <Link to="/login">Sign in</Link></p>}
    {busy?<p role="status" className="muted">Loading your day…</p>:<>
      <section className="hero grid">
        <article className="card calorie"><div className="ring" style={{background:`radial-gradient(closest-side,#111214 86%,transparent 88%),conic-gradient(#b7e85b ${caloriesPct}%,#30342b 0)`}}><div><strong>{totals.kcal==null?'—':Math.round(totals.kcal)}</strong><small>kcal eaten</small></div></div><div className="calcopy"><span className="pill"><span className="dot"/>{remaining==null?'Calories unavailable':`${Math.round(remaining)} kcal remaining`}</span><h2>On your way</h2><p className="muted">Daily target: {goals.calories} kcal</p></div></article>
        <article className="card macro"><div className="sectionhead"><div><p className="eyebrow">DAILY GOALS</p><h2>Macros</h2></div><Link className="textlink" to="/analytics">View insights <ChevronRight size={14}/></Link></div>
          {([['Protein','protein','lime'],['Carbohydrates','carbs','blue'],['Fat','fat','violet']] as const).map(([label,key,color])=>{const amount=totals[key] as number|null|undefined;const target=goals[key];return <div className="macro-row" key={key}><div><b>{label}</b><span>{amount==null?'—':Math.round(amount)} <i>/ {target}g</i></span></div><div className="track"><div className={color} style={{width:amount==null?'0%':`${Math.min(amount/target*100,100)}%`}}/></div></div>})}
        </article>
      </section>
      <section className="card water"><div className="watericon"><Droplets size={20}/></div><div className="watermain"><div className="sectionhead"><div><p className="eyebrow">HYDRATION</p><h2>{water.toFixed(1)} <span className="muted">/ 3.5 L</span></h2></div><span className="muted">Daily goal</span></div><div className="track"><div className="blue" style={{width:`${Math.min(water/3.5*100,100)}%`}}/></div><div className="wateractions">{[250,500,750].map(ml=><button key={ml} className="chip" onClick={()=>addWater(ml)}><Plus size={13}/>{ml} ml</button>)}</div></div></section>
      <section className="card simple" aria-labelledby="daily-suggestions-title"><div className="sectionhead"><div><p className="eyebrow">PERSONALIZED IDEAS</p><h2 id="daily-suggestions-title">Suggestions for today</h2></div><span className="pill">Based on your log</span></div>{recommendationError?<p className="error" role="alert">Suggestions are unavailable right now. Your food log still works.</p>:!recommendations?<p className="muted" role="status">Finding catalogue options…</p>:<><p className="muted">{recommendations.message}</p>{recommendations.items?.length>0&&<div className="mealgrid">{recommendations.items.map((item:any)=><Link className="card meal" key={item.food_id} to={`/foods/${item.food_id}`}><div className="mealemoji" aria-hidden="true">🥗</div><div className="mealcontent"><h3>{item.name}</h3><p className="muted">{item.reason}</p><div className="nutrients"><span>{item.kcal==null?'Calories unavailable':`${Math.round(item.kcal*item.serving_grams/100)} kcal`}</span><span>Protein <b>{item.protein==null?'—':(item.protein*item.serving_grams/100).toFixed(1)}g</b></span><span>{item.serving_label} · {item.serving_grams}g</span></div><small className="muted">{item.verification.replace('_',' ')}{item.source?` · ${item.source}`:''}</small></div><ChevronRight size={17} className="chev"/></Link>)}</div>}{recommendations.caution&&<p className="integration-note" role="note">{recommendations.caution}</p>}</>}</section>
      <div className="sectionhead meals-title"><div><p className="eyebrow">{summary?.date?new Date(`${summary.date}T12:00:00`).toLocaleDateString(undefined,{weekday:'long',month:'long',day:'numeric'}).toUpperCase():'TODAY'}</p><h2>Today’s meals</h2></div><Link className="textlink" to="/log">Full food log <ArrowRight size={15}/></Link></div>
      <div className="mealgrid">{(summary?.meals??[]).map((meal:any)=><Link to={`/meals/${meal.id}`} className="card meal" key={meal.id}><div className="mealemoji" aria-hidden="true">🍽️</div><div className="mealcontent"><div className="mealrow"><h3>{meal.name}</h3><span className="kcal">{meal.kcal==null?'—':Math.round(meal.kcal)} kcal</span></div><p className="muted">{meal.meal_type}</p><div className="nutrients"><span><b>{meal.protein??'—'}g</b> protein</span><span><b>{meal.carbs??'—'}g</b> carbs</span><span><b>{meal.fat??'—'}g</b> fat</span></div></div><ChevronRight size={17} className="chev"/></Link>)}</div>
      {!summary?.meals?.length&&<section className="card simple"><p className="muted">No meals logged yet today.</p><Link className="button primary" to="/meals/new">Add your first meal</Link></section>}
    </>}
  </>;
}

function NotFound(){return <section className="card simple"><p className="eyebrow">404</p><h1>Page not found</h1><p className="muted">That LossFit page isn’t available.</p><Link className="button primary" to="/home">Back to today</Link></section>}
function App(){return <><a className="skip-link" href="#main-content">Skip to main content</a><Routes><Route element={<PublicFrame/>}>
  <Route path="/" element={<LandingPage/>}/><Route path="/login" element={<AuthPage/>}/><Route path="/forgot-password" element={<ForgotPasswordPage/>}/><Route path="/reset-password" element={<ResetPasswordPage/>}/><Route path="/register" element={<AuthPage register/>}/>
  </Route><Route element={<PrivateRoute/>}><Route element={<PrivateShell/>}>
    <Route path="/onboarding/body" element={<OnboardingPage/>}/><Route path="/onboarding/preferences" element={<OnboardingPage/>}/><Route path="/weight" element={<WeightPage/>}/><Route path="/home" element={<Dashboard/>}/>
    <Route path="/recipes/new" element={<RecipePage/>}/><Route path="/recipes/:foodId/edit" element={<RecipePage/>}/><Route path="/foods" element={<FoodsPage/>}/><Route path="/foods/new" element={<ManualFoodPage/>}/><Route path="/foods/:foodId/edit" element={<EditFoodPage/>}/><Route path="/foods/:foodId" element={<FoodDetailPage/>}/><Route path="/learn/:slug?" element={<LearningPage/>}/>
    <Route path="/scan" element={<ScannerPage/>}/><Route path="/scan/barcode" element={<BarcodeScannerPage/>}/><Route path="/scan/label" element={<NutritionLabelPage/>}/><Route path="/scan/review/:scanId" element={<ScannerReviewPage/>}/>
    <Route path="/meals/new" element={<NewMealPage/>}/><Route path="/meals/:mealId" element={<MealDetailPage/>}/><Route path="/log" element={<FoodLogPage/>}/><Route path="/analytics" element={<AnalyticsPage/>}/>
    <Route path="/profile" element={<ProfilePage/>}/><Route path="/settings" element={<Navigate to="/profile" replace/>}/><Route path="/settings/accounts" element={<ConnectedAccountsPage/>}/><Route path="/help" element={<HelpPage/>}/><Route path="/assistant/:conversationId?" element={<AssistantPage/>}/>
  </Route></Route>
  <Route element={<PublicFrame/>}><Route path="*" element={<NotFound/>}/></Route>
</Routes></>}

createRoot(document.getElementById('root')!).render(<React.StrictMode><BrowserRouter><App/></BrowserRouter></React.StrictMode>);
