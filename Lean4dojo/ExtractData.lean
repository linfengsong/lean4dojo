import Init
import Lean
import Lake

import Lean4dojo.Share
import Lean4dojo.Pp
import Lean4dojo.Path
import Lean4dojo.Traversal

open Lean Elab System
open Traversal

def getImports (header: TSyntax `Lean.Parser.Module.header) : IO String := do
  -- Similar to `lean --deps` in Lean 3.
  let mut s := ""

  for dep in headerToImports header do
    -- let oleanPath ← findOLean dep.module
    let leanPath ← Path.findLean dep.module
    s := s ++ "\n" ++ leanPath.toString
    /-
    if oleanPath.isRelative then
      let leanPath := Path.toSrcDir! oleanPath "lean"
      assert! ← leanPath.pathExists
      s := s ++ "\n" ++ leanPath.toString
    else if ¬(oleanPath.toString.endsWith "/lib/lean/Init.olean") then
      let mut p := (Path.packagesDir / "lean4").toString ++ FilePath.pathSeparator.toString
      let mut found := false
      for c in (oleanPath.withExtension "lean").components do
        if c == "lib" then
          found := true
          p := p ++ "src"
          continue
        if found then
          p := p ++ FilePath.pathSeparator.toString ++ c
      p := p.replace "/lean4/src/lean/Lake" "/lean4/src/lean/lake/Lake"
      assert! ← FilePath.mk p |>.pathExists
      s := s ++ "\n" ++ p
  -/

  return s.trim

/--
Trace a *.lean file.
-/
unsafe def processFile (path : FilePath) : IO Unit := do
  println! s!"processFile, path: {path}"
  let input ← IO.FS.readFile path
  enableInitializersExecution
  let inputCtx := Parser.mkInputContext input path.toString
  let (header, parserState, messages) ← Parser.parseHeader inputCtx
  let (env, messages) ← processHeader header {} messages inputCtx

  if messages.hasErrors then
    for msg in messages.toList do
      if msg.severity == .error then
        println! "ERROR: {← msg.toString}"
    throw $ IO.userError "Errors during import; aborting"

  let env := env.setMainModule (← moduleNameOfFileName path none)
  let commandState := { Command.mkState env messages {} with infoState.enabled := true }
  let s ← IO.processCommands inputCtx parserState commandState
  let env' := s.commandState.env
  let commands := s.commands.pop -- Remove EOI command.
  let trees := s.commandState.infoState.trees.toArray

  println! s!"processFile, commands: {commands}"
  let traceM := (traverseForest trees env').run' ⟨#[header] ++ commands, #[], #[]⟩
  let (trace, _) ← traceM.run'.toIO {fileName := s!"{path}", fileMap := FileMap.ofString input} {env := env}

  let cwd ← IO.currentDir
  assert! cwd.fileName != "lean4"

  let some relativePath := Path.relativeTo path cwd | throw $ IO.userError s!"Invalid path: {path}"
  let json_path := Path.toBuildDir "ir" relativePath "ast.json" |>.get!
  Path.makeParentDirs json_path
  IO.FS.writeFile json_path (toJson trace).pretty

  let dep_path := Path.toBuildDir "ir" relativePath "dep_paths" |>.get!
  Path.makeParentDirs dep_path
  IO.FS.writeFile dep_path (← getImports header)

/--
Whether a *.lean file should be traced.
-/
def shouldProcess (path : FilePath) (noDeps : Bool) : IO Bool := do
  if (← path.isDir) ∨ path.extension != "lean" then
    return false

  let cwd ← IO.currentDir
  let some relativePath := Path.relativeTo path cwd |
    throw $ IO.userError s!"Invalid path: {path}"

  if noDeps ∧ Path.isRelativeTo relativePath Path.packagesDir then
    return false

  let some oleanPath := Path.toBuildDir "lib/lean" relativePath "olean" |
    throw $ IO.userError s!"Invalid path: {path}"

  if ¬ (← oleanPath.pathExists) then
    println! s!"olean does not exist: {path}"
  return ← oleanPath.pathExists

/--
Trace all *.lean files in the current directory whose corresponding *.olean file exists.
-/
def processAllFiles (extractLeanPath : String) (noDeps : Bool) : IO Unit := do
  IO.println s!"processAllFiles, extractLeanPath: {extractLeanPath}, noDeps: {noDeps}!"
  let cwd ← IO.currentDir
  assert! cwd.fileName != "lean4"
  println! "Extracting data at {cwd}"

  let mut tasks := #[]
  for path in ← System.FilePath.walkDir cwd do
    if ← shouldProcess path noDeps then
      let t ← IO.asTask $ IO.Process.run
        {cmd := "lake", args := #["env", "lean", "--run", extractLeanPath, path.toString]}
      tasks := tasks.push (t, path)

  for (t, path) in tasks do
    match ← IO.wait t with
    | Except.error e =>
      println! s!"WARNING: Failed to process {path} {e}"
      println! s!"WARNING: task {t.get}"
      pure ()
      -- throw e
    | Except.ok _ => pure ()
