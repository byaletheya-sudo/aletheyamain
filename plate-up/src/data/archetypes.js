// ============================================================
// PLATE UP — scoring. Archetypes + Buffet IQ.
// Input: every item on both plates + dessert bowl + drink,
// plus meta about the run. Output: who you are, numerically.
// ============================================================

const count = (items, fn) => items.filter(fn).length
const hasId = (items, id) => items.some((i) => i.id === id)
const hasTag = (i, t) => i.tags && i.tags.includes(t)

// Each archetype scores the plate 0–100; highest score wins.
// Order matters only for ties (earlier wins).
export const ARCHETYPES = [
  {
    id: 'thanksgiving-in-july',
    name: 'Thanksgiving in July',
    emoji: '🦃',
    tagline: 'The calendar is a suggestion. The gravy is a lifestyle.',
    match(items) {
      const carving = count(items, (i) => i.station === 'carving')
      const stuffing = hasId(items, 'stuffing')
      const gbc = hasId(items, 'green-bean-casserole')
      const extras = count(items, (i) => hasTag(i, 'thanksgiving'))
      if (carving && stuffing && gbc) return 95 + Math.min(5, extras)
      if (carving && (stuffing || gbc)) return 62 + extras * 2
      return 0
    },
  },
  {
    id: 'grandma-special',
    name: 'The Grandma Special',
    emoji: '👵',
    tagline: 'Cottage cheese, jello, and the quiet confidence of a woman who survived the Depression.',
    match(items) {
      const grandma = count(items, (i) => hasTag(i, 'grandma'))
      const wobble = hasId(items, 'jello-cubes') || hasId(items, 'cottage-cheese') || hasId(items, 'sugar-free-jello')
      const saladHeavy = count(items, (i) => i.category === 'salad') >= 3
      if (grandma >= 4 && wobble) return 88 + Math.min(8, grandma)
      if (grandma >= 3 && wobble && saladHeavy) return 80
      if (grandma >= 5) return 66
      return 0
    },
  },
  {
    id: 'certified-8-year-old',
    name: 'Certified 8-Year-Old',
    emoji: '🧒',
    tagline: 'No vegetables were harmed in the making of this plate.',
    match(items) {
      const kid = count(items, (i) => hasTag(i, 'kid'))
      const veg = count(items, (i) => i.category === 'veg')
      const kidRatio = items.length ? kid / items.length : 0
      const chocSoft = items.some((i) => i.softServe && i.softServe.flavor !== 'vanilla')
      const core = ['mac-and-cheese', 'pizza-squares', 'french-fries'].filter((id) => hasId(items, id)).length
      if (core >= 2 && veg === 0) return 90 + core * 2 + (chocSoft ? 4 : 0)
      if (kid >= 5 && veg === 0 && kidRatio >= 0.45) return 78 + (chocSoft ? 4 : 0)
      if (kid >= 4 && veg <= 1 && kidRatio >= 0.45) return 58
      return 0
    },
  },
  {
    id: 'the-optimizer',
    name: 'The Optimizer',
    emoji: '📈',
    tagline: 'Maximum flavor per square inch. You brought a spreadsheet to a buffet.',
    match(items, meta) {
      const plateItems = items.filter((i) => i.size > 0)
      if (plateItems.length < 4) return 0
      const goat = count(plateItems, (i) => hasTag(i, 'goat-tier'))
      const ratio = goat / plateItems.length
      if (ratio >= 0.7 && meta.efficiency >= 0.9) return 92
      if (ratio >= 0.6 && meta.efficiency >= 0.8) return 70
      return 0
    },
  },
  {
    id: 'chaos-plate',
    name: 'Chaos Plate',
    emoji: '🌪️',
    tagline: 'Orange chicken touching the mashed potatoes. Anarchy. Beautiful, delicious anarchy.',
    match(items) {
      const cats = new Set(items.filter((i) => i.category !== 'drink').map((i) => i.category)).size
      const chaos = count(items, (i) => hasTag(i, 'chaos'))
      const collision = hasId(items, 'orange-chicken') && hasId(items, 'mashed-potatoes')
      if (cats >= 6 && chaos >= 1) return 85 + chaos * 2 + (collision ? 5 : 0)
      if (collision && chaos >= 2) return 74
      if (chaos >= 3) return 60
      return 0
    },
  },
  {
    id: 'carb-cathedral',
    name: 'The Carb Cathedral',
    emoji: '🥖',
    tagline: 'Bread, on starch, with a side of noodles. An architectural marvel.',
    match(items) {
      const plateItems = items.filter((i) => i.size > 0)
      if (plateItems.length < 3) return 0
      const carbs = count(plateItems, (i) => i.category === 'starch' || i.category === 'bread')
      const ratio = carbs / plateItems.length
      if (ratio >= 0.75) return 68
      if (ratio >= 0.6) return 52
      return 0
    },
  },
  {
    id: 'protein-maximalist',
    name: 'The Protein Maximalist',
    emoji: '💪',
    tagline: 'Doug carved. You conquered. The sides never stood a chance because you never gave them one.',
    match(items) {
      const plateItems = items.filter((i) => i.size > 0)
      if (plateItems.length < 3) return 0
      const protein = count(plateItems, (i) => i.category === 'protein')
      const ratio = protein / plateItems.length
      if (ratio >= 0.75) return 66
      if (ratio >= 0.6) return 50
      return 0
    },
  },
  {
    id: 'dessert-first-adult',
    name: 'Dessert-First Adult',
    emoji: '🍦',
    tagline: 'Nobody can tell you what to do anymore, and the dessert bowl knows it.',
    match(items, meta) {
      const dessertUnits = items.filter((i) => i.category === 'dessert').reduce((a, i) => a + i.size, 0)
      if (dessertUnits >= meta.plateUnits && dessertUnits >= 4) return 72
      if (dessertUnits >= 6) return 55
      return 0
    },
  },
  {
    id: 'sensible-regular',
    name: 'The Sensible Regular',
    emoji: '🧘',
    tagline: 'Soup, salad, one entree, one dessert. The staff knows your booth. This is your home.',
    match(items) {
      const cats = new Set(items.filter((i) => i.category !== 'drink').map((i) => i.category)).size
      const plateItems = items.filter((i) => i.size > 0)
      if (cats >= 3 && cats <= 5 && plateItems.length >= 4 && plateItems.length <= 8) return 40
      return 0
    },
  },
  {
    id: 'hometown-classic',
    name: 'The Hometown Classic',
    emoji: '🏠',
    tagline: 'A little of this, a little of that, a lot of gravy. Exactly as it should be.',
    match() {
      return 10 // universal fallback
    },
  },
]

const JUDGMENTS = [
  { min: 95, text: 'Perfect run. Doug is telling the kitchen about you right now.' },
  { min: 85, text: 'Elite work. You clearly grew up within driving distance of a sneeze guard.' },
  { min: 72, text: 'Strong plate. Your grandma would still add a roll, but she’d be proud.' },
  { min: 60, text: 'Respectable. A journeyman’s plate. The soft serve will decide your legacy.' },
  { min: 45, text: 'Bold choices. Not all of them legal in every state, but bold.' },
  { min: 30, text: 'Your eyes wrote a check your stomach is nervously reading.' },
  { min: 0, text: 'The buffet believes in second chances. Go back for seconds. Please.' },
]

// items: all item objects (plates + dessert bowl + drink)
// meta: { capacity, used, plateUnits, plateCount, softServe, momMoments }
export function scorePlate(items, meta) {
  let best = ARCHETYPES[ARCHETYPES.length - 1]
  let bestScore = -1
  for (const a of ARCHETYPES) {
    const s = a.match(items, meta)
    if (s > bestScore) {
      best = a
      bestScore = s
    }
  }

  // Buffet IQ — 0–100 of pure vibes-based pseudoscience.
  let iq = 40
  const goat = count(items, (i) => hasTag(i, 'goat-tier'))
  iq += Math.min(20, goat * 4)
  iq += Math.round(meta.efficiency * 15)
  const cats = new Set(items.filter((i) => i.category !== 'drink').map((i) => i.category)).size
  iq += Math.min(12, cats * 2)
  if (hasId(items, 'honey-butter')) iq += 3 // free points. always free points.
  if (meta.softServe) {
    if (meta.softServe.quality === 'perfect') iq += 10
    else if (meta.softServe.quality === 'good') iq += 5
    else if (meta.softServe.quality === 'collapsed') iq -= 5
  }
  if (items.some((i) => i.category === 'drink')) iq += 2
  iq -= Math.min(6, (meta.momMoments || 0) * 2)
  iq = Math.max(5, Math.min(100, iq))

  const judgment = JUDGMENTS.find((j) => iq >= j.min).text

  return { archetype: best, iq, judgment }
}
