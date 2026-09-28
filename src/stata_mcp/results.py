"""Bounded JSON representations of Stata returns, preserving matrix labels."""
import math

from .reporting import regression_report


def number(value):
    v = float(value)
    # Stata . and extended missing values are finite IEEE doubles above this value.
    return None if not math.isfinite(v) or v >= 8.98846567431158e307 else v


def snapshot():
    import sfi
    result = {'scope': 'Session state after this successful run; e() may persist from earlier commands.',
              'missing_values': 'Stata missing and nonfinite numbers are JSON null.', 'truncated': False}
    for namespace in ('r', 'e', 's'):
        items = {}
        for kind in ('scalar', 'macro', 'matrix'):
            if namespace == 's' and kind != 'macro':
                continue
            names = sfi.SFIToolkit.listReturn(namespace + '()', kind).split()
            for name in names:
                if len(items) >= 200:
                    result['truncated'] = True
                    break
                key = f'{namespace}({name})'
                if kind == 'scalar':
                    items[key] = number(sfi.Scalar.getValue(key))
                elif kind == 'macro':
                    value = sfi.Macro.getGlobal(key)
                    items[key] = value[:4000]
                    if len(value) > 4000:
                        result['truncated'] = True
                else:
                    rows = sfi.Matrix.getRowTotal(key)
                    cols = sfi.Matrix.getColTotal(key)
                    ncol = min(cols, 256)
                    nrow = min(rows, max(1, 4096 // max(1, ncol)))
                    values = [[number(sfi.Matrix.getAt(key, i, j)) for j in range(ncol)] for i in range(nrow)]
                    truncated = nrow < rows or ncol < cols
                    items[key] = {'shape': [rows, cols], 'values': values,
                                  'row_names': sfi.Matrix.getRowNames(key)[:nrow],
                                  'column_names': sfi.Matrix.getColNames(key)[:ncol],
                                  'truncated': truncated}
                    result['truncated'] |= truncated
        result[namespace] = items
    result['regression_report'] = regression_report(result)
    return result
