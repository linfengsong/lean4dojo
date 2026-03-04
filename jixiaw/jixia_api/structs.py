import msgspec
from collections.abc import Sequence
from typing import Optional, Literal, TypeVar, List

LeanNameID = list[str | int]

def is_lean_disjoint_union(*xs) -> bool:
    return sum(x is not None for x in xs) == 1
    
# Declaration types
LeanBinderInfo = Literal["default", "implicit", "strictImplicit", "instImplicit"]
#### original file missing define protected
LeanVisibility = Literal["regular", "protected", "private", "public"]
LeanComputeKind = Literal["regular", "meta", "noncomputable"]
LeanRecKind = Literal["default", "partial", "nonrec"]
LeanDeclarationKind = Literal[
    "abbrev",
    "axiom",
    "classInductive",
    "definition",
    "example",
    "inductive",
    "instance",
    "opaque",
    "structure",
    "theorem",
    "proofWanted",
]
# Symbol
LeanSymbolKind = Literal[
    "axiom",
    "definition",
    "theorem",
    "opaque",
    "quotient",
    "inductive",
    "constructor",
    "recursor",
]

LeanSimpleElabInfo = Literal[
    "command",
    "field",
    "option",
    "completion",
    "uw",
    "custom",
    "alias",
    "redecl",
    "omission",
    "partial",
    "term",
]

# Module Info
class LeanModuleInfo(msgspec.Struct):
    """Module-level information"""

    imports: list[LeanNameID]
    """Modules directly imported by this module"""
    docstring: list[str]
    """List of all docstrings in this module, as marked by /-! ... -/"""


class LeanStringRange(msgspec.Struct, array_like=True):
    """A byte range within a file"""

    start: int
    stop: int

    def as_slice(self) -> slice:
        return slice(self.start, self.stop)


class LeanParam(msgspec.Struct):
    """A parameter to a declaration, as defined in the source code"""

    ref: Optional[LeanStringRange] = None
    """The entire syntax object, e.g., `{x : A}`"""
    id: Optional[LeanStringRange] = None
    """The identifier part, e.g., `x` in {x : A}"""
    type: Optional[LeanStringRange] = None
    """The type part, e.g., `A` in {x : A}"""
    binder_info: LeanBinderInfo = "default"
    """The binder kind of this parameter, e.g., `implicit` for {x : A}"""


class LeanModifiers(msgspec.Struct):
    """A modifier attached to a declaration"""

    visibility: LeanVisibility
    """Visibility level of a declaration"""
    is_noncomputable: bool = False
    compute_kind: LeanComputeKind = "regular"
    rec_kind: LeanRecKind = "default"
    """Recursion level of a declaration"""
    is_unsafe: bool = False
    docstring: Optional[tuple[str, bool]] = None


class LeanSyntax(msgspec.Struct):
    """A simplified representation of a Syntax node"""

    original: bool
    """Whether this Syntax node is original or generated (e.g., by a macro)"""
    range: Optional[LeanStringRange] = None


class LeanPPSyntax(msgspec.Struct):
    """A Syntax node with pretty-printing info"""

    original: bool
    range: Optional[LeanStringRange] = None
    pp: Optional[str] = None


class LeanOpenDeclSimple(msgspec.Struct):
    """Simple open declaration"""
    namespace: LeanNameID
    hiding: list[LeanNameID] = msgspec.field(default_factory=list)


class LeanOpenDeclRename(msgspec.Struct):
    """Rename open declaration"""
    name: LeanNameID
    as_: LeanNameID = msgspec.field(name="as")


class LeanOpenDecl(msgspec.Struct):
    """An `open` directive in Lean"""

    simple: Optional[LeanOpenDeclSimple] = None
    rename: Optional[LeanOpenDeclRename] = None

    def __post_init__(self):
        if not is_lean_disjoint_union(self.simple, self.rename):
            raise ValueError("exactly one of [simple, rename] is expected")


class LeanScopeInfo(msgspec.Struct):
    """Current scope info, i.e., variables, namespaces, etc.  Used for isolating declarations in a file"""

    var_decls: list[str]
    """`variable` directives"""
    include_vars: list[LeanNameID]
    """variables marked with `include`"""
    omit_vars: list[LeanNameID]
    """variables marked with `omit`"""
    curr_namespace: LeanNameID
    """The current namespace"""
    open_decl: list[LeanOpenDecl]
    """`open` directives"""


class LeanDeclaration(msgspec.Struct):
    """Declarations in the source code"""
    
    kind: LeanDeclarationKind
    """Kind of a declaration"""
    ref: LeanPPSyntax
    name: LeanNameID
    signature: LeanPPSyntax
    """The signature part, e.g., `{α : Sort u} (a : α) : α` in `def id {α : Sort u} (a : α) : α`"""
    modifiers: LeanModifiers
    params: list[LeanParam]
    type: Optional[LeanPPSyntax] = None
    value: Optional[LeanPPSyntax] = None
    scope_info: Optional[LeanScopeInfo] = None

class LeanSymbol(msgspec.Struct):
    """
    A symbol, as seen by the Lean kernel.

    Usually called a `constant` in Lean terminology.
    """

    kind: LeanSymbolKind
    name: LeanNameID
    type_full: Optional[str] = None
    type_readable: Optional[str] = None
    type_fallback: str = ""
    type_references: list[LeanNameID] = msgspec.field(default_factory=list)
    """Names used in defining the type of this symbol"""
    value_references: Optional[list[LeanNameID]] = None
    """Names used in defining the value of this symbol, or None if it has no value"""
    is_prop: bool = False
    """Whether the type of this symbol is a `Prop`"""


    @property
    def type(self) -> str:
        return self.type_full or self.type_fallback


# Context / Goal
class LeanVariable(msgspec.Struct, kw_only=True):
    """
    A variable in Lean contexts.

    Usually called a :term:`free variable` or an `fvar` in Lean terminology.
    """

    id: LeanNameID
    name: LeanNameID
    binder_info: Optional[LeanBinderInfo] = None
    """Binder info of this variable, or None if it is defined by a `let`"""
    type: str
    value: Optional[str] = None
    """Value of this variable if it is defined by a `let`, or None otherwise"""
    is_prop: bool = False


LeanContext = list[LeanVariable]
"""A :term:`local context` in Lean"""


class LeanGoal(msgspec.Struct):
    """A :term:`metavariable` in Lean"""

    tag: LeanNameID
    """The user name of this metavariable"""
    context: LeanContext
    type: str
    is_prop: bool = False
    pp: str = None
    """Pretty-printed representation of this goal by `Meta.ppGoal`"""


LeanProofState = list[LeanGoal]
"""A :term:`proof state`, represented by a list of goals"""


# Elaboration
class LeanPPSyntaxWithKind(msgspec.Struct):
    """A Syntax node with pretty-printing and kind info"""

    original: bool
    range: Optional[LeanStringRange] = None
    pp: Optional[str] = None
    kind: LeanNameID = msgspec.field(default_factory=list)
    """Syntax kind"""


class LeanTacticElabInfo(msgspec.Struct):
    """An InfoTree node about a tactic"""

    references: list[LeanNameID] = msgspec.field(default_factory=list)
    """Names directly referenced in the tactic"""
    before: LeanProofState = msgspec.field(default_factory=list)
    after: LeanProofState = msgspec.field(default_factory=list)


class LeanSpecialValue(msgspec.Struct):
    """Marks the current value is of a special form of interest"""

    const: Optional[LeanNameID] = None
    """This value is a constant reference"""
    fvar: Optional[LeanNameID] = None
    """This value is a fvar reference"""

    def __post_init__(self):
        if not is_lean_disjoint_union(self.const, self.fvar):
            raise ValueError("exactly one of [const, fvar] is expected")


class LeanTermElabInfo(msgspec.Struct):
    """An InfoTree node about a term"""

    context: LeanContext = msgspec.field(default_factory=list)
    type: str = ""
    expected_type: Optional[str] = None
    value: str = ""
    special: Optional[LeanSpecialValue] = None


class LeanMacroInfo(msgspec.Struct):
    """An InfoTree node about a macro expansion"""

    expanded: LeanPPSyntaxWithKind

class LeanElabInfo(msgspec.Struct):
    """
    An InfoTree node

    Can be one of term node, tactic node, macro node, or simple node.

    A simple node is one with only its kind recorded.
    """

    term: Optional[LeanTermElabInfo] = None
    tactic: Optional[LeanTacticElabInfo] = None
    macro: Optional[LeanMacroInfo] = None
    simple: Optional[LeanSimpleElabInfo] = None

    def __post_init__(self):
        if not is_lean_disjoint_union(self.term, self.tactic, self.macro, self.simple):
            raise ValueError("exactly one of [term, tactic, macro, simple] is expected")


class LeanInfoTree(msgspec.Struct):
    """An InfoTree node with elaboration information"""
    
    info: LeanElabInfo
    ref: LeanPPSyntaxWithKind
    children: list["LeanInfoTree"]= msgspec.field(default_factory=list)

class LeanLineModel(msgspec.Struct):
    """An Line node with line information"""
    start: int

class LeanSyntaxOriginal(msgspec.Struct):
    pos: int
    endPos: int
    leading: str = ""
    trailing: str = ""

class LeanSyntaxInfo(msgspec.Struct):
    original: Optional[LeanSyntaxOriginal] = None

class LeanSyntaxAtom(msgspec.Struct):
    val: str
    info: Optional[LeanSyntaxInfo] = None

class LeanSyntaxIdent(msgspec.Struct):
    val: List[str]      # 注意：您的範例中 val 是 ["hello_world"] 陣列
    rawVal: str
    info: Optional[LeanSyntaxInfo] = None
    preresolved: List[str] = []

class LeanSyntaxNode(msgspec.Struct):
    kind: Optional[str] = None # Jixia 有時在 node 外層或內層標註 kind
    args: List["LeanSyntaxTree"] = []

class LeanSyntaxTreeInfo(msgspec.Struct):
    node: Optional[LeanSyntaxNode] = None
    atom: Optional[LeanSyntaxAtom] = None
    ident: Optional[LeanSyntaxIdent] = None

class LeanSyntaxTree(msgspec.Struct):
    kind: str
    children: Optional[List[Optional["LeanSyntaxTree"]]] = None
    value: Optional[str] = None
    range: Optional[LeanStringRange] = None
    info: Optional[LeanSyntaxTreeInfo] = None
