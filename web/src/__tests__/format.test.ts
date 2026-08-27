import { describe, expect, it } from 'vitest'
import { dishLine, distance, sourceLabel } from '../format'

describe('distance', () => {
  it('rounds metres to the nearest ten', () => {
    expect(distance(834)).toBe('830 m')
  })

  it('switches to kilometres past 950 m', () => {
    expect(distance(1200)).toBe('1.2 km')
  })

  it('drops the decimal for long distances', () => {
    expect(distance(12400)).toBe('12 km')
  })

  it('returns null rather than zero when there is no coordinate', () => {
    // A venue with null coordinates stays rankable by preference. Showing "0 m"
    // would claim it is where the user is standing.
    expect(distance(null)).toBeNull()
  })
})

describe('dishLine', () => {
  it('is null when the post named no dish', () => {
    expect(dishLine([])).toBeNull()
  })

  it('keeps dish names in their original script', () => {
    expect(dishLine(['椰浆饭', 'nasi lemak'])).toBe('椰浆饭, nasi lemak')
  })

  it('counts the overflow rather than truncating silently', () => {
    expect(dishLine(['a', 'b', 'c', 'd', 'e'])).toBe('a, b, c +2')
  })
})

describe('sourceLabel', () => {
  it('names the platform readably', () => {
    expect(sourceLabel('rednote', null)).toBe('RedNote')
  })

  it('attributes the author when there is one', () => {
    expect(sourceLabel('rednote', 'author_ab12')).toBe('RedNote · author_ab12')
  })

  it('passes an unknown platform through rather than hiding it', () => {
    expect(sourceLabel('instagram', null)).toBe('instagram')
  })
})
