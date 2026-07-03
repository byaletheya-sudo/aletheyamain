# Plate Up 🍽️

Build your dream hometown-buffet plate, station by station, exactly like the real
thing circa 1995–2015. Walk the line, fight the sneeze guard, respect the soft
serve machine, get judged for your choices.

Mobile-first web game. No backend, no auth — everything runs in the browser.

## Run it

```bash
npm install
npm run dev       # local dev server
npm run build     # production build → dist/
npm run preview   # serve the production build
```

## How it plays

1. **Entrance** — the marquee, the price board, "Grab a Tray."
2. **Tray & plate** — pick a tray color and plate size (8/12/16 space units).
3. **Station walk** — 7 stations, left to right: Salad Bar → Soups & Bread →
   Hot Entrees → Carving Station → Sides → Dessert Bar → Drinks. Tap items to
   add them; each costs 1–4 plate units. Overfill and mom's voice appears —
   put something back or grab a second plate (max 2, like real life).
   Desserts go in a separate bowl that unlocks at the dessert bar. Drinks ride free.
4. **Soft serve machine** — hold to pour, release at the peak. Perfect swirl,
   respectable swirl, sad dollop, or structural failure. Your call.
5. **Find your table** — pick a booth, plate reveals on the paper placemat.
6. **The verdict** — an archetype (The Grandma Special, Certified 8-Year-Old,
   Thanksgiving in July, The Optimizer, Chaos Plate, …), a 0–100 Buffet IQ,
   and a shareable card (1080×1920 story + 1080×1080 square).

## Structure

```
src/
  data/menu.js          # every item + flavor text (single source of truth)
  data/archetypes.js    # scoring: archetypes + Buffet IQ
  store/gameStore.js    # Zustand game state
  sound.js              # tiny WebAudio synth (off by default)
  art/foodArt.jsx       # layered-SVG illustration for every item
                        # (open the app at #gallery to review the full sheet)
  components/           # Entrance, TrayPicker, StationWalk, Station, FoodItem,
                        # Plate (dock + plate render), SoftServeMachine,
                        # TableReveal, ShareCard
  fonts/                # self-hosted Titan One + Nunito (offline-friendly)
```

Stack: Vite + React 18, Zustand, framer-motion, html-to-image. Plain CSS.
`prefers-reduced-motion` is respected throughout.

## Status

- ✅ Phase 1 — core loop (all stations, full menu + flavor text, plate mechanics)
- ✅ Phase 2 — archetypes, Buffet IQ, share-card export
- ✅ Phase 3 — soft serve mini-game, animations, sneeze guard, tray rail,
  mom-voice moment, sound toggle
- ✅ Phase 4 — layered SVG food art for all 71 items (90s menu-board
  sticker style; emoji remains only as a fallback for unknown ids)
- ⬜ Phase 5 — Capacitor / App Store wrap (on hold until Edgar says go;
  parody-safe naming already in place)
