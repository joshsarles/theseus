// SPDX-License-Identifier: AGPL-3.0-only
// Pepr module entrypoint — wires the THESEUS rails Capability into the runtime.
// `npx pepr build` discovers this file (the "module" entry) and the `pepr` block
// in package.json. The PeprModule constructor reads { description, pepr } from
// package.json; capabilities are passed as the second arg.
import { PeprModule } from "pepr";
// cfg is the parsed package.json (Pepr injects it at build/dev time).
import cfg from "./package.json";

import { TheseusPolicies } from "./theseus-policies";

new PeprModule(cfg, [TheseusPolicies]);
