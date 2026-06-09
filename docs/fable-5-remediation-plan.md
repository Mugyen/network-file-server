# Remediation Plan — Fable 5 Review (2026-06-09)

Design document and plan of action addressing every weakness cataloged in
`fable-5-codebase-review.md` §3 (groups A–G). Each item below states the problem, why it
is a problem, the proposed solution, and why that solution was chosen (with rejected
alternatives where the choice is non-obvious). Discussion is intentionally limited to
logic and design — no code.

---

## 1. Purpose & Scope

- Covers all 22 weakness items from the review: A1–A4 (bugs), B1–B2 (swallowed
exceptions), C1–C4 (coupling), D1–D2 (concurrency), E1–E3 (dependency injection),
F1–F5 (frontend), G1–G5 (process).
- Strengths listed in the review (§2) are explicitly out of scope — nothing in this plan
may regress them. The security model, tunnel backpressure, and typed-exception
discipline are treated as invariants.
- Each phase is independently shippable; the plan tolerates being executed partially or
out of order within the stated dependency constraints (§5).

## 2. Guiding Principles

1. **Minimal change per fix.** Every item is solved with the smallest intervention that
  fully resolves it; no opportunistic rewrites of adjacent code.
2. **Strict contracts.** Fixes must preserve or strengthen input validation and typed
  exceptions — never weaken them (project rules 1–2, 11).
3. **Every fix lands with its own tests** covering happy path, edge cases, and failure
  modes (project rule 3).
4. **Behavior preservation.** Except for the four acknowledged bugs (A1–A4), all phases
  are refactors: externally observable behavior must be identical before and after.
5. **Reuse over reinvention.** Where a correct pattern already exists in the codebase
  (the server store's WAL mode, the store's locking discipline, the share-TTL constant
   pattern in the client), the fix adopts that pattern rather than inventing a new one
   (project rule 8).

---

## 3. Phased Plan of Action

Ordering is driven by two rules: **safety nets before changes** and **visibility before
restructuring**. Cheap, isolated fixes come early; architectural moves come after the
ground is instrumented.


| Phase | Theme                                          | Review items   | Risk                      |
| ----- | ---------------------------------------------- | -------------- | ------------------------- |
| 1     | Safety net: CI, lint, types, dead-file cleanup | G1, G2         | None (no behavior change) |
| 2     | Correctness bugs                               | A1, A2, A3, A4 | Low (isolated)            |
| 3     | Observability: eliminate swallowed exceptions  | B1, B2         | Low                       |
| 4     | Concurrency & performance                      | D1, D2, G4, G5 | Low–medium                |
| 5     | Decoupling: break cross-package imports        | C1, C2, C3, C4 | Medium                    |
| 6     | Dependency injection: retire singletons        | E1, E2, E3     | Medium–high               |
| 7     | Frontend structure & trust boundaries          | F1–F5          | Medium                    |
| 8     | Test-coverage rebalancing                      | G3             | None                      |


**Why this order.**

- *Phase 1 first:* the project has ~835 tests that run only when someone remembers to run
them. Automating them before touching any code means every subsequent phase gets free
regression detection. Deleting dead files is zero-risk and removes actively misleading
signals (a Flask-era requirements file in a FastAPI project).
- *Phase 2 second:* the bugs are user-visible or latent-interface failures, each isolated
to one module, and each cheap. Fixing them early decouples "the system is wrong" from
"the system is being restructured."
- *Phase 3 before refactors:* phases 5–6 restructure exactly the code paths the silent
exception handlers currently guard. If those handlers stay silent, a refactor mistake
manifests as a hung transfer instead of a log line. Observability must precede surgery.
- *Phase 4 before architecture:* thread-offloading and journal-mode changes are mechanical
and behavior-preserving; doing them while the module boundaries are still familiar is
cheaper than re-learning the code after the decoupling phase moves things.
- *Phase 5 before 6:* the worst singleton symptom (the agent mutating server-global
config) can only be removed once the agent receives its app through injection — a
Phase 5 outcome. Decoupling defines the seams; DI then formalizes them.
- *Phase 7 parallel-friendly:* frontend work has no backend dependency except A4 (device
identity, done in Phase 2). It can run concurrently with phases 4–6 if desired.
- *Phase 8 last:* every earlier phase adds tests for what it changes; this phase covers
only what no earlier phase touches (tunnel depth, full-path integration, client units).

---

## 4. Per-Item Design Entries

### Group A — Real Bugs (Phase 2)

#### A1. TTL warnings re-fire on every sweep

- **Problem.** The relay's TTL sweep marks a mount as "warned" on an in-memory record
that is rebuilt from SQLite on every sweep cycle. The flag never reaches the database
(`relay/app/services/ttl_sweep.py`, `sqlite_registry.py`).
- **Why it's a problem.** Every mount inside the warning window receives a fresh warning
every sweep interval until it expires — warning spam for agents and users, and the
"warned" state in the data model is a lie: it claims idempotence the system doesn't have.
- **Solution.** Persist the warned flag as part of the mount registry's stored state, set
in the same operation that sends the warning. The sweep reads the persisted flag and
skips already-warned mounts. Reset the flag if a mount's TTL is ever extended, so a
renewed mount earns a fresh warning later.
- **Why this solution.** It makes the existing field mean what it already claims to mean —
the minimal fix. *Rejected:* keeping a separate in-memory "warned set" inside the sweep
task — it would desynchronize from reality across relay restarts and duplicate state
the registry already models.

#### A2. WebSocket bridge handles only text frames

- **Problem.** The agent's WS bridge between the tunnel and the local app always
sends/receives text (`agent/proxy.py`). Binary WS messages crash on decode or are
mishandled, even though the tunnel's WS data frames already carry raw bytes.
- **Why it's a problem.** Any application feature using binary WebSocket payloads breaks
silently through the relay path while working fine on LAN — a capability asymmetry
between the two access modes that is invisible until someone hits it.
- **Solution.** The bridge inspects each frame's actual kind (text vs binary) on both
directions and mirrors it faithfully, encoding the kind alongside the payload so the
receiving side can reconstruct the original frame type. The relay side of the bridge
must apply the same discipline.
- **Why this solution.** The wire protocol already transports bytes; only the bridge's
assumption is wrong. Carrying frame kind explicitly restores WS semantics end-to-end.
*Rejected:* normalizing everything to binary — it would change what the local app
receives and break text-expecting handlers.

#### A3. Tunnel WebSocket Protocol contract omits close

- **Problem.** The structural protocol that defines "a WebSocket" for the tunnel package
lists five operations but not close — yet the connection's shutdown path calls close on
whatever it was given (`tunnel/protocol.py`, `tunnel/connection.py`). A second, smaller
issue: a dead, deprecated event-loop lookup sits in the stream-reading path.
- **Why it's a problem.** An implementor can satisfy the declared contract completely,
pass type-checking, and still fail at runtime during teardown — precisely the moment
when error handling is least observable. Latent contract holes in the project's most
reusable package undermine its 10/10 portability claim.
- **Solution.** Add close to the protocol's required surface so all implementations are
contractually obligated to provide it; delete the dead deprecated call.
- **Why this solution.** One-line contract repair; all known implementations already
comply, so nothing breaks. *Rejected:* tolerating close's absence defensively in the
connection — it would paper over the contract gap rather than fix it and would violate
the strict-contract principle.

#### A4. Client device identity keyed on display name

- **Problem.** The file-request feature passes the human-readable device display name as
the device identifier (`useFileRequests.ts`), so "who made this request" is keyed on a
cosmetic string.
- **Why it's a problem.** Two devices that generate or choose the same display name are
the same identity as far as request ownership is concerned: one can dismiss the other's
requests, and "my requests" filtering is wrong. Renaming a device would also orphan its
requests.
- **Solution.** Generate a stable random identifier per browser once, persist it locally,
and use it as the device ID everywhere identity matters. The display name remains
purely presentational and freely changeable. Existing stored requests keyed by name are
accepted as a one-time migration loss (the data is ephemeral by design).
- **Why this solution.** Identity and presentation are different concerns; separating them
is the standard repair. *Rejected:* deriving an ID from browser fingerprinting — fragile
and privacy-hostile for no benefit when local persistence is available.

### Group B — Swallowed Exceptions (Phase 3)

#### B1. Backend: silent catch-all handlers in the tunnel glue

- **Problem.** The agent proxy, relay mount proxy, relay agent-WS handler, and the server
app factory all contain catch-everything blocks that do nothing — in violation of
project rule 11.
- **Why it's a problem.** These handlers guard the most failure-prone seams in the system
(network bridges, teardown paths, config bootstrapping). When a bridge dies mid-stream
the user sees a hung download and the operator sees nothing. Every future bug in these
paths costs an unbounded amount of debugging time because the first symptom is silence.
The config-swallow case is worse: it converts a legitimate initialization error into a
mysteriously half-configured app.
- **Solution.** Triage each site into one of the three permitted outcomes: (a) log with
full contextual identifiers (mount code, stream ID, direction) and continue, for
expected teardown races where continuing is correct; (b) convert to a typed domain
exception, where the caller can act on it; (c) re-raise, where swallowing was simply
wrong (the config case — the factory should require explicit configuration and fail
loudly when it's absent, with the import-time construction problem handled in E1).
- **Why this solution.** Not all these catches are equal — some guard genuinely benign
races (a peer disconnecting during shutdown), so deleting them all would create noise
or crashes. The triage preserves intentional tolerance while making every tolerated
failure visible and every unintentional one fatal.

#### B2. Client: silent promise rejections

- **Problem.** Clipboard, file-request, and search hooks discard errors in empty catch
callbacks.
- **Why it's a problem.** A failed snippet save looks identical to a successful one; the
user's data is gone and nothing says so. Silent failure in a sync feature is worse than
crashing, because the user keeps trusting state that diverged.
- **Solution.** Route mutation failures through the existing toast-notification
infrastructure so the user learns the operation failed; log non-actionable background
failures (e.g., a search fallback) to the console with context. Where optimistic
updates were applied, roll them back on failure.
- **Why this solution.** The toast system already exists and is the established
user-facing error channel — reuse over new machinery. Rollback restores the invariant
that the UI reflects server state.

### Group C — Cross-Package Coupling (Phase 5)

#### C1. Agent display code imports server services

- **Problem.** The agent's terminal-output module imports QR-code generation and LAN-IP
detection from the server package.
- **Why it's a problem.** Importing the agent drags in the entire server dependency tree
for the sake of printing a QR code — it is the single cheapest-to-fix obstacle to ever
distributing the agent standalone, and the dependency direction is dishonest (a CLI
presentation concern depending on a web application package).
- **Solution.** Relocate the QR and network-detection helpers into the shared utilities
package; both server and agent import them from there.
- **Why this solution.** The helpers are already self-contained (pure stdlib plus small
libraries, no domain logic) — they were simply born in the wrong package. The prior
modularity audit reached the same conclusion. *Rejected:* duplicating them into the
agent — violates the no-duplication rule and doubles maintenance.

#### C2. Agent imports the server's app factory and mutates its config

- **Problem.** To serve proxied requests, the agent imports the server's application
factory, config setter, and auth-token setter, and calls the global setters on every
connection.
- **Why it's a problem.** The agent is permanently welded to one specific server
implementation, cannot be tested without it, and cannot be reused to tunnel any other
local app. The global mutation also means two mounts in one process would overwrite
each other's configuration (the DI half of this is item E2).
- **Solution.** Invert the dependency: the agent's connection logic accepts "a thing that
can produce an ASGI application" as an input. The CLI glue layer — which already
orchestrates both packages — constructs the configured server app and hands the factory
to the agent. The agent's contract becomes "I tunnel any ASGI app," with no knowledge
of which one.
- **Why this solution.** The CLI is the natural composition root; it already knows about
both sides, so injecting there adds no new layer. The agent drops from "depends on
server" to "depends on the ASGI interface," which is the loosest coupling that still
works. *Rejected:* extracting the server app into a third package the agent depends
on — heavier restructuring for the same decoupling result.

#### C3. Server imports relay for file-TTL enrichment

- **Problem.** The server's files router imports a relay service inside a guarded
try/except to enrich listings with expiry data when relay-served, silently degrading
when the import fails.
- **Why it's a problem.** This is the reverse half of a dependency cycle (relay also
imports server), so neither package can be extracted, versioned, or reasoned about
independently. Worse, the guard makes breakage invisible: restructure the relay and the
server quietly stops showing TTLs, with no error anywhere.
- **Solution.** Define a small TTL-provider abstraction inside the server package (the
consumer owns the interface). The server uses it whenever one has been supplied; the
relay implements it and supplies its implementation at mount setup through the agent's
configuration path. Standalone LAN mode supplies nothing and the feature is cleanly
absent — by explicit configuration, not by failed import.
- **Why this solution.** Dependency inversion at exactly one point removes the cycle while
keeping TTL data where it belongs. *Rejected:* moving TTL storage into the server — TTL
is a relay-mount concept (it tracks relay-imposed expiry); the server owning it would
misplace the domain. *Rejected:* having the relay strip/inject TTL via response
post-processing — fragile content rewriting where a typed interface is available.

#### C4. Relay deep-imports server internals

- **Problem.** The relay's dropbox, user-storage, and app-wiring modules import internal
server modules directly (config class, factory, file-service functions, schemas,
connection manager).
- **Why it's a problem.** Relay→server is an acceptable dependency *direction* (the relay
legitimately embeds a server instance for the drop box and reuses file logic), but deep
imports couple the relay to the server's private layout. Any internal server refactor
breaks the relay even when the server's actual behavior is unchanged.
- **Solution.** Declare a public interface for the server package — its top-level
namespace exports the factory, config type, the file-service operations, and the
exception types that external consumers are allowed to use. The relay imports only from
that declared surface. Internal layout becomes free to change.
- **Why this solution.** This is the "empty `__init__` files" gap the prior modularity
audit ranked as the highest-leverage fix; it costs little and creates an enforceable
boundary (lint can forbid deep imports once a public surface exists). *Rejected:*
extracting file operations into a separate package — more moves for a boundary the
public-interface approach already provides.

### Group D — Concurrency & Performance (Phase 4)

#### D1. Blocking filesystem work on the event loop

- **Problem.** Directory listing, recursive search, recursive delete, rename, folder
creation, and the user-quota walk all execute synchronously inside async request
handlers (`server/app/services/file_service.py`, `relay/app/services/user_storage.py`).
- **Why it's a problem.** The server runs on a single event loop — and on mounted setups
the agent runs that loop in the same process as the tunnel. One recursive search over a
large tree (or one slow network filesystem) freezes every concurrent transfer,
heartbeat, and WebSocket message until it finishes. The codebase already does uploads
asynchronously, so the slow paths are exactly the unfixed ones, which makes the failure
intermittent and confusing.
- **Solution.** Offload each blocking filesystem operation to the runtime's worker-thread
pool, awaited from the handler. Path-safety validation stays exactly where it is —
only the execution context changes. Bound the search operation additionally with a
result cap or timeout, since it is the only unbounded-cost operation a user can trigger
with one request.
- **Why this solution.** Thread offloading is the standard, mechanical remedy for
blocking calls in async code: behavior-identical, testable per-operation, no new
dependencies. *Rejected:* converting the whole file service to an async-filesystem
library — large surface change for no additional benefit, since threads are exactly how
such libraries work underneath. *Rejected:* a process pool — filesystem calls are
I/O-bound, not CPU-bound.

#### D2. SQLite journal mode and connection sharing in the relay

- **Problem.** The relay's mount registry and the accounts store use rollback-journal
mode, while the server's state store already uses write-ahead logging; additionally the
file-TTL table shares the registry's single database connection.
- **Why it's a problem.** Rollback mode takes an exclusive lock per write, so the TTL
sweep, agent registrations, and access-request writes serialize against each other and
block readers. The shared connection further serializes two unrelated subsystems.
The inconsistency with the server store also means the codebase demonstrates the right
pattern and ignores it.
- **Solution.** Adopt write-ahead logging for the relay registry and accounts databases,
matching the server store. Give the file-TTL table its own connection so TTL traffic
and registry traffic stop queueing behind one another; document the shared-database
(not shared-connection) arrangement.
- **Why this solution.** It's the codebase's own established pattern applied uniformly;
WAL is strictly better for this concurrent-readers-plus-writers workload.
*Rejected for now:* a connection pool or moving to a client-server database —
unjustified operational weight at this scale.

#### G4 (scheduled here). Access-request listing does per-row user lookups

- **Problem.** Serializing each access request triggers an individual user lookup, so
listing N requests costs N+1 queries.
- **Why it's a problem.** Admin listing degrades linearly with request volume on the
relay's single serialized connection — compounding D2.
- **Solution.** Collect the distinct user IDs for the page being listed and resolve them
in one batched lookup, then serialize from the in-memory map. Provide the batch lookup
as a first-class store operation so other callers reuse it.
- **Why this solution.** Standard N+1 elimination; adding the batch operation to the
abstract store keeps the fix available to any future caller (rule 8).

#### G5 (scheduled here). Share-link in-memory map is unsynchronized

- **Problem.** The share-link service's authoritative in-memory map is a plain dictionary
mutated from request handlers and listing paths, with no synchronization — unlike the
server state store, which already uses a lock.
- **Why it's a problem.** Under a multi-threaded server configuration, concurrent
create/revoke/list operations can interleave mid-mutation; the failure is rare,
unreproducible corruption — the worst kind.
- **Solution.** Apply the same locking discipline the state store already uses to all
read-modify operations on the map, and route mutations through the service's own
methods exclusively (which item E3 enforces anyway by ending direct field access).
- **Why this solution.** Reuses the proven in-repo pattern; the map is small and
contention is negligible, so a lock is sufficient and simple.

### Group E — Dependency Injection (Phase 6)

#### E1. Module-level singletons and import-time app construction

- **Problem.** Roughly nine services are wired through module-global instance variables
with getter/setter pairs, and both applications construct themselves at import time.
- **Why it's a problem.** Initialization order is implicit (call the setter before the
getter or crash); a function's dependencies are invisible in its signature; two app
instances cannot coexist in one process, which forces test choreography (reset globals
between tests) and forbids legitimate multi-instance use. Import-time construction
means merely importing the module performs configuration reads and storage
initialization — side effects where none are expected.
- **Solution.** Construct all services in each application's startup lifecycle, store
them on the application's own state object, and have request handlers declare the
services they need through the framework's dependency-declaration mechanism. The
module-level app objects are replaced by explicit factory invocation at the entry
points (CLI, ASGI server config, tests). Getters/setters are deleted once no caller
remains.
- **Why this solution.** The framework's built-in dependency mechanism provides scoped,
declared, test-overridable wiring with zero new dependencies — the lightest design that
fixes all four symptoms. Migration can proceed service-by-service (each singleton
removed independently), honoring the minimal-change principle. *Rejected:* a DI
container library — adds a dependency and a concept for no capability the framework
lacks. *Rejected:* keeping singletons but adding reset hooks for tests — treats the
symptom and leaves multi-instance use impossible.

#### E2. Agent mutates server-global configuration per connection

- **Problem.** Each agent connection overwrites the server package's global config and
token-service pointers.
- **Why it's a problem.** Cross-package mutation of global state is the strongest form of
coupling; concurrent or repeated mounts in one process silently fight over the same
globals.
- **Solution.** Subsumed by C2 plus E1: the CLI builds a fully configured app via the
factory and hands it to the agent; configuration travels inside the app instance, and
no global is touched. Listed separately so traceability shows it closed.
- **Why this solution.** Falls out of the two refactors for free — no additional design.

#### E3. Router reads a service's private field; tests mutate internals

- **Problem.** The share router reaches into the share service's private link map to
build its response, and tests fake expiry by editing that map directly.
- **Why it's a problem.** The service's encapsulation is fictional: its internal
representation is load-bearing for callers, so it can never change safely. Tests that
poke internals don't prove the public contract.
- **Solution.** The create operation returns the complete record the router needs, so no
caller touches internals. For tests, provide a deliberate seam — injectable clock or
expiry override — so expiry scenarios are exercised through the public API.
- **Why this solution.** Returning what the caller demonstrably needs is the contract the
service should have had; a clock seam is the established technique for time-dependent
testing without internal access.

### Group F — Frontend Structure & Trust Boundaries (Phase 7)

#### F1. Root component owns all application state

- **Problem.** The 613-line root component instantiates every domain hook, owns all
dialog state, and threads results down through props (2–3 levels deep).
- **Why it's a problem.** Every new feature must pass through this file, so it grows
monotonically; unrelated state changes re-render unrelated subtrees; prop chains make
component reuse and testing awkward.
- **Solution.** Introduce two or three context providers cut along the hook boundaries
that already exist — file browsing/selection, upload pipeline, notifications — each
provider owning the corresponding hook's state. Components consume the context they
need; the root component shrinks to layout plus provider composition. Dialog open/close
state moves to the panel components that own each dialog.
- **Why this solution.** The hooks already define the correct domain seams; contexts
formalize them with zero new dependencies. *Rejected:* an external store
(Redux/Zustand) — the state is not shared widely enough to justify a new dependency and
idiom. *Rejected:* a router library for state — routing is not the bottleneck here.

#### F2. WebSocket messages are trusted without validation

- **Problem.** Incoming WS payloads are cast directly to expected shapes in the
WebSocket, clipboard, and device handlers.
- **Why it's a problem.** The WS boundary is the one place data enters the client without
the typed API layer's mediation. A server-side shape change produces silent
misbehavior (wrong fields rendered, handlers no-oping) instead of a detectable error.
- **Solution.** A single validation module defines a type guard per message kind;
every WS handler validates before acting and logs-and-drops messages that fail,
identifying the offending kind. Guards are unit-tested against valid and malformed
payloads.
- **Why this solution.** Roughly ten message shapes need guarding — hand-rolled guards in
one module are proportionate and dependency-free. *Rejected:* a schema library (zod) —
a fine tool, but a new dependency for a small fixed surface contradicts the
minimal-change principle; revisit if message variety grows.

#### F3. No error boundaries

- **Problem.** No error boundary exists anywhere; any render error blanks the whole app.
- **Why it's a problem.** A bug in one panel (e.g., preview) destroys the entire session
including unrelated, functioning features; the user gets a white screen with no
recovery path.
- **Solution.** One error boundary wrapping each SPA root target (the entries of the
client's root-picker), rendering a recovery panel with a reload action and logging the
error. Optionally a second boundary around the preview modal, the most complex
render path.
- **Why this solution.** Boundaries at the root-target level contain failure to the
affected page at near-zero cost; finer-grained boundaries can follow if evidence
warrants.

#### F4. Generic delete helper cannot express empty responses

- **Problem.** The shared delete helper always expects a JSON body and response, so
endpoints returning no content are called with raw fetch workarounds in two API
modules.
- **Why it's a problem.** The API layer's value is uniform error handling and typing;
workarounds bypass both, and the inconsistency invites copy-paste drift.
- **Solution.** Extend the helper's contract to support no-content responses and
optional request bodies; replace the raw-fetch call sites with the helper.
- **Why this solution.** Fixes the leak at its source (the helper's contract) rather than
multiplying call-site exceptions.

#### F5. Small consistency defects

- **Problem & why.** Theme-cycling logic is duplicated in two components (rule 8
violation); upload TTL options are raw strings while share TTLs use the proper
const-object pattern (rule 4 violation); the admin dashboard makes API calls inline
instead of through a domain hook like every other feature; one non-null assertion
papers over a control-flow guarantee. Each is small, but each is a precedent that
invites more of the same.
- **Solution.** Extract theme cycling into the shared theme utility; define an
upload-TTL const object mirroring the share-TTL pattern; extract an admin-data hook
that owns fetching, mutation, and error state; replace the assertion with an explicit
type-narrowed branch.
- **Why this solution.** All four restore existing in-repo conventions — no new patterns
introduced.

### Group G — Process Gaps (Phases 1 and 8)

#### G1. No CI, no enforced linting, no type checking (Phase 1)

- **Problem.** Tests run only manually; the linter is installed but unconfigured; type
hints exist throughout but nothing enforces them in either language.
- **Why it's a problem.** Every guarantee in this plan decays without enforcement: a
contributor (or an AI session) can land a regression and nobody learns until manual
testing. The 835 tests are an unrealized asset.
- **Solution.** One CI workflow running on pushes and pull requests: Python lint, full
pytest suite, client type-check, and client unit tests; the Playwright e2e job runs on
a schedule or label to keep PR feedback fast. Add a lint configuration with an agreed
rule set. Adopt static type checking incrementally: leaf packages first (tunnel,
accounts, shared — already clean and framework-free), then agent, then the apps,
ratcheting strictness package by package.
- **Why this solution.** Incremental adoption avoids the classic failure of strict-mode
big-bangs (a thousand errors, abandoned effort). Leaf-first ordering puts enforcement
on the most reusable code earliest. *Rejected:* enforcing strict typing repo-wide at
once — the FastAPI app layers have dynamic seams that need staged cleanup first.

#### G2. Dead root-level files contradict the project (Phase 1)

- **Problem.** The repository root carries the predecessor Flask app, its launcher, a
hello-world stub, a Flask-era requirements file, and three runner scripts that overlap
the canonical scripts directory.
- **Why it's a problem.** First impressions mislead: a newcomer reading the root
concludes this is a Flask project with competing entry points. Dead files also rot —
they reference modules that no longer exist and erode trust in the rest of the docs.
- **Solution.** Delete all of them; git history preserves anything ever needed again.
Verify nothing references them (docs, scripts, deploy tooling) before removal.
- **Why this solution.** Deletion is the only honest cleanup; archival directories just
relocate the confusion.

#### G3. Test coverage inverted relative to risk (Phase 8)

- **Problem.** The tunnel — the most critical and most reusable package — has the
thinnest test suite; no automated test exercises the full proxy path
(browser→relay→agent→server) beyond auth flows; the client has effectively one unit
test file.
- **Why it's a problem.** Coverage concentrates where bugs are cheap (CRUD handlers) and
thins out where they are expensive (framing, multiplexing, teardown, bridging). The
full-path flow — the product's core promise — is verified only by hand.
- **Solution.** Three additions: (1) tunnel depth — property-style framing round-trip
tests, malformed-frame rejection, stream lifecycle and cancellation races, heartbeat
expiry, backpressure under a slow consumer; (2) one full-path integration test that
mounts a real folder through a real relay in-process and exercises browse, upload,
download, and a WS message through the tunnel; (3) client unit tests for the hooks
touched in Phase 7 (upload queue, WS reconnect gating, clipboard optimistic updates)
plus a Playwright spec covering core browse/upload/preview.
- **Why this solution.** Targets the three named gaps in proportion to risk rather than
chasing a coverage percentage. The e2e harness from the auth suite already provides
the orchestration pattern to reuse.

---

## 5. Dependencies & Risk Register

**Hard dependencies.**

- E2 requires C2 (the agent can only stop mutating globals once the app is injected).
- C3's injection path rides on C2's configuration handoff.
- F1 should precede the client unit tests in G3 (test the refactored hooks, not the
doomed layout).
- B1's config decision (fail loudly) lands fully only with E1 (no import-time
construction); B1 implements the logging, E1 removes the reason the swallow existed.

**Highest-regression-risk items and mitigations.**

- *E1 (singleton retirement):* widest blast radius — mitigate by migrating one service at
a time, keeping the full suite green between each, with Phase 1's CI as the gate.
- *C2/C3 (decoupling):* import restructuring historically hides silent breakage here
(the guarded import) — mitigate by doing B1 first so failures are loud, and by adding
an import-direction lint check (server must not import relay; agent must not import
server) so the cycle cannot silently return.
- *F1 (context split):* render-behavior regressions — mitigate with the Playwright core
flows from G3 written against the pre-refactor UI first, then run across the refactor.
- *D1 (thread offload):* thread-safety of moved operations — mitigate by keeping
validation single-threaded on the loop and offloading only the leaf filesystem call.

## 6. Verification Strategy (per phase)


| Phase | Proof of no regression                                                    | New tests added                                                                                                           |
| ----- | ------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| 1     | Full suite green in CI on an unchanged tree (baseline run)                | CI itself; lint baseline                                                                                                  |
| 2     | Full suite                                                                | Sweep idempotence (A1); binary/text WS round-trip (A2); protocol-conformance check (A3); device-identity persistence (A4) |
| 3     | Full suite; e2e auth suite                                                | Log-emission assertions for each former silent catch; client toast-on-failure tests                                       |
| 4     | Full suite; manual large-directory latency check                          | Concurrency smoke test (slow listing must not stall a parallel request); batch-lookup unit tests; share-map race test     |
| 5     | Full suite; both CLI modes manually exercised (LAN, mount)                | Import-direction lint rule; agent test with a stub ASGI app (proves decoupling)                                           |
| 6     | Full suite; two app instances in one test process (proves multi-instance) | Per-service DI override tests replacing global-reset choreography                                                         |
| 7     | Playwright core-flow suite before and after                               | Type-guard units; error-boundary render test; hook units                                                                  |
| 8     | — (this phase is tests)                                                   | Tunnel depth, full-path integration, client units/e2e                                                                     |


## 7. Traceability


| Review item                           | Phase     | Entry |
| ------------------------------------- | --------- | ----- |
| A1 ttl_warned never persisted         | 2         | §4 A1 |
| A2 WS bridge text-only                | 2         | §4 A2 |
| A3 Protocol missing close + dead call | 2         | §4 A3 |
| A4 device identity conflation         | 2         | §4 A4 |
| B swallowed exceptions (backend)      | 3         | §4 B1 |
| B swallowed exceptions (client)       | 3         | §4 B2 |
| C agent→server (display)              | 5         | §4 C1 |
| C agent→server (factory/config)       | 5         | §4 C2 |
| C server→relay (file TTL)             | 5         | §4 C3 |
| C relay→server deep imports           | 5         | §4 C4 |
| D blocking I/O in async handlers      | 4         | §4 D1 |
| D journal mode / shared connection    | 4         | §4 D2 |
| E singletons + import-time apps       | 6         | §4 E1 |
| E agent global mutation               | 6 (via 5) | §4 E2 |
| E private-field access / test pokes   | 6         | §4 E3 |
| F god component                       | 7         | §4 F1 |
| F WS blind casts                      | 7         | §4 F2 |
| F no error boundaries                 | 7         | §4 F3 |
| F delete-helper contract              | 7         | §4 F4 |
| F consistency defects                 | 7         | §4 F5 |
| G no CI / lint / types                | 1         | §4 G1 |
| G dead root files                     | 1         | §4 G2 |
| G coverage inverted                   | 8         | §4 G3 |
| G access-request N+1                  | 4         | §4 G4 |
| G share-link map unsynchronized       | 4         | §4 G5 |



---

## 8. Completion Record (2026-06-10)

All eight phases executed and verified. Every item in the §7 traceability
table is closed; per-phase details are in docs/project-log.md (eight
"Remediation phase N" entries). Final state: 902 pytest + 89 vitest +
9 Playwright e2e green; ruff, mypy (strict, leaf packages), eslint, tsc
all clean; CI enforces the full gate on push/PR.

Bonus findings fixed along the way (not in the original review): a stale
ttl-closure bug in the upload queue, the requester-fulfillment toast that
could never deliver (WS connection keying), the agent shutdown hang on
in-flight handlers, and a vestigial mock in test_spa_serving.
