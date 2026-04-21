// Copyright 2018 Ulf Adams
//
// The contents of this file may be used under the terms of the Apache License,
// Version 2.0.
//
//    (See accompanying file LICENSE-Apache or copy at
//     http://www.apache.org/licenses/LICENSE-2.0)
//
// Alternatively, the contents of this file may be used under the terms of
// the Boost Software License, Version 1.0.
//    (See accompanying file LICENSE-Boost or copy at
//     https://www.boost.org/LICENSE_1_0.txt)
//
// Unless required by applicable law or agreed to in writing, this software
// is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
// KIND, either express or implied.
#ifndef RYU_H
#define RYU_H

#ifdef __cplusplus
extern "C" {
#endif

#include <inttypes.h>
#include <stddef.h>

int d2s_buffered_n(double f, char* result);
void d2s_buffered(double f, char* result);
char* d2s(double f);

int f2s_buffered_n(float f, char* result);
void f2s_buffered(float f, char* result);
char* f2s(float f);

// Caller must supply a buffer of at least d2fixed_buffered_size(precision) bytes
int d2fixed_buffered_n(double d, uint32_t precision, char* result);
void d2fixed_buffered(double d, uint32_t precision, char* result);
char* d2fixed(double d, uint32_t precision);

// Worst-case output size of d2fixed_buffered_n, including the trailing NUL:
// sign + up to 310 integer digits (309 + optional carry) + '.' + precision
// fractional digits + NUL.
static inline size_t d2fixed_buffered_size(uint32_t precision) {
  return (size_t)precision + 325;
}

// Caller must supply a buffer of at least d2exp_buffered_size(precision) bytes
int d2exp_buffered_n(double d, uint32_t precision, char* result);
void d2exp_buffered(double d, uint32_t precision, char* result);
char* d2exp(double d, uint32_t precision);

// Worst-case output size of d2exp_buffered_n, including the trailing NUL:
// sign + 1 digit + '.' + precision fractional digits + 'e' + sign + up to
// 3 exponent digits + NUL.
static inline size_t d2exp_buffered_size(uint32_t precision) {
  return (size_t)precision + 16;
}

#ifdef __cplusplus
}
#endif

#endif // RYU_H
