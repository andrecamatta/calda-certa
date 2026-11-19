// Gera src/caldacerta/data/*.json a partir de tools/referencia/motor_original.js.
// Uso: node tools/gerar_dados.mjs
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { carregarMotor } from "./carregar_motor.mjs";
import {
  CHAVES_PERFIL_ACUCAR, GRUPOS_ACUCAR, METRICAS,
  traduzirPerfilAcucar, traduzirFaixas,
} from "./mapeamento.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const destino = path.join(here, "..", "src", "caldacerta", "data");
const M = carregarMotor();
const num = (v) => Number(v) || 0;

// Ingredientes efetivos do app (lr = xg com perfis de açúcar aplicados e
// POD/PAC recalculados), na mesma ordem do banco.
const ingredientes = M.lr.map((e) => {
  const o = {
    id: e.id,
    nome: e.name,
    categoria: e.category,
    agua: num(e.water),
    gordura: num(e.fat),
    proteina: num(e.protein),
    acucares: num(e.sugars),
    sng: num(e.msnf),
    lactose: num(e.lactose),
    outros_solidos: num(e.otherSolids),
    alcool: num(e.alcohol),
    pod: num(e.pod),
    pac: num(e.pac),
    custo_kg: num(e.cost),
    pod_pac_auto: !!e.autoPodPac,
    perfil_acucares: traduzirPerfilAcucar(e.profile),
  };
  if (e.note) o.nota = e.note;
  return o;
});

const perfis = M.Jt.map((f) => ({
  id: f.id,
  grupo: f.group,
  nome: f.name,
  descricao: f.description,
  faixas: traduzirFaixas(f.ranges),
}));

const maquinas = M.ga.map((m) => ({
  id: m.id,
  nome: m.name,
  nome_curto: m.short,
  ajuste_pac: m.pacOffset,
  temp_servir: m.serveTemp,
  lote_g: m.batch,
  nota_lote: m.batchNote,
  dicas: [...m.tips],
}));

// Receitas: mesmo formato do arquivo de receita da CLI. lote_g segue o app ao
// carregar uma receita na bancada: Math.round(soma dos gramas) || 1000.
const receitas = M.ja.map((r) => {
  const soma = r.items.reduce((a, b) => a + (Number(b.grams) || 0), 0);
  return {
    id: r.id,
    nome: r.name,
    versao: r.version,
    perfil: r.familyId,
    maquina: r.machineId,
    status: r.status,
    notas: r.notes,
    atualizada_em: r.updatedAt,
    lote_g: Math.round(soma) || 1000,
    evaporada_g: num(r.evaporation),
    itens: r.items.map((i) => ({ ingrediente: i.ingredientId, gramas: i.grams, travado: !!i.locked })),
  };
});

const constantes = {
  _sobre: "Constantes do motor, copiadas do app original. Alterar muda os resultados.",
  acucares: M.Fl.map((a) => ({
    chave: CHAVES_PERFIL_ACUCAR[a.key], rotulo: a.label, grupo: GRUPOS_ACUCAR[a.group], pod: a.pod, pac: a.pac,
  })),
  lactose: { pod: M.wc.pod, pac: M.wc.pac },
  alcool: { pod: M.hg.pod, pac: M.hg.pac },
  curva_congelamento: M.it.map(([a, b]) => [a, b]),
  metricas: M.Nl.map((m) => ({
    chave: METRICAS[m.key], rotulo: m.label, unidade: m.unit, casas: m.decimals,
    dica_baixo: m.tipLow, dica_alto: m.tipHigh,
  })),
  grupos_perfis: [...M.Ac],
  substituicoes: Object.fromEntries(
    Object.entries(M.bl).map(([k, v]) => [k, { para: v.to, fator: v.factor, motivo: v.why }]),
  ),
  receitas_removidas: [...M.Mc],
};

fs.mkdirSync(destino, { recursive: true });
const grava = (nome, obj) => {
  fs.writeFileSync(path.join(destino, nome), JSON.stringify(obj, null, 2) + "\n");
  console.log(`ok: ${nome}`);
};
grava("ingredientes.json", ingredientes);
grava("perfis.json", perfis);
grava("maquinas.json", maquinas);
grava("receitas.json", receitas);
grava("constantes.json", constantes);
