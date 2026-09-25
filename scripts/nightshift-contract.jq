# Strict local contract validation. Invoke with jq -e --arg role ROLE -f FILE.
def keys_are($names): type == "object" and (keys == ($names | sort));
def strings: type == "array" and all(.[]; type == "string");
def natural: type == "number" and . >= 0 and floor == .;
def valid_contract($role):
  keys_are(["status","reason","attempts","artifacts","rules_fired","results"])
  and (.status | . == "SUCCESS" or . == "FAIL" or . == "SKIP")
  and (.reason | type == "string")
  and (if .status != "SUCCESS" then (.reason | length > 0) else true end)
  and (.attempts | natural and . >= 1)
  and (.artifacts | keys_are(["branch","diff","provider","model"]) and all(.[]; type == "string"))
  and (.rules_fired | strings)
  and (if $role == "nightshift-engineer" or $role == "nightshift-architect" or $role == "nightshift-repair-analyst" then
    (.results | keys_are(["files_changed"]) and (.files_changed | strings))
  elif $role == "nightshift-operation-worker" then
    (.results | keys_are(["binding","decision","findings","resolved","coverage"])
      and (.binding | type == "string")
      and (.decision | . == "approve" or . == "repair" or . == "abstain")
      and (.findings | strings) and (.resolved | strings) and (.coverage | strings))
  elif $role == "nightshift-code-fact-extractor" then
    (.results | keys_are(["claims"]) and (.claims | type == "array" and all(.[];
      keys_are(["claim","status","file","line","inspected_files"])
      and (.claim | type == "string") and (.file | type == "string")
      and (.status | . == "VERIFIED" or . == "NOT_FOUND" or . == "CONFLICT")
      and (.line | natural) and (.inspected_files | strings))))
  elif $role == "nightshift-behavior-reviewer" then
    (.results | keys_are(["decision","scenario_ids","findings","reviewed_input_sha256"])
      and (.decision | . == "approve" or . == "repair")
      and (.scenario_ids | strings and (length == (unique | length)))
      and (.reviewed_input_sha256 | type == "string")
      and (.findings | type == "array" and all(.[];
        keys_are(["scenario_id","code","reason"]) and all(.[]; type == "string"))))
    and (if .status == "SUCCESS" then
      (.results.reviewed_input_sha256 | test("^[0-9a-f]{64}$"))
      and (if .results.decision == "approve" then (.results.findings | length == 0) else (.results.findings | length > 0) end)
      else true end)
  elif $role == "nightshift-decision-reviewer" then
    (.results | type == "object" and
      (keys | sort) == (["decision","packet_sha256","reviewer_id","evidence"] | sort) and
      (.decision == "yes" or .decision == "no" or .decision == "abstain") and
      (.packet_sha256 | type == "string") and (.reviewer_id | type == "string") and
      (.evidence | type == "array" and all(.[]; type == "string")))
  elif $role == "nightshift-recovery-reviewer" then
    (.results | keys_are(["binding","stage","reviewer_id","decision","findings","dispositions","cases","ac_ids"])
      and (.binding | type == "string") and (.reviewer_id | type == "string")
      and (.stage | . == "adoption" or . == "review" or . == "drift" or . == "qa")
      and (.decision | . == "approve" or . == "reject") and (.findings | strings) and (.ac_ids | strings)
      and (.dispositions | type == "array" and all(.[]; keys_are(["id","resolution","reason"]) and all(.[]; type == "string")))
      and (.cases | type == "array" and all(.[]; keys_are(["id","status","reason","checks"])
        and (.id | type == "string") and (.status | type == "string") and (.reason | type == "string")
        and (.checks | type == "array" and all(.[]; keys_are(["id","sha256"]) and all(.[]; type == "string"))))))
  elif $role == "nightshift-run-all-tests" then
    (.results | keys_are(["passed","failed"]) and (.passed | natural) and (.failed | natural))
    and (if .status == "SUCCESS" then .results.failed == 0 else true end)
  elif $role == "nightshift-spec-writer" then
    (.results | keys_are(["spec_path"]) and (.spec_path | type == "string"))
    and (if .status == "SUCCESS" then (.results.spec_path | length > 0) else true end)
  else false end);
try valid_contract($role) catch false
