# Archimedes V1 — Direct Entity-Transfer Protocol

**Status:** DESIGN COMPLETE FOR REFEREE REVIEW — NO BENCHMARK EXECUTION AUTHORIZED

## 1. Scientific claim under test

V1 tests one narrow D4 claim:

> Can the Full epistemic architecture infer an entity partition from Paradigm A that remains predictive for different entities under a structurally distinct Paradigm B, and does it do so better than a compute-matched Flat baseline?

The only learned representation that crosses from A into B is the committed entity partition. V1 contains no symbolic-law synthesizer and makes no D2 symbolic-law-discovery claim.

## 2. Frozen public geometry

V1 retains the existing finite benchmark geometry:

- entities: exactly `entity_00` through `entity_15`;
- `|E| = 16`;
- actions: integers `0..7`;
- outcomes: integers `0..7`;
- paradigms: `A` and `B`;
- known measurement-corruption rate: `0.02`;
- total observation envelope: exactly `128`.

The causal and Null world definitions remain sealed. No model receives generator source, seeds, ground-truth group assignments, world condition, hidden programs, or validation reports.

## 3. V1 representation

A candidate hypothesis is only an equivalence relation over the 16 opaque entities, represented by integer group assignments.

The Broker enforces:

- `2 <= k_hat <= floor(sqrt(16)) = 4`;
- every entity is assigned exactly once;
- every declared group is used;
- every group contains at least two entities;
- no program, formula, lookup table, or per-entity free parameter may be submitted by the model.

This prevents the trivial memorization solution `k_hat = |E|`.

### Canonical relabeling

Group numbers carry no scientific meaning. Before any candidate is passed between roles, and before the final partition is frozen, the Broker canonicalizes labels without changing membership:

1. compute the lexicographically smallest entity ID in each equivalence class;
2. order classes by that minimum entity ID;
3. relabel them `0,1,...,k_hat-1` in that order.

All hashes, schedules, gates, and B pair construction use this canonical partition. This prevents cosmetic label choices from influencing which interventions are selected.

## 4. Model-call schedule: A only

Because V1 performs no B-side model fitting, all language-model calls occur before the A partition is frozen.

There are exactly six A research rounds, each consuming exactly ten A observations.

### Full arm

For each round:

1. Conjecturer call, max output `4096`, returns up to four candidate partitions;
2. isolated Critic call, max output `2048`, receives only visible records plus normalized candidate partitions and returns exactly ten legal A interventions;
3. Broker executes exactly those ten interventions.

After round 6, one Conjecturer commit call, max output `4096`, either commits one partition or abstains.

Full maximum:

- 7 Conjecturer calls;
- 6 Critic calls;
- 13 model calls total;
- `7*4096 + 6*2048 = 40,960` maximum output tokens.

### Flat arm

For each round:

1. Flat Generate, max output `4096`, returns up to four candidate partitions;
2. Flat Select, max output `2048`, using the same Flat system prompt and role identity, receives visible records plus the normalized candidate set and returns exactly ten A interventions;
3. Broker executes exactly those ten interventions.

After round 6, one Flat commit call, max output `4096`, either commits one partition or abstains.

Flat maximum:

- 6 Generate calls;
- 6 Select calls;
- 1 commit call;
- 13 model calls total;
- `6*4096 + 6*2048 + 4096 = 40,960` maximum output tokens.

There are no model calls after A commit in either arm. B calibration and transfer are deterministic Broker operations. This makes the independent variable the separately prompted and isolated Critic in Full versus same-role Flat self-selection, not additional B reasoning compute.

## 5. Semantic-output failure rule

Structured output is mandatory. No semantic retry is permitted.

- A malformed or schema-invalid research response consumes its model-call slot and closes that arm/world with causal score `0.0` unless the provider's structured-output layer prevented the call from completing at all.
- A malformed or invalid commit closes the arm/world with score `0.0`.
- No second candidate submission, gate retry, or back-transition is allowed.
- Infrastructure/transport retry policy remains a final provider-adapter freeze item and may not depend on scientific content.

## 6. A discovery phase

Exactly 60 A observations are consumed in six ten-observation rounds.

Repeated entity/action interventions are legal and consume budget normally. Repetition numbers are part of the deterministic observation record. Repeats do not create additional cross-entity support for the empirical A gate.

After all 60 observations:

- the model may abstain; or
- it may commit exactly one partition.

Abstention is not permitted before all 60 A discovery observations have been consumed.

## 7. Empirical A gate

The empirical A gate replaces the eliminated symbolic-fit gate. It asks whether the committed grouping compresses A strongly enough to predict an unobserved entity/action measurement from other entities assigned to the same group.

The four-unit gate budget is charged once, immediately after a non-abstaining commit and before Broker semantic validation of the committed partition or gate eligibility. Any invalid partition, insufficient empirical coverage, or failed prediction closes the world; there is no retry.

### 7.1 Discovery reduction at the entity/action level

For each entity `e` and action `a` observed one or more times in the 60 discovery records:

1. collect all observed `y` values for that exact `(e,a)` pair;
2. compute the frequency of each value `0..7`;
3. if one value has a unique maximum frequency, define `V_A(e,a)` as that value;
4. if the maximum is tied, `V_A(e,a)` is undefined.

This prevents repeated measurements of one entity from numerically outweighing distinct entities while still allowing deterministic noise reduction under the publicly known 2% corruption rate.

### 7.2 Empirical group/action cell

For each canonical inferred cell `(q_hat,a)`:

1. collect defined `V_A(e,a)` values from distinct entities whose committed group is `q_hat`;
2. require support from at least two distinct entities;
3. count the supported values;
4. the cell is **eligible** only if one value has a strict majority, i.e. count `> support/2`;
5. the unique strict-majority value is the frozen A-cell prediction `L_A(q_hat,a)`.

No model supplies `L_A`. It is computed by trusted deterministic code from visible discovery records and the frozen partition.

### 7.3 Sealed gate challenge construction

A candidate held-out gate intervention `(e,a)` is eligible only when:

- the committed group of `e` is `q_hat`;
- cell `(q_hat,a)` is eligible under 7.2;
- the exact pair `(e,a)` never appeared in the 60 discovery observations.

Cells are ordered by `(canonical q_hat, action)` ascending. Within a cell, candidate entities are ordered by entity ID.

The Broker selects exactly one challenge from each of the first four eligible **distinct cells**, using the first eligible entity in that cell. If fewer than four distinct eligible cells exist, the A gate fails immediately after its already-charged four-unit budget.

Before observing any gate outcome, the Broker freezes the four predictions and their digest. It then executes the four challenges behind the sealed boundary.

### 7.4 A-gate score

Each challenge is predicted with `L_A(q_hat,a)`.

`A_gate_accuracy = exact_correct / 4`.

The inherited `>= 0.90` gate threshold therefore requires exactly `4/4` correct predictions. Any miss closes the world. Gate outcomes are never offered as a chance to revise the partition.

This gate measures empirical cross-entity compression: the prediction for the held-out `(e,a)` pair is derived from other entities assigned to the same group, not from an entity-specific parameter.

## 8. Partition freeze

A successful A gate freezes, irreversibly:

- canonical `k_hat`;
- canonical entity-to-group assignments;
- finite-discrete domain declaration;
- partition digest;
- A-gate prediction digest.

B cannot merge, split, relabel, revise, or replace the partition. No model call exists after this point.

## 9. B observation budget

The referee-authorized B budget is:

- 32 B calibration observations;
- 32 sealed B transfer observations.

Together with 60 A discovery + 4 A gate, the total remains exactly 128.

The old hidden 8/8 B calibration/transfer entity split is not consulted by the V1 scheduling algorithm. V1 scheduling uses only the public entity/action IDs and the already-frozen inferred partition. Ground-truth group assignments are never consulted.

## 10. Canonical B calibration construction

Let canonical cells be

`C = [(q,a) for q in 0..k_hat-1, a in 0..7]`

ordered first by `q`, then by `a`. For each cell, its entity members are sorted by entity ID.

Calibration selection is deterministic and outcome-blind.

### Pass 0: one observation per cell

For every cell in canonical order, select its first entity as a calibration intervention for that cell's action. This consumes `8*k_hat` observations and ensures every possible inferred `(q,a)` cell has calibration support.

### Additional calibration passes

If fewer than 32 calibration observations have been selected, perform rounds with member index `r = 1,2,...`.

For each round and each cell in canonical order:

- select member `r` for calibration only if `r < group_size - 1`, so at least one entity in that cell remains completely uncalibrated for that action;
- stop immediately when calibration count reaches exactly 32.

This rule is guaranteed to reach 32 for every legal 16-entity partition with `2 <= k_hat <= 4` and at least two entities per group. It never uses outcomes to choose cells or entities.

Each selected entity/action pair is observed once in B calibration.

## 11. B empirical lookup and inconsistency rule

For each inferred cell `(q_hat,a)`, collect all B calibration outcomes assigned to that cell.

- If all observed outcomes in the cell are identical, define `L_B(q_hat,a)` as that value.
- If two or more distinct outcomes occur, mark the cell **inconsistent**.
- No majority vote, smoothing, denoising, optimization, or model intervention is permitted for an inconsistent B cell.

An inconsistent cell deterministically forces every transfer slot relying on that cell to score incorrect.

## 12. Canonical sealed B transfer construction

After all 32 B calibration observations are complete, define for each cell the sorted list of entities whose exact `(entity,action)` pair was **not** used for B calibration.

Transfer slots are allocated in deterministic rounds:

1. round `r=0`: traverse all cells in canonical order and select the first remaining entity in each cell;
2. round `r=1`: traverse all cells again and select the second remaining entity where one exists;
3. continue increasing `r` until exactly 32 transfer interventions are selected.

No transfer entity/action pair may have appeared in B calibration. At least one transfer entity remains in every cell by construction.

Before any transfer outcome is observed, the Broker freezes all 32 transfer records:

- entity ID;
- action;
- canonical inferred group;
- lookup-cell identity;
- predicted `y` if the cell is consistent;
- forced-failure marker if the cell is inconsistent;
- digest over the complete ordered prediction set.

Only after that freeze are the 32 sealed B interventions executed.

## 13. B transfer scoring

For each of the 32 transfer slots:

- consistent lookup cell: correct iff observed `y == L_B(q_hat,a)`;
- inconsistent/missing/invalid cell: deterministically incorrect;
- no abstention or rescue is available after A gate.

Per-world causal score:

`S_world = B_transfer_exact_correct / 32`

if the arm reaches B transfer; otherwise `S_world = 0.0`.

The secondary individual-world D4 threshold remains `S_world >= 0.90`, i.e. at least 29 of 32 exact predictions.

## 14. Null-world positive declaration

For Null worlds, a **positive concept declaration** occurs exactly when a non-abstaining Full-arm partition passes the empirical A gate and advances to B.

Abstention, invalid commit, insufficient A-gate coverage, or A-gate failure is not a positive.

The Full Null false-positive rate must remain strictly below `0.05`. With 100 preregistered Null worlds, `5+` positives triggers the Hallucination Kill.

Prompts never disclose that a noise-only condition exists.

## 15. Primary causal analysis

Use 100 paired causal worlds. Full and Flat receive the same sealed world definitions under opaque IDs, but each arm's B schedule is deterministically conditioned on its own frozen partition as authorized by the referee.

For each world compute

`d_i = S_world,Full - S_world,Flat`.

Primary test remains:

- one-sided paired sign-flip randomization;
- 100 worlds;
- 100,000 sign-flip draws;
- RNG seed `20260830`;
- alpha `0.05`;
- minimum mean Full-over-Flat advantage `0.05`.

Primary success requires both `p < 0.05` and mean paired advantage `>= 0.05`, subject to compute validity.

Failure triggers the Baseline Kill.

## 16. Compute validity

For every provider call, trusted logging records input tokens, output tokens, thought/reasoning tokens when reported, total provider tokens, latency, exact model/version metadata, role, and slot.

Across paired causal worlds:

`R_compute = total_provider_tokens_Full / total_provider_tokens_Flat`.

The accepted asymmetric audit remains:

- if Full otherwise wins but `R_compute > 1.05`, the primary architecture claim is invalidated by compute confounding;
- if `R_compute < 0.95`, report the Flat compute advantage as conservative for a Full win; it does not invalidate the Full win;
- no post-hoc top-up calls or reruns.

Prospective call count and output-token envelopes are exactly matched at 13 calls and 40,960 maximum output tokens per completed A phase.

## 17. Secondary diagnostics

Report, without changing the primary endpoint:

- distribution of B transfer accuracy by arm;
- fraction of causal worlds reaching B;
- fraction with `>=0.90` transfer accuracy;
- `k_hat` distribution;
- after unblinding only, `delta_k = k_hat-k_true` and exact partition recovery up to label permutation;
- A-gate coverage and pass rate;
- number of eligible A cells at commit;
- B inconsistent-cell count;
- calibration and transfer coverage by inferred cell;
- abstention/schema-failure rates;
- provider compute and latency by arm.

No true-cardinality or exact-partition diagnostic is exposed before the experimental record is frozen.

## 18. Benchmark firewalls

Before explicit referee benchmark authorization:

- no causal world may be supplied to an LLM;
- no Null world may be supplied to an LLM;
- no prompt may be tuned against benchmark outcomes;
- implementation tests use only independently hand-constructed deterministic fixtures;
- the V1 Broker may not import or inspect ground-truth partition fields for scheduling or scoring predictions;
- hidden A/B programs are used only by the sealed runtime and pre-existing hidden-world validity checks.

## 19. Interpretation boundaries

A successful V1 supports only the claim that an A-discovered entity grouping had predictive reach to different entities under a distinct B mechanism after bounded B calibration.

It does not establish:

- symbolic law discovery;
- free-form ontology invention;
- extrapolation to uncalibrated group/action cells;
- causal-mechanism identification;
- D5 ontology revision.

Those remain future experiments.