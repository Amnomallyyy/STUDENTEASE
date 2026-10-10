// Minimal, safe markdown for chat replies: **bold**, *italic* / _italic_, `code`, "- " / "* " / "1. " lists
// and blank-line paragraphs. Builds React elements (never innerHTML), so model output cannot inject markup.
// Unfinished markers while a reply is still streaming are shown as plain text.
import type { ReactNode } from "react";

const INLINE = /(\*\*[^*\n]+\*\*|`[^`\n]+`|\*[^*\s][^*\n]*\*|_[^_\s][^_\n]*_)/g;

export function renderInline(text: string, keyPrefix = "i"): ReactNode[] {
  const out: ReactNode[] = [];
  let last = 0;
  let n = 0;
  for (const m of text.matchAll(INLINE)) {
    const start = m.index ?? 0;
    if (start > last) out.push(text.slice(last, start));
    const token = m[0];
    const key = `${keyPrefix}-${n++}`;
    if (token.startsWith("**")) out.push(<strong key={key}>{token.slice(2, -2)}</strong>);
    else if (token.startsWith("`"))
      out.push(
        <code key={key} className="rounded bg-white/10 px-1 text-[0.85em]">
          {token.slice(1, -1)}
        </code>,
      );
    else out.push(<em key={key}>{token.slice(1, -1)}</em>);
    last = start + token.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

type Block = { kind: "p"; lines: string[] } | { kind: "ul" | "ol"; items: string[] };

const BULLET = /^\s*[-*•]\s+(.*)$/;
const NUMBERED = /^\s*\d+[.)]\s+(.*)$/;

export function parseBlocks(text: string): Block[] {
  const blocks: Block[] = [];
  for (const raw of text.replace(/\r\n/g, "\n").split("\n")) {
    const bullet = raw.match(BULLET);
    const numbered = raw.match(NUMBERED);
    const last = blocks[blocks.length - 1];
    if (bullet || numbered) {
      const kind = bullet ? "ul" : "ol";
      const item = (bullet ?? numbered)![1];
      if (last && last.kind === kind) last.items.push(item);
      else blocks.push({ kind, items: [item] });
    } else if (!raw.trim()) {
      blocks.push({ kind: "p", lines: [] }); // paragraph break
    } else if (last && last.kind === "p" && last.lines.length) {
      last.lines.push(raw);
    } else {
      blocks.push({ kind: "p", lines: [raw] });
    }
  }
  return blocks.filter((b) => (b.kind === "p" ? b.lines.length > 0 : b.items.length > 0));
}

export function MiniMarkdown({ text }: { text: string }) {
  return (
    <>
      {parseBlocks(text).map((block, b) => {
        if (block.kind === "p")
          return (
            <p key={b} className="mb-2 last:mb-0">
              {block.lines.map((line, l) => (
                <span key={l}>
                  {l > 0 && <br />}
                  {renderInline(line, `${b}-${l}`)}
                </span>
              ))}
            </p>
          );
        const List = block.kind === "ul" ? "ul" : "ol";
        return (
          <List key={b} className={`mb-2 space-y-0.5 pl-5 last:mb-0 ${block.kind === "ul" ? "list-disc" : "list-decimal"}`}>
            {block.items.map((item, i) => (
              <li key={i}>{renderInline(item, `${b}-${i}`)}</li>
            ))}
          </List>
        );
      })}
    </>
  );
}
