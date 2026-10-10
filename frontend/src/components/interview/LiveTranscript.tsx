// The transcript while the user speaks, with filler words highlighted as they happen.

import { findFillers } from "../../lib/fillers";

interface Props {
  text: string;
  interim?: string;
  placeholder?: string;
}

export default function LiveTranscript({ text, interim = "", placeholder = "Your words will appear here as you speak." }: Props) {
  if (!text && !interim) return <p className="text-sm text-slate-400">{placeholder}</p>;
  return (
    <p className="max-h-56 overflow-y-auto text-sm leading-relaxed whitespace-pre-wrap">
      <HighlightFillers text={text} /> {interim && <span className="text-slate-400">{interim}</span>}
    </p>
  );
}

export function HighlightFillers({ text }: { text: string }) {
  const hits = findFillers(text);
  const out: React.ReactNode[] = [];
  let pos = 0;
  hits.forEach((h, i) => {
    if (h.start < pos) return;
    out.push(text.slice(pos, h.start));
    out.push(
      <mark key={i} className="rounded bg-amber-200 px-0.5 text-amber-950 dark:bg-amber-500/40 dark:text-amber-100" title="Filler word">
        {text.slice(h.start, h.end)}
      </mark>,
    );
    pos = h.end;
  });
  out.push(text.slice(pos));
  return <>{out}</>;
}
