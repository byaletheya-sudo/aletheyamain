import { motion, AnimatePresence } from 'framer-motion'
import { useGame } from '../store/gameStore.js'
import { TRAY_COLORS, BOWL_CAPACITY } from '../data/menu.js'

// Deterministic golden-angle spiral so items settle into plate
// zones the same way every render (dock, table, share card).
export function layoutPositions(n) {
  const GOLDEN = 2.399963
  return Array.from({ length: n }).map((_, i) => {
    const r = n === 1 ? 0 : 34 * Math.sqrt((i + 0.6) / n)
    const a = i * GOLDEN
    return { left: 50 + r * Math.cos(a), top: 50 + r * Math.sin(a) }
  })
}

export function PlateGraphic({ items, className = '', onRemove, animate = true }) {
  const positions = layoutPositions(items.length)
  return (
    <div className={`plate-graphic ${className}`}>
      <div className="plate-rim" />
      {items.map((item, i) => {
        const pos = positions[i]
        const inner = (
          <span
            className="plate-item-emoji"
            style={{ fontSize: `${0.9 + item.size * 0.28}em` }}
            role="img"
            aria-label={item.name}
          >
            {item.emoji}
          </span>
        )
        const style = { left: `${pos.left}%`, top: `${pos.top}%` }
        // positioning lives on the outer span so framer's transform
        // animation on the inner element can't clobber the centering
        return (
          <span key={`${item.id}-${i}`} className="plate-item" style={style}>
            {animate ? (
              <motion.button
                className="plate-item-btn"
                initial={{ scale: 0, y: -18 }}
                animate={{ scale: 1, y: 0 }}
                transition={{ type: 'spring', stiffness: 400, damping: 18 }}
                onClick={onRemove ? () => onRemove(i) : undefined}
                title={onRemove ? `Remove ${item.name}` : item.name}
                disabled={!onRemove}
              >
                {inner}
              </motion.button>
            ) : (
              <span className="plate-item-btn" title={item.name}>
                {inner}
              </span>
            )}
          </span>
        )
      })}
      {items.length === 0 && <span className="plate-empty-hint">empty</span>}
    </div>
  )
}

export function BowlGraphic({ items, className = '', onRemove }) {
  return (
    <div className={`bowl-graphic ${className}`}>
      {items.map((item, i) => (
        <motion.button
          key={`${item.id}-${i}`}
          className="bowl-item"
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          onClick={onRemove ? () => onRemove(i) : undefined}
          title={onRemove ? `Remove ${item.name}` : item.name}
          disabled={!onRemove}
        >
          {item.emoji}
        </motion.button>
      ))}
      {items.length === 0 && <span className="bowl-empty-hint">🥣</span>}
    </div>
  )
}

// The tray rail — docked at the bottom for the whole station walk.
// Your plate travels with you, exactly like the real thing.
export default function PlateDock() {
  const plates = useGame((s) => s.plates)
  const activePlate = useGame((s) => s.activePlate)
  const setActivePlate = useGame((s) => s.setActivePlate)
  const dessertBowl = useGame((s) => s.dessertBowl)
  const drink = useGame((s) => s.drink)
  const removeItem = useGame((s) => s.removeItem)
  const trayColor = useGame((s) => s.trayColor)
  const capacity = useGame((s) => s.capacity)
  const plateUsed = useGame((s) => s.plateUsed)
  const bowlUsed = useGame((s) => s.bowlUsed)
  const dessertUnlocked = useGame((s) => s.dessertUnlocked)

  const tray = TRAY_COLORS.find((t) => t.id === trayColor)
  const cap = capacity()
  const used = plateUsed(activePlate)

  return (
    <div className="plate-dock" style={{ '--tray-color': tray.hex }}>
      <div className="tray-surface">
        <div className="tray-ridges-bg" aria-hidden="true" />

        {plates.length > 1 && (
          <div className="plate-tabs">
            {plates.map((_, i) => (
              <button
                key={i}
                className={`plate-tab ${i === activePlate ? 'active' : ''}`}
                onClick={() => setActivePlate(i)}
              >
                Plate {i + 1}
              </button>
            ))}
          </div>
        )}

        <div className="dock-row">
          <div className="dock-plate-wrap">
            <PlateGraphic
              items={plates[activePlate]}
              className="dock-plate"
              onRemove={(i) => removeItem(activePlate, i)}
            />
            <div className="capacity-meter" aria-label={`Plate space: ${used} of ${cap} units`}>
              <div
                className={`capacity-fill ${used >= cap ? 'maxed' : ''}`}
                style={{ width: `${Math.min(100, (used / cap) * 100)}%` }}
              />
              <span className="capacity-text">
                {used}/{cap}
              </span>
            </div>
          </div>

          <AnimatePresence>
            {dessertUnlocked() && (
              <motion.div
                className="dock-bowl-wrap"
                initial={{ opacity: 0, scale: 0.6 }}
                animate={{ opacity: 1, scale: 1 }}
              >
                <BowlGraphic items={dessertBowl} onRemove={(i) => removeItem('bowl', i)} />
                <span className="dock-slot-label">
                  bowl {bowlUsed()}/{BOWL_CAPACITY}
                </span>
              </motion.div>
            )}
          </AnimatePresence>

          <div className="dock-drink-wrap">
            {drink ? (
              <button
                className="dock-drink"
                onClick={() => removeItem('drink')}
                title={`Remove ${drink.name}`}
              >
                {drink.emoji}
              </button>
            ) : (
              <span className="dock-drink empty">🫗</span>
            )}
            <span className="dock-slot-label">drink</span>
          </div>
        </div>
      </div>
    </div>
  )
}
