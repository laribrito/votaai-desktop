/*
 * VotaAI Desktop — Núcleo Nativo de Segurança, Ofuscação e Integridade (_votaai_native_core.so)
 *
 * Implementa:
 *   1. Achatamento de Fluxo de Controle (Control Flow Flattening - CFF) com dispatchers
 *      baseados em tabelas de salto (switch 0..11 com 12 estados densos) e predicados opacos.
 *   2. Ofuscação de strings em tempo de compilação (XOR stream cipher em stack),
 *      eliminando literais sensíveis da seção .rodata.
 *   3. Decifragem em memória dos módulos Python congelados (PYZ) e selo criptográfico
 *      de integridade para o modo congelado (sys.frozen).
 */

#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define HIDDEN_NOINLINE __attribute__((visibility("hidden"), noinline))
#define EXPORT_API      __attribute__((visibility("default"), noinline))

static volatile uint32_t g_cff_entropy = 0x564F5441u;

/* Predicados opacos invariantes: x*(x+1) é sempre par */
static inline int opaque_true(uint32_t x) {
    uint32_t v = x ^ g_cff_entropy;
    return (((v * (v + 1u)) & 1u) == 0u);
}

static inline int opaque_false(uint32_t x) {
    uint32_t v = x ^ g_cff_entropy;
    return (((v * (v + 1u)) & 1u) != 0u);
}

static inline void secure_wipe(volatile uint8_t *buf, size_t len) {
    for (size_t i = 0; i < len; ++i) {
        buf[i] = 0;
    }
}

/*
 * Detector nativo de TracerPid com Control Flow Flattening (cases densos 0..11 -> jump table)
 * e strings "/proc/self/status" e "TracerPid:" cifradas via XOR ((0x5A + i*7) & 0xFF).
 */
HIDDEN_NOINLINE int cff_check_tracer_pid(uint32_t seed) {
    volatile uint32_t state = 0u;
    /* "/proc/self/status" cifrado */
    static const uint8_t enc_path[17] = {
        0x75, 0x11, 0x1a, 0x00, 0x15, 0x52, 0xf7, 0xee, 0xfe, 0xff,
        0x8f, 0xd4, 0xda, 0xd4, 0xc8, 0xb6, 0xb9
    };
    /* "TracerPid:" cifrado */
    static const uint8_t enc_tag[10] = {
        0x0e, 0x13, 0x09, 0x0c, 0x13, 0x0f, 0xd4, 0xe2, 0xf6, 0xa3
    };
    char dec_path[18];
    char dec_tag[11];
    FILE *fp = NULL;
    char line[256];
    int tracer_pid = 0;
    int result = 0;
    uint32_t guard_acc = seed ^ 0xA55AA55Au;

    while (state < 12u) {
        switch (state) {
            case 0u:
                for (size_t i = 0; i < 17; ++i) {
                    uint8_t k = (uint8_t)((0x5Au + (i * 7u)) & 0xFFu);
                    dec_path[i] = (char)(enc_path[i] ^ k);
                }
                dec_path[17] = '\0';
                guard_acc = (guard_acc * 33u) ^ 0x11u;
                state = opaque_true(guard_acc) ? 1u : 10u;
                break;
            case 1u:
                for (size_t i = 0; i < 10; ++i) {
                    uint8_t k = (uint8_t)((0x5Au + (i * 7u)) & 0xFFu);
                    dec_tag[i] = (char)(enc_tag[i] ^ k);
                }
                dec_tag[10] = '\0';
                guard_acc ^= 0x22u;
                state = 2u;
                break;
            case 2u:
                fp = fopen(dec_path, "r");
                guard_acc += (fp != NULL) ? 3u : 7u;
                state = (fp != NULL) ? 3u : 8u;
                break;
            case 3u:
                if (fgets(line, sizeof(line), fp) != NULL) {
                    state = 4u;
                } else {
                    state = 7u;
                }
                break;
            case 4u:
                if (strncmp(line, dec_tag, 10) == 0) {
                    state = 5u;
                } else {
                    state = opaque_false(guard_acc) ? 10u : 3u;
                }
                break;
            case 5u:
                tracer_pid = atoi(line + 10);
                guard_acc ^= (uint32_t)tracer_pid;
                state = 6u;
                break;
            case 6u:
                if (tracer_pid != 0) {
                    static const uint8_t enc_msg[78] = {
                        0x50, 0x3a, 0x3e, 0x00, 0x02, 0x1c, 0xc5, 0xc2, 0xb2, 0xca, 0xc5, 0xc4, 0xdb,
                        0xc7, 0xd5, 0xb7, 0xb3, 0x96, 0xad, 0xbe, 0x94, 0x89, 0xa9, 0xdb, 0x54, 0x40,
                        0x5f, 0x5b, 0x5f, 0xe6, 0xab, 0xf0, 0xb9, 0x0e, 0x68, 0x0c, 0x04, 0x9e, 0xe9,
                        0x3f, 0x3b, 0x3a, 0xc1, 0xa7, 0xca, 0xd0, 0xc8, 0xe6, 0xe9, 0xe5, 0xf9, 0xfb,
                        0x87, 0xf7, 0xf4, 0x80, 0xa3, 0x87, 0x84, 0x9e, 0xd3, 0x41, 0x69, 0x71, 0x6f,
                        0x46, 0x75, 0x0f, 0x62, 0x4f, 0x25, 0x28, 0x37, 0x2b, 0x30, 0x0e, 0x0a, 0x7f
                    };
                    uint8_t dec_msg[78];
                    for (size_t i = 0; i < 78; ++i) {
                        uint8_t k = (uint8_t)((0x5Au + (i * 7u)) & 0xFFu);
                        dec_msg[i] = enc_msg[i] ^ k;
                    }
                    ssize_t w = write(2, dec_msg, sizeof(dec_msg));
                    (void)w;
                    secure_wipe((volatile uint8_t *)dec_msg, sizeof(dec_msg));
                    result = 1;
                } else {
                    result = 0;
                }
                state = 7u;
                break;
            case 7u:
                if (fp != NULL) {
                    fclose(fp);
                    fp = NULL;
                }
                state = 8u;
                break;
            case 8u:
                secure_wipe((volatile uint8_t *)dec_path, sizeof(dec_path));
                secure_wipe((volatile uint8_t *)dec_tag, sizeof(dec_tag));
                state = opaque_true(seed) ? 9u : 10u;
                break;
            case 9u:
                g_cff_entropy ^= (guard_acc & 0u);
                state = 11u;
                break;
            case 10u:
                result = -1;
                state = 11u;
                break;
            case 11u:
                state = 12u;
                break;
        }
    }
    return result;
}

/*
 * Passo do gerador de keystream com Control Flow Flattening (cases densos 0..11)
 */
HIDDEN_NOINLINE uint32_t cff_keystream_step(uint32_t s, uint32_t idx, uint32_t salt) {
    volatile uint32_t state = 0u;
    uint32_t acc = s ^ (idx * 0x9E3779B9u);

    while (state < 12u) {
        switch (state) {
            case 0u:
                acc ^= (salt << 7) | (salt >> 25);
                state = opaque_true(acc) ? 1u : 10u;
                break;
            case 1u:
                acc = (acc + 0x7F4A7C15u) ^ (acc >> 11);
                state = 2u;
                break;
            case 2u:
                acc *= 0x85EBCA6Bu;
                state = 3u;
                break;
            case 3u:
                acc ^= (acc >> 13);
                state = opaque_false(idx) ? 10u : 4u;
                break;
            case 4u:
                acc *= 0xC2B2AE35u;
                state = 5u;
                break;
            case 5u:
                acc ^= (acc >> 16);
                state = 6u;
                break;
            case 6u:
                acc = ((acc << 3) | (acc >> 29)) ^ (idx + 0xA5A55A5Au);
                state = 7u;
                break;
            case 7u:
                acc ^= (salt * 0x27D4EB2Du);
                state = 8u;
                break;
            case 8u:
                acc = (acc ^ (acc >> 15)) * 0x165667B1u;
                state = 9u;
                break;
            case 9u:
                acc ^= (acc >> 13);
                state = 11u;
                break;
            case 10u:
                acc ^= 0xDEADBEEFu;
                state = 11u;
                break;
            case 11u:
                state = 12u;
                break;
        }
    }
    return acc;
}

/*
 * Selo criptográfico de integridade 64-bit com Control Flow Flattening (cases densos 0..11)
 */
HIDDEN_NOINLINE uint64_t cff_compute_integrity_seal(const uint8_t *data, size_t len, uint64_t key_seed) {
    volatile uint32_t state = 0u;
    uint64_t h1 = 0xCBF29CE484222325ULL ^ key_seed;
    uint64_t h2 = 0x84222325CBF29CE4ULL + (key_seed * 0x100000001B3ULL);
    size_t i = 0;

    while (state < 12u) {
        switch (state) {
            case 0u:
                state = (data == NULL || len == 0) ? 10u : 1u;
                break;
            case 1u:
                state = (i < len) ? 2u : 6u;
                break;
            case 2u:
                h1 ^= (uint64_t)data[i];
                h1 *= 0x100000001B3ULL;
                state = opaque_true((uint32_t)i) ? 3u : 10u;
                break;
            case 3u:
                h2 ^= ((uint64_t)data[i] << ((i & 7u) * 8u));
                h2 = (h2 << 13) | (h2 >> 51);
                state = 4u;
                break;
            case 4u:
                h2 *= 0x9E3779B97F4A7C15ULL;
                h1 ^= (h2 >> 17);
                state = 5u;
                break;
            case 5u:
                ++i;
                state = 1u;
                break;
            case 6u:
                h1 ^= (h2 >> 29) ^ (uint64_t)len;
                h1 *= 0xFF51AFD7ED558CCDULL;
                state = 7u;
                break;
            case 7u:
                h1 ^= (h1 >> 33);
                h1 *= 0xC4CEB9FE1A85EC53ULL;
                state = 8u;
                break;
            case 8u:
                h1 ^= (h1 >> 33);
                state = opaque_false((uint32_t)len) ? 10u : 9u;
                break;
            case 9u:
                state = 11u;
                break;
            case 10u:
                h1 = 0ULL;
                state = 11u;
                break;
            case 11u:
                state = 12u;
                break;
        }
    }
    return h1;
}

/*
 * Transforma (cifra/decifra) in-place um buffer de bytecode congelado com CFF (cases 0..11)
 */
EXPORT_API int votaai_transform_bytecode(uint8_t *buf, size_t len, uint32_t module_seed) {
    volatile uint32_t state = 0u;
    size_t idx = 0;
    uint32_t ks = 0;
    int rc = -1;

    while (state < 12u) {
        switch (state) {
            case 0u:
                state = (buf == NULL || len == 0) ? 10u : 1u;
                break;
            case 1u:
                ks = 0x564F5441u ^ module_seed;
                state = opaque_true(module_seed) ? 2u : 10u;
                break;
            case 2u:
                state = (idx < len) ? 3u : 8u;
                break;
            case 3u:
                if ((idx & 3u) == 0u) {
                    state = 4u;
                } else {
                    state = 5u;
                }
                break;
            case 4u:
                ks = cff_keystream_step(ks, (uint32_t)idx, module_seed);
                state = 5u;
                break;
            case 5u: {
                uint8_t mask = (uint8_t)((ks >> ((idx & 3u) * 8u)) & 0xFFu);
                buf[idx] ^= mask;
                state = 6u;
                break;
            }
            case 6u:
                ++idx;
                state = opaque_false((uint32_t)idx) ? 10u : 7u;
                break;
            case 7u:
                state = 2u;
                break;
            case 8u:
                rc = 0;
                state = 9u;
                break;
            case 9u:
                state = 11u;
                break;
            case 10u:
                rc = -1;
                state = 11u;
                break;
            case 11u:
                state = 12u;
                break;
        }
    }
    return rc;
}

EXPORT_API uint64_t votaai_compute_seal(const uint8_t *data, size_t len, uint64_t seed) {
    return cff_compute_integrity_seal(data, len, seed);
}

EXPORT_API int votaai_native_guard_check(uint32_t seed) {
    return cff_check_tracer_pid(seed);
}
