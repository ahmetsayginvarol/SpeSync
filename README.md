# Nocturne Pre-Order Management

Web-based cruise ship restaurant pre-order management system. Replaces the SpeSync desktop app suite with a Firebase-powered web application accessible from any device.

## Stack

| Layer | Tech |
|---|---|
| Frontend | React 18 + TypeScript + Vite + Tailwind CSS |
| Database | Firebase Firestore (real-time, offline-capable) |
| Auth | Firebase Authentication + custom claims (role-based) |
| Server logic | Firebase Cloud Functions (TypeScript) |
| File storage | Firebase Storage (guest CSV imports) |
| Hosting | Firebase Hosting |

## Project Structure

```
nocturne_order/
├── frontend/          # React + Vite app
│   └── src/
│       ├── pages/
│       │   ├── restaurant/   # Order entry
│       │   ├── galley/       # Kitchen board (live via Firestore onSnapshot)
│       │   ├── admin/        # Users, venues, allergies, voyages, config
│       │   └── reports/      # PDF export (client-side jsPDF)
│       ├── hooks/            # useOrders, useAppConfig
│       ├── lib/              # api.ts, pdf.ts, utils.ts
│       └── context/          # AuthContext
├── functions/         # Cloud Functions (TypeScript)
│   └── src/
│       ├── auth/             # setUserRole (callable)
│       ├── orders/           # carryStandingOrders (scheduled)
│       ├── guests/           # importGuestsOnUpload (Storage trigger)
│       └── voyages/          # archiveVoyage (callable)
├── firestore.rules    # Role-based security rules
├── firestore.indexes.json
└── firebase.json
```

## Roles

| Role | Access |
|---|---|
| `admin` | Everything: users, venues, voyages, config, all views |
| `restaurant` | Order entry + reports |
| `galley` | Galley board (read orders, write chef flag/remark) |

## Setup

### 1. Firebase project

1. Create a Firebase project at [console.firebase.google.com](https://console.firebase.google.com)
2. Enable **Authentication** (Email/Password provider)
3. Enable **Firestore** (start in production mode)
4. Enable **Storage**
5. Update `.firebaserc` with your project ID

### 2. Frontend

```bash
cd frontend
cp .env.example .env.local
# Fill in your Firebase config values from the Firebase console
npm install
npm run dev
```

### 3. Cloud Functions

```bash
cd functions
npm install
npm run build
```

### 4. Deploy

```bash
npm install -g firebase-tools
firebase login
firebase deploy
```

### 5. Seed initial data

After deploying, use the Admin panel to:
1. Set a first admin user (use Firebase console to manually set the `role: "admin"` custom claim for the first user)
2. Add venues
3. Add allergies (or use "Seed defaults")
4. Create a voyage and set it as active
5. Upload a guest manifest CSV (columns: `cabin_number`, `first_name`, `last_name`)

## Standing Orders

A Cloud Scheduler job (`carryStandingOrders`) runs daily at 3 AM UTC. It copies all standing-order preorders from today to tomorrow under the active voyage. The schedule can be adjusted in `functions/src/orders/carryStandingOrders.ts`.

## Offline Support

Firestore offline persistence is enabled by default (`enableIndexedDbPersistence`). Restaurant staff can continue entering orders during connectivity drops; changes sync automatically when the connection is restored.
