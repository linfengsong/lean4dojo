from typing import Optional, Self
from pathlib import Path
from dataclasses import dataclass
from dataclasses_json import dataclass_json
from jixia.structs import (
    Modifiers, ModuleInfo, PPSyntax, Param, Symbol, Declaration, StringRange, 
    InfoTree, OpenDecl, ScopeInfo, PPSyntaxWithKind,
    Variable,SpecialValue,TermElabInfo,Goal,TacticElabInfo,ElabInfo
)
from .structs import (
    LeanModifiers, LeanModuleInfo, LeanPPSyntax, LeanParam, LeanSymbol, LeanDeclaration, LeanStringRange, 
    LeanInfoTree, LeanOpenDecl, LeanOpenDeclSimple, LeanOpenDeclRename, LeanScopeInfo, LeanPPSyntaxWithKind,
    LeanVariable, LeanSpecialValue, LeanTermElabInfo, LeanGoal, LeanTacticElabInfo, LeanElabInfo
)

LeanIdent = str

@dataclass_json
@dataclass
class ModuleData:
    docstring: Optional[str]
    imports: list[list[str]]
    
    @classmethod
    def create(cls, module_info: ModuleInfo) -> Self:
        return cls(
            docstring=module_info.docstring,
            imports=module_info.imports
        )
    
    @classmethod
    def lean_create(cls, module_info: LeanModuleInfo) -> Self:
        return cls(
            docstring=module_info.docstring,
            imports=module_info.imports
        )
    
@dataclass_json
@dataclass
class SymbolData:
    kind: str
    name: LeanIdent
    type_full: Optional[str]
    type_readable: Optional[str]
    type_fallback: Optional[str]
    type_references: list[LeanIdent]
    value_references: Optional[list[LeanIdent]]
    is_prop: bool

    @classmethod
    def create(cls, symbol: Symbol) -> Self:
        return cls(
            kind=str(symbol.kind),
            name=to_lean_ident(symbol.name),
            type_full=symbol.type_full,
            type_readable=symbol.type_readable,
            type_fallback=symbol.type_fallback,
            type_references=[ to_lean_ident(ref) for ref in symbol.type_references],
            value_references=[ to_lean_ident(ref) for ref in symbol.value_references] if symbol.value_references is not None else None,
            is_prop=symbol.is_prop
        )
    
    @classmethod
    def lean_create(cls, symbol: LeanSymbol) -> Self:
        return cls(
            kind=str(symbol.kind),
            name=to_lean_ident(symbol.name),
            type_full=symbol.type_full,
            type_readable=symbol.type_readable,
            type_fallback=symbol.type_fallback,
            type_references=[ to_lean_ident(ref) for ref in symbol.type_references],
            value_references=[ to_lean_ident(ref) for ref in symbol.value_references] if symbol.value_references is not None else None,
            is_prop=symbol.is_prop
        )
    
@dataclass_json
@dataclass
class RangeData:
    start: int
    stop: int

    @classmethod
    def create(cls, range: StringRange) -> Self:
        return cls(
            start=int(range.start),
            stop=int(range.stop)
        )
    
    @classmethod
    def lean_create(cls, range: LeanStringRange) -> Self:
        return cls(
            start=range.start,
            stop=range.stop
        )

@dataclass_json
@dataclass
class PPSyntaxData:
    original: bool
    range: Optional[RangeData]
    pp: Optional[str]

    @classmethod
    def create(cls, ppSyntax: PPSyntax) -> Self:
        return cls(
            original=ppSyntax.original,
            range=RangeData.create(ppSyntax.range) if ppSyntax.range is not None else None,
            pp=ppSyntax.pp
        )
    
    @classmethod
    def lean_create(cls, ppSyntax: LeanPPSyntax) -> Self:
        return cls(
            original=ppSyntax.original,
            range=RangeData.lean_create(ppSyntax.range) if ppSyntax.range is not None else None,
            pp=ppSyntax.pp
        )

@dataclass_json
@dataclass
class ParamData:
    ref: Optional[RangeData]
    id: Optional[RangeData]
    type: Optional[RangeData]
    binder_info: LeanIdent

    @classmethod
    def create(cls, param: Param) -> Self:
        return cls(
            ref=RangeData.create(param.ref) if param.ref is not None else None,
            id=RangeData.create(param.id) if param.id is not None else None,
            type=RangeData.create(param.type) if param.type is not None else None,
            binder_info=to_lean_ident(param.binder_info)
        )
    
    @classmethod
    def lean_create(cls, param: LeanParam) -> Self:
        return cls(
            ref=RangeData.lean_create(param.ref) if param.ref is not None else None,
            id=RangeData.lean_create(param.id) if param.id is not None else None,
            type=RangeData.lean_create(param.type) if param.type is not None else None,
            binder_info=to_lean_ident(param.binder_info)
        )
    
@dataclass_json
@dataclass
class ModifiersData:
    visibility: str
    compute_kind: str
    rec_kind: str
    is_unsafe: bool
    docstring: Optional[str]
    has_docstring: Optional[bool]
    is_noncomputable: bool = False

    @classmethod
    def create(cls, modifiers: Modifiers) -> Self:
        return cls(
            visibility=str(modifiers.visibility),
            compute_kind=str(modifiers.compute_kind),
            rec_kind=str(modifiers.rec_kind),
            is_unsafe=modifiers.is_unsafe,
            docstring=modifiers.docstring[0] if modifiers.docstring is not None else None,
            has_docstring=modifiers.docstring[1] if modifiers.docstring is not None else None,
            #is_noncomputable=modifiers.is_noncomputable
        )
    
    @classmethod
    def lean_create(cls, modifiers: LeanModifiers) -> Self:
        return cls(
            visibility=str(modifiers.visibility),
            compute_kind=str(modifiers.compute_kind),
            rec_kind=str(modifiers.rec_kind),
            is_unsafe=modifiers.is_unsafe,
            docstring=modifiers.docstring[0] if modifiers.docstring is not None else None,
            has_docstring=modifiers.docstring[1] if modifiers.docstring is not None else None,
            #is_noncomputable=modifiers.is_noncomputable
        )
    
@dataclass_json
@dataclass
class OpenDeclSimpleData:
    namespace: LeanIdent
    hiding: list[LeanIdent]

    @classmethod
    def create(cls, simple: OpenDecl.Simple):
        return cls(
            namespace=to_lean_ident(simple.namespace),
            hiding=[ to_lean_ident(item) for item in simple.hiding ]
        )
    
    @classmethod
    def lean_create(cls, simple: LeanOpenDeclSimple):
        return cls(
            namespace=to_lean_ident(simple.namespace),
            hiding=[ to_lean_ident(item) for item in simple.hiding ]
        )

@dataclass_json
@dataclass
class OpenDeclRenameData:
    name: LeanIdent
    as_: LeanIdent

    @classmethod
    def create(cls, rename: OpenDecl.Rename):
        return cls(
            name=to_lean_ident(rename.name),
            as_=to_lean_ident(rename.as_),
        )
    
    @classmethod
    def lean_create(cls, rename: LeanOpenDeclRename):
        return cls(
            name=to_lean_ident(rename.name),
            as_=to_lean_ident(rename.as_),
        )

@dataclass_json
@dataclass
class OpenDeclData:
    simple: Optional[OpenDeclSimpleData]
    rename: Optional[OpenDeclRenameData]

    @classmethod
    def create(cls, openDecl: OpenDecl):
        return cls(
            simple=OpenDeclSimpleData.create(openDecl.simple) if openDecl.simple is not None else None,
            rename=OpenDeclRenameData.create(openDecl.rename) if openDecl.rename is not None else None
        )
    
    @classmethod
    def lean_create(cls, openDecl: LeanOpenDecl):
        return cls(
            simple=OpenDeclSimpleData.lean_create(openDecl.simple) if openDecl.simple is not None else None,
            rename=OpenDeclRenameData.lean_create(openDecl.rename) if openDecl.rename is not None else None
        )
    
@dataclass_json
@dataclass
class ScopeInfoData:
    var_decls: list[str]
    include_vars: list[LeanIdent]
    omit_vars: list[LeanIdent]
    curr_namespace: LeanIdent
    open_decl: list[OpenDecl]

    @classmethod
    def create(cls, scopeInfo: ScopeInfo):
        return cls(
            var_decls=scopeInfo.var_decls,
            include_vars=[ to_lean_ident(var) for var in scopeInfo.include_vars ],
            omit_vars=[ to_lean_ident(var) for var in scopeInfo.omit_vars ],
            curr_namespace=to_lean_ident(scopeInfo.curr_namespace),
            open_decl=[ OpenDeclData.create(decl) for decl in scopeInfo.open_decl ],
        )
    
    @classmethod
    def lean_create(cls, scopeInfo: LeanScopeInfo):
        return cls(
            var_decls=scopeInfo.var_decls,
            include_vars=[ to_lean_ident(var) for var in scopeInfo.include_vars ],
            omit_vars=[ to_lean_ident(var) for var in scopeInfo.omit_vars ],
            curr_namespace=to_lean_ident(scopeInfo.curr_namespace),
            open_decl=[ OpenDeclData.lean_create(decl) for decl in scopeInfo.open_decl ],
        )

@dataclass_json
@dataclass
class DeclarationData:
    kind: str
    ref: PPSyntaxData
    name: LeanIdent
    signature: PPSyntaxData
    modifiers: ModifiersData
    params: list[ParamData]
    type: Optional[PPSyntaxData]
    value: Optional[PPSyntaxData]
    scope_info: Optional[ScopeInfoData]

    @classmethod
    def create(cls, decl: Declaration):
        return cls(
            kind=str(decl.kind),
            ref=PPSyntaxData.create(decl.ref),
            name=to_lean_ident(decl.name),
            signature=PPSyntaxData.create(decl.signature),
            modifiers=ModifiersData.create(decl.modifiers),
            params=[ ParamData.create(param) for param in decl.params ],
            type=PPSyntaxData.create(decl.type) if decl.type is not None else None,
            value=PPSyntaxData.create(decl.value) if decl.value is not None else None,
            scope_info=ScopeInfoData.create(decl.scope_info) if decl.scope_info is not None else None
        )
    
    @classmethod
    def lean_create(cls, decl: LeanDeclaration):
        return cls(
            kind=str(decl.kind),
            ref=PPSyntaxData.lean_create(decl.ref),
            name=to_lean_ident(decl.name),
            signature=PPSyntaxData.lean_create(decl.signature),
            modifiers=ModifiersData.lean_create(decl.modifiers),
            params=[ ParamData.lean_create(param) for param in decl.params ],
            type=PPSyntaxData.lean_create(decl.type) if decl.type is not None else None,
            value=PPSyntaxData.lean_create(decl.value) if decl.value is not None else None,
            scope_info=ScopeInfoData.lean_create(decl.scope_info) if decl.scope_info is not None else None
        )
    
@dataclass_json
@dataclass
class PPSyntaxWithKindData(PPSyntaxData):
    kind: LeanIdent

    @classmethod
    def create(cls, ppSyntax: PPSyntaxWithKind):
        return cls(
            ppSyntax.original,
            RangeData.create(ppSyntax.range) if ppSyntax.range is not None else None,
            ppSyntax.pp,
            to_lean_ident(ppSyntax.kind)
        )
    
    @classmethod
    def lean_create(cls, ppSyntax: LeanPPSyntaxWithKind):
        return cls(
            ppSyntax.original,
            RangeData.lean_create(ppSyntax.range) if ppSyntax.range is not None else None,
            ppSyntax.pp,
            to_lean_ident(ppSyntax.kind)
        )
    
@dataclass_json
@dataclass
class VariableData:
    id: LeanIdent
    name: LeanIdent
    binder_info: Optional[str]
    type: str
    value: Optional[str]
    is_prop: bool

    @classmethod
    def create(cls, variable: Variable):
        return cls(
            id=to_lean_ident(variable.id),
            name=to_lean_ident(variable.name),
            binder_info=variable.binder_info,
            type=variable.type,
            value=variable.value,
            is_prop=variable.is_prop
        )
    
    @classmethod
    def lean_create(cls, variable: LeanVariable):
        return cls(
            id=to_lean_ident(variable.id),
            name=to_lean_ident(variable.name),
            binder_info=variable.binder_info,
            type=variable.type,
            value=variable.value,
            is_prop=variable.is_prop
        )

@dataclass_json
@dataclass
class SpecialValueData:
    const: Optional[LeanIdent]
    fvar: Optional[LeanIdent]

    @classmethod
    def create(cls, value: SpecialValue):
        return cls(
            const=to_lean_ident(value.const) if value.const is not None else None,
            fvar=to_lean_ident(value.fvar) if value.fvar is not None else None
        )

    @classmethod
    def lean_create(cls, value: LeanSpecialValue):
        return cls(
            const=to_lean_ident(value.const) if value.const is not None else None,
            fvar=to_lean_ident(value.fvar) if value.fvar is not None else None
        )

@dataclass_json
@dataclass
class TermElabInfoData:
    context: list[Variable]
    type: str
    expected_type: Optional[str]
    value: str
    special: Optional[SpecialValue]

    @classmethod
    def create(cls, termElab: TermElabInfo):
        return cls(
            context=[ VariableData.create(var) for var in termElab.context ],
            type=termElab.type,
            expected_type=termElab.expected_type,
            value=termElab.value,
            special=SpecialValueData.create(termElab.special) if termElab.special is not None else None
        )
    
    @classmethod
    def lean_create(cls, termElab: LeanTermElabInfo):
        return cls(
            context=[ VariableData.lean_create(var) for var in termElab.context ],
            type=termElab.type,
            expected_type=termElab.expected_type,
            value=termElab.value,
            special=SpecialValueData.lean_create(termElab.special) if termElab.special is not None else None
        )

@dataclass_json
@dataclass
class GoalData:
    tag: LeanIdent
    context: list[VariableData]
    type: str
    is_prop: bool
    pp: Optional[str] = None

    @classmethod
    def create(cls, termElab: Goal):
        return cls(
            tag=to_lean_ident(termElab.tag),
            context=[ VariableData.create(var) for var in termElab.context ],
            type=termElab.type,
            is_prop=termElab.is_prop,
            pp=termElab.pp
        )
    
    @classmethod
    def lean_create(cls, termElab: LeanGoal):
        return cls(
            tag=to_lean_ident(termElab.tag),
            context=[ VariableData.lean_create(var) for var in termElab.context ],
            type=termElab.type,
            is_prop=termElab.is_prop,
            pp=termElab.pp
        )
    
@dataclass_json
@dataclass
class TacticElabInfoData:

    references: list[LeanIdent]
    before: list[GoalData]
    after: list[GoalData]

    @classmethod
    def create(cls, tactic: TacticElabInfo):
        return cls(
            references=[ to_lean_ident(ref) for ref in tactic.references ],
            before=[ GoalData.create(goal) for goal in tactic.before ],
            after=[ GoalData.create(goal) for goal in tactic.after ]
        )
    
    @classmethod
    def lean_create(cls, tactic: LeanTacticElabInfo):
        return cls(
            references=[ to_lean_ident(ref) for ref in tactic.references ],
            before=[ GoalData.lean_create(goal) for goal in tactic.before ],
            after=[ GoalData.lean_create(goal) for goal in tactic.after ]
        )

@dataclass_json
@dataclass
class ElabInfoData:
    term: Optional[TermElabInfoData]
    tactic: Optional[TacticElabInfoData]
    macro: Optional[PPSyntaxWithKindData]
    simple: Optional[str]

    @classmethod
    def create(cls, elabInfo: ElabInfo):
        return cls(
            term=TermElabInfoData.create(elabInfo.term) if elabInfo.term is not None else None,
            tactic=TacticElabInfoData.create(elabInfo.tactic) if elabInfo.tactic is not None else None,
            macro=PPSyntaxWithKindData.create(elabInfo.macro.expanded) if elabInfo.macro is not None else None,
            simple=str(elabInfo.simple) if elabInfo.simple is not None else None
        )
    
    @classmethod
    def lean_create(cls, elabInfo: LeanElabInfo):
        return cls(
            term=TermElabInfoData.lean_create(elabInfo.term) if elabInfo.term is not None else None,
            tactic=TacticElabInfoData.lean_create(elabInfo.tactic) if elabInfo.tactic is not None else None,
            macro=PPSyntaxWithKindData.lean_create(elabInfo.macro.expanded) if elabInfo.macro is not None else None,
            simple=str(elabInfo.simple) if elabInfo.simple is not None else None
        )

@dataclass_json
@dataclass
class InfoTreeData:
    info: ElabInfoData
    ref: PPSyntaxWithKindData
    children: list[Self]

    @classmethod
    def create(cls, infoTree: InfoTree):
        return cls(
            info=ElabInfoData.create(infoTree.info),
            ref=PPSyntaxWithKindData.create(infoTree.ref),
            children=[ InfoTreeData.create(child) for child in infoTree.children ]
        )
    
    @classmethod
    def lean_create(cls, infoTree: LeanInfoTree):
        return cls(
            info=ElabInfoData.lean_create(infoTree.info),
            ref=PPSyntaxWithKindData.lean_create(infoTree.ref),
            children=[ InfoTreeData.lean_create(child) for child in infoTree.children ]
        )

def to_lean_ident(name: list[str]):
    return ".".join([str(v) for v in name])
