/**
 * Generated-API type access point.
 *
 * `api.gen.ts` is generated from the server's OpenAPI schema by
 * `scripts/gen_api_types.sh` — never edit it by hand. This module exposes its
 * schema namespace under a clean name so response/request types can be
 * derived from the backend contract (`Schemas["FileEntry"]`, etc.) instead of
 * being hand-written and drifting out of sync.
 */
import type { components } from "./api.gen";

export type Schemas = components["schemas"];
