import { motion } from 'framer-motion'
import { useGame } from '../store/gameStore.js'
import { TRAY_COLORS, PLATE_SIZES } from '../data/menu.js'

export default function TrayPicker() {
  const trayColor = useGame((s) => s.trayColor)
  const plateSize = useGame((s) => s.plateSize)
  const chooseTray = useGame((s) => s.chooseTray)
  const choosePlateSize = useGame((s) => s.choosePlateSize)
  const setPhase = useGame((s) => s.setPhase)

  return (
    <motion.section
      className="screen tray-picker"
      initial={{ opacity: 0, x: 60 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -60 }}
    >
      <header className="station-sign">
        <h2>GRAB A TRAY</h2>
        <p>Still warm from the dishwasher. That&rsquo;s the good kind.</p>
      </header>

      <div className="picker-group">
        <h3 className="picker-label">Tray Color</h3>
        <div className="tray-options">
          {TRAY_COLORS.map((t) => (
            <button
              key={t.id}
              className={`tray-option ${trayColor === t.id ? 'selected' : ''}`}
              onClick={() => chooseTray(t.id)}
            >
              <span className="tray-swatch" style={{ background: t.hex }}>
                <span className="tray-ridges" />
              </span>
              <strong>{t.name}</strong>
              <small>{t.blurb}</small>
            </button>
          ))}
        </div>
      </div>

      <div className="picker-group">
        <h3 className="picker-label">Plate Size</h3>
        <div className="plate-options">
          {Object.values(PLATE_SIZES).map((p) => (
            <button
              key={p.id}
              className={`plate-option ${plateSize === p.id ? 'selected' : ''}`}
              onClick={() => choosePlateSize(p.id)}
            >
              <span
                className="plate-preview"
                style={{ width: 36 + p.capacity * 3, height: 36 + p.capacity * 3 }}
              />
              <strong>{p.name}</strong>
              <small>{p.blurb}</small>
              <span className="capacity-chip">{p.capacity} units</span>
            </button>
          ))}
        </div>
      </div>

      <button className="btn btn-primary btn-big" onClick={() => setPhase('stations')}>
        Walk the Line →
      </button>
    </motion.section>
  )
}
