from __future__ import annotations

import shutil

import pytest

from codementor_ai.agents import build_agents
from codementor_ai.project import is_runnable_source, java_main_class, run_project

needs_jdk = pytest.mark.skipif(shutil.which("javac") is None, reason="needs a JDK (javac) on PATH")

MAIN = 'public class Main {\n  public static void main(String[] args) {\n    System.out.println("2 + 3 = " + Calculator.add(2, 3));\n  }\n}\n'
CALCULATOR = "public class Calculator {\n  public static int add(int a, int b) { return a + b; }\n}\n"


def test_java_main_class_includes_the_package():
    assert java_main_class("Main.java", MAIN) == "Main"
    assert java_main_class("src/app/App.java", "package app;\npublic class App {}\n") == "app.App"


def test_java_test_sources_are_not_runnable_programs():
    assert is_runnable_source("Main.java")
    assert not is_runnable_source("CalculatorTest.java")
    assert not is_runnable_source("tests/Helper.java")


@needs_jdk
def test_java_project_compiles_and_runs_with_helper_classes():
    files = {"Main.java": MAIN, "Calculator.java": CALCULATOR, "tests/CalculatorTest.java": "import org.junit.jupiter.api.Test;\n"}
    output = run_project(files, language="Java")
    assert "=== Compile: javac -encoding UTF-8 -d build Calculator.java Main.java ===\nExit code: 0" in output
    assert output.endswith("Exit code: 0\n2 + 3 = 5")


@needs_jdk
def test_opening_a_helper_class_runs_the_class_with_main():
    output = run_project({"Main.java": MAIN, "Calculator.java": CALCULATOR}, entrypoint="Calculator.java", language="Java")
    assert output.endswith("2 + 3 = 5")


@needs_jdk
def test_compile_errors_stop_before_running():
    output = run_project({"Main.java": 'public class Main { public static void main(String[] a) { int x = "no"; } }\n'}, language="Java")
    assert "error: incompatible types" in output
    assert output.endswith("Not run because compilation failed.")


def test_non_python_files_use_a_tester_without_the_python_sandbox():
    agents = build_agents()
    assert agents["tester"].tools and not agents["tester_no_sandbox"].tools
    assert "JUnit 5" in agents["tester_no_sandbox"].instructions
    assert "public class Calculator" in agents["code_writer"].instructions
