// floatium._ext — Python-facing entry points.
#include <Python.h>

#include "common/backend.h"

extern "C" {

// Provided by slots.cc.
int floatium_install(const FloatiumFormatBackend *fmt_b,
                     const FloatiumParseBackend *parse_b);
int floatium_uninstall(void);
int floatium_is_patched(void);
const char *floatium_current_format_backend(void);
const char *floatium_current_parse_backend(void);

}  // extern "C"

static PyObject *py_install(PyObject * /*self*/, PyObject *args,
                            PyObject *kwargs) {
    static const char *kwlist[] = {"format_backend", "parse_backend", nullptr};
    const char *fmt_name = nullptr;
    const char *parse_name = nullptr;
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "|ss",
                                     const_cast<char **>(kwlist),
                                     &fmt_name, &parse_name)) {
        return nullptr;
    }

    const FloatiumFormatBackend *fmt_b = fmt_name
        ? floatium_format_backend(fmt_name)
        : floatium_default_format_backend();
    if (!fmt_b) {
        PyErr_Format(PyExc_ValueError,
                     "unknown format backend: %s (available: %s)",
                     fmt_name ? fmt_name : "(default)",
                     floatium_format_backend_names());
        return nullptr;
    }
    const FloatiumParseBackend *parse_b = parse_name
        ? floatium_parse_backend(parse_name)
        : floatium_default_parse_backend();
    if (!parse_b) {
        PyErr_Format(PyExc_ValueError,
                     "unknown parse backend: %s (available: %s)",
                     parse_name ? parse_name : "(default)",
                     floatium_parse_backend_names());
        return nullptr;
    }

    if (floatium_install(fmt_b, parse_b) < 0) return nullptr;
    Py_RETURN_NONE;
}

static PyObject *py_uninstall(PyObject * /*self*/, PyObject * /*args*/) {
    if (floatium_uninstall() < 0) return nullptr;
    Py_RETURN_NONE;
}

static PyObject *py_is_patched(PyObject * /*self*/, PyObject * /*args*/) {
    return PyBool_FromLong(floatium_is_patched());
}

static PyObject *py_info(PyObject * /*self*/, PyObject * /*args*/) {
    PyObject *d = PyDict_New();
    if (!d) return nullptr;

    PyObject *tmp;

    tmp = PyBool_FromLong(floatium_is_patched());
    PyDict_SetItemString(d, "patched", tmp); Py_DECREF(tmp);

    const char *cur = floatium_current_format_backend();
    tmp = cur ? PyUnicode_FromString(cur) : (Py_INCREF(Py_None), Py_None);
    PyDict_SetItemString(d, "format_backend", tmp); Py_DECREF(tmp);

    cur = floatium_current_parse_backend();
    tmp = cur ? PyUnicode_FromString(cur) : (Py_INCREF(Py_None), Py_None);
    PyDict_SetItemString(d, "parse_backend", tmp); Py_DECREF(tmp);

    tmp = PyUnicode_FromString(floatium_format_backend_names());
    PyDict_SetItemString(d, "available_format_backends", tmp); Py_DECREF(tmp);

    tmp = PyUnicode_FromString(floatium_parse_backend_names());
    PyDict_SetItemString(d, "available_parse_backends", tmp); Py_DECREF(tmp);

    tmp = PyUnicode_FromString(FLOATIUM_DEFAULT_FORMAT_BACKEND);
    PyDict_SetItemString(d, "default_format_backend", tmp); Py_DECREF(tmp);

    tmp = PyUnicode_FromString(FLOATIUM_DEFAULT_PARSE_BACKEND);
    PyDict_SetItemString(d, "default_parse_backend", tmp); Py_DECREF(tmp);

    return d;
}

static PyMethodDef ext_methods[] = {
    {"install",    (PyCFunction)py_install, METH_VARARGS | METH_KEYWORDS,
     "Install backends. Arguments: format_backend='fmt', parse_backend='fast_float'."},
    {"uninstall",  py_uninstall,  METH_NOARGS,  "Restore stock float slots."},
    {"is_patched", py_is_patched, METH_NOARGS,  "Return True if installed."},
    {"info",       py_info,       METH_NOARGS,  "Dict of current state."},
    {nullptr, nullptr, 0, nullptr},
};

static PyModuleDef_Slot ext_slots[] = {
#ifdef Py_MOD_GIL_NOT_USED
    // Free-threaded build: opt in. We only mutate PyFloat_Type at
    // install()/uninstall() time (typically once at interpreter startup)
    // and PyType_Modified() invalidates the type cache for other threads.
    // Lookups after install() are read-only pointer reads from the slot.
    {Py_mod_gil, Py_MOD_GIL_NOT_USED},
#endif
    {0, nullptr},
};

static PyModuleDef ext_module = {
    PyModuleDef_HEAD_INIT,
    "floatium._ext",
    "Backend registry and PyFloat_Type slot patcher.",
    0,
    ext_methods,
    ext_slots,
    nullptr, nullptr, nullptr,
};

PyMODINIT_FUNC PyInit__ext(void) {
    return PyModuleDef_Init(&ext_module);
}
