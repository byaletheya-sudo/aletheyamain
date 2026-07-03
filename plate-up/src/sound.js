// Tiny WebAudio synth — no assets, off by default.
// ding: item added · blip: item removed · womp: plate full ·
// hum: soft serve machine (start/stop) · tada: plate complete

let ctx = null
function ac() {
  if (!ctx) ctx = new (window.AudioContext || window.webkitAudioContext)()
  if (ctx.state === 'suspended') ctx.resume()
  return ctx
}

function tone(freq, dur, type = 'sine', gain = 0.08, when = 0) {
  if (!sound.enabled) return
  try {
    const c = ac()
    const o = c.createOscillator()
    const g = c.createGain()
    o.type = type
    o.frequency.value = freq
    g.gain.setValueAtTime(gain, c.currentTime + when)
    g.gain.exponentialRampToValueAtTime(0.0001, c.currentTime + when + dur)
    o.connect(g).connect(c.destination)
    o.start(c.currentTime + when)
    o.stop(c.currentTime + when + dur + 0.05)
  } catch {
    /* audio is a garnish, never the meal */
  }
}

let humNodes = null

export const sound = {
  enabled: false,
  ding() {
    tone(880, 0.12, 'triangle', 0.09)
    tone(1320, 0.18, 'triangle', 0.05, 0.06)
  },
  blip() {
    tone(440, 0.08, 'square', 0.04)
  },
  womp() {
    tone(220, 0.25, 'sawtooth', 0.05)
    tone(180, 0.35, 'sawtooth', 0.05, 0.12)
  },
  tada() {
    tone(660, 0.15, 'triangle', 0.08)
    tone(880, 0.15, 'triangle', 0.08, 0.12)
    tone(1100, 0.3, 'triangle', 0.08, 0.24)
  },
  humStart() {
    if (!sound.enabled || humNodes) return
    try {
      const c = ac()
      const o = c.createOscillator()
      const o2 = c.createOscillator()
      const g = c.createGain()
      o.type = 'sawtooth'
      o.frequency.value = 55
      o2.type = 'sine'
      o2.frequency.value = 110
      g.gain.value = 0.03
      o.connect(g)
      o2.connect(g)
      g.connect(c.destination)
      o.start()
      o2.start()
      humNodes = { o, o2, g }
    } catch {
      /* no hum, no harm */
    }
  },
  humStop() {
    if (!humNodes) return
    try {
      const { o, o2, g } = humNodes
      g.gain.exponentialRampToValueAtTime(0.0001, ac().currentTime + 0.15)
      o.stop(ac().currentTime + 0.2)
      o2.stop(ac().currentTime + 0.2)
    } catch {
      /* already stopped */
    }
    humNodes = null
  },
}
