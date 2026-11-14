import { expect, test } from '@playwright/test';

test('registered user can personalize, rate, save, sign back in, and delete account', async ({ page }) => {
  const email = `browser-${Date.now()}@example.test`;
  const password = 'correct horse battery staple';
  await page.goto('/auth');
  await page.getByRole('button', { name: /need an account/i }).click();
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Register', exact: true }).click();
  await expect(page.getByText(/account is ready to sign in/i)).toBeVisible();
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page).toHaveURL(/for-you/);

  await page.goto('/genres');
  await page.getByLabel('Action').check();
  await page.getByRole('button', { name: 'Save genres' }).click();
  await expect(page).toHaveURL(/for-you/);
  await page.goto('/');
  await page.getByPlaceholder('Search by title').fill('Toy Story');
  await page.getByRole('button', { name: 'Search' }).click();
  await page.locator('.movie-card a').first().click();
  await page.getByLabel('Your rating').selectOption('4.5');
  await page.getByRole('button', { name: 'Add to watchlist' }).click();
  await expect(page.getByRole('button', { name: 'Remove from watchlist' })).toBeVisible();

  await page.goto('/account');
  await page.getByRole('button', { name: 'Sign out' }).click();
  await page.goto('/auth');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page).toHaveURL(/for-you/);
  await page.goto('/account');
  page.once('dialog', dialog => dialog.accept());
  await page.getByRole('button', { name: 'Delete account' }).click();
  await expect(page).toHaveURL('http://127.0.0.1:5173/');
});
