import { useEffect, useMemo } from 'react'
import { motion } from 'framer-motion'
import { useGame } from '../store/gameStore.js'
import { scorePlate } from '../data/archetypes.js'
import { PlateGraphic, BowlGraphic } from './Plate.jsx'
import ShareButtons from './ShareCard.jsx'
import { sound } from '../sound.js'

const BOOTHS = [
  {
    id: 'window',
    name: 'The Window Booth',
    emoji: '🪟',
    blurb: 'Parking lot view. Prime real estate. Your family claimed it with a purse.',
  },
  {
    id: 'round',
    name: 'The Big Round One',
    emoji: '🎂',
    blurb: 'For birthdays and family reunions. Seats nine. You are one person. Iconic.',
  },
  {
    id: 'strategic',
    name: 'Near the Soft Serve',
    emoji: '🍦',
    blurb: 'Strategic positioning. Four steps from the machine. You’ve done this before.',
  },
]

function BoothPicker() {
  const chooseBooth = useGame((s) => s.chooseBooth)
  return (
    <motion.section
      className="screen booth-picker"
      initial={{ opacity: 0, x: 60 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0 }}
    >
      <header className="station-sign">
        <h2>🪑 FIND YOUR TABLE</h2>
        <p>The hostess already knows where you&rsquo;re headed.</p>
      </header>
      <div className="booth-options">
        {BOOTHS.map((b, i) => (
          <motion.button
            key={b.id}
            className="booth-card"
            onClick={() => chooseBooth(b)}
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.1 }}
            whileTap={{ scale: 0.96 }}
          >
            <span className="booth-emoji">{b.emoji}</span>
            <strong>{b.name}</strong>
            <small>{b.blurb}</small>
          </motion.button>
        ))}
      </div>
    </motion.section>
  )
}

function Reveal() {
  const plates = useGame((s) => s.plates)
  const dessertBowl = useGame((s) => s.dessertBowl)
  const drink = useGame((s) => s.drink)
  const booth = useGame((s) => s.booth)
  const reset = useGame((s) => s.reset)
  const allItems = useGame((s) => s.allItems)
  const scoringMeta = useGame((s) => s.scoringMeta)

  const { archetype, iq, judgment } = useMemo(
    () => scorePlate(allItems(), scoringMeta()),
    // plate contents are frozen once you sit down
    [] // eslint-disable-line react-hooks/exhaustive-deps
  )

  useEffect(() => {
    sound.tada()
  }, [])

  const shareResult = { plates, dessertBowl, drink, archetype, iq, judgment }

  return (
    <motion.section className="screen reveal" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
      <header className="station-sign">
        <h2>
          {booth ? booth.emoji : '🪑'} YOUR TABLE
        </h2>
        <p>{booth ? booth.name : 'Somewhere in the dining room'} · the tray hits the table with a satisfying clunk.</p>
      </header>

      <div className="table-scene">
        <div className="placemat">
          <div className="placemat-title">~ welcome, friend ~</div>
          <div className="reveal-plates">
            {plates.map((p, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, scale: 0.7, y: 20 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                transition={{ delay: 0.2 + i * 0.15, type: 'spring', stiffness: 200, damping: 18 }}
              >
                <PlateGraphic items={p} className="reveal-plate" animate={false} />
              </motion.div>
            ))}
          </div>
          <div className="reveal-extras">
            {dessertBowl.length > 0 && <BowlGraphic items={dessertBowl} className="reveal-bowl" />}
            {drink && (
              <span className="reveal-drink" title={drink.name}>
                {drink.emoji}
              </span>
            )}
          </div>
        </div>
      </div>

      <motion.div
        className="verdict-card"
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.6 }}
      >
        <div className="verdict-label">THE VERDICT</div>
        <h3 className="verdict-archetype">
          {archetype.emoji} {archetype.name}
        </h3>
        <p className="verdict-tagline">{archetype.tagline}</p>
        <div className="verdict-iq">
          <span className="iq-number">{iq}</span>
          <span className="iq-label">BUFFET IQ</span>
        </div>
        <p className="verdict-judgment">&ldquo;{judgment}&rdquo;</p>
      </motion.div>

      <ShareButtons result={shareResult} />

      <button className="btn btn-primary btn-big" onClick={reset}>
        Go Back for Seconds 🔁
      </button>
    </motion.section>
  )
}

export default function TableReveal() {
  const phase = useGame((s) => s.phase)
  return phase === 'booth' ? <BoothPicker /> : <Reveal />
}
