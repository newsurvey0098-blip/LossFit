import {expect,test} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('password recovery forms validate confirmation and submit the reset token',async({page},info)=>{
 const requests:unknown[]=[];
 await page.route('**/api/v1/auth/reset-password',route=>{requests.push(route.request().postDataJSON());return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({message:'Password updated'})})});
 await page.goto('/reset-password?token=browser-test-reset-token');
 await page.setViewportSize({width:390,height:844});
 await page.screenshot({path:info.outputPath('reset-password-390.png'),fullPage:true});
 await page.setViewportSize({width:1440,height:900});
 await page.screenshot({path:info.outputPath('reset-password-1440.png'),fullPage:true});
 await page.setViewportSize({width:390,height:844});
 expect((await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze()).violations).toEqual([]);
 await page.getByLabel('New password',{exact:true}).fill('new-password-safe-987');
 await page.getByLabel('Confirm password',{exact:true}).fill('different-password-123');
 await page.getByRole('button',{name:'Update password'}).click();
 await expect(page.getByRole('alert')).toHaveText('The passwords do not match.');
 expect(requests).toHaveLength(0);
 await page.getByLabel('Confirm password',{exact:true}).fill('new-password-safe-987');
 await page.getByRole('button',{name:'Update password'}).click();
 await expect(page.getByRole('status')).toContainText('Your password has been updated.');
 expect(requests).toEqual([{token:'browser-test-reset-token',password:'new-password-safe-987'}]);
 await page.getByRole('link',{name:'Continue to sign in'}).click();
 await expect(page.getByRole('heading',{name:'Welcome back'})).toBeVisible();
});

test('a missing reset token offers a new-link workflow with private account feedback',async({page},info)=>{
 await page.route('**/api/v1/auth/forgot-password',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({message:'If an account exists for that email, password reset instructions will be sent.'})}));
 await page.goto('/reset-password');
 await page.getByLabel('New password',{exact:true}).fill('new-password-safe-987');
 await page.getByLabel('Confirm password',{exact:true}).fill('new-password-safe-987');
 await page.getByRole('button',{name:'Update password'}).click();
 await expect(page.getByRole('alert')).toContainText('missing its token');
 await page.setViewportSize({width:390,height:844});
 await page.screenshot({path:info.outputPath('reset-missing-390.png'),fullPage:true});
 await page.getByRole('link',{name:'Request another link'}).click();
 await page.screenshot({path:info.outputPath('forgot-password-390.png'),fullPage:true});
 await page.setViewportSize({width:1440,height:900});
 await page.screenshot({path:info.outputPath('forgot-password-1440.png'),fullPage:true});
 await page.setViewportSize({width:390,height:844});
 expect((await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze()).violations).toEqual([]);
 await page.getByLabel('Email').fill('recovery@example.com');
 await page.getByRole('button',{name:'Send reset link'}).click();
 await expect(page.getByRole('status')).toContainText('If an account exists');
});
