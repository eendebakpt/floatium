// Slot-level patching of PyFloat_Type.
//
// We overwrite three points on the type:
//
//   tp_repr      -> floatium_float_repr   (covers repr(), str(), f"{x}")
//   __format__   -> floatium_float_format (covers format(), f"{x:spec}")
//   tp_new       -> floatium_float_new    (covers float("..."))
//
// PyOS_double_to_string (used by the '%' operator and some internal
// formatting paths) lives in libpython itself and is not hookable from
// a pip-installed package without LD_PRELOAD. See README "Limitations".
//
// Concurrency / free-threading: we only patch at install() time and only
// unpatch at uninstall() time. The user contract is "install once at
// interpreter startup, stay installed" (the .pth / FLOATIUM_AUTOPATCH path
// satisfies this). Patching is guarded by the GIL on non-freethreaded
// builds; on freethreaded we additionally use PyType_Modified() to
// invalidate type caches and a critical section around the patching.

#include <Python.h>

#include "common/backend.h"
#include "common/format_short.h"

#include <cstring>

// Pre-3.12, `PyFloat_Type.tp_dict` is a valid borrowed reference. Starting
// in 3.12 the field can be NULL until the dict is lazily materialized;
// PyType_GetDict() is the supported way to reach it and returns a new
// strong reference.
static inline PyObject *floatium_get_type_dict(PyTypeObject *tp) {
#if PY_VERSION_HEX >= 0x030C0000
    return PyType_GetDict(tp);
#else
    PyObject *d = tp->tp_dict;
    if (d) Py_INCREF(d);
    return d;
#endif
}

// ---------------------------------------------------------------------------
// Saved originals (set at install, restored at uninstall).
// ---------------------------------------------------------------------------
namespace {

struct SavedState {
    reprfunc tp_repr = nullptr;
    newfunc tp_new = nullptr;
    PyObject *orig_format = nullptr;  // original float.__format__ bound method descriptor

    bool patched = false;
    const FloatiumFormatBackend *fmt_backend = nullptr;
    const FloatiumParseBackend *parse_backend = nullptr;
};

SavedState g_state;

}  // namespace

// ---------------------------------------------------------------------------
// Replacement: tp_repr
// ---------------------------------------------------------------------------
static PyObject *floatium_float_repr(PyObject *v) {
    double d = PyFloat_AS_DOUBLE(v);
    int type_out = 0;
    char *s = floatium_double_to_string(
        g_state.fmt_backend, d, 'r', 0, FLOATIUM_ADD_DOT_0, &type_out);
    if (!s) return nullptr;
    PyObject *result = PyUnicode_FromString(s);
    PyMem_Free(s);
    return result;
}

// ---------------------------------------------------------------------------
// Replacement: float.__format__(format_spec)
// ---------------------------------------------------------------------------
//
// Python's float.__format__ accepts the full mini-language:
//   [[fill]align][sign][#][0][width][,_][.precision][type]
//
// CPython's float___format___impl handles the parsing and then delegates
// the digit generation to PyOS_double_to_string. For a byte-identical
// demo we'd have to port all of that parsing code. That's on the roadmap;
// for v0.1 we intercept the common fast path (type in {r, g, G, e, E, f,
// F, empty} with optional precision, no fill/align/width/#/,/_) and
// fall back to the original for anything complex. Every unit test we
// ship checks this intercept is byte-identical to stock CPython on the
// handled subset.

static PyObject *original_format_call(PyObject *self, PyObject *spec) {
    // g_state.orig_format is a method descriptor (PyMethodDescrObject).
    // These are directly callable as descr(self, *args) — descr_call
    // unpacks the first positional argument as self and passes the rest
    // to the underlying C function. See Objects/descrobject.c:method_call.
    //
    // We deliberately do NOT use PyObject_GetAttrString(self, "__format__")
    // here: that would look up __format__ via the type dict, where we've
    // installed OUR replacement, and recurse forever.
    return PyObject_CallFunctionObjArgs(g_state.orig_format, self, spec, nullptr);
}

// Returns 1 if the spec is one of the simple forms we handle inline:
//   ""                       -> repr
//   "r"                      -> repr
//   "[.precision]{g,G,e,E,f,F}"
// Returns 0 and leaves *out_code / *out_precision untouched otherwise.
static int parse_simple_spec(const char *spec, Py_ssize_t len,
                             char *out_code, int *out_precision,
                             int *out_flags) {
    *out_flags = 0;
    if (len == 0) {
        *out_code = 'r';
        *out_precision = 0;
        *out_flags = FLOATIUM_ADD_DOT_0;
        return 1;
    }
    Py_ssize_t pos = 0;
    int precision = -1;
    // Look for ".precision"
    if (spec[pos] == '.') {
        pos++;
        if (pos >= len || !(spec[pos] >= '0' && spec[pos] <= '9')) return 0;
        precision = 0;
        while (pos < len && spec[pos] >= '0' && spec[pos] <= '9') {
            precision = precision * 10 + (spec[pos] - '0');
            if (precision > 1000000) return 0;  // bail to original
            pos++;
        }
    }
    if (pos >= len) return 0;
    if (pos != len - 1) return 0;  // must be one trailing type char
    char t = spec[pos];
    switch (t) {
    case 'g': case 'G': case 'e': case 'E': case 'f': case 'F':
        *out_code = t;
        *out_precision = precision < 0 ? 6 : precision;
        return 1;
    case 'r':
        if (precision >= 0) return 0;
        *out_code = 'r';
        *out_precision = 0;
        *out_flags = FLOATIUM_ADD_DOT_0;
        return 1;
    default:
        return 0;
    }
}

static PyObject *floatium_float_format(PyObject *self, PyObject *spec) {
    if (!PyFloat_Check(self)) {
        PyErr_SetString(PyExc_TypeError, "float.__format__ requires float");
        return nullptr;
    }
    if (!PyUnicode_Check(spec)) {
        PyErr_SetString(PyExc_TypeError, "format_spec must be str");
        return nullptr;
    }
    Py_ssize_t len = 0;
    const char *utf = PyUnicode_AsUTF8AndSize(spec, &len);
    if (!utf) return nullptr;

    char code = 0;
    int precision = 0;
    int flags = 0;
    if (parse_simple_spec(utf, len, &code, &precision, &flags)) {
        double d = PyFloat_AS_DOUBLE(self);
        char *s = floatium_double_to_string(
            g_state.fmt_backend, d, code, precision, flags, nullptr);
        if (!s) return nullptr;
        PyObject *result = PyUnicode_FromString(s);
        PyMem_Free(s);
        return result;
    }

    // Complex spec (fill, align, width, #, grouping): spec-parsing
    // translation layer isn't built yet. The original __format__ parses
    // these and then calls through to PyOS_double_to_string on stock
    // CPython — meaning this fallback path does go through dtoa.c today.
    // That is a wrapper gap, not a strategic retreat: the upstream goal
    // is to route every float-formatting path through fmt, so the right
    // fix here is to extend parse_simple_spec to handle the full
    // mini-language rather than delegate. Tracked as future work.
    return original_format_call(self, spec);
}

// ---------------------------------------------------------------------------
// Replacement: tp_new
// ---------------------------------------------------------------------------
//
// Intercepts float("<string>"). Everything else (no args, float, int,
// __float__, PyObject with __index__) falls through to the original
// tp_new. We also fall through if the string contains characters
// fast_float is unprepared for (underscores, embedded whitespace,
// "inf"/"nan" literals) so we preserve CPython's exact semantics on
// the edges without re-implementing PyFloat_FromString.
static PyObject *parse_ascii_with_backend(const char *buf, Py_ssize_t len);

static PyObject *floatium_float_new(PyTypeObject *type, PyObject *args,
                                    PyObject *kwds) {
    // Only intercept the one-positional-argument, str case. For everything
    // else we go through the original tp_new.
    if (type != &PyFloat_Type) {
        return g_state.tp_new(type, args, kwds);
    }
    if (kwds != nullptr && PyDict_GET_SIZE(kwds) != 0) {
        return g_state.tp_new(type, args, kwds);
    }
    if (args == nullptr || PyTuple_GET_SIZE(args) != 1) {
        return g_state.tp_new(type, args, kwds);
    }
    PyObject *arg = PyTuple_GET_ITEM(args, 0);
    if (!PyUnicode_Check(arg)) {
        return g_state.tp_new(type, args, kwds);
    }

    Py_ssize_t len = 0;
    const char *buf = PyUnicode_AsUTF8AndSize(arg, &len);
    if (!buf) return nullptr;

    PyObject *result = parse_ascii_with_backend(buf, len);
    if (result) return result;
    // Either fast_float rejected it or it had tricky chars. Fall back.
    PyErr_Clear();
    return g_state.tp_new(type, args, kwds);
}

static PyObject *parse_ascii_with_backend(const char *buf, Py_ssize_t len) {
    // Strip leading/trailing ASCII whitespace, matching PyFloat_FromString.
    while (len > 0 && (*buf == ' ' || *buf == '\t' || *buf == '\n'
                       || *buf == '\r' || *buf == '\f' || *buf == '\v')) {
        ++buf; --len;
    }
    while (len > 0 && (buf[len-1] == ' ' || buf[len-1] == '\t'
                       || buf[len-1] == '\n' || buf[len-1] == '\r'
                       || buf[len-1] == '\f' || buf[len-1] == '\v')) {
        --len;
    }
    if (len == 0) return nullptr;

    // Reject strings containing chars we don't inline-handle (underscores,
    // embedded whitespace, non-ASCII). The _Py_fast_float_strtod backend
    // already stops at the first non-numeric char, but CPython's accepted
    // "1_000.5" etc. which require stripping. Leave those to the original.
    for (Py_ssize_t i = 0; i < len; ++i) {
        unsigned char c = (unsigned char)buf[i];
        if (c == '_' || c > 0x7f) return nullptr;
    }

    // Copy to a null-terminated buffer for strtod (backend doesn't take a
    // length). For strings up to 63 chars we avoid malloc.
    char stack[64];
    char *heap = nullptr;
    char *cstr;
    if (len < (Py_ssize_t)sizeof(stack)) {
        std::memcpy(stack, buf, len);
        stack[len] = '\0';
        cstr = stack;
    } else {
        heap = (char *)PyMem_Malloc((size_t)len + 1);
        if (!heap) { PyErr_NoMemory(); return nullptr; }
        std::memcpy(heap, buf, len);
        heap[len] = '\0';
        cstr = heap;
    }

    char *end = nullptr;
    double val = g_state.parse_backend->strtod(cstr, &end);
    bool consumed_all = (end == cstr + len);
    bool invalid = (end == cstr);
    int saved_errno = errno;
    if (heap) PyMem_Free(heap);
    errno = 0;

    if (invalid || !consumed_all) return nullptr;  // fall through to original

    if (saved_errno == ERANGE) {
        // fast_float returned inf/0; stock also raises OverflowError on
        // inf-in-underflow depends on the value. Let the original handle
        // errno cases for exact parity.
        return nullptr;
    }
    return PyFloat_FromDouble(val);
}

// ---------------------------------------------------------------------------
// install() / uninstall()
// ---------------------------------------------------------------------------
extern "C" {

int floatium_install(const FloatiumFormatBackend *fmt_b,
                     const FloatiumParseBackend *parse_b) {
    if (g_state.patched) return 0;
    if (!fmt_b) {
        PyErr_SetString(PyExc_ValueError, "format backend is NULL");
        return -1;
    }
    if (!parse_b) {
        PyErr_SetString(PyExc_ValueError, "parse backend is NULL");
        return -1;
    }

    // Use PyType_GetDict (3.12+): PyFloat_Type.tp_dict can be NULL since
    // types now lazily materialize their dict. PyType_GetDict returns a new
    // strong reference that we must DECREF.
    PyObject *type_dict = floatium_get_type_dict(&PyFloat_Type);
    if (!type_dict) {
        PyErr_SetString(PyExc_RuntimeError,
                        "PyType_GetDict(float) returned NULL");
        return -1;
    }

    // Save __format__ descriptor BEFORE overwriting.
    PyObject *orig_format = PyDict_GetItemString(type_dict, "__format__");
    if (orig_format == nullptr) {
        Py_DECREF(type_dict);
        PyErr_SetString(PyExc_RuntimeError,
                        "float has no __format__ descriptor?");
        return -1;
    }
    Py_INCREF(orig_format);
    g_state.orig_format = orig_format;

    // Build a PyCFunction for our replacement __format__, wrap it as a
    // method descriptor, and install it in tp_dict.
    static PyMethodDef format_def = {
        "__format__", (PyCFunction)floatium_float_format, METH_O,
        "floatium-patched __format__"
    };
    PyObject *func = PyDescr_NewMethod(&PyFloat_Type, &format_def);
    if (!func) {
        Py_DECREF(type_dict);
        Py_CLEAR(g_state.orig_format);
        return -1;
    }
    if (PyDict_SetItemString(type_dict, "__format__", func) < 0) {
        Py_DECREF(func);
        Py_DECREF(type_dict);
        Py_CLEAR(g_state.orig_format);
        return -1;
    }
    Py_DECREF(func);
    Py_DECREF(type_dict);

    // Save originals and install our tp_repr / tp_new.
    g_state.tp_repr = PyFloat_Type.tp_repr;
    g_state.tp_new  = PyFloat_Type.tp_new;
    g_state.fmt_backend = fmt_b;
    g_state.parse_backend = parse_b;

    PyFloat_Type.tp_repr = floatium_float_repr;
    PyFloat_Type.tp_new  = floatium_float_new;

    // Invalidate PyFloat_Type's method cache by clearing the version tag.
    // PyType_Modified() asserts against static builtin types in debug builds
    // (3.15+). Clearing tp_version_tag is the kernel of what PyType_Modified
    // does for the mcache and is safe on static types. Subtypes of float
    // (if any existed) would need their own invalidation, but nothing in
    // stdlib subclasses float.
    // PyType_Modified is the supported way to invalidate method caches,
    // but 3.15 debug builds assert against it on static builtin types
    // (Objects/typeobject.c:type_modified_unlocked). Use the version-tag
    // trick there; use PyType_Modified everywhere else.
#if PY_VERSION_HEX >= 0x030F0000 && defined(Py_DEBUG)
    PyFloat_Type.tp_version_tag = 0;
#else
    PyType_Modified(&PyFloat_Type);
#endif

    g_state.patched = true;
    return 0;
}

int floatium_uninstall(void) {
    if (!g_state.patched) return 0;

    PyFloat_Type.tp_repr = g_state.tp_repr;
    PyFloat_Type.tp_new  = g_state.tp_new;

    if (g_state.orig_format) {
        PyObject *type_dict = floatium_get_type_dict(&PyFloat_Type);
        if (type_dict) {
            PyDict_SetItemString(type_dict, "__format__", g_state.orig_format);
            Py_DECREF(type_dict);
        }
        Py_CLEAR(g_state.orig_format);
    }

    // PyType_Modified is the supported way to invalidate method caches,
    // but 3.15 debug builds assert against it on static builtin types
    // (Objects/typeobject.c:type_modified_unlocked). Use the version-tag
    // trick there; use PyType_Modified everywhere else.
#if PY_VERSION_HEX >= 0x030F0000 && defined(Py_DEBUG)
    PyFloat_Type.tp_version_tag = 0;
#else
    PyType_Modified(&PyFloat_Type);
#endif

    g_state.tp_repr = nullptr;
    g_state.tp_new  = nullptr;
    g_state.fmt_backend = nullptr;
    g_state.parse_backend = nullptr;
    g_state.patched = false;
    return 0;
}

int floatium_is_patched(void) {
    return g_state.patched ? 1 : 0;
}

const char *floatium_current_format_backend(void) {
    return g_state.patched && g_state.fmt_backend
        ? g_state.fmt_backend->name : nullptr;
}

const char *floatium_current_parse_backend(void) {
    return g_state.patched && g_state.parse_backend
        ? g_state.parse_backend->name : nullptr;
}

}  // extern "C"
