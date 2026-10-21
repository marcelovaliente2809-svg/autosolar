import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/** Renderiza content/glosario.md y content/metodologia.md (componente de servidor: el markdown no
 * llega al cliente). Los enlaces abren en pestaña nueva. */
export default function Glosario({ markdown }: { markdown: string }) {
  return (
    <article className="max-w-4xl space-y-4 text-sm leading-relaxed text-tinta-2">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: (p) => <h1 className="text-2xl font-semibold text-tinta" {...p} />,
          h2: (p) => <h2 className="mt-8 border-b border-borde pb-1 text-lg font-semibold text-tinta" {...p} />,
          h3: (p) => <h3 className="mt-4 font-semibold text-tinta" {...p} />,
          a: ({ node: _, ...p }) => (
            <a
              className="text-acento underline decoration-acento/40 underline-offset-2 hover:decoration-acento"
              target="_blank"
              rel="noopener noreferrer"
              {...p}
            />
          ),
          ul: (p) => <ul className="list-disc space-y-1 pl-5" {...p} />,
          ol: (p) => <ol className="list-decimal space-y-1 pl-5" {...p} />,
          strong: (p) => <strong className="font-semibold text-tinta" {...p} />,
          table: (p) => (
            <div className="overflow-x-auto rounded-xl border border-borde bg-panel">
              <table className="w-full min-w-[560px] border-collapse text-left text-[13px]" {...p} />
            </div>
          ),
          thead: (p) => <thead className="border-b border-borde bg-fondo/70 text-xs text-tinta-2" {...p} />,
          th: (p) => <th className="px-4 py-2 font-semibold" {...p} />,
          tbody: (p) => <tbody className="divide-y divide-borde/70" {...p} />,
          td: (p) => <td className="px-4 py-2 align-top first:w-[22%] first:font-medium first:text-tinta" {...p} />,
        }}
      >
        {markdown}
      </ReactMarkdown>
    </article>
  );
}
