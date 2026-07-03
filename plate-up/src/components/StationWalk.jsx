import { motion, useReducedMotion } from 'framer-motion'
import { useGame } from '../store/gameStore.js'
import { STATIONS } from '../data/menu.js'
import Station from './Station.jsx'
import PlateDock from './Plate.jsx'

export default function StationWalk() {
  const stationIndex = useGame((s) => s.stationIndex)
  const nextStation = useGame((s) => s.nextStation)
  const prevStation = useGame((s) => s.prevStation)
  const reduceMotion = useReducedMotion()

  const station = STATIONS[stationIndex]
  const isLast = stationIndex === STATIONS.length - 1

  return (
    <motion.section
      className="screen station-walk"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
    >
      <header className="station-sign" key={station.id}>
        <h2>
          {station.emoji} {station.name.toUpperCase()}
        </h2>
        <p>{station.subtitle}</p>
        <div className="station-progress" aria-label={`Station ${stationIndex + 1} of ${STATIONS.length}`}>
          {STATIONS.map((s, i) => (
            <span key={s.id} className={`progress-dot ${i === stationIndex ? 'active' : i < stationIndex ? 'done' : ''}`} />
          ))}
        </div>
      </header>

      <div className="stations-viewport">
        <motion.div
          className="stations-track"
          animate={{ x: `-${stationIndex * 100}%` }}
          transition={
            reduceMotion
              ? { duration: 0 }
              : { type: 'spring', stiffness: 180, damping: 26 }
          }
        >
          {STATIONS.map((s) => (
            <div className="station-slot" key={s.id}>
              <Station station={s} />
            </div>
          ))}
        </motion.div>
      </div>

      <nav className="station-nav">
        <button className="btn btn-ghost" onClick={prevStation} disabled={stationIndex === 0}>
          ← Back
        </button>
        <button className={`btn ${isLast ? 'btn-gold' : 'btn-primary'}`} onClick={nextStation}>
          {isLast ? 'Find a Table 🪑' : 'Next Station →'}
        </button>
      </nav>

      <PlateDock />
    </motion.section>
  )
}
