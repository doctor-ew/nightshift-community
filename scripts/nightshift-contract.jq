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
  and (if $role == "nightshift-engineer" or $role == "nightshift-architect" then
    (.results | keys_are(["files_changed"]) and (.files_changed | strings))
  elif $role == "nightshift-code-fact-extractor" then
    (.results | keys_are(["claims"]) and (.claims | type == "array" and all(.[];
      keys_are(["claim","status","file","line","inspected_files"])
      and (.claim | type == "string") and (.file | type == "string")
      and (.status | . == "VERIFIED" or . == "NOT_FOUND" or . == "CONFLICT")
      and (.line | natural) and (.inspected_files | strings))))
  elif $role == "nightshift-run-all-tests" then
    (.results | keys_are(["passed","failed"]) and (.passed | natural) and (.failed | natural))
    and (if .status == "SUCCESS" then .results.failed == 0 else true end)
  elif $role == "nightshift-spec-writer" then
    (.results | keys_are(["spec_path"]) and (.spec_path | type == "string"))
    and (if .status == "SUCCESS" then (.results.spec_path | length > 0) else true end)
  else false end);
try valid_contract($role) catch false
