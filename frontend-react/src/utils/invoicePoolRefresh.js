export function buildRefreshInvoicePoolTasks(pool, filters, { force = true } = {}) {
  const tasks = [];

  for (const direction of ['sale', 'purchase']) {
    const entries = Object.values(pool?.[direction] || {});
    if (entries.length === 0) {
      tasks.push({
        direction,
        filters,
        options: { defaultToCurrentMonth: false },
        force,
        source: 'empty_cache',
      });
      continue;
    }

    for (const entry of entries) {
      const query = entry?.query;
      if (!query) continue;
      tasks.push({
        direction,
        filters: {
          month: '',
          issue_date_from: query.issue_date_from || '',
          issue_date_to: query.issue_date_to || '',
          issue_date_before: query.issue_date_before || '',
          status: query.status || '',
          contractor: query.number_filter || '',
        },
        options: { defaultToCurrentMonth: false },
        force,
        source: 'cached_query',
      });
    }
  }

  return tasks;
}
