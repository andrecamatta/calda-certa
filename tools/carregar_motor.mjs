// Carrega tools/referencia/motor_original.js num contexto isolado (node:vm)
// e devolve os dados e funções originais do app.
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));

export function carregarMotor() {
  const code = fs.readFileSync(path.join(here, "referencia", "motor_original.js"), "utf8");
  const ctx = vm.createContext({});
  return vm.runInContext(
    code +
      "\n;({Mc, xg, Fl, wc, hg, Pc, rr, Lg, _c, bl, lr, Jt, ga, ja, Nl, Dc, it, Ig, Dl, Cg, Sg, vg, Bl, Rl, Fc, Ac, Tl})",
    ctx,
  );
}
