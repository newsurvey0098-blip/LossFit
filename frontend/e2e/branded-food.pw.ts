import {expect,test} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('USDA branded search and private import work through the catalogue UI',async({page})=>{
  const user={id:71,name:'Branded Food User',email:'branded@example.test',goals:{calories:2000,protein:120,carbs:220,fat:70},profile:{age:30}};
  const food={id:901,name:'Unsweetened oat drink',state:'prepared',verification:'imported',source:'USDA FoodData Central Branded',source_record_id:'123456',source_url:'https://fdc.nal.usda.gov/food-details/123456/nutrients',brand:'North Farm',category:'Plant based beverages',kcal:42,protein:1.2,carbs:6.5,fat:null,is_custom:true,is_favorite:false};
  let imported=false;
  await page.setViewportSize({width:390,height:844});
  await page.route('**/api/v1/auth/refresh',route=>route.fulfill({status:401,contentType:'application/json',body:JSON.stringify({detail:'Please sign in'})}));
  await page.route('**/api/v1/auth/login',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({access_token:'branded-test-token',...user})}));
  await page.route('**/api/v1/auth/me',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(user)}));
  await page.route('**/api/v1/foods*',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(imported?[food]:[])}));
  await page.route('**/api/v1/food-sources/usda-branded/status',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({available:true})}));
  await page.route('**/api/v1/food-sources/usda-branded/search**',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify([{fdc_id:123456,name:food.name,brand:food.brand,package_serving:'240 g',nutrients:{kcal:null,protein:1.2,carbs:6.5,fat:1.5},source_url:food.source_url}])}));
  await page.route('**/api/v1/food-sources/usda-branded/123456/import',route=>{
    if(route.request().method()!=='POST')return route.continue();
    imported=true;
    return route.fulfill({status:201,contentType:'application/json',body:JSON.stringify(food)});
  });

  await page.goto('/login');
  await page.getByLabel('Email').fill(user.email);
  await page.getByLabel('Password').fill('safe-password-987');
  await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await page.goto('/foods');
  await expect(page.getByRole('heading',{name:'Search USDA branded foods'})).toBeVisible();
  await expect(page.getByText(/The search term is sent to USDA/)).toBeVisible();
  await page.getByLabel('Product name or brand').fill('oat drink');
  await page.getByRole('button',{name:'Search USDA'}).click();
  await expect(page.getByRole('heading',{name:food.name})).toBeVisible();
  await expect(page.getByText('Calories unavailable')).toBeVisible();
  await expect(page.getByRole('link',{name:'USDA source record'})).toHaveAttribute('href',food.source_url);
  await page.getByRole('button',{name:`Save ${food.name} privately`}).click();
  await expect(page.getByText(/Saved privately\./)).toBeVisible();
  await expect(page.getByRole('link',{name:`Open ${food.name}`})).toHaveAttribute('href','/foods/901');
  await expect(page.getByRole('link',{name:new RegExp(`^${food.name}`)})).toBeVisible();
  await expect(page.getByText(/imported/).first()).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  expect((await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze()).violations).toEqual([]);
});
