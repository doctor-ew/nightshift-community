Read-only independent review of only the remaining token-semantics claim. No shell/network/hash invocation is needed; Read tool suffices. No role/factory dispatch. Previous review verified field names but the type definitions alone did not prove containment arithmetic. Controller now fetched primary source codex-rs/codex-api/src/sse/responses.rs and protocol/src/protocol.rs into local snapshots and recomputed each Git blob SHA successfully. Treat hashes as controller transport provenance, not an additional model gate requirement.
Read docs/35/codex-response-usage.txt lines 127-166 and 902-941; the upstream regression explicitly uses input_tokens=100, cached=40, cache_write=60, output=10, reasoning=5, total=110 and asserts preservation into TokenUsage. Read docs/35/codex-token-semantics.txt lines 2415-2428 for cached/non_cached_input behavior. JSON API envelopes beside each snapshot retain original content, SHA and source URL.
Claim: Codex cache-read and cache-write are input-token details (not additional totals), reasoning is an output-token detail; compute overall total=input_tokens+output_tokens, fresh=input-read-write with validation. The upstream fixture discriminates naive cache/reasoning addition. Verify or conflict this claim with specific snapshot line evidence. Do not reopen verified field-name and repository claims. Do not mark a source conflict merely because your process cannot recompute a transport hash; identify an actual content/semantics issue if present.
Primary-source excerpt follows for convenience; compare local snapshot with Read if necessary:
127: #[derive(Debug, Deserialize)]
128: struct ResponseCompletedUsage {
129:     input_tokens: i64,
130:     input_tokens_details: Option<ResponseCompletedInputTokensDetails>,
131:     output_tokens: i64,
132:     output_tokens_details: Option<ResponseCompletedOutputTokensDetails>,
133:     total_tokens: i64,
134:     #[serde(default)]
135:     codex_rollout_budget_units: Option<serde_json::Number>,
136: }
137: 
138: impl From<ResponseCompletedUsage> for TokenUsage {
139:     fn from(val: ResponseCompletedUsage) -> Self {
140:         let input_tokens_details = val.input_tokens_details.unwrap_or_default();
141:         TokenUsage {
142:             input_tokens: val.input_tokens,
143:             cached_input_tokens: input_tokens_details.cached_tokens,
144:             cache_write_input_tokens: input_tokens_details.cache_write_tokens,
145:             output_tokens: val.output_tokens,
146:             reasoning_output_tokens: val
147:                 .output_tokens_details
148:                 .map(|d| d.reasoning_tokens)
149:                 .unwrap_or(0),
150:             total_tokens: val.total_tokens,
151:             codex_rollout_budget_units: val.codex_rollout_budget_units,
152:         }
153:     }
154: }
155: 
156: #[derive(Debug, Default, Deserialize)]
157: struct ResponseCompletedInputTokensDetails {
158:     cached_tokens: i64,
159:     #[serde(default)]
160:     cache_write_tokens: i64,
161: }
162: 
163: #[derive(Debug, Deserialize)]
164: struct ResponseCompletedOutputTokensDetails {
165:     reasoning_tokens: i64,
166: }
902:             }
903:             other => panic!("unexpected third event: {other:?}"),
904:         }
905:     }
906: 
907:     #[test]
908:     fn parses_cache_write_token_usage() {
909:         let usage: ResponseCompletedUsage = serde_json::from_value(json!({
910:             "input_tokens": 100,
911:             "input_tokens_details": {
912:                 "cached_tokens": 40,
913:                 "cache_write_tokens": 60
914:             },
915:             "output_tokens": 10,
916:             "output_tokens_details": { "reasoning_tokens": 5 },
917:             "total_tokens": 110,
918:             "codex_rollout_budget_units": 2.5
919:         }))
920:         .expect("valid response usage");
921: 
922:         assert_eq!(
923:             TokenUsage::from(usage),
924:             TokenUsage {
925:                 input_tokens: 100,
926:                 cached_input_tokens: 40,
927:                 cache_write_input_tokens: 60,
928:                 output_tokens: 10,
929:                 reasoning_output_tokens: 5,
930:                 total_tokens: 110,
931:                 codex_rollout_budget_units: serde_json::Number::from_f64(2.5),
932:             }
933:         );
934:     }
935: 
936:     #[tokio::test]
937:     async fn parses_reasoning_summary_done() {
938:         let events = run_sse(vec![
939:             json!({
940:                 "type": "response.reasoning_summary_text.done",
941:                 "item_id": "reasoning-1",
942:                 "summary_index": 0,