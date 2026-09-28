"""Default regression reporting: SE underneath, stars from unrounded p-values."""
import copy

import pytest


def fixture_result():
    return {'e': {'e(cmd)': 'regress', 'e(cmdline)': 'regress y x, vce(robust)',
        'e(depvar)': 'y', 'e(N)': 20, 'e(r2)': .5, 'e(r2_a)': .47,
        'e(df_r)': 18, 'e(vce)': 'robust',
        'e(b)': {'column_names': ['x', '_cons'], 'values': [[2., 1.]], 'truncated': False},
        'e(V)': {'column_names': ['x', '_cons'], 'row_names': ['x', '_cons'], 'values': [[.25, 0], [0, 1.]], 'truncated': False}},
        'r': {'r(table)': {'row_names': ['b', 'se', 'pvalue', 'df'],
            'column_names': ['x', '_cons'], 'values': [[2., 1.], [.5, 1.], [.009, .06], [18, 18]], 'truncated': False}}}


def test_estimates_are_followed_by_parenthesized_se():
    from stata_mcp.reporting import regression_report
    result = regression_report(fixture_result())
    assert '| x | 2.00*** |\n|  | (0.50) |' in result['markdown']
    assert '| _cons | 1.00* |\n|  | (1.00) |' in result['markdown']
    assert result['standard_errors'] == 'robust'
    assert result['legend'] == '* p<0.10, ** p<0.05, *** p<0.01'


@pytest.mark.parametrize('p,stars', [(0, '***'), (.009999, '***'), (.01, '**'), (.049999, '**'), (.05, '*'), (.099999, '*'), (.10, ''), (None, '')])
def test_unrounded_p_values_and_strict_cutoffs(p, stars):
    from stata_mcp.reporting import significance_stars
    assert significance_stars(p) == stars


@pytest.mark.parametrize('change', ['coefficient', 'se', 'df', 'truncated', 'no_table'])
def test_unmatched_or_incomplete_return_table_is_not_used(change):
    from stata_mcp.reporting import regression_report
    result = copy.deepcopy(fixture_result())
    if change == 'coefficient': result['r']['r(table)']['values'][0][0] = 999
    if change == 'se': result['r']['r(table)']['values'][1][0] = 999
    if change == 'df': result['r']['r(table)']['values'][3][0] = 100
    if change == 'truncated': result['e']['e(V)']['truncated'] = True
    if change == 'no_table': result['r'] = {}
    assert regression_report(result)['available'] is False


def test_reference_term_not_reported_as_estimated_zero():
    from stata_mcp.reporting import regression_report
    result = fixture_result()
    result['e']['e(b)']['column_names'][0] = '0b.foreign'
    result['r']['r(table)']['column_names'][0] = '0b.foreign'
    result['e']['e(V)']['column_names'][0] = '0b.foreign'
    result['e']['e(V)']['row_names'][0] = '0b.foreign'
    result['e']['e(b)']['values'][0][0] = 0
    result['e']['e(V)']['values'][0][0] = 0
    for row in (0, 1, 2): result['r']['r(table)']['values'][row][0] = 0 if row == 0 else None
    report = regression_report(result)
    assert report['rows'][0]['status'] == 'reference_or_omitted'
    assert 'reference/omitted' in report['markdown']


def test_degenerate_zero_estimate_is_not_a_reference_category():
    from stata_mcp.reporting import regression_report
    result = fixture_result()
    result['e']['e(b)']['values'][0][0] = 0
    result['e']['e(V)']['values'][0][0] = 0
    for row in (0, 1, 2): result['r']['r(table)']['values'][row][0] = 0 if row == 0 else None
    assert regression_report(result)['available'] is False
