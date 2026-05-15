Topic: faster float-to-string conversions

To experiment with faster float-to-string conversions there is now the [floatium](https://github.com/eendebakpt/floatium/) package.
The package makes `repr(float)`, `str(float)`, `f"{x:.3f}"` and similar conversions much faster (and also speeds up `float(str)` parsing).
Install it with `pip install floatium`. Benchmarks on CPython 3.14.3:

| Corpus          | Operation       | Stock (ns) | floatium (ns) | Speedup |
|-----------------|-----------------|-----------:|--------------:|--------:|
| random_uniform  | `repr(x)`       |        284 |            96 |   2.95× |
| random_uniform  | `f"{x:.4f}"`    |        119 |           103 |   1.16× |
| random_uniform  | `float(s)`      |        121 |            44 |   2.79× |
| random_bits     | `repr(x)`       |        820 |           134 |   6.11× |
| random_bits     | `f"{x:.4f}"`    |      1,933 |           196 |   9.86× |
| random_bits     | `float(s)`      |        275 |            61 |   4.52× |
| financial       | `repr(x)`       |        171 |            80 |   2.14× |
| financial       | `f"{x:.4f}"`    |        145 |           101 |   1.43× |
| financial       | `float(s)`      |         37 |            36 |   1.01× |
| scientific      | `repr(x)`       |        640 |           135 |   4.74× |
| scientific      | `f"{x:.4f}"`    |      1,081 |           161 |   6.71× |
| scientific      | `float(s)`      |        212 |            58 |   3.64× |
| integer_valued  | `repr(x)`       |        143 |            88 |   1.62× |
| integer_valued  | `f"{x:.4f}"`    |        169 |           106 |   1.60× |
| integer_valued  | `float(s)`      |         43 |            42 |   1.02× |

The package should be fully compatible with cpython.

* Earlier discussion can be found at https://discuss.python.org/t/faster-float-string-conversion-ryu.
*  Please report any bugs or differences on the github issue tracker, we will use it to improve the cpython unit tests and the package
* The microbenchmarks show significant improvements, but does this have impact on real-world cases? If so, please report it (github, here or via DM).
* Will this be in cpython? Probably that will take some time. The backends implemented in `floatium` are either C++ (currently not supported in cpython) or slightly modifed versions of the packages (for performance reasons). For inclusion in cpython we probably need a fast, fully compliant, C based implementation that fully replaces `dtoa.c`.
