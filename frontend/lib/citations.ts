export interface ParsedCitations {
  body: string;
  sources: Record<string, string>;
}

/**
 * Parses the agent's Perplexity-style citation convention: inline [1], [2] markers with a
 * trailing "**Sources**" list mapping each number to what it is. Strips the trailing list and
 * turns each inline marker into a markdown link (`[1](#cite-1 "source text")`) carrying the
 * source text as its title, so a custom link renderer can show it as a hover tooltip instead
 * of a separate list the reader has to scroll to and cross-reference.
 */
export function extractCitations(content: string): ParsedCitations {
  const sources: Record<string, string> = {};
  const sourcesHeaderRe = /\n{1,2}\*\*Sources\*\*\s*\n([\s\S]*)$/i;
  const match = content.match(sourcesHeaderRe);
  let body = content;

  if (match) {
    body = content.slice(0, match.index).trimEnd();
    const lineRe = /^\[(\d+)\]\s*(.+)$/gm;
    let m: RegExpExecArray | null;
    while ((m = lineRe.exec(match[1])) !== null) {
      sources[m[1]] = m[2].trim();
    }
  }

  body = body.replace(/\[(\d+)\](?!\()/g, (whole, num: string) => {
    const src = sources[num];
    if (!src) return whole; // no matching Sources entry — not a real citation, leave as-is
    const safeTitle = src.replace(/"/g, "'");
    return `[${num}](#cite-${num} "${safeTitle}")`;
  });

  return { body, sources };
}
