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
│   ├── notebook_portscan.ipynb     # Port Scan
│   ├── notebook_ddos.ipynb         # DDoS
│   ├── notebook_ddos_PCA.ipynb     # DDoS com redução de dimensionalidade (PCA)
│   ├── notebook_web.ipynb          # Ataques Web (Brute Force, XSS, SQL Injection)
│   └── archive/                    # Notebooks antigos, mantidos só como histórico
├── results/
│   └── modelos/                    # Modelos treinados e artefatos (não versionados)
├── src/                            # Código Python reutilizável
├── README.md
└── requirements.txt
```

## Dados

Os CSVs do [CIC-IDS-2017](https://www.unb.ca/cic/datasets/ids-2017.html) devem ser colocados em `datas/raw/` com os nomes abaixo:

| Notebook | Arquivo esperado em `datas/raw/` |
| --- | --- |
| `notebook_portscan.ipynb` | `Friday-WorkingHours-Afternoon-PortScan.pcap_ISCX.csv` |
| `notebook_ddos.ipynb` / `notebook_ddos_PCA.ipynb` | `DDoS.csv` (renomeado de `Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv`) |
| `notebook_web.ipynb` | `Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv` |

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

## Pipeline dos Notebooks

Todos os notebooks seguem o mesmo fluxo:

1. Carregamento do CSV e exploração (shape, tipos).
2. Limpeza: remoção de espaços nos nomes das colunas, infinitos → NaN, remoção de NaN e duplicatas.
3. Codificação do `Label` com `LabelEncoder`.
4. Divisão treino/teste (80/20, `random_state=42`).
5. Treino e avaliação de Decision Tree, Random Forest, XGBoost, SVM Linear e MLP.
6. Matrizes de confusão, importância de features e comparação final de acurácia.

No `notebook_ddos_PCA.ipynb` os dados são padronizados (`StandardScaler`) e reduzidos com PCA (95% da variância) antes do treino; a importância é exibida por componente principal.

## Boas Práticas

- Não comite dados brutos no repositório (`datas/` e `results/modelos/` estão no `.gitignore`).
- Use `datas/processed/` apenas para dados preparados.
- Documente cada experimento nos notebooks.
- Código compartilhado entre notebooks (limpeza, avaliação) deve ir para `src/`.

## Contato

- Projeto mantido por Guilherme Martins.
