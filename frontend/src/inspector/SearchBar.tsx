import { useState, type FormEvent } from 'react'

export interface SearchBarProps {
  cellTypes: string[]
  cellTypeFilter: string
  message: string | null
  onSearchId: (neuronId: string) => void
  onCellTypeFilter: (cellType: string) => void
}

export function SearchBar({ cellTypes, cellTypeFilter, message, onSearchId, onCellTypeFilter }: SearchBarProps) {
  const [value, setValue] = useState('')
  const submit = (event: FormEvent) => {
    event.preventDefault()
    onSearchId(value.trim())
  }
  return (
    <form className="search" onSubmit={submit} data-testid="inspector-search-form">
      <label className="control__label" htmlFor="inspector-search">
        Search neuron id <span className="muted">(exact id in the loaded circuit)</span>
      </label>
      <div className="search__row">
        <input
          id="inspector-search"
          type="text"
          inputMode="numeric"
          placeholder="e.g. 10010"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          data-testid="inspector-search"
          aria-label="Neuron id"
        />
        <button type="submit" className="btn btn--small" data-testid="inspector-search-submit">
          Find
        </button>
      </div>
      <label className="control__label" htmlFor="inspector-cell-type">
        Cell type <span className="muted">(values from loaded data only)</span>
      </label>
      <select
        id="inspector-cell-type"
        value={cellTypeFilter}
        onChange={(event) => onCellTypeFilter(event.target.value)}
        data-testid="inspector-cell-type"
      >
        <option value="">all cell types</option>
        {cellTypes.map((type) => (
          <option key={type} value={type}>
            {type}
          </option>
        ))}
      </select>
      {message && (
        <p className="search__message" role="status" data-testid="inspector-search-message">
          {message}
        </p>
      )}
    </form>
  )
}
