import { MENU_BY_STATION } from '../data/menu.js'
import FoodItem from './FoodItem.jsx'
import SoftServeMachine from './SoftServeMachine.jsx'

export default function Station({ station }) {
  const items = MENU_BY_STATION[station.id]
  return (
    <div className="station" aria-label={station.name}>
      <div className="sneeze-guard" aria-hidden="true" />
      <div className="station-scroll">
        {station.id === 'dessert-bar' && <SoftServeMachine />}
        {station.id === 'drinks' && (
          <p className="station-note">Drinks ride free — they don&rsquo;t take plate space. Pick your poison.</p>
        )}
        <div className="food-grid">
          {items.map((item) => (
            <FoodItem key={item.id} item={item} />
          ))}
        </div>
      </div>
    </div>
  )
}
