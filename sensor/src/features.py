"""Selecao de features por importancia (SHAP do XGBoost) e correlacao."""
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import f1_score
from sklearn.model_selection import StratifiedKFold
from sklearn.utils.class_weight import compute_sample_weight

XGB_PARAMS = dict(n_estimators=100, max_depth=8, learning_rate=0.1,
                  tree_method='hist', n_jobs=-1, random_state=42)


def make_model(n_classes, **params):
    params = {**XGB_PARAMS, **params}
    if n_classes > 2:
        return xgb.XGBClassifier(objective='multi:softprob', **params)
    return xgb.XGBClassifier(objective='binary:logistic', **params)


def sample_weights(y, balanced):
    return compute_sample_weight('balanced', y) if balanced else None


def shap_importance(model, X):
    """Media do |SHAP| por feature (TreeSHAP nativo do XGBoost).

    Em multiclasse, faz a media tambem entre as classes.
    """
    contribs = model.get_booster().predict(xgb.DMatrix(X), pred_contribs=True)
    contribs = np.abs(contribs)
    if contribs.ndim == 3:            # (amostras, classes, features + bias)
        contribs = contribs.mean(axis=1)
    values = contribs[:, :-1].mean(axis=0)   # ultima coluna e o bias
    return pd.Series(values, index=X.columns).sort_values(ascending=False)


def gain_importance(model, columns):
    gain = model.get_booster().get_score(importance_type='gain')
    return pd.Series(gain, index=columns).fillna(0).sort_values(ascending=False)


def correlation_filter(X, ranking, threshold=0.95):
    """Remove features muito correlacionadas, mantendo a mais importante.

    Percorre as features na ordem do ranking; uma feature e descartada se a
    correlacao absoluta com alguma ja mantida passar do limiar.
    """
    corr = X[ranking.index].corr().abs()
    kept, dropped = [], {}
    for col in ranking.index:
        match = next((k for k in kept if corr.loc[col, k] > threshold), None)
        if match is None:
            kept.append(col)
        else:
            dropped[col] = match
    return kept, dropped


def stratified_sample(X, y, per_class, random_state=42):
    """Amostra ate `per_class` linhas de cada classe (classes raras entram inteiras)."""
    idx = (y.groupby(y, group_keys=False)
            .apply(lambda s: s.sample(min(len(s), per_class), random_state=random_state))
            .index)
    return X.loc[idx], y.loc[idx]


def cv_score(X, y, balanced, n_splits=3, random_state=42):
    """F1 em validacao cruzada estratificada (macro em multiclasse)."""
    n_classes = y.nunique()
    average = 'macro' if n_classes > 2 else 'binary'
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
    scores = []
    for tr, va in skf.split(X, y):
        model = make_model(n_classes)
        model.fit(X.iloc[tr], y.iloc[tr], sample_weight=sample_weights(y.iloc[tr], balanced))
        scores.append(f1_score(y.iloc[va], model.predict(X.iloc[va]), average=average))
    return np.mean(scores), np.std(scores)


def topk_curve(X, y, ranking, ks, balanced):
    """F1 (validacao cruzada) usando as top-k features do ranking, para cada k."""
    rows = []
    for k in ks:
        mean, std = cv_score(X[ranking.index[:k]], y, balanced)
        rows.append({'k': k, 'f1': mean, 'std': std})
    return pd.DataFrame(rows)


def choose_k(curve):
    """Menor k cujo F1 fica a no maximo um desvio padrao do melhor resultado."""
    best = curve.loc[curve['f1'].idxmax()]
    ok = curve[curve['f1'] >= best['f1'] - best['std']]
    return int(ok['k'].min())
