# SPDX-License-Identifier: Apache-2.0
import unittest

import pytest
from antlr4 import InputStream
from tests.coverage.case_file_parser import parse_stream, parse_one_file, ParseError
from tests.coverage.nodes import CaseLiteral


def parse_string(input_string):
    return parse_stream(InputStream(input_string), "test_string")


def make_header(version, include):
    return f"""### SUBSTRAIT_SCALAR_TEST: {version}
### SUBSTRAIT_INCLUDE: '{include}'

"""


def test_parse_basic_example():
    header = make_header("v1.0", "/extensions/functions_arithmetic.yaml")
    tests = """# 'Basic examples without any special cases'
add(120::i8, 5::i8) = 125::i8
add(100::i16, 100::i16) = 200::i16

# Overflow examples demonstrating overflow behavior
add(120::i8, 10::i8) [overflow:ERROR] = <!ERROR>
"""

    test_file = parse_string(header + tests)
    assert len(test_file.testcases) == 3


def test_parse_date_time_example():
    header = make_header("v1.0", "/extensions/functions_datetime.yaml")
    tests = """# timestamp examples using the timestamp type
lt('2016-12-31T13:30:15'::ts, '2017-12-31T13:30:15'::ts) = true::bool
"""

    test_file = parse_string(header + tests)
    assert len(test_file.testcases) == 1
    assert test_file.testcases[0].func_name == "lt"
    assert test_file.testcases[0].base_uri == "/extensions/functions_datetime.yaml"
    assert (
        test_file.testcases[0].group.name
        == "timestamp examples using the timestamp type"
    )
    assert test_file.testcases[0].result == CaseLiteral("true", "bool")
    assert test_file.testcases[0].args[0] == CaseLiteral("2016-12-31T13:30:15", "ts")
    assert test_file.testcases[0].args[1] == CaseLiteral("2017-12-31T13:30:15", "ts")


def test_parse_decimal_example():
    header = make_header("v1.0", "extensions/functions_arithmetic_decimal.yaml")
    tests = """# basic
power(8::dec<38,0>, 2::dec<38, 0>) = 64::fp64
power(1.0::dec<38, 0>, -1.0::dec<38, 0>) = 1.0::fp64
power(-1::dec, 0.5::dec<38,1>) [complex_number_result:NAN] = nan::fp64
"""
    test_file = parse_string(header + tests)
    assert len(test_file.testcases) == 3
    assert test_file.testcases[0].func_name == "power"
    assert (
        test_file.testcases[0].base_uri
        == "extensions/functions_arithmetic_decimal.yaml"
    )
    assert test_file.testcases[0].group.name == "basic"
    assert test_file.testcases[0].result == CaseLiteral("64", "fp64")
    assert test_file.testcases[0].args[0] == CaseLiteral("8", "dec<38,0>")
    assert test_file.testcases[0].args[1] == CaseLiteral("2", "dec<38,0>")


def test_parse_decimal_example_with_nan():
    header = make_header("v1.0", "extensions/functions_arithmetic_decimal.yaml")
    tests = """# basic
power(-1::dec, 0.5::dec<38,1>) [complex_number_result:NAN] = nan::fp64
"""
    test_file = parse_string(header + tests)
    assert len(test_file.testcases) == 1
    assert test_file.testcases[0].func_name == "power"
    assert (
        test_file.testcases[0].base_uri
        == "extensions/functions_arithmetic_decimal.yaml"
    )
    assert test_file.testcases[0].group.name == "basic"
    assert test_file.testcases[0].result == CaseLiteral("nan", "fp64")
    assert test_file.testcases[0].args[0] == CaseLiteral("-1", "dec")
    assert test_file.testcases[0].args[1] == CaseLiteral("0.5", "dec<38,1>")


def test_parse_file_add():
    test_file = parse_one_file("../cases/arithmetic/add.test")
    assert len(test_file.testcases) == 15
    assert test_file.testcases[0].func_name == "add"
    assert test_file.testcases[0].base_uri == "/extensions/functions_arithmetic.yaml"
    assert test_file.include == "/extensions/functions_arithmetic.yaml"


def test_parse_file_lt_datetime():
    test_file = parse_one_file("../cases/datetime/lt_datetime.test")
    assert len(test_file.testcases) == 13
    assert test_file.testcases[0].func_name == "lt"
    assert test_file.testcases[0].base_uri == "/extensions/functions_datetime.yaml"


def test_parse_file_power_decimal():
    test_file = parse_one_file("../cases/arithmetic_decimal/power.test")
    assert len(test_file.testcases) == 9
    assert test_file.testcases[0].func_name == "power"
    assert (
        test_file.testcases[0].base_uri
        == "extensions/functions_arithmetic_decimal.yaml"
    )


@pytest.mark.parametrize(
    "input_func_test, position, expected_message",
    [
        (
            "add(-12::i8, +5::i8) = -7.0::i8",
            29,
            "no viable alternative at input '-7.0::i8'",
        ),
        (
            "add(123.5::i8, 5::i8) = 125::i8",
            11,
            "no viable alternative at input '123.5::i8'",
        ),
        (
            "add(123.5::i16, 5.5::i16) = 125::i16",
            11,
            "no viable alternative at input '123.5::i16'",
        ),
        (
            "add(123.5::i32, 5.5::i32) = 125::i32",
            21,
            "no viable alternative at input '5.5::i32'",
        ),
        (
            "add(123f::i64, 5.5::i64) = 125::i64",
            7,
            "no viable alternative at input '123f'",
        ),
        (
            "add(123::i64, 5_000::i64) = 5123::i64",
            15,
            "no viable alternative at input '5_000'",
        ),
        (
            "add(123::dec<38,10>, 5.0E::dec<38,10>) = 123::dec<38,10>",
            24,
            "no viable alternative at input '5.0E'",
        ),
        (
            "add(123::dec<38,10>, 1a.2::dec<38,10>) = 123::fp32",
            22,
            "no viable alternative at input '1a'",
        ),
        (
            "add(123::dec<38,10>, 1.2.3::dec<38,10>) = 123::fp32",
            24,
            "no viable alternative at input '1.2.'",
        ),
        (
            "add(123::dec<38,10>, +-12.3::dec<38,10>) = 123::i64",
            21,
            "extraneous input '+'",
        ),
        ("add(123::fp32, .5E2::fp32) = 123::fp32", 15, "extraneous input '.'"),
        ("add(123::fp32, 4.1::fp32) = ++123::fp32", 28, "extraneous input '+'"),
        (
            "add(123::fp32, 2.5E::fp32) = 123::fp32",
            18,
            "no viable alternative at input '2.5E'",
        ),
        (
            "add(123::fp32, 1.4E+::fp32) = 123::fp32",
            18,
            "no viable alternative at input '1.4E'",
        ),
        (
            "add(123::fp32, 3.E.5::fp32) = 123::fp32",
            17,
            "no viable alternative at input '3.E'",
        ),
    ],
)
def test_parse_errors_with_bad_cases(input_func_test, position, expected_message):
    header = make_header("v1.0", "extensions/functions_arithmetic.yaml") + "# basic\n"
    with pytest.raises(ParseError) as pm:
        parse_string(header + input_func_test + "\n")
    assert f"Syntax error at line 5, column {position}: {expected_message}" in str(
        pm.value
    )