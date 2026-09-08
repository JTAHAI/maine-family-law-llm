# v9 specialist release constraint

Latest Evidence base control completed: one of four fictional development cases
passes; scoped absence, injection and unrelated-clock interpretation fail.
See `V9_NEXT_MODEL_RUN.md` latest override. Both base controls are complete.
Next is targeted fresh TRAIN coverage correction, not another completed control.

The owner explicitly requires Evidence Review and Drafting in the next MSIX.
Do not build another model-empty maintenance package. Preserve the existing
8.0.2 artifact. Do not bump to 9.0.0 or claim a specialist is ready merely because
weights load, training loss decreases, application tests pass, or one pilot passes.

The next package requires both specialists to produce useful source-bound answers,
pass pinned answer-quality and adversarial regression, and work through the actual
application with hardware admission, source drill-down, privacy, matter isolation,
visible review status, cancellation, and restart. The existing production-admission
and output-verification gates remain in force. Never fabricate legal expertise,
attorney review, independent evaluation, or release sign-offs.

Current priority: correct source-sensitive answer quality using measured fresh
native-frame adapter trials. The initial framing ablation is complete; native
framing alone did not repair the old adapters. Fresh 64-example Evidence and
Drafting adapters now exist but still have measured answer defects. A larger
512-example Evidence candidate is trained and has completed both small quality
suites; arithmetic and instruction-exclusion failures remain. The tested v3
correction corpus has now completed a fresh 512-step Evidence training run;
its paired and adversarial evaluations completed and still failed source meaning,
quote attribution and arithmetic. Three of eight inspected development answers
passed their semantic criteria; this is not a general quality score. Drafting v3
also completed 512-step fresh training. Its paired test has three semantic passes
and one semantic failure, but all four answers have formatting, task/meaning or
source-reference defects. Its adversarial test also completed: one of four
passes, while the others fail useful task completion, explicitly requested
privacy redaction, or preservation of unchanged source terms. Across Drafting's
eight inspected cases, four meet basic semantics but only one meets all scoped
acceptance checks. Neither specialist is qualified for release. Available RAM
has recovered to about 22 GiB; answer quality, not current RAM shortage, is the
immediate blocker. The unchanged-base Drafting control also fails privacy and
meaningful clarification, but correctly preserves terms the candidate changed.
Thus removing the adapter alone is not a solution. The next control is Evidence
under the same v3 prompt before selecting another correction; do not repeat
completed controls or failed adapters.
`scripts/diagnose_mfl_prompt_framing.py` compares the unchanged base and a pinned
adapter on fictional development cases. This diagnostic is not a replacement
production backend or final holdout. See `V9_MODEL_CORRECTION_2026-09-06.md` for
the current resource guards and exact evidence, and `V9_NEXT_MODEL_RUN.md` for
the precise pending runs, not the older model-empty notes.
Native framing is hard-coded; downloaded executable chat templates are not run.
All new artifacts stay under repository `dist`; bases are reused without copying.

## Latest Evidence V5 safety replay — not a quality promotion

The completed V5 adversarial suite adds two semantic passes and two P1 failures:
it omits a selected source in the injection case and incorrectly establishes a
20-minute duration from unrelated clocks. The combined V5 result is four passes
and four failures across eight fictional development cases; it remains blocked.

The current LocalAgentRuntime nevertheless safely replays the saved V5 raw output:
it displays only verified literal record excerpts, keeps `Review required` visible,
withholds the false duration narrative, and quarantines chat-template-like document
instructions before the specialist receives context. This protection reduces harm
from an unqualified candidate; it does not make the model useful enough to admit,
package, or label as release-ready.
