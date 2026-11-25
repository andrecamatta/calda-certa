/**
 * Motor completo do Calda Certa em JavaScript (ESM).
 *
 * Implementa fielmente ``motor.py``, ``nutricao.py``, ``relatorio.py``,
 * ``ficha.py`` e ``receita.py`` para rodar 100% no navegador (e em Node.js
 * para testes de equivalência).
 */

export const CHAVES_BALANCO = [
  "gordura",
  "proteina",
  "acucares",
  "sng",
  "outros_solidos",
  "solidos_totais",
  "pod",
  "pac",
];

const CAMPOS = [
  "agua",
  "gordura",
  "proteina",
  "acucares",
  "sng",
  "outros_solidos",
  "alcool",
  "lactose",
  "sng_lactose",
  "solidos_totais",
  "pod",
  "pac",
  "custo",
];

export const FRACAO_GELO_SERVIR = 0.72;
export const TEMP_SERVIR_PADRAO = -12.0;

export const PESOS_BALANCO = {
  gordura: 2.5,
  proteina: 0.8,
  acucares: 2,
  sng: 2,
  outros_solidos: 1,
  solidos_totais: 2.4,
  pod: 2,
  pac: 2.6,
};

export const MSG_POUCOS_DESTRAVADOS =
  "Destrave pelo menos 2 ingredientes para o otimizador trabalhar.";
export const MSG_MASSA_ZERO = "A receita precisa ter massa maior que zero.";
export const MSG_JA_OTIMO =
  "A fórmula já está no melhor ponto possível com os ingredientes destravados.";
export const MSG_AJUSTADA =
  "Fórmula ajustada: ingredientes destravados movidos em direção ao centro das faixas.";

// ---------------------------------------------------------------------------
// Utilitários numéricos (mesma semântica de jsnum.py)
// ---------------------------------------------------------------------------
export function numero(x) {
  if (x === null || x === undefined || x === "") return 0;
  const v = Number(x);
  return Number.isNaN(v) ? 0 : v === 0 ? 0 : v;
}

export function br(x, casas = 1) {
  const v = Number(x);
  if (Number.isNaN(v)) return "NaN";
  if (!Number.isFinite(v)) return v > 0 ? "Infinity" : "-Infinity";
  let s = v.toFixed(casas);
  if (v === 0) s = s.replace(/^-/, "");
  return s.replace(".", ",");
}

// ---------------------------------------------------------------------------
// Merge de dados base + novidades + customizados
// ---------------------------------------------------------------------------
export function construirCatalogo(bundle, custom = {}) {
  const constantes = bundle.constantes;
  const nov = bundle.novidades || {};
  const kNov = nov.constantes || {};
  const compl = nov.complementos_ingredientes || {};

  const complementar = (lista) =>
    lista.map((ing) => {
      const extra = compl[ing.id];
      if (!extra) return { ...ing };
      const out = { ...ing };
      for (const [k, v] of Object.entries(extra)) {
        if (out[k] === undefined) out[k] = v;
      }
      return out;
    });

  // Custom ingredients override or prepend; base + novidades
  const customIngs = Array.isArray(custom.ingredientes) ? custom.ingredientes : [];
  const customIngIds = new Set(customIngs.map((i) => i.id));
  const baseIngs = (bundle.ingredientes || []).map((i) => ({
    ...i,
    _origem: "base",
  }));
  const baseIngIds = new Set(baseIngs.map((i) => i.id));
  const novIngs = (nov.ingredientes || [])
    .filter((i) => !baseIngIds.has(i.id))
    .map((i) => ({ ...i, _origem: "novidade" }));

  const ingsMerged = complementar([
    ...customIngs.map((i) => ({ ...i, _origem: "usuario" })),
    ...baseIngs.filter((i) => !customIngIds.has(i.id)),
    ...novIngs.filter((i) => !customIngIds.has(i.id)),
  ]);
  const mapaIngredientes = Object.fromEntries(ingsMerged.map((i) => [i.id, i]));

  // Perfis
  const basePerfis = (bundle.perfis || []).map((p) => ({ ...p, _origem: "base" }));
  const basePerfilIds = new Set(basePerfis.map((p) => p.id));
  const novPerfis = (nov.perfis || [])
    .filter((p) => !basePerfilIds.has(p.id))
    .map((p) => ({ ...p, _origem: "novidade" }));
  const perfis = [...basePerfis, ...novPerfis];
  const mapaPerfis = Object.fromEntries(perfis.map((p) => [p.id, p]));

  // Máquinas
  const maquinas = (bundle.maquinas || []).map((m) => ({ ...m }));
  const mapaMaquinas = Object.fromEntries(maquinas.map((m) => [m.id, m]));

  // Receitas
  const customRecs = Array.isArray(custom.receitas) ? custom.receitas : [];
  const customRecIds = new Set(customRecs.map((r) => r.id));
  const baseRecs = (bundle.receitas || []).map((r) => ({ ...r, _origem: "base" }));
  const baseRecIds = new Set(baseRecs.map((r) => r.id));
  const novRecs = (nov.receitas || [])
    .filter((r) => !baseRecIds.has(r.id))
    .map((r) => ({ ...r, _origem: "novidade" }));
  const receitas = [
    ...customRecs.map((r) => ({ ...r, _origem: "usuario" })),
    ...baseRecs.filter((r) => !customRecIds.has(r.id)),
    ...novRecs.filter((r) => !customRecIds.has(r.id)),
  ];

  return {
    constantes,
    constantesNov: kNov,
    ingredientes: ingsMerged,
    mapaIngredientes,
    perfis,
    mapaPerfis,
    maquinas,
    mapaMaquinas,
    receitas,
  };
}

// ---------------------------------------------------------------------------
// POD/PAC automáticos e SNG pela lactose
// ---------------------------------------------------------------------------
export function podPacAutomatico(ing, constantes) {
  const perfil = ing.perfil_acucares || {};
  let t = 0;
  let o = 0;
  for (const a of constantes.acucares) {
    const n = numero(perfil[a.chave]);
    t += n * a.pod;
    o += n * a.pac;
  }
  const r = numero(ing.lactose);
  const lalc = numero(ing.alcool);
  t += r * constantes.lactose.pod;
  o += r * constantes.lactose.pac + lalc * constantes.alcool.pac;
  return {
    pod: Math.round(t * 10) / 10,
    pac: Math.round(o * 10) / 10,
  };
}

export function aplicarPodPacAuto(ing, constantes) {
  const novo = { ...ing };
  if (novo.pod_pac_auto) {
    Object.assign(novo, podPacAutomatico(novo, constantes));
  }
  return novo;
}

export function sngPelaLactose(ing) {
  const a = numero(ing.sng);
  const t = numero(ing.lactose);
  if (a <= 0) return 0;
  return t > 0 ? Math.min(a, t / 0.545) : a;
}

// ---------------------------------------------------------------------------
// Curva de congelamento
// ---------------------------------------------------------------------------
export function depressaoCurva(se, curva) {
  if (se <= 0) return 0;
  const a = curva[curva.length - 1];
  if (se >= a[0]) {
    const t = curva[curva.length - 2];
    return a[1] + ((se - a[0]) * (a[1] - t[1])) / (a[0] - t[0]);
  }
  for (let idx = 1; idx < curva.length; idx++) {
    const [o, r] = curva[idx];
    if (se <= o) {
      const [l, u] = curva[idx - 1];
      return u + ((se - l) * (r - u)) / (o - l);
    }
  }
  return a[1];
}

export function depressao(pac10, sng, agua, curva) {
  if (agua <= 0) return Infinity;
  return depressaoCurva((pac10 / agua) * 100, curva) + (2.37 * sng) / agua;
}

export function fracaoCongelada(pac10, sng, agua, temp, curva) {
  if (agua <= 0) return 0;
  const r = -temp;
  if (depressao(pac10, sng, agua, curva) >= r) return 0;
  let lo = 0.01;
  let hi = agua;
  for (let i = 0; i < 60; i++) {
    const d = (lo + hi) / 2;
    if (depressao(pac10, sng, d, curva) > r) {
      lo = d;
    } else {
      hi = d;
    }
  }
  return (agua - (lo + hi) / 2) / agua;
}

export function tempServirIdeal(
  pac10,
  sng,
  agua,
  fracaoGelo = FRACAO_GELO_SERVIR,
  curva
) {
  if (agua <= 0) return 0;
  return -depressao(pac10, sng, agua * (1 - fracaoGelo), curva);
}

/** Amostra pontos (temp °C, fração congelada %) para o gráfico SVG. */
export function amostrarCurvaCongelamento(metricas, curva, tempMin = -22, passo = 0.5) {
  const pac10 = metricas.pac / 10;
  const sng = metricas.sng_lactose;
  const agua = metricas.agua;
  const pontos = [];
  if (agua <= 1) return pontos;
  for (let t = 0; t >= tempMin - 1e-9; t -= passo) {
    const tc = Math.round(t * 10) / 10;
    const fc = fracaoCongelada(pac10, sng, agua, tc, curva);
    pontos.push({ temp: tc, fracao: fc * 100 });
  }
  return pontos;
}

// ---------------------------------------------------------------------------
// Avaliação da receita (Bl)
// ---------------------------------------------------------------------------
function numCampo(ing, chave) {
  const v = ing[chave];
  return typeof v === "number" ? v : numero(v);
}

export function avaliar(
  itens,
  ingredientes,
  constantes,
  tempServir = TEMP_SERVIR_PADRAO,
  evaporada = 0
) {
  const curva = constantes.curva_congelamento;
  const tot = { gramas: 0 };
  for (const c of CAMPOS) tot[c] = 0;

  const linhas = [];
  for (const item of itens) {
    const ingId = item.ingrediente;
    const c = ingId != null ? ingredientes[ingId] : null;
    const f = Math.max(0, numero(item.gramas));
    tot.gramas += f;
    if (!c) {
      const linha = {
        ...item,
        ingrediente: ingId,
        gramas: f,
        conhecido: false,
        nome: null,
      };
      for (const k of CAMPOS) linha[k] = 0;
      linhas.push(linha);
      continue;
    }
    const h = f / 100;
    const s = {
      agua: h * numCampo(c, "agua"),
      gordura: h * numCampo(c, "gordura"),
      proteina: h * numero(c.proteina),
      acucares: h * numCampo(c, "acucares"),
      sng: h * numCampo(c, "sng"),
      outros_solidos: h * numCampo(c, "outros_solidos"),
      alcool: h * numero(c.alcool),
      lactose: h * numero(c.lactose),
      sng_lactose: h * sngPelaLactose(c),
      pod: h * numCampo(c, "pod"),
      pac: h * numCampo(c, "pac"),
      custo: (f * numCampo(c, "custo_kg")) / 1e3,
    };
    s.solidos_totais = s.gordura + s.acucares + s.sng + s.outros_solidos;
    for (const k of [
      "agua",
      "gordura",
      "proteina",
      "acucares",
      "sng",
      "outros_solidos",
      "alcool",
      "lactose",
      "sng_lactose",
      "pod",
      "pac",
      "custo",
      "solidos_totais",
    ]) {
      tot[k] += s[k];
    }
    linhas.push({
      ...item,
      ingrediente: ingId,
      gramas: f,
      conhecido: true,
      nome: c.nome,
      ...s,
    });
  }

  const n = Math.max(0, Math.min(numero(evaporada), tot.agua));
  tot.gramas_brutos = tot.gramas;
  tot.evaporada = n;
  tot.agua -= n;
  tot.gramas -= n;
  const g = tot.gramas;

  const pct = (v) => (g > 0 ? (v / g) * 100 : 0);
  const porKg = (v) => (g > 0 ? (v / g) * 1e3 : 0);

  const m = {
    agua: pct(tot.agua),
    gordura: pct(tot.gordura),
    proteina: pct(tot.proteina),
    acucares: pct(tot.acucares),
    sng: pct(tot.sng),
    outros_solidos: pct(tot.outros_solidos),
    solidos_totais: pct(tot.solidos_totais),
    alcool: pct(tot.alcool),
    lactose: pct(tot.lactose),
    sng_lactose: pct(tot.sng_lactose),
    pod: porKg(tot.pod),
    pac: porKg(tot.pac),
  };

  const limite = Math.max(
    0,
    (100 - (m.acucares + m.gordura + m.outros_solidos)) * 0.15
  );
  const arenosidade = {
    valor: m.sng_lactose,
    maximo: limite,
    ok: m.sng_lactose <= limite + 0.05,
  };
  const pac10 = m.pac / 10;
  const ponto =
    m.agua > 1 ? -depressao(pac10, m.sng_lactose, m.agua, curva) : 0;
  const congelada = fracaoCongelada(
    pac10,
    m.sng_lactose,
    m.agua,
    tempServir,
    curva
  );
  const servir =
    m.agua > 1
      ? tempServirIdeal(
          pac10,
          m.sng_lactose,
          m.agua,
          FRACAO_GELO_SERVIR,
          curva
        )
      : 0;

  return {
    linhas,
    totais: tot,
    metricas: m,
    arenosidade,
    ponto_congelamento: ponto,
    temp_servir: tempServir,
    fracao_congelada: congelada,
    temp_servir_ideal: servir,
    custo_kg: porKg(tot.custo),
  };
}

// ---------------------------------------------------------------------------
// Faixas alvo, conformidade, escalonamento
// ---------------------------------------------------------------------------
export function faixasAlvo(perfil, maquina) {
  const t = (maquina && maquina.ajuste_pac) || 0;
  const f = {};
  for (const [k, v] of Object.entries(perfil.faixas)) {
    f[k] = [v[0], v[1]];
  }
  const pac = perfil.faixas.pac;
  f.pac = [pac[0] + t, pac[1] + t];
  return f;
}

export function conformidade(metricas, faixas, constantes) {
  const params = [];
  for (const md of constantes.metricas) {
    const chave = md.chave;
    const v = metricas[chave] || 0;
    const [lo, hi] = faixas[chave];
    let st = "IDEAL";
    if (v < lo - 0.01) st = "ABAIXO";
    else if (v > hi + 0.01) st = "ACIMA";
    params.push({
      chave,
      rotulo: md.rotulo,
      unidade: md.unidade,
      casas: md.casas,
      valor: v,
      min: lo,
      max: hi,
      status: st,
      dica:
        st === "ABAIXO"
          ? md.dica_baixo
          : st === "ACIMA"
          ? md.dica_alto
          : null,
    });
  }
  const ideal = params.filter((p) => p.status === "IDEAL").length;
  return { parametros: params, ideal, total: params.length };
}

export function escalonar(
  itens,
  ingredientes,
  constantes,
  alvo,
  evaporada = 0
) {
  const v = Number(alvo);
  if (Number.isNaN(v) || v <= 0) {
    throw new Error("Informe um peso alvo válido maior que 0g.");
  }
  const total = avaliar(
    itens,
    ingredientes,
    constantes,
    TEMP_SERVIR_PADRAO,
    evaporada
  ).totais.gramas;
  if (total <= 0) {
    throw new Error(
      "Adicione ingredientes com peso maior que 0g antes de escalonar."
    );
  }
  const e = v / total;
  return itens.map((i) => ({
    ...i,
    gramas: Math.round(numero(i.gramas) * e * 10) / 10,
  }));
}

// ---------------------------------------------------------------------------
// Auto-balanceamento (Fc)
// ---------------------------------------------------------------------------
export function prepararObjetivo(itens, ingredientes, faixas, evaporada) {
  const coef = itens.map((item) => {
    const c = ingredientes[item.ingrediente];
    if (!c) return null;
    return [
      numCampo(c, "agua"),
      numCampo(c, "gordura"),
      numero(c.proteina),
      numCampo(c, "acucares"),
      numCampo(c, "sng"),
      numCampo(c, "outros_solidos"),
      sngPelaLactose(c),
      numCampo(c, "pod"),
      numCampo(c, "pac"),
    ];
  });
  const evap = numero(evaporada);
  const alvos = CHAVES_BALANCO.map((chave) => {
    const [g, c] = faixas[chave];
    const f = (g + c) / 2;
    const h = Math.max(
      (c - g) / 2,
      chave === "pod" || chave === "pac" ? 10 : 0.5
    );
    return [PESOS_BALANCO[chave], g, c, f, h];
  });

  return function objetivo(gramas) {
    let tg = 0,
      tw = 0,
      tf = 0,
      tp = 0,
      ts = 0,
      tm = 0,
      to = 0,
      tq = 0,
      tpod = 0,
      tpac = 0,
      tts = 0;
    for (let i = 0; i < gramas.length; i++) {
      const f = gramas[i];
      const cf = coef[i];
      tg += f;
      if (!cf) continue;
      const h = f / 100;
      const [w, fa, pr, su, ms, ot, eq, po, pa] = cf;
      const sfa = h * fa;
      const ssu = h * su;
      const sms = h * ms;
      const sot = h * ot;
      tw += h * w;
      tf += sfa;
      tp += h * pr;
      ts += ssu;
      tm += sms;
      to += sot;
      tq += h * eq;
      tpod += h * po;
      tpac += h * pa;
      tts += sfa + ssu + sms + sot;
    }
    const n = Math.max(0, Math.min(evap, tw));
    tg -= n;
    let mf = 0,
      mp = 0,
      ms_ = 0,
      mm = 0,
      mo = 0,
      mts = 0,
      mq = 0,
      mpod = 0,
      mpac = 0;
    if (tg > 0) {
      mf = (tf / tg) * 100;
      mp = (tp / tg) * 100;
      ms_ = (ts / tg) * 100;
      mm = (tm / tg) * 100;
      mo = (to / tg) * 100;
      mts = (tts / tg) * 100;
      mq = (tq / tg) * 100;
      mpod = (tpod / tg) * 1e3;
      mpac = (tpac / tg) * 1e3;
    }
    const lim = Math.max(0, (100 - (ms_ + mf + mo)) * 0.15);
    let y = 0;
    if (!(mq <= lim + 0.05)) {
      y += 30 * ((mq - lim) / 0.5) ** 2;
    }
    const vals = [mf, mp, ms_, mm, mo, mts, mpod, mpac];
    for (let i = 0; i < alvos.length; i++) {
      const [peso, g, c, f, h] = alvos[i];
      const s = vals[i];
      const p = (s - f) / h;
      y += peso * 0.15 * p * p;
      if (s < g) {
        y += peso * 10 * ((g - s) / h) ** 2;
      } else if (s > c) {
        y += peso * 10 * ((s - c) / h) ** 2;
      }
    }
    return y;
  };
}

export function balancear(
  itens,
  ingredientes,
  faixas,
  evaporada = 0,
  funcaoObjetivo = null
) {
  const lista = [...itens];
  const r = [];
  for (let i = 0; i < lista.length; i++) {
    if (!lista[i].travado && ingredientes[lista[i].ingrediente]) {
      r.push(i);
    }
  }
  if (r.length < 2) {
    return { sucesso: false, mensagem: MSG_POUCOS_DESTRAVADOS, itens: lista };
  }
  let massa = 0;
  for (const m of lista) massa += numero(m.gramas);
  if (massa <= 0) {
    return { sucesso: false, mensagem: MSG_MASSA_ZERO, itens: lista };
  }
  let u = lista.map((m) => Math.max(0, numero(m.gramas)));
  const d =
    funcaoObjetivo !== null
      ? funcaoObjetivo
      : prepararObjetivo(lista, ingredientes, faixas, evaporada);
  const inicial = d(u);
  let x = inicial;

  for (const passo of [
    massa * 0.05,
    massa * 0.02,
    massa * 0.008,
    massa * 0.002,
    0.5,
  ]) {
    let mudou = true;
    let cont = 0;
    while (mudou && cont < 80) {
      cont += 1;
      mudou = false;
      for (const y of r) {
        for (const mm of r) {
          if (y === mm || u[mm] < passo) continue;
          const g = u.slice();
          g[y] = u[y] + passo;
          g[mm] = u[mm] - passo;
          const c = d(g);
          if (c < x - 1e-9) {
            u = g;
            x = c;
            mudou = true;
          }
        }
      }
    }
  }

  u = u.map((v) => Math.round(v * 10) / 10);
  let soma = 0;
  for (const v of u) soma += v;
  const ajuste = Math.round((massa - soma) * 10) / 10;
  if (ajuste !== 0) {
    let m = r[0];
    for (const k of r) {
      if (u[k] > u[m]) m = k;
    }
    u[m] = Math.max(0, Math.round((u[m] + ajuste) * 10) / 10);
  }
  const novos = lista.map((item, idx) => ({ ...item, gramas: u[idx] }));
  const msg = x >= inicial - 1e-9 ? MSG_JA_OTIMO : MSG_AJUSTADA;
  return {
    sucesso: true,
    mensagem: msg,
    itens: novos,
    objetivo_inicial: inicial,
    objetivo_final: x,
  };
}

// ---------------------------------------------------------------------------
// Validação de ingrediente (Rl)
// ---------------------------------------------------------------------------
export function somaComposicao(e) {
  return (
    numero(e.agua) +
    numero(e.gordura) +
    numero(e.acucares) +
    numero(e.sng) +
    numero(e.outros_solidos) +
    numero(e.alcool)
  );
}

export function validarIngrediente(e, constantes) {
  const a = (n) => numero(e[n]);
  const fx = (v, casas = 1) => Number(v).toFixed(casas);
  const t = [];
  const o =
    a("agua") +
    a("gordura") +
    a("acucares") +
    a("sng") +
    a("outros_solidos") +
    a("alcool");
  if (Math.abs(o - 100) > 0.5) {
    t.push({
      nivel: "error",
      texto: `Água + gordura + açúcares + SNLG + outros sólidos + álcool soma ${fx(o)}%; precisa dar 100%.`,
    });
  }
  const r = a("sng");
  const lac = a("lactose");
  const u = a("proteina");
  if (lac > 0 && r <= 0) {
    t.push({
      nivel: "warn",
      texto:
        "Tem lactose mas o SNLG está zerado: a lactose faz parte do SNLG.",
    });
  }
  if (r > 0 && lac > 0.58 * r) {
    t.push({
      nivel: "warn",
      texto: `Lactose (${lac}%) passa de ~55% do SNLG (${r}%). No leite a lactose é ~54,5% do SNLG.`,
    });
  }
  if (r > 0 && lac > 0) {
    const n = (u + lac) / r;
    if (n > 1.02) {
      t.push({
        nivel: "warn",
        texto:
          "Proteína + lactose maior que o SNLG: algum desses valores está alto.",
      });
    } else if (n < 0.8) {
      t.push({
        nivel: "warn",
        texto: `SNLG alto para a proteína e a lactose informadas (no leite, proteína + lactose ≈ 90% do SNLG). Pela lactose, o SNLG seria ~${fx(lac / 0.545)}%.`,
      });
    }
  }
  if (e.pod_pac_auto) {
    const perfil = e.perfil_acucares || {};
    const somaGrupo = (grupo) => {
      let s = 0;
      for (const ac of constantes.acucares) {
        if (ac.grupo === grupo) s += numero(perfil[ac.chave]);
      }
      return s;
    };
    const i = somaGrupo("acucares");
    if (Math.abs(i - a("acucares")) > 1) {
      t.push({
        nivel: "warn",
        texto: `Os açúcares listados na composição somam ${fx(i)}%, mas o campo Açúcares diz ${a("acucares")}%.`,
      });
    }
    const x = somaGrupo("outros_solidos");
    if (x > a("outros_solidos") + 0.5) {
      t.push({
        nivel: "warn",
        texto: `Polióis, fibras, ácidos e sal somam ${fx(x)}%, mais que os outros sólidos (${a("outros_solidos")}%).`,
      });
    }
    if (somaGrupo("sng") + lac > a("sng") + 0.5) {
      t.push({
        nivel: "warn",
        texto: "Lactose + ácido lático passam do SNLG.",
      });
    }
  }
  if (a("acucares") + lac > 1 && a("pac") === 0 && a("pod") === 0) {
    t.push({
      nivel: "warn",
      texto: "Há açúcar, mas POD e PAC estão zerados.",
    });
  }
  if (a("acucares") > 5 && a("pac") < 0.3 * a("acucares")) {
    t.push({
      nivel: "warn",
      texto:
        "PAC muito baixo para a quantidade de açúcar (sacarose vale 1 por grama; maltodextrina ~0,34).",
    });
  }
  if (
    a("pac") > 0 &&
    a("acucares") + lac + a("outros_solidos") + a("alcool") === 0
  ) {
    t.push({
      nivel: "warn",
      texto:
        "PAC informado, mas não há açúcar, sólido ou álcool que o justifique.",
    });
  }
  return t;
}

// ---------------------------------------------------------------------------
// Novidades: Nutrição, Densidade, Pote, Brix, Alertas, Correções, Light
// ---------------------------------------------------------------------------
function mapaGruposAcucares(constantes) {
  const g = {};
  for (const a of constantes.acucares) g[a.chave] = a.grupo;
  return g;
}

export function kcal100g(ing, constantes, kNov) {
  if (ing.kcal_100g !== undefined && ing.kcal_100g !== null) {
    return numero(ing.kcal_100g);
  }
  const e = kNov.energia;
  const fat = e.por_acucar;
  const grupos = mapaGruposAcucares(constantes);
  const perfil = ing.perfil_acucares || {};
  const g = (c) => numero(ing[c]);
  const proteina = g("proteina");
  const sng = g("sng");
  const lactose = g("lactose");
  let kcal =
    g("gordura") * e.gordura +
    proteina * e.proteina +
    lactose * e.carboidrato +
    g("alcool") * e.alcool;
  const listado = { acucares: 0, outros_solidos: 0, sng: 0 };
  for (const [chave, val] of Object.entries(perfil)) {
    const v = numero(val);
    const grp = grupos[chave] || "outros_solidos";
    listado[grp] = (listado[grp] || 0) + v;
    kcal += v * (fat[chave] !== undefined ? fat[chave] : e.carboidrato);
  }
  kcal += Math.max(0, g("acucares") - listado.acucares) * e.carboidrato;
  const proteinaForaSng = Math.max(0, proteina - Math.max(0, sng - lactose));
  const fibra = g("fibra");
  const cinzas = g("cinzas");
  const resto = Math.max(
    0,
    g("outros_solidos") -
      listado.outros_solidos -
      proteinaForaSng -
      fibra -
      cinzas
  );
  kcal +=
    fibra * e.fibra +
    cinzas * e.cinzas +
    resto * e.outros_nao_especificados;
  return kcal;
}

export function caseina100g(ing, kNov) {
  if (ing.caseina !== undefined && ing.caseina !== null) {
    return numero(ing.caseina);
  }
  if (numero(ing.sng) > 0) {
    return numero(ing.proteina) * kNov.caseina_fracao_proteina_leite;
  }
  return 0;
}

export function densidade(metricas, kNov) {
  const d = kNov.densidade;
  const agua = metricas.agua || 0;
  const gord = metricas.gordura || 0;
  const alc = metricas.alcool || 0;
  const snf = Math.max(0, (metricas.solidos_totais || 0) - gord);
  const vol =
    agua / d.agua +
    gord / d.gordura +
    snf / d.solidos_nao_gordurosos +
    alc / d.alcool;
  return vol > 0 ? 100 / vol : 1.0;
}

export function potesMaquina(maquina) {
  return Array.isArray(maquina && maquina.potes) ? maquina.potes : [];
}

export function escolherPote(maquina, poteId = null) {
  const lista = potesMaquina(maquina);
  if (!lista.length) return null;
  if (!poteId) return lista[0];
  return (
    lista.find((p) => p.id === poteId) ||
    lista.find((p) => p.nome.toLowerCase().includes(String(poteId).toLowerCase())) ||
    lista[0]
  );
}

export function gramasPote(maquina, pote, rho) {
  return pote.volume_ml * numero(maquina.enchimento_max_fracao || 1) * rho;
}

export function infoPote(maquina, poteId, metricas, kNov) {
  const pote = escolherPote(maquina, poteId);
  if (!pote) return null;
  const rho = densidade(metricas, kNov);
  return {
    ...pote,
    densidade_g_ml: rho,
    enchimento_max_fracao: numero(maquina.enchimento_max_fracao || 1),
    gramas: gramasPote(maquina, pote, rho),
  };
}

export function ajustarBrix(ing, brix, constantes, kNov) {
  const b = numero(brix);
  if (!(b > 0 && b < 100)) {
    throw new Error(`Brix inválido para ${ing.id}: ${brix} (use 0–100)`);
  }
  const antigo = numero(ing.acucares);
  if (antigo <= 0) {
    throw new Error(
      `${ing.nome} não tem açúcares na composição: Brix não se aplica`
    );
  }
  const perfil = { ...(ing.perfil_acucares || {}) };
  const acidos = numero(perfil.acidos_fruta);
  const novo = Math.max(0, b - acidos);
  const delta = novo - antigo;
  const agua = numero(ing.agua) - delta;
  if (agua < 0) {
    throw new Error(
      `Brix ${br(b)} impossível para ${ing.nome}: não há água suficiente na composição`
    );
  }
  const f = novo / antigo;
  const grupos = mapaGruposAcucares(constantes);
  for (const [chave, v] of Object.entries(perfil)) {
    if (grupos[chave] === "acucares") {
      perfil[chave] = numero(v) * f;
    }
  }
  const out = {
    ...ing,
    acucares: novo,
    agua,
    perfil_acucares: perfil,
    brix: b,
  };
  if (out.pod_pac_auto) {
    Object.assign(out, podPacAutomatico(out, constantes));
  } else {
    out.pod = numero(ing.pod) * f;
    out.pac = numero(ing.pac) * f;
  }
  if (ing.kcal_100g !== undefined && ing.kcal_100g !== null) {
    out.kcal_100g = numero(ing.kcal_100g) + delta * kNov.energia.carboidrato;
  }
  return out;
}

export function aplicarBrix(ingredientes, itens, constantes, kNov) {
  const leituras = {};
  const erros = [];
  for (const it of itens) {
    if (it.brix === undefined || it.brix === null || it.brix === "") continue;
    const b = numero(it.brix);
    const iid = it.ingrediente;
    if (leituras[iid] !== undefined && leituras[iid] !== b) {
      erros.push(`Leituras de Brix diferentes para ${iid} na mesma receita.`);
      continue;
    }
    leituras[iid] = b;
  }
  const ids = Object.keys(leituras);
  if (!ids.length) return { ingredientes, ajustes: [], erros };
  const novo = { ...ingredientes };
  const ajustes = [];
  for (const iid of ids) {
    const b = leituras[iid];
    if (!novo[iid]) {
      erros.push(`Brix informado para ingrediente fora do banco: ${iid}`);
      continue;
    }
    try {
      const antes = novo[iid];
      const depois = ajustarBrix(antes, b, constantes, kNov);
      novo[iid] = depois;
      ajustes.push({
        ingrediente: iid,
        brix: b,
        acucares_antes: numero(antes.acucares),
        acucares_depois: depois.acucares,
        agua_antes: numero(antes.agua),
        agua_depois: depois.agua,
        pod: depois.pod,
        pac: depois.pac,
        texto: `${antes.nome}: Brix ${br(b)} → açúcares ${br(numero(antes.acucares))}% → ${br(depois.acucares)}%, água ${br(numero(antes.agua))}% → ${br(depois.agua)}%`,
      });
    } catch (err) {
      erros.push(err.message);
    }
  }
  return { ingredientes: novo, ajustes, erros };
}

export function calcularNutricao(
  z,
  ingredientes,
  constantes,
  kNov,
  porcaoG = null,
  poteG = null
) {
  const porcao =
    porcaoG !== null && porcaoG !== undefined
      ? numero(porcaoG)
      : kNov.porcao_padrao_g;
  const tol = {};
  for (const [c, v] of Object.entries(kNov.tolerancia_digestiva_g_porcao)) {
    if (!c.startsWith("_")) tol[c] = v;
  }
  let kcal = 0;
  let caseina = 0;
  const poliois = {};
  for (const c of Object.keys(tol)) poliois[c] = 0;
  let alulose = 0;

  for (const l of z.linhas) {
    const ing = l.conhecido ? ingredientes[l.ingrediente] : null;
    if (!ing) continue;
    const h = l.gramas / 100;
    kcal += h * kcal100g(ing, constantes, kNov);
    caseina += h * caseina100g(ing, kNov);
    const perfil = ing.perfil_acucares || {};
    for (const c of Object.keys(poliois)) {
      poliois[c] += h * numero(perfil[c]);
    }
    alulose += h * numero(perfil.alulose);
  }
  const t = z.totais;
  const peso = t.gramas;
  const polioisPos = {};
  for (const [c, v] of Object.entries(poliois)) {
    if (v > 0) polioisPos[c] = v;
  }
  const lote = {
    gramas: peso,
    kcal,
    proteina_g: t.proteina,
    gordura_g: t.gordura,
    acucares_g: Math.max(0, t.acucares + t.lactose - alulose),
    alcool_g: t.alcool,
    caseina_g: caseina,
    poliois_g: polioisPos,
  };

  const fatia = (g) => {
    const f = peso > 0 ? g / peso : 0;
    const out = {};
    for (const [c, v] of Object.entries(lote)) {
      if (c === "poliois_g") continue;
      out[c] = typeof v === "number" ? v * f : v;
    }
    out.gramas = g;
    out.poliois_g = {};
    for (const [c, v] of Object.entries(lote.poliois_g)) {
      out.poliois_g[c] = v * f;
    }
    return out;
  };

  const por100 = fatia(100);
  return {
    kcal_100g: por100.kcal,
    proteina_pct: por100.proteina_g,
    caseina_pct: por100.caseina_g,
    por_100g: por100,
    porcao: fatia(porcao),
    pote: poteG ? fatia(poteG) : null,
    lote,
  };
}

export function limiteEritritolPorcao(kNov, pesoKg = null) {
  const e = kNov.eritritol;
  const peso =
    pesoKg !== null && pesoKg !== undefined
      ? numero(pesoKg)
      : e.peso_kg_padrao;
  return e.ida_g_kg_dia * peso * e.fracao_ida_porcao;
}

function alertasEritritol(nutri, kNov, pesoKg) {
  const e = kNov.eritritol;
  const out = [];
  const onde = [];
  for (const [chave, rot] of [
    ["porcao", "na porção"],
    ["pote", "no pote"],
    ["lote", "no lote"],
  ]) {
    const fat = nutri[chave];
    const g = (fat && fat.poliois_g && fat.poliois_g.eritritol) || 0;
    if (fat && g >= e.alerta_forte_g) {
      onde.push(`${br(g, 1)} g ${rot} (${br(fat.gramas, 0)} g)`);
    }
  }
  if (onde.length) {
    out.push({
      codigo: "eritritol_30g",
      nivel: "forte",
      texto: `ATENÇÃO: eritritol ≥ ${br(e.alerta_forte_g, 0)} g: ${onde.join("; ")}. É a dose que aumentou a reatividade das plaquetas em estudo de intervenção (Nature Medicine 2023; replicado em 2024). Associação, não causalidade provada; evite se tiver risco cardiovascular e prefira alulose.`,
    });
  }
  const lim = limiteEritritolPorcao(kNov, pesoKg);
  const gp = (nutri.porcao.poliois_g && nutri.porcao.poliois_g.eritritol) || 0;
  if (gp > lim) {
    const peso =
      pesoKg !== null && pesoKg !== undefined
        ? numero(pesoKg)
        : e.peso_kg_padrao;
    out.push({
      codigo: "eritritol_ida",
      nivel: "warn",
      texto: `Eritritol na porção: ${br(gp, 1)} g, mais de 1/3 da ingestão diária aceitável da EFSA (0,5 g/kg/dia → ${br(lim, 1)} g por porção para ${br(peso, 0)} kg). Reduza a porção ou troque parte por alulose.`,
    });
  }
  return out;
}

export function calcularAlertas(
  z,
  ingredientes,
  nutri,
  kNov,
  processo = null,
  pesoKg = null
) {
  const lim = kNov.limites;
  const tol = {};
  for (const [c, v] of Object.entries(kNov.tolerancia_digestiva_g_porcao)) {
    if (!c.startsWith("_")) tol[c] = v;
  }
  const out = [];
  const peso = z.totais.gramas;
  const m = z.metricas;

  for (const l of z.linhas) {
    const ing = l.conhecido ? ingredientes[l.ingrediente] : null;
    if (!ing || l.gramas <= 0) continue;
    const dmax = ing.dose_max_pct;
    if (dmax !== undefined && dmax !== null && peso > 0) {
      const pct = (l.gramas / peso) * 100;
      if (pct > numero(dmax) + 1e-9) {
        const defeito = ing.defeito_excesso || "textura estranha";
        out.push({
          codigo: "dose_maxima",
          nivel: "warn",
          ingrediente: ing.id,
          texto: `${ing.nome}: ${br(pct, 2)}% da calda passa da dose máxima de ${br(numero(dmax), 2)}% (≈ ${br((numero(dmax) * peso) / 100, 1)} g neste lote). Em excesso fica ${defeito}.`,
        });
      }
    }
    if (processo === "frio" && ing.ativacao === "quente") {
      out.push({
        codigo: "ativacao",
        nivel: "warn",
        ingrediente: ing.id,
        texto: `${ing.nome} só hidrata a quente (~80 °C), mas o processo é a frio: aqueça a calda ou troque por um estabilizante de ativação a frio (guar, xantana).`,
      });
    }
  }

  const erit =
    (nutri.por_100g.poliois_g && nutri.por_100g.poliois_g.eritritol) || 0;
  if (erit > lim.eritritol_pct_max) {
    out.push({
      codigo: "eritritol_cristaliza",
      nivel: "warn",
      texto: `Eritritol a ${br(erit, 1)}% da calda (acima de ~${br(lim.eritritol_pct_max, 0)}%): pouco solúvel no frio, recristaliza e deixa a massa arenosa e dura, apesar do PAC teórico alto. Troque parte por alulose.`,
    });
  }

  out.push(...alertasEritritol(nutri, kNov, pesoKg));

  const cas = nutri.caseina_pct;
  if (cas > lim.caseina_pct_max) {
    out.push({
      codigo: "caseina_alta",
      nivel: "warn",
      texto: `Caseína ~${br(cas, 1)}% da calda (acima de ~${br(lim.caseina_pct_max, 0)}%, heurística): a massa tende a ficar pastosa/borrachuda. Troque parte da proteína por whey isolado.`,
    });
  }

  if (peso > 0 && m.solidos_totais < lim.solidos_totais_min_pct) {
    out.push({
      codigo: "agua_livre",
      nivel: "warn",
      texto: `Sólidos totais ${br(m.solidos_totais, 1)}% (água ${br(m.agua, 1)}%): muita água livre, tende a cristais grandes de gelo (textura de raspadinha). Suba sólidos (proteína, fibras, oleaginosas, alulose) ou, no Creami, faça Re-spin com 1 colher de leite.`,
    });
  }

  for (const [chave, rot] of [
    ["porcao", "porção"],
    ["pote", "pote inteiro"],
  ]) {
    const fat = nutri[chave];
    if (!fat) continue;
    const pol = fat.poliois_g || {};
    let soma = 0;
    for (const c of Object.keys(tol)) {
      soma += (pol[c] || 0) / tol[c];
    }
    if (soma >= 1) {
      const partes = Object.entries(pol)
        .filter(([, g]) => g > 0.05)
        .map(([c, g]) => `${br(g, 1)} g de ${c}`)
        .join(", ");
      out.push({
        codigo: `tolerancia_digestiva_${chave}`,
        nivel: "warn",
        texto: `Na ${rot} (${br(fat.gramas, 0)} g): ${partes}. Acima da dose que costuma ser bem tolerada de uma vez (gases, inchaço, efeito laxativo); reduza ou sirva porções menores.`,
      });
      break;
    }
  }

  return out;
}

function conteudoIng(ing, chave) {
  if (chave === "solidos_totais") {
    return (
      numero(ing.gordura) +
      numero(ing.acucares) +
      numero(ing.sng) +
      numero(ing.outros_solidos)
    );
  }
  return numero(ing[chave]);
}

export function calcularCorrecoes(
  z,
  itens,
  ingredientes,
  faixas,
  conf,
  temp,
  evaporada,
  constantes,
  kNov
) {
  const cand = kNov.correcoes;
  const t = z.totais;
  const G = t.gramas;
  const out = [];
  if (G <= 0) return out;
  const kcal0 = calcularNutricao(z, ingredientes, constantes, kNov).kcal_100g;

  for (const p of conf.parametros) {
    const chave = p.chave;
    const st = p.status;
    const ids = cand[chave] && cand[chave][st];
    if (st === "IDEAL" || !ids) continue;
    const lo = p.min;
    const hi = p.max;
    const alvo =
      st === "ABAIXO" ? lo + (hi - lo) * 0.25 : hi - (hi - lo) * 0.25;
    const escala = chave === "pod" || chave === "pac" ? 1000 : 100;
    for (const iid of ids) {
      const ing = ingredientes[iid];
      if (!ing) continue;
      const c = conteudoIng(ing, chave);
      const den = (c * escala) / 100 - alvo;
      if (den === 0) continue;
      let x = (alvo * G - t[chave] * escala) / den;
      if (!(x > 0) || x > 2 * G) continue;
      x = Math.round(x * 10) / 10;
      const novos = [
        ...itens.map((i) => ({ ...i })),
        { ingrediente: iid, gramas: x, travado: false },
      ];
      const z2 = avaliar(novos, ingredientes, constantes, temp, evaporada);
      const conf2 = conformidade(z2.metricas, faixas, constantes);
      if (conf2.ideal < conf.ideal) continue;
      out.push({
        metrica: chave,
        rotulo: p.rotulo,
        status: st,
        valor: p.valor,
        alvo,
        ingrediente: iid,
        nome: ing.nome,
        gramas: x,
        valor_depois: z2.metricas[chave],
        faixa_verde_depois: `${conf2.ideal}/${conf2.total}`,
        kcal_100g_antes: kcal0,
        kcal_100g_depois: calcularNutricao(z2, ingredientes, constantes, kNov)
          .kcal_100g,
      });
    }
  }
  return out;
}

export function temChocolate(itens, ingredientes) {
  return itens.some((i) => {
    const ing = ingredientes[i.ingrediente];
    return (
      ing &&
      (ing.categoria === "Chocolates" ||
        String(ing.nome || "").toLowerCase().includes("chocolate"))
    );
  });
}

export function lembretesProcesso(maquina, itens, ingredientes, kNov) {
  const lp = kNov.lembretes_processo;
  const out = [...lp.geral];
  const creami = potesMaquina(maquina).length > 0;
  if (creami) out.push(...lp.creami);
  if (creami || temChocolate(itens, ingredientes)) out.push(lp.chocolate);
  return out;
}

export function orientacoesMaquina(maquina) {
  const out = [];
  for (const p of potesMaquina(maquina)) {
    out.push(`${p.nome}: até a linha MAX (~${p.volume_ml} ml).`);
  }
  if (maquina.temp_freezer_c !== undefined && maquina.temp_freezer_c !== null) {
    out.push(`Freezer a ${maquina.temp_freezer_c} °C ou mais frio.`);
  }
  if (maquina.congelamento_h) {
    out.push(
      `Congelar por pelo menos ${maquina.congelamento_h.minimo} h; ~${maquina.congelamento_h.base_aquecida} h se a base foi aquecida.`
    );
  }
  if (Array.isArray(maquina.orientacoes)) {
    out.push(...maquina.orientacoes);
  }
  return out;
}

export function comparacaoClassica(z, perfil, maquina, mapaPerfis, constantes) {
  const refId = perfil.referencia_classica;
  if (!refId || !mapaPerfis[refId]) return null;
  const ref = mapaPerfis[refId];
  const conf = conformidade(
    z.metricas,
    faixasAlvo(ref, maquina),
    constantes
  );
  return {
    perfil: ref.id,
    nome: ref.nome,
    ideal: conf.ideal,
    total: conf.total,
    fora: conf.parametros
      .filter((p) => p.status !== "IDEAL")
      .map((p) => ({
        chave: p.chave,
        rotulo: p.rotulo,
        unidade: p.unidade,
        casas: p.casas,
        valor: p.valor,
        min: p.min,
        max: p.max,
        status: p.status,
      })),
  };
}

export function objetivoLight(
  itens,
  ingredientes,
  faixas,
  constantes,
  kNov,
  evaporada = 0,
  proteinaMin = null,
  porcaoG = null,
  pesoKg = null
) {
  const cfg = kNov.light;
  const fx = {};
  for (const [c, v] of Object.entries(faixas)) fx[c] = [v[0], v[1]];
  let pmin = null;
  if (proteinaMin !== null && proteinaMin !== undefined && proteinaMin !== "") {
    pmin = numero(proteinaMin);
    const [lo, hi] = fx.proteina;
    fx.proteina = [Math.max(lo, pmin), Math.max(hi, pmin)];
  }
  const base = prepararObjetivo(itens, ingredientes, fx, evaporada);
  const coef = itens.map((item) => {
    const c = ingredientes[item.ingrediente];
    if (!c) return null;
    const st =
      numero(c.gordura) +
      numero(c.acucares) +
      numero(c.sng) +
      numero(c.outros_solidos);
    return {
      agua: numero(c.agua),
      kcal: kcal100g(c, constantes, kNov),
      erit: numero((c.perfil_acucares || {}).eritritol),
      v: [
        numero(c.gordura),
        numero(c.proteina),
        numero(c.acucares),
        numero(c.sng),
        numero(c.outros_solidos),
        st,
        numero(c.pod),
        numero(c.pac),
      ],
    };
  });
  const alvos = CHAVES_BALANCO.map((chave) => {
    const [lo, hi] = fx[chave];
    const h = Math.max(
      (hi - lo) / 2,
      chave === "pod" || chave === "pac" ? 10 : 0.5
    );
    return [
      PESOS_BALANCO[chave],
      lo,
      hi,
      h,
      chave === "pod" || chave === "pac" ? 1e3 : 100,
    ];
  });
  const evap = numero(evaporada);
  const extraFaixa = cfg.fator_fora_da_faixa - 1;
  const porcao =
    porcaoG !== null && porcaoG !== undefined
      ? numero(porcaoG)
      : kNov.porcao_padrao_g;
  const tetoErit = limiteEritritolPorcao(kNov, pesoKg);

  const medir = (gramas) => {
    let tg = 0,
      tw = 0,
      tk = 0,
      te = 0;
    const tv = [0, 0, 0, 0, 0, 0, 0, 0];
    for (let i = 0; i < gramas.length; i++) {
      const f = gramas[i];
      const c = coef[i];
      tg += f;
      if (!c) continue;
      const h = f / 100;
      tw += h * c.agua;
      tk += h * c.kcal;
      te += h * c.erit;
      for (let j = 0; j < 8; j++) tv[j] += h * c.v[j];
    }
    tg -= Math.max(0, Math.min(evap, tw));
    return [tg, tk, tv, te];
  };

  const [g0, k0] = medir(itens.map((i) => Math.max(0, numero(i.gramas))));
  const kcalRef = g0 > 0 && k0 > 0 ? (k0 / g0) * 100 : 1.0;

  const objetivo = (gramas) => {
    let y = base(gramas);
    const [tg, tk, tv, te] = medir(gramas);
    if (tg <= 0) return y;
    for (let i = 0; i < alvos.length; i++) {
      const [peso, lo, hi, h, esc] = alvos[i];
      const s = (tv[i] / tg) * esc;
      if (s < lo) {
        y += extraFaixa * peso * 10 * ((lo - s) / h) ** 2;
      } else if (s > hi) {
        y += extraFaixa * peso * 10 * ((s - hi) / h) ** 2;
      }
    }
    y += (cfg.peso_kcal * ((tk / tg) * 100)) / kcalRef;
    if (pmin !== null) {
      const mp = (tv[1] / tg) * 100;
      if (mp < pmin) {
        const d = (pmin - mp) / 0.5;
        y += cfg.peso_proteina_min * (d + d * d);
      }
    }
    if (te > 0) {
      y += cfg.peso_preferencia_eritritol * ((te / tg) * 100);
      const naPorcao = (te / tg) * porcao;
      if (naPorcao > tetoErit) {
        const excesso = naPorcao - tetoErit;
        y += cfg.peso_teto_eritritol * (excesso + excesso * excesso);
      }
    }
    return y;
  };

  return { objetivo, faixasEfetivas: fx };
}

// ---------------------------------------------------------------------------
// Análise completa (equivalente a relatorio.analisar)
// ---------------------------------------------------------------------------
export function analisarReceita(receita, catalogo, opcoes = {}) {
  const { constantes, constantesNov: kNov, mapaPerfis, mapaMaquinas } = catalogo;
  const maquina =
    opcoes.maquina ||
    mapaMaquinas[receita.maquina] ||
    catalogo.maquinas[0];
  const perfil =
    opcoes.perfil ||
    mapaPerfis[receita.perfil] ||
    catalogo.perfis[0];
  const evap =
    opcoes.evaporada !== undefined
      ? numero(opcoes.evaporada)
      : numero(receita.evaporada_g);
  const processo =
    opcoes.processo !== undefined ? opcoes.processo : receita.processo || null;
  const porcaoG = opcoes.porcaoG ?? null;
  const poteId = opcoes.poteId ?? null;
  const pesoKg = opcoes.pesoKg ?? null;

  const {
    ingredientes: ingsEfetivos,
    ajustes: ajustesBrix,
    erros: errosBrix,
  } = aplicarBrix(catalogo.mapaIngredientes, receita.itens, constantes, kNov);

  const z = avaliar(
    receita.itens,
    ingsEfetivos,
    constantes,
    maquina.temp_servir,
    evap
  );
  const faixas = faixasAlvo(perfil, maquina);
  const conf = conformidade(z.metricas, faixas, constantes);
  const pote =
    z.totais.gramas > 0 ? infoPote(maquina, poteId, z.metricas, kNov) : null;
  const nutri = calcularNutricao(
    z,
    ingsEfetivos,
    constantes,
    kNov,
    porcaoG,
    pote ? pote.gramas : null
  );
  const alertas = calcularAlertas(
    z,
    ingsEfetivos,
    nutri,
    kNov,
    processo,
    pesoKg
  );
  const correcoes = calcularCorrecoes(
    z,
    receita.itens,
    ingsEfetivos,
    faixas,
    conf,
    maquina.temp_servir,
    evap,
    constantes,
    kNov
  );
  const totalG = z.totais.gramas || 1;
  const linhas = z.linhas.map((l) => ({
    ...l,
    travado: Boolean(l.travado),
    pct: (l.gramas / totalG) * 100,
  }));

  return {
    receita,
    maquina,
    perfil,
    faixas,
    ingredientesEfetivos: ingsEfetivos,
    linhas,
    totais: z.totais,
    metricas: z.metricas,
    conformidade: conf,
    arenosidade: z.arenosidade,
    ponto_congelamento_c: z.ponto_congelamento,
    temp_servir_maquina_c: z.temp_servir,
    fracao_agua_congelada_na_maquina: z.fracao_congelada,
    temp_servir_ideal_c: z.temp_servir_ideal,
    custo: { por_kg: z.custo_kg, lote: z.totais.custo },
    comparacao_classica: comparacaoClassica(
      z,
      perfil,
      maquina,
      mapaPerfis,
      constantes
    ),
    processo,
    pote,
    nutricao: nutri,
    alertas,
    limite_eritritol_porcao_g: limiteEritritolPorcao(kNov, pesoKg),
    correcoes,
    lembretes: lembretesProcesso(maquina, receita.itens, ingsEfetivos, kNov),
    orientacoes_maquina: orientacoesMaquina(maquina),
    ajustes_brix: ajustesBrix,
    erros_brix: errosBrix,
    curva_pontos: amostrarCurvaCongelamento(
      z.metricas,
      constantes.curva_congelamento
    ),
  };
}

// ---------------------------------------------------------------------------
// Normalização de receita (aceita formato PT e formato original EN)
// ---------------------------------------------------------------------------
export function normalizarReceita(r, constantes) {
  const itensBrutos = r.itens || r.items || [];
  const itens = itensBrutos.map((i) => {
    const item = {
      ingrediente: i.ingrediente ?? i.ingredientId,
      gramas: numero(i.gramas ?? i.grams ?? 0),
      travado: Boolean(i.travado ?? i.locked ?? false),
    };
    if (i.brix !== undefined && i.brix !== null && i.brix !== "") {
      item.brix = numero(i.brix);
    }
    return item;
  });
  const out = {
    id: r.id || null,
    nome: r.nome || r.name || "Receita Sem Nome",
    versao: r.versao || r.version || "V1.0",
    perfil: r.perfil || r.familyId || null,
    maquina: r.maquina || r.machineId || null,
    status: r.status || "Em Teste",
    notas: r.notas ?? r.notes ?? "",
    atualizada_em: r.atualizada_em || r.updatedAt || null,
    evaporada_g: numero(r.evaporada_g ?? r.evaporation ?? 0),
    processo:
      r.processo === "frio" || r.processo === "quente" ? r.processo : null,
    itens,
  };
  const soma = itens.reduce((acc, i) => acc + numero(i.gramas), 0);
  out.lote_g = r.lote_g != null ? numero(r.lote_g) : Math.round(soma) || 1000;

  // Substituições de ingredientes removidos
  const subs = (constantes && constantes.substituicoes) || {};
  const avisos = [];
  for (const item of out.itens) {
    const s = subs[item.ingrediente];
    if (s) {
      const novo = Math.round(numero(item.gramas) * s.fator * 10) / 10;
      avisos.push(
        `${item.ingrediente} trocado por ${s.para} (${item.gramas} g → ${novo} g): ${s.motivo}`
      );
      item.ingrediente = s.para;
      item.gramas = novo;
    }
  }
  return { receita: out, avisos };
}

export function paraArquivoReceita(r) {
  const out = {};
  for (const k of [
    "id",
    "nome",
    "versao",
    "perfil",
    "maquina",
    "status",
    "notas",
    "atualizada_em",
    "lote_g",
    "evaporada_g",
  ]) {
    if (r[k] !== undefined && r[k] !== null && r[k] !== "") {
      out[k] = r[k];
    }
  }
  if (r.processo === "frio" || r.processo === "quente") {
    out.processo = r.processo;
  }
  out.itens = r.itens.map((i) => {
    const it = {
      ingrediente: i.ingrediente,
      gramas: numero(i.gramas),
      travado: Boolean(i.travado),
    };
    if (i.brix !== undefined && i.brix !== null && i.brix !== "") {
      it.brix = numero(i.brix);
    }
    return it;
  });
  return out;
}

// ---------------------------------------------------------------------------
// Formatação de texto e Markdown (ficha.py + nutricao.py)
// ---------------------------------------------------------------------------
export function linhaComparacao(c) {
  const partes = c.fora.map(
    (p) =>
      `${p.rotulo} ${br(p.valor, p.casas)} (faixa ${br(p.min, p.casas)}–${br(p.max, p.casas)})`
  );
  return (
    `Pelos padrões de ${c.nome}: faixa verde ${c.ideal}/${c.total}` +
    (partes.length ? `. Fora: ${partes.join("; ")}.` : ".")
  );
}

export function linhasNutricao(n, pote, limiteEritritol) {
  const fx = (f) =>
    `${br(f.kcal, 0)} kcal · ${br(f.proteina_g, 1)} g proteína · ${br(f.gordura_g, 1)} g gordura · ${br(f.acucares_g, 1)} g açúcares`;
  const out = [
    `${br(n.kcal_100g, 0)} kcal/100 g · proteína ${br(n.proteina_pct, 1)}%`,
    `Porção de ${br(n.porcao.gramas, 0)} g: ${fx(n.porcao)}`,
  ];
  if (n.pote && pote) {
    out.push(
      `${pote.nome.split(" (")[0]} (~${br(pote.gramas, 0)} g): ${fx(n.pote)}`
    );
  }
  out.push(`Lote (${br(n.lote.gramas, 0)} g): ${fx(n.lote)}`);
  const pol = n.porcao.poliois_g || {};
  if (Object.values(pol).some((v) => v > 0.05)) {
    const txt = Object.entries(pol)
      .filter(([, v]) => v > 0.05)
      .map(([c, v]) => `${br(v, 1)} g de ${c}`)
      .join(", ");
    out.push(`Polióis/alulose/fibras na porção: ${txt}`);
  }
  const erit = (n.lote.poliois_g && n.lote.poliois_g.eritritol) || 0;
  if (erit > 0) {
    const eritPote =
      n.pote && n.pote.poliois_g && n.pote.poliois_g.eritritol
        ? ` · ${br(n.pote.poliois_g.eritritol, 1)} g no pote`
        : "";
    out.push(
      `Eritritol: ${br(pol.eritritol || 0, 1)} g por porção (teto sugerido ${br(limiteEritritol, 1)} g = 1/3 da IDA da EFSA) · ${br(erit, 1)} g no lote${eritPote}`
    );
  }
  return out;
}

export function linhaCorrecao(c) {
  const st = c.status === "ABAIXO" ? "abaixo" : "acima";
  const casas = c.metrica === "pod" || c.metrica === "pac" ? 0 : 1;
  return `${c.rotulo} ${br(c.valor, casas)} (${st} da faixa): +${br(c.gramas, 1)} g de ${c.nome} → ${br(c.valor_depois, casas)}, faixa verde ${c.faixa_verde_depois}, ${br(c.kcal_100g_antes, 0)} → ${br(c.kcal_100g_depois, 0)} kcal/100 g`;
}

export function gerarFichaTexto(analise, constantes) {
  const { receita: r, perfil, maquina, totais, metricas, faixas } = analise;
  const linhas = [
    `${r.nome} (${r.versao}) — ${perfil.nome} — ${maquina.nome}`,
    ["Ingrediente", "g", "%"].join("\t"),
  ];
  const e = totais.gramas || 1;
  for (const row of analise.linhas) {
    if (row.conhecido) {
      linhas.push(
        [row.nome, br(row.gramas), br((row.gramas / e) * 100)].join("\t")
      );
    }
  }
  linhas.push(["TOTAL", br(totais.gramas), "100"].join("\t"));
  linhas.push("");
  for (const md of constantes.metricas) {
    const v = metricas[md.chave];
    const [lo, hi] = faixas[md.chave];
    const c = md.casas;
    linhas.push(
      [
        md.rotulo,
        `${br(v, c)} ${md.unidade}`,
        `faixa ${br(lo, c)}–${br(hi, c)}`,
      ].join("\t")
    );
  }
  if (totais.evaporada > 0) {
    linhas.push(
      `Água evaporada no cozimento\t${br(totais.evaporada)} g (peso final ${br(totais.gramas)} g)`
    );
  }
  linhas.push(
    `SNLG pela lactose (arenosidade)\t${br(analise.arenosidade.valor)}%\tlimite ${br(analise.arenosidade.maximo)}%`
  );
  linhas.push(
    `Ponto de congelamento\t${br(analise.ponto_congelamento_c)} °C`
  );
  linhas.push(
    `Servir a (~72% da água congelada)\t${br(analise.temp_servir_ideal_c)} °C`
  );
  linhas.push(`Custo\tR$ ${br(analise.custo.por_kg, 2)}/kg`);
  return linhas.join("\n");
}

export function gerarFichaMarkdown(analise) {
  const { receita: r, perfil, maquina, totais, conformidade: conf } = analise;
  const mdCel = (s) => String(s).replace(/\|/g, "\\|");
  const out = [
    `# ${r.nome} (${r.versao})`,
    "",
    `- **Perfil:** ${perfil.nome}`,
    `- **Máquina:** ${maquina.nome}`,
    `- **Faixa verde:** ${conf.ideal}/${conf.total} parâmetros`,
  ];
  if (r.notas) out.push(`- **Notas:** ${r.notas}`);
  out.push("", "## Ingredientes", "", "| Ingrediente | g | % |", "|---|---:|---:|");
  const e = totais.gramas || 1;
  for (const row of analise.linhas) {
    if (row.conhecido) {
      out.push(
        `| ${mdCel(row.nome)} | ${br(row.gramas)} | ${br((row.gramas / e) * 100)} |`
      );
    }
  }
  out.push(`| **TOTAL** | **${br(totais.gramas)}** | **100** |`);

  out.push(
    "",
    "## Balanceamento",
    "",
    "| Parâmetro | Valor | Faixa | Status |",
    "|---|---:|---:|---|"
  );
  const stMap = { IDEAL: "ok", ABAIXO: "abaixo", ACIMA: "acima" };
  for (const p of conf.parametros) {
    const c = p.casas;
    out.push(
      `| ${p.rotulo} | ${br(p.valor, c)} ${p.unidade} | ${br(p.min, c)}–${br(p.max, c)} | ${stMap[p.status]} |`
    );
  }
  out.push("", "## Congelamento, arenosidade e custo", "");
  if (totais.evaporada > 0) {
    out.push(
      `- **Água evaporada no cozimento:** ${br(totais.evaporada)} g (peso final ${br(totais.gramas)} g)`
    );
  }
  const a = analise.arenosidade;
  out.push(
    `- **SNLG pela lactose (arenosidade):** ${br(a.valor)}% · limite ${br(a.maximo)}%` +
      (a.ok ? "" : " — **risco de arenosidade**")
  );
  out.push(`- **Ponto de congelamento:** ${br(analise.ponto_congelamento_c)} °C`);
  out.push(
    `- **Servir a (~72% da água congelada):** ${br(analise.temp_servir_ideal_c)} °C`
  );
  out.push(`- **Custo:** R$ ${br(analise.custo.por_kg, 2)}/kg`);

  const dicas = conf.parametros.filter((p) => p.dica);
  if (dicas.length) {
    out.push("", "## Ajustes sugeridos", "");
    for (const p of dicas) {
      out.push(
        `- **${p.rotulo}** (${p.status === "ABAIXO" ? "abaixo" : "acima"}): ${p.dica}`
      );
    }
  }
  if (analise.comparacao_classica) {
    out.push(
      "",
      "## Comparação com o padrão clássico",
      "",
      linhaComparacao(analise.comparacao_classica),
      "",
      "Estilo 'fit': no Creami a lâmina compensa o PAC baixo; em vitrine ficaria duro e cristalino."
    );
  }
  out.push("", "## Nutrição (estimativa)", "");
  for (const l of linhasNutricao(
    analise.nutricao,
    analise.pote,
    analise.limite_eritritol_porcao_g
  )) {
    out.push(`- ${l}`);
  }
  if (analise.alertas.length) {
    out.push("", "## Alertas", "");
    for (const al of analise.alertas) {
      out.push(
        `- ${al.nivel === "forte" ? `**${al.texto}**` : al.texto}`
      );
    }
  }
  if (analise.correcoes.length) {
    out.push("", "## Correções de um ingrediente (estimativa)", "");
    for (const c of analise.correcoes) {
      out.push(`- ${linhaCorrecao(c)}`);
    }
  }
  if (analise.orientacoes_maquina.length) {
    out.push("", "## Máquina", "");
    if (analise.pote) {
      const p = analise.pote;
      out.push(
        `- **Pote:** ${p.nome}: ~${br(p.gramas, 0)} g de calda (${br(p.volume_ml * p.enchimento_max_fracao, 0)} ml × ${br(p.densidade_g_ml, 2)} g/ml)`
      );
    }
    for (const o of analise.orientacoes_maquina) out.push(`- ${o}`);
  }
  if (analise.lembretes.length) {
    out.push("", "## Lembretes de processo", "");
    for (const l of analise.lembretes) out.push(`- [ ] ${l}`);
  }
  return out.join("\n") + "\n";
}
