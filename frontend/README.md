# RazorSell AI — Frontend

React + TypeScript + Vite + Tailwind CSS v4. The customer shopping experience
(chat, product cards, cart, checkout confirmation, payment result) and the
merchant dashboard (overview/analytics, orders, audit trail, failure center)
in one app, split by client-side route.

## Run locally

```bash
npm install
cp .env.example .env   # VITE_API_BASE_URL=http://localhost:8000
npm run dev
```

Requires the backend running (see `../backend/README` in the root `README.md`
for setup) — CORS is pre-configured for `http://localhost:5173`.

## Build

```bash
npm run build   # tsc -b && vite build, output in dist/
npm run preview # serve the production build locally
```

## Structure

```
src/
├── components/   Shared UI: cards, panels, modals, badges
├── pages/        CustomerPage, MerchantLoginPage, MerchantDashboardShell + tabs
├── lib/          api.ts (typed fetch client), session.ts, format.ts
├── types/        TypeScript interfaces matching the backend's Pydantic schemas
└── App.tsx       Routing
```

Every API call in `src/lib/api.ts` maps to one FastAPI endpoint documented in
the backend's `/docs`. See the root `README.md` and `docs/` for the full
product and architecture writeup.
