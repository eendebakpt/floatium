// "stock" parse backend: uses the C library strtod. Mainly for A/B
// comparison and to have a "noop" option when swapping backends.
#include "common/backend.h"

#include <Python.h>

#include <cstdlib>

extern "C" {

static double stock_strtod(const char *nptr, char **endptr) {
    return std::strtod(nptr, endptr);
}

}  // extern "C"

namespace {

struct Register {
    Register() {
        static const FloatiumParseBackend b = {
            /*name=*/"stock",
            /*strtod=*/&stock_strtod,
        };
        floatium::register_parse_backend(b);
    }
};
Register _reg;

}  // namespace
