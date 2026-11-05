# Screen coverage inventory

Reviewed the 21 HTML exports and their 21 paired screenshots from the ZIP, the Obsidian design guide, and the 12 supplementary screenshots on 2026-11-05. The HTML is reference material only. Desktop browser interaction and visual verification remain unverified.

The original design uses mobile-first dark surfaces and food photography, a daily calorie ring, colored macro indicators, bottom navigation, camera-driven food analysis, and an assistant chat. LossFit keeps the dark nutrition dashboard direction with emerald/lime progress, blue hydration/action accents, restrained violet, keyboard-visible focus, and responsive layouts. Reduce or remove motion when `prefers-reduced-motion` is set.

| Reference | Final route | Component | Required layout and interactions | Current implementation / verification |
|---|---|---|---|---|
| `authentication_forgot_password` | `/forgot-password` | `ForgotPasswordPage` | Centered credential form; generic submission status; return-to-login link; labels, validation, keyboard focus | Implemented; SMTP delivery unavailable unless configured; API tested, browser unverified |
| `food_detail_animated` | `/foods/:foodId` | `FoodDetailPage` | Food image/detail, nutrition, serving controls, add-to-meal action; animation respects reduced motion | Shared with food detail; portion and meal logging integrated; full catalogue provenance outstanding |
| `authentication_log_in` | `/login` | `AuthPage` | Email/password form, error/success state, recovery and registration links | Implemented and API tested; browser unverified |
| `food_detail` | `/foods/:foodId` | `FoodDetailPage` | Food detail with portion and meal assignment | Implemented for available catalogue records; serving shortcuts, nutrition source labels, and add-to-meal API integrated; browser unverified |
| `authentication_link_google_account` | `/settings/accounts` | `ConnectedAccountsPage` | Connected methods, reauthentication, safe link/unlink, unavailable-provider explanation | Not implemented; Google credentials/provider unavailable |
| `welcome_to_nutritrack_ai_animated` | `/` | `LandingPage` | Brand introduction, clear sign-in/register actions, reduced-motion intro | Partial placeholder only; functional marketing/onboarding entry outstanding |
| `welcome_to_nutritrack_ai_updated` | `/` | `LandingPage` | Updated welcome layout consistent with brand and accessible navigation | Partial placeholder only |
| `today_s_dashboard` | `/home` | `DashboardPage` | Daily calorie ring, macro progress, hydration controls, dated meal cards, quick actions | Partial; daily totals, hydration, and meal links use API; analytics details and visual review outstanding |
| `meal_detail_lunch` | `/meals/new`, `/meals/:mealId` | `NewMealPage`, `MealDetailPage` | Meal composition, detail, editable items/portions, save and delete with feedback | Multi-food creation, serving selection, add/remove/edit items, time/type/name editing, save and delete implemented against API; backend ownership-tested; browser unverified |
| `ai_nutrition_assistant` | `/assistant/:conversationId?` | `AssistantPage` | Conversation list, new/delete/clear, chat history, retry, loading, outage states | Implemented with persisted API; deterministic mocked provider tested; live provider unverified |
| `food_items` | `/foods` | `FoodsPage` | Searchable catalogue, recent/favorite states, food navigation, add custom food | Search includes aliases; private custom-food create/edit/delete and servings implemented; public imported catalogue, favorites/recent outstanding |
| `food_log_analytics` | `/log`, `/analytics` | `FoodLogPage`, `AnalyticsPage` | Dated meal history, range filters, daily/week/month charts and empty states | Routes/screens not implemented; JSON/CSV exports exist |
| `profile_settings` | `/profile`, `/settings` | `ProfilePage`, `SettingsPage` | Profile, targets, preferences, units, exports, account/privacy controls | Profile goals, weight link, exports, sign-out and account deletion implemented; settings/preferences editing incomplete |
| `app_launch_splash_animated_3` | application startup | `AppBootstrapScreen` | Brief accessible startup/loading transition, no motion when reduced | Not implemented; app loads directly |
| `ai_scanner` | `/scan`, `/scan/review` | `ScannerPage`, `ScannerReviewPage` | Camera/upload, progress, candidate resolution, portion editing, confirm or remove uncertain items | Not implemented; scanner and vision integration unavailable |
| `body_metrics_step_1_of_2` | `/onboarding/body` | `OnboardingPage` | Age, sex, height, weight, goal and activity inputs; validation and step progress | Implemented with persisted target calculation and weight; tested, browser unverified |
| `today_s_dashboard_animated` | `/home` | `DashboardPage` | Same dashboard behavior with restrained, optional micro-animations | Shared dashboard; motion and browser verification outstanding |
| `authentication_sign_up` | `/register` | `AuthPage` | Name/email/password, validation, privacy copy, onboarding transition | Implemented and API tested; browser unverified |
| `preferences_habits_step_2_of_2` | `/onboarding/preferences` | `OnboardingPage` | Dietary preference, allergies, timezone/units, finish and back navigation | Persisted preference fields partially implemented; incomplete unit UX; API validation tested |
| `authentication_signing_in` | `/auth/callback` and login transition | `AuthCallbackPage`, `SigningInState` | Explicit loading, success redirect and failure recovery | Login transition exists; callback/Google OAuth not implemented |
| `add_manually` | `/foods/new` | `ManualFoodPage` | Food name/state, nutrition inputs, serving, validation and saved result | Private custom-food form/API includes optional portion shortcut, category, brand, aliases, raw/cooked/prepared states and null nutrients; browser unverified |

## Global responsive and accessibility requirements

- Use semantic landmarks, real links/buttons, associated labels, keyboard navigation, visible focus indicators, screen-reader status/error announcements, sufficient contrast, and layouts that remain usable at 200% zoom.
- Verify mobile, tablet, and desktop breakpoints. Keep bottom navigation clear of scanner controls, form actions, and dialogs; allow content to scroll behind fixed navigation with safe-area padding.
- Provide loading, empty, success, and error states for every asynchronous view. No inert placeholder links or unreported unavailable integrations.
- Keep all forms usable with keyboard and touch; honor reduced-motion settings.

## Cross-screen feature references

Favorites/recent foods, reminders, barcode and label scanning, Google linking, manual-entry images, serving units, meal assignment, profile units, and help appear in the reference family. Each is either mapped above to an implementation task or explicitly marked outstanding/unavailable; none should be treated as silently delivered.
