// SPDX-License-Identifier: AGPL-3.0-only
// Copie para credentials_private.h (ignorado pelo Git). Nunca versione o token.
#pragma once
// Token de dispositivo provisionado no servidor; revogável.
static const char DEVICE_TOKEN[] = "PREENCHA_TOKEN_DO_DISPOSITIVO";
// CA pública ISRG Root X1 (Let's Encrypt), em PEM.
static const char ROOT_CA[] = R"PEM(
-----BEGIN CERTIFICATE-----
COLE AQUI O PEM DA ISRG ROOT X1
-----END CERTIFICATE-----
)PEM";
