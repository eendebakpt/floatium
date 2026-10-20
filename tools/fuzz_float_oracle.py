"""Differential fuzzer for float <-> str conversion against exact arithmetic.

Checks float(s), format(x, ".Nf" / ".Ne" / ".Ng"), repr(x) and round(x, n)
of the *running* interpreter against oracles that never touch dtoa.c or any
floatium backend:

  * parsing : digits + exponent as exact ints -> int/int true division,
              which CPython guarantees to be correctly rounded (including
              subnormals); huge exponents are short-circuited.
  * format  : Decimal(x) is exact; quantize / round with ROUND_HALF_EVEN.
  * repr    : brute-force shortest-then-closest search over Decimal
              candidates, round-trip checked with the parse oracle.
  * round   : exact Fraction rounding (half-even) -> int/int division.

Inputs are biased towards the hard cases: exact binary midpoints and their
decimal neighbours (full expansions up to ~1100 digits, truncations, bumped
last digits), random 1-1500 digit strings with random exponents, subnormals,
powers of ten +- ulps, and the overflow / underflow thresholds.

    FLOATIUM_AUTOPATCH=0 python tools/fuzz_float_oracle.py [seed] [N]   # stock CPython
    FLOATIUM_FORMAT_BACKEND=zmij FLOATIUM_PARSE_BACKEND=wuffs \
        python tools/fuzz_float_oracle.py 1 40000                      # a floatium backend

N=40000 is ~1M checks and takes ~12 s with the C decimal module.
FUZZ_NO_ORACLE=1 only exercises the conversions (for sanitizer builds that
lack libmpdec).
"""
import math, random, struct, sys, time, re
from fractions import Fraction
from decimal import Decimal, Context, ROUND_HALF_EVEN, localcontext, getcontext

getcontext().prec = 2000
SEED = int(sys.argv[1]) if len(sys.argv) > 1 else 1
N = int(sys.argv[2]) if len(sys.argv) > 2 else 20000
rng = random.Random(SEED)
report = {}
def bad(cat, item):
    lst = report.setdefault(cat, [])
    lst.append(item)

def bits(b): return struct.unpack("<d", b.to_bytes(8, "little"))[0]
def tobits(x): return struct.unpack("<Q", struct.pack("<d", x))[0]

def nearest(fr: Fraction, neg=False) -> float:
    """Correctly rounded double of a non-negative Fraction (independent of dtoa)."""
    try:
        v = fr.numerator / fr.denominator
    except OverflowError:
        v = math.inf
    return -v if neg else v

_NUM = re.compile(r"(\d*)\.?(\d*)(?:[eE]([+-]?\d+))?")
def parse_oracle(s: str) -> float:
    """Correctly rounded value of a decimal string via exact ints + int/int
    division. Huge exponents are short-circuited instead of materialised."""
    neg = s.lstrip().startswith("-")
    core = s.strip().lstrip("+-")
    m = _NUM.fullmatch(core); assert m, s
    ip, fp, e = m.groups()
    digits = int((ip + fp) or "0")
    if digits == 0:
        return -0.0 if neg else 0.0
    exp10 = (int(e) if e else 0) - len(fp)
    adjusted = len(str(digits)) + exp10          # decimal magnitude
    if adjusted > 312:
        return -math.inf if neg else math.inf
    if adjusted < -330:
        return -0.0 if neg else 0.0
    fr = Fraction(digits * 10 ** exp10) if exp10 >= 0 else Fraction(digits, 10 ** -exp10)
    return nearest(fr, neg)

NO_ORACLE = __import__("os").environ.get("FUZZ_NO_ORACLE") == "1"
if NO_ORACLE:   # exercise-only mode (for sanitizer builds without libmpdec)
    parse_oracle = lambda s: float(s)

# ---------------------------------------------------------------- values
def random_values(n):
    vals = []
    for _ in range(n):
        r = rng.random()
        if r < 0.4:
            x = bits(rng.getrandbits(64))
            if not math.isfinite(x): continue
        elif r < 0.55:
            x = bits(rng.getrandbits(52) | (rng.getrandbits(1) << 63))   # subnormal
        elif r < 0.7:
            k = rng.randint(-320, 308); x = 10.0 ** k
            for _ in range(rng.randint(0, 3)): x = math.nextafter(x, rng.choice([0.0, math.inf]))
        elif r < 0.85:
            x = rng.uniform(-1e6, 1e6)
        else:
            x = float(rng.randint(-10**17, 10**17)) * 10.0 ** rng.randint(-20, 20)
        if math.isfinite(x): vals.append(x)
    return vals

def one_value():
    while True:
        v = random_values(1)
        if v: return v[0]

# ---------------------------------------------------------------- parse
def exact_decimal_string(fr: Fraction) -> str:
    """Finite decimal expansion of a dyadic rational (as digits, no exponent)."""
    d = Decimal(fr.numerator) / Decimal(fr.denominator)   # exact at prec 2000 for dyadics < 2^1024 / 2^1074... use scaleb
    return format(d, "f")

def check_parse(n):
    t0 = time.time(); cnt = 0
    # (a) halfway cases and their neighbours, full expansion and truncations
    for _ in range(n):
        x = abs(one_value()) if rng.random() < 0.9 else abs(bits(rng.getrandbits(52)))
        if x == 0 or not math.isfinite(x): continue
        y = math.nextafter(x, math.inf)
        if not math.isfinite(y): continue
        mid = (Fraction(x) + Fraction(y)) / 2
        with localcontext() as ctx:
            ctx.prec = 1200
            dm = Decimal(mid.numerator) / Decimal(mid.denominator)
            s_full = format(dm, "f")
        variants = [s_full]
        # perturb last digit, append digits, truncate
        if "." in s_full:
            variants.append(s_full + "1")
            variants.append(s_full + "0" * rng.randint(1, 50) + "1")
            cut = rng.randint(1, len(s_full) - 1)
            if s_full[cut-1] != ".":
                variants.append(s_full[:cut])
            # bump last digit down/up
            last = s_full[-1]
            if last != "0": variants.append(s_full[:-1] + str(int(last) - 1))
            if last != "9": variants.append(s_full[:-1] + str(int(last) + 1))
        # exponent form of the same number
        mant = s_full.replace(".", "").lstrip("0") or "0"
        intlen = s_full.index(".") if "." in s_full else len(s_full)
        lead = len(s_full.replace(".", "")) - len(s_full.replace(".", "").lstrip("0"))
        e = intlen - lead - 1
        variants.append(f"{mant[0]}.{mant[1:]}e{e}" if len(mant) > 1 else f"{mant}e{e}")
        for s in variants:
            cnt += 1
            got = float(s); exp = parse_oracle(s)
            if tobits(got) != tobits(exp):
                bad("parse", (s[:80] + ("..." if len(s) > 80 else ""), got, exp))
    # (b) random digit strings
    for _ in range(n):
        nd = rng.choice([1, 5, 17, 18, 19, 20, 25, 40, 41, 60, 100, 400, 800, 1500])
        digits = "".join(rng.choice("0123456789") for _ in range(nd))
        if rng.random() < 0.3: digits = "0" * rng.randint(1, 30) + digits
        if rng.random() < 0.5:
            p = rng.randint(0, len(digits)); digits = digits[:p] + "." + digits[p:]
            if digits.startswith("."): digits = "0" + digits
            if digits.endswith("."): digits += "0"
        s = digits + rng.choice(["", "", f"e{rng.randint(-400, 400)}", f"E+{rng.randint(0, 330)}", f"e-{rng.randint(0, 350)}"])
        if rng.random() < 0.3: s = "-" + s
        cnt += 1
        got = float(s); exp = parse_oracle(s)
        if tobits(got) != tobits(exp):
            bad("parse", (s[:80], got, exp))
    # (c) overflow / underflow thresholds
    dmax = Fraction(1.7976931348623157e308); half_ulp = Fraction(2) ** 970
    tiny = Fraction(2) ** -1075                               # half of min subnormal
    for base, name in [(dmax + half_ulp, "DBL_MAX+half"), (tiny, "min_sub/2")]:
        with localcontext() as ctx:
            ctx.prec = 1200
            dd = Decimal(base.numerator) / Decimal(base.denominator)
        s = format(dd, "f")
        for v in [s, s + "1", s[:-1] + "0", s[:-3]]:
            cnt += 1
            got = float(v); exp = parse_oracle(v)
            if tobits(got) != tobits(exp): bad("parse-threshold", (name, v[:60], got, exp))
    for s in ["1e308", "1.8e308", "2e308", "1e309", "1e400", "1e99999", "1e-99999", "1e-400", "1e-324", "2e-324", "2.5e-324", "3e-324",
              "4.9406564584124654e-324", "2.4703282292062327e-324", "2.4703282292062328e-324", "2.47032822920623272e-324",
              "0." + "0" * 400 + "1", "1" + "0" * 400, "1" + "0" * 400 + "e-400", "9" * 400 + "e-400",
              "1e+" + "0" * 30 + "308", "1e-" + "0" * 30 + "324", "0e99999999999999999999", "1e-" + "9" * 30, "1e" + "9" * 30]:
        cnt += 1
        got = float(s); exp = parse_oracle(s)
        if tobits(got) != tobits(exp): bad("parse-edge", (s[:60], got, exp))
    print(f"parse: {cnt} cases in {time.time()-t0:.1f}s, {len(report.get('parse', [])) + len(report.get('parse-threshold', [])) + len(report.get('parse-edge', []))} mismatches")

# ---------------------------------------------------------------- format
def norm_e(s):
    m = re.fullmatch(r"(-?)(\d)(?:\.(\d*))?[eE]([+-]?\d+)", s)
    assert m, s
    sign, d0, frac, e = m.groups()
    return f"{sign}{d0}.{frac or ''}e{int(e)}"

def fmt_f_oracle(x, nd):
    d = Decimal(x)
    q = d.quantize(Decimal(1).scaleb(-nd), rounding=ROUND_HALF_EVEN)
    return format(q, "f")

def sig_round(x, nsig):
    """Decimal(x) rounded half-even to nsig significant digits (exact ctx)."""
    d = Decimal(x)
    if d == 0: return d
    ctx = Context(prec=nsig, rounding=ROUND_HALF_EVEN)
    return ctx.plus(d)

def fmt_e_oracle(x, nd):
    q = sig_round(x, nd + 1)
    return norm_e(format(q, f".{nd}e"))

def fmt_g_oracle(x, prec):
    P = prec if prec else 1
    q = sig_round(x, P)
    if q == 0:
        return "-0" if math.copysign(1, x) < 0 else "0"
    E = q.adjusted()
    if -4 <= E < P:
        s = format(q.quantize(Decimal(1).scaleb(E - P + 1), rounding=ROUND_HALF_EVEN), "f")
        if "." in s: s = s.rstrip("0").rstrip(".")
        return s
    s = format(q, f".{P-1}e")
    mant, _, e = s.partition("e")
    if "." in mant: mant = mant.rstrip("0").rstrip(".")
    return f"{mant}e{int(e)}"

def check_format(n):
    global fmt_f_oracle, fmt_e_oracle, fmt_g_oracle
    if NO_ORACLE:
        fmt_f_oracle = lambda x, nd: format(x, f".{nd}f")
        fmt_e_oracle = lambda x, nd: norm_e(format(x, f".{nd}e"))
        fmt_g_oracle = lambda x, p: (lambda g: (lambda m, _, e: f"{m}e{int(e)}")(*g.partition("e")) if "e" in g else g)(format(x, f".{p}g"))
    t0 = time.time(); cnt = 0
    vals = random_values(n)
    for x in vals:
        for nd in rng.sample([0, 1, 2, 3, 6, 10, 15, 16, 17, 18, 19, 20, 25, 30, 50, 100, 400, 1100], 5):
            cnt += 1
            got = format(x, f".{nd}f"); exp = fmt_f_oracle(x, nd)
            if got != exp: bad("format-f", (repr(x), nd, got[:60], exp[:60]))
        for nd in rng.sample([0, 1, 2, 5, 6, 14, 15, 16, 17, 18, 19, 25, 60, 400], 4):
            cnt += 1
            got = norm_e(format(x, f".{nd}e")); exp = fmt_e_oracle(x, nd)
            if got != exp: bad("format-e", (repr(x), nd, got[:60], exp[:60]))
        for p in rng.sample([0, 1, 2, 5, 6, 10, 15, 16, 17, 18, 20, 30, 100], 3):
            cnt += 1
            got = format(x, f".{p}g")
            if "e" in got:
                mant, _, e = got.partition("e"); got = f"{mant}e{int(e)}"
            exp = fmt_g_oracle(x, p)
            if got != exp: bad("format-g", (repr(x), p, got[:60], exp[:60]))
    print(f"format: {cnt} cases in {time.time()-t0:.1f}s, {sum(len(report.get(k, [])) for k in ('format-f','format-e','format-g'))} mismatches")

# ---------------------------------------------------------------- repr
def check_repr(n):
    t0 = time.time(); cnt = 0; ambiguous = 0
    for x in random_values(n):
        if x == 0: continue
        cnt += 1
        if NO_ORACLE:
            float(repr(x)); float(str(x)); continue
        ax = abs(x); exact = Fraction(ax)
        r = repr(ax)
        rd = Decimal(r)
        # 1. round trip (oracle parse)
        if nearest(Fraction(rd)) != ax:
            bad("repr-roundtrip", (r,)); continue
        rdig = rd.normalize().as_tuple().digits; L = len(rdig)
        # 2. shortest & closest
        best = None
        for nsig in range(1, 18):
            q = sig_round(ax, nsig)
            ulp = Decimal(1).scaleb(q.adjusted() - nsig + 1)
            cands = {q, q - ulp, q + ulp}
            ok = [c for c in cands if c > 0 and nearest(Fraction(c)) == ax]
            if ok:
                dist = {c: abs(Fraction(c) - exact) for c in ok}
                m = min(dist.values())
                closest = [c for c in ok if dist[c] == m]
                best = (nsig, closest); break
        nsig, closest = best
        if L != nsig:
            bad("repr-not-shortest", (r, nsig, [str(c) for c in closest])); continue
        if rd.normalize() not in [c.normalize() for c in closest]:
            # repr is shortest but not the closest candidate
            if any(nearest(Fraction(c)) == ax for c in closest):
                bad("repr-not-closest", (r, [str(c) for c in closest], str(abs(Fraction(rd)-exact) - min(abs(Fraction(c)-exact) for c in closest))))
        if len(closest) > 1: ambiguous += 1
    print(f"repr: {cnt} values in {time.time()-t0:.1f}s, {len(report.get('repr-roundtrip', [])) + len(report.get('repr-not-shortest', [])) + len(report.get('repr-not-closest', []))} mismatches, {ambiguous} equidistant ties")

# ---------------------------------------------------------------- round
def check_round(n):
    t0 = time.time(); cnt = 0
    for x in random_values(n):
        fx = Fraction(x)
        for nd in rng.sample(range(-25, 26), 6):
            cnt += 1
            got = round(x, nd)
            if nd >= 0:
                r = round(fx * 10 ** nd); fr = Fraction(r, 10 ** nd)
            else:
                r = round(fx / 10 ** (-nd)); fr = Fraction(r * 10 ** (-nd))
            exp = nearest(abs(fr)) if fr else 0.0
            if fr < 0: exp = -exp
            if fr == 0: exp = math.copysign(0.0, x)
            if tobits(got) != tobits(exp): bad("round", (repr(x), nd, got, exp))
    print(f"round: {cnt} cases in {time.time()-t0:.1f}s, {len(report.get('round', []))} mismatches")

print(sys.version.split()[0], "float_repr_style =", sys.float_repr_style, "seed", SEED, "N", N, flush=True)
check_parse(N); check_format(N); check_repr(N // 4); check_round(N)
for k, v in report.items():
    print(f"== {k}: {len(v)}")
    for item in v[:8]: print("   ", item)
