import {expect,test} from '@playwright/test';

test('registration, onboarding, private food, and meal persist through the API',async({page})=>{
  const suffix=crypto.randomUUID();
  await page.goto('/register');
  await page.getByLabel('Name').fill('Browser Test User');
  await page.getByLabel('Email').fill(`browser-${suffix}@example.com`);
  await page.getByLabel('Password').fill('safe-password-987');
  await page.getByRole('button',{name:'Create account'}).click();
  await expect(page.getByRole('heading',{name:'Let’s get to know you.'})).toBeVisible();
  await page.getByRole('button',{name:'Continue'}).click();
  await expect(page.getByRole('heading',{name:'How you eat and move.'})).toBeVisible();
  await page.getByRole('button',{name:'Finish setup'}).click();
  await expect(page.getByRole('heading',{name:'Your profile is ready'})).toBeVisible();
  await expect(page.getByRole('heading',{name:'Good morning, Browser Test User.'})).toBeVisible({timeout:5000});

  await page.goto('/foods/new');
  await page.getByLabel('Food name').fill('Browser test oatmeal');
  await page.getByLabel('Preparation state').selectOption('cooked');
  await page.getByLabel('Calories (kcal)').fill('150');
  await page.getByLabel('Protein (g)').fill('5');
  await page.getByLabel('Carbohydrates (g)').fill('27');
  await page.getByLabel('Fat (g)').fill('3');
  await page.getByRole('button',{name:'Save food'}).click();
  await expect(page.getByRole('status')).toContainText('Food saved to your private catalogue.');

  await page.goto('/meals/new');
  await page.getByLabel('Meal name').fill('Persisted oatmeal breakfast');
  await page.getByLabel('Search foods to add').fill('Browser test oatmeal');
  await page.getByRole('button',{name:/Browser test oatmeal/}).click();
  await page.getByLabel('Amount in grams').fill('150');
  await page.getByRole('button',{name:'Add item'}).click();
  await page.getByRole('button',{name:'Save meal'}).click();
  await expect(page.getByRole('heading',{name:'Persisted oatmeal breakfast'})).toBeVisible();
  await expect(page.getByText('225 kcal')).toBeVisible();

  const detailUrl=page.url();
  await page.reload();
  await expect(page.getByRole('heading',{name:'Persisted oatmeal breakfast'})).toBeVisible();
  await expect(page.getByText('225 kcal')).toBeVisible();
  expect(page.url()).toBe(detailUrl);
});
