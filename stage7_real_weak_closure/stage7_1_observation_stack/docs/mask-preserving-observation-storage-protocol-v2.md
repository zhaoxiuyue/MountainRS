# Stage 7.1 mask-preserving observation storage protocol v2

Status: **frozen and preregistered before the first v2 Export task**  
Decision authority: PF3 `C7.1-D3B-M2`, recorded 2026-08-04  
Scope: replaces the failed **v1 three-band single-file storage route only**. It
does not revise the frozen 21-acquisition universe, acquisition identities,
canonical order, ROI, target grid, candidate states, support semantics, or
split rule.

## 1. Why this protocol exists

`C7.1-D3B-M1` established that ten frozen-universe scenes have target-grid
`SR_B4` source-mask zeros. Those zeros are source-native missingness, are not
explained by `QA_PIXEL` bit 0 or `QA_RADSAT` B4 saturation, and must not be
collapsed into a shared GeoTIFF nodata value, an SR fill DN, or legal
`QA_PIXEL = 0`.

The v1 manifest and its `source_masks_must_be_all_valid` gate remain immutable
historical evidence. This v2 protocol supersedes that storage route; it does
not rewrite v1, exclude the ten scenes, create a new acquisition, or declare a
scene stack-eligible.

## 2. Frozen v2 transfer representation

Each canonical acquisition is transferred by exactly one Earth Engine task to
one six-band GeoTIFF. The authoritative band order is:

1. `SR_B4` — original unscaled raw uint16 DN;
2. `SR_B5` — original unscaled raw uint16 DN;
3. `QA_PIXEL` — original complete uint16 QA word;
4. `SR_B4_VALID` — uint16 values exactly 0 or 1;
5. `SR_B5_VALID` — uint16 values exactly 0 or 1;
6. `QA_PIXEL_VALID` — uint16 values exactly 0 or 1.

For each source band, the executor must first derive `VALID` from that band's
Earth Engine source mask on the exact frozen target grid. Only after that
derivation may it use `unmask(0)` on the data band solely to serialize a
full-grid transfer array. It may never scale, offset, QA-mask, score, rank or
otherwise rewrite valid raw DN values. The `VALID` bands are full-grid arrays,
are the sole authority for reconstructing the original source mask, and make a
raw data value of zero unambiguous.

No dataset or band nodata is set. In particular, neither transfer zero nor
`QA_PIXEL = 0` means missing. The source-band mask, source SR fill DN,
`QA_PIXEL` bit 0 and GeoTIFF nodata are four distinct concepts.

## 3. Invariants and local reconciliation

The output must use the frozen `shadow-risk-b-b4-grid-v1` CRS, six-element
affine transform, shape, bounds and pixel alignment. The task may not set
`scale`, `dimensions`, `bestEffort`, a non-nearest resampling mode, a shared
nodata value, or a partial/sharded-output option.

Before an acquisition can be called `stack_eligible`, local reconciliation
must establish all of the following:

- one unique local GeoTIFF exists at the manifest-relative path and has a
  recorded hash and byte size;
- it has exactly the six uint16 bands in the frozen order, no nodata and the
  exact frozen grid;
- every `*_VALID` array is full-grid and contains only 0 or 1;
- each data cell with `VALID = 0` is transfer zero; reconstructing its source
  mask from `VALID` gives the exact per-band target-grid `mask=0` count in
  `source-mask-causal-audit-v1.json` for that acquisition;
- the reconstructed masks, raw DN bands and raw QA word are used in the
  existing frozen support definition, including `base_valid_land > 0`.

The last bullet is a direct application of `selection-protocol.md` section 3:
`stack_eligible` requires exported members, verified hashes, exact grid
integrity and nonzero `base_valid_land`. It adds no numerical threshold. If a
future local audit cannot uniquely apply those already frozen rules, it must
record the problem and stop rather than infer a threshold from the results.

## 4. Task serialisation and state boundary

The candidate universe remains all 21 acquisitions in canonical catalog order.
Every acquisition stays in that universe even if its source mask has zeros.
There may be at most one active v2 export task. A task submission, a running
task, a Drive file or a local download is not itself stack eligibility or
success.

Task lineage is append-only and is stored separately from the immutable v2
manifest. An unconfirmed task-start outcome is `unknown`, blocks resubmission
and requires reconciliation. Existing output paths are never overwritten. A
terminal external success is still incomplete until the local checks above pass.

`stack_eligible` remains `not_yet_evaluated`, the split remains
`not_yet_assigned`, and model eligibility remains outside Stage 7.1 until all
local file and support audits have completed.

## 5. Explicit non-actions

This protocol authorizes neither an Earth Engine asset nor an image download by
itself. It does not change the existing Export v1 contract, relax the frozen
candidate set, select a split, exclude the ten source-mask scenes, run model
work, or create a PF3 node. Task creation is permitted only by a separately
authorized execution of the audited v2 manifest.
