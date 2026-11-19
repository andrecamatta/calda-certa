// Gera tests/fixtures/referencia_js.json executando o motor ORIGINAL do app
// (tools/referencia/motor_original.js) em node. Os testes Python comparam o
// motor reescrito contra esses resultados.
// Uso: node tools/gerar_fixtures.mjs
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { carregarMotor } from "./carregar_motor.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const M = carregarMotor();
const ings = Object.fromEntries(M.lr.map((e) => [e.id, e]));

// PRNG determinístico (mulberry32) para casos aleatórios reprodutíveis.
function mulberry32(a) {
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const rnd = mulberry32(20261119);
const pick = (arr) => arr[Math.floor(rnd() * arr.length)];
const r1 = (x) => Math.round(x * 10) / 10;

// --- cópias literais da lógica que vive nos componentes React ---------------
// Status por métrica e contagem "IDEAL" (componente sn: pt / Ol).
function statusParametros(Z, ct) {
  const pt = M.Nl.map((v) => {
    let F = Z.metrics[v.key] || 0,
      [E, b] = ct[v.key],
      B = "IDEAL";
    F < E - 0.01 ? (B = "ABAIXO") : F > b + 0.01 && (B = "ACIMA");
    return { key: v.key, value: F, min: E, max: b, status: B };
  });
  return { params: pt, ideal: pt.filter((v) => v.status === "IDEAL").length };
}
// Escalonar para peso alvo (componente sn: Oc).
function escalonar(items, Z, alvo) {
  let v = parseFloat(alvo),
    F = Z.totals.grams;
  if (isNaN(v) || v <= 0) return { erro: "alvo" };
  if (F <= 0) return { erro: "vazio" };
  let E = v / F;
  return { items: items.map((B) => ({ ...B, grams: Math.round(B.grams * E * 10) / 10 })) };
}
// Ficha técnica copiada para a área de transferência (componente sn: Vc).
function ficha(x, m, ft, je, Z, ct) {
  let v = (b, B = 1) => b.toFixed(B).replace(".", ","),
    F = [`${x} (${m}) — ${ft.name} — ${je.name}`, ["Ingrediente", "g", "%"].join("\t")],
    E = Z.totals.grams || 1;
  Z.rows.forEach((b) => {
    b.ingredient && F.push([b.ingredient.name, v(b.grams), v((b.grams / E) * 100)].join("\t"));
  });
  F.push(["TOTAL", v(Z.totals.grams), "100"].join("\t"));
  F.push("");
  M.Nl.forEach((b) => {
    let B = Z.metrics[b.key],
      [Be, xa] = ct[b.key];
    F.push(
      [b.label, `${v(B, b.decimals)} ${b.unit}`, `faixa ${v(Be, b.decimals)}–${v(xa, b.decimals)}`].join("\t"),
    );
  });
  Z.totals.evaporation > 0 &&
    F.push(`\xC1gua evaporada no cozimento\t${v(Z.totals.evaporation)} g (peso final ${v(Z.totals.grams)} g)`);
  F.push(`SNLG pela lactose (arenosidade)\t${v(Z.sandiness.value)}%\tlimite ${v(Z.sandiness.max)}%`);
  F.push(`Ponto de congelamento\t${v(Z.freezingPoint)} \xB0C`);
  F.push(`Servir a (~72% da \xE1gua congelada)\t${v(Z.scoopTemp)} \xB0C`);
  F.push(`Custo\tR$ ${v(Z.costPerKg, 2)}/kg`);
  return F.join("\n");
}
// ---------------------------------------------------------------------------

const itensJS = (lista) =>
  lista.map((i) => ({ ingredientId: i.ingredientId, grams: i.grams, locked: !!i.locked }));
const itensPy = (lista) =>
  lista.map((i) => ({ ingrediente: i.ingredientId, gramas: i.grams, travado: !!i.locked }));
const CAMPOS_LINHA = [
  "water", "fat", "protein", "sugars", "msnf", "otherSolids", "alcohol",
  "lactose", "msnfEq", "totalSolids", "pod", "pac", "cost",
];
const resumoAval = (Z) => ({
  totals: Z.totals,
  metrics: Z.metrics,
  sandiness: Z.sandiness,
  freezingPoint: Z.freezingPoint,
  frozenAtServe: Z.frozenAtServe,
  scoopTemp: Z.scoopTemp,
  costPerKg: Z.costPerKg,
  rows: Z.rows.map((r) => {
    const o = { ingrediente: r.ingredientId, grams: r.grams, conhecido: !!r.ingredient };
    for (const k of CAMPOS_LINHA) o[k] = r[k];
    return o;
  }),
});

const out = {
  gerado_de: "tools/referencia/motor_original.js",
  ingredientes: [],
  curva: [],
  avaliacoes: [],
  conformidade: [],
  escalonamentos: [],
  fichas: [],
  balanceamentos: [],
};

// 1) Ingredientes: rr (POD/PAC automáticos), vg (SNG pela lactose), Rl (avisos).
for (const e of M.lr) out.ingredientes.push({ id: e.id, rr: M.rr(e), vg: M.vg(e), avisos: M.Rl(e) });
// Ingredientes sintéticos (nomes de campo do app) para exercitar os avisos de Rl.
const sinteticos = [
  { id: "s1", water: 50, fat: 0, sugars: 10, msnf: 0, otherSolids: 30, lactose: 2, pod: 0, pac: 0 },
  { id: "s2", water: 80, fat: 2, sugars: 0, msnf: 10, otherSolids: 0, lactose: 7, protein: 4 },
  { id: "s3", water: 80, fat: 2, sugars: 0, msnf: 10, otherSolids: 0, lactose: 3, protein: 1 },
  { id: "s4", water: 50, fat: 0, sugars: 20, msnf: 0, otherSolids: 30, pod: 2, pac: 3, autoPodPac: true,
    profile: { sucrose: 5, sorbitol: 40, lacticAcid: 1 } },
  { id: "s5", water: 100, fat: 0, sugars: 0, msnf: 0, otherSolids: 0, pac: 5 },
  { id: "s6", water: 40, fat: 0, sugars: 10, msnf: 5, otherSolids: 5, alcohol: 40, lactose: 2, protein: 2,
    autoPodPac: true, profile: { glucose: 10, salt: 1, lacticAcid: 4 } },
  { id: "s7", water: 60, fat: 0, sugars: 30, msnf: 0, otherSolids: 0, pod: 3, pac: 4 },
];
for (const e of sinteticos)
  out.ingredientes.push({ id: e.id, ingrediente: e, rr: M.rr(e), vg: M.vg(e), avisos: M.Rl(e) });

// 2) Curva de congelamento e funções auxiliares em grade.
for (const se of [-5, 0, 1.5, 3, 44.4, 90, 179.9, 180, 200, 260]) {
  for (const msnf of [0, 3.3, 10]) {
    for (const w of [0, 20, 55.5, 64, 80]) {
      for (const T of [-6, -12, -18]) {
        out.curva.push({
          pac10: se, msnf, water: w, temp: T,
          Ig: M.Ig(se), Dl: M.Dl(se, msnf, w), Cg: M.Cg(se, msnf, w, T), Sg: M.Sg(se, msnf, w),
        });
      }
    }
  }
}

// 3) Avaliação de cada receita em cada máquina, com e sem água evaporada.
const receitas = M.ja.map((r) => ({
  id: r.id, nome: r.name, versao: r.version, perfil: r.familyId, maquina: r.machineId, items: itensJS(r.items),
}));
// Receitas aleatórias (ingredientes e gramas sorteados) para cobrir mais o espaço.
for (let n = 0; n < 60; n++) {
  const k = 2 + Math.floor(rnd() * 7);
  const items = [];
  for (let j = 0; j < k; j++) items.push({ ingredientId: pick(M.lr).id, grams: r1(rnd() * 600), locked: rnd() < 0.2 });
  if (n % 15 === 0) items.push({ ingredientId: "ing_inexistente", grams: 50, locked: false });
  receitas.push({
    id: `aleatoria_${n}`, nome: `Aleatória ${n}`, versao: "V1.0",
    perfil: pick(M.Jt).id, maquina: pick(M.ga).id, items,
  });
}

for (const r of receitas) {
  for (const maq of M.ga) {
    for (const evap of [0, 37.5]) {
      const Z = M.Bl(r.items, ings, maq.serveTemp, evap);
      out.avaliacoes.push({ receita: r.id, itens: itensPy(r.items), maquina: maq.id, evaporada: evap, ...resumoAval(Z) });
      if (evap === 0) {
        for (const fam of M.Jt) {
          const ct = M.Dc(fam, maq);
          const st = statusParametros(Z, ct);
          out.conformidade.push({
            receita: r.id, maquina: maq.id, perfil: fam.id, faixas: ct,
            status: st.params.map((p) => p.status), ideal: st.ideal,
          });
        }
      }
    }
  }
}
// Evaporação maior que a água: é limitada à água total.
{
  const r = receitas[0];
  const Z = M.Bl(r.items, ings, -12, 5000);
  out.avaliacoes.push({ receita: r.id, itens: itensPy(r.items), maquina: "mac_vitrine", evaporada: 5000, ...resumoAval(Z) });
}

// 4) Escalonamento para peso alvo.
for (const r of receitas.slice(0, 30)) {
  for (const [alvo, evap] of [[450, 0], [900, 0], [1000, 25], [1234.5, 0]]) {
    const Z = M.Bl(r.items, ings, -12, evap);
    const res = escalonar(r.items, Z, alvo);
    out.escalonamentos.push({
      receita: r.id, itens: itensPy(r.items), alvo, evaporada: evap,
      erro: res.erro || null, resultado: res.items ? itensPy(res.items) : null,
    });
  }
}

// 5) Ficha técnica (texto copiado pelo botão do app).
for (const r of receitas.slice(0, 21)) {
  const fam = M.Jt.find((f) => f.id === r.perfil);
  const maq = M.ga.find((m) => m.id === r.maquina);
  for (const evap of [0, 30]) {
    const Z = M.Bl(r.items, ings, maq.serveTemp, evap);
    out.fichas.push({
      receita: r.id, nome: r.nome, versao: r.versao, itens: itensPy(r.items), maquina: maq.id, perfil: fam.id,
      evaporada: evap, texto: ficha(r.nome, r.versao, fam, maq, Z, M.Dc(fam, maq)),
    });
  }
}

// 6) Auto-balanceamento (Fc).
const casosBal = [];
for (const r of receitas.slice(0, 21)) {
  const famR = M.Jt.find((f) => f.id === r.perfil);
  for (const maq of M.ga) casosBal.push({ r, maq, fam: famR, evap: 0, items: r.items });
  const maq = M.ga.find((m) => m.id === r.maquina);
  casosBal.push({ r, maq, fam: famR, evap: 40, items: r.items });
  casosBal.push({ r, maq, fam: famR, evap: 0, items: r.items.map((i, k) => ({ ...i, locked: k < 2 ? true : i.locked })) });
  casosBal.push({ r, maq, fam: pick(M.Jt), evap: 0, items: r.items });
}
for (const r of receitas.slice(21, 41)) {
  casosBal.push({ r, maq: M.ga.find((m) => m.id === r.maquina), fam: M.Jt.find((f) => f.id === r.perfil), evap: 0, items: r.items });
}
{
  const r = receitas[0];
  const maq = M.ga[0], fam = M.Jt[0];
  casosBal.push({ r, maq, fam, evap: 0, items: r.items.map((i) => ({ ...i, locked: true })) });
  casosBal.push({ r, maq, fam, evap: 0, items: r.items.map((i) => ({ ...i, grams: 0 })) });
}
for (const c of casosBal) {
  const ct = M.Dc(c.fam, c.maq);
  const res = M.Fc(c.items, ings, ct, c.evap);
  out.balanceamentos.push({
    receita: c.r.id, itens: itensPy(c.items), maquina: c.maq.id, perfil: c.fam.id, evaporada: c.evap,
    success: res.success, message: res.message, resultado: itensPy(res.items),
  });
}

const dest = path.join(here, "..", "tests", "fixtures", "referencia_js.json");
fs.mkdirSync(path.dirname(dest), { recursive: true });
fs.writeFileSync(dest, JSON.stringify(out) + "\n");
console.log(
  `ok: ${dest}`,
  Object.fromEntries(Object.entries(out).filter(([, v]) => Array.isArray(v)).map(([k, v]) => [k, v.length])),
);
