# Accessibility verification

The shared layout provides a keyboard-visible skip link, a focusable main landmark, focus transfer after navigation, current-page navigation announcements, and visible focus on links, buttons, inputs, selects, and textareas. Assistant access lives in the header so it does not cover scanner or form controls. Main content includes space for fixed navigation and device safe areas. Reduced motion is respected in the stylesheet.

## Automated evidence

`npm.cmd run test:e2e:local` passed both Chromium tests after these changes. The navigation test uses deterministic API fixtures and runs axe WCAG 2 A/AA and WCAG 2.1 AA checks on login, catalogue, manual food entry, and the scanner unavailable state. No violations were reported on those states. It also verifies keyboard activation of the skip link, focus on main content, the catalogue navigation announcement, horizontal overflow at 320/390/768/1440px, and that the manual-entry save button remains unobstructed after scrolling.

The companion live API test uses a freshly migrated PostgreSQL database for registration, onboarding, weight, conversations, food/meal logging, editing, exports, and deletion. The same authenticated journey now also runs axe against the profile (including meal-reminder controls) and Help page; no WCAG 2/2.1 A/AA violations were reported there.

## Remaining verification

Automated axe checks do not prove complete accessibility. Screen-reader behavior, actual browser zoom, all dialog/form error states, the configured scanner review, assistant provider responses, and every screen variant still need broader verification. Narrow viewport tests are not a substitute for a browser zoom check. No blanket WCAG conformance is claimed.

The welcome page additionally passed axe and 320/390/768/1440px reflow checks. Reduced-motion startup animation is disabled, and the branded loader disappears when the real session check completes. Desktop and mobile welcome screenshots were visually inspected.
