import Lean
import Lake

import Lean4dojo.Share
import Lean4dojo.Path
import Lean4dojo.Pp

open Lean Elab System

namespace Traversal

/--
Extract tactic information from `TacticInfo` in `InfoTree`.
-/
private def visitTacticInfo (ctx : ContextInfo) (ti : TacticInfo) (parent : InfoTree) : TraceM Unit := do
  match ti.stx.getKind with
  | ``Lean.Parser.Term.byTactic =>
    match ti.stx with
    | .node _ _ #[.atom _ "by", .node _ ``Lean.Parser.Tactic.tacticSeq _] => pure ()
    | _ => assert! false

  | ``Lean.Parser.Tactic.tacticSeq =>
    match ti.stx with
    | .node _ _ #[.node _ ``Lean.Parser.Tactic.tacticSeq1Indented _] => pure ()
    | .node _ _ #[.node _ ``Lean.Parser.Tactic.tacticSeqBracketed _] => pure ()
    | _ => assert! false

  | _ => pure ()

  match parent with
  | .node (Info.ofTacticInfo i) _ =>
    match i.stx.getKind with
    | ``Lean.Parser.Tactic.tacticSeq1Indented | ``Lean.Parser.Tactic.tacticSeqBracketed | ``Lean.Parser.Tactic.rewriteSeq =>
      let ctxBefore := { ctx with mctx := ti.mctxBefore }
      let ctxAfter := { ctx with mctx := ti.mctxAfter }
      let stateBefore ← Pp.ppGoals ctxBefore ti.goalsBefore
      let stateAfter ← Pp.ppGoals ctxAfter ti.goalsAfter
      if stateBefore == "no goals" || stateBefore == stateAfter then
        pure ()
      else
        let some posBefore := ti.stx.getPos? true | pure ()
        let some posAfter := ti.stx.getTailPos? true | pure ()
        match ti.stx with
        | .node _ _ _ =>
          modify fun trace => {
            trace with tactics := trace.tactics.push {
              stateBefore := stateBefore,
              stateAfter := stateAfter,
              pos := posBefore,
              endPos := posAfter,
             }
          }
        | _ => pure ()
    | _ => pure ()
  | _ => pure ()


/--
Extract premise information from `TermInfo` in `InfoTree`.
-/
private def visitTermInfo (ti : TermInfo) (env : Environment) : TraceM Unit := do
  let some fullName := ti.expr.constName? | return ()
  let fileMap ← getFileMap

  let posBefore := match ti.toElabInfo.stx.getPos? with
    | some posInfo => fileMap.toPosition posInfo
    | none => none

  let posAfter := match ti.toElabInfo.stx.getTailPos? with
    | some posInfo => fileMap.toPosition posInfo
    | none => none

  let decRanges ← withEnv env $ findDeclarationRanges? fullName
  let defPos := decRanges >>= fun (decR : DeclarationRanges) => decR.selectionRange.pos
  let defEndPos := decRanges >>= fun (decR : DeclarationRanges) => decR.selectionRange.endPos

  let modName :=
  if let some modIdx := env.const2ModIdx.get? fullName then
    env.header.moduleNames[modIdx.toNat]!
  else
    env.header.mainModule

  let mut defPath := toString $ ← Path.findLean modName
  while defPath.startsWith "./" do
    defPath := defPath.drop 2
  if defPath.startsWith "/lake/" then
    defPath := ".lake/" ++ (defPath.drop 6)

  if defPos != posBefore ∧ defEndPos != posAfter then  -- Don't include defintions as premises.
    modify fun trace => {
        trace with premises := trace.premises.push {
          fullName := toString fullName,
          defPos := defPos,
          defEndPos := defEndPos,
          defPath := defPath,
          modName := toString modName,
          pos := posBefore,
          endPos := posAfter,
        }
    }


private def visitInfo (ctx : ContextInfo) (i : Info) (parent : InfoTree) (env : Environment) : TraceM Unit := do
  match i with
  | .ofTacticInfo ti => visitTacticInfo ctx ti parent
  | .ofTermInfo ti => visitTermInfo ti env
  | _ => pure ()


private partial def traverseTree (ctx: ContextInfo) (tree : InfoTree)
(parent : InfoTree) (env : Environment) : TraceM Unit := do
  match tree with
  | .context ctx' t =>
    match ctx'.mergeIntoOuter? ctx with
    | some ctx' => traverseTree ctx' t tree env
    | none => panic! "fail to synthesis contextInfo when traversing infoTree"
  | .node i children =>
    visitInfo ctx i parent env
    for x in children do
      traverseTree ctx x tree env
  | _ => pure ()


private def traverseTopLevelTree (tree : InfoTree) (env : Environment) : TraceM Unit := do
  match tree with
  | .context ctx t =>
    match ctx.mergeIntoOuter? none with
    | some ctx => traverseTree ctx t tree env
    | none => panic! "fail to synthesis contextInfo for top-level infoTree"
  | _ => pure ()


/--
Process an array of `InfoTree` (one for each top-level command in the file).
-/
def traverseForest (trees : Array InfoTree) (env : Environment) : TraceM Trace := do
  for t in trees do
    traverseTopLevelTree t env
  get


end Traversal
