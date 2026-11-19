# Calda Certa

Balanceamento de sorvetes, gelatos e sorbets: biblioteca Python + CLI `calda`.

Dada uma receita (ingredientes em gramas), uma máquina e um perfil (estilo),
o Calda Certa calcula a composição (água, gordura, proteína, açúcares, SNG,
outros sólidos, sólidos totais), doçura (POD) e maciez (PAC), compara com as
faixas do perfil ("faixa verde", ex.: 8/8), checa o risco de arenosidade
(lactose), estima o ponto de congelamento, a temperatura boa para servir e a
fração de água congelada na temperatura da máquina, calcula o custo por kg e
por lote, escala a receita e faz auto-balanceamento respeitando ingredientes
travados.

## Origem

Reconstruído em 2026-11-19 a partir do artefato **Calda Certa** do claude.ai
(app React, sem código-fonte original disponível). O trecho do bundle
compilado com os dados e o motor de cálculo está preservado literalmente em
`tools/referencia/motor_original.js`; dados e fixtures de teste são gerados
a partir dele. A interface React não foi portada: a CLI e o relatório HTML
cobrem as mesmas informações.

## Instalação

Requer Python ≥ 3.11 e [uv](https://docs.astral.sh/uv/). Sem dependências de
execução (só biblioteca padrão); `pytest` para os testes.

```sh
uv sync
uv run calda --help
uv run pytest -q
```

## CLI

Todos os comandos aceitam `--json` (antes ou depois do subcomando). Com
`--json`, a saída vai para stdout em JSON; erros vão para stderr como
`{"erro": "..."}` com código de saída 1. Avisos (ex.: ingrediente
substituído) aparecem em stderr no modo texto e no campo `avisos` no JSON.

Onde se pede uma receita, aceita-se um arquivo `.json`, `-` (stdin) ou o id
(ou trecho único do nome) de uma receita da biblioteca. Máquina e perfil
também aceitam id ou trecho único do nome.

```sh
# Banco de ingredientes
calda ingredientes
calda ingredientes --busca leite --familia Lácteos
calda ingrediente mostrar ing_leite_po_desn
calda ingrediente adicionar --nome "Xarope de Bordo" --categoria Açúcares \
    --agua 32 --acucares 67 --outros-solidos 1 \
    --perfil-acucares "sacarose=60,glicose=4,frutose=3" --custo-kg 120
calda ingrediente editar ing_custom_xarope_de_bordo --custo-kg 99
calda ingrediente remover ing_custom_xarope_de_bordo        # --forcar se usado em receitas

# Biblioteca, máquinas e perfis
calda receitas [--busca X] [--perfil fam_branca]
calda receita mostrar rec_fiordilatte > fior.json
calda receita salvar fior.json [--id rec_meu_fior]
calda receita remover rec_meu_fior
calda maquinas
calda perfis

# Análise (dashboard completo)
calda analisar rec_fiordilatte
calda analisar fior.json --maquina mac_creami --perfil fam_branca --lote 450 --evaporada 0
calda analisar fior.json --lote maquina          # escala para o lote da máquina

# Auto-balanceamento
calda balancear fior.json --maquina mac_vitrine --travar ing_leite_int,ing_goma_guar -o fior_v2.json
calda balancear fior.json --liberar todos         # ignora as travas do arquivo

# Ficha técnica e página
calda ficha rec_pistache                         # Markdown (padrão), boa para nota
calda ficha rec_pistache --formato texto         # idêntico ao botão "copiar ficha" do app
calda ficha rec_pistache -o pistache.md
calda pagina rec_pistache -o pistache.html       # HTML estático, CSS embutido, sem JS
```

### Formato do arquivo de receita

```json
{
  "nome": "Fior di Latte",
  "versao": "V1.0",
  "maquina": "mac_kitchenaid_freezer",
  "perfil": "fam_branca",
  "lote_g": 1000,
  "evaporada_g": 0,
  "itens": [
    {"ingrediente": "ing_leite_int", "gramas": 585, "travado": false},
    {"ingrediente": "ing_goma_guar", "gramas": 1.5, "travado": true}
  ]
}
```

Campos opcionais: `id`, `status`, `notas`, `atualizada_em`. `lote_g` é o
peso alvo do lote (informativo; como no app, vale `round(soma dos gramas)` se
ausente); a escala só é aplicada com `--lote`. O formato interno do app
(`name`, `version`, `familyId`, `machineId`, `evaporation`, `items` com
`ingredientId`/`grams`/`locked`) também é aceito. Exemplo em
`exemplos/fior_di_latte.json`.

## Biblioteca Python

```python
from caldacerta import dados, motor
ings = dados.mapa_ingredientes()
r = dados.achar(dados.receitas(), "rec_fiordilatte", "receita")
maq = dados.achar(dados.maquinas(), "mac_creami", "máquina")
perf = dados.achar(dados.perfis(), "fam_branca", "perfil")
z = motor.avaliar(r["itens"], ings, maq["temp_servir"], evaporada=0)
faixas = motor.faixas_alvo(perf, maq)
print(motor.conformidade(z["metricas"], faixas)["ideal"])
print(motor.balancear(r["itens"], ings, faixas)["itens"])
```

Módulos: `motor` (cálculos), `dados` (arquivos JSON), `receita` (arquivo de
receita), `relatorio` (análise completa), `ficha`, `pagina`, `cli`, `jsnum`
(arredondamentos com a semântica do JavaScript).

## Arquivos de dados

Em `src/caldacerta/data/` (JSON editável, UTF-8):

| arquivo | conteúdo |
|---|---|
| `ingredientes.json` | os 45 ingredientes do banco (composição em % do ingrediente) |
| `receitas.json` | as 21 receitas de exemplo |
| `maquinas.json` | 4 máquinas: ajuste de PAC, temperatura de referência, lote, dicas |
| `perfis.json` | 11 perfis/estilos com as faixas alvo das 8 métricas |
| `constantes.json` | coeficientes POD/PAC de cada açúcar, lactose e álcool; curva de congelamento; rótulos e dicas das métricas; substituições de ingredientes removidos |

**Onde as alterações são gravadas.** Se a variável de ambiente `CALDA_DADOS`
apontar para um diretório, cada arquivo é lido de lá quando existir (senão,
do pacote) e toda gravação da CLI vai para lá; um agente pode editar esses
JSON diretamente. Sem `CALDA_DADOS`, a CLI grava nos arquivos do próprio
pacote (num checkout, as mudanças aparecem no `git diff`).

### Como adicionar um ingrediente

Pela CLI (valida a soma da composição e recalcula POD/PAC):

```sh
calda ingrediente adicionar --nome "Pasta de Castanha de Caju" --categoria "Pastas & Nuts" \
  --agua 2 --gordura 46 --proteina 18 --acucares 6 --outros-solidos 46 \
  --perfil-acucares "sacarose=6" --custo-kg 110
```

Ou editando `ingredientes.json`. Regras (as mesmas do formulário do app):

- `agua + gordura + acucares + sng + outros_solidos + alcool` deve somar 100 (±0,5);
- `acucares` são os açúcares **sem** lactose; a lactose e a proteína do leite
  ficam dentro de `sng` (sólidos não gordurosos do leite);
- `pod`/`pac` em pontos por 100 g do ingrediente (sacarose = 100);
- com `pod_pac_auto: true`, POD/PAC vêm de `perfil_acucares` (g por 100 g de
  cada açúcar/poliol/ácido/sal), da lactose e do álcool; pela CLI isso é
  recalculado ao salvar (como no app). Editando o JSON à mão, rode
  `calda ingrediente editar ID` sem outras opções para recalcular;
- `custo_kg` em R$/kg.

Chaves aceitas em `perfil_acucares`: `sacarose, glicose, frutose, maltose,
trealose, alulose, solidos_glicose, maltodextrina, eritritol, sorbitol,
xilitol, maltitol, inulina, polidextrose, acidos_fruta, acido_latico, sal,
outros_soluveis`.

### Mapeamento de campos (app original → arquivos)

| app | arquivo | app | arquivo |
|---|---|---|---|
| `name` | `nome` | `otherSolids` | `outros_solidos` |
| `category` | `categoria` | `alcohol` | `alcool` |
| `water` | `agua` | `cost` | `custo_kg` |
| `fat` | `gordura` | `autoPodPac` | `pod_pac_auto` |
| `protein` | `proteina` | `profile` | `perfil_acucares` |
| `sugars` | `acucares` | `note` | `nota` |
| `msnf` | `sng` | `totalSolids` | `solidos_totais` |
| `msnfEq` | `sng_lactose` | `ranges` | `faixas` |
| `familyId` | `perfil` | `machineId` | `maquina` |
| `pacOffset` | `ajuste_pac` | `serveTemp` | `temp_servir` |
| `batch` | `lote_g` | `batchNote` / `tips` | `nota_lote` / `dicas` |
| `items[].ingredientId/grams/locked` | `itens[].ingrediente/gramas/travado` | `evaporation` | `evaporada_g` |

O mapeamento completo (incluindo as chaves do perfil de açúcares) está em
`tools/mapeamento.mjs`. Os ingredientes gravados são os **efetivos** do app
(lista `lr`: banco base com perfis de açúcar aplicados e POD/PAC recalculados).

## Como a equivalência é verificada

1. `node tools/extrair_referencia.mjs caminho/all.js` recorta do bundle
   compilado o trecho de dados + motor e grava `tools/referencia/motor_original.js`.
2. `node tools/gerar_dados.mjs` carrega esse trecho em `node:vm` e gera os
   JSON de `src/caldacerta/data/`.
3. `node tools/gerar_fixtures.mjs` executa as funções originais
   (`rr`, `vg`, `Rl`, `Ig`, `Dl`, `Cg`, `Sg`, `Bl`, `Dc`, `Fc`, mais cópias
   literais da lógica que vivia nos componentes React: status/contagem da faixa
   verde, "Escalonar" e o texto da ficha técnica) e grava
   `tests/fixtures/referencia_js.json`: as 21 receitas + 60 receitas
   aleatórias (semente fixa) × 4 máquinas × com/sem água evaporada; a
   conformidade contra os 11 perfis; escalonamentos; fichas; 169
   auto-balanceamentos (cada receita em cada máquina, com evaporação, com
   travas, com perfil trocado, aleatórias e casos de erro); a curva de
   congelamento em grade; POD/PAC automáticos e avisos de validação.
4. `tests/test_equivalencia.py` compara o motor Python com esses resultados
   (tolerância 1e-6). Na prática os números saem **idênticos bit a bit**: a
   ordem das operações em ponto flutuante foi mantida, `Math.round` e
   `toFixed` são reproduzidos em `jsnum.py` (arredondamento meio-para-cima, não
   o meio-para-par do Python), e os gramas do auto-balanceamento e o texto da
   ficha batem exatamente.

## Leituras feitas onde o app era ambíguo

- **Lote / escala.** No app, o peso alvo só é aplicado no botão "Escalonar",
  com fator `alvo / peso final` (já descontada a água evaporada) e
  arredondamento a 0,1 g por item. Com evaporação, o peso final escalado
  não fica exatamente no alvo; reproduzido assim. Na CLI, `--lote N` aplica
  essa escala antes da análise; `--lote maquina` usa o lote da máquina (o app
  preenche o alvo com ele ao trocar de máquina).
- **Custo do lote** é o custo dos ingredientes da receita (como "Lote atual"
  no app), incluindo a água que evapora.
- **Auto-balanceamento** usa as faixas do perfil com o ajuste de PAC da
  máquina e ignora a temperatura de serviço (como o app, que avalia a −12 °C
  dentro do otimizador; a temperatura não afeta as métricas).
- **Lista de receitas** (`calda receitas`) mostra métricas avaliadas a
  −12 °C como a biblioteca do app, mais a faixa verde na máquina/perfil
  próprios da receita.
- **Máquina/perfil ausentes** caem no primeiro da lista, como o app.
- **Ingredientes removidos do banco** (`ing_neutro_5`, `ing_creme_20`,
  `ing_eritritol`, `ing_maltodextrina`) são trocados pelos substitutos com o
  fator de gramas, como na migração do app, com aviso. Ingrediente
  desconhecido conta só no peso (como no app).
- **Receita nova salva** entra com status "Em Teste" e notas padrão
  ("Formulada na bancada do Calda Certa."); id gerado como
  `rec_<nome>_<versão>` em vez de `rec_<timestamp>`. Ingrediente novo:
  `ing_custom_<nome>` em vez de `ing_custom_<timestamp>` (o prefixo é o
  mesmo que o app usa para preservar cadastros do usuário) e entra no topo
  do banco.
- **Ficha em Markdown** tem o mesmo conteúdo da ficha do app, mais o status
  de cada métrica e as dicas de ajuste exibidas no dashboard;
  `--formato texto` é idêntico ao texto copiado pelo app.
- Não portado: estado no `localStorage`, duplicar versão (V1 → V2) e edição
  de perfis pela interface (edite `perfis.json`).

## Estrutura

```
src/caldacerta/       motor, dados, CLI, ficha, página
src/caldacerta/data/  arquivos de dados (JSON)
tools/                extração e harness em node (fonte: tools/referencia/motor_original.js)
tests/                testes (equivalência + unidade + CLI) e fixtures
exemplos/             arquivo de receita de exemplo
```
