// ============================================================
// PLATE UP — Phase 4 food art.
// One layered-SVG illustration per menu item, drawn in a
// consistent 90s menu-board sticker style: flat fills, chunky
// warm-brown outline, one specular highlight, soft ground shadow.
// All drawings live on a 64×64 viewBox centered near (32, 34).
// ============================================================

import { ITEM_BY_ID } from '../data/menu.js'

const INK = '#43281a'
const S = { stroke: INK, strokeWidth: 3, strokeLinejoin: 'round', strokeLinecap: 'round' }
const thin = { ...S, strokeWidth: 2 }

const Shadow = ({ rx = 19 }) => <ellipse cx="32" cy="56" rx={rx} ry="4" fill={INK} opacity="0.12" />
const Hi = ({ cx, cy, rx = 4.5, ry = 2.4, o = 0.55, rot = -22 }) => (
  <ellipse cx={cx} cy={cy} rx={rx} ry={ry} fill="#fff" opacity={o} transform={`rotate(${rot} ${cx} ${cy})`} />
)

// a diner bowl seen slightly from above — contents drawn on the surface
function SoupBowl({ surface, children }) {
  return (
    <>
      <Shadow />
      <path {...S} fill="#EFE3CB" d="M11 30 L53 30 C53 44 45 53 32 53 C19 53 11 44 11 30 Z" />
      <ellipse {...S} cx="32" cy="30" rx="21" ry="7" fill={surface} />
      {children}
      <Hi cx="20" cy="44" rx="4" ry="2" o={0.35} rot={24} />
    </>
  )
}

// a fountain-style drink cup, straw optional
function Cup({ fill, band, straw = true, children }) {
  return (
    <>
      <Shadow rx={13} />
      <path {...S} fill={fill} d="M18 16 L46 16 L42 54 L22 54 Z" />
      {band && <path {...S} fill={band} d="M19.4 28 L44.6 28 L43.4 39 L20.6 39 Z" />}
      {straw && <path {...S} fill="#F2E8D5" d="M33 16 L40 4 L44 5 L36.5 17.5 Z" />}
      <ellipse {...S} cx="32" cy="16" rx="14" ry="4" fill="#fff" />
      {children}
      <Hi cx="24" cy="34" rx="2.6" ry="6" rot={4} o={0.4} />
    </>
  )
}

// small souffle / condiment cup with a domed filling
function SouffleCup({ dome, drip }) {
  return (
    <>
      <Shadow rx={14} />
      <path {...S} fill="#fff" d="M16 34 L48 34 L44 52 L20 52 Z" />
      <path fill="none" {...thin} d="M22 36 L21 50 M28 36 L27.5 50 M36 36 L36.5 50 M42 36 L43 50" opacity="0.4" />
      <path {...S} fill={dome} d="M16 34 C16 22 24 17 32 17 C40 17 48 22 48 34 Z" />
      {drip && <path {...S} fill={dome} d="M22 34 C22 39 17 39 17 34 Z" />}
      <Hi cx="26" cy="24" />
    </>
  )
}

// tumbler glass for the drink station
function Glass({ fill, children }) {
  return (
    <>
      <Shadow rx={13} />
      <path {...S} fill={fill} d="M20 12 L44 12 L42 54 L22 54 Z" />
      <ellipse {...S} cx="32" cy="12" rx="12" ry="3.6" fill="#fff" opacity="0.9" />
      {children}
      <Hi cx="26" cy="32" rx="2.4" ry="8" rot={3} o={0.45} />
    </>
  )
}

const ice = (x, y, r = 0) => (
  <rect x={x} y={y} width="8" height="8" rx="2" fill="#EAF4F5" opacity="0.85" {...thin} transform={r ? `rotate(${r} ${x + 4} ${y + 4})` : undefined} />
)

// soft serve in a cup — flavor decides the tier colors
function softServe(colors) {
  return (
    <>
      <Shadow rx={15} />
      <path {...S} fill="#fff" d="M15 36 L49 36 L44 54 L20 54 Z" />
      <path {...S} fill={colors[0]} d="M17 36 C14 30 20 27 25 29 C22 24 28 20 33 23 C31 17 40 16 41 22 C47 22 49 29 44 31 C50 32 49 37 46 36 Z" />
      <path {...S} fill={colors[1 % colors.length]} d="M22 28 C20 22 27 19 31 22 C30 15 39 14 40 20 C45 20 46 27 42 28 Z" />
      <path {...S} fill={colors[0]} d="M28 20 C27 14 34 11 37 15 C39 12 43 14 42 18 C42 21 38 22 36 20 C34 23 29 23 28 20 Z" />
      <Hi cx="27" cy="31" />
    </>
  )
}

// ── the registry ─────────────────────────────────────────────
const ART = {
  // ═══ SALAD BAR ═══
  'iceberg-lettuce': () => (
    <>
      <Shadow />
      <path {...S} fill="#8CBF66" d="M10 40 C8 26 20 15 33 16 C46 17 55 28 51 41 C48 49 14 49 10 40 Z" />
      <path {...S} fill="#EFF7DF" d="M16 40 C15 30 23 23 33 24 C42 25 49 32 46 40 C44 45 18 45 16 40 Z" />
      <path fill="none" {...thin} stroke="#A8CC7E" d="M21 40 C21 33 27 28 33 29 C39 30 43 34 42 40 M27 41 C27 36 30 33 33 34 C36 34 38 37 37 41" />
      <Hi cx="21" cy="22" rx="4" ry="2.2" />
    </>
  ),
  'shredded-cheese': () => (
    <>
      <Shadow />
      <path {...S} fill="#F5B93F" d="M14 44 C12 34 22 28 32 28 C42 28 52 34 50 44 C48 50 16 50 14 44 Z" />
      <path fill="none" {...thin} stroke="#C98A1B" d="M20 36 L28 44 M26 32 L36 42 M34 31 L42 40 M40 34 L46 42 M18 42 L24 46" />
      <path fill="none" {...thin} stroke="#FFDF8E" d="M23 34 L31 42 M31 30 L40 39 M38 32 L45 39" />
      <Hi cx="24" cy="33" />
    </>
  ),
  croutons: () => (
    <>
      <Shadow />
      <rect {...S} x="14" y="26" width="15" height="15" rx="3" fill="#DEA95B" transform="rotate(-12 21.5 33.5)" />
      <rect {...S} x="34" y="20" width="15" height="15" rx="3" fill="#E8BC72" transform="rotate(9 41.5 27.5)" />
      <rect {...S} x="28" y="37" width="14" height="14" rx="3" fill="#D89C48" transform="rotate(-4 35 44)" />
      <path fill={INK} opacity="0.35" d="M20 31 h3 v2 h-3 z M40 26 h3 v2 h-3 z M34 43 h3 v2 h-3 z" />
      <Hi cx="40" cy="23" rx="3" />
    </>
  ),
  ranch: () => <SouffleCup dome="#FBF6E9" drip />,
  'bacon-bits': () => (
    <>
      <Shadow />
      <rect {...S} x="14" y="30" width="10" height="7" rx="2" fill="#A5402E" transform="rotate(-20 19 33.5)" />
      <rect {...S} x="27" y="22" width="11" height="7" rx="2" fill="#B24A33" transform="rotate(12 32.5 25.5)" />
      <rect {...S} x="41" y="30" width="10" height="7" rx="2" fill="#9C3A2A" transform="rotate(-8 46 33.5)" />
      <rect {...S} x="21" y="41" width="10" height="7" rx="2" fill="#B24A33" transform="rotate(6 26 44.5)" />
      <rect {...S} x="36" y="42" width="9" height="6" rx="2" fill="#A5402E" transform="rotate(-14 40.5 45)" />
      <path fill="none" {...thin} stroke="#E8A38B" d="M17 33 l5 -2 M30 25 l6 1 M43 33 l6 -1 M24 44 l5 1" />
    </>
  ),
  'macaroni-salad': () => (
    <>
      <Shadow />
      <path {...S} fill="#F7EBCB" d="M13 42 C11 32 21 26 32 26 C43 26 53 32 51 42 C49 49 15 49 13 42 Z" />
      <path fill="none" {...S} stroke="#F0C75E" d="M21 34 a4.5 4.5 0 1 1 6 4 M33 30 a4.5 4.5 0 1 1 6 4 M40 38 a4.5 4.5 0 1 0 -7 3" strokeWidth="4" />
      <circle cx="19" cy="41" r="1.6" fill="#5C9E4A" />
      <circle cx="45" cy="40" r="1.6" fill="#D64533" />
      <Hi cx="24" cy="30" />
    </>
  ),
  'potato-salad': () => (
    <>
      <Shadow />
      <path {...S} fill="#F3E4B5" d="M13 42 C11 31 22 25 32 25 C42 25 53 31 51 42 C49 49 15 49 13 42 Z" />
      <rect {...S} x="20" y="31" width="9" height="8" rx="2.5" fill="#EFD98F" transform="rotate(-9 24.5 35)" />
      <rect {...S} x="35" y="33" width="9" height="8" rx="2.5" fill="#F5E6A8" transform="rotate(7 39.5 37)" />
      <ellipse {...thin} cx="31" cy="42" rx="4.6" ry="3.4" fill="#FFF9E8" />
      <circle cx="31" cy="42" r="1.8" fill="#F0C75E" {...thin} />
      <circle cx="18" cy="38" r="1.4" fill="#5C9E4A" />
      <circle cx="46" cy="37" r="1.4" fill="#5C9E4A" />
      <path fill="none" {...thin} stroke="#C4462F" d="M26 28 l2 1.4 M40 29 l-2 1.4" opacity="0.8" />
    </>
  ),
  'ambrosia-salad': () => (
    <>
      <Shadow />
      <path {...S} fill="#FCEFE4" d="M12 42 C12 32 19 27 25 29 C25 23 34 21 37 26 C43 22 51 27 49 33 C54 36 52 43 47 44 C44 49 18 49 12 42 Z" />
      <ellipse {...S} cx="23" cy="37" rx="4" ry="3" fill="#F7A44C" />
      <path fill="none" {...thin} stroke="#D97E23" d="M20 37 h6" />
      <circle {...thin} cx="38" cy="34" r="3.2" fill="#fff" />
      <circle {...thin} cx="44" cy="40" r="2.7" fill="#FBD9E4" />
      <circle {...thin} cx="30" cy="42" r="2.7" fill="#fff" />
      <path fill="none" {...thin} stroke="#E8C3A0" d="M33 28 l3 -2 M17 39 l3 -1" />
    </>
  ),
  'jello-cubes': () => (
    <>
      <Shadow />
      <rect {...S} x="13" y="27" width="17" height="17" rx="4" fill="#E23B4E" opacity="0.92" transform="rotate(-7 21.5 35.5)" />
      <rect {...S} x="33" y="22" width="18" height="18" rx="4" fill="#EA4A5D" opacity="0.92" transform="rotate(6 42 31)" />
      <rect {...S} x="27" y="38" width="15" height="14" rx="4" fill="#D63145" opacity="0.92" transform="rotate(-3 34.5 45)" />
      <Hi cx="20" cy="31" rx="4" ry="2.6" />
      <Hi cx="41" cy="26" rx="4.6" ry="2.8" />
      <Hi cx="33" cy="42" rx="3.2" ry="2" />
    </>
  ),
  'cottage-cheese': () => (
    <>
      <Shadow />
      <path {...S} fill="#FBF6E9" d="M13 42 C11 33 20 27 32 27 C44 27 53 33 51 42 C49 49 15 49 13 42 Z" />
      <circle {...thin} cx="22" cy="35" r="3.4" fill="#fff" />
      <circle {...thin} cx="31" cy="32" r="3.8" fill="#F5EEDC" />
      <circle {...thin} cx="40" cy="35" r="3.3" fill="#fff" />
      <circle {...thin} cx="27" cy="41" r="3.2" fill="#F5EEDC" />
      <circle {...thin} cx="37" cy="42" r="3.5" fill="#fff" />
      <Hi cx="22" cy="31" rx="3" />
    </>
  ),
  'three-bean-salad': () => (
    <>
      <Shadow />
      <path {...S} fill="#B23A48" d="M15 34 C13 27 20 23 25 27 C29 30 28 37 23 39 C19 41 16 38 15 34 Z" />
      <path {...S} fill="#E8D46B" d="M27 26 C29 20 37 20 39 26 C40 31 35 35 31 33 C28 32 26 29 27 26 Z" />
      <path {...S} fill="#6FA84F" d="M38 34 C44 30 51 35 49 41 C47 46 40 46 38 42 C36 39 36 36 38 34 Z" />
      <path {...S} fill="#8CBF66" d="M20 43 C26 40 32 44 31 49 L22 49 C19 47 18 45 20 43 Z" />
      <Hi cx="21" cy="29" rx="2.6" />
      <Hi cx="33" cy="24" rx="2.6" />
      <Hi cx="43" cy="37" rx="2.6" />
    </>
  ),
  'pickled-beets': () => (
    <>
      <Shadow />
      <ellipse {...S} cx="25" cy="33" rx="12.5" ry="11" fill="#8E2F5C" />
      <ellipse fill="none" {...thin} cx="25" cy="33" rx="7.5" ry="6.4" stroke="#C05688" />
      <ellipse fill="none" {...thin} cx="25" cy="33" rx="3.4" ry="2.8" stroke="#C05688" />
      <ellipse {...S} cx="42" cy="42" rx="11" ry="9.6" fill="#A03A6B" />
      <ellipse fill="none" {...thin} cx="42" cy="42" rx="6" ry="5" stroke="#CD6DA0" />
      <Hi cx="20" cy="27" />
    </>
  ),
  'sunflower-seeds': () => (
    <>
      <Shadow />
      {[
        [21, 28, -25], [35, 23, 12], [46, 33, 38], [27, 42, -8], [40, 44, -32],
      ].map(([x, y, r], i) => (
        <g key={i} transform={`rotate(${r} ${x} ${y})`}>
          <path {...S} fill="#5C534A" d={`M${x} ${y - 9} C${x + 7.5} ${y - 3} ${x + 6.5} ${y + 7} ${x} ${y + 10} C${x - 6.5} ${y + 7} ${x - 7.5} ${y - 3} ${x} ${y - 9} Z`} />
          <path fill="none" {...thin} stroke="#EDE6D4" d={`M${x - 2.6} ${y - 4} L${x - 2.6} ${y + 5} M${x + 2.6} ${y - 4} L${x + 2.6} ${y + 5}`} />
        </g>
      ))}
    </>
  ),

  // ═══ SOUPS & BREAD ═══
  'chicken-noodle-soup': () => (
    <SoupBowl surface="#F0C75E">
      <path fill="none" {...thin} stroke="#FFF3C8" d="M20 29 C24 26 28 32 32 29 C36 26 40 32 44 29" />
      <circle cx="24" cy="32" r="2" fill="#E8863C" {...thin} />
      <circle cx="39" cy="31" r="2" fill="#E8863C" {...thin} />
      <path fill="none" {...thin} stroke={INK} opacity="0.5" d="M28 12 C26 15 30 16 28 19 M36 11 C34 14 38 15 36 18" />
    </SoupBowl>
  ),
  'clam-chowder': () => (
    <SoupBowl surface="#FBF3E0">
      <circle cx="25" cy="30" r="1.6" fill="#DEA95B" {...thin} />
      <circle cx="33" cy="28" r="1.6" fill="#DEA95B" {...thin} />
      <circle cx="40" cy="31" r="1.6" fill="#DEA95B" {...thin} />
      <path fill="none" {...thin} stroke={INK} opacity="0.5" d="M31 12 C29 15 33 16 31 19" />
    </SoupBowl>
  ),
  chili: () => (
    <SoupBowl surface="#B33A26">
      <path {...thin} fill="#8E2A1B" d="M23 29 a2.6 2 0 1 0 5 0 a2.6 2 0 1 0 -5 0 M35 31 a2.6 2 0 1 0 5 0 a2.6 2 0 1 0 -5 0" />
      <path fill="none" {...thin} stroke="#F5B93F" d="M27 26 l4 2 M38 27 l4 1" />
      <path fill="none" {...thin} stroke={INK} opacity="0.5" d="M33 11 C31 14 35 15 33 18" />
    </SoupBowl>
  ),
  'dinner-roll': () => (
    <>
      <Shadow />
      <path {...S} fill="#E8B45C" d="M12 40 C12 26 22 19 32 19 C42 19 52 26 52 40 C52 47 44 50 32 50 C20 50 12 47 12 40 Z" />
      <path fill="none" {...S} stroke="#C68B33" d="M24 21 C28 28 28 40 25 48 M40 21 C36 28 36 40 39 48" />
      <Hi cx="24" cy="27" rx="5" ry="3" />
    </>
  ),
  cornbread: () => (
    <>
      <Shadow />
      <path {...S} fill="#E8B94E" d="M14 30 L50 30 L50 48 C50 51 14 51 14 48 Z" />
      <path {...S} fill="#F5D983" d="M14 30 L24 20 L60 20 L50 30 Z" transform="translate(-5 2)" />
      <path {...S} fill="#F5D983" d="M14 30 L22 22 L54 22 L50 30 Z" />
      <path fill={INK} opacity="0.25" d="M20 36 h2.4 v2.4 h-2.4 z M32 40 h2.4 v2.4 h-2.4 z M42 35 h2.4 v2.4 h-2.4 z" />
      <Hi cx="28" cy="26" rx="5" ry="2" />
    </>
  ),
  biscuit: () => (
    <>
      <Shadow />
      <ellipse {...S} cx="32" cy="41" rx="19" ry="9" fill="#E3B268" />
      <path {...S} fill="#F0D19A" d="M13 40 C13 28 20 22 32 22 C44 22 51 28 51 40 C51 44 44 47 32 47 C20 47 13 44 13 40 Z" />
      <path fill="none" {...thin} stroke="#C68B33" d="M18 38 C24 41 40 41 46 38" />
      <Hi cx="25" cy="28" rx="5" ry="2.6" />
    </>
  ),
  breadstick: () => (
    <>
      <Shadow />
      <path {...S} fill="#E8B45C" d="M12 46 C10 42 14 38 18 40 L48 16 C52 13 57 18 54 22 L24 46 C21 49 14 50 12 46 Z" />
      <path fill="none" {...thin} stroke="#C68B33" d="M22 40 l4 4 M30 34 l4 4 M38 28 l4 4 M46 22 l4 4" />
      <circle cx="27" cy="41" r="1.2" fill="#FFF3C8" />
      <circle cx="37" cy="32" r="1.2" fill="#FFF3C8" />
      <circle cx="46" cy="25" r="1.2" fill="#FFF3C8" />
    </>
  ),
  'honey-butter': () => (
    <>
      <Shadow />
      <path {...S} fill="#FBF6E9" d="M15 33 L49 33 L46 52 L18 52 Z" />
      <path {...S} fill="#F2B33A" d="M15 33 C15 23 22 18 32 18 C42 18 49 23 49 33 Z" />
      <path {...S} fill="#F2B33A" d="M27 33 C27 40 20 40 20 33 Z" />
      <path fill="none" {...thin} stroke="#FFDF8E" d="M24 25 C28 22 36 22 40 25" />
      <Hi cx="26" cy="23" />
    </>
  ),

  // ═══ HOT ENTREES ═══
  'fried-chicken': () => (
    <>
      <Shadow />
      <path {...S} fill="#F2E8D5" d="M40 38 L50 48 C54 46 56 49 53 52 C50 55 47 53 48 50 L38 40 Z" />
      <circle {...S} cx="52" cy="45" r="3.4" fill="#F2E8D5" />
      <circle {...S} cx="57" cy="50" r="3.4" fill="#F2E8D5" />
      <path {...S} fill="#C9812E" d="M10 26 C8 14 22 6 33 12 C44 18 46 32 38 40 C30 47 16 44 12 36 C10 33 10 29 10 26 Z" />
      <path fill={INK} opacity="0.3" d="M18 20 a2 2 0 1 0 4 0 a2 2 0 1 0 -4 0 M28 16 a2 2 0 1 0 4 0 a2 2 0 1 0 -4 0 M25 30 a2 2 0 1 0 4 0 a2 2 0 1 0 -4 0 M34 24 a2 2 0 1 0 4 0 a2 2 0 1 0 -4 0" />
      <Hi cx="20" cy="14" rx="5" ry="3" />
    </>
  ),
  'baked-chicken': () => (
    <>
      <Shadow />
      <path {...S} fill="#D89C48" d="M11 32 C11 20 23 13 34 16 C45 19 51 28 47 37 C43 46 19 47 13 39 C11 37 11 35 11 32 Z" />
      <path {...S} fill="#C9812E" d="M36 37 C44 34 50 40 46 45 C43 49 36 47 35 42 Z" />
      <path {...S} fill="#F2E8D5" d="M45 44 L51 49 C54 48 56 51 53 53 C51 55 48 53 49 51 L43 47 Z" />
      <path fill="none" {...S} stroke="#B0761F" d="M19 24 C25 28 33 28 39 24" />
      <path fill="none" {...thin} stroke="#B0761F" d="M18 33 C23 36 29 36 34 34" />
      <Hi cx="21" cy="19" rx="5" ry="2.6" />
    </>
  ),
  meatloaf: () => (
    <>
      <Shadow />
      <path {...S} fill="#8C5432" d="M14 30 L50 30 L50 48 C50 51 14 51 14 48 Z" />
      <path fill="none" {...thin} stroke="#6E3D20" d="M19 37 h6 M30 40 h7 M41 36 h5 M22 44 h5 M35 45 h6" />
      <path {...S} fill="#C4462F" d="M14 30 C14 24 20 20 32 20 C44 20 50 24 50 30 C50 33 44 34 32 34 C20 34 14 33 14 30 Z" />
      <path fill="none" {...thin} stroke="#E06A50" d="M22 25 C28 23 38 23 44 26" />
      <Hi cx="23" cy="24" />
    </>
  ),
  'salisbury-steak': () => (
    <>
      <Shadow />
      <ellipse {...S} cx="32" cy="38" rx="20" ry="12" fill="#7A4526" />
      <path {...S} fill="#9C6236" d="M12 36 C12 27 21 23 32 23 C43 23 52 27 52 36 C52 41 43 44 32 44 C21 44 12 41 12 36 Z" />
      <path fill="none" {...S} stroke="#C9955C" d="M18 31 C24 34 40 34 46 30" strokeWidth="4" opacity="0.7" />
      <ellipse {...thin} cx="41" cy="27" rx="4.6" ry="3.2" fill="#E4D3B8" />
      <path fill="none" {...thin} d="M39 27 h5" stroke="#B79A6E" />
      <Hi cx="21" cy="27" />
    </>
  ),
  'pot-roast': () => (
    <>
      <Shadow />
      <path {...S} fill="#7A4526" d="M13 34 C11 22 24 15 35 18 C47 21 53 31 48 40 C43 49 18 48 14 40 C13 38 13 36 13 34 Z" />
      <path fill="none" {...S} stroke="#5C2F14" d="M20 26 C26 30 26 38 22 42 M32 21 C31 29 33 37 38 43 M42 25 C39 31 41 38 46 39" />
      <path {...S} fill="#E8863C" d="M44 44 C48 41 54 44 52 49 C51 52 46 53 44 50 C43 48 43 46 44 44 Z" />
      <Hi cx="23" cy="21" rx="5" ry="2.6" />
    </>
  ),
  'bbq-ribs': () => (
    <>
      <Shadow />
      <path {...S} fill="#F2E8D5" d="M15 22 L20 22 L20 50 L15 50 Z M29 22 L34 22 L34 50 L29 50 Z M43 22 L48 22 L48 50 L43 50 Z" />
      <path {...S} fill="#93331E" d="M10 26 C10 20 54 20 54 26 L54 44 C54 50 10 50 10 44 Z" />
      <path fill="none" {...S} stroke="#5C1D0E" d="M21 23 L21 47 M32 23 L32 47 M43 23 L43 47" />
      <path fill="none" {...S} stroke="#C4462F" d="M14 30 C22 26 42 26 50 30" strokeWidth="4" opacity="0.85" />
      <Hi cx="18" cy="35" rx="3" ry="5" rot={8} o={0.35} />
    </>
  ),
  'fried-fish': () => (
    <>
      <Shadow />
      <path {...S} fill="#E8D46B" d="M46 20 C52 20 56 26 52 30 L50 32 C54 33 54 39 50 40 C46 41 44 38 45 35 Z" />
      <path {...S} fill="#DEA95B" d="M10 32 C10 24 18 18 27 18 L42 24 C48 27 48 37 42 40 L27 46 C18 46 10 40 10 32 Z" />
      <path fill={INK} opacity="0.3" d="M17 26 a1.8 1.8 0 1 0 3.6 0 a1.8 1.8 0 1 0 -3.6 0 M27 24 a1.8 1.8 0 1 0 3.6 0 a1.8 1.8 0 1 0 -3.6 0 M23 36 a1.8 1.8 0 1 0 3.6 0 a1.8 1.8 0 1 0 -3.6 0 M34 32 a1.8 1.8 0 1 0 3.6 0 a1.8 1.8 0 1 0 -3.6 0" />
      <Hi cx="18" cy="23" rx="4" />
    </>
  ),
  'popcorn-shrimp': () => (
    <>
      <Shadow />
      <path {...S} fill="#E8A34C" d="M12 34 C10 26 18 20 25 23 C31 26 31 35 25 38 C20 41 13 40 12 34 Z" />
      <path {...S} fill="#DE9540" d="M31 24 C31 16 41 14 45 20 C48 25 44 32 38 31 C34 30 31 28 31 24 Z" />
      <path {...S} fill="#E8A34C" d="M32 40 C32 33 42 32 46 37 C49 42 45 48 39 47 C35 46 32 44 32 40 Z" />
      <path {...S} fill="#E06A50" d="M44 18 C48 14 54 17 52 22 C51 25 47 25 45 23 Z M45 36 C50 33 55 38 52 42 C50 45 46 43 45 41 Z" />
      <path fill={INK} opacity="0.3" d="M17 29 a1.6 1.6 0 1 0 3.2 0 a1.6 1.6 0 1 0 -3.2 0 M37 22 a1.6 1.6 0 1 0 3.2 0 a1.6 1.6 0 1 0 -3.2 0 M38 41 a1.6 1.6 0 1 0 3.2 0 a1.6 1.6 0 1 0 -3.2 0" />
    </>
  ),
  'spaghetti-meatballs': () => (
    <>
      <Shadow />
      <path {...S} fill="#F0C75E" d="M12 40 C10 30 20 24 32 24 C44 24 54 30 52 40 C50 47 14 47 12 40 Z" />
      <path fill="none" {...thin} stroke="#D9A33C" d="M16 36 C22 31 28 40 34 34 C40 28 46 38 50 33 M18 41 C26 36 34 44 42 38" />
      <circle {...S} cx="26" cy="27" r="6" fill="#8C4A2B" />
      <circle {...S} cx="40" cy="29" r="5.4" fill="#8C4A2B" />
      <path fill="none" {...S} stroke="#C4462F" d="M20 26 C26 20 38 20 46 26" strokeWidth="5" opacity="0.85" />
      <Hi cx="24" cy="24" rx="3" />
    </>
  ),
  'mac-and-cheese': () => (
    <>
      <Shadow />
      <path {...S} fill="#F5A623" d="M12 41 C10 31 20 25 32 25 C44 25 54 31 52 41 C50 48 14 48 12 41 Z" />
      <path fill="none" {...S} stroke="#FFD24D" strokeWidth="4.5" d="M19 34 a5 5 0 1 1 7 4 M31 30 a5 5 0 1 1 7 4 M39 39 a5 5 0 1 0 -8 3" />
      <path fill="none" {...thin} stroke="#D9820C" d="M16 43 C24 46 40 46 48 43" />
      <Hi cx="22" cy="29" />
    </>
  ),
  'orange-chicken': () => (
    <>
      <Shadow />
      <path {...S} fill="#D9581F" d="M13 33 C11 25 19 19 26 22 C32 25 32 34 26 37 C21 40 14 39 13 33 Z" />
      <path {...S} fill="#E56A2B" d="M31 25 C31 17 42 15 46 21 C49 27 45 34 38 32 C34 31 31 29 31 25 Z" />
      <path {...S} fill="#D9581F" d="M30 42 C30 35 41 33 45 39 C48 44 44 50 37 49 C33 48 30 46 30 42 Z" />
      <circle cx="22" cy="27" r="1.1" fill="#FFF3C8" />
      <circle cx="40" cy="23" r="1.1" fill="#FFF3C8" />
      <circle cx="38" cy="43" r="1.1" fill="#FFF3C8" />
      <path fill="none" {...thin} stroke="#5C9E4A" d="M17 44 l6 -2 M42 30 l5 2" />
      <Hi cx="19" cy="25" rx="3" />
    </>
  ),
  'chow-mein': () => (
    <>
      <Shadow />
      <path {...S} fill="#E3B268" d="M11 40 C9 30 20 23 32 23 C44 23 55 30 53 40 C51 48 13 48 11 40 Z" />
      <path fill="none" {...thin} stroke="#B0761F" d="M15 34 C23 28 31 38 39 31 C45 26 50 34 51 37 M17 41 C25 35 35 43 45 37 M22 28 C28 33 38 26 44 30" />
      <path {...thin} fill="#5C9E4A" d="M24 38 l6 -1.4 l-0.6 2.8 l-5.4 -1.4 Z" />
      <path {...thin} fill="#E8863C" d="M38 41 l5.5 1 l-1 2.6 l-4.5 -3.6 Z" />
    </>
  ),
  'pizza-squares': () => (
    <>
      <Shadow />
      <path {...S} fill="#E8B45C" d="M13 17 L51 17 L51 51 L13 51 Z" />
      <path {...S} fill="#D64533" d="M17 21 L47 21 L47 47 L17 47 Z" />
      <path {...S} fill="#F5D983" d="M19 23 L45 23 L45 45 L19 45 Z" />
      <circle {...S} cx="27" cy="30" r="4.4" fill="#B23A2A" />
      <circle {...S} cx="38" cy="38" r="4.4" fill="#B23A2A" />
      <Hi cx="38" cy="27" rx="4" />
    </>
  ),
  'taco-fixings': () => (
    <>
      <Shadow />
      <path {...S} fill="#8CBF66" d="M14 32 C18 22 26 18 32 18 C38 18 46 22 50 32 L44 30 C40 26 24 26 20 30 Z" />
      <path {...S} fill="#7A4526" d="M17 33 C21 26 43 26 47 33 L44 36 C38 32 26 32 20 36 Z" />
      <path {...S} fill="#E8B45C" d="M10 38 C14 24 50 24 54 38 C56 44 50 50 44 48 C36 44 28 44 20 48 C14 50 8 44 10 38 Z" />
      <path fill="none" {...thin} stroke="#C68B33" d="M16 38 C24 33 40 33 48 38" />
      <circle cx="24" cy="29" r="1.6" fill="#D64533" {...thin} />
      <circle cx="39" cy="29" r="1.6" fill="#F5B93F" {...thin} />
      <Hi cx="20" cy="41" rx="3" ry="4" rot={22} o={0.35} />
    </>
  ),
  enchiladas: () => (
    <>
      <Shadow />
      <path {...S} fill="#A33222" d="M10 34 C10 30 54 30 54 34 L54 46 C54 50 10 50 10 46 Z" />
      <path {...S} fill="#C4462F" d="M12 28 C12 22 30 22 30 28 L30 40 C30 44 12 44 12 40 Z" />
      <path {...S} fill="#C4462F" d="M34 28 C34 22 52 22 52 28 L52 40 C52 44 34 44 34 40 Z" />
      <path fill="none" {...S} stroke="#F5D983" strokeWidth="4" d="M15 27 C20 24 26 24 29 27 M37 27 C42 24 48 24 51 27" opacity="0.9" />
      <path fill="none" {...thin} stroke="#5C9E4A" d="M20 34 l4 1 M42 35 l4 -1" />
    </>
  ),

  // ═══ CARVING STATION ═══
  'carved-ham': () => (
    <>
      <Shadow />
      <path {...S} fill="#F2C7CE" d="M16 20 C28 14 46 18 50 30 C53 40 44 48 32 48 C20 48 10 40 12 30 C13 25 14 22 16 20 Z" />
      <path {...S} fill="#E58FA0" d="M18 23 C28 18 43 21 46 30 C49 38 42 44 32 44 C22 44 14 38 16 30 C16 27 17 25 18 23 Z" />
      <path fill="none" {...thin} stroke="#C9657C" d="M24 28 C30 25 38 26 42 31 M22 35 C28 32 38 33 42 37" />
      <Hi cx="25" cy="24" rx="5" ry="2.6" />
    </>
  ),
  'roast-turkey': () => (
    <>
      <Shadow />
      <path {...S} fill="#E8C48E" d="M14 26 C22 20 42 20 50 26 L48 46 C40 50 24 50 16 46 Z" />
      <path fill="none" {...S} stroke="#C99C58" d="M18 32 C26 28 38 28 46 32 M17 39 C25 35 39 35 47 39" />
      <path {...S} fill="#8A5A2B" d="M22 22 C28 18 36 18 42 22 C44 26 40 30 32 30 C24 30 20 26 22 22 Z" opacity="0.95" />
      <path {...S} fill="#8A5A2B" d="M28 28 C28 34 24 34 24 29 Z" opacity="0.95" />
      <Hi cx="27" cy="23" rx="4" />
    </>
  ),
  'roast-beef': () => (
    <>
      <Shadow />
      <path {...S} fill="#7A4526" d="M12 30 C20 24 44 24 52 30 L50 46 C42 51 22 51 14 46 Z" />
      <path {...S} fill="#B0555A" d="M16 30 C24 26 40 26 48 30 C48 34 40 37 32 37 C24 37 16 34 16 30 Z" />
      <path fill="none" {...thin} stroke="#D98289" d="M22 30 C28 28 36 28 42 30" />
      <path fill="none" {...thin} stroke="#5C2F14" d="M18 42 C26 45 38 45 46 42" />
      <Hi cx="24" cy="28" rx="4" ry="2" />
    </>
  ),

  // ═══ SIDES ═══
  'mashed-potatoes': () => (
    <>
      <Shadow />
      <path {...S} fill="#FBF3E0" d="M12 40 C10 32 16 26 22 28 C22 21 32 18 36 24 C42 20 50 25 48 31 C54 33 54 41 48 43 C46 49 16 49 12 40 Z" />
      <path {...S} fill="#8A5A2B" d="M22 34 C26 30 38 30 42 34 C44 37 40 40 32 40 C24 40 20 37 22 34 Z" />
      <path {...S} fill="#F2B33A" d="M29 31 L36 31 L35 36 L30 36 Z" />
      <Hi cx="20" cy="32" />
    </>
  ),
  stuffing: () => (
    <>
      <Shadow />
      <path {...S} fill="#B0763A" d="M12 40 C10 32 17 27 23 29 C24 23 33 21 37 26 C43 22 51 27 49 33 C53 36 51 43 46 43 C42 49 16 48 12 40 Z" />
      <path fill={INK} opacity="0.25" d="M20 34 h4 v3 h-4 z M31 31 h4 v3 h-4 z M40 36 h4 v3 h-4 z M26 41 h4 v3 h-4 z" />
      <path fill="none" {...thin} stroke="#5C9E4A" d="M24 30 l3 -1.6 M37 40 l3 -1.6" />
      <path fill="none" {...thin} stroke="#E8863C" d="M35 33 l3.4 1 M18 40 l3.4 1" />
      <Hi cx="21" cy="30" rx="3.4" />
    </>
  ),
  'green-bean-casserole': () => (
    <>
      <Shadow />
      <path {...S} fill="#F2E8D5" d="M10 34 L54 34 L51 50 C50 53 14 53 13 50 Z" />
      <path {...S} fill="#5F8F4A" d="M11 34 C11 28 53 28 53 34 C53 37 11 37 11 34 Z" />
      <path fill="none" {...S} stroke="#7DB05A" d="M16 31 C22 28 28 33 34 30 M32 33 C38 29 44 33 49 31" />
      <path {...thin} fill="#D9A33C" d="M20 28 l4 -2.4 l1.6 2.6 l-4.4 1.6 Z M33 26 l4.4 -1.6 l1 2.8 l-4.6 1 Z M43 28 l4 -2 l1.4 2.6 l-4.2 1.4 Z" />
      <Hi cx="20" cy="44" rx="4" ry="2" o={0.35} />
    </>
  ),
  corn: () => (
    <>
      <Shadow />
      <path {...S} fill="#F5CE47" d="M10 32 C10 24 18 20 32 20 C46 20 54 24 54 32 C54 40 46 44 32 44 C18 44 10 40 10 32 Z" />
      <path fill="none" {...thin} stroke="#D9A81E" d="M17 25 C17 39 17 39 17 39 M25 22 L25 42 M33 21 L33 43 M41 22 L41 42 M48 25 L48 39 M12 28 C24 31 40 31 52 28 M12 36 C24 39 40 39 52 36" />
      <path {...S} fill="#F2B33A" d="M27 14 L37 14 L36 21 L28 21 Z" />
      <Hi cx="20" cy="26" rx="4" ry="2" />
    </>
  ),
  'broccoli-cheese': () => (
    <>
      <Shadow />
      <path {...S} fill="#5F8F4A" d="M14 28 C12 20 20 15 26 19 C28 13 38 13 40 19 C46 15 54 20 52 28 C56 32 52 38 47 37 L19 37 C13 38 10 32 14 28 Z" />
      <circle cx="21" cy="24" r="1.6" fill="#3F6B31" />
      <circle cx="31" cy="20" r="1.6" fill="#3F6B31" />
      <circle cx="42" cy="24" r="1.6" fill="#3F6B31" />
      <circle cx="35" cy="28" r="1.6" fill="#3F6B31" />
      <path {...S} fill="#8CBF66" d="M27 37 L37 37 L36 48 C36 51 28 51 28 48 Z" />
      <path {...S} fill="#F5A623" d="M18 33 C24 29 40 29 46 33 C46 38 40 40 37 38 C36 42 28 42 27 38 C24 40 18 38 18 33 Z" />
      <Hi cx="24" cy="33" rx="3" />
    </>
  ),
  'rice-pilaf': () => (
    <>
      <Shadow />
      <path {...S} fill="#F3E7C6" d="M12 41 C10 32 20 26 32 26 C44 26 54 32 52 41 C50 48 14 48 12 41 Z" />
      <path fill="none" {...thin} stroke="#B89A55" d="M19 34 l4.5 -1.8 M28 30 l4.5 1.6 M38 33 l4.5 -1.6 M22 40 l4.5 1.6 M32 42 l4.5 -1.8 M42 39 l4.5 1.6 M31 36 l4 -1.4" />
      <path fill="none" {...thin} stroke="#E8863C" d="M25 36 l3.4 1 M40 43 l3 1 M17 39 l3 -1" />
      <path fill="none" {...thin} stroke="#5C9E4A" d="M36 28 l3 -1.2" />
      <Hi cx="21" cy="30" rx="3.6" />
    </>
  ),
  'baked-beans': () => (
    <>
      <Shadow />
      <path {...S} fill="#7A3A1E" d="M12 40 C10 31 20 26 32 26 C44 26 54 31 52 40 C50 47 14 47 12 40 Z" />
      <path {...thin} fill="#A65B33" d="M19 33 a3.4 2.6 0 1 0 6.8 0 a3.4 2.6 0 1 0 -6.8 0 M30 30 a3.4 2.6 0 1 0 6.8 0 a3.4 2.6 0 1 0 -6.8 0 M39 35 a3.4 2.6 0 1 0 6.8 0 a3.4 2.6 0 1 0 -6.8 0 M25 39 a3.4 2.6 0 1 0 6.8 0 a3.4 2.6 0 1 0 -6.8 0 M36 41 a3.4 2.6 0 1 0 6.8 0 a3.4 2.6 0 1 0 -6.8 0" />
      <Hi cx="23" cy="31" rx="3" />
    </>
  ),
  'sweet-potato-casserole': () => (
    <>
      <Shadow />
      <path {...S} fill="#D9702B" d="M13 32 L51 32 L50 48 C49 51 15 51 14 48 Z" />
      <circle {...thin} cx="20" cy="31" r="4" fill="#FBF6E9" />
      <circle {...thin} cx="28" cy="29" r="4" fill="#fff" />
      <circle {...thin} cx="36" cy="31" r="4" fill="#FBF6E9" />
      <circle {...thin} cx="44" cy="29" r="4" fill="#fff" />
      <circle {...thin} cx="24" cy="35" r="3.6" fill="#F5E8D0" />
      <circle {...thin} cx="32" cy="34" r="3.6" fill="#fff" />
      <circle {...thin} cx="40" cy="35" r="3.6" fill="#F5E8D0" />
      <Hi cx="20" cy="43" rx="4" ry="2" o={0.3} />
    </>
  ),
  'french-fries': () => (
    <>
      <Shadow />
      <path {...S} fill="#F5CE47" d="M24 12 L30 12 L29 34 L24 34 Z" transform="rotate(-10 27 23)" />
      <path {...S} fill="#E8B45C" d="M31 10 L37 10 L36 34 L31 34 Z" />
      <path {...S} fill="#F5CE47" d="M38 12 L44 12 L44 34 L39 34 Z" transform="rotate(10 41 23)" />
      <path {...S} fill="#E8B45C" d="M18 16 L24 16 L24 34 L19 34 Z" transform="rotate(-18 21 25)" />
      <path {...S} fill="#F5CE47" d="M42 16 L48 16 L48 34 L43 34 Z" transform="rotate(16 45 25)" />
      <path {...S} fill="#C4462F" d="M15 30 L49 30 L45 52 L19 52 Z" />
      <path fill="none" {...thin} stroke="#8E2A1B" d="M22 36 L42 36" opacity="0.5" />
      <Hi cx="24" cy="40" rx="3" ry="6" rot={6} o={0.3} />
    </>
  ),
  'hush-puppies': () => (
    <>
      <Shadow />
      <circle {...S} cx="22" cy="30" r="9.6" fill="#D89C48" />
      <circle {...S} cx="41" cy="27" r="8.6" fill="#E3AC5C" />
      <circle {...S} cx="33" cy="43" r="9" fill="#D89C48" />
      <path fill={INK} opacity="0.28" d="M18 27 a1.6 1.6 0 1 0 3.2 0 a1.6 1.6 0 1 0 -3.2 0 M38 24 a1.6 1.6 0 1 0 3.2 0 a1.6 1.6 0 1 0 -3.2 0 M30 41 a1.6 1.6 0 1 0 3.2 0 a1.6 1.6 0 1 0 -3.2 0 M25 33 a1.6 1.6 0 1 0 3.2 0 a1.6 1.6 0 1 0 -3.2 0" />
      <Hi cx="19" cy="25" rx="3" />
      <Hi cx="38" cy="22" rx="2.6" />
    </>
  ),
  'fried-okra': () => (
    <>
      <Shadow />
      <circle {...S} cx="21" cy="29" r="8" fill="#D89C48" />
      <circle {...S} cx="40" cy="26" r="7.4" fill="#E3AC5C" />
      <circle {...S} cx="31" cy="43" r="7.6" fill="#D89C48" />
      <circle {...S} cx="47" cy="41" r="6.6" fill="#E3AC5C" />
      <path {...thin} fill="#8CBF66" d="M18 27 l3 -2 l3 2 l-1 3.4 l-4 0 Z" />
      <path {...thin} fill="#8CBF66" d="M37 24 l3 -2 l3 2 l-1 3.4 l-4 0 Z" />
      <circle cx="21" cy="29" r="1.2" fill="#FBF6E9" />
      <circle cx="40" cy="26" r="1.2" fill="#FBF6E9" />
    </>
  ),

  // ═══ DESSERT BAR ═══
  sprinkles: () => (
    <>
      <Shadow />
      {[
        [18, 26, -30, '#E23B4E'], [28, 20, 15, '#2E7F7A'], [38, 25, -10, '#F2B33A'],
        [46, 32, 40, '#8E4FA8'], [22, 37, 25, '#F5CE47'], [33, 33, -35, '#E06A50'],
        [43, 42, 10, '#5C9E4A'], [27, 46, -18, '#E23B4E'], [37, 47, 30, '#2E7F7A'], [16, 45, 8, '#8E4FA8'],
      ].map(([x, y, r, c], i) => (
        <rect key={i} x={x} y={y} width="9" height="4" rx="2" fill={c} {...thin} transform={`rotate(${r} ${x + 4.5} ${y + 2})`} />
      ))}
    </>
  ),
  'chocolate-syrup': () => (
    <>
      <Shadow rx={12} />
      <path {...S} fill="#6E3D20" d="M22 22 L42 22 L44 50 C44 53 20 53 20 50 Z" />
      <path {...S} fill="#8A5A2B" d="M26 14 L38 14 L40 22 L24 22 Z" />
      <path {...S} fill="#F2B33A" d="M28 8 L36 8 L36 14 L28 14 Z" />
      <path {...S} fill="#F2E8D5" d="M24 32 C30 28 34 36 40 32 L40 38 C34 42 30 34 24 38 Z" opacity="0.9" />
      <path {...S} fill="#8A5A2B" d="M32 2 C34 5 33 8 32 8 C31 8 30 5 32 2 Z" />
      <Hi cx="26" cy="27" rx="2.2" ry="5" rot={4} o={0.35} />
    </>
  ),
  brownies: () => (
    <>
      <Shadow />
      <path {...S} fill="#4A2A16" d="M16 26 L48 20 L50 44 L18 50 Z" />
      <path {...S} fill="#6E3D20" d="M16 26 L48 20 L48.6 27 L16.6 33 Z" />
      <path fill="none" {...thin} stroke="#9C6236" d="M24 37 l6 -1 M35 33 l6 -1 M27 44 l6 -1" opacity="0.8" />
      <Hi cx="24" cy="26" rx="4" ry="1.8" rot={-8} o={0.3} />
    </>
  ),
  'chocolate-chip-cookies': () => (
    <>
      <Shadow />
      <circle {...S} cx="32" cy="33" r="17" fill="#E3AC5C" />
      <path fill="none" {...thin} stroke="#C68B33" d="M20 28 C26 24 40 24 45 30" opacity="0.7" />
      <circle cx="25" cy="28" r="2.4" fill="#4A2A16" {...thin} />
      <circle cx="37" cy="26" r="2.4" fill="#4A2A16" {...thin} />
      <circle cx="41" cy="37" r="2.4" fill="#4A2A16" {...thin} />
      <circle cx="29" cy="39" r="2.4" fill="#4A2A16" {...thin} />
      <circle cx="33" cy="32" r="2" fill="#4A2A16" {...thin} />
      <Hi cx="24" cy="23" rx="4" />
    </>
  ),
  'peach-cobbler': () => (
    <>
      <Shadow />
      <path {...S} fill="#F2E8D5" d="M11 36 L53 36 L50 50 C49 53 15 53 14 50 Z" />
      <path {...S} fill="#E8863C" d="M12 36 C12 31 52 31 52 36 C52 38 12 38 12 36 Z" />
      <path {...S} fill="#F0A868" d="M17 33 a4 3 0 1 0 8 0 a4 3 0 1 0 -8 0 M31 32 a4 3 0 1 0 8 0 a4 3 0 1 0 -8 0" transform="translate(0 1)" />
      <path {...S} fill="#E8CF9E" d="M18 30 C18 24 26 22 29 27 C31 22 40 23 40 28 C45 26 50 30 47 34 L20 34 C17 33 17 31 18 30 Z" />
      <path fill={INK} opacity="0.2" d="M23 28 h2.6 v2 h-2.6 z M35 27 h2.6 v2 h-2.6 z" />
      <Hi cx="22" cy="45" rx="4" ry="2" o={0.35} />
    </>
  ),
  'apple-cobbler': () => (
    <>
      <Shadow />
      <path {...S} fill="#F2E8D5" d="M11 36 L53 36 L50 50 C49 53 15 53 14 50 Z" />
      <path {...S} fill="#B23A2A" d="M12 36 C12 31 52 31 52 36 C52 38 12 38 12 36 Z" />
      <path {...S} fill="#E8CF9E" d="M17 31 C17 25 25 23 28 27 C30 22 39 24 39 29 C44 26 50 30 47 34 L19 34 C16 33 16 32 17 31 Z" />
      <path fill="none" {...thin} stroke="#8E2A1B" d="M22 34 l4 0 M34 34 l4 0" />
      <Hi cx="22" cy="45" rx="4" ry="2" o={0.35} />
    </>
  ),
  'banana-pudding': () => (
    <>
      <Shadow rx={14} />
      <path {...S} fill="#F7EBCB" d="M16 24 L48 24 L44 52 L20 52 Z" />
      <path fill="none" {...thin} stroke="#E8C878" d="M17.5 34 L46.5 34 M18.8 42 L45.2 42" />
      <ellipse {...thin} cx="26" cy="38" rx="4" ry="3" fill="#F5E27A" />
      <ellipse {...thin} cx="38" cy="46" rx="3.6" ry="2.8" fill="#F5E27A" />
      <circle {...S} cx="38" cy="27" r="5.4" fill="#E3AC5C" />
      <circle fill="none" {...thin} cx="38" cy="27" r="2.6" stroke="#C68B33" />
      <path {...S} fill="#FFF6E3" d="M18 24 C18 17 46 17 46 24 C46 27 18 27 18 24 Z" />
      <Hi cx="24" cy="21" rx="4" ry="1.8" />
    </>
  ),
  'bread-pudding': () => (
    <>
      <Shadow />
      <path {...S} fill="#C98F52" d="M16 26 L48 26 L50 46 C50 50 14 50 14 46 Z" />
      <path fill={INK} opacity="0.3" d="M22 34 a1.8 1.8 0 1 0 3.6 0 a1.8 1.8 0 1 0 -3.6 0 M34 38 a1.8 1.8 0 1 0 3.6 0 a1.8 1.8 0 1 0 -3.6 0 M40 31 a1.8 1.8 0 1 0 3.6 0 a1.8 1.8 0 1 0 -3.6 0 M26 43 a1.8 1.8 0 1 0 3.6 0 a1.8 1.8 0 1 0 -3.6 0" />
      <path {...S} fill="#FBF3E0" d="M16 26 C16 21 48 21 48 26 C48 29 44 30 42 28 C41 32 36 32 34 29 C32 33 26 33 25 29 C22 31 17 30 16 26 Z" />
      <Hi cx="24" cy="24" rx="4" ry="1.6" />
    </>
  ),
  'carrot-cake': () => (
    <>
      <Shadow />
      <path {...S} fill="#9C6236" d="M14 46 L32 18 L50 46 C50 49 14 49 14 46 Z" />
      <path {...S} fill="#FBF3E0" d="M23 32 L41 32 L44 37 L20 37 Z" />
      <path {...S} fill="#FBF3E0" d="M28 24 L36 24 L38 28 L26 28 Z" />
      <path fill={INK} opacity="0.25" d="M25 42 a1.5 1.5 0 1 0 3 0 a1.5 1.5 0 1 0 -3 0 M35 43 a1.5 1.5 0 1 0 3 0 a1.5 1.5 0 1 0 -3 0" />
      <path {...thin} fill="#E8863C" d="M30 12 L34 12 L33 19 L31 19 Z" />
      <path fill="none" {...thin} stroke="#5C9E4A" d="M31 12 C30 9 28 9 27 10 M33 12 C34 9 36 9 37 10" />
      <Hi cx="27" cy="40" rx="3" />
    </>
  ),
  'cheesecake-squares': () => (
    <>
      <Shadow />
      <path {...S} fill="#D8A75C" d="M15 42 L49 42 L49 48 C49 51 15 51 15 48 Z" />
      <path {...S} fill="#FBF3E0" d="M15 26 L49 26 L49 42 L15 42 Z" />
      <circle {...S} cx="32" cy="22" r="5" fill="#B22438" />
      <path fill="none" {...thin} stroke="#5C9E4A" d="M33 17 C34 13 37 12 39 13" />
      <path fill="none" {...thin} stroke="#E8C878" d="M18 38 L46 38" opacity="0.7" />
      <Hi cx="22" cy="30" rx="4" ry="1.8" />
    </>
  ),
  'sugar-free-jello': () => (
    <>
      <Shadow />
      <path {...S} fill="#3FA457" opacity="0.92" d="M18 24 C18 18 46 18 46 24 L48 44 C48 50 16 50 16 44 Z" />
      <path fill="none" {...thin} stroke="#2C7A3E" d="M20 38 C26 41 38 41 44 38" />
      <Hi cx="25" cy="25" rx="5.4" ry="3" />
      <Hi cx="38" cy="33" rx="3" ry="1.8" o={0.35} />
    </>
  ),
  'cinnamon-rolls': () => (
    <>
      <Shadow />
      <circle {...S} cx="32" cy="34" r="17" fill="#E3AC5C" />
      <path fill="none" {...S} stroke="#8A5A2B" d="M32 34 C32 30 38 30 38 34 C38 39 26 39 26 33 C26 26 41 26 41 34 C41 42 23 42 23 33" />
      <path {...S} fill="#FBF6E9" d="M18 30 C24 24 40 24 46 30 C46 34 42 35 39 33 C38 37 32 37 30 34 C28 37 22 36 21 33 C19 34 18 32 18 30 Z" opacity="0.95" />
      <Hi cx="25" cy="27" rx="3.4" />
    </>
  ),

  // ═══ DRINK STATION ═══
  'fountain-soda': () => (
    <Cup fill="#C4462F" band="#F2E8D5">
      <path fill="none" {...thin} stroke="#C4462F" d="M23 33 C27 31 37 31 41 33" />
    </Cup>
  ),
  'sweet-tea': () => (
    <Glass fill="#C97F2E">
      {ice(24, 20, -8)}
      {ice(33, 26, 12)}
      {ice(26, 36, 5)}
      <path {...S} fill="#F5CE47" d="M40 10 A9 9 0 0 1 49 19 L40 19 Z" />
    </Glass>
  ),
  lemonade: () => (
    <Glass fill="#F5E27A">
      {ice(25, 22, 10)}
      {ice(32, 34, -6)}
      <circle {...thin} cx="40" cy="16" r="6.4" fill="#F5CE47" />
      <path fill="none" {...thin} stroke="#D9A81E" d="M40 10.5 L40 21.5 M35 13 L45 19 M35 19 L45 13" />
    </Glass>
  ),
  'fruit-punch': () => (
    <Glass fill="#D6304A">
      {ice(25, 24, -10)}
      {ice(31, 36, 8)}
      <path {...S} fill="#E8863C" d="M44 12 A8 8 0 0 1 36 20 L36 12 Z" transform="rotate(90 40 16)" />
    </Glass>
  ),
  coffee: () => (
    <>
      <Shadow rx={14} />
      <path {...S} fill="#D8BA8E" d="M14 22 L46 22 L44 50 C44 53 16 53 16 50 Z" />
      <path fill="none" {...S} stroke="#D8BA8E" strokeWidth="5" d="M46 28 C54 28 54 40 45 40" />
      <ellipse {...S} cx="30" cy="22" rx="16" ry="4.6" fill="#6E4527" />
      <ellipse fill="none" {...thin} cx="30" cy="22" rx="10" ry="2.6" stroke="#9C6236" />
      <path fill="none" {...thin} stroke={INK} opacity="0.5" d="M25 12 C23 15 27 16 25 19 M34 10 C32 13 36 14 34 17" />
      <Hi cx="21" cy="32" rx="2.4" ry="6" rot={4} o={0.4} />
    </>
  ),
  icee: () => (
    <>
      <Shadow rx={13} />
      <path {...S} fill="#F2E8D5" d="M20 28 L44 28 L41 54 L23 54 Z" />
      <path {...S} fill="#D6304A" d="M21 28 L43 28 L42 38 L22 38 Z" opacity="0.9" />
      <path {...S} fill="#3F7FBF" d="M22 38 L42 38 L41 47 L23 47 Z" opacity="0.9" />
      <path {...S} fill="#3F7FBF" d="M20 28 C17 18 25 12 32 15 C39 12 47 18 44 28 Z" opacity="0.85" />
      <path {...S} fill="#F2E8D5" d="M33 15 L39 4 L43 6 L36 16.5 Z" />
      <Hi cx="26" cy="21" rx="3.4" />
    </>
  ),

  // ═══ SOFT SERVE (machine output) ═══
  'soft-serve-vanilla': () => softServe(['#FFF6E3']),
  'soft-serve-chocolate': () => softServe(['#7B4A2D']),
  'soft-serve-swirl': () => softServe(['#FFF6E3', '#7B4A2D']),
}

export function FoodArt({ id, title, className, style }) {
  const draw = ART[id]
  if (!draw) {
    const emoji = ITEM_BY_ID[id]?.emoji || '🍽️'
    return (
      <span className={className} style={style} role="img" aria-label={title}>
        {emoji}
      </span>
    )
  }
  return (
    <svg
      viewBox="0 0 64 64"
      className={className}
      style={style}
      role="img"
      aria-label={title}
      focusable="false"
    >
      {draw()}
    </svg>
  )
}

export const ART_IDS = Object.keys(ART)
