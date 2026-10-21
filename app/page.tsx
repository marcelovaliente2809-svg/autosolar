import { readFile } from "node:fs/promises";
import path from "node:path";
import Aplicacion from "@/components/Aplicacion";
import Glosario from "@/components/Glosario";
import { extraerTips } from "@/lib/glosario";

const leer = (archivo: string) => readFile(path.join(process.cwd(), "content", archivo), "utf-8");

// Componente de servidor: los .md de content/ se leen en build time (la página es estática).
export default async function Pagina() {
  const [glosario, metodologia] = await Promise.all([leer("glosario.md"), leer("metodologia.md")]);
  return (
    <Aplicacion
      tips={extraerTips(glosario)}
      glosario={<Glosario markdown={glosario} />}
      metodologia={<Glosario markdown={metodologia} />}
    />
  );
}
