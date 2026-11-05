import {expect,test} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test.use({reducedMotion:'reduce'});

test('welcome content reflows and account links work with reduced motion',async({page},info)=>{
 await page.goto('/');
 await expect(page.getByRole('heading',{level:1})).toContainText('Know what you eat.');
 await expect(page.getByLabel('Illustrative daily nutrition summary')).toBeVisible();
 expect((await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze()).violations).toEqual([]);
 for(const width of [320,390,768,1440]){
  await page.setViewportSize({width,height:900});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 }
 await page.screenshot({path:info.outputPath('welcome-desktop.png'),fullPage:true});
 await page.setViewportSize({width:390,height:844});
 await page.screenshot({path:info.outputPath('welcome-mobile.png'),fullPage:true});
 await page.getByRole('link',{name:'Explore LossFit'}).click();
 await expect(page).toHaveURL(/#how-it-works$/);
 await page.getByRole('link',{name:'Create your account',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Create your account'})).toBeVisible();
});

test('branded startup waits for the real session check without motion or an artificial delay',async({page})=>{
 let release!:()=>void;
 await page.route('**/api/v1/auth/refresh',route=>new Promise<void>(resolve=>{release=()=>{void route.fulfill({status:401,contentType:'application/json',body:'{}'}).then(resolve)}}));
 await page.route('**/api/v1/auth/me',route=>route.fulfill({status:401,contentType:'application/json',body:'{}'}));
 await page.goto('/home');
 await expect(page.getByRole('status')).toHaveText('Checking your session…');
 expect(await page.locator('.bootstrap-mark').evaluate(element=>getComputedStyle(element).animationName)).toBe('none');
 release();
 await expect(page.getByRole('heading',{name:'Welcome back'})).toBeVisible();
});
