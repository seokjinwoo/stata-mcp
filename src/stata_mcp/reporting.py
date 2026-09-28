"""Presentation of verified Stata OLS returns; never infer stars from rounded output."""
import math
import re


LEGEND = '* p<0.10, ** p<0.05, *** p<0.01'


def significance_stars(p):
    if p is None or not math.isfinite(p) or not 0 <= p <= 1:
        return ''
    return '***' if p < .01 else '**' if p < .05 else '*' if p < .10 else ''


def _escape(value):
    return str(value).replace('|', '\\|').replace('\r', ' ').replace('\n', ' ')


def regression_report(snapshot):
    unavailable = {'available': False, 'legend': LEGEND,
        'reason': 'Requires complete matching regress e(b), e(V), e(df_r) and r(table). Replay the intended stored regression with estimates replay, then call stata_results. Never use unrelated or rounded p-values.'}
    e, r = snapshot.get('e', {}), snapshot.get('r', {})
    if e.get('e(cmd)') != 'regress':
        return {**unavailable, 'reason': 'Automatic regression table currently supports regress (OLS) only.'}
    b, v, table = e.get('e(b)'), e.get('e(V)'), r.get('r(table)')
    if not all(isinstance(item, dict) and not item.get('truncated') for item in (b, v, table)):
        return unavailable
    try:
        names = b['column_names']
        coefficients = b['values'][0]
        if names != table['column_names'] or len(coefficients) != len(names):
            return unavailable
        if v['column_names'] != names or v['row_names'] != names:
            return unavailable
        returned = dict(zip(table['row_names'], table['values']))
        if any(len(returned[key]) != len(names) for key in ('b', 'se', 'pvalue', 'df')):
            return unavailable
        rows = []
        for index, name in enumerate(names):
            coef, variance = coefficients[index], v['values'][index][index]
            if coef is None or variance is None or variance < 0:
                return unavailable
            if not math.isclose(coef, returned['b'][index], rel_tol=1e-10, abs_tol=1e-12):
                return unavailable
            if returned['df'][index] != e.get('e(df_r)'):
                return unavailable
            se = math.sqrt(variance)
            reported_se, p = returned['se'][index], returned['pvalue'][index]
            omitted = coef == 0 and variance == 0 and bool(re.search(r'(^|#)(?:\d+)?[bo]\.', name))
            if not omitted and (reported_se is None or not math.isclose(se, reported_se, rel_tol=1e-10, abs_tol=1e-12)):
                return unavailable
            if p is not None and (not math.isfinite(p) or not 0 <= p <= 1):
                return unavailable
            rows.append({'term': name, 'estimate': coef, 'std_error': None if omitted else se,
                'p_value': None if omitted else p, 'stars': '' if omitted else significance_stars(p),
                'status': 'reference_or_omitted' if omitted else 'estimated'})
    except (KeyError, IndexError, TypeError, ValueError):
        return unavailable
    lines = ['| Variable | Estimate |', '|---|---:|']
    for row in rows:
        if row['status'] == 'reference_or_omitted':
            lines.append(f"| {_escape(row['term'])} | reference/omitted |")
        else:
            lines.append(f"| {_escape(row['term'])} | {row['estimate']:,.2f}{row['stars']}<br>({row['std_error']:,.2f}) |")
    for label, key in [('N', 'e(N)'), ('R²', 'e(r2)'), ('Adjusted R²', 'e(r2_a)')]:
        value = e.get(key)
        if value is not None:
            rendered = f'{value:.0f}' if label == 'N' else f'{value:.3f}'
            lines.append(f'| {label} | {rendered} |')
    se_type = e.get('e(vce)', 'ols')
    lines.extend(['', f'Standard errors in parentheses beneath estimates ({_escape(se_type)}). {LEGEND}.'])
    return {'available': True, 'dependent_variable': e.get('e(depvar)'), 'command': e.get('e(cmdline)'),
            'standard_errors': se_type, 'cluster_variable': e.get('e(clustvar)'),
            'rows': rows, 'N': e.get('e(N)'), 'r2': e.get('e(r2)'), 'r2_adjusted': e.get('e(r2_a)'),
            'legend': LEGEND, 'markdown': '\n'.join(lines),
            'scope': 'Current stored e() estimate, which may predate the last command. Not necessarily a newly fitted model.'}
