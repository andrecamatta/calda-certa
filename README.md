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

Campos opcionais: `id`, `status`, `notas`, `atualizada_em`; e, como
novidade, `processo` (`"frio"`/`"quente"`) e `brix` por item (ver Novidades). `lote_g` é o
peso alvo do lote (informativo; como no app, vale `round(soma dos gramas)` se
ausente); a escala só é aplicada com `--lote`. O formato interno do app
(`name`, `version`, `familyId`, `machineId`, `evaporation`, `items` com
`ingredientId`/`grams`/`locked`) também é aceito. Exemplo em
`exemplos/fior_di_latte.json`.

## Novidades

Funções acrescentadas depois do app original. **Tudo é aditivo**: os
cálculos do app, a ficha `--formato texto`, o `--lote maquina`, o
balanceamento padrão e os arquivos `ingredientes.json`, `receitas.json` e
`perfis.json` não mudaram (os testes de equivalência continuam batendo bit a
bit). As saídas ganham só seções/chaves novas no fim.

Ingredientes, perfis, receitas e constantes novos ficam em
`src/caldacerta/data/novidades.json` (gerado por `tools/gerar_novidades.py`),
o **banco complementar**. As listas mostram só o banco original por padrão;
use `--todos` (`calda ingredientes --todos`, `calda receitas --todos`,
`calda perfis --todos`). Buscas por id/nome olham o banco original primeiro e
só caem no complementar se nada for achado (buscas que já funcionavam não
ficam ambíguas). Campos novos de ingredientes antigos (ex.: regras da goma
guar) ficam em `complementos_ingredientes` e só preenchem o que estiver
ausente, então cópias próprias em `CALDA_DADOS` continuam valendo. Editar um
ingrediente do banco complementar grava em `novidades.json` (no
`CALDA_DADOS`, se definido).

### 1. Calorias e proteína por porção

`analisar` (texto e `--json`, chave `nutricao`), `ficha` (Markdown) e
`pagina` mostram kcal/100 g, e kcal, proteína, gordura e açúcares por porção
(padrão 100 g, `--porcao G`), por pote (máquinas com pote, `--pote ID`) e no
lote. A água evaporada não tem caloria.

```sh
calda analisar rec_proteico_baunilha --porcao 150
calda ficha rec_creami_frosty_agua --pote deluxe
```

kcal por 100 g de ingrediente (`nutricao.kcal_100g`): campo `kcal_100g` do
ingrediente se existir (sobreposição para polióis e açúcares raros); senão
fatores de Atwater sobre a composição: gordura 9, proteína 4, lactose e
açúcares 4, álcool 7 kcal/g; cada açúcar/poliol do perfil com o seu fator
(alulose 0,4; eritritol 0; sorbitol/xilitol/maltitol 2,4; inulina 2;
polidextrose 1; ácidos 3; sucralose/estévia 0); o resto dos outros sólidos a
4 kcal/g, menos `fibra` (2 kcal/g) e `cinzas` (0), campos opcionais
preenchidos para cacau, chocolates, pastas, frutas e gomas. "Açúcares" na
nutrição exclui a alulose (como no rótulo americano).

**Balanceamento light.** `calda balancear ... --objetivo light
[--proteina-min X]` usa o mesmo otimizador, mas o objetivo é: o original +
sair das faixas verdes pesa 10× mais + kcal/100 g (relativas à receita
inicial) × 4 + proteína abaixo de X% com penalidade quase rígida (e a faixa
de proteína sobe para incluir X) + eritritol (ver abaixo). Sem `--objetivo`,
o algoritmo é exatamente o original. `--incluir id1,id2` acrescenta
ingredientes com 0 g (destravados) para o otimizador poder usá-los.

```sh
calda balancear rec_proteico_baunilha --objetivo light                 # 92 → ~64 kcal/100 g, 8/8
calda balancear rec_proteico_baunilha --objetivo light --proteina-min 9 --liberar todos
calda balancear rec_creami_frosty_amendoas --objetivo light \
    --incluir ing_alulose,ing_polidextrose --liberar ing_tamara        # 6/8 → 8/8, 95 → ~67 kcal/100 g
```

### 2. Ninja CREAMi

`mac_creami` ganhou (campos opcionais): `potes` (padrão 16 oz = 473 ml, séries
Original/Breeze/Swirl; Deluxe 24 oz = 709 ml, NC500/NC501; não
intercambiáveis), `enchimento_max_fracao` (0,95: folga para a espuma),
`temp_freezer_c` (−18), `congelamento_h` (24 h; ~36 h se a base foi aquecida)
e `orientacoes` (linha MAX, programas com velocidades diferentes entre
Original, Deluxe e Swirl). Aparecem em `calda maquinas`, na análise, na ficha
e na página.

`--lote pote` (ou `--lote pote:deluxe`) escala a receita para o que cabe no
pote: `volume até a MAX × 0,95 × densidade estimada da calda`. `--lote
maquina` continua usando o `lote_g` (450 g), como no app.

Densidade: `100 / (água/1,0 + gordura/0,93 + sólidos não gordurosos/1,58 +
álcool/0,79)` (H. D. Goff, *Dairy Science and Technology e-book*, Univ. of
Guelph, "Ice cream mix calculations"). Um gelato típico dá ~1,10 g/ml → ~495
g no pote de 16 oz e ~740 g no Deluxe.

Fontes das capacidades: guias de usuários e lojas
([craftingafamily.com](https://www.craftingafamily.com/ninja-creami-deluxe-conversion/),
[abt.com](https://www.abt.com/blog/ninja-creami-vs-deluxe)); 24 h a −18 °C é a
orientação do manual. 36 h para base aquecida e a folga de 95% são
heurísticas.

### 3. Adoçantes sem açúcar

Novos no banco complementar: `ing_eritritol_puro` (POD 65, PAC 280, 0
kcal), `ing_sucralose_pura` (POD 60 000, PAC 86 por 100 g: dose de
décimos de grama por kg), `ing_eritritol_estevia` (adoçante "1:1" de
mercado, modelado como 99,86% eritritol + 0,14% glicosídeos de esteviol;
qualquer "adoçante zero" que seja quase todo eritritol deve ser cadastrado
assim). A alulose (`ing_alulose`) já existia. Novas chaves de perfil de
açúcares em `constantes.json` (acrescentadas ao fim da lista, não mudam nada
existente): `sucralose` (POD 600×, FDA; PAC 342,3/397,6 = 0,86) e
`esteviosideos` (POD 250×, FDA 200–400×; PAC 342,3/967 = 0,35).

O id antigo `ing_eritritol` continua sendo trocado por alulose na carga de
receitas (migração do app), por isso o eritritol novo tem outro id.

**PAC do eritritol × alulose.** O motor calcula o PAC pela massa molar
(depressão do ponto de congelamento é coligativa): eritritol 122 g/mol →
342,3/122,1 = 2,8× a sacarose; alulose 180 g/mol → 1,9×. A afirmação do
vídeo de que "a alulose abaixa mais o ponto de congelamento que o eritritol"
contradiz essa conta por grama. O que acontece na prática é outra coisa: o
eritritol é pouco solúvel no frio (~37% m/m a 25 °C, bem menos perto de 0 °C;
de Cock, *Erythritol*, em *Sweeteners and Sugar Alternatives in Food
Technology*, 2012) e, na fase não congelada, recristaliza; o cristal sai da
solução e para de amaciar, e a massa fica dura e arenosa. Tratamos assim:
mantemos o PAC molar e **alertamos acima de 6% de eritritol na calda**
(heurística), sugerindo trocar parte por alulose.

**Eritritol e saúde.** O app original tinha removido o eritritol por isso;
ele voltou com limites:

- **Alerta forte** quando o lote, o pote ou a porção tem **≥ 30 g** de
  eritritol: é a dose em que, em estudo de intervenção, o eritritol aumentou
  a reatividade das plaquetas (Witkowski et al., *Nature Medicine* 29, 2023;
  replicado contra glicose em Witkowski et al., *Arterioscler Thromb Vasc
  Biol*, 2024). É associação + efeito plaquetário, **não causalidade
  provada**; evite se tiver risco cardiovascular.
- **Alerta de ingestão diária** quando uma porção passa de **1/3 da IDA** da
  EFSA (0,5 g/kg de peso/dia, reavaliação do E 968, 2023): 11,7 g para 70 kg;
  `--peso-kg` muda o peso.
- **Balanceamento light**: penalidade pequena por % de eritritol (prefere
  alulose e outros açúcares) e **teto rígido** de 1/3 da IDA por porção.
- A ficha Markdown e a página mostram os gramas de eritritol por porção
  sempre que houver (o `--formato texto` não muda).

**Tolerância digestiva por porção** (alerta quando Σ g/limiar ≥ 1, também
para o pote inteiro): eritritol 25 g (EFSA 2023; Storey et al., *Eur J Clin
Nutr* 2007), alulose 28 g (0,4 g/kg × 70 kg; Han et al., *Nutrients* 2018),
sorbitol 10 g, xilitol 20 g, maltitol 30 g (Mäkinen, *Int J Dent* 2016),
inulina 10 g (Bonnema et al., *J Am Diet Assoc* 2010). São limiares
populacionais aproximados; a sensibilidade individual varia muito.

### 4. Regras de estabilizantes

Campos opcionais de ingrediente: `dose_max_pct` (% da calda), `ativacao`
(`"frio"` | `"quente"`) e `defeito_excesso`. Receita: campo opcional
`processo` (`"frio"` | `"quente"`; ausente = sem alerta), ou `--processo`.
Alertas: dose acima da máxima (com o defeito) e estabilizante de ativação a
quente num processo a frio.

| ingrediente | dose máx. | ativação | defeito em excesso |
|---|---:|---|---|
| goma guar (`ing_goma_guar`, via complemento) | 0,3% | frio | fibrosa/elástica |
| goma xantana (`ing_goma_xantana`, nova) | 0,1% | frio | viscosa/babenta |
| goma alfarroba/LBG (`ing_goma_alfarroba`, nova) | 0,3% | quente (~80 °C) | gomosa/elástica |

Fonte: Goff & Hartel, *Ice Cream*, 7ª ed. (2013), cap. 4; as doses máximas
são heurísticas de uso. Pela CLI: `calda ingrediente editar ID
--dose-max-pct 0.2 --ativacao frio --defeito-excesso "..."` (também
`--kcal-100g`, `--fibra`, `--cinzas`, `--caseina`, `--fonte`).

### 5. Ingredientes proteicos

Novos: `ing_whey_caseina` (blend 50/50, caseína 37,5%),
`ing_leite_uf_proteico` (ultrafiltrado, 5,4% de proteína),
`ing_leite_1` (1%, USDA), `ing_bebida_amendoas` (sem açúcar, USDA),
`ing_proteina_ervilha`, `ing_proteina_chocolate` (whey sabor chocolate com
sucralose). O whey isolado já existia (agora com `caseina: 0`).

- **Caseína**: campo `caseina` ou, em lácteos (SNG > 0), 80% da proteína
  (Fox & McSweeney, *Dairy Chemistry and Biochemistry*). Alerta acima de
  **4% de caseína na calda** (heurística: a massa fica pastosa/borrachuda).
- **Água livre**: alerta com sólidos totais **abaixo de 25%** (sorvetes
  clássicos têm 36–42%, Goff & Hartel 2013): base só de bebida de amêndoas,
  por exemplo, vira gelo.

### 6. Brix medido

Item de receita com `"brix": 12.5` (ou `--brix ing_polpa_manga=12.5`,
repetível) corrige o açúcar daquela fruta nesta receita: açúcares = Brix −
ácidos do perfil (o refratômetro também lê os ácidos), a diferença sai/entra
da água, os açúcares do perfil são escalados na mesma proporção e POD/PAC
recalculados. Vale para análise, balanceamento, ficha (inclusive texto) e
página. Duas leituras diferentes para o mesmo ingrediente na receita dão
erro.

```sh
calda analisar rec_sorbet_manga --brix ing_polpa_manga=12
```

### 7. Lembretes de processo

`ficha --formato md` e `pagina` terminam com uma lista: provar a calda (deve
parecer um pouco doce demais, o frio tira doçura), misturar os secos antes,
bater ~90 s com mixer; no Creami, esperar ~15 min a espuma baixar e congelar
24 h (36 h se aquecida); mix-in de chocolate derretido com um pouco de óleo
(no Creami ou quando a receita tem chocolate).

### 8. Ingredientes de "comida de verdade" para o Creami

Novos (composição USDA FoodData Central SR Legacy ou TACO 4ª ed.; fibra conta
em outros sólidos): `ing_tamara` (Medjool; açúcar quase invertido),
`ing_nozes`, `ing_castanha_caju`, `ing_couve_flor` (arroz de couve-flor),
`ing_pure_abobora`, `ing_acai_polpa` (TACO), `ing_cafe_coado`. Bebida de
aveia e cacau em pó já existiam. Fruta-do-monge não foi incluída (decisão do
usuário).

### 9. Perfil "Creami Proteico de Comida de Verdade (fit)"

`fam_creami_fit`: gordura 2–7%, proteína 5–10%, açúcares 5–12%, SNG 0–10%,
outros sólidos 4–14%, sólidos totais 22–32%, POD 90–180, PAC 180–240
(heurísticas; PAC como o perfil Proteico do app, pensado para o Creami a −18
°C; POD alto porque proteína em pó vem com sucralose). Pelos padrões
clássicos essas bases ficam muito longe de um gelato (pouco açúcar e pouco
sólido = bloco duro e cristalino a −18 °C); a lâmina do Creami e o Re-spin
com um fio de leite compensam. O perfil indica `referencia_classica:
fam_branca`, e a análise mostra a mesma receita contra o gelato clássico.

Receitas: `rec_creami_frosty_amendoas` (o "chocolate frosty" do vídeo: 2½
tâmaras, 8 metades de noz, ¾ xícara de couve-flor, 1 scoop de proteína de
chocolate, bebida de amêndoas até 1 pote; 6/8, PAC 165) e
`rec_creami_frosty_agua` (2 tâmaras, água, 14 g de alulose, 10 g de
polidextrose; 8/8, ~80 kcal/100 g).

**Correções de um ingrediente.** Para métricas fora da faixa, a análise
calcula quantos gramas de UM ingrediente (alulose, eritritol, dextrose para
PAC; creme ou pasta de amendoim para gordura; leite em pó ou polidextrose
para sólidos...) levam a métrica a 1/4 da faixa, simula a receita com essa
adição e mostra a nova faixa verde e as kcal. Só aparecem as que não pioram
a contagem da faixa verde.

```sh
calda analisar rec_creami_frosty_amendoas
#   PAC (maciez) 165 (abaixo da faixa): +8,6 g de Alulose → 195, faixa verde 7/8, 95 → 94 kcal/100 g
```

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
(arredondamentos com a semântica do JavaScript) e `nutricao` (novidades:
kcal, densidade/pote, Brix, alertas, correções, objetivo light). Para usar o
banco complementar na biblioteca: `dados.mapa_ingredientes_todos()`.

## Arquivos de dados

Em `src/caldacerta/data/` (JSON editável, UTF-8):

| arquivo | conteúdo |
|---|---|
| `ingredientes.json` | os 45 ingredientes do banco (composição em % do ingrediente) |
| `receitas.json` | as 21 receitas de exemplo |
| `maquinas.json` | 4 máquinas: ajuste de PAC, temperatura de referência, lote, dicas |
| `perfis.json` | 11 perfis/estilos com as faixas alvo das 8 métricas |
| `constantes.json` | coeficientes POD/PAC de cada açúcar, lactose e álcool; curva de congelamento; rótulos e dicas das métricas; substituições de ingredientes removidos |
| `novidades.json` | banco complementar (Novidades): 18 ingredientes, 1 perfil, 2 receitas, complementos de ingredientes antigos e as constantes das funções novas, com fontes |

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
outros_soluveis, sucralose, esteviosideos` (as duas últimas são novidades).

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

## Interface Web (GitHub Pages)

A pasta `web/` contém uma interface web interativa estática (HTML/CSS/ES modules,
sem dependências de build) que roda o mesmo motor (`web/engine.js`) e os mesmos
dados (`web/data/bundle.json`, gerado a partir de `src/caldacerta/data/` via
`python3 tools/sync_web_data.py`), com persistência local em `localStorage`.

Para testar localmente:

```sh
python3 tools/sync_web_data.py
python3 -m http.server --directory web 8080
```

O workflow `.github/workflows/pages.yml` sincroniza o `bundle.json` e publica
`web/` automaticamente no **GitHub Pages** a cada push em `main`.

## Estrutura

```
src/caldacerta/       motor, dados, CLI, ficha, página
src/caldacerta/data/  arquivos de dados (JSON)
web/                  interface web interativa (GitHub Pages)
tools/                extração, harness em node e sync_web_data.py
tests/                testes (equivalência + unidade + CLI + motor JS) e fixtures
exemplos/             arquivo de receita de exemplo
```
