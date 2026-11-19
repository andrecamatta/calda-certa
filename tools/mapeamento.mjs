// Mapeamento dos nomes de campo do app original (inglês, minificado) para os
// nomes usados nos arquivos de dados em português. Documentado no README.
export const CAMPOS_INGREDIENTE = {
  id: "id",
  name: "nome",
  category: "categoria",
  water: "agua",
  fat: "gordura",
  protein: "proteina",
  sugars: "acucares",
  msnf: "sng",
  lactose: "lactose",
  otherSolids: "outros_solidos",
  alcohol: "alcool",
  pod: "pod",
  pac: "pac",
  cost: "custo_kg",
  autoPodPac: "pod_pac_auto",
  profile: "perfil_acucares",
  note: "nota",
};

export const CHAVES_PERFIL_ACUCAR = {
  sucrose: "sacarose",
  glucose: "glicose",
  fructose: "frutose",
  maltose: "maltose",
  trehalose: "trealose",
  allulose: "alulose",
  glucoseSyrup: "solidos_glicose",
  maltodextrin: "maltodextrina",
  erythritol: "eritritol",
  sorbitol: "sorbitol",
  xylitol: "xilitol",
  maltitol: "maltitol",
  inulin: "inulina",
  polydextrose: "polidextrose",
  citricAcid: "acidos_fruta",
  lacticAcid: "acido_latico",
  salt: "sal",
  soluble: "outros_soluveis",
};

export const GRUPOS_ACUCAR = { sugars: "acucares", other: "outros_solidos", msnf: "sng" };

export const METRICAS = {
  water: "agua",
  fat: "gordura",
  protein: "proteina",
  sugars: "acucares",
  msnf: "sng",
  otherSolids: "outros_solidos",
  totalSolids: "solidos_totais",
  alcohol: "alcool",
  lactose: "lactose",
  msnfEq: "sng_lactose",
  pod: "pod",
  pac: "pac",
  cost: "custo",
};

export const traduzirPerfilAcucar = (p) =>
  Object.fromEntries(Object.entries(p || {}).map(([k, v]) => [CHAVES_PERFIL_ACUCAR[k], v]));

export const traduzirFaixas = (r) =>
  Object.fromEntries(Object.entries(r).map(([k, v]) => [METRICAS[k], [...v]]));
