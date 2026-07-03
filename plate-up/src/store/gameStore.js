import { create } from 'zustand'
import { PLATE_SIZES, BOWL_CAPACITY, MAX_PLATES, STATIONS } from '../data/menu.js'
import { sound } from '../sound.js'

// phases: entrance → tray → stations → booth → reveal
export const useGame = create((set, get) => ({
  phase: 'entrance',
  soundOn: false,
  trayColor: 'brown',
  plateSize: 'regular',
  stationIndex: 0,
  plates: [[]], // array of plates, each an array of item objects
  activePlate: 0,
  dessertBowl: [],
  drink: null,
  softServe: null, // { flavor, quality }
  momMoment: null, // { text, canSecondPlate }
  momMoments: 0, // times you got The Voice (scoring)
  toast: null, // { name, flavorText, key }
  booth: null,

  setPhase: (phase) => set({ phase }),
  toggleSound: () => {
    const on = !get().soundOn
    sound.enabled = on
    set({ soundOn: on })
  },
  chooseTray: (trayColor) => set({ trayColor }),
  choosePlateSize: (plateSize) => set({ plateSize }),

  capacity: () => PLATE_SIZES[get().plateSize].capacity,
  plateUsed: (idx) => get().plates[idx].reduce((a, i) => a + i.size, 0),
  bowlUsed: () => get().dessertBowl.reduce((a, i) => a + i.size, 0),

  nextStation: () => {
    const { stationIndex } = get()
    if (stationIndex < STATIONS.length - 1) set({ stationIndex: stationIndex + 1 })
    else set({ phase: 'booth', toast: null })
  },
  prevStation: () => {
    const { stationIndex } = get()
    if (stationIndex > 0) set({ stationIndex: stationIndex - 1 })
  },

  dessertUnlocked: () => get().stationIndex >= STATIONS.findIndex((s) => s.id === 'dessert-bar'),

  addItem: (item) => {
    const s = get()
    const showToast = () =>
      set({ toast: { name: item.name, flavorText: item.flavorText, key: Math.random() } })

    if (item.category === 'drink') {
      set({ drink: item })
      sound.ding()
      showToast()
      return 'drink'
    }

    if (item.category === 'dessert') {
      // desserts live in the bowl, which unlocks at the dessert station
      const used = s.bowlUsed()
      if (used + item.size > BOWL_CAPACITY) {
        sound.womp()
        set({
          momMoment: {
            text: 'The bowl has limits. The bowl is not a plate. Even here, there are rules.',
            canSecondPlate: false,
          },
          momMoments: s.momMoments + 1,
        })
        return 'full'
      }
      // soft serve replaces previous soft serve — the machine forgives
      const bowl = item.softServe
        ? [...s.dessertBowl.filter((i) => !i.softServe), item]
        : [...s.dessertBowl, item]
      set({ dessertBowl: bowl, softServe: item.softServe || s.softServe })
      sound.ding()
      showToast()
      return 'dessert'
    }

    const idx = s.activePlate
    const used = s.plateUsed(idx)
    if (used + item.size > s.capacity()) {
      sound.womp()
      set({
        momMoment: {
          text: '“Your eyes are bigger than your stomach.”',
          canSecondPlate: s.plates.length < MAX_PLATES,
        },
        momMoments: s.momMoments + 1,
      })
      return 'full'
    }
    const plates = s.plates.map((p, i) => (i === idx ? [...p, item] : p))
    set({ plates })
    sound.ding()
    showToast()
    return 'added'
  },

  removeItem: (zone, idx) => {
    const s = get()
    sound.blip()
    if (zone === 'bowl') {
      const removed = s.dessertBowl[idx]
      set({
        dessertBowl: s.dessertBowl.filter((_, i) => i !== idx),
        softServe: removed && removed.softServe ? null : s.softServe,
      })
    } else if (zone === 'drink') {
      set({ drink: null })
    } else {
      const plates = s.plates.map((p, i) => (i === zone ? p.filter((_, j) => j !== idx) : p))
      set({ plates })
    }
  },

  grabSecondPlate: () => {
    const s = get()
    if (s.plates.length >= MAX_PLATES) return
    sound.ding()
    set({ plates: [...s.plates, []], activePlate: s.plates.length, momMoment: null })
  },
  setActivePlate: (activePlate) => set({ activePlate }),
  dismissMom: () => set({ momMoment: null }),
  clearToast: () => set({ toast: null }),

  chooseBooth: (booth) => {
    sound.ding()
    set({ booth, phase: 'reveal', toast: null })
  },

  allItems: () => {
    const s = get()
    return [...s.plates.flat(), ...s.dessertBowl, ...(s.drink ? [s.drink] : [])]
  },

  scoringMeta: () => {
    const s = get()
    const capacity = s.capacity() * s.plates.length
    const plateUnits = s.plates.flat().reduce((a, i) => a + i.size, 0)
    return {
      capacity,
      used: plateUnits,
      plateUnits,
      efficiency: capacity ? plateUnits / capacity : 0,
      plateCount: s.plates.length,
      softServe: s.softServe,
      momMoments: s.momMoments,
    }
  },

  // Go back for seconds — one tap, clean slate, same tray preferences.
  reset: () =>
    set({
      phase: 'entrance',
      stationIndex: 0,
      plates: [[]],
      activePlate: 0,
      dessertBowl: [],
      drink: null,
      softServe: null,
      momMoment: null,
      momMoments: 0,
      toast: null,
      booth: null,
    }),
}))
