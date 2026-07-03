import { useRef, useState } from 'react'
import { toPng } from 'html-to-image'
import { PlateGraphic } from './Plate.jsx'
import { FoodArt } from '../art/foodArt.jsx'

// Offscreen, fixed-size cards (1080×1920 story / 1080×1080 square)
// exported with html-to-image. This is the growth mechanic.
function CardContent({ format, result }) {
  const { plates, dessertBowl, drink, archetype, iq, judgment } = result
  const story = format === 'story'
  return (
    <div className={`share-card ${story ? 'share-card-story' : 'share-card-square'}`}>
      <div className="share-header">
        <div className="share-marquee">PLATE UP</div>
        <div className="share-sub">ALL YOU CAN PLATE · BUFFET & GRILL</div>
      </div>

      <div className="share-placemat">
        <div className="share-plates">
          {plates.map((p, i) => (
            <PlateGraphic key={i} items={p} className={plates.length > 1 ? 'share-plate share-plate-two' : 'share-plate'} animate={false} />
          ))}
        </div>
        {(dessertBowl.length > 0 || drink) && (
          <div className="share-extras">
            {dessertBowl.length > 0 && (
              <span className="share-bowl">
                {dessertBowl.map((d, i) => (
                  <FoodArt key={i} id={d.id} title={d.name} className="share-extra-art" />
                ))}
              </span>
            )}
            {drink && <FoodArt id={drink.id} title={drink.name} className="share-extra-art" />}
          </div>
        )}
      </div>

      <div className="share-verdict">
        <div className="share-archetype">
          {archetype.emoji} {archetype.name}
        </div>
        <div className="share-tagline">{archetype.tagline}</div>
        <div className="share-iq">
          BUFFET IQ: <strong>{iq}</strong>/100
        </div>
        {story && <div className="share-judgment">{judgment}</div>}
      </div>

      <div className="share-footer">Build your plate → plate-up.game</div>
    </div>
  )
}

export default function ShareButtons({ result }) {
  const storyRef = useRef(null)
  const squareRef = useRef(null)
  const [busy, setBusy] = useState(null)
  const [error, setError] = useState(null)

  const exportCard = async (format) => {
    const node = format === 'story' ? storyRef.current : squareRef.current
    if (!node || busy) return
    setBusy(format)
    setError(null)
    try {
      const dataUrl = await toPng(node, { pixelRatio: 1, cacheBust: true })
      const blob = await (await fetch(dataUrl)).blob()
      const file = new File([blob], `plate-up-${format}.png`, { type: 'image/png' })
      if (navigator.canShare && navigator.canShare({ files: [file] })) {
        try {
          await navigator.share({ files: [file], title: 'My buffet plate' })
          setBusy(null)
          return
        } catch (e) {
          if (e.name === 'AbortError') {
            setBusy(null)
            return
          }
          // fall through to download
        }
      }
      const a = document.createElement('a')
      a.href = dataUrl
      a.download = `plate-up-${format}.png`
      a.click()
    } catch (e) {
      setError('Could not render the card. The kitchen apologizes. Try again.')
    }
    setBusy(null)
  }

  return (
    <div className="share-buttons">
      <button className="btn btn-gold" onClick={() => exportCard('story')} disabled={!!busy}>
        {busy === 'story' ? 'Plating…' : '📲 Share Story (9:16)'}
      </button>
      <button className="btn btn-gold" onClick={() => exportCard('square')} disabled={!!busy}>
        {busy === 'square' ? 'Plating…' : '🖼️ Share Square (1:1)'}
      </button>
      {error && <p className="share-error">{error}</p>}

      {/* offscreen render targets */}
      <div className="share-offscreen" aria-hidden="true">
        <div ref={storyRef}>
          <CardContent format="story" result={result} />
        </div>
        <div ref={squareRef}>
          <CardContent format="square" result={result} />
        </div>
      </div>
    </div>
  )
}
