# IDS - Network Intrusion Detection

Sistema de Detecção de Intrusões (IDS) construído com aprendizado de máquina usando o dataset CIC-IDS-2017.

## Sobre o Projeto

Este repositório implementa um pipeline de análise de tráfego de rede para detectar ataques cibernéticos. O objetivo é usar o dataset CIC-IDS-2017 para:

- extrair e entender padrões de tráfego normal e malicioso;
- limpar, tratar e transformar features de rede;
- treinar e avaliar modelos de classificação;
- comparar desempenho de diferentes algoritmos;
- documentar resultados e importância das variáveis.

## Tecnologias Utilizadas

- Python 3
- scikit-learn
- XGBoost
- pandas
- NumPy
- matplotlib
- seaborn
- Jupyter Notebook

## Estrutura do Repositório

```
IDS-Network-Intrusion-Detection/
├── datas/                          # Dados do projeto (não versionados)
│   ├── raw/                        # CSVs originais do CIC-IDS-2017
│   └── processed/                  # Dados tratados e preparados para treino
├── notebooks/                      # Jupyter Notebooks de análise
│   ├── 02_selecao_features.ipynb   # Seleção de features dos dois modelos
│   ├── 03_modelo_binario.ipynb     # Modelo 1: BENIGN x Ataque
│   ├── 04_modelo_tipo_ataque.ipynb # Modelo 2: tipo de ataque
│   ├── 05_pipeline_completo.ipynb  # Avaliação dos dois modelos juntos
│   ├── notebook_portscan.ipynb     # Port Scan
│   ├── notebook_ddos.ipynb         # DDoS
│   ├── notebook_ddos_PCA.ipynb     # DDoS com redução de dimensionalidade (PCA)
│   ├── notebook_web.ipynb          # Ataques Web (Brute Force, XSS, SQL Injection)
│   └── archive/                    # Notebooks antigos, mantidos só como histórico
├── results/
│   └── modelos/                    # Modelos finais (.ubj) e metadados (.json)
├── src/
│   ├── data.py                     # Carregamento, limpeza e divisão treino/teste
│   ├── features.py                 # Seleção de features (SHAP, correlação, curva top-k)
│   ├── pipeline.py                 # Detecção em duas etapas (IDSPipeline)
│   ├── flows.py                    # Pacotes -> fluxos com as features do CIC-IDS-2017
│   ├── storage.py                  # Banco SQLite das detecções
│   ├── detect.py                   # Classificação de lotes de fluxos e gravação no SQLite
│   ├── live.py                     # Captura ao vivo com tcpdump
│   ├── report.py                   # Resumo das execuções
│   ├── ids.py                      # Linha de comando (./ids)
│   └── slice_pcap.py               # Recorta uma janela de tempo de um PCAP
├── tests/                          # Testes (pytest)
├── ids                             # Atalho: ./ids <comando>
├── README.md
└── requirements.txt
```

## Dados

Os CSVs do [CIC-IDS-2017](https://www.unb.ca/cic/datasets/ids-2017.html) devem ser colocados em `datas/raw/` com os nomes abaixo:

| Arquivo esperado em `datas/raw/` | Arquivo original do CIC-IDS-2017 |
| --- | --- |
| `PortScan.csv` | `Friday-WorkingHours-Afternoon-PortScan.pcap_ISCX.csv` |
| `DDos.csv` | `Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv` |
| `WebAttacks.csv` | `Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv` |

Os notebooks 02 a 05 usam os três arquivos juntos; os notebooks `notebook_*.ipynb` usam um arquivo cada.

Os nomes diferenciam maiúsculas de minúsculas no Linux (`DDos.csv` ≠ `DDoS.csv`).

Os notebooks leem os dados a partir de `../datas`, então devem ser executados de dentro da pasta `notebooks/`.

## Como Executar

1. Clone o repositório:
   ```bash
   git clone git@github.com:Guilhermedantass/IDS-Network-Intrusion-Detection.git
   cd IDS-Network-Intrusion-Detection
   ```

2. Crie o ambiente virtual e instale as dependências:
   ```bash
   python -m venv .venv
   source .venv/bin/activate        # Linux / macOS
   # .\.venv\Scripts\activate       # Windows
   pip install -r requirements.txt
   ```

3. Coloque os CSVs em `datas/raw/` (veja a seção **Dados**).

4. Abra o Jupyter e execute os notebooks em `notebooks/`:
   ```bash
   jupyter notebook
   ```

## Modelo de Detecção (2 etapas)

```
fluxo -> Modelo 1 (BENIGN x Ataque) -> Modelo 2 (tipo) -> DDoS / PortScan / WebAttack / SQLInjection / Desconhecido
```

Os dois modelos são XGBoost treinados com os três CSVs juntos (`src/data.py`):

- **Limpeza:** infinitos e NaN removidos, duplicatas removidas **antes** da divisão treino/teste (evita vazamento).
- **Features removidas por decisão de domínio:** colunas constantes, colunas idênticas a outras e atalhos
  que identificam o ambiente da captura em vez do ataque (`Destination Port`, `Init_Win_bytes_*`).
- **Flags TCP removidas:** o CICFlowMeter que gerou o dataset calcula as colunas de flags errado (ex.: os fluxos
  de port scan só têm `PSH`, nunca o `RST` das portas fechadas), e um extrator correto não reproduz esses valores.
- **Classes:** BruteForce e XSS viram `WebAttack`, porque as features de fluxo não distinguem os dois.
- **Seleção de features** (notebook 02, só no treino): ranking por SHAP, remoção de features com correlação > 0,95
  e curva de F1 x número de features.
- **Modelo 1:** limiar de probabilidade escolhido para favorecer o recall de ataques (F2).
- **Modelo 2:** treinado só com ataques, com pesos por classe para o desequilíbrio; confiança baixa vira `Desconhecido`.

Uso:

```python
from src.data import clean_features
from src.pipeline import IDSPipeline

ids = IDSPipeline.load()
resultado = ids.predict(clean_features(fluxos))   # attack_prob, is_attack, attack_type, type_confidence
```

Para retreinar, execute os notebooks 02, 03, 04 e 05 nessa ordem.

## Usando o IDS

Tudo passa pelo comando `./ids` (usa o Python do `.venv` automaticamente):

```bash
./ids ao-vivo                 # monitora a placa de rede e mostra alertas em tempo real (Ctrl+C para parar)
./ids ao-vivo -i lo --duracao 60
./ids teste-nmap              # escaneia o próprio PC (127.0.0.1) e mostra se o IDS detectou
./ids teste-nmap --syn        # inclui o scan SYN (sudo nmap -sS)
./ids arquivo captura.pcap    # analisa um arquivo de captura
./ids resumo                  # resultado da última execução
./ids resumo --lista          # todas as execuções
```

`ao-vivo` e `teste-nmap` capturam com `tcpdump`, por isso pedem a senha do `sudo`. Os resultados ficam em
`results/ids.db` (use `--db` para outro arquivo).

```
tcpdump / PCAP -> src/flows.py (features de fluxo) -> IDSPipeline -> SQLite -> alertas e resumo
```

No modo ao vivo, um fluxo também é encerrado após 10 s sem pacotes (o CICFlowMeter original só encerra no
FIN ou após 120 s); sem isso, um port scan só geraria alerta 2 minutos depois.

O extrator de fluxos (`src/flows.py`) reproduz a semântica do CICFlowMeter em Java que gerou o CIC-IDS-2017,
incluindo os bugs dele, conferidos contra os CSVs:

- tempos em microssegundos, tamanho = payload, desvio padrão amostral, fim do fluxo no primeiro FIN ou após 120 s;
- o padding do Ethernet (quadros com menos de 60 bytes) conta como payload;
- o primeiro pacote entra duas vezes em `Packet Length Mean/Std/Variance` e `Average Packet Size`;
- `act_data_pkt_fwd` ignora o primeiro pacote e o padding.

O pacote `cicflowmeter` do PyPI não é usado porque calcula várias features em outra escala.

O banco tem duas tabelas: `runs` (uma por execução) e `flows` (um fluxo por linha, com a previsão; as
features ficam salvas em JSON só para os fluxos classificados como ataque).

### PCAPs do CIC-IDS-2017

Os PCAPs originais (página do dataset, pasta `PCAPs/`, exige cadastro) têm vários GB por dia. Para recortar só a
janela do ataque, inclusive durante o download:

```bash
curl -L <url-do-pcap> | python -m src.slice_pcap - datas/raw/recorte.pcap \
    --inicio 2017-07-07T13:50-03:00 --fim 2017-07-07T14:40-03:00
```

## Testes

```bash
pytest
```

## Notebooks por Ataque (primeira etapa)

Os notebooks `notebook_*.ipynb` seguem o mesmo fluxo:

1. Carregamento do CSV e exploração (shape, tipos).
2. Limpeza: remoção de espaços nos nomes das colunas, infinitos → NaN, remoção de NaN e duplicatas.
3. Codificação do `Label` com `LabelEncoder`.
4. Divisão treino/teste (80/20, `random_state=42`).
5. Treino e avaliação de Decision Tree, Random Forest, XGBoost, SVM Linear e MLP.
6. Matrizes de confusão, importância de features e comparação final de acurácia.

No `notebook_ddos_PCA.ipynb` os dados são padronizados (`StandardScaler`) e reduzidos com PCA (95% da variância) antes do treino; a importância é exibida por componente principal.

## Boas Práticas

- Não comite dados brutos no repositório (`datas/` está no `.gitignore`). De `results/modelos/` só os modelos finais (`.ubj`) e metadados (`.json`) são versionados.
- Use `datas/processed/` apenas para dados preparados.
- Documente cada experimento nos notebooks.
- Código compartilhado entre notebooks (limpeza, avaliação) deve ir para `src/`.

## Contato

- Projeto mantido por Guilherme Martins.
