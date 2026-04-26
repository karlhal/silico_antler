# Render + Cloudflare Launch Runbook

## 1) Render API service

Service root: `apps/api`

Required environment variables:

- `BOOKING_URL`
- `ANALYTICS_KEY`
- `CONTACT_EMAIL`
- `CONTACT_WEBHOOK_URL`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM_EMAIL`
- `SMTP_USE_SSL`
- `SMTP_USE_STARTTLS`
- `WEBSITE_URL=https://silico-labs.com`
- `ALLOWED_ORIGINS=https://silico-labs.com,https://www.silico-labs.com`

Health checks:

- `/api/health`
- `/api/ready`

## 2) Cloudflare Pages frontend

Project settings:

- Root directory: `apps/marketing`
- Build command: `npm run build`
- Build output directory: `dist`
- Environment variable: `VITE_API_BASE_URL=https://api.silico-labs.com`

## 3) DNS and proxy

- Add `api.silico-labs.com` CNAME record to the Render service hostname.
- Keep Cloudflare proxy enabled.
- Add cache bypass rule for `api.silico-labs.com/*`.

## 4) Smoke test checklist

- `https://silico-labs.com` loads the real marketing site.
- `https://silico-labs.com/showcase/` loads demo page.
- `https://silico-labs.com/showcase` redirects to `/showcase/`.
- `https://api.silico-labs.com/api/health` returns `{ "status": "ok" }`.
- `https://api.silico-labs.com/api/ready` returns `{ "status": "ready" }`.
- Landing CTA opens booking link.
- Showcase can load presets and run simulation.
- Contact form success and error states are visible.

## 5) Rollback

- Re-deploy the previous Cloudflare Pages build if marketing regressions appear.
- If API issues block the demo, switch `VITE_API_BASE_URL` to the previous stable API deployment.
- As a last resort, re-deploy the previous marketing build artifact while investigating.
