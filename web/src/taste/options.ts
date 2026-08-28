import type { Prefs } from '../api'

export type Choice<T> = { value: T; label: string; note?: string }

/**
 * Craving options, generated deterministically from the clock. No API call and no
 * randomness, so the same hour always produces the same four.
 *
 * The clock is real information rather than a gimmick: somebody hungry at 08:00 and
 * somebody hungry at 23:00 want different food, and offering bak kut teh at breakfast
 * wastes the one screen where we get to be useful. Every dish below appears in the
 * corpus, written the way the posts write it, which is also why the labels carry
 * Chinese, Malay and English together instead of picking one.
 */
export function cravingOptions(now: Date = new Date()): Choice<string>[] {
  const h = now.getHours()
  if (h >= 5 && h < 11) {
    return [
      { value: 'roti canai teh tarik', label: 'Roti Canai And Teh Tarik' },
      { value: '咖央多士 kaya toast kopitiam', label: '咖央多士, Kaya Toast' },
      { value: 'nasi lemak 椰浆饭', label: 'Nasi Lemak, 椰浆饭' }
    ]
  }
  if (h >= 11 && h < 16) {
    return [
      { value: '瓦煲鸡饭 claypot chicken rice', label: '瓦煲鸡饭, Claypot Chicken Rice' },
      { value: 'nasi campur banana leaf rice', label: 'Nasi Campur Or Banana Leaf' },
      { value: '咖喱叻沙 curry laksa noodles', label: '咖喱叻沙, Curry Laksa' }
    ]
  }
  if (h >= 16 && h < 22) {
    return [
      { value: '肉骨茶 bak kut teh', label: '肉骨茶, Bak Kut Teh' },
      { value: 'ayam goreng berempah satay', label: 'Ayam Goreng Berempah, Satay' },
      { value: '海鲜 seafood 大排档', label: '海鲜, Seafood' }
    ]
  }
  return [
    { value: 'nasi lemak bumbung supper', label: 'Nasi Lemak, Late' },
    { value: '牛肉粉 beef noodles 粥', label: '牛肉粉, Beef Noodles' },
    { value: '炒粿条 char kuey teow', label: '炒粿条, Char Kuey Teow' }
  ]
}

export const COMPANY: Choice<NonNullable<Prefs['company']>>[] = [
  { value: 'solo', label: 'On My Own', note: 'Counter seats and a quick queue are fine.' },
  { value: 'couple', label: 'Two Of Us' },
  { value: 'family', label: 'Family', note: 'Somewhere with room and a mixed menu.' },
  { value: 'group', label: 'A Group', note: 'Big table, shared plates.' }
]

export const RANGE: Choice<number>[] = [
  { value: 1000, label: 'Walking Distance', note: 'About 1 km.' },
  { value: 3000, label: 'A Short Drive', note: 'About 3 km.' },
  { value: 10000, label: 'Across Town', note: 'About 10 km.' },
  { value: 0, label: 'Anywhere In KL', note: 'No location needed.' }
]

export const MOOD: Choice<NonNullable<Prefs['mood']>>[] = [
  { value: 'comfort', label: 'Something Familiar', note: 'The version people keep going back to.' },
  { value: 'adventurous', label: 'Something New', note: 'Somewhere I have not been.' }
]

export const BUDGET: Choice<NonNullable<Prefs['budget']>>[] = [
  { value: 'cheap', label: 'Cheap' },
  { value: 'mid', label: 'Mid' },
  { value: 'splurge', label: 'Splurge' }
]

export const STEPS = ['Craving', 'Company', 'Range', 'Mood'] as const
export type StepName = (typeof STEPS)[number]
