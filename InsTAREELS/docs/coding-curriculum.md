# Coding experience curriculum

Updated 2026-09-27. The 100-project run uses real local inference and executable JSON CLI checks. This is persistent experience learning, not model-weight fine-tuning. The same verified lesson store is consulted by ordinary Jarvis coding generation.

## How it learns

Each standalone project has a contract, three independent reference cases, a generated program and a usage README. Two examples are visible to the model; the third is initially withheld. A failed attempt supplies actual validation/execution feedback to the next inference, in a fresh attempt directory. Repairs see failed-case results, so repaired passes are training results, not unseen generalization evidence. No generated code or self-reported success is promoted into application source.

Verified categories (syntax, JSON serialization, runtime, timeout, policy, logic, generation/provider failures, missing imports, input shape, output shape and silent output) are saved as metadata in `.jarvis-runtime/coding-lessons.jsonl`. Recall supplies fixed, bounded lessons derived from those categories; arbitrary stored text cannot become instructions. Runtime-message matching selects coarse advice, not a proven root cause; output-shape checks compare actual parsed JSON types with reference types. Successes and failures are recorded, and first-attempt versus repaired success are reported separately. Mistakes can still recur; improvement is measured rather than guaranteed.

After a verified missing-import observation, normal Jarvis Python coding also applies a small static check before returning a draft: selected `json`/`sys` uses need an explicit visible binding. A rejected draft uses the existing bounded inference-repair loop before user project writes. Parameters and wildcard imports are treated conservatively. This is not full scope/type analysis and does not catch every missing import; it does not impose the curriculum's JSON-CLI contract on unrelated coding tasks.

Future processes also recall up to two developer-authored curriculum example sets per category when a goal names a previously failed algorithm. Related categories take priority over global frequency. These examples contain no generated instructions or private code. They are previously checked teaching data, so later repeated curricula cannot call recalled cases unseen tests. This enhancement was added after the live runner started; the first hundred-project run retains its earlier category-only recall.

The current input-shape advice now explicitly covers scalars and strings as well as collections, following the observed prime-list rejection of a valid integer. The running curriculum retains its earlier text. [Exact protocol details](../artifacts/coding-curriculum-20260927T101300Z/protocol-details.json) preserve the lesson texts used for all three stages.

Packaged experience support reads `jarvis/assets/coding-lessons-seed.jsonl` alongside the recent local runtime store, deduplicates identical records and ignores malformed or unknown categories. The packaged seed contains 151 validated metadata records from the hundred projects, ten larger checks and invoice transfer; it carries only validated metadata, not generated code, user recordings, credentials or instructions. Future records remain local. Lessons are explicitly scoped to relevant current goals; unrelated projects retain their own language and interfaces.

Generated programs receive one JSON input, emit one JSON output and use permitted standard-library imports. Static source checks reject unsupported imports, named dynamic execution and selected filesystem/introspection APIs, including common aliases. This is not an OS sandbox or a proof of containment. Each CLI check has a five-second deadline and bounded output reading, without OS memory limits. Training uses CPU; it installs no models or dependencies.

Current output readers read at most 8 KB stdout for reference/transfer checks, 32 KB for larger stress checks, and the final 1 KB stderr. The already-running first curriculum used a legacy full-file read before enforcing its 8 KB stdout limit; its raw output files are preserved for audit. Log files on disk and child-process memory have no OS resource quota.

## Run and resume

```powershell
.\.venv\Scripts\python.exe -u train_coding.py --limit 100 --attempts 2
.\.venv\Scripts\python.exe -u train_coding.py --resume artifacts/coding-curriculum-20260927T101300Z --limit 100 --attempts 2
.\.venv\Scripts\python.exe -u verify_coding_stress.py --run artifacts/coding-curriculum-20260927T101300Z
.\.venv\Scripts\python.exe -u verify_coding_transfer.py
```

Completed projects are skipped on resume. An interrupted attempt gets a new directory; old generated writes are not replayed. Results are checkpointed after every project. Only a test-owned Ollama server is stopped afterward; shared servers are reused. Raw server logs are ignored by Git.

The follow-up verifier requires a completed hundred-project run and tests ten retained final programs with larger, previously unseen inputs. These include 400-character edit-distance strings, a 500-node graph, a 100×100 grid, 5,000 LIS values and 10,000 trapped-water positions. Expected results follow independently calculable structured inputs. It performs no new inference, uses fresh source copies, preserves output and checks source hashes. Rejected/missing programs are marked not executed. Verified stress failures enter the same lesson store. All ten follow-up checks executed and passed on 2026-09-27. [Stress evidence](../artifacts/coding-curriculum-20260927T101300Z/stress-20260927T132426Z/results.json). These passes do not clear original small-case failures, including LIS and weighted shortest path.

The transfer verifier generates a new invoice calculator through the ordinary `generate_checked` path, records the lesson categories actually sent to inference, and executes ten CLI cases. Two examples are shown and eight are withheld, including duplicate items, fractional prices, half-cent discount/tax rounding, zero quantities and a large order. Its reference arithmetic uses Decimal HALF_UP with independently checked expected examples. Internal syntax/import repair can run; no CLI execution feedback is supplied before the final ten checks. The live transfer passed 10/10 cases in one inference, with no syntax/import or execution-feedback repair. [Transfer evidence](../artifacts/coding-transfer-20260927T132452Z/results.json). Money fields use an absolute 1e-8 comparison tolerance, with numeric type and exact key checks.

## Live run

The hundred-project run completed on 2026-09-27: **69/100 passed**, comprising **61 first recorded attempts** and **8 repaired projects**; **31 failed** within two attempts. There were **139 completed generation attempts** and **405 actual CLI invocations** across them. Two attempts were rejected by the source guard and two failed at model inference deadlines without CLI execution. The final retained attempts passed 227 individual reference cases; this partial-case total does not turn failed projects into passes.

[Complete results](../artifacts/coding-curriculum-20260927T101300Z/results.json) and [reference cases](../artifacts/coding-curriculum-20260927T101300Z/curriculum.json) preserve the evidence. Primary results use the original recorded categories; packaged memory distinguishes the two observed HTTP inference timeouts as generation failures. [Metadata before packaging](../artifacts/coding-curriculum-20260927T101300Z/coding-lessons-before-package.jsonl) is retained. All recorded raw stdout files from the primary attempts were at most 72 bytes, despite the legacy reader's broader worst-case limitation.

| Band | Projects | First recorded pass | Repaired pass | Failed |
|---|---:|---:|---:|---:|
| 1 | 25 | 13 | 2 | 10 |
| 2 | 25 | 18 | 3 | 4 |
| 3 | 25 | 14 | 1 | 10 |
| 4 | 25 | 16 | 2 | 7 |

First-attempt metrics refer to the completed attempts retained in `results.json`; interrupted directories remain available and are not credited as completed attempts. Difficulty and prompts differ across stages, so these counts do not prove causal improvement or error elimination. This is 100 standalone Python CLI projects, not 100 full-stack applications or model-weight training.

Those observed errors informed more specific canonical import and JSON-input lessons. After 11 completed projects, the owned training helper was stopped and resumed from its checkpoint with those lessons and failing-input values in repair feedback. After 21 completed projects, it resumed with specific failure-pattern classification and stronger alias checks. Fourteen earlier failure records were reclassified from actual case evidence; the [original metadata](../artifacts/coding-curriculum-20260927T101300Z/coding-lessons-phase2.jsonl) is preserved. Completed results and interrupted attempt files were preserved; shared Ollama was untouched. `protocol_phases` records these changes. Later results therefore cannot establish a controlled causal improvement. Resume refuses to overwrite changed reference cases.

## Framework verification

On 2026-09-27 all **386 regression tests passed** with the packaged experience present, and `python -m jarvis.launcher --check` reported **ready**, with no missing requirements. The new tests cover oracle answers, actual fixture CLI execution, invalid JSON, output budgets, specific failure categories, learned import repair, related-case retrieval, portable-seed fallback and deduplication. These regression/readiness checks are separate from the live model curriculum, stress and transfer results. No new microphone, GUI, account or external-provider live trial was performed here.

## Projects

The sequence progresses broadly from basic numeric/text utilities through collections, parsing, dynamic programming, graphs and structured-data tools. Bands are curriculum groupings, not calibrated difficulty scores; advanced bands also contain applied-library exercises.

| ID | Project | Band | Contract | Outcome |
|---|---|---|---|---|
| 001-sum | sum | 1 | Sum a JSON list of numbers. Empty list returns 0. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/001-sum/attempt-1/verification.json) |
| 002-pair-add | pair-add | 1 | Add the two numbers in the input pair. | [Repaired pass](../artifacts/coding-curriculum-20260927T101300Z/002-pair-add/attempt-2/verification.json) |
| 003-product | product | 1 | Multiply list values; empty product is 1. | [Repaired pass](../artifacts/coding-curriculum-20260927T101300Z/003-product/attempt-2/verification.json) |
| 004-celsius | celsius | 1 | Convert Celsius number to Fahrenheit. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/004-celsius/attempt-1/verification.json) |
| 005-rectangle | rectangle | 1 | Pair width,height to rectangle area. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/005-rectangle/attempt-1/verification.json) |
| 006-triangle | triangle | 1 | Pair base,height to triangle area. | [Failed](../artifacts/coding-curriculum-20260927T101300Z/006-triangle/attempt-2/verification.json) |
| 007-circle | circle | 1 | Radius to area using math.pi. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/007-circle/attempt-1/verification.json) |
| 008-discount | discount | 1 | Pair price,percentage to discounted price. | [Failed](../artifacts/coding-curriculum-20260927T101300Z/008-discount/attempt-2/verification.json) |
| 009-tip | tip | 1 | Pair bill,tip percentage to total including tip. | [Failed](../artifacts/coding-curriculum-20260927T101300Z/009-tip/attempt-2/verification.json) |
| 010-bmi | bmi | 1 | Pair kilograms,meters to BMI. | [Failed](../artifacts/coding-curriculum-20260927T101300Z/010-bmi/attempt-2/verification.json) |
| 011-simple-interest | simple-interest | 1 | Triple principal,annual percent,years to interest alone. | [Failed](../artifacts/coding-curriculum-20260927T101300Z/011-simple-interest/attempt-2/verification.json) |
| 012-compound-interest | compound-interest | 1 | Triple principal,annual percent,integer years to final balance. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/012-compound-interest/attempt-1-102649478648/verification.json) |
| 013-seconds | seconds | 1 | Nonnegative seconds to [hours,minutes,seconds], hours unbounded. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/013-seconds/attempt-1/verification.json) |
| 014-evens | evens | 1 | Preserve order of even integers only. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/014-evens/attempt-1/verification.json) |
| 015-positive-count | positive-count | 1 | Count values strictly greater than zero. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/015-positive-count/attempt-1/verification.json) |
| 016-numeric-span | numeric-span | 1 | Nonempty list to maximum minus minimum. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/016-numeric-span/attempt-1/verification.json) |
| 017-mean | mean | 1 | Mean of nonempty numeric list. | [Failed](../artifacts/coding-curriculum-20260927T101300Z/017-mean/attempt-2/verification.json) |
| 018-median | median | 1 | Median of nonempty numeric list. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/018-median/attempt-1/verification.json) |
| 019-reverse-text | reverse-text | 1 | Reverse the input string. | [Failed](../artifacts/coding-curriculum-20260927T101300Z/019-reverse-text/attempt-2/verification.json) |
| 020-word-count | word-count | 1 | Count whitespace-separated words. | [Failed](../artifacts/coding-curriculum-20260927T101300Z/020-word-count/attempt-2/verification.json) |
| 021-vowel-count | vowel-count | 1 | Count ASCII vowels case-insensitively. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/021-vowel-count/attempt-1/verification.json) |
| 022-slug | slug | 1 | Lowercase; replace each run of non ASCII alphanumeric with hyphen; strip edge hyphens. | [Failed](../artifacts/coding-curriculum-20260927T101300Z/022-slug/attempt-2-103858478524/verification.json) |
| 023-palindrome | palindrome | 1 | Ignore nonalphanumeric characters and case to test palindrome. | [Failed](../artifacts/coding-curriculum-20260927T101300Z/023-palindrome/attempt-2/verification.json) |
| 024-title-case | title-case | 1 | Apply Python str.title to input text. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/024-title-case/attempt-1/verification.json) |
| 025-ordered-unique | ordered-unique | 1 | Remove duplicate integers preserving first occurrence order. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/025-ordered-unique/attempt-1/verification.json) |
| 026-frequencies | frequencies | 2 | Count string items into JSON object. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/026-frequencies/attempt-1/verification.json) |
| 027-numeric-sort | numeric-sort | 2 | Sort integers ascending retaining duplicates. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/027-numeric-sort/attempt-1/verification.json) |
| 028-second-largest | second-largest | 2 | Second largest DISTINCT integer; fewer than two distinct values returns null. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/028-second-largest/attempt-1/verification.json) |
| 029-chunks | chunks | 2 | Pair list,positive chunk size to consecutive chunks, retaining final partial chunk. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/029-chunks/attempt-1/verification.json) |
| 030-rotate | rotate | 2 | Pair list,k to right rotation by k, wrapping; empty list remains empty. | [Repaired pass](../artifacts/coding-curriculum-20260927T101300Z/030-rotate/attempt-2/verification.json) |
| 031-flatten-list | flatten-list | 2 | Flatten exactly one level of nested lists. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/031-flatten-list/attempt-1/verification.json) |
| 032-transpose | transpose | 2 | Transpose rectangular matrix; empty matrix returns []. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/032-transpose/attempt-1/verification.json) |
| 033-matrix-product | matrix-product | 2 | Pair compatible nonempty matrices to matrix multiplication. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/033-matrix-product/attempt-1/verification.json) |
| 034-running-totals | running-totals | 2 | Cumulative sums of numeric list. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/034-running-totals/attempt-1/verification.json) |
| 035-moving-average | moving-average | 2 | Pair list,positive window size to means of complete sliding windows. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/035-moving-average/attempt-1/verification.json) |
| 036-merge-sorted | merge-sorted | 2 | Pair sorted integer lists to merged sorted list. | [Repaired pass](../artifacts/coding-curriculum-20260927T101300Z/036-merge-sorted/attempt-2/verification.json) |
| 037-missing-integers | missing-integers | 2 | Pair observed integers,n to missing numbers in inclusive range 1..n. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/037-missing-integers/attempt-1/verification.json) |
| 038-pair-sum | pair-sum | 2 | Pair list,target to sorted unique value pairs a<=b from distinct indices summing to target. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/038-pair-sum/attempt-1/verification.json) |
| 039-three-sum | three-sum | 2 | List to sorted unique ascending value triples from distinct indices summing to zero. | [Failed](../artifacts/coding-curriculum-20260927T101300Z/039-three-sum/attempt-2/verification.json) |
| 040-merge-intervals | merge-intervals | 2 | Merge overlapping OR touching closed [start,end] intervals; sort output. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/040-merge-intervals/attempt-1/verification.json) |
| 041-jaccard | jaccard | 2 | Pair lists to set Jaccard similarity; both empty returns 1. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/041-jaccard/attempt-1/verification.json) |
| 042-weighted-mean | weighted-mean | 2 | List of [value,positive weight] pairs to weighted average. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/042-weighted-mean/attempt-1/verification.json) |
| 043-minmax-normalize | minmax-normalize | 2 | Nonempty numeric list to (value-min)/(max-min); constant list returns all zeros. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/043-minmax-normalize/attempt-1/verification.json) |
| 044-run-length-encode | run-length-encode | 2 | String to [character,count] runs. | [Failed](../artifacts/coding-curriculum-20260927T101300Z/044-run-length-encode/attempt-2/verification.json) |
| 045-run-length-decode | run-length-decode | 2 | List of [character,count] runs to decoded string. | [Failed](../artifacts/coding-curriculum-20260927T101300Z/045-run-length-decode/attempt-2/verification.json) |
| 046-caesar | caesar | 2 | Pair string,integer shift; shift ASCII lowercase only and leave other characters unchanged. | [Repaired pass](../artifacts/coding-curriculum-20260927T101300Z/046-caesar/attempt-2/verification.json) |
| 047-anagram-groups | anagram-groups | 2 | Group case-sensitive strings by sorted characters; sort members and sort groups lexicographically. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/047-anagram-groups/attempt-1/verification.json) |
| 048-binary-to-int | binary-to-int | 2 | Binary digit string to integer. | [Failed](../artifacts/coding-curriculum-20260927T101300Z/048-binary-to-int/attempt-2/verification.json) |
| 049-balanced-brackets | balanced-brackets | 2 | Validate (), [], {} nesting; ignore other characters. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/049-balanced-brackets/attempt-1/verification.json) |
| 050-roman-numerals | roman-numerals | 2 | Convert integer 1..3999 to uppercase Roman numerals. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/050-roman-numerals/attempt-1/verification.json) |
| 051-rpn-calculator | rpn-calculator | 3 | Evaluate valid reverse Polish tokens +,-,*,/ with normal operand order. | [Failed](../artifacts/coding-curriculum-20260927T101300Z/051-rpn-calculator/attempt-2/verification.json) |
| 052-polynomial-value | polynomial-value | 3 | Pair ascending-power coefficients,value to polynomial evaluation. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/052-polynomial-value/attempt-1/verification.json) |
| 053-polynomial-derivative | polynomial-derivative | 3 | Ascending-power coefficients to derivative coefficients; constants return []. | [Failed](../artifacts/coding-curriculum-20260927T101300Z/053-polynomial-derivative/attempt-2/verification.json) |
| 054-gcd | gcd | 3 | Pair nonnegative integers to greatest common divisor. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/054-gcd/attempt-1/verification.json) |
| 055-lcm | lcm | 3 | Pair nonnegative integers to least common multiple. | [Repaired pass](../artifacts/coding-curriculum-20260927T101300Z/055-lcm/attempt-2/verification.json) |
| 056-prime-list | prime-list | 3 | Integer n to all primes <=n ascending. | [Failed](../artifacts/coding-curriculum-20260927T101300Z/056-prime-list/attempt-2/verification.json) |
| 057-prime-factors | prime-factors | 3 | Integer >=1 to ascending prime factors with multiplicity. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/057-prime-factors/attempt-1/verification.json) |
| 058-fibonacci | fibonacci | 3 | Nth Fibonacci F0=0,F1=1; n>=0. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/058-fibonacci/attempt-1/verification.json) |
| 059-factorial | factorial | 3 | Integer n>=0 to n factorial. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/059-factorial/attempt-1/verification.json) |
| 060-divisors | divisors | 3 | Positive integer to ascending positive divisors. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/060-divisors/attempt-1/verification.json) |
| 061-edit-distance | edit-distance | 3 | Pair strings to Levenshtein distance with unit insertion/deletion/substitution costs. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/061-edit-distance/attempt-1/verification.json) |
| 062-lcs-length | lcs-length | 3 | Pair strings to longest common subsequence length. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/062-lcs-length/attempt-1/verification.json) |
| 063-coin-change | coin-change | 3 | Pair positive denominations,target>=0 to minimum coins with unlimited supply; impossible -1. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/063-coin-change/attempt-1/verification.json) |
| 064-knapsack | knapsack | 3 | Pair [weight,value] items,capacity to maximum value in 0/1 knapsack. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/064-knapsack/attempt-1/verification.json) |
| 065-lis-length | lis-length | 3 | List integers to strictly increasing subsequence length. | [Failed](../artifacts/coding-curriculum-20260927T101300Z/065-lis-length/attempt-2/verification.json) |
| 066-grid-path-count | grid-path-count | 3 | Pair positive rows,columns to count right/down paths in unobstructed grid. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/066-grid-path-count/attempt-1/verification.json) |
| 067-max-subarray | max-subarray | 3 | Nonempty list to maximum NONEMPTY contiguous subarray sum. | [Failed](../artifacts/coding-curriculum-20260927T101300Z/067-max-subarray/attempt-2/verification.json) |
| 068-subsets | subsets | 3 | Distinct integers to all subsets, each sorted; sort output lexicographically. | [Failed](../artifacts/coding-curriculum-20260927T101300Z/068-subsets/attempt-2/verification.json) |
| 069-unique-permutations | unique-permutations | 3 | Integer list to sorted unique permutations as lists. | [Failed](../artifacts/coding-curriculum-20260927T101300Z/069-unique-permutations/attempt-2/verification.json) |
| 070-combinations | combinations | 3 | Pair distinct integers,k to sorted unique sorted k-element combinations. | [Failed](../artifacts/coding-curriculum-20260927T101300Z/070-combinations/attempt-2/verification.json) |
| 071-binary-insertion | binary-insertion | 3 | Pair sorted list,target to leftmost insertion index. | [Failed](../artifacts/coding-curriculum-20260927T101300Z/071-binary-insertion/attempt-2/verification.json) |
| 072-hamming-distance | hamming-distance | 3 | Equal-length strings to differing character count. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/072-hamming-distance/attempt-1/verification.json) |
| 073-reachability | reachability | 3 | Pair directed adjacency object,start to sorted reachable nodes including start. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/073-reachability/attempt-1/verification.json) |
| 074-shortest-hop-distance | shortest-hop-distance | 3 | Triple directed adjacency,start,target to shortest edge count, -1 if unreachable. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/074-shortest-hop-distance/attempt-1/verification.json) |
| 075-weighted-shortest-path | weighted-shortest-path | 3 | Pair directed adjacency with [neighbor,nonnegative weight] entries,start to distances for reachable nodes only. | [Failed](../artifacts/coding-curriculum-20260927T101300Z/075-weighted-shortest-path/attempt-2/verification.json) |
| 076-topological-sort | topological-sort | 4 | Directed adjacency object to lexicographically smallest topological order, [] if cyclic. | [Repaired pass](../artifacts/coding-curriculum-20260927T101300Z/076-topological-sort/attempt-2/verification.json) |
| 077-connected-components | connected-components | 4 | UNDIRECTED adjacency object to sorted components, each sorted. | [Failed](../artifacts/coding-curriculum-20260927T101300Z/077-connected-components/attempt-2/verification.json) |
| 078-lru-simulation | lru-simulation | 4 | Pair positive capacity,sequence of string keys to {hits,keys}; keys ordered oldest to newest. | [Failed](../artifacts/coding-curriculum-20260927T101300Z/078-lru-simulation/attempt-2/verification.json) |
| 079-minimum-grid-cost | minimum-grid-cost | 4 | Nonempty rectangular numeric grid to minimum top-left/bottom-right path sum, right/down only, include both endpoints. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/079-minimum-grid-cost/attempt-1/verification.json) |
| 080-csv-records | csv-records | 4 | CSV text with header to list of string-valued record objects using csv.DictReader. | [Failed](../artifacts/coding-curriculum-20260927T101300Z/080-csv-records/attempt-2/verification.json) |
| 081-flatten-object | flatten-object | 4 | Nested JSON objects to dotted-key object; retain lists as leaves; empty objects contribute nothing. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/081-flatten-object/attempt-1/verification.json) |
| 082-deep-merge | deep-merge | 4 | Pair JSON objects; recursively merge objects, otherwise right value replaces left including lists. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/082-deep-merge/attempt-1/verification.json) |
| 083-business-days | business-days | 4 | Pair ISO dates start,end to weekdays in half-open [start,end); start<=end. No holiday rules. | [Failed](../artifacts/coding-curriculum-20260927T101300Z/083-business-days/attempt-2/verification.json) |
| 084-date-difference | date-difference | 4 | Pair ISO dates to signed end-start days. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/084-date-difference/attempt-1/verification.json) |
| 085-base64-encode | base64-encode | 4 | UTF-8 string to standard Base64 ASCII text. | [Failed](../artifacts/coding-curriculum-20260927T101300Z/085-base64-encode/attempt-2/verification.json) |
| 086-base64-decode | base64-decode | 4 | Valid Base64 of UTF-8 text to decoded string. | [Repaired pass](../artifacts/coding-curriculum-20260927T101300Z/086-base64-decode/attempt-2/verification.json) |
| 087-sha256-text | sha256-text | 4 | UTF-8 string to lowercase SHA256 hex digest. | [Failed](../artifacts/coding-curriculum-20260927T101300Z/087-sha256-text/attempt-2/verification.json) |
| 088-inverted-index | inverted-index | 4 | List document strings to word->ascending document indices; lowercase whitespace tokens, deduplicate within document. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/088-inverted-index/attempt-1/verification.json) |
| 089-word-ranking | word-ranking | 4 | List strings to [word,count] pairs sorted descending count, then alphabetical; lowercase whitespace tokens. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/089-word-ranking/attempt-1/verification.json) |
| 090-interval-conflicts | interval-conflicts | 4 | List closed intervals to pairs of original indices i<j whose intervals overlap or touch, sorted. | [Failed](../artifacts/coding-curriculum-20260927T101300Z/090-interval-conflicts/attempt-2/verification.json) |
| 091-longest-common-prefix | longest-common-prefix | 4 | List strings to longest common prefix; empty list returns empty string. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/091-longest-common-prefix/attempt-1/verification.json) |
| 092-multiset-intersection | multiset-intersection | 4 | Pair integer lists to sorted intersection retaining minimum multiplicities. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/092-multiset-intersection/attempt-1/verification.json) |
| 093-window-maxima | window-maxima | 4 | Pair integer list,positive window size to maxima of complete sliding windows. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/093-window-maxima/attempt-1/verification.json) |
| 094-histogram-area | histogram-area | 4 | Nonnegative heights to largest rectangle area under histogram, unit widths. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/094-histogram-area/attempt-1/verification.json) |
| 095-trapped-water | trapped-water | 4 | Nonnegative heights to total trapped water, unit widths. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/095-trapped-water/attempt-1/verification.json) |
| 096-minimum-jumps | minimum-jumps | 4 | Nonnegative jump capacities; minimum jumps from index0 to final index, -1 unreachable, empty/single returns0. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/096-minimum-jumps/attempt-1/verification.json) |
| 097-partition-equal-sum | partition-equal-sum | 4 | Nonnegative integer list to whether it can split into equal-sum subsets, empty true. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/097-partition-equal-sum/attempt-1/verification.json) |
| 098-longest-palindrome | longest-palindrome | 4 | String to longest palindromic SUBSTRING; ties choose earliest start, empty string stays empty. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/098-longest-palindrome/attempt-1/verification.json) |
| 099-balanced-parentheses-generation | balanced-parentheses-generation | 4 | n>=0 to all balanced n-pair parentheses strings, lexicographic order. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/099-balanced-parentheses-generation/attempt-1/verification.json) |
| 100-longest-unique-substring | longest-unique-substring | 4 | String to length of longest substring without duplicate characters. | [First pass](../artifacts/coding-curriculum-20260927T101300Z/100-longest-unique-substring/attempt-1/verification.json) |
