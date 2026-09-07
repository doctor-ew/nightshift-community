export const active = new Set(['running', 'in_progress']);
export const attention = new Set(['blocked', 'failed', 'needs-decision']);
export const modified = row => Math.max(0, ...(row.links || []).filter(Boolean).map(link => link.modified_at || 0));
export function currentRows(rows) {
  // File mtime orders presentation only. Never use it to supersede another gate,
  // batch or attempt's claim; concurrent and contradictory evidence stays visible.
  return rows.filter(r => ['batch', 'gate'].includes(r.source))
    .sort((a, b) => modified(b) - modified(a));
}
export function filterRows(rows, query, state, provider) {
  return rows.filter(row => (!query || [row.ticket, row.gate, row.checkout, row.provider].join(' ').toLowerCase().includes(query.toLowerCase()))
    && (state === 'all' || (state === 'active' ? active.has(row.state) : state === 'attention' ? attention.has(row.state) : row.state === state))
    && (provider === 'all' || row.provider === provider));
}
