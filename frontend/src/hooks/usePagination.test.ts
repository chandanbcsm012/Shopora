import { act, renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { usePagination } from './usePagination'

describe('usePagination', () => {
  it('computes totalPages from total/pageSize and starts on page 1', () => {
    const { result } = renderHook(() => usePagination(45, 10))
    expect(result.current.page).toBe(1)
    expect(result.current.totalPages).toBe(5)
  })

  it('never reports fewer than 1 total page, even with zero items', () => {
    const { result } = renderHook(() => usePagination(0, 10))
    expect(result.current.totalPages).toBe(1)
  })

  it('goToNext/goToPrevious clamp within [1, totalPages]', () => {
    const { result } = renderHook(() => usePagination(25, 10))
    expect(result.current.totalPages).toBe(3)

    act(() => result.current.goToPrevious())
    expect(result.current.page).toBe(1)

    act(() => result.current.goToNext())
    act(() => result.current.goToNext())
    act(() => result.current.goToNext())
    expect(result.current.page).toBe(3)
  })

  it('setPage sets the page directly', () => {
    const { result } = renderHook(() => usePagination(25, 10))
    act(() => result.current.setPage(2))
    expect(result.current.page).toBe(2)
  })
})
