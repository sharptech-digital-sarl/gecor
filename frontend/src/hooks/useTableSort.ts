import { useCallback, useMemo, useState } from 'react'

export type SortDirection = 'asc' | 'desc'

export function useTableSort<K extends string>(initialKey: K, initialDir: SortDirection = 'asc') {
  const [sortBy, setSortBy] = useState<K>(initialKey)
  const [sortDir, setSortDir] = useState<SortDirection>(initialDir)

  const toggleSort = useCallback(
    (key: K) => {
      if (sortBy === key) {
        setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
      } else {
        setSortBy(key)
        setSortDir('asc')
      }
    },
    [sortBy]
  )

  const sortRows = useCallback(
    <T,>(rows: T[], accessor: (row: T, key: K) => string | number | Date | null | undefined) => {
      const copy = [...rows]
      copy.sort((a, b) => {
        const va = accessor(a, sortBy)
        const vb = accessor(b, sortBy)
        const aEmpty = va === null || va === undefined || va === ''
        const bEmpty = vb === null || vb === undefined || vb === ''
        if (aEmpty && bEmpty) return 0
        if (aEmpty) return 1
        if (bEmpty) return -1
        let cmp = 0
        if (va instanceof Date && vb instanceof Date) cmp = va.getTime() - vb.getTime()
        else if (typeof va === 'number' && typeof vb === 'number') cmp = va - vb
        else cmp = String(va).localeCompare(String(vb), undefined, { numeric: true, sensitivity: 'base' })
        return sortDir === 'asc' ? cmp : -cmp
      })
      return copy
    },
    [sortBy, sortDir]
  )

  return useMemo(
    () => ({ sortBy, sortDir, toggleSort, sortRows }),
    [sortBy, sortDir, toggleSort, sortRows]
  )
}
