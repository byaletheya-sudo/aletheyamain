import { motion } from 'framer-motion'
import { useGame } from '../store/gameStore.js'

export default function Entrance() {
  const setPhase = useGame((s) => s.setPhase)
  return (
    <motion.section
      className="screen entrance"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
    >
      <div className="entrance-inner">
        <motion.div
          className="marquee-sign"
          initial={{ y: -40, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ type: 'spring', stiffness: 120, damping: 14 }}
        >
          <div className="marquee-bulbs" aria-hidden="true">
            {Array.from({ length: 14 }).map((_, i) => (
              <span key={i} className="bulb" style={{ animationDelay: `${(i % 4) * 0.3}s` }} />
            ))}
          </div>
          <h1 className="marquee-title">PLATE UP</h1>
          <p className="marquee-sub">ALL YOU CAN PLATE &middot; BUFFET &amp; GRILL</p>
        </motion.div>

        <motion.div
          className="price-board"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25 }}
        >
          <div className="price-board-title">— TODAY&rsquo;S PRICES —</div>
          <div className="price-row">
            <span>ADULTS</span>
            <span className="price-dots" />
            <span>$8.99</span>
          </div>
          <div className="price-row">
            <span>KIDS 3–10</span>
            <span className="price-dots" />
            <span>60&cent; &times; AGE</span>
          </div>
          <div className="price-row">
            <span>SENIORS</span>
            <span className="price-dots" />
            <span>ASK ABOUT CLUB 55</span>
          </div>
          <div className="price-row price-row-small">
            <span>DRINKS INCLUDED &middot; NO SHARING PLATES (WE SEE YOU)</span>
          </div>
        </motion.div>

        <motion.button
          className="btn btn-primary btn-big"
          onClick={() => setPhase('tray')}
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.45 }}
          whileTap={{ scale: 0.95 }}
        >
          Grab a Tray 🍽️
        </motion.button>

        <p className="entrance-footnote">
          Inspired by every hometown buffet your family drove 25 minutes to on a Sunday.
        </p>
      </div>
    </motion.section>
  )
}
