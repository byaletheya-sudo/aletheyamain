import { useRef, useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion'
import { useGame } from '../store/gameStore.js'
import { SOFT_SERVE_FLAVORS, makeSoftServeItem } from '../data/menu.js'
import { sound } from '../sound.js'

// Hold to pour. Release in the sweet spot for the perfect swirl.
// Fill rate ≈ 0.45/s → perfect zone lands around a 1.7–2.3s hold.
const FILL_RATE = 0.45
const ZONES = { weak: 0.35, good: 0.75, perfect: 1.0, collapse: 1.08 }
const SEGMENTS = 9

function quality(h) {
  if (h >= ZONES.collapse) return 'collapsed'
  if (h >= ZONES.good) return 'perfect'
  if (h >= ZONES.weak) return 'good'
  return 'weak'
}

export default function SoftServeMachine() {
  const addItem = useGame((s) => s.addItem)
  const softServe = useGame((s) => s.softServe)
  const reduceMotion = useReducedMotion()

  const [flavor, setFlavor] = useState('swirl')
  const [height, setHeight] = useState(0)
  const [pouring, setPouring] = useState(false)
  const [result, setResult] = useState(null) // quality string after release
  const raf = useRef(null)
  const heightRef = useRef(0)
  const pouringRef = useRef(false)

  const finish = useCallback(
    (h) => {
      if (!pouringRef.current) return
      pouringRef.current = false
      setPouring(false)
      sound.humStop()
      const q = quality(h)
      setResult(q)
      const item = makeSoftServeItem(flavor, q)
      addItem(item)
      if (q === 'perfect') sound.tada()
    },
    [flavor, addItem]
  )

  const startPour = useCallback(
    (e) => {
      e.preventDefault()
      if (pouringRef.current) return
      pouringRef.current = true
      setPouring(true)
      setResult(null)
      heightRef.current = 0
      setHeight(0)
      sound.humStart()
      let last = performance.now()
      const tick = (now) => {
        if (!pouringRef.current) return
        const dt = (now - last) / 1000
        last = now
        heightRef.current += dt * FILL_RATE
        setHeight(heightRef.current)
        if (heightRef.current >= ZONES.collapse) {
          finish(heightRef.current) // held too long — gravity wins
          return
        }
        raf.current = requestAnimationFrame(tick)
      }
      raf.current = requestAnimationFrame(tick)
    },
    [finish]
  )

  const stopPour = useCallback(() => {
    if (raf.current) cancelAnimationFrame(raf.current)
    finish(heightRef.current)
  }, [finish])

  useEffect(
    () => () => {
      if (raf.current) cancelAnimationFrame(raf.current)
      sound.humStop()
    },
    []
  )

  const flavorDef = SOFT_SERVE_FLAVORS.find((f) => f.id === flavor)
  const segCount = Math.min(SEGMENTS, Math.ceil((height / ZONES.perfect) * (SEGMENTS - 1)) + (height > 0 ? 1 : 0))
  const collapsed = result === 'collapsed'
  const inPerfectZone = pouring && height >= ZONES.good && height < ZONES.collapse

  const segColor = (i) => {
    if (flavor === 'swirl') return i % 2 === 0 ? '#FFF6E3' : '#7B4A2D'
    return flavorDef.color
  }

  const resultText = {
    perfect: '⭐ PERFECT SWIRL. Frame it.',
    good: 'A respectable swirl. Doug nods.',
    weak: 'A shy little dollop. No shame. Some shame.',
    collapsed: 'Structural failure. A classic.',
  }

  return (
    <div className="soft-serve">
      <div className="soft-serve-header">
        <h3>SOFT SERVE MACHINE</h3>
        <p>Hold the lever. Release at the peak. Do not get greedy.</p>
      </div>

      <div className="flavor-picker" role="radiogroup" aria-label="Soft serve flavor">
        {SOFT_SERVE_FLAVORS.map((f) => (
          <button
            key={f.id}
            className={`flavor-btn ${flavor === f.id ? 'selected' : ''}`}
            onClick={() => setFlavor(f.id)}
            disabled={pouring}
          >
            {f.id === 'swirl' ? '🍥' : f.id === 'chocolate' ? '🟤' : '⚪'} {f.name}
          </button>
        ))}
      </div>

      <div className="machine-stage">
        <div className="machine-body">
          <div className="machine-nozzle" />
          {pouring && <div className="machine-stream" style={{ background: flavor === 'chocolate' ? '#7B4A2D' : '#FFF6E3' }} />}
        </div>

        <div className="swirl-zone">
          <div className={`swirl-stack ${collapsed ? 'collapsed' : ''}`}>
            <AnimatePresence>
              {Array.from({ length: segCount }).map((_, i) => (
                <motion.div
                  key={i}
                  className="swirl-seg"
                  initial={reduceMotion ? false : { scale: 0.4, opacity: 0 }}
                  animate={
                    collapsed && i > segCount / 2
                      ? { rotate: 38 + i * 6, x: 26 + i * 4, y: 10, opacity: 0.9 }
                      : { scale: 1, opacity: 1, rotate: 0, x: 0 }
                  }
                  style={{
                    width: `${88 - i * 7}%`,
                    background: segColor(i),
                    zIndex: i,
                  }}
                />
              ))}
            </AnimatePresence>
            {result === 'perfect' && !collapsed && <div className="swirl-curl">🍦</div>}
          </div>
          <div className="swirl-cup" />
        </div>

        <div className="pour-meter" aria-hidden="true">
          <div className="pour-zone-perfect" style={{ bottom: `${ZONES.good * 82}%`, height: `${(ZONES.perfect - ZONES.good) * 82}%` }} />
          <div
            className={`pour-level ${inPerfectZone ? 'hot' : ''}`}
            style={{ height: `${Math.min(100, (height / ZONES.collapse) * 90)}%` }}
          />
        </div>
      </div>

      <button
        className={`btn pour-lever ${pouring ? 'pouring' : ''}`}
        onPointerDown={startPour}
        onPointerUp={stopPour}
        onPointerLeave={() => pouringRef.current && stopPour()}
        onPointerCancel={() => pouringRef.current && stopPour()}
        onContextMenu={(e) => e.preventDefault()}
      >
        {pouring ? 'POURING… RELEASE AT THE PEAK' : softServe ? 'GO AGAIN (replaces yours)' : 'HOLD TO POUR 🍦'}
      </button>

      <AnimatePresence>
        {result && (
          <motion.p
            className={`pour-result ${result}`}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
          >
            {resultText[result]}
          </motion.p>
        )}
      </AnimatePresence>
    </div>
  )
}
