/**
 * Calda Certa — Aplicação Web Interativa
 *
 * Roda 100% no navegador sobre ``engine.js`` e ``data/bundle.json``, com
 * persistência local em ``localStorage`` para receitas e ingredientes do usuário.
 */

import * as eng from "./engine.js";

const STORAGE_KEY = "calda_certa_state_v1";
const LIGHT_EXTRAS = [
  { id: "ing_alulose", rotulo: "Alulose" },
  { id: "ing_polidextrose", rotulo: "Polidextrose" },
  { id: "ing_inulina", rotulo: "Inulina" },
  { id: "ing_whey_iso", rotulo: "Whey Isolado" },
  { id: "ing_leite_po_desn", rotulo: "Leite em Pó Desnatado" },
];

const state = {
  bundle: null,
  catalogo: null,
  custom: {
    receitas: [],
    ingredientes: [],
  },
  receita: null,
  poteId: null,
  porcaoG: 100,
  pesoKg: 70,
  lightExtras: new Set(),
  undoStack: [],
  activeView: "bancada",
  fichaTab: "md",
  checkedLembretes: new Set(),
  comboHighlight: 0,
  comboResults: [],
  analiseAtual: null,
};

// ---------------------------------------------------------------------------
// Utilitários de DOM e formatação
// ---------------------------------------------------------------------------
const $ = (id) => document.getElementById(id);

function esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function slug(s) {
  return String(s || "item")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_|_$/g, "")
    .slice(0, 40) || "item";
}

let toastTimer = null;
function showToast(msg) {
  const el = $("toast");
  el.textContent = msg;
  el.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), 3200);
}

function cloneRecipe(r) {
  return JSON.parse(JSON.stringify(r));
}

function pushUndo() {
  if (!state.receita) return;
  state.undoStack.push(cloneRecipe(state.receita));
  if (state.undoStack.length > 30) state.undoStack.shift();
  $("btn-desfazer").disabled = state.undoStack.length === 0;
}

// ---------------------------------------------------------------------------
// Persistência (localStorage + Tema)
// ---------------------------------------------------------------------------
function loadSavedState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function persistState() {
  try {
    const payload = {
      custom: state.custom,
      receita: state.receita,
      poteId: state.poteId,
      porcaoG: state.porcaoG,
      pesoKg: state.pesoKg,
      theme: document.documentElement.dataset.theme || "light",
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  } catch {
    // quota ou modo privado
  }
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  const icon = $("icon-theme");
  if (theme === "dark") {
    icon.innerHTML =
      '<circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>';
  } else {
    icon.innerHTML =
      '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>';
  }
}

// ---------------------------------------------------------------------------
// Inicialização
// ---------------------------------------------------------------------------
async function init() {
  const saved = loadSavedState();
  const prefersDark =
    window.matchMedia &&
    window.matchMedia("(prefers-color-scheme: dark)").matches;
  applyTheme((saved && saved.theme) || (prefersDark ? "dark" : "light"));

  const resp = await fetch("./data/bundle.json");
  if (!resp.ok) throw new Error("Não foi possível carregar data/bundle.json");
  state.bundle = await resp.json();

  if (saved && saved.custom) {
    state.custom = {
      receitas: Array.isArray(saved.custom.receitas)
        ? saved.custom.receitas
        : [],
      ingredientes: Array.isArray(saved.custom.ingredientes)
        ? saved.custom.ingredientes
        : [],
    };
  }
  if (saved && saved.porcaoG) state.porcaoG = eng.numero(saved.porcaoG) || 100;
  if (saved && saved.pesoKg) state.pesoKg = eng.numero(saved.pesoKg) || 70;
  if (saved && saved.poteId) state.poteId = saved.poteId;

  rebuildCatalog();

  if (saved && saved.receita && Array.isArray(saved.receita.itens)) {
    state.receita = eng.normalizarReceita(
      saved.receita,
      state.catalogo.constantes
    ).receita;
  } else {
    const inicial =
      state.catalogo.receitas.find((r) => r.id === "rec_fiordilatte") ||
      state.catalogo.receitas[0];
    state.receita = cloneRecipe(inicial);
  }

  $("inp-porcao-g").value = state.porcaoG;
  $("inp-peso-kg").value = state.pesoKg;

  populateStaticSelectors();
  renderLightChips();
  bindEvents();
  syncRecipeHeaderInputs();
  renderAll();
}

function rebuildCatalog() {
  state.catalogo = eng.construirCatalogo(state.bundle, state.custom);
  $("count-receitas").textContent = String(state.catalogo.receitas.length);
  $("count-ingredientes").textContent = String(
    state.catalogo.ingredientes.length
  );
}

function populateStaticSelectors() {
  const { perfis, maquinas, ingredientes, constantes } = state.catalogo;

  // Perfis agrupados
  const selPerfil = $("sel-perfil");
  const filtroPerfil = $("rec-filtro-perfil");
  selPerfil.innerHTML = "";
  filtroPerfil.innerHTML = '<option value="">Todos os perfis</option>';
  const grupos = new Map();
  for (const p of perfis) {
    const g = p.grupo || "Outros";
    if (!grupos.has(g)) grupos.set(g, []);
    grupos.get(g).push(p);
  }
  for (const [grupo, lista] of grupos.entries()) {
    const og1 = document.createElement("optgroup");
    og1.label = grupo;
    const og2 = document.createElement("optgroup");
    og2.label = grupo;
    for (const p of lista) {
      const o1 = document.createElement("option");
      o1.value = p.id;
      o1.textContent = p.nome;
      og1.appendChild(o1);
      const o2 = o1.cloneNode(true);
      og2.appendChild(o2);
    }
    selPerfil.appendChild(og1);
    filtroPerfil.appendChild(og2);
  }

  // Máquinas
  const selMaq = $("sel-maquina");
  selMaq.innerHTML = "";
  for (const m of maquinas) {
    const opt = document.createElement("option");
    opt.value = m.id;
    opt.textContent = m.nome;
    selMaq.appendChild(opt);
  }

  // Categorias de ingredientes
  const cats = [...new Set(ingredientes.map((i) => i.categoria).filter(Boolean))].sort(
    (a, b) => a.localeCompare(b, "pt-BR")
  );
  const filtroCat = $("ing-filtro-cat");
  filtroCat.innerHTML = '<option value="">Todas as categorias</option>';
  const datalist = $("cat-datalist");
  datalist.innerHTML = "";
  for (const c of cats) {
    const opt = document.createElement("option");
    opt.value = c;
    opt.textContent = c;
    filtroCat.appendChild(opt);
    const opt2 = document.createElement("option");
    opt2.value = c;
    datalist.appendChild(opt2);
  }

  // Grid de perfil_acucares no modal de ingrediente
  const perfilGrid = $("f-ing-perfil-grid");
  perfilGrid.innerHTML = constantes.acucares
    .map(
      (a) => `
      <div>
        <label class="field-label" for="f-ac-${a.chave}" title="POD ${a.pod} · PAC ${a.pac}">${esc(a.rotulo)}</label>
        <input type="number" step="0.1" min="0" class="input input-num f-ac-input" data-ac="${a.chave}" id="f-ac-${a.chave}" placeholder="0">
      </div>`
    )
    .join("");
}

function renderLightChips() {
  const wrap = $("light-include-chips");
  wrap.innerHTML = LIGHT_EXTRAS.map((x) => {
    const sel = state.lightExtras.has(x.id) ? "selected" : "";
    return `<button type="button" class="toggle-chip ${sel}" data-light-ing="${x.id}">${esc(x.rotulo)}</button>`;
  }).join("");
}

function syncRecipeHeaderInputs() {
  const r = state.receita;
  $("rec-nome").value = r.nome || "";
  $("rec-versao").value = r.versao || "V1.0";
  $("rec-notas").value = r.notas || "";
  $("sel-perfil").value =
    (state.catalogo.mapaPerfis[r.perfil] && r.perfil) ||
    state.catalogo.perfis[0].id;
  $("sel-maquina").value =
    (state.catalogo.mapaMaquinas[r.maquina] && r.maquina) ||
    state.catalogo.maquinas[0].id;
  $("sel-processo").value = r.processo || "";
  $("inp-evaporada").value = r.evaporada_g || 0;
  $("btn-desfazer").disabled = state.undoStack.length === 0;
}

// ---------------------------------------------------------------------------
// Renderização principal
// ---------------------------------------------------------------------------
function renderAll() {
  const analise = eng.analisarReceita(state.receita, state.catalogo, {
    porcaoG: state.porcaoG,
    poteId: state.poteId,
    pesoKg: state.pesoKg,
  });
  state.analiseAtual = analise;

  renderPoteSelector(analise);
  renderFormulaTable(analise);
  renderScoreHero(analise);
  renderAlerts(analise);
  renderMetrics(analise);
  renderCorrecoes(analise);
  renderFreezingCurve(analise);
  renderNutrition(analise);
  renderMachineAndReminders(analise);

  if (state.activeView === "receitas") renderRecipesLibrary();
  if (state.activeView === "ingredientes") renderIngredientsLibrary();

  persistState();
}

function renderPoteSelector(a) {
  const wrap = $("pote-selector-wrap");
  const potes = eng.potesMaquina(a.maquina);
  const btnPote = $("btn-escala-pote");

  if (!potes.length) {
    wrap.innerHTML = "";
    btnPote.style.display = "none";
    return;
  }

  const ativo = a.pote ? a.pote.id : potes[0].id;
  btnPote.style.display = "inline-flex";
  if (a.pote) {
    btnPote.textContent = `Encher pote (~${eng.br(a.pote.gramas, 0)} g)`;
  }

  wrap.innerHTML = `
    <div class="pote-toggle-row">
      <strong>Pote:</strong>
      ${potes
        .map(
          (p) =>
            `<button type="button" class="pote-chip ${p.id === ativo ? "active" : ""}" data-pote-id="${esc(p.id)}">${esc(p.nome.split(" (")[0])} (${p.volume_ml} ml)</button>`
        )
        .join("")}
      ${
        a.pote
          ? `<span class="mono" style="margin-left:auto;">~${eng.br(a.pote.gramas, 0)} g · ${eng.br(a.pote.densidade_g_ml, 2)} g/ml</span>`
          : ""
      }
    </div>
  `;
}

function renderFormulaTable(a) {
  const tbody = $("formula-tbody");
  const tfoot = $("formula-tfoot");

  if (!a.linhas.length) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:24px;color:var(--ink-muted);">Nenhum ingrediente ainda. Busque abaixo para montar sua calda.</td></tr>`;
  } else {
    tbody.innerHTML = a.linhas
      .map((l, idx) => {
        const ing = state.catalogo.mapaIngredientes[l.ingrediente];
        const temAcucar =
          (ing && eng.numero(ing.acucares) > 0 && eng.numero(ing.agua) > 10) ||
          l.brix !== undefined && l.brix !== null;
        const brixVal =
          l.brix !== undefined && l.brix !== null ? eng.br(l.brix, 1) : null;
        const lockTitle = l.travado
          ? "Travado (não muda no balanceamento)"
          : "Destravado (livre para o balanceamento)";
        const lockSvg = l.travado
          ? '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>'
          : '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 9.9-1"/></svg>';
        return `
          <tr data-row-idx="${idx}">
            <td>
              <div class="ing-cell-main">
                <div class="ing-name-line">
                  <span class="ing-name">${l.conhecido ? esc(l.nome) : `${esc(l.ingrediente)} <em>(fora do banco)</em>`}</span>
                  ${
                    temAcucar
                      ? `<button type="button" class="brix-btn ${brixVal ? "active" : ""}" data-action="brix" data-idx="${idx}" title="Informar °Brix medido no refratômetro">${brixVal ? `Brix ${brixVal}°` : "+ Brix"}</button>`
                      : ""
                  }
                </div>
                <div class="ing-meta-line">
                  ${ing ? `<span>${esc(ing.categoria || "")}</span>` : ""}
                  ${l.conhecido ? `<span class="mono">G ${eng.br(l.gordura, 1)} · A ${eng.br(l.acucares, 1)} · ST ${eng.br(l.solidos_totais, 1)}</span>` : ""}
                </div>
              </div>
            </td>
            <td>
              <input type="number" step="0.5" min="0" class="grams-input" data-action="grams" data-idx="${idx}" value="${l.gramas}" aria-label="Gramas de ${esc(l.nome || l.ingrediente)}">
            </td>
            <td class="mono">${eng.br(l.pct, 1)}%</td>
            <td class="mono hide-sm">${eng.br(l.custo, 2)}</td>
            <td>
              <button type="button" class="lock-btn ${l.travado ? "locked" : ""}" data-action="lock" data-idx="${idx}" title="${lockTitle}" aria-label="${lockTitle}">
                ${lockSvg}
              </button>
            </td>
            <td>
              <button type="button" class="btn btn-icon-sm btn-ghost btn-danger" data-action="remove" data-idx="${idx}" title="Remover ingrediente" aria-label="Remover ingrediente">✕</button>
            </td>
          </tr>
        `;
      })
      .join("");
  }

  const t = a.totais;
  const evapNota =
    t.evaporada > 0
      ? `<span style="font-weight:400;font-size:0.76rem;color:var(--ink-muted);display:block;">bruto ${eng.br(t.gramas_brutos, 1)} g − ${eng.br(t.evaporada, 1)} g evap.</span>`
      : "";
  tfoot.innerHTML = `
    <tr>
      <td>TOTAL ${evapNota}</td>
      <td class="mono">${eng.br(t.gramas, 1)} g</td>
      <td class="mono">100%</td>
      <td class="mono hide-sm">R$ ${eng.br(t.custo, 2)}</td>
      <td colspan="2"></td>
    </tr>
  `;
  $("inp-peso-alvo").placeholder = String(Math.round(t.gramas) || 1000);
}

function renderScoreHero(a) {
  const conf = a.conformidade;
  const ratio = conf.total > 0 ? conf.ideal / conf.total : 0;
  const radius = 27;
  const circ = 2 * Math.PI * radius;
  const dash = circ * (1 - ratio);
  const strokeColor =
    conf.ideal === conf.total
      ? "var(--ok)"
      : conf.ideal >= 6
        ? "var(--low)"
        : "var(--high)";

  $("score-hero").innerHTML = `
    <div class="score-ring-wrap" title="Faixa verde: ${conf.ideal} de ${conf.total} parâmetros no alvo">
      <svg width="68" height="68" viewBox="0 0 68 68">
        <circle cx="34" cy="34" r="${radius}" fill="none" stroke="var(--surface-inset)" stroke-width="6"/>
        <circle cx="34" cy="34" r="${radius}" fill="none" stroke="${strokeColor}" stroke-width="6"
          stroke-linecap="round" stroke-dasharray="${circ.toFixed(1)}" stroke-dashoffset="${dash.toFixed(1)}"
          style="transition: stroke-dashoffset 260ms ease, stroke 200ms ease;"/>
      </svg>
      <div class="score-ring-text">
        <span class="score-ring-num" style="color:${strokeColor};">${conf.ideal}/${conf.total}</span>
        <span class="score-ring-lbl">Verde</span>
      </div>
    </div>
    <div class="kpi-grid">
      <div class="kpi-item">
        <span class="kpi-label">Congelamento</span>
        <span class="kpi-val">${eng.br(a.ponto_congelamento_c, 1)} °C</span>
        <span class="kpi-hint">1º cristal de gelo</span>
      </div>
      <div class="kpi-item">
        <span class="kpi-label">Servir ideal</span>
        <span class="kpi-val">${eng.br(a.temp_servir_ideal_c, 1)} °C</span>
        <span class="kpi-hint">${eng.br(a.fracao_agua_congelada_na_maquina * 100, 0)}% gelo a ${a.maquina.temp_servir} °C</span>
      </div>
      <div class="kpi-item">
        <span class="kpi-label">Energia</span>
        <span class="kpi-val">${eng.br(a.nutricao.kcal_100g, 0)} kcal</span>
        <span class="kpi-hint">100g · ${eng.br(a.nutricao.proteina_pct, 1)}% prot.</span>
      </div>
      <div class="kpi-item">
        <span class="kpi-label">Custo</span>
        <span class="kpi-val">R$ ${eng.br(a.custo.por_kg, 2)}</span>
        <span class="kpi-hint">/kg · lote R$ ${eng.br(a.custo.lote, 2)}</span>
      </div>
    </div>
  `;
}

function renderAlerts(a) {
  const boxes = [];
  const ar = a.arenosidade;

  boxes.push(`
    <div class="alert-box ${ar.ok ? "ok" : "forte"}">
      <span>${ar.ok ? "✓" : "!"}</span>
      <div>
        <strong>${ar.ok ? "Sem risco de arenosidade" : "Risco de arenosidade"}:</strong>
        SNLG pela lactose <span class="mono">${eng.br(ar.valor, 1)}%</span> · limite desta receita <span class="mono">${eng.br(ar.maximo, 1)}%</span>.
        ${ar.ok ? "" : "Reduza leite em pó, doce de leite ou leite condensado."}
      </div>
    </div>
  `);

  if (a.metricas.alcool > 0.05) {
    boxes.push(`
      <div class="alert-box warn">
        <span>!</span>
        <div><strong>Álcool (${eng.br(a.metricas.alcool, 1)}%):</strong> já incluído no PAC. Acima de ~2–3% o sorvete pode não firmar.</div>
      </div>
    `);
  }

  for (const err of a.erros_brix) {
    boxes.push(`<div class="alert-box forte"><span>!</span><div>${esc(err)}</div></div>`);
  }

  for (const aj of a.ajustes_brix) {
    boxes.push(`<div class="alert-box info"><span>°Bx</span><div>${esc(aj.texto)}</div></div>`);
  }

  if (a.comparacao_classica) {
    boxes.push(`
      <div class="alert-box info">
        <span>ℹ</span>
        <div>
          ${esc(eng.linhaComparacao(a.comparacao_classica))}
          <span style="display:block;margin-top:2px;opacity:0.9;">Estilo fit: no Creami a lâmina compensa o PAC baixo; em vitrine ficaria duro e cristalino.</span>
        </div>
      </div>
    `);
  }

  for (const al of a.alertas) {
    boxes.push(`
      <div class="alert-box ${al.nivel === "forte" ? "forte" : "warn"}">
        <span>${al.nivel === "forte" ? "⚠" : "!"}</span>
        <div>${esc(al.texto)}</div>
      </div>
    `);
  }

  $("alerts-wrap").innerHTML = boxes.join("");
}

function renderMetrics(a) {
  const { perfil, maquina, conformidade: conf } = a;
  $("balance-subtitle").textContent = `${perfil.nome} · ${perfil.descricao || ""}`;
  const aj = maquina.ajuste_pac;
  const pacBadge = $("pac-offset-badge");
  pacBadge.textContent =
    aj > 0 ? `PAC +${aj} (${maquina.nome_curto})` : `${maquina.nome_curto} (${maquina.temp_servir} °C)`;

  $("metrics-list").innerHTML = conf.parametros
    .map((q) => {
      const c = q.casas;
      const lo = q.min;
      const hi = q.max;
      const v = q.valor;
      const span = Math.max(hi - lo, 1e-9);
      const a0 = lo - span * 0.6;
      const a1 = hi + span * 0.6;
      const pos = (x) =>
        Math.max(0, Math.min(100, ((x - a0) / (a1 - a0)) * 100));
      const pLo = pos(lo);
      const pHi = pos(hi);
      const pV = pos(v);

      return `
        <div class="metric-row">
          <div class="metric-top">
            <span class="metric-label">${esc(q.rotulo)}</span>
            <div class="metric-val-wrap">
              <span class="metric-val">${eng.br(v, c)} ${esc(q.unidade)}</span>
              <span class="status-tag ${q.status}">${q.status}</span>
            </div>
          </div>
          <div class="gauge-track" aria-hidden="true">
            <div class="gauge-band" style="left:${pLo.toFixed(1)}%;width:${Math.max(2, pHi - pLo).toFixed(1)}%;"></div>
            <div class="gauge-marker ${q.status}" style="left:${pV.toFixed(1)}%;"></div>
          </div>
          <div class="metric-foot">
            <span>Faixa ideal: <strong class="mono">${eng.br(lo, c)}–${eng.br(hi, c)} ${esc(q.unidade)}</strong></span>
          </div>
          ${q.dica ? `<p class="metric-tip">${esc(q.dica)}</p>` : ""}
        </div>
      `;
    })
    .join("");
}

function renderCorrecoes(a) {
  const card = $("card-correcoes");
  const list = $("correcoes-list");
  if (!a.correcoes.length) {
    card.style.display = "none";
    return;
  }
  card.style.display = "block";
  list.innerHTML = a.correcoes
    .map((c, idx) => {
      const casas = c.metrica === "pod" || c.metrica === "pac" ? 0 : 1;
      const st = c.status === "ABAIXO" ? "abaixo" : "acima";
      return `
        <div class="fix-row">
          <div class="fix-text">
            <strong>+${eng.br(c.gramas, 1)} g de ${esc(c.nome)}</strong>
            <span style="color:var(--ink-secondary);"> para ${esc(c.rotulo)} (${eng.br(c.valor, casas)}, ${st})</span>
            <span class="fix-meta">→ ${eng.br(c.valor_depois, casas)} · faixa verde ${esc(c.faixa_verde_depois)} · ${eng.br(c.kcal_100g_antes, 0)} → ${eng.br(c.kcal_100g_depois, 0)} kcal/100 g</span>
          </div>
          <button type="button" class="btn btn-sm btn-soft" data-apply-fix="${idx}">Aplicar</button>
        </div>
      `;
    })
    .join("");
}

function renderFreezingCurve(a) {
  const wrap = $("curve-wrap");
  const readout = $("curve-readout");
  const pts = a.curva_pontos;
  if (!pts || pts.length < 2) {
    wrap.innerHTML = `<p class="card-sub">Adicione ingredientes com água para visualizar a curva de congelamento.</p>`;
    readout.textContent = "";
    return;
  }

  const W = 520;
  const H = 195;
  const pad = { l: 42, r: 16, t: 16, b: 30 };
  const iw = W - pad.l - pad.r;
  const ih = H - pad.t - pad.b;
  const tMin = -22;
  const tMax = 0;

  const xOf = (t) => pad.l + ((tMax - t) / (tMax - tMin)) * iw;
  const yOf = (pct) => pad.t + (1 - pct / 100) * ih;

  const pathD = pts
    .map((p, i) => `${i === 0 ? "M" : "L"}${xOf(p.temp).toFixed(1)},${yOf(p.fracao).toFixed(1)}`)
    .join(" ");
  const areaD = `${pathD} L${xOf(pts[pts.length - 1].temp).toFixed(1)},${yOf(0).toFixed(1)} L${xOf(pts[0].temp).toFixed(1)},${yOf(0).toFixed(1)} Z`;

  const fp = Math.max(tMin, Math.min(tMax, a.ponto_congelamento_c));
  const tServe = Math.max(tMin, Math.min(tMax, a.temp_servir_ideal_c));
  const tMaq = Math.max(tMin, Math.min(tMax, a.temp_servir_maquina_c));
  const fMaq = a.fracao_agua_congelada_na_maquina * 100;

  const yTicks = [0, 25, 50, 72, 100];
  const xTicks = [0, -4, -8, -12, -16, -20];

  readout.textContent = `A ${a.maquina.temp_servir} °C: ${eng.br(fMaq, 0)}% gelo`;

  wrap.innerHTML = `
    <svg class="curve-svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="Curva de água congelada versus temperatura" id="curve-svg">
      <defs>
        <linearGradient id="iceGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="var(--cold)" stop-opacity="0.24"/>
          <stop offset="100%" stop-color="var(--cold)" stop-opacity="0.02"/>
        </linearGradient>
      </defs>
      ${yTicks
        .map(
          (yt) => `
        <line x1="${pad.l}" y1="${yOf(yt).toFixed(1)}" x2="${W - pad.r}" y2="${yOf(yt).toFixed(1)}"
          stroke="${yt === 72 ? "var(--ok)" : "var(--border)"}" stroke-dasharray="${yt === 72 ? "4 3" : ""}" stroke-width="1"/>
        <text x="${pad.l - 7}" y="${(yOf(yt) + 3.5).toFixed(1)}" text-anchor="end" font-size="10" font-family="var(--font-mono)" fill="${yt === 72 ? "var(--ok)" : "var(--ink-muted)"}">${yt}%</text>
      `
        )
        .join("")}
      ${xTicks
        .map(
          (xt) => `
        <text x="${xOf(xt).toFixed(1)}" y="${H - 9}" text-anchor="middle" font-size="10" font-family="var(--font-mono)" fill="var(--ink-muted)">${xt}°C</text>
      `
        )
        .join("")}
      <path d="${areaD}" fill="url(#iceGrad)"/>
      <path d="${pathD}" fill="none" stroke="var(--cold)" stroke-width="2.4" stroke-linejoin="round"/>
      <!-- Ponto de congelamento -->
      <circle cx="${xOf(fp).toFixed(1)}" cy="${yOf(0).toFixed(1)}" r="4.2" fill="var(--surface)" stroke="var(--cold)" stroke-width="2.2"/>
      <!-- Servir ideal (~72%) -->
      <circle cx="${xOf(tServe).toFixed(1)}" cy="${yOf(72).toFixed(1)}" r="4.8" fill="var(--ok)" stroke="var(--surface)" stroke-width="1.8"/>
      <!-- Máquina -->
      <circle cx="${xOf(tMaq).toFixed(1)}" cy="${yOf(fMaq).toFixed(1)}" r="4.8" fill="var(--accent)" stroke="var(--surface)" stroke-width="1.8"/>
      <!-- Hover hairline -->
      <line id="curve-hover-line" x1="0" y1="${pad.t}" x2="0" y2="${H - pad.b}" stroke="var(--ink-muted)" stroke-dasharray="2 2" stroke-width="1" style="display:none;"/>
      <circle id="curve-hover-dot" cx="0" cy="0" r="4.5" fill="var(--ink)" style="display:none;"/>
      <rect id="curve-hit" x="${pad.l}" y="${pad.t}" width="${iw}" height="${ih}" fill="transparent" style="cursor:crosshair;"/>
    </svg>
    <div class="curve-legend">
      <span class="legend-item"><span class="legend-dot" style="background:var(--cold);"></span> Congelamento: <strong class="mono">${eng.br(a.ponto_congelamento_c, 1)} °C</strong></span>
      <span class="legend-item"><span class="legend-dot" style="background:var(--ok);"></span> Servir (~72%): <strong class="mono">${eng.br(a.temp_servir_ideal_c, 1)} °C</strong></span>
      <span class="legend-item"><span class="legend-dot" style="background:var(--accent);"></span> Máquina (${a.maquina.temp_servir} °C): <strong class="mono">${eng.br(fMaq, 0)}%</strong></span>
    </div>
  `;

  // Interatividade no hover
  const hit = $("curve-hit");
  const hLine = $("curve-hover-line");
  const hDot = $("curve-hover-dot");
  const svg = $("curve-svg");
  hit.addEventListener("mousemove", (ev) => {
    const rect = svg.getBoundingClientRect();
    const sx = ((ev.clientX - rect.left) / rect.width) * W;
    const t = Math.max(tMin, Math.min(tMax, tMax - ((sx - pad.l) / iw) * (tMax - tMin)));
    const fc =
      eng.fracaoCongelada(
        a.metricas.pac / 10,
        a.metricas.sng_lactose,
        a.metricas.agua,
        t,
        state.catalogo.constantes.curva_congelamento
      ) * 100;
    hLine.setAttribute("x1", xOf(t).toFixed(1));
    hLine.setAttribute("x2", xOf(t).toFixed(1));
    hLine.style.display = "block";
    hDot.setAttribute("cx", xOf(t).toFixed(1));
    hDot.setAttribute("cy", yOf(fc).toFixed(1));
    hDot.style.display = "block";
    readout.textContent = `A ${eng.br(t, 1)} °C: ${eng.br(fc, 0)}% da água em gelo`;
  });
  hit.addEventListener("mouseleave", () => {
    hLine.style.display = "none";
    hDot.style.display = "none";
    readout.textContent = `A ${a.maquina.temp_servir} °C: ${eng.br(fMaq, 0)}% gelo`;
  });
}

function renderNutrition(a) {
  const n = a.nutricao;
  const rows = [
    { rotulo: "Por 100 g", d: n.por_100g },
    { rotulo: `Porção (${eng.br(n.porcao.gramas, 0)} g)`, d: n.porcao },
  ];
  if (n.pote && a.pote) {
    rows.push({
      rotulo: `${a.pote.nome.split(" (")[0]} (~${eng.br(a.pote.gramas, 0)} g)`,
      d: n.pote,
    });
  }
  rows.push({ rotulo: `Lote (${eng.br(n.lote.gramas, 0)} g)`, d: n.lote });

  $("nutri-table").innerHTML = `
    <thead>
      <tr>
        <th>Referência</th>
        <th>kcal</th>
        <th>Prot.</th>
        <th>Gord.</th>
        <th>Açúc.</th>
      </tr>
    </thead>
    <tbody>
      ${rows
        .map(
          (r) => `
        <tr>
          <td><strong>${esc(r.rotulo)}</strong></td>
          <td class="mono">${eng.br(r.d.kcal, 0)}</td>
          <td class="mono">${eng.br(r.d.proteina_g, 1)} g</td>
          <td class="mono">${eng.br(r.d.gordura_g, 1)} g</td>
          <td class="mono">${eng.br(r.d.acucares_g, 1)} g</td>
        </tr>`
        )
        .join("")}
    </tbody>
  `;

  const extras = [];
  const pol = n.porcao.poliois_g || {};
  const polEntries = Object.entries(pol).filter(([, v]) => v > 0.05);
  if (polEntries.length) {
    extras.push(
      `<strong>Polióis/alulose/fibras na porção:</strong> ${polEntries
        .map(([c, v]) => `${eng.br(v, 1)} g de ${esc(c)}`)
        .join(", ")}.`
    );
  }
  const eritLote = (n.lote.poliois_g && n.lote.poliois_g.eritritol) || 0;
  if (eritLote > 0) {
    extras.push(
      `<strong>Eritritol:</strong> ${eng.br(pol.eritritol || 0, 1)} g/porção (teto sugerido ${eng.br(a.limite_eritritol_porcao_g, 1)} g = 1/3 da IDA da EFSA) · ${eng.br(eritLote, 1)} g no lote.`
    );
  }
  if (n.caseina_pct > 0.5) {
    extras.push(`Caseína estimada: <span class="mono">${eng.br(n.caseina_pct, 1)}%</span> da calda.`);
  }
  $("nutri-extra-wrap").innerHTML = extras.map((x) => `<div style="margin-top:4px;">${x}</div>`).join("");
}

function renderMachineAndReminders(a) {
  const m = a.maquina;
  $("maquina-nota-sub").textContent = m.nota_lote || m.nome;
  const dicas = [...(m.dicas || []), ...a.orientacoes_maquina];
  const uniqueDicas = [...new Set(dicas)];
  $("maquina-dicas-wrap").innerHTML = `
    <ul style="margin:0;padding-left:18px;font-size:0.82rem;color:var(--ink-secondary);display:flex;flex-direction:column;gap:5px;">
      ${uniqueDicas.map((d) => `<li>${esc(d)}</li>`).join("")}
    </ul>
  `;

  $("lembretes-list").innerHTML = a.lembretes
    .map((l, i) => {
      const checked = state.checkedLembretes.has(l);
      return `
        <li class="${checked ? "checked" : ""}">
          <input type="checkbox" id="lemb-${i}" data-lembrete="${esc(l)}" ${checked ? "checked" : ""}>
          <label for="lemb-${i}">${esc(l)}</label>
        </li>
      `;
    })
    .join("");
}

// ---------------------------------------------------------------------------
// View 2: Biblioteca de Receitas
// ---------------------------------------------------------------------------
function renderRecipesLibrary() {
  const busca = ($("rec-busca").value || "").trim().toLowerCase();
  const filtroPerfil = $("rec-filtro-perfil").value;
  const filtroOrigem = $("rec-filtro-origem").value;

  const lista = state.catalogo.receitas.filter((r) => {
    if (filtroPerfil && r.perfil !== filtroPerfil) return false;
    if (filtroOrigem && r._origem !== filtroOrigem) return false;
    if (busca) {
      const inNome = String(r.nome || "").toLowerCase().includes(busca);
      const inNotas = String(r.notas || "").toLowerCase().includes(busca);
      const inIng = (r.itens || []).some((it) => {
        const ing = state.catalogo.mapaIngredientes[it.ingrediente];
        return ing && ing.nome.toLowerCase().includes(busca);
      });
      if (!inNome && !inNotas && !inIng) return false;
    }
    return true;
  });

  const grid = $("recipes-grid");
  if (!lista.length) {
    grid.innerHTML = `<div class="card" style="grid-column:1/-1;text-align:center;color:var(--ink-muted);">Nenhuma receita encontrada com esses filtros.</div>`;
    return;
  }

  grid.innerHTML = lista
    .map((r) => {
      const a = eng.analisarReceita(r, state.catalogo);
      const okClass =
        a.conformidade.ideal === a.conformidade.total ? "ok" : "warn";
      const origBadge =
        r._origem === "usuario"
          ? '<span class="badge accent">Salva</span>'
          : r._origem === "novidade"
            ? '<span class="badge">Fit / Creami</span>'
            : "";
      return `
        <article class="recipe-card">
          <div class="recipe-card-top">
            <div>
              <h3 class="recipe-card-title">${esc(r.nome)}</h3>
              <div class="recipe-card-meta">${esc(a.perfil.nome)} · ${esc(a.maquina.nome_curto)}</div>
            </div>
            <span class="badge ${okClass} mono">${a.conformidade.ideal}/${a.conformidade.total}</span>
          </div>
          ${r.notas ? `<p style="margin:0;font-size:0.79rem;color:var(--ink-secondary);line-height:1.4;">${esc(r.notas)}</p>` : ""}
          <div class="recipe-card-stats">
            <div><span>Gord.</span>${eng.br(a.metricas.gordura, 1)}%</div>
            <div><span>Açúc.</span>${eng.br(a.metricas.acucares, 1)}%</div>
            <div><span>PAC</span>${eng.br(a.metricas.pac, 0)}</div>
            <div><span>kcal/100g</span>${eng.br(a.nutricao.kcal_100g, 0)}</div>
          </div>
          <div class="recipe-card-foot">
            <div style="display:flex;gap:6px;align-items:center;">
              <span class="mono" style="font-size:0.76rem;color:var(--ink-muted);">${eng.br(a.totais.gramas, 0)} g</span>
              ${origBadge}
            </div>
            <div style="display:flex;gap:6px;">
              ${r._origem === "usuario" ? `<button type="button" class="btn btn-sm btn-ghost btn-danger" data-delete-rec="${esc(r.id)}">Excluir</button>` : ""}
              <button type="button" class="btn btn-sm btn-primary" data-open-rec="${esc(r.id)}">Abrir</button>
            </div>
          </div>
        </article>
      `;
    })
    .join("");
}

// ---------------------------------------------------------------------------
// View 3: Banco de Ingredientes
// ---------------------------------------------------------------------------
function renderIngredientsLibrary() {
  const busca = ($("ing-busca").value || "").trim().toLowerCase();
  const cat = $("ing-filtro-cat").value;
  const { constantes, constantesNov: kNov } = state.catalogo;

  const lista = state.catalogo.ingredientes.filter((i) => {
    if (cat && i.categoria !== cat) return false;
    if (busca) {
      const hit =
        String(i.nome || "").toLowerCase().includes(busca) ||
        String(i.id || "").toLowerCase().includes(busca) ||
        String(i.categoria || "").toLowerCase().includes(busca);
      if (!hit) return false;
    }
    return true;
  });

  $("ing-db-tbody").innerHTML = lista
    .map((i) => {
      const kcal = eng.kcal100g(i, constantes, kNov);
      const badge =
        i._origem === "usuario"
          ? '<span class="badge accent" style="margin-left:6px;">Meu</span>'
          : i._origem === "novidade"
            ? '<span class="badge" style="margin-left:6px;">Extra</span>'
            : "";
      return `
        <tr>
          <td>
            <div style="font-weight:600;">${esc(i.nome)}${badge}</div>
            <div style="font-size:0.74rem;color:var(--ink-muted);">${esc(i.categoria || "—")} · <span class="mono">${esc(i.id)}</span></div>
          </td>
          <td class="mono">${eng.br(i.agua, 1)}</td>
          <td class="mono">${eng.br(i.gordura, 1)}</td>
          <td class="mono">${eng.br(i.proteina || 0, 1)}</td>
          <td class="mono">${eng.br(i.acucares, 1)}</td>
          <td class="mono">${eng.br(i.sng, 1)}</td>
          <td class="mono">${eng.br(i.outros_solidos, 1)}</td>
          <td class="mono">${eng.br(i.pod, 0)}</td>
          <td class="mono">${eng.br(i.pac, 0)}</td>
          <td class="mono">${eng.br(kcal, 0)}</td>
          <td class="mono">${eng.br(i.custo_kg, 2)}</td>
          <td>
            <button type="button" class="btn btn-sm btn-ghost" data-edit-ing="${esc(i.id)}">
              ${i._origem === "usuario" ? "Editar" : "Duplicar"}
            </button>
          </td>
        </tr>
      `;
    })
    .join("");
}

// ---------------------------------------------------------------------------
// Combobox de Adicionar Ingrediente
// ---------------------------------------------------------------------------
function updateAddIngMenu(query) {
  const menu = $("add-ing-menu");
  const q = (query || "").trim().toLowerCase();
  const { constantes, constantesNov: kNov } = state.catalogo;
  const results = state.catalogo.ingredientes
    .filter((i) => {
      if (!q) return true;
      return (
        i.nome.toLowerCase().includes(q) ||
        String(i.categoria || "").toLowerCase().includes(q) ||
        i.id.toLowerCase().includes(q)
      );
    })
    .slice(0, 14);

  state.comboResults = results;
  state.comboHighlight = 0;

  if (!results.length) {
    menu.innerHTML = `<div style="padding:10px 12px;font-size:0.82rem;color:var(--ink-muted);">Nenhum ingrediente encontrado. Cadastre na aba Ingredientes.</div>`;
    menu.classList.add("open");
    return;
  }

  menu.innerHTML = results
    .map((i, idx) => {
      const kcal = eng.kcal100g(i, constantes, kNov);
      return `
        <button type="button" class="combobox-item ${idx === 0 ? "highlighted" : ""}" data-pick-ing="${esc(i.id)}" role="option">
          <div>
            <div class="combobox-item-name">${esc(i.nome)}</div>
            <div class="combobox-item-cat">${esc(i.categoria || "")}</div>
          </div>
          <span class="combobox-item-stats">G ${eng.br(i.gordura, 0)}% · A ${eng.br(i.acucares, 0)}% · PAC ${eng.br(i.pac, 0)} · ${eng.br(kcal, 0)} kcal</span>
        </button>
      `;
    })
    .join("");
  menu.classList.add("open");
}

function addIngredientToRecipe(ingId, defaultGrams = 50) {
  const ing = state.catalogo.mapaIngredientes[ingId];
  if (!ing) return;
  pushUndo();
  const existente = state.receita.itens.find((i) => i.ingrediente === ingId);
  if (existente) {
    existente.gramas = Math.round((eng.numero(existente.gramas) + defaultGrams) * 10) / 10;
    showToast(`+${defaultGrams} g de ${ing.nome}`);
  } else {
    const sugerido =
      ing.dose_max_pct && ing.dose_max_pct <= 0.5
        ? 1.5
        : ing.categoria === "Estabilizantes"
          ? 2
          : defaultGrams;
    state.receita.itens.push({
      ingrediente: ingId,
      gramas: sugerido,
      travado: Boolean(ing.dose_max_pct && ing.dose_max_pct <= 0.5),
    });
    showToast(`${ing.nome} adicionado (${sugerido} g)`);
  }
  $("inp-add-ing").value = "";
  $("add-ing-menu").classList.remove("open");
  renderAll();
}

// ---------------------------------------------------------------------------
// Modal de Ingrediente Customizado
// ---------------------------------------------------------------------------
function openIngredientModal(existingId = null) {
  const form = $("form-ing");
  form.reset();
  const isEditCustom =
    existingId &&
    state.custom.ingredientes.some((i) => i.id === existingId);
  const src = existingId ? state.catalogo.mapaIngredientes[existingId] : null;

  $("modal-ing-title").textContent = isEditCustom
    ? "Editar Ingrediente"
    : src
      ? `Duplicar: ${src.nome}`
      : "Novo Ingrediente";
  $("btn-excluir-ing").style.display = isEditCustom ? "inline-flex" : "none";
  $("f-ing-id").value = isEditCustom ? src.id : "";

  if (src) {
    $("f-ing-nome").value = isEditCustom ? src.nome : `${src.nome} (cópia)`;
    $("f-ing-cat").value = src.categoria || "Outros";
    $("f-ing-agua").value = src.agua ?? 0;
    $("f-ing-gordura").value = src.gordura ?? 0;
    $("f-ing-proteina").value = src.proteina ?? 0;
    $("f-ing-acucares").value = src.acucares ?? 0;
    $("f-ing-sng").value = src.sng ?? 0;
    $("f-ing-lactose").value = src.lactose ?? 0;
    $("f-ing-outros").value = src.outros_solidos ?? 0;
    $("f-ing-alcool").value = src.alcool ?? 0;
    $("f-ing-custo").value = src.custo_kg ?? 0;
    $("f-ing-auto").checked = Boolean(src.pod_pac_auto);
    $("f-ing-pod").value = src.pod ?? 0;
    $("f-ing-pac").value = src.pac ?? 0;
    $("f-ing-fibra").value = src.fibra ?? "";
    $("f-ing-kcal").value = src.kcal_100g ?? "";
    $("f-ing-dmax").value = src.dose_max_pct ?? "";
    const perf = src.perfil_acucares || {};
    for (const inp of form.querySelectorAll(".f-ac-input")) {
      inp.value = perf[inp.dataset.ac] ?? "";
    }
  } else {
    $("f-ing-agua").value = 100;
    $("f-ing-auto").checked = true;
  }

  refreshIngredientModalPreview();
  $("modal-ing").classList.add("open");
}

function readIngredientForm() {
  const perfil = {};
  for (const inp of $("form-ing").querySelectorAll(".f-ac-input")) {
    const v = eng.numero(inp.value);
    if (v > 0) perfil[inp.dataset.ac] = v;
  }
  const obj = {
    id: $("f-ing-id").value || `ing_custom_${slug($("f-ing-nome").value)}`,
    nome: $("f-ing-nome").value.trim() || "Ingrediente Custom",
    categoria: $("f-ing-cat").value.trim() || "Outros",
    agua: eng.numero($("f-ing-agua").value),
    gordura: eng.numero($("f-ing-gordura").value),
    proteina: eng.numero($("f-ing-proteina").value),
    acucares: eng.numero($("f-ing-acucares").value),
    sng: eng.numero($("f-ing-sng").value),
    lactose: eng.numero($("f-ing-lactose").value),
    outros_solidos: eng.numero($("f-ing-outros").value),
    alcool: eng.numero($("f-ing-alcool").value),
    custo_kg: eng.numero($("f-ing-custo").value),
    pod_pac_auto: $("f-ing-auto").checked,
    pod: eng.numero($("f-ing-pod").value),
    pac: eng.numero($("f-ing-pac").value),
    perfil_acucares: perfil,
  };
  if ($("f-ing-fibra").value !== "") obj.fibra = eng.numero($("f-ing-fibra").value);
  if ($("f-ing-kcal").value !== "") obj.kcal_100g = eng.numero($("f-ing-kcal").value);
  if ($("f-ing-dmax").value !== "") obj.dose_max_pct = eng.numero($("f-ing-dmax").value);
  return eng.aplicarPodPacAuto(obj, state.catalogo.constantes);
}

function refreshIngredientModalPreview() {
  const ing = readIngredientForm();
  const auto = $("f-ing-auto").checked;
  $("f-ing-pod").disabled = auto;
  $("f-ing-pac").disabled = auto;
  if (auto) {
    $("f-ing-pod").value = ing.pod;
    $("f-ing-pac").value = ing.pac;
  }
  const soma = eng.somaComposicao(ing);
  const somaEl = $("f-ing-soma");
  somaEl.textContent = `Soma: ${eng.br(soma, 1)}%`;
  somaEl.style.color = Math.abs(soma - 100) <= 0.5 ? "var(--ok)" : "var(--high)";

  const avisos = eng.validarIngrediente(ing, state.catalogo.constantes);
  $("f-ing-avisos").innerHTML = avisos
    .map(
      (av) =>
        `<div class="alert-box ${av.nivel === "error" ? "forte" : "warn"}"><span>${av.nivel === "error" ? "!" : "ℹ"}</span><div>${esc(av.texto)}</div></div>`
    )
    .join("");
}

// ---------------------------------------------------------------------------
// Modal de Ficha Técnica + Download HTML estático
// ---------------------------------------------------------------------------
function updateFichaPreview() {
  const a = state.analiseAtual;
  if (!a) return;
  let txt = "";
  if (state.fichaTab === "md") {
    txt = eng.gerarFichaMarkdown(a);
  } else if (state.fichaTab === "texto") {
    txt = eng.gerarFichaTexto(a, state.catalogo.constantes);
  } else {
    txt = JSON.stringify(eng.paraArquivoReceita(state.receita), null, 2);
  }
  $("ficha-preview").value = txt;
}

function gerarHtmlEstatico(a) {
  const r = a.receita;
  const conf = a.conformidade;
  const t = a.totais;
  const css = `:root{--bg:#f6f7f9;--card:#fff;--tx:#17202a;--mut:#5d6b7a;--ln:#e3e7ec;--ok:#1f7a4d;--okbg:#e6f4ec;--lo:#a15c00;--lobg:#fdf1de;--hi:#b0283b;--hibg:#fbe7ea;--band:#cfe9da;--mark:#17202a;--acc:#0b6fa4}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);font:15px/1.5 system-ui,-apple-system,sans-serif}main{max-width:860px;margin:0 auto;padding:18px}h1{font-size:1.5rem;margin:.2rem 0}h2{font-size:1.05rem;margin:0 0 .6rem}.sub{color:var(--mut);font-size:.9rem;margin:0}.card{background:var(--card);border:1px solid var(--ln);border-radius:14px;padding:14px 16px;margin:14px 0}.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;margin:14px 0}.kpi{background:var(--card);border:1px solid var(--ln);border-radius:14px;padding:12px 14px}.kpi b{display:block;font-size:1.3rem}.kpi span{color:var(--mut);font-size:.76rem;text-transform:uppercase}table{width:100%;border-collapse:collapse}th,td{padding:6px 4px;border-bottom:1px solid var(--ln);text-align:right}th:first-child,td:first-child{text-align:left}tfoot td{font-weight:700;border-bottom:0}.tag{display:inline-block;font-size:.72rem;font-weight:700;padding:1px 8px;border-radius:99px}.IDEAL{color:var(--ok);background:var(--okbg)}.ABAIXO{color:var(--lo);background:var(--lobg)}.ACIMA{color:var(--hi);background:var(--hibg)}`;
  return `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${esc(r.nome)} (${esc(r.versao)}) · Calda Certa</title><style>${css}</style></head><body><main>
  <p class="sub">Calda Certa · Ficha de Balanceamento</p>
  <h1>${esc(r.nome)} <small>(${esc(r.versao)})</small></h1>
  <p class="sub">${esc(a.perfil.nome)} · ${esc(a.maquina.nome)} · Faixa verde: <strong>${conf.ideal}/${conf.total}</strong></p>
  ${r.notas ? `<p class="sub">${esc(r.notas)}</p>` : ""}
  <div class="kpis">
    <div class="kpi"><span>Congelamento</span><b>${eng.br(a.ponto_congelamento_c, 1)} °C</b></div>
    <div class="kpi"><span>Servir ideal</span><b>${eng.br(a.temp_servir_ideal_c, 1)} °C</b></div>
    <div class="kpi"><span>Energia</span><b>${eng.br(a.nutricao.kcal_100g, 0)} kcal/100g</b></div>
    <div class="kpi"><span>Custo</span><b>R$ ${eng.br(a.custo.por_kg, 2)}/kg</b></div>
  </div>
  <section class="card"><h2>Ingredientes</h2><table><thead><tr><th>Ingrediente</th><th>g</th><th>%</th><th>R$</th></tr></thead><tbody>
  ${a.linhas.map((l) => `<tr><td>${esc(l.nome || l.ingrediente)}</td><td>${eng.br(l.gramas, 1)}</td><td>${eng.br(l.pct, 1)}</td><td>${eng.br(l.custo, 2)}</td></tr>`).join("")}
  </tbody><tfoot><tr><td>TOTAL</td><td>${eng.br(t.gramas, 1)}</td><td>100</td><td>${eng.br(t.custo, 2)}</td></tr></tfoot></table></section>
  <section class="card"><h2>Balanceamento</h2><table><thead><tr><th>Parâmetro</th><th>Valor</th><th>Faixa</th><th>Status</th></tr></thead><tbody>
  ${conf.parametros.map((q) => `<tr><td>${esc(q.rotulo)}</td><td>${eng.br(q.valor, q.casas)} ${esc(q.unidade)}</td><td>${eng.br(q.min, q.casas)}–${eng.br(q.max, q.casas)}</td><td><span class="tag ${q.status}">${q.status}</span></td></tr>`).join("")}
  </tbody></table></section>
  <section class="card"><h2>Nutrição</h2><ul>${eng.linhasNutricao(a.nutricao, a.pote, a.limite_eritritol_porcao_g).map((l) => `<li>${esc(l)}</li>`).join("")}</ul></section>
  ${a.alertas.length ? `<section class="card"><h2>Alertas</h2><ul>${a.alertas.map((x) => `<li>${esc(x.texto)}</li>`).join("")}</ul></section>` : ""}
  <section class="card"><h2>Lembretes</h2><ul>${a.lembretes.map((l) => `<li>${esc(l)}</li>`).join("")}</ul></section>
  </main></body></html>`;
}

function downloadFile(filename, content, mime = "text/plain;charset=utf-8") {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// ---------------------------------------------------------------------------
// Eventos
// ---------------------------------------------------------------------------
function switchView(view) {
  state.activeView = view;
  document.querySelectorAll(".nav-tab[data-view]").forEach((b) => {
    b.classList.toggle("active", b.dataset.view === view);
  });
  document.querySelectorAll(".view").forEach((s) => {
    s.classList.toggle("active", s.id === `view-${view}`);
  });
  if (view === "receitas") renderRecipesLibrary();
  if (view === "ingredientes") renderIngredientsLibrary();
  window.scrollTo({ top: 0, behavior: "instant" });
}

function bindEvents() {
  // Tabs
  document.querySelectorAll(".nav-tab[data-view]").forEach((b) => {
    b.addEventListener("click", () => switchView(b.dataset.view));
  });
  $("brand-home").addEventListener("click", (e) => {
    e.preventDefault();
    switchView("bancada");
  });

  // Theme
  $("btn-theme").addEventListener("click", () => {
    const next =
      document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    applyTheme(next);
    persistState();
  });

  // Recipe header inputs
  $("rec-nome").addEventListener("input", (e) => {
    state.receita.nome = e.target.value;
    persistState();
  });
  $("rec-versao").addEventListener("input", (e) => {
    state.receita.versao = e.target.value;
    persistState();
  });
  $("rec-notas").addEventListener("input", (e) => {
    state.receita.notas = e.target.value;
    persistState();
  });
  $("sel-perfil").addEventListener("change", (e) => {
    state.receita.perfil = e.target.value;
    renderAll();
  });
  $("sel-maquina").addEventListener("change", (e) => {
    state.receita.maquina = e.target.value;
    state.poteId = null;
    renderAll();
  });
  $("sel-processo").addEventListener("change", (e) => {
    state.receita.processo = e.target.value || null;
    renderAll();
  });
  $("inp-evaporada").addEventListener("input", (e) => {
    state.receita.evaporada_g = Math.max(0, eng.numero(e.target.value));
    renderAll();
  });

  // Pote selector
  $("pote-selector-wrap").addEventListener("click", (e) => {
    const btn = e.target.closest("[data-pote-id]");
    if (!btn) return;
    state.poteId = btn.dataset.poteId;
    renderAll();
  });

  // Nutrition controls
  $("inp-porcao-g").addEventListener("input", (e) => {
    const v = eng.numero(e.target.value);
    if (v > 0) {
      state.porcaoG = v;
      renderAll();
    }
  });
  $("inp-peso-kg").addEventListener("input", (e) => {
    const v = eng.numero(e.target.value);
    if (v > 0) {
      state.pesoKg = v;
      renderAll();
    }
  });

  // Formula table events (delegated)
  $("formula-tbody").addEventListener("input", (e) => {
    const inp = e.target.closest('input[data-action="grams"]');
    if (!inp) return;
    const idx = Number(inp.dataset.idx);
    state.receita.itens[idx].gramas = Math.max(0, eng.numero(inp.value));
    // Re-render análise sem destruir o foco do input ativo
    const analise = eng.analisarReceita(state.receita, state.catalogo, {
      porcaoG: state.porcaoG,
      poteId: state.poteId,
      pesoKg: state.pesoKg,
    });
    state.analiseAtual = analise;
    // Atualiza % e R$ na tabela sem recriar os inputs
    const rows = $("formula-tbody").querySelectorAll("tr");
    analise.linhas.forEach((l, i) => {
      const tr = rows[i];
      if (!tr) return;
      const tds = tr.querySelectorAll("td");
      if (tds[2]) tds[2].textContent = `${eng.br(l.pct, 1)}%`;
      if (tds[3]) tds[3].textContent = eng.br(l.custo, 2);
      const meta = tr.querySelector(".ing-meta-line .mono");
      if (meta && l.conhecido) {
        meta.textContent = `G ${eng.br(l.gordura, 1)} · A ${eng.br(l.acucares, 1)} · ST ${eng.br(l.solidos_totais, 1)}`;
      }
    });
    const t = analise.totais;
    const tfootTds = $("formula-tfoot").querySelectorAll("td");
    if (tfootTds[1]) tfootTds[1].textContent = `${eng.br(t.gramas, 1)} g`;
    if (tfootTds[3]) tfootTds[3].textContent = `R$ ${eng.br(t.custo, 2)}`;
    renderPoteSelector(analise);
    renderScoreHero(analise);
    renderAlerts(analise);
    renderMetrics(analise);
    renderCorrecoes(analise);
    renderFreezingCurve(analise);
    renderNutrition(analise);
    persistState();
  });

  $("formula-tbody").addEventListener("click", (e) => {
    const btn = e.target.closest("[data-action]");
    if (!btn) return;
    const idx = Number(btn.dataset.idx);
    const action = btn.dataset.action;
    if (action === "lock") {
      state.receita.itens[idx].travado = !state.receita.itens[idx].travado;
      renderAll();
    } else if (action === "remove") {
      pushUndo();
      state.receita.itens.splice(idx, 1);
      renderAll();
    } else if (action === "brix") {
      const item = state.receita.itens[idx];
      const ing = state.catalogo.mapaIngredientes[item.ingrediente];
      const atual = item.brix != null ? String(item.brix) : "";
      const entrada = window.prompt(
        `°Brix medido para ${ing ? ing.nome : item.ingrediente} (deixe vazio para usar o padrão do banco):`,
        atual
      );
      if (entrada === null) return;
      pushUndo();
      if (entrada.trim() === "") {
        delete item.brix;
      } else {
        const val = Number(entrada.replace(",", "."));
        if (!Number.isNaN(val) && val > 0 && val < 100) {
          item.brix = val;
        } else {
          showToast("Informe um °Brix entre 0 e 100.");
          return;
        }
      }
      renderAll();
    }
  });

  // Add Ingredient Combobox
  const addInp = $("inp-add-ing");
  const addMenu = $("add-ing-menu");
  addInp.addEventListener("focus", () => updateAddIngMenu(addInp.value));
  addInp.addEventListener("input", () => updateAddIngMenu(addInp.value));
  addInp.addEventListener("keydown", (e) => {
    if (!addMenu.classList.contains("open")) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      state.comboHighlight = Math.min(
        state.comboResults.length - 1,
        state.comboHighlight + 1
      );
      highlightCombo();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      state.comboHighlight = Math.max(0, state.comboHighlight - 1);
      highlightCombo();
    } else if (e.key === "Enter") {
      e.preventDefault();
      const chosen = state.comboResults[state.comboHighlight];
      if (chosen) addIngredientToRecipe(chosen.id);
    } else if (e.key === "Escape") {
      addMenu.classList.remove("open");
    }
  });
  addMenu.addEventListener("click", (e) => {
    const item = e.target.closest("[data-pick-ing]");
    if (item) addIngredientToRecipe(item.dataset.pickIng);
  });
  document.addEventListener("click", (e) => {
    if (!e.target.closest(".add-ing-wrap")) {
      addMenu.classList.remove("open");
    }
  });

  function highlightCombo() {
    addMenu.querySelectorAll(".combobox-item").forEach((el, idx) => {
      el.classList.toggle("highlighted", idx === state.comboHighlight);
      if (idx === state.comboHighlight) el.scrollIntoView({ block: "nearest" });
    });
  }

  // Undo & Unlock all
  $("btn-desfazer").addEventListener("click", () => {
    if (!state.undoStack.length) return;
    state.receita = state.undoStack.pop();
    syncRecipeHeaderInputs();
    renderAll();
    showToast("Alteração desfeita");
  });

  $("btn-destravar-todos").addEventListener("click", () => {
    pushUndo();
    state.receita.itens.forEach((i) => (i.travado = false));
    renderAll();
    showToast("Todos os ingredientes destravados");
  });

  // Scaling
  const aplicarEscala = (alvo, label) => {
    try {
      pushUndo();
      const a = state.analiseAtual;
      state.receita.itens = eng.escalonar(
        state.receita.itens,
        a.ingredientesEfetivos,
        state.catalogo.constantes,
        alvo,
        state.receita.evaporada_g || 0
      );
      state.receita.lote_g = Math.round(alvo);
      renderAll();
      showToast(`Escalonada para ${eng.br(alvo, 0)} g (${label})`);
    } catch (err) {
      showToast(err.message);
    }
  };

  $("btn-escalonar").addEventListener("click", () => {
    const v = eng.numero($("inp-peso-alvo").value);
    if (v <= 0) return showToast("Informe um peso alvo maior que 0 g.");
    aplicarEscala(v, "peso alvo");
  });

  $("btn-escala-maquina").addEventListener("click", () => {
    const m = state.analiseAtual.maquina;
    aplicarEscala(m.lote_g, m.nome_curto);
  });

  $("btn-escala-pote").addEventListener("click", () => {
    const p = state.analiseAtual.pote;
    if (!p) return;
    aplicarEscala(p.gramas, p.nome.split(" (")[0]);
  });

  // Auto-Balancear (padrão)
  $("btn-balancear").addEventListener("click", () => {
    const a = state.analiseAtual;
    const res = eng.balancear(
      state.receita.itens,
      a.ingredientesEfetivos,
      a.faixas,
      state.receita.evaporada_g || 0
    );
    if (!res.sucesso) return showToast(res.mensagem);
    pushUndo();
    state.receita.itens = res.itens;
    renderAll();
    showToast(res.mensagem);
  });

  // Light Drawer & Execute Light
  $("btn-toggle-light").addEventListener("click", () => {
    $("drawer-light").classList.toggle("open");
  });

  $("light-include-chips").addEventListener("click", (e) => {
    const btn = e.target.closest("[data-light-ing]");
    if (!btn) return;
    const id = btn.dataset.lightIng;
    if (state.lightExtras.has(id)) state.lightExtras.delete(id);
    else state.lightExtras.add(id);
    renderLightChips();
  });

  $("btn-executar-light").addEventListener("click", () => {
    const a = state.analiseAtual;
    const itensTrabalho = state.receita.itens.map((i) => ({ ...i }));
    const existentes = new Set(itensTrabalho.map((i) => i.ingrediente));
    for (const extraId of state.lightExtras) {
      if (!existentes.has(extraId) && a.ingredientesEfetivos[extraId]) {
        itensTrabalho.push({ ingrediente: extraId, gramas: 0, travado: false });
      }
    }
    const pminRaw = $("inp-light-prot").value;
    const pmin = pminRaw !== "" ? eng.numero(pminRaw) : null;
    const { objetivo } = eng.objetivoLight(
      itensTrabalho,
      a.ingredientesEfetivos,
      a.faixas,
      state.catalogo.constantes,
      state.catalogo.constantesNov,
      state.receita.evaporada_g || 0,
      pmin,
      state.porcaoG,
      state.pesoKg
    );
    const res = eng.balancear(
      itensTrabalho,
      a.ingredientesEfetivos,
      a.faixas,
      state.receita.evaporada_g || 0,
      objetivo
    );
    if (!res.sucesso) return showToast(res.mensagem);
    pushUndo();
    // Remove extras que ficaram zerados
    state.receita.itens = res.itens.filter(
      (it) => existentes.has(it.ingrediente) || it.gramas > 0
    );
    renderAll();
    const depois = state.analiseAtual;
    showToast(
      `Light: ${eng.br(a.nutricao.kcal_100g, 0)} → ${eng.br(depois.nutricao.kcal_100g, 0)} kcal/100 g (${depois.conformidade.ideal}/${depois.conformidade.total})`
    );
  });

  // Apply 1-ingredient quick fix
  $("correcoes-list").addEventListener("click", (e) => {
    const btn = e.target.closest("[data-apply-fix]");
    if (!btn) return;
    const c = state.analiseAtual.correcoes[Number(btn.dataset.applyFix)];
    if (!c) return;
    addIngredientToRecipe(c.ingrediente, c.gramas);
  });

  // Save / New Recipe
  $("btn-salvar-receita").addEventListener("click", () => {
    const r = cloneRecipe(state.receita);
    if (!r.id || !r.id.startsWith("rec_user_")) {
      r.id = `rec_user_${slug(r.nome)}_${slug(r.versao)}`;
    }
    r.atualizada_em = new Date().toISOString().slice(0, 10);
    r._origem = "usuario";
    state.receita.id = r.id;
    const idx = state.custom.receitas.findIndex((x) => x.id === r.id);
    if (idx >= 0) state.custom.receitas[idx] = r;
    else state.custom.receitas.unshift(r);
    rebuildCatalog();
    persistState();
    showToast(`Receita "${r.nome}" salva na biblioteca!`);
  });

  const criarNovaReceita = () => {
    pushUndo();
    state.receita = {
      id: null,
      nome: "Nova Receita",
      versao: "V1.0",
      perfil: state.catalogo.perfis[0].id,
      maquina: state.catalogo.maquinas[0].id,
      status: "Em Teste",
      notas: "",
      evaporada_g: 0,
      processo: null,
      itens: [
        { ingrediente: "ing_leite_int", gramas: 600, travado: false },
        { ingrediente: "ing_creme_35", gramas: 180, travado: false },
        { ingrediente: "ing_sacarose", gramas: 140, travado: false },
        { ingrediente: "ing_leite_po_desn", gramas: 40, travado: false },
        { ingrediente: "ing_dextrose", gramas: 38, travado: false },
        { ingrediente: "ing_goma_guar", gramas: 2, travado: true },
      ],
    };
    syncRecipeHeaderInputs();
    switchView("bancada");
    renderAll();
    showToast("Nova receita criada com base inicial");
  };
  $("btn-nova-receita").addEventListener("click", criarNovaReceita);
  $("btn-nova-receita-lib").addEventListener("click", criarNovaReceita);

  // Lembretes checkboxes
  $("lembretes-list").addEventListener("change", (e) => {
    const cb = e.target.closest('input[type="checkbox"]');
    if (!cb) return;
    const txt = cb.dataset.lembrete;
    if (cb.checked) state.checkedLembretes.add(txt);
    else state.checkedLembretes.delete(txt);
    cb.closest("li").classList.toggle("checked", cb.checked);
  });

  // Library views filters & actions
  $("rec-busca").addEventListener("input", renderRecipesLibrary);
  $("rec-filtro-perfil").addEventListener("change", renderRecipesLibrary);
  $("rec-filtro-origem").addEventListener("change", renderRecipesLibrary);
  $("recipes-grid").addEventListener("click", (e) => {
    const openBtn = e.target.closest("[data-open-rec]");
    if (openBtn) {
      const rec = state.catalogo.receitas.find(
        (r) => r.id === openBtn.dataset.openRec
      );
      if (rec) {
        pushUndo();
        state.receita = cloneRecipe(rec);
        state.poteId = null;
        syncRecipeHeaderInputs();
        switchView("bancada");
        renderAll();
        showToast(`Receita "${rec.nome}" carregada`);
      }
      return;
    }
    const delBtn = e.target.closest("[data-delete-rec]");
    if (delBtn) {
      const id = delBtn.dataset.deleteRec;
      state.custom.receitas = state.custom.receitas.filter((r) => r.id !== id);
      rebuildCatalog();
      persistState();
      renderRecipesLibrary();
      showToast("Receita removida da biblioteca local");
    }
  });

  // Ingredients view filters & actions
  $("ing-busca").addEventListener("input", renderIngredientsLibrary);
  $("ing-filtro-cat").addEventListener("change", renderIngredientsLibrary);
  $("btn-novo-ingrediente").addEventListener("click", () =>
    openIngredientModal(null)
  );
  $("ing-db-tbody").addEventListener("click", (e) => {
    const btn = e.target.closest("[data-edit-ing]");
    if (btn) openIngredientModal(btn.dataset.editIng);
  });

  // Ingredient modal live validation & submit
  $("form-ing").addEventListener("input", refreshIngredientModalPreview);
  $("form-ing").addEventListener("change", refreshIngredientModalPreview);
  $("form-ing").addEventListener("submit", (e) => {
    e.preventDefault();
    const ing = readIngredientForm();
    const erros = eng
      .validarIngrediente(ing, state.catalogo.constantes)
      .filter((x) => x.nivel === "error");
    if (erros.length) {
      showToast(erros[0].texto);
      return;
    }
    const idx = state.custom.ingredientes.findIndex((i) => i.id === ing.id);
    if (idx >= 0) state.custom.ingredientes[idx] = ing;
    else state.custom.ingredientes.unshift(ing);
    rebuildCatalog();
    populateStaticSelectors();
    syncRecipeHeaderInputs();
    renderAll();
    $("modal-ing").classList.remove("open");
    showToast(`Ingrediente "${ing.nome}" salvo!`);
  });
  $("btn-excluir-ing").addEventListener("click", () => {
    const id = $("f-ing-id").value;
    state.custom.ingredientes = state.custom.ingredientes.filter(
      (i) => i.id !== id
    );
    rebuildCatalog();
    renderAll();
    $("modal-ing").classList.remove("open");
    showToast("Ingrediente removido");
  });

  // Ficha modal
  $("btn-abrir-ficha").addEventListener("click", () => {
    updateFichaPreview();
    $("modal-ficha").classList.add("open");
  });
  document.querySelectorAll("[data-ficha-tab]").forEach((b) => {
    b.addEventListener("click", () => {
      state.fichaTab = b.dataset.fichaTab;
      document
        .querySelectorAll("[data-ficha-tab]")
        .forEach((x) => x.classList.toggle("active", x === b));
      updateFichaPreview();
    });
  });
  $("btn-copiar-ficha").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText($("ficha-preview").value);
      showToast("Copiado para a área de transferência!");
    } catch {
      $("ficha-preview").select();
      document.execCommand("copy");
      showToast("Copiado!");
    }
  });
  $("btn-baixar-ficha").addEventListener("click", () => {
    const ext =
      state.fichaTab === "md"
        ? "md"
        : state.fichaTab === "json"
          ? "json"
          : "txt";
    downloadFile(
      `${slug(state.receita.nome)}.${ext}`,
      $("ficha-preview").value
    );
  });
  $("btn-baixar-html").addEventListener("click", () => {
    downloadFile(
      `${slug(state.receita.nome)}.html`,
      gerarHtmlEstatico(state.analiseAtual),
      "text/html;charset=utf-8"
    );
  });

  // Import JSON
  $("btn-importar-json").addEventListener("click", () =>
    $("file-import-json").click()
  );
  $("file-import-json").addEventListener("change", async (e) => {
    const file = e.target.files && e.target.files[0];
    e.target.value = "";
    if (!file) return;
    try {
      const obj = JSON.parse(await file.text());
      const { receita, avisos } = eng.normalizarReceita(
        obj,
        state.catalogo.constantes
      );
      pushUndo();
      state.receita = receita;
      state.poteId = null;
      syncRecipeHeaderInputs();
      switchView("bancada");
      renderAll();
      showToast(
        avisos.length
          ? `Importada com ${avisos.length} substituição(ões)`
          : `Receita "${receita.nome}" importada!`
      );
    } catch (err) {
      showToast(`Erro ao importar JSON: ${err.message}`);
    }
  });

  // Close modals
  document.querySelectorAll("[data-close-modal]").forEach((b) => {
    b.addEventListener("click", () => {
      $(b.dataset.closeModal).classList.remove("open");
    });
  });
  document.querySelectorAll(".modal-backdrop").forEach((bg) => {
    bg.addEventListener("click", (e) => {
      if (e.target === bg) bg.classList.remove("open");
    });
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      document
        .querySelectorAll(".modal-backdrop.open")
        .forEach((m) => m.classList.remove("open"));
    }
  });
}

init().catch((err) => {
  console.error(err);
  document.body.innerHTML = `<main style="padding:32px;font-family:sans-serif;"><h1>Erro ao carregar o Calda Certa</h1><p>${esc(err.message)}</p></main>`;
});
