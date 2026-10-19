import { readFile } from "node:fs/promises";
import path from "node:path";
import Aplicacion from "@/components/Aplicacion";
import Glosario from "@/components/Glosario";
import { extraerTips } from "@/lib/glosario";

// Componente de servidor: content/glosario.md se lee en build time (la página es estática).
export default async function Pagina() {
  const markdown = await readFile(path.join(process.cwd(), "content", "glosario.md"), "utf-8");
  return <Aplicacion tips={extraerTips(markdown)} glosario={<Glosario markdown={markdown} />} />;
}
