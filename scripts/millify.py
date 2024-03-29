#!/usr/bin/env python3

# SOURCE: https://github.com/azaitsev/millify/blob/master/millify/__init__.py
import math
import re
import sys
from decimal import Decimal

__author__ = "Alexander Zaitsev (azaitsev@gmail.com)"
__copyright__ = "Copyright 2018, azaitsev@gmail.com"
__license__ = "MIT"
__version__ = "0.1.1"


def remove_exponent(d):
    """Remove exponent."""
    return d.quantize(Decimal(1)) if d == d.to_integral() else d.normalize()


def millify(n, precision=0, drop_nulls=True, prefixes=[]):
    """Humanize number."""
    millnames = ['', 'k', 'm', 'b']
    if prefixes:
        millnames = ['']
        millnames.extend(prefixes)
    n = float(n)
    millidx = max(0, min(len(millnames) - 1,
                         int(math.floor(0 if n == 0 else math.log10(abs(n)) / 3))))
    result = '{:.{precision}f}'.format(n / 10**(3 * millidx), precision=precision)
    if drop_nulls:
        result = remove_exponent(Decimal(result))
    return '{0}{dx}'.format(result, dx=millnames[millidx])

print(millify(''.join(list(sys.stdin.read())), precision=1))
