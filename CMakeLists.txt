cmake_minimum_required(VERSION 3.20)
project(floatium LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# --- Backend selection ------------------------------------------------------
# Format backend: fmt (default), stock (for A/B vs CPython's dtoa), all.
# Parse backend:  fast_float (default), stock, all.
#
# With "all", every backend is compiled in and the active one is chosen at
# runtime via env vars FLOATIUM_FORMAT_BACKEND / FLOATIUM_PARSE_BACKEND.
set(FLOATIUM_FORMAT_BACKEND "fmt" CACHE STRING "Format backend: fmt, stock, all")
set(FLOATIUM_PARSE_BACKEND  "fast_float" CACHE STRING "Parse backend: fast_float, stock, all")
set_property(CACHE FLOATIUM_FORMAT_BACKEND PROPERTY STRINGS fmt stock all)
set_property(CACHE FLOATIUM_PARSE_BACKEND  PROPERTY STRINGS fast_float stock all)

# --- Python -----------------------------------------------------------------
# scikit-build-core passes Python3_EXECUTABLE via the FindPython hint file.
find_package(Python3 REQUIRED COMPONENTS Interpreter Development.Module)

# --- Sources ----------------------------------------------------------------
set(FLOATIUM_SRCS
    src/ext.cc
    src/slots.cc
    src/format_short.cc
    src/backends/registry.cc
    src/cpython_adapter/fmt_dtoa.cc
    src/cpython_adapter/fast_float_strtod.cc
)

# Compile-in backends based on selection. Default selection is made in
# backends/registry.cc at runtime via FLOATIUM_DEFAULT_FORMAT_BACKEND etc.
if(FLOATIUM_FORMAT_BACKEND STREQUAL "fmt" OR FLOATIUM_FORMAT_BACKEND STREQUAL "all")
    list(APPEND FLOATIUM_SRCS src/backends/fmt_format.cc)
    set(FLOATIUM_HAS_FMT_FORMAT 1)
endif()
if(FLOATIUM_FORMAT_BACKEND STREQUAL "stock" OR FLOATIUM_FORMAT_BACKEND STREQUAL "all")
    list(APPEND FLOATIUM_SRCS src/backends/stock_format.cc)
    set(FLOATIUM_HAS_STOCK_FORMAT 1)
endif()
if(FLOATIUM_PARSE_BACKEND STREQUAL "fast_float" OR FLOATIUM_PARSE_BACKEND STREQUAL "all")
    list(APPEND FLOATIUM_SRCS src/backends/fast_float_parse.cc)
    set(FLOATIUM_HAS_FAST_FLOAT_PARSE 1)
endif()
if(FLOATIUM_PARSE_BACKEND STREQUAL "stock" OR FLOATIUM_PARSE_BACKEND STREQUAL "all")
    list(APPEND FLOATIUM_SRCS src/backends/stock_parse.cc)
    set(FLOATIUM_HAS_STOCK_PARSE 1)
endif()

python3_add_library(_ext MODULE ${FLOATIUM_SRCS} WITH_SOABI)

target_include_directories(_ext PRIVATE
    src
    src/common
    third_party/fmt
    third_party/fast_float
)

# Match the build flags the CPython fmt-fastfloat branch uses for the
# vendored C++ code. -fno-exceptions / -fno-rtti keep the libstdc++ footprint
# minimal and avoid any dependency on C++ runtime type info.
if(NOT MSVC)
    target_compile_options(_ext PRIVATE
        -fno-exceptions
        -fno-rtti
        -fvisibility=hidden
        -Wall
        -Wextra
        -Wno-unused-parameter
    )
else()
    target_compile_options(_ext PRIVATE
        /EHs-c-      # disable C++ exceptions
        /GR-         # disable RTTI
        /utf-8       # fmt's base.h static_asserts against CP-1252 sources
        /W3
        /wd4100      # unreferenced formal parameter
    )
endif()

# Configure-time feature flags surfaced to C++
target_compile_definitions(_ext PRIVATE
    $<$<BOOL:${FLOATIUM_HAS_FMT_FORMAT}>:FLOATIUM_HAS_FMT_FORMAT=1>
    $<$<BOOL:${FLOATIUM_HAS_STOCK_FORMAT}>:FLOATIUM_HAS_STOCK_FORMAT=1>
    $<$<BOOL:${FLOATIUM_HAS_FAST_FLOAT_PARSE}>:FLOATIUM_HAS_FAST_FLOAT_PARSE=1>
    $<$<BOOL:${FLOATIUM_HAS_STOCK_PARSE}>:FLOATIUM_HAS_STOCK_PARSE=1>
    FLOATIUM_DEFAULT_FORMAT_BACKEND="${FLOATIUM_FORMAT_BACKEND}"
    FLOATIUM_DEFAULT_PARSE_BACKEND="${FLOATIUM_PARSE_BACKEND}"
)

install(TARGETS _ext DESTINATION floatium)

# .pth files must sit directly in site-packages (the purelib/platlib root)
# to be processed by site.py. scikit-build-core maps `DESTINATION .` to
# the wheel's platlib root, which becomes site-packages/ after install.
install(FILES ${CMAKE_CURRENT_SOURCE_DIR}/floatium.pth DESTINATION .)
