import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

// Markdown renderer for assistant replies. The LangGraph agent emits GH-
// flavored markdown (tables, bold, headers, lists) and we were dumping it
// as pre-wrapped plaintext, which made tables unreadable. react-markdown +
// remark-gfm covers tables + strikethrough + autolinks; everything else
// here is dark-theme styling via the components map so we don't need the
// @tailwindcss/typography plugin (which would add another dep for five
// elements we actually use).

interface Props {
  source: string
}

export default function Markdown({ source }: Props) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        p: ({ children }) => <p className="mb-2 last:mb-0 leading-relaxed">{children}</p>,
        h1: ({ children }) => (
          <h1 className="text-lg font-semibold mt-3 mb-2 text-[var(--color-text)]">{children}</h1>
        ),
        h2: ({ children }) => (
          <h2 className="text-base font-semibold mt-3 mb-2 text-[var(--color-text)]">
            {children}
          </h2>
        ),
        h3: ({ children }) => (
          <h3 className="text-sm font-semibold mt-2 mb-1 text-[var(--color-text)]">{children}</h3>
        ),
        strong: ({ children }) => (
          <strong className="font-semibold text-[var(--color-accent)]">{children}</strong>
        ),
        em: ({ children }) => <em className="italic">{children}</em>,
        ul: ({ children }) => (
          <ul className="list-disc pl-5 space-y-1 mb-2">{children}</ul>
        ),
        ol: ({ children }) => (
          <ol className="list-decimal pl-5 space-y-1 mb-2">{children}</ol>
        ),
        li: ({ children }) => <li className="leading-relaxed">{children}</li>,
        a: ({ href, children }) => (
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[var(--color-accent)] underline hover:brightness-125"
          >
            {children}
          </a>
        ),
        code: ({ children, ...props }) => {
          const isInline = !('data-language' in props)
          return isInline ? (
            <code className="rounded bg-[var(--color-surface-raised)] px-1 py-0.5 text-xs font-mono text-[var(--color-accent)]">
              {children}
            </code>
          ) : (
            <code className="font-mono text-xs">{children}</code>
          )
        },
        pre: ({ children }) => (
          <pre className="rounded-md bg-[var(--color-surface-raised)] border border-[var(--color-border)] p-3 overflow-x-auto text-xs mb-2">
            {children}
          </pre>
        ),
        table: ({ children }) => (
          <div className="overflow-x-auto my-2 rounded-md border border-[var(--color-border)]">
            <table className="w-full text-xs border-collapse">{children}</table>
          </div>
        ),
        thead: ({ children }) => (
          <thead className="bg-[var(--color-surface-raised)] text-[var(--color-text-muted)] uppercase tracking-wider">
            {children}
          </thead>
        ),
        th: ({ children }) => (
          <th className="text-left px-3 py-2 font-medium border-b border-[var(--color-border)]">
            {children}
          </th>
        ),
        td: ({ children }) => (
          <td className="px-3 py-2 border-t border-[var(--color-border)] align-top">
            {children}
          </td>
        ),
        blockquote: ({ children }) => (
          <blockquote className="border-l-2 border-[var(--color-accent)]/50 pl-3 italic text-[var(--color-text-muted)] my-2">
            {children}
          </blockquote>
        ),
        hr: () => <hr className="my-3 border-[var(--color-border)]" />,
      }}
    >
      {source}
    </ReactMarkdown>
  )
}
