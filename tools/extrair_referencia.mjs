// Recorta, do bundle compilado do artefato "Calda Certa", o trecho com os DADOS
// e o MOTOR de cálculo (antes do código React da interface) e salva em
// tools/referencia/motor_original.js. Esse trecho é a fonte de verdade para
// gerar os arquivos de dados (gerar_dados.mjs) e os fixtures (gerar_fixtures.mjs).
//
// Uso: node tools/extrair_referencia.mjs caminho/para/all.js
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const src = process.argv[2];
if (!src) {
  console.error("uso: node tools/extrair_referencia.mjs <bundle.js>");
  process.exit(2);
}
const text = fs.readFileSync(src, "utf8").replace(/\r\n/g, "\n");
const INICIO = 'var Mc = ["rec_vermelhas_zero"]';
const FIM = "var s = $e(sr(), 1);";
const i = text.indexOf(INICIO);
const j = text.indexOf(FIM, i);
if (i < 0 || j < 0) {
  console.error("marcadores não encontrados no bundle");
  process.exit(1);
}
const trecho = text.slice(i, j).replace(/[ \t]+$/gm, "").trimEnd() + "\n";
const cab =
  "// Trecho extraído literalmente do bundle compilado do artefato Calda Certa\n" +
  "// (dados + motor, sem a interface React). Gerado por tools/extrair_referencia.mjs.\n" +
  "// Nomes minificados mantidos: xg=ingredientes base, _c=perfis de açúcar,\n" +
  "// lr=ingredientes efetivos, Jt=perfis/famílias, ga=máquinas, ja=receitas,\n" +
  "// Nl=métricas, it=curva de congelamento, Bl=avaliação, Fc=auto-balanceamento.\n";
const out = path.join(here, "referencia", "motor_original.js");
fs.mkdirSync(path.dirname(out), { recursive: true });
fs.writeFileSync(out, cab + trecho);
console.log(`ok: ${out} (${trecho.split("\n").length} linhas)`);
