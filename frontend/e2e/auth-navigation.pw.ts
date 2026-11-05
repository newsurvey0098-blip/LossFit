import {expect,test} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('signed-out users can sign in to the requested private page at mobile and desktop sizes',async({page})=>{
    await page.setViewportSize({width:390,height:844});
    await page.route('**/api/v1/auth/refresh',route=>route.fulfill({status:401,contentType:'application/json',body:JSON.stringify({detail:'Please sign in'})}));
    await page.route('**/api/v1/auth/login',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({access_token:'browser-test-token',id:7,name:'Lena',email:'lena@example.test',goals:{calories:2000,protein:120,carbs:220,fat:70},profile:{age:30}})}));
    await page.route('**/api/v1/auth/me',route=>{
      if(!route.request().headers()['authorization'])return route.fulfill({status:401,contentType:'application/json',body:JSON.stringify({detail:'Please sign in'})});
      expect(route.request().headers()['authorization']).toBe('Bearer browser-test-token');
      return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({id:7,name:'Lena',email:'lena@example.test',goals:{calories:2000,protein:120,carbs:220,fat:70},profile:{age:30}})});
    });
    await page.route('**/api/v1/foods**',route=>route.fulfill({status:200,contentType:'application/json',body:'[]'}));

    await page.goto('/foods');
    await expect(page.getByRole('heading',{name:'Welcome back'})).toBeVisible();
    expect((await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze()).violations).toEqual([]);
    await expect(page.locator('nav[aria-label="Main navigation"]')).toHaveCount(0);
    await page.getByLabel('Email').fill('lena@example.test');
    await page.getByLabel('Password').fill('safe-password-987');
    await page.getByRole('button',{name:'Sign in'}).click();
    await expect(page).toHaveURL(/\/foods$/);
    await expect(page.getByRole('heading',{name:'Find your next meal'})).toBeVisible();
    await expect(page.locator('nav[aria-label="Main navigation"]')).toBeVisible();
    await expect(page.getByRole('link',{name:'Foods',exact:true})).toHaveAttribute('aria-current','page');
    await page.getByRole('link',{name:'Skip to main content'}).focus();
    await page.keyboard.press('Enter');
    await expect(page.locator('main')).toBeFocused();
    expect((await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze()).violations).toEqual([]);
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
    await page.setViewportSize({width:768,height:1024});
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
    await page.setViewportSize({width:1440,height:900});
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
    await page.getByRole('link',{name:'Add manually',exact:true}).first().click();
    await page.setViewportSize({width:320,height:640});
    expect((await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze()).violations).toEqual([]);
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
    const save=page.getByRole('button',{name:'Save food',exact:true});
    await save.scrollIntoViewIfNeeded();
    expect(await save.evaluate(button=>{const box=button.getBoundingClientRect();const target=document.elementFromPoint(box.x+box.width/2,box.y+box.height/2);return target===button||button.contains(target)})).toBe(true);
    await page.route('**/api/v1/scan/status',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({available:false})}));
    await page.goBack();
    await page.getByRole('link',{name:'Scan a meal',exact:true}).click();
    await expect(page.getByRole('status')).toContainText('not configured');
    expect((await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze()).violations).toEqual([]);
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
});
