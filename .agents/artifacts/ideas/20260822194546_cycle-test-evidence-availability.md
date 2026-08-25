# Cycleのtest結果証拠を取得可能性で扱う

**Created:** 2026-08-22 19:45:46
**Status:** ✅ Converged
**Tags:** `cycle,evidence,test-summary,human-gate`

---

## Summary

Cycleはtest件数を推測せず、構造化されたreporterから明確に取得できた場合だけ保存する。
取得できない件数は理由付きの`unavailable`として扱い、合否に必要なcommand、exit code、
outcome、対象identityは常に証拠へ残す。Plan作成指示には、既に仕様化されたHuman gate宣言を
実際に出力する契約を追加する。

## Key Discussion Points

- 任意のtest commandにはpass、fail、skip件数を共通形式で返すprotocolがない。
- runner固有の出力を曖昧に解釈すると、誤った件数がdurable evidenceとして固定される。
- test件数は補助情報であり、対象identityとcommandの合否を置き換えない。
- `PL-024`〜`PL-026`はHuman gate宣言を要求するが、Plan作成instructionに出力形式がない。

## Decisions & Conclusions

- command、exit code、outcome、対象identityは常に必須証拠とする。
- pass、fail、skip件数は構造化reporterから一意に取得できる場合だけ保存する。
- 件数を取得できない場合は`unavailable`と理由を記録し、推測値やcommand数で代用しない。
- stdout、stderr、provider log全体はdurable evidenceへ保存しない。
- Plan作成instructionへHuman gate declaration v1の出力契約を追加する。

## Open Questions

- なし。

## Next Steps

- `docs/spec/cycle-skill-migration.md`の`CY-063`を更新する。
- 実装scopeにPlan作成instructionを追加したrevision 3を作成する。
- revision 3承認後、停止したTDD実装を再開する。

---

## Exit Contract

**Exit Status:** CONVERGED

### Agreements

| # | Decision | Rationale | Destination |
|---|----------|-----------|-------------|
| A1 | test件数は構造化取得できた場合だけ保存し、取得不能は理由付き`unavailable`とする | runner非依存の推測は証拠を偽るため | docs/spec |
| A2 | command、exit code、outcome、対象identityは常に必須とする | 件数取得の可否にかかわらず合否と対象を再確認できるため | docs/spec |
| A3 | raw outputをdurable evidenceへ保存せず、件数をcommand数で代用しない | secret混入と誤った証拠の固定を防ぐため | docs/spec |
| A4 | Plan作成instructionへHuman gate declaration v1を追加する | 正本仕様をPlan skillが実際に生成できるようにするため | plan |

### Undecided Items

| # | Item | Why undecided | Blocks plan? |
|---|------|---------------|--------------|
| — | なし | — | false |

### Acceptance Criteria

| # | Criterion | Verifiable? | Source |
|---|-----------|-------------|--------|
| C1 | 構造化件数を取得できるcommandではpass、fail、skipを欠落なく記録する | yes | A1 |
| C2 | 件数を取得できないcommandでは理由付き`unavailable`を記録する | yes | A1 |
| C3 | 件数取得不能でもcommand、exit code、outcome、対象identityを記録する | yes | A2 |
| C4 | raw output、推測件数、command数によるtest件数代用を拒否する | yes | A3 |
| C5 | Human gateが必要なPlan stepはversion 1の機械可読宣言を出力し、不要なら省略する | yes | A4 |

### Codebase Evidence

| File | Finding | Relevance |
|------|---------|-----------|
| `docs/spec/cycle-skill-migration.md` | `CY-063`はtest件数を要求するが、取得不能時の表現を定義していない | A1〜A3の根拠 |
| `docs/spec/plan-skill-migration.md` | `PL-024`〜`PL-026`はversion付きHuman gate宣言を要求する | A4の正本根拠 |
| `skills/ba0918-plan/references/creation.md` | Human gate declaration v1の具体的な出力指示がない | revision 3でのscope追加根拠 |
| `skills/ba0918-cycle/scripts/cycle_runtime.py` | oracleは任意commandを実行するため、exit codeだけからtest case件数を導出できない | A1の実装境界 |

### Routing

| Destination | Items | Action |
|-------------|-------|--------|
| Plan | A1〜A4、C1〜C5 | revision 3へ反映する |
| Spec | A1〜A3、C1〜C4 | Generated at `docs/spec/cycle-skill-migration.md` |
| Docs | A4、C5 | Plan作成instructionへ反映する |
| Clauses (side line) | C1〜C5 | 必要時に`spec-verify formalize`を実行する |
