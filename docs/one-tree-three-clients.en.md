# One tree, three clients, and a deliberate stopping point

[中文](one-tree-three-clients.md) · [MountainRS overview](../README.en.md)

This is a retrospective on **how the project was coordinated**, written after work stopped on September 10, 2026. Counts below describe that historical snapshot. The repository became public on September 18; later documentation commits are outside those counts.

Node IDs, receipt IDs and route revisions are preserved as recorded. They identify objects in the private PF3 service used for this project, not publicly queryable endpoints. [PF3 Showcase](https://github.com/zhaoxiuyue/pf3-showcase) publishes design notes, selected project records and an independent protocol example. The research files linked below are public; the full coordination history remains an author-recorded account.

## 1. The project and its stopping point

MountainRS is my single-author research project on surface-state inference in mountainous terrain. Where slope orientation changes direct illumination and mountains cast shadows kilometers away, the project fixes the criteria for evidence first, then tests which conclusions survive. Most results are negative.

- **Time and scale, as recorded at the stopping point:** June 22–September 10, 2026; 80 days and 93 commits (June: 3, July: 26, August: 53, September: 11). The inventory had 360 tracked files, including 101 evidence artifacts, 17 frozen configs, 19 area READMEs and four architecture PDFs with SHA-256 hashes.
- **Clients:** the latest 100 receipts for PF3 project `proj_6cbeea3266ff` contained actor labels `claude-code` (53), `oauth:chatgpt` (27) and `codex` (20), covering August 4 at 19:33 through September 10 at 12:45. These are client labels from tools associated with two model providers, not a transcript of every model interaction.
- **Tree:** 36 nodes—23 `done`, 10 `planned`, one `paused` and two `failed`. Route `rt_f634f0ab72fb` reached revision 100; the project reached revision 6.
- **Stopping point:** the owner deliberately stopped the project on September 10. Work through Stage 7.8 was closed; Stage 8.0 had passed its activation preflight but was not activated. No nodes were active, no frozen-timing procedure was running, and no work was left half-executed. The recorded reason was that this research did not belong on my own continuing work agenda; resumption would require an external collaboration or commission. A possible technical path forward was not itself a reason to resume. The project lifecycle was set to `abandoned`. This describes the owner's decision, not a successful scientific outcome; negative results remain negative.

The stopping note went through three versions that day: `rc_c3f7e504fd12` (10:41) → undo `rc_d0746bf37d28` (11:25) → `rc_bc7be235821a` (11:25) → undo `rc_884a166ecdf6` (12:44) → final `rc_e1ce8d23bc92` (12:45). Each undo also left a receipt.

## 2. What the coordination mechanisms addressed

The recurring problems were concrete: two windows disagreed about the current state; one changed a contract without the other knowing; an oral rule disappeared at the next handoff; a new window reread all the files and still had to guess. The following mechanisms addressed those observed problems.

**One authoritative state.** All three clients wrote to the same tree. A write supplied the version the client had read; a mismatch was rejected. The route revision increased to 100. The project's internal record of an August 6–8 session reported that the concurrency checks remained effective and no concurrent overwrite occurred during that session. That internal record is not included in this repository.

**Receipts for changes and reversals.** At 23:28 on August 16, the ChatGPT client wrote three node constraints: `rc_c53368606991`, `rc_a535d92965a9` and `rc_343fb54e6858`. Their `undoneBy` fields were later populated. Reversal added a record rather than erasing the earlier one.

**Proposals and approval were separate actions.** A node could propose a change to a downstream contract, not directly approve its own proposal. At 09:45 on September 10, Stage 7.8 proposed a downstream change (`propose_downstream`, `rc_8e2da7aa5f99`). Fourteen seconds later, a separate resolution action applied it (`resolve_proposal`, `rc_b0d3f92eabc9`), advancing the route from revision 99 to 100. The proposal and its resolution had separate receipts.

**Handoff instructions preserved the next window's limits.** After Stage 7.6's ablation work, the final progress record prohibited substantive Stage 7.7 work until the owner decided its role—including freezing the universe on the grounds that “it is an empty set anyway.” The empty-set result was determined, but the freeze had occurred after results were visible. The executing window could not decide for itself that this timing was acceptable.

**Cross-node obligations were attached to the work they governed.** Constraint `nc_8fe5b4709440`, written with receipt `rc_604e9514b224` at 10:01 on August 16, required Stage 7.9 to check two counts before activation and report `blocked` if either was zero. It explicitly excluded bypasses such as switching to direct-only, activating because a fixture ran, or recasting an objective count as `decision_required`. The obligation had to survive a change of execution window. This responded to an actual Stage 7.6 failure: a cross-node timing requirement had been followed from remembered wording, and the freeze came after the first results. The deviation is preserved in the public [timing-deviation record](../stage7_real_weak_closure/stage7_6_optical_operator/evidence/cross-node-timing-deviation-v1.json).

The project also retained 23 confirmed knowledge entries in five categories after stopping. Their contents are outside this public case; the focus here is continuity of project work.

## 3. Three roles, one source of project state

The project used the following division of responsibility. These are workflow roles, not claims that a person cannot inspect facts or that an AI's factual judgment is infallible.

| Role | Reads | Decides | Boundary in this workflow |
|---|---|---|---|
| Owner | Node state and progress | Intent: whether to proceed, which option to choose, which costs to accept | Approval does not establish facts that still need file inspection |
| Discussion window, in web chat | Rules, project overview and current contract | Proposes changes | Cannot verify local files; factual premises remain unverified until checked locally |
| Local execution window | All of the above and local files | Factual feasibility: whether a prerequisite is present or a claim holds | Can stop work when a prerequisite fails; a passing check does not grant permission to proceed |

The August 6–8 work on Stage 7.3 illustrates this division. Contract clause ③ required Stage 7.0's frozen definitions to uniquely specify the core's shape, size, anchor, enumeration order, edge handling, tie-break and selection algorithm. When written, that premise was only an assumption. The local window read the four relevant documents and found all seven items missing. Activation changed from possible to blocked. The owner then approved a core-topology subprotocol; clauses ③ and ⑧ were revised under receipt `rc_8f02b6c39b79` at 10:09 on August 8, allowing the prerequisites to be closed before activation.

The choices were different kinds of work. The AI could not decide for me whether choosing a minimum-support threshold justified dropping one training acquisition and one test acquisition; under that option, 32 of 36 acquisition×band units were fitted and four were `unsupported_calibration`. My preference, in turn, could not establish whether Stage 7.0 actually contained a core definition. That required reading the files.

Even after Stage 7.3's preflight passed, the execution window waited for the owner's instruction. A finding of “feasible” did not authorize the next step.

The owner could change rules, but the change remained visible. During Stage 7.8 domain selection, I added criterion A7 **after results were produced**: human-modified surface fraction ≤ 0.50. The excluded candidate had 54.1%. The execution window applied the decision and marked it `post_result`; it could not be described as preregistered. Later inspection found that the seven retained candidates had fractions of only 0.0–0.1%, so any threshold between 1% and 54% would have excluded the same candidate. The marker still remained: robustness to threshold choice did not make the change prospective.

## 4. An error the workflow did not catch

On September 10, before publication, a separate review found an invalid inference.

An admission criterion required the sky-view factor's IQR within each fold. The stage did not produce fold structures, so it used a region-level measurement and argued that a fold's training support, being a subset, could not have a larger IQR. A region-level value of 0.0655 < 0.10 was then used to conclude that the fold-level requirement failed.

**IQR is not monotone under taking subsets.** For example, using inclusive, linearly interpolated quartiles, eight zeros and two ones have IQR 0, while a subset of two zeros and two ones has IQR 1.

**Documentation correction, September 18:** an earlier version of this retrospective added that a contiguous interval in sorted order was an exception. That was also incorrect. Eight zeros followed by `1, 2, 3, 4` have IQR **1.25**; the contiguous final four values have IQR **1.5**, using the same quartile convention. This corrects the retrospective's explanation; it changes neither the frozen artifacts nor the research gate verdict.

The original inference was handled through a visible correction:

- The original report and script retained their bytes. A separate [defect record](../stage7_real_weak_closure/stage7_8_multidomain_evidence/evidence/requalification-gate-g1-defect-v1.json) withdrew the inference in the append-only evidence area.
- Criterion G1 moved from “not satisfied” to **“not established.”** The overall gate weakened from `not_warranted` to `not_established`. The measured value 0.0655 was not the mistake; the inference from it was.
- The project stopping note stated that G1 was `not_established`, not `not_satisfied`. It also recorded that this correction **did not remove the downstream block**, which depended on an independent count: `activated_count = 0`.
- The defect record explained why the argument survived: it looked like an obvious lemma and agreed with the current decision, so it was not tested separately. **No step within the project caught it.** Other quantile-based arguments had not been comprehensively reviewed; that limitation was recorded too.

There had been an earlier correction. Stage 7.8 withdrew two land-cover findings after a histogram exposed a faulty mode result in the resampling workflow: the returned “savanna” class was only 1.1%, while grassland was 46.1%. [v1](../stage7_real_weak_closure/stage7_8_multidomain_evidence/evidence/screening-findings-v1.json) was retained; [v2](../stage7_real_weak_closure/stage7_8_multidomain_evidence/evidence/screening-findings-v2.json) recorded the withdrawals. The error was caught while checking the factual basis for an owner decision. Otherwise, two false premises would both have argued for changing frozen criteria.

A useful coordination record does not make the reasoning immune to error. It makes the original claim, its correction and the consequences inspectable.

## 5. What this case offers another research group

Multiple people or AI windows can produce work quickly while losing track of which criterion justified a conclusion, or whether that criterion was fixed before or after the result was seen. This case shows one way to retain those connections: criteria, decisions, withdrawals and the reason for stopping all have recorded references. The next window begins from shared project state and can inspect the relevant records—including the ones that contradict an earlier conclusion.

The public research artifacts support checking the examples linked here. The private receipt references preserve the structure of the account, but do not substitute for independently accessible logs or a measured comparison of coordination methods.
