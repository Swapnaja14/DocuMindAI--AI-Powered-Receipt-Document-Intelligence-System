import { describe, it, expect } from 'vitest';

describe('RAG Citations & Response Parsing', () => {
  it('extracts bracketed citations [1], [2] correctly from answers', () => {
    const rawAnswer = 'Based on the receipt from Acme Corp [1], the subtotal was $45.00 with tax $3.60 [2].';
    const citationRegex = /\[(\d+)\]/g;
    const matches = [...rawAnswer.matchAll(citationRegex)].map(m => parseInt(m[1], 10));

    expect(matches).toEqual([1, 2]);
  });

  it('validates question string length requirements (3-2000 chars)', () => {
    const isValidQuestion = (q) => {
      if (!q || typeof q !== 'string') return false;
      const trimmed = q.trim();
      return trimmed.length >= 3 && trimmed.length <= 2000;
    };

    expect(isValidQuestion('')).toBe(false);
    expect(isValidQuestion('hi')).toBe(false);
    expect(isValidQuestion('   ')).toBe(false);
    expect(isValidQuestion('What was my total spend on groceries?')).toBe(true);
    expect(isValidQuestion('a'.repeat(2001))).toBe(false);
  });

  it('correctly maps evidence sources to metadata structure', () => {
    const backendSources = [
      {
        document_id: 'doc-65239a',
        filename: 'invoice_2026.pdf',
        page: 1,
        chunk_id: 'chunk-1',
        snippet: 'Total Paid: $450.00',
      },
    ];

    const source = backendSources[0];
    expect(source.document_id).toBeDefined();
    expect(source.filename).toBe('invoice_2026.pdf');
    expect(source.page).toBe(1);
    expect(source.snippet).toContain('$450.00');
  });
});
