from sheetlens.formulas import dependency_edges, normalize_formula
from sheetlens.model import ir


def test_normalize_formula_uses_cell_relative_r1c1_and_preserves_literals():
    assert normalize_formula(
        '=c11+$C11+C$11+$C$11+"c11"',
        origin="E11",
    ) == '=R[0]C[-2]+R[0]C3+R11C[-2]+R11C3+"c11"'
    assert normalize_formula("='My Sheet'!a10:b12", origin="D11") == (
        "='My Sheet'!R[-1]C[-3]:R[1]C[-2]"
    )


def test_dependency_edges_distinguish_external_names_and_unresolved_operands():
    workbook = ir.Workbook(
        source_file="source.xlsx",
        sha256="00" * 32,
        sheets=[
            ir.Sheet(
                name="Input",
                cells=[
                    ir.Cell(
                        ref="A1",
                        formula=(
                            "='rates'!$A$1+[Book.xlsx]Rates!B2+RateName+"
                            "UnknownName+Table1[Amount]+Sheet1:Sheet3!C3"
                        ),
                    )
                ],
            ),
            ir.Sheet(name="Rates"),
            ir.Sheet(name="Sheet1"),
            ir.Sheet(name="Sheet3"),
        ],
        defined_names={"RateName": "='Rates'!$B$2"},
    )

    assert [edge.model_dump() for edge in dependency_edges(workbook)] == [
        {
            "source": "cell:'Input'!A1",
            "target_workbook": None,
            "target_sheet": "Rates",
            "target_range": "$A$1",
            "unresolved": False,
        },
        {
            "source": "cell:'Input'!A1",
            "target_workbook": None,
            "target_sheet": "Rates",
            "target_range": "$B$2",
            "unresolved": False,
        },
        {
            "source": "cell:'Input'!A1",
            "target_workbook": None,
            "target_sheet": None,
            "target_range": "Sheet1:Sheet3!C3",
            "unresolved": True,
        },
        {
            "source": "cell:'Input'!A1",
            "target_workbook": None,
            "target_sheet": None,
            "target_range": "Table1[Amount]",
            "unresolved": True,
        },
        {
            "source": "cell:'Input'!A1",
            "target_workbook": None,
            "target_sheet": None,
            "target_range": "UnknownName",
            "unresolved": True,
        },
        {
            "source": "cell:'Input'!A1",
            "target_workbook": "Book.xlsx",
            "target_sheet": "Rates",
            "target_range": "B2",
            "unresolved": True,
        },
    ]


def test_dependency_edges_include_each_validation_and_conditional_format_range():
    workbook = ir.Workbook(
        source_file="source.xlsx",
        sha256="00" * 32,
        sheets=[
            ir.Sheet(
                name="Input Sheet",
                validations=[
                    ir.ValidationRule(
                        ranges=["B5:B9", "C5"],
                        type="list",
                        formula1="=rates!$A$1:$A$2",
                    )
                ],
                conditional_formats=[
                    ir.ConditionalFormat(
                        range="F1:F9 G1:G9",
                        rule_type="expression",
                        formulas=["rates!A1>0"],
                    )
                ],
            ),
            ir.Sheet(name="Rates"),
        ],
    )

    assert [edge.model_dump() for edge in dependency_edges(workbook)] == [
        {
            "source": "conditional_format:'Input Sheet'!F1:F9",
            "target_workbook": None,
            "target_sheet": "Rates",
            "target_range": "A1",
            "unresolved": True,
        },
        {
            "source": "conditional_format:'Input Sheet'!G1:G9",
            "target_workbook": None,
            "target_sheet": "Rates",
            "target_range": "A1",
            "unresolved": True,
        },
        {
            "source": "validation:'Input Sheet'!B5:B9",
            "target_workbook": None,
            "target_sheet": "Rates",
            "target_range": "$A$1:$A$2",
            "unresolved": False,
        },
        {
            "source": "validation:'Input Sheet'!C5",
            "target_workbook": None,
            "target_sheet": "Rates",
            "target_range": "$A$1:$A$2",
            "unresolved": False,
        },
    ]


def test_multicell_relative_validation_reference_is_unresolved():
    workbook = ir.Workbook(
        source_file="source.xlsx",
        sha256="00" * 32,
        sheets=[
            ir.Sheet(
                name="Input",
                validations=[
                    ir.ValidationRule(
                        ranges=["F1:F9", "G1", "H1:H9"],
                        type="custom",
                        formula1="=Rates!A1",
                    ),
                    ir.ValidationRule(
                        ranges=["I1:I9"],
                        type="custom",
                        formula1="=Rates!$A1",
                    ),
                ],
            ),
            ir.Sheet(name="Rates"),
        ],
    )

    edges = {edge.source: edge for edge in dependency_edges(workbook)}
    assert edges["validation:'Input'!F1:F9"].unresolved is True
    assert edges["validation:'Input'!G1"].unresolved is False
    assert edges["validation:'Input'!H1:H9"].unresolved is True
    assert edges["validation:'Input'!I1:I9"].unresolved is True


def test_external_path_and_defined_name_keep_workbook_identity():
    workbook = ir.Workbook(
        source_file="source.xlsx",
        sha256="00" * 32,
        sheets=[
            ir.Sheet(
                name="Input",
                cells=[
                    ir.Cell(ref="A1", formula="='C:\\\\dir\\\\[Book.xlsx]Sheet'!A1"),
                    ir.Cell(ref="A2", formula="=[Book.xlsx]RateName"),
                ],
            )
        ],
    )

    assert [edge.model_dump() for edge in dependency_edges(workbook)] == [
        {
            "source": "cell:'Input'!A1",
            "target_workbook": "Book.xlsx",
            "target_sheet": "Sheet",
            "target_range": "A1",
            "unresolved": True,
        },
        {
            "source": "cell:'Input'!A2",
            "target_workbook": "Book.xlsx",
            "target_sheet": None,
            "target_range": "RateName",
            "unresolved": True,
        },
    ]


def test_unqualified_structured_reference_is_not_an_external_book():
    workbook = ir.Workbook(
        source_file="source.xlsx",
        sha256="00" * 32,
        sheets=[
            ir.Sheet(
                name="Input",
                cells=[ir.Cell(ref="A1", formula="=[Amount]")],
            )
        ],
    )

    assert [edge.model_dump() for edge in dependency_edges(workbook)] == [
        {
            "source": "cell:'Input'!A1",
            "target_workbook": None,
            "target_sheet": None,
            "target_range": "[Amount]",
            "unresolved": True,
        }
    ]


def test_dependency_edges_canonicalize_quoted_sheet_names_and_source_quotes():
    workbook = ir.Workbook(
        source_file="source.xlsx",
        sha256="00" * 32,
        sheets=[
            ir.Sheet(
                name="User's Input",
                cells=[ir.Cell(ref="A1", formula="='bob''s data'!a1")],
            ),
            ir.Sheet(name="Bob's Data"),
        ],
    )

    assert [edge.model_dump() for edge in dependency_edges(workbook)] == [
        {
            "source": "cell:'User''s Input'!A1",
            "target_workbook": None,
            "target_sheet": "Bob's Data",
            "target_range": "A1",
            "unresolved": False,
        }
    ]


def test_defined_name_cycle_is_unresolved():
    workbook = ir.Workbook(
        source_file="source.xlsx",
        sha256="00" * 32,
        sheets=[ir.Sheet(name="Input", cells=[ir.Cell(ref="A1", formula="=First")])],
        defined_names={"First": "=Second", "Second": "=First"},
    )

    assert [edge.model_dump() for edge in dependency_edges(workbook)] == [
        {
            "source": "cell:'Input'!A1",
            "target_workbook": None,
            "target_sheet": None,
            "target_range": "First",
            "unresolved": True,
        }
    ]


def test_tokenize_failure_is_preserved_as_unresolved():
    workbook = ir.Workbook(
        source_file="source.xlsx",
        sha256="00" * 32,
        sheets=[
            ir.Sheet(
                name="Input",
                cells=[ir.Cell(ref="A1", formula='="unterminated')],
            )
        ],
    )

    assert normalize_formula('="unterminated', origin="A1") == '="unterminated'
    assert [edge.model_dump() for edge in dependency_edges(workbook)] == [
        {
            "source": "cell:'Input'!A1",
            "target_workbook": None,
            "target_sheet": None,
            "target_range": '="unterminated',
            "unresolved": True,
        }
    ]
