import Lean
import Lake


open Lean Elab System

set_option maxHeartbeats 2000000  -- 10x the default maxHeartbeats.


instance : ToJson Substring where
  toJson s := toJson s.toString

instance : ToJson String.Pos where
  toJson n := toJson n.1

deriving instance ToJson for SourceInfo
deriving instance ToJson for Syntax.Preresolved
deriving instance ToJson for Syntax
deriving instance ToJson for Position


/--
The trace of a tactic.
-/
structure TacticTrace where
  stateBefore: String
  stateAfter: String
  pos: String.Pos      -- Start position of the tactic.
  endPos: String.Pos   -- End position of the tactic.
deriving ToJson


/--
The trace of a premise.
-/
structure PremiseTrace where
  fullName: String            -- Fully-qualified name of the premise.
  defPos: Option Position     -- Where the premise is defined.
  defEndPos: Option Position
  modName: String             -- In which module the premise is defined.
  defPath: String             -- The path of the file where the premise is defined.
  pos: Option Position        -- Where the premise is used.
  endPos: Option Position
deriving ToJson


/--
The trace of a Lean file.
-/
structure Trace where
  commandASTs : Array Syntax    -- The ASTs of the commands in the file.
  tactics: Array TacticTrace    -- All tactics in the file.
  premises: Array PremiseTrace  -- All premises in the file.
deriving ToJson


abbrev TraceM := StateT Trace MetaM
