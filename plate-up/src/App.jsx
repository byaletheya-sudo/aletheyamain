import { AnimatePresence, motion } from 'framer-motion'
import { useEffect } from 'react'
import { useGame } from './store/gameStore.js'
import Entrance from './components/Entrance.jsx'
import TrayPicker from './components/TrayPicker.jsx'
import StationWalk from './components/StationWalk.jsx'
import TableReveal from './components/TableReveal.jsx'

function MomOverlay() {
  const momMoment = useGame((s) => s.momMoment)
  const dismissMom = useGame((s) => s.dismissMom)
  const grabSecondPlate = useGame((s) => s.grabSecondPlate)
  return (
    <AnimatePresence>
      {momMoment && (
        <motion.div
          className="mom-overlay"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={dismissMom}
        >
          <motion.div
            className="mom-card"
            initial={{ scale: 0.8, y: 30 }}
            animate={{ scale: 1, y: 0 }}
            exit={{ scale: 0.9, opacity: 0 }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mom-eyes">👀</div>
            <p className="mom-text">{momMoment.text}</p>
            <div className="mom-actions">
              <button className="btn btn-ghost" onClick={dismissMom}>
                Fine, I&rsquo;ll put something back
              </button>
              {momMoment.canSecondPlate && (
                <button className="btn btn-primary" onClick={grabSecondPlate}>
                  Grab a second plate 🍽️
                </button>
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

function FlavorToast() {
  const toast = useGame((s) => s.toast)
  const clearToast = useGame((s) => s.clearToast)
  useEffect(() => {
    if (!toast) return
    const t = setTimeout(clearToast, 2800)
    return () => clearTimeout(t)
  }, [toast, clearToast])
  return (
    <AnimatePresence>
      {toast && (
        <motion.div
          key={toast.key}
          className="flavor-toast"
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -12 }}
          onClick={clearToast}
        >
          <strong>{toast.name}</strong>
          <span>{toast.flavorText}</span>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

function SoundToggle() {
  const soundOn = useGame((s) => s.soundOn)
  const toggleSound = useGame((s) => s.toggleSound)
  return (
    <button
      className="sound-toggle"
      onClick={toggleSound}
      aria-label={soundOn ? 'Mute sounds' : 'Enable sounds'}
      title={soundOn ? 'Sound on' : 'Sound off'}
    >
      {soundOn ? '🔔' : '🔕'}
    </button>
  )
}

export default function App() {
  const phase = useGame((s) => s.phase)
  return (
    <div className="app">
      <SoundToggle />
      <AnimatePresence mode="wait">
        {phase === 'entrance' && <Entrance key="entrance" />}
        {phase === 'tray' && <TrayPicker key="tray" />}
        {phase === 'stations' && <StationWalk key="stations" />}
        {(phase === 'booth' || phase === 'reveal') && <TableReveal key="table" />}
      </AnimatePresence>
      <MomOverlay />
      <FlavorToast />
    </div>
  )
}
