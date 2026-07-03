import { motion, useReducedMotion } from 'framer-motion'
import { useGame } from '../store/gameStore.js'
import { FoodArt } from '../art/foodArt.jsx'

export default function FoodItem({ item }) {
  const addItem = useGame((s) => s.addItem)
  const reduceMotion = useReducedMotion()

  return (
    <motion.button
      className="food-item"
      onClick={() => addItem(item)}
      whileTap={reduceMotion ? undefined : { scale: 0.88, y: 4 }}
      transition={{ type: 'spring', stiffness: 500, damping: 20 }}
    >
      <span className="food-pan">
        <FoodArt id={item.id} title={item.name} className="food-art" />
      </span>
      <span className="food-name">{item.name}</span>
      {item.size > 0 && (
        <span className="food-size" title={`${item.size} plate unit${item.size > 1 ? 's' : ''}`}>
          {'•'.repeat(item.size)}
        </span>
      )}
    </motion.button>
  )
}
