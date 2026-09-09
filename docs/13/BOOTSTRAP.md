# Issue 13 recovery bootstrap

The independently reviewed recovery design was sealed at 23f5c05 and independent failing tests at b0733ea before further engine implementation. The public fixture correction was separately reviewed and recorded at 613441a. Earlier premature implementation commits remain retained and are not retroactively described as RED-first development.

The actual no-tool prototype used Claude CLI 2.1.265, subscription authentication, safe mode, an empty tool list, no session persistence, an empty temporary working directory and a bounded process-group executor. It evaluated actual completion text through the fixed independent oracle. No role-wrapper SUCCESS value established a behavioral pass.

| Attempt | Case | Fixed evaluator outcome |
| --- | --- | --- |
| 089b5d2735a3449690c9fb677c60d4ee | public-missing-negative | FAIL: required digest omitted |
| 01ee3d92de66454eb000dd6a470aa1b6 | public-missing-negative | PASS after one prompt repair |
| 04893adbb2a54603b69afe68b30f1c15 | public-corrected | FAIL retained; independent diagnosis found incomplete test input |
| 17a3cd4649a64a7a8ae4d495a93d411a | public-corrected-v2 | PASS after independently reviewed mutation-denial coverage was added |
| 63b8aa7facf241e59fde0073da93e312 | heldout-a | PASS |
| 5ac2bb7236314bbd9a0159064f05ddb5 | heldout-b | PASS |

Development consumed seven of eight allowed CLI launches: three independent design reviews and four prototype invocations. Final consumed two of two launches. The original failures remain charged. A sandbox authentication failure and a worker runtime-version mismatch occurred before model launch and are retained as infrastructure observations. The worker then used the same verified binary as public executions; the required version was not relaxed.

The final prompt SHA256 is 797c18c86a2be735ed54cee71286d9e020dc556834b1a1ded52acdf065cb03df. The unchanged evaluator SHA256 is 27c21879ce7bc7b674841f8424e01ac80dafed8f45e208395e1b6b4a3823523e. The manual executor SHA256 is 2ea1e431c3a167de82405db172dc6cf897148e43b6d4fb2e9434234181df099a. The retained manual ledger SHA256 is a42d21d271d05c2fd4d368c26bee750d8ca7ed75164ddce844e8d7cedf8ea666.

Accounting units are CLI invocations, not claims about the provider's internal request count. The configured model was sonnet; the observed transport reported claude-sonnet-5 and an auxiliary claude-haiku-4-5-20251001 entry. Usage observations are retained with raw results. No API-key fallback was used.

Raw outputs, evaluator receipts and the manual ledger remain outside the checkout in the retained temporary bootstrap directory. Private fixture bodies were not supplied to the implementation worker. These manual results are bootstrap evidence only: they are not imported through a production API or represented as completed-engine receipts. A distinct real fixture must exercise the completed helper before delivery.
