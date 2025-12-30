import Lean
import Lake

open Lean Elab System

namespace Path

/--
Return the path of `path` relative to `parent`.
-/
def relativeTo (path parent : FilePath) : Option FilePath :=
  let rec componentsRelativeTo (pathComps parentComps : List String) : Option FilePath :=
    match pathComps, parentComps with
    | _, [] => mkFilePath pathComps
    | [], _ => none
    | (h₁ :: t₁), (h₂ :: t₂) =>
      if h₁ == h₂ then
        componentsRelativeTo t₁ t₂
      else
        none

    componentsRelativeTo path.components parent.components


/--
Return if the path `path` is relative to `parent`.
-/
def isRelativeTo (path parent : FilePath) : Bool :=
  match relativeTo path parent with
  | some _ => true
  | none => false


/--
Convert the path `path` to an absolute path.
-/
def toAbsolute (path : FilePath) : IO FilePath := do
  if path.isAbsolute then
    pure path
  else
    let cwd ← IO.currentDir
    pure $ cwd / path


private def trim (path : FilePath) : FilePath :=
  assert! path.isRelative
  mkFilePath $ path.components.filter (· != ".")


def packagesDir : FilePath :=
  if Lake.defaultPackagesDir == "packages"  then
    ".lake" / Lake.defaultPackagesDir
  else
    Lake.defaultPackagesDir


def buildDir : FilePath :=
  if Lake.defaultPackagesDir.fileName == "packages" then  -- Lean >= v4.3.0-rc2
    ".lake/build"
  else  -- Lean < v4.3.0-rc2
   "build"


def libDir : FilePath := buildDir / "lib" / "lean"


/--
Convert the path of a *.lean file to its corresponding file (e.g., *.olean) in the "build" directory.
-/
def toBuildDir (subDir : FilePath) (path : FilePath) (ext : String) : Option FilePath :=
  let path' := (trim path).withExtension ext
  match relativeTo path' $ packagesDir / "lean4/src" with
  | some p =>
    match relativeTo p "lean/lake" with
    | some p' => packagesDir / "lean4/lib/lean" / p'
    | none => packagesDir / "lean4/lib" / p
  | none => match relativeTo path' packagesDir with
    | some p =>
      match p.components with
      | [] => none
      | hd :: tl => packagesDir / hd / buildDir / subDir / (mkFilePath tl)
    | none => buildDir / subDir / path'


/--
The reverse of `toBuildDir`.
-/
-- proofwidgets/build/lib/ProofWidgets/Compat.lean
-- proofwidgets/.lake/build/lib
def toSrcDir! (path : FilePath) (ext : String) : FilePath :=
  let path' := (trim path).withExtension ext
  match relativeTo path' $ packagesDir / "lean4/lib" with
  | some p =>  -- E.g., `.lake/packages/lean4/lib/lean/Init/Prelude.olean` -> `.lake/packages/lean4/src/lean/Init/Prelude.lean`
    packagesDir / "lean4/src" / p
  | none =>
    match relativeTo path' packagesDir with
    | some p =>  -- E.g., `.lake/packages/aesop/.lake/build/lib/lean/Aesop.olean`-> `.lake/packages/aesop/Aesop.lean`
      let pkgName := p.components.head!
      let sep := "build/lib/lean/"
      packagesDir / pkgName / (p.toString.splitOn sep |>.tail!.head!)
    | none =>
      -- E.g., `.lake/build/lib/lean/Mathlib/LinearAlgebra/Basic.olean` -> `Mathlib/LinearAlgebra/Basic.lean`
      relativeTo path' libDir |>.get!


/--
Create all parent directories of `p` if they don't exist.
-/
def makeParentDirs (p : FilePath) : IO Unit := do
  let some parent := p.parent | throw $ IO.userError s!"Unable to get the parent of {p}"
  IO.FS.createDirAll parent


/--
Return the *.lean file corresponding to a module name.
-/
def findLean (mod : Name) : IO FilePath := do
  IO.println s!"xxxxx findLean"
  let modStr := mod.toString
  if modStr.startsWith "«lake-packages»." then
    return FilePath.mk (modStr.replace "«lake-packages»" "lake-packages" |>.replace "." "/") |>.withExtension "lean"
  if modStr.startsWith "«.lake»." then
    return FilePath.mk (modStr.replace "«.lake»" ".lake" |>.replace "." "/") |>.withExtension "lean"
  if modStr == "Lake" then
    return packagesDir / "lean4/src/lean/lake/Lake.lean"
  IO.println s!"xxxxx findLean, mod: {mod}"
  let olean ← findOLean mod
  IO.println s!"xxxxx findLean, olean: {olean}"
  -- Remove a "build/lib/lean/" substring from the path.
  let lean := olean.toString.replace ".lake/build/lib/lean/" ""
    |>.replace "build/lib/lean/" "" |>.replace "lib/lean/Lake/" "lib/lean/lake/Lake/"
  let mut path := FilePath.mk lean |>.withExtension "lean"
  let leanLib ← getLibDir (← getBuildDir)
  if let some p := relativeTo path leanLib then
    path := packagesDir / "lean4/src/lean" / p
  assert! ← path.pathExists
  return path

end Path
