/-
Copyright (c) 2024 BICMR@PKU. All rights reserved.
Released under the Apache 2.0 license as described in the file LICENSE.
-/
import Lean
import Analyzer.Types
import Analyzer.Process.Common

open Lean Meta Elab Term Command Frontend Parser
open Std (HashSet)

namespace Analyzer.Process.Symbol

/-- 引用資訊結構 -/
structure InfoReference where
  name  : Name
  srcName : String --source name
  range : String.Range
  isCallHead : Bool := false --whether source token is followed by (
  binderCount : Nat := 0 -- total binders of resolved constant type.
  explicitArgCount : Nat := 0 -- explicit binders count.
  namespacePrefixSafe : Bool := true -- final decision for auto-prefixer.
  namespacePrefixReason : Option String := none -- e.g. "implicit-only callable".
  deriving Inhabited, Repr


def sliceByRange (input : String) (r : String.Range) : String :=
  input.extract r.start r.stop

private def hasSubstr (s sub : String) : Bool :=
  (s.splitOn sub).length > 1

private def isInstanceBySyntax
    (input : String) (fileMap : FileMap)
    (declRange? : Option DeclarationRanges) : Bool :=
  match declRange? with
  | none => false
  | some dr =>

    let start := fileMap.ofPosition dr.range.pos
    let nameStart := fileMap.ofPosition dr.selectionRange.pos

    let headText := sliceByRange input { start := start, stop := nameStart }
    let t := headText.trimLeft

    t.startsWith "instance" ||
    t.startsWith "local instance" ||
    t.startsWith "scoped instance" ||
    hasSubstr t " instance "

partial def forallBody (e : Expr) : Expr :=
  match e with
  | .forallE _ _ b _ => forallBody b
  | _ => e

private def isInstanceByType (ci : ConstantInfo) : TermElabM Bool := do
  let b := forallBody ci.type
  match b.getAppFn.consumeMData with
| .const cls lvls =>
    return (← Meta.isClass? (.const cls lvls)).isSome
  | _ =>
      return false

partial def collectConsts (e : Expr) (acc : Std.HashSet Name := {}) : Std.HashSet Name :=
  match e with
  | .const n _        => acc.insert n
  | .app f a          => collectConsts a (collectConsts f acc)
  | .lam _ t b _      => collectConsts b (collectConsts t acc)
  | .forallE _ t b _  => collectConsts b (collectConsts t acc)
  | .letE _ t v b _   => collectConsts b (collectConsts v (collectConsts t acc))
  | .mdata _ b        => collectConsts b acc
  | .proj _ _ b       => collectConsts b acc
  | _                 => acc

def valueExprOf? : ConstantInfo → Option Expr
  | .defnInfo d   => some d.value
  | .thmInfo t    => some t.value
  | .opaqueInfo _ => none
  | _             => none

private def isEqnThmLike (n : Name) : Bool :=
  match n with
  | .str p s =>
      let thisPart := s.startsWith "eq_" && (s.drop 3).data.all Char.isDigit
      thisPart || isEqnThmLike p
  | .num p _ => isEqnThmLike p
  | .anonymous => false

private def defNameCandidate (n : Name) : Option Name :=
  match n with
  | .str p s => some (Name.str p (s ++ "_def"))
  | _ => none

private def expandWithDefEqName (env : Environment) (n : Name) : Array Name :=
  match defNameCandidate n with
  | some d =>
    if env.contains d then #[n, d] else #[n]
  | none => #[n]

partial def binderInfos (ty : Expr) : List BinderInfo :=
  match ty with
  | .forallE _ _ body bi => bi :: binderInfos body
  | _ => []

def binderCount (ty : Expr) : Nat :=
  (binderInfos ty).length

def explicitArgCount (ty : Expr) : Nat :=
  (binderInfos ty).foldl (init := 0) fun n bi =>
    if bi.isExplicit then n + 1 else n

private def mkEnvRef (env : Environment) (n : Name) : SymbolRef :=
  let (b, e, safe, reason) :=
    match env.find? n with
    | some ci =>
      let b := binderCount ci.type
      let e := explicitArgCount ci.type
      (b, e, true, none)   -- no call-head context here
    | none => (0, 0, true, none)
  {
    name := n
    srcName := toString n
    range := none
    isCallHead := false
    binderCount := b
    explicitArgCount := e
    namespacePrefixSafe := safe
    namespacePrefixReason := reason
  }

private def pushRefIfNew (arr : Array SymbolRef) (r : SymbolRef) : Array SymbolRef :=
  if arr.any (fun x => x.name == r.name && x.range == r.range) then arr else arr.push r

def firstBinderImplicit (ty : Expr) : Bool :=
  match binderInfos ty with
  | [] => false
  | bi :: _ => !bi.isExplicit

/-- safer generic rule for auto-prefixing -/
def computePrefixSafety (isCallHead : Bool) (ci : ConstantInfo) :
    Nat × Nat × Bool × Option String :=

  let b := binderCount ci.type
  let e := explicitArgCount ci.type
  let firstImpl := firstBinderImplicit ci.type

  let implicitOnlyUnsafe := isCallHead && b > 0 && e == 0
  let leadingImplicitUnsafe := isCallHead && firstImpl

  let unsafeFlag := implicitOnlyUnsafe || leadingImplicitUnsafe
  let reason :=
    if implicitOnlyUnsafe then some "implicit-only callable"
    else if leadingImplicitUnsafe then some "leading implicit binder"
    else none

  (b, e, !unsafeFlag, reason)

def isIdentChar (c : Char) : Bool :=
  c.isAlphanum || c == '_' || c == '\''

def isSimpleIdent (s : String) : Bool :=
  if s.isEmpty then
    false
  else
    s.data.all isIdentChar

/-- Resolve projection declaration name from `Expr.proj struct idx _`. -/
private def resolveProjName? (env : Environment) (structName : Name) (idx : Nat) : Option Name :=
  match getStructureInfo? env structName with
  | none => none
  | some sinfo =>
      if h : idx < sinfo.fieldNames.size then
        some (sinfo.fieldNames[idx])
      else
        none

/-- Resolve the semantic head name of a term expression.
    Supports const head and projection head. -/
private def resolveHeadName? (env : Environment) (e : Expr) : Option Name :=
  let h := e.consumeMData.getAppFn.consumeMData
  match h with
  | .const nm _    => some nm
  | .proj s i _    => resolveProjName? env s i
  | _              => none

partial def prevNonWsChar? (s : String) (p : String.Pos) : Option Char := Id.run do
  let mut i := p
  while i.byteIdx > 0 do
    let j := s.prev i
    let c := s.get j
    if !c.isWhitespace then
      return some c
    i := j
  return none

partial def nextNonWsChar? (s : String) (p : String.Pos) : Option Char := Id.run do
  let mut i := p
  while i.byteIdx < s.endPos.byteIdx do
    let c := s.get i
    if !c.isWhitespace then
      return some c
    i := s.next i
  return none

def nameEndsWithSrc (n : Name) (src : String) : Bool :=
  let full := toString n
  full == src || full.endsWith (s!"." ++ src)

def syntacticUnsafeReason (input : String) (ref : InfoReference) : Option String :=
  let src := ref.srcName
  if !isSimpleIdent src then
    some "non-identifier token (notation/operator/field-like)"
  else if (prevNonWsChar? input ref.range.start) == some '|' then
    some "case/alt tag position"
  else if (nextNonWsChar? input ref.range.stop) == some ':' then
    -- catches many `x := ...` label contexts (named arg / field update)
    some "label-like ':=' context"
  else if !nameEndsWithSrc ref.name src then
    some "resolved name not suffix-matching source token"
  else
    none

def enrichRefsWithSafety
    (env : Environment)
    (refs : Array InfoReference)
    (input : String := "") : Array InfoReference :=
  refs.map fun ref =>
    match syntacticUnsafeReason input ref with
    | some reason =>
      { ref with
        namespacePrefixSafe := false
        namespacePrefixReason := some reason
      }
    | none =>
      match env.find? ref.name with
      | none =>
        if ref.isCallHead then
          { ref with
            namespacePrefixSafe := false
            namespacePrefixReason := some "unresolved call-head"
          }
        else
          ref
      | some ci =>
        let (b, e, safe, reason) := computePrefixSafety ref.isCallHead ci
        { ref with
          binderCount := b
          explicitArgCount := e
          namespacePrefixSafe := safe
          namespacePrefixReason := reason
        }

/-- 輔助：格式化表達式 (解決 ppType 未定義問題) -/
def ppType (type : Expr) : MetaM (Option String) :=
  tryCatchRuntimeEx (do
    let format ← PrettyPrinter.ppExpr type |>.run'
    pure <| some format.pretty
  ) (fun _ => pure none)

/-- Is `nm` the function head of parent application expression? -/
def isHeadConstOfParentApp (parentExpr? : Option Expr) (nm : Name) : Bool :=
  match parentExpr?.map Expr.consumeMData with
  | some p =>
    if p.isApp then
      match p.getAppFn.consumeMData with
      | .const fn _ => fn == nm
      | _ => false
    else
      false
  | none => false

def isFullWord (input : String) (range : String.Range) : Bool :=
  let s := range.start
  let e := range.stop
  -- 檢查前一個字元：如果前面還有識別碼字元，說明這是一個被切掉的後半部
  let headSafe := s == 0 || !isIdentChar (input.get (input.prev s))
  -- 檢查後一個字元：如果後面還有識別碼字元，說明這是一個被切掉的前半部
  let tailSafe := e >= input.endPos || !isIdentChar (input.get e)
  headSafe && tailSafe

/-- 深度遍歷 InfoTree 並去重，只抓取最細顆粒度的引用 -/
partial def collectInfoRefs (env : Environment) (input : String) (tree : InfoTree) : Array InfoReference :=
  let rawRefs := go none tree
  filterGarbage rawRefs
where
  go (parentExpr? : Option Expr) (tree : InfoTree) : Array InfoReference :=
    match tree with

    | .context _ t => go parentExpr? t
    -- 補上 hole 的分支，防止 Missing cases 報錯
    | .hole _ => #[]
    | .node info children => Id.run do
      let currentExpr? : Option Expr :=
        match info with

        | .ofTermInfo ti => some ti.expr.consumeMData
        | _ => parentExpr?

      let mut refs := #[]
      for child in children do
        refs := refs ++ go currentExpr? child

      if let .ofTermInfo ti := info then
        if ti.stx.isIdent then
          if let some r := ti.stx.getRange? then
            let src := ti.stx.getId.eraseMacroScopes.toString
            let raw := input.extract r.start r.stop

            -- strict token/range sanity: reduce range noise
            if raw == src && isSimpleIdent src && isFullWord input r then
              if let some nm := resolveHeadName? env ti.expr then
                -- keep only suffix-matching refs (huge noise reduction)
                if nameEndsWithSrc nm src then
                  refs := refs.push {
                    name := nm
                    srcName := src
                    range := r
                    isCallHead := isHeadConstOfParentApp parentExpr? nm
                  }
      return refs

  /-- 保護機制 3：同起點競爭過濾（Double-check） -/
  filterGarbage (refs : Array InfoReference) : Array InfoReference :=
    let sorted := refs.qsort fun a b =>
      if a.range.start < b.range.start then true
      else if a.range.start == b.range.start then a.range.stop > b.range.stop
      else false
    sorted.foldl (init := #[]) fun acc x =>
      if acc.any (fun y =>
          y.range.start == x.range.start &&
          y.range.stop == x.range.stop &&
          y.name == x.name) then
        acc
      else
        acc.push x


/-- 核心：提取符號資訊（保留 ranged 引用；過濾 self 與 eqn-thm artifact） -/
def getSymbolInfo
    (name : Name)
    (info : ConstantInfo)
    (allRefs : Array InfoReference) : TermElabM SymbolInfo := do

  let env ← getEnv
  let fileMap ← getFileMap
  let input := fileMap.source
  let declRange? ← Lean.findDeclarationRanges? name

  let isInstSyntax := isInstanceBySyntax input fileMap declRange?

  let isInst ←
    match info with
    | .thmInfo _ => pure isInstSyntax
    | _ =>
        let isInstType ← isInstanceByType info
        pure (isInstSyntax || isInstType)

  let kind :=
    if isInst then
      .«instance»
    else
      match info with
      | .axiomInfo _ => .«axiom»
      | .defnInfo _ => .definition
      | .thmInfo _ => .«theorem»
      | .opaqueInfo _ => .«opaque»
      | .quotInfo _ => .«quotient»
      | .inductInfo _ => .«inductive»
      | .ctorInfo _ => .constructor
      | .recInfo _ => .recursor

  let type := info.toConstantVal.type
  let typeFull ← ppType type
  let typeReadable ← ppType type
  let typeFallback := type.dbgToString
  let isProp := (match info with | .thmInfo _ => true | _ => false)

  let mut typeReferences : Array SymbolRef := #[]
  let mut valueReferences : Array SymbolRef := #[]

  let recoverCanonicalName (rawName : Name) (src : String) : Name := Id.run do
    let currentModIdx? := env.getModuleIdxFor? name
    let rawS := toString rawName
    let sufRaw := s!"." ++ rawS
    let sufSrc := s!"." ++ src

    let sameMod (k : Name) : Bool :=
      match currentModIdx?, env.getModuleIdxFor? k with
      | some i, some j => i == j
      | _, _ => true

    let isPrivateLike (k : Name) : Bool :=
      (toString k).startsWith "_private."

    let mut bestPrivate : Option Name := none
    let mut bestOther : Option Name := none

    for (k, _) in env.constants.map₁ do
      let ks := toString k
      if sameMod k then
        let matchBySuffix := ks == rawS || ks.endsWith sufRaw || ks.endsWith sufSrc
        if matchBySuffix then
          if isPrivateLike k then
            match bestPrivate with
            | none =>
                bestPrivate := some k
            | some b =>
                let bs := toString b
                if ks.endsWith sufSrc && !bs.endsWith sufSrc then
                  bestPrivate := some k
          else
            if bestOther.isNone then
              bestOther := some k

    for (k, _) in env.constants.map₂ do
      let ks := toString k
      if sameMod k then
        let matchBySuffix := ks == rawS || ks.endsWith sufRaw || ks.endsWith sufSrc
        if matchBySuffix then
          if isPrivateLike k then
            match bestPrivate with
            | none =>
                bestPrivate := some k
            | some b =>
                let bs := toString b
                if ks.endsWith sufSrc && !bs.endsWith sufSrc then
                  bestPrivate := some k
          else
            if bestOther.isNone then
              bestOther := some k

    match bestPrivate with
    | some k => k
    | none =>
        if env.contains rawName then rawName
        else bestOther.getD rawName

  if let some dr := declRange? then
    let start := fileMap.ofPosition dr.range.pos
    let stop := fileMap.ofPosition dr.range.endPos
    let nameEnd := fileMap.ofPosition dr.selectionRange.endPos

    let tailText := sliceByRange input { start := nameEnd, stop := stop }

    let findPosInTail (sub : String) : Option String.Pos :=
      let parts := tailText.splitOn sub
      if parts.length > 1 then
        some ⟨(parts[0]!).utf8ByteSize⟩
      else
        none

    let valueStart : String.Pos :=
      if let some pos := findPosInTail ":=" then
        ⟨nameEnd.byteIdx + pos.byteIdx⟩
      else if let some pos := findPosInTail "where" then
        ⟨nameEnd.byteIdx + pos.byteIdx⟩
      else
        match info with
        | .inductInfo _ | .axiomInfo _ | .quotInfo _ => stop
        | _ => nameEnd

    let myRefs := allRefs.filter fun ref =>
      ref.range.start >= start && ref.range.stop <= stop

    for ref in myRefs do
      let fixedName := recoverCanonicalName ref.name ref.srcName

      if fixedName == name then
        continue
      if isEqnThmLike fixedName then
        continue

      let outRef : Analyzer.SymbolRef := {
        name := fixedName
        srcName := ref.srcName
        range := some ref.range
        isCallHead := ref.isCallHead
        binderCount := ref.binderCount
        explicitArgCount := ref.explicitArgCount
        namespacePrefixSafe := ref.namespacePrefixSafe
        namespacePrefixReason := ref.namespacePrefixReason
      }

      if ref.range.start < valueStart then
        typeReferences := pushRefIfNew typeReferences outRef
      else
        valueReferences := pushRefIfNew valueReferences outRef

  return {
    kind := kind
    name := name
    typeFull := typeFull
    typeReadable := typeReadable
    typeFallback := typeFallback
    typeReferences := typeReferences
    valueReferences := some valueReferences
    isProp := isProp
  }





/-- 執行指令循環以產生 InfoTree -/
def runFrontendLoop (ictx : Frontend.Context) (s : Frontend.State) : IO Frontend.State := do
  -- 使用 StateRefT 的 run 模式，這通常能避開類型不匹配
  let (_, s') ← (Frontend.processCommands).run ictx |>.run s
  pure s'

def getResult (path : System.FilePath) : IO (Array SymbolInfo) := do
  let sysroot ← findSysroot
  let ssp := (← getSrcSearchPath) ++ [sysroot / "src" / "lean"]
  let module := (← searchModuleNameOfFileName path ssp).get!

  let input ← IO.FS.readFile path
  let inputCtx := Parser.mkInputContext input path.toString
  let (header, parserState, messages) ← Parser.parseHeader inputCtx
  let (env, messages) ← processHeader header .empty messages inputCtx

  let ictx : Frontend.Context := { inputCtx := inputCtx }
  let s : Frontend.State := {
    commandState := {
      Command.mkState env messages .empty with
      infoState.enabled := true
    },
    parserState := parserState,
    cmdPos      := parserState.pos
  }

  let s' ← runFrontendLoop ictx s

  let finalEnv := s'.commandState.env
  let mut allRefs := #[]
  for tree in s'.commandState.infoState.trees do
    allRefs := allRefs ++ collectInfoRefs finalEnv input tree

  allRefs := enrichRefsWithSafety finalEnv allRefs input


  let index := finalEnv.allImportedModuleNames.idxOf? module

  let config : Core.Context := {
    fileMap := inputCtx.fileMap,
    fileName := path.toString
  }

  let f a name info := do
    -- keep only declarations defined in this file
    if finalEnv.getModuleIdxFor? name != index then
      return a
    let (si, _, _) ← getSymbolInfo name info allRefs |>.run' |>.toIO config { env := finalEnv }
    return a.push si

  let a ← finalEnv.constants.map₁.foldM f #[]
  finalEnv.constants.map₂.foldlM f a

end Analyzer.Process.Symbol
