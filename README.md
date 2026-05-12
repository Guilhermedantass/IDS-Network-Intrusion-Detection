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
IDS - Network Intrusion Detection/
├── .venv/                      # Ambiente virtual Python
├── datas/                      # Dados do projeto
│   ├── raw/                    # Dados brutos (originais)
│   └── processed/              # Dados processados e tratados
├── notebooks/                  # Jupyter Notebooks de análise
│   ├── notebook_ddos.ipynb      # Análise de DDoS
│   ├── notebook_portscan.ipynb  # Análise de Port Scan
│   └── notebook_web.ipynb      # Análise de ataques Web
├── results/                    # Resultados de treino e avaliação
│   └── modelos/                # Modelos treinados e artefatos
├── src/                        # Código Python reutilizável
├── README.md                   # Documentação do projeto
└── requirements.txt            # Dependências do projeto
```

## Como Executar

1. Clone o repositório:
   ```bash
   git clone <URL-do-repositorio>
   cd "IDS - Network Intrusion Detection"
   ```

2. Crie o ambiente virtual e instale dependências:
   ```bash
   python -m venv .venv
   .\.venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Abra o Jupyter Notebook:
   ```bash
   jupyter notebook
   ```

4. Execute os notebooks no seguinte fluxo:
   - `notebook_portscan.ipynb` para análise de port scan
   - `notebook_ddos.ipynb` para análise de DDoS
   - `notebook_web.ipynb` para análise de ataques web

## Objetivos do Projeto

- Entender a qualidade e o formato dos dados do CIC-IDS-2017.
- Realizar limpeza e tratamento de dados para modelagem.
- Treinar classificadores como Decision Tree, Random Forest, XGBoost, SVM e MLP.
- Avaliar métricas de acurácia, relatório de classificação e matriz de confusão.
- Identificar as features mais importantes para a detecção de intrusões.

## Resultado Esperado

- Relatórios de desempenho para cada modelo.
- Visualizações de métricas e matrizes de confusão.
- Comparação clara entre algoritmos.
- Recomendações de features relevantes para o IDS.

## Estrutura dos Dados

- `datas/raw/`: arquivos CSV originais do CIC-IDS-2017 utilizados no projeto.
- `datas/processed/`: dados tratados e preparados para treino.
- `results/modelos/`: modelos treinados e artefatos gerados.

## Boas Práticas

- Não comite dados brutos sensíveis no repositório.
- Use `datas/processed/` apenas para dados preparados.
- Versione modelos e resultados importantes em `results/modelos/`.
- Documente cada experimento nos notebooks.

## Como Contribuir

1. Crie uma branch com a sua feature ou correção.
2. Faça commit com mensagens claras.
3. Abra um pull request descrevendo as mudanças.

## Contato

- Projeto mantido por `Guilherme Martins`
- Use este repositório para explorar, ajustar e avaliar novos modelos de detecção de intrusão.
