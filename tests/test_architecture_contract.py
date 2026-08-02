from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.validate_architecture_contract import SCHEMA_PATH, validate


def _contract() -> dict:
    return {
        "schema_version": "1.0.0",
        "layers": {
            "runtime": "runtime",
            "adapters": "adapters",
            "integrations": "integrations",
            "composition": "seoctl",
        },
        "allowed_layer_edges": [
            {"source": "composition", "target": "runtime"},
            {"source": "composition", "target": "adapters"},
            {"source": "composition", "target": "integrations"},
        ],
        "exceptions": [],
        "network_modules": [],
        "network_transports": {},
    }


def _fixture(tmp_path: Path, contract: dict, sources: dict[str, str]) -> tuple[Path, Path]:
    for package in ("runtime", "adapters", "integrations", "seoctl"):
        package_path = tmp_path / package
        package_path.mkdir(parents=True)
        (package_path / "__init__.py").write_text("", encoding="utf-8")
    for relative, source in sources.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
    contract_path = tmp_path / "governance" / "architecture-contract.json"
    schema_path = tmp_path / "schemas" / "architecture-contract.schema.json"
    contract_path.parent.mkdir(parents=True)
    schema_path.parent.mkdir(parents=True)
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    schema_path.write_bytes(SCHEMA_PATH.read_bytes())
    return contract_path, schema_path


def test_canonical_architecture_contract_passes() -> None:
    assert validate() == []


def test_forbidden_runtime_to_integration_import_fails(tmp_path: Path) -> None:
    contract_path, schema_path = _fixture(
        tmp_path,
        _contract(),
        {"runtime/new_boundary.py": "from integrations.provider import Client\n"},
    )
    errors = validate(tmp_path, contract_path, schema_path)
    assert "forbidden dependency edge: runtime.new_boundary -> integrations.provider" in errors


def test_new_internal_cycle_fails_even_with_exact_exceptions(tmp_path: Path) -> None:
    contract = _contract()
    contract["exceptions"] = [
        {
            "source": "runtime.port",
            "target": "integrations.provider",
            "owner": "Architecture owner",
            "rationale": "Adversarial fixture exact edge with accountable ownership.",
            "removal_phase": "P5",
        },
        {
            "source": "integrations.provider",
            "target": "runtime.port",
            "owner": "Architecture owner",
            "rationale": "Adversarial fixture reverse edge with accountable ownership.",
            "removal_phase": "P5",
        },
    ]
    contract_path, schema_path = _fixture(
        tmp_path,
        contract,
        {
            "runtime/port.py": "from integrations.provider import Client\n",
            "integrations/provider.py": "from runtime.port import Port\n",
        },
    )
    errors = validate(tmp_path, contract_path, schema_path)
    assert any(error.startswith("internal import cycle:") for error in errors)


def test_single_dot_relative_cycle_fails(tmp_path: Path) -> None:
    contract_path, schema_path = _fixture(
        tmp_path,
        _contract(),
        {
            "runtime/a.py": "from .b import B\n",
            "runtime/b.py": "from .a import A\n",
        },
    )

    assert any(
        error.startswith("internal import cycle:")
        for error in validate(tmp_path, contract_path, schema_path)
    )


def test_multi_dot_relative_cycle_fails(tmp_path: Path) -> None:
    contract_path, schema_path = _fixture(
        tmp_path,
        _contract(),
        {
            "integrations/shared.py": "from .nested.worker import Worker\n",
            "integrations/nested/__init__.py": "",
            "integrations/nested/worker.py": "from ..shared import Shared\n",
        },
    )

    assert any(
        error.startswith("internal import cycle:")
        for error in validate(tmp_path, contract_path, schema_path)
    )


def test_package_init_relative_cycle_fails(tmp_path: Path) -> None:
    contract_path, schema_path = _fixture(
        tmp_path,
        _contract(),
        {
            "runtime/package/__init__.py": "from .worker import Worker\n",
            "runtime/package/worker.py": "from runtime import package\n",
        },
    )

    assert any(
        error.startswith("internal import cycle:")
        for error in validate(tmp_path, contract_path, schema_path)
    )


def test_mixed_absolute_relative_cycle_fails(tmp_path: Path) -> None:
    contract_path, schema_path = _fixture(
        tmp_path,
        _contract(),
        {
            "runtime/package/__init__.py": (
                "from runtime.package import worker as imported_worker\n"
            ),
            "runtime/package/worker.py": "from . import helper\n",
            "runtime/package/helper.py": "from runtime import package as imported_package\n",
        },
    )

    assert any(
        error.startswith("internal import cycle:")
        for error in validate(tmp_path, contract_path, schema_path)
    )


def test_broad_or_unknown_exception_fails_closed(tmp_path: Path) -> None:
    contract = _contract()
    broad = copy.deepcopy(contract)
    broad["exceptions"] = [
        {
            "source": "runtime",
            "target": "integrations",
            "owner": "Architecture owner",
            "rationale": "This intentionally broad mutation must be rejected by schema.",
            "removal_phase": "P5",
        }
    ]
    contract_path, schema_path = _fixture(tmp_path / "broad", broad, {})
    assert any(error.startswith("schema exceptions") for error in validate(tmp_path / "broad", contract_path, schema_path))

    unknown = copy.deepcopy(contract)
    unknown["exceptions"] = [
        {
            "source": "runtime.missing",
            "target": "integrations.missing",
            "owner": "Architecture owner",
            "rationale": "An exception must bind one currently observed exact import edge.",
            "removal_phase": "P5",
        }
    ]
    contract_path, schema_path = _fixture(tmp_path / "unknown", unknown, {})
    errors = validate(tmp_path / "unknown", contract_path, schema_path)
    assert "stale or unknown dependency exception: runtime.missing -> integrations.missing" in errors


def test_new_direct_network_module_fails_until_explicitly_owned(tmp_path: Path) -> None:
    contract_path, schema_path = _fixture(
        tmp_path,
        _contract(),
        {"integrations/new_transport.py": "import urllib.request\n"},
    )
    errors = validate(tmp_path, contract_path, schema_path)
    assert "unapproved network-capable module: integrations/new_transport.py" in errors


def test_registered_network_sink_requires_canonical_transport_mapping(tmp_path: Path) -> None:
    contract = _contract()
    contract["network_modules"] = ["integrations/new_transport.py"]
    contract_path, schema_path = _fixture(
        tmp_path,
        contract,
        {"integrations/new_transport.py": "import urllib.request\n"},
    )
    assert (
        "network sink missing canonical transport mapping: integrations/new_transport.py"
        in validate(tmp_path, contract_path, schema_path)
    )


def test_new_playwright_browser_module_fails_until_explicitly_owned(tmp_path: Path) -> None:
    contract_path, schema_path = _fixture(
        tmp_path,
        _contract(),
        {"integrations/new_browser.py": "from playwright.sync_api import sync_playwright\n"},
    )

    assert "unapproved network-capable module: integrations/new_browser.py" in validate(
        tmp_path, contract_path, schema_path
    )


def test_literal_dynamic_and_process_egress_fail_until_owned(tmp_path: Path) -> None:
    contract_path, schema_path = _fixture(
        tmp_path,
        _contract(),
        {
            "runtime/dynamic_client.py": (
                "import importlib\nclient = importlib.import_module('httpx')\n"
            ),
            "runtime/process_client.py": (
                "import subprocess\nsubprocess.run(['curl', 'https://example.test'])\n"
            ),
        },
    )
    errors = validate(tmp_path, contract_path, schema_path)

    assert "unapproved network-capable module: runtime/dynamic_client.py" in errors
    assert "unapproved network-capable module: runtime/process_client.py" in errors


@pytest.mark.parametrize(
    ("import_line", "call"),
    [
        ("from subprocess import run", "run(args=['curl', 'https://example.test'])"),
        ("from importlib import import_module", "import_module(name='httpx')"),
        ("import subprocess", "subprocess.run(['/usr/bin/curl', 'https://example.test'])"),
        ("import subprocess", "subprocess.run(['CURL.EXE', 'https://example.test'])"),
        ("import subprocess", "subprocess.run(['powershell.exe', 'Invoke-WebRequest'])"),
        ("from builtins import __import__ as load", "load('httpx')"),
        (
            "import subprocess",
            "subprocess.run('\\\"C:\\\\Program Files\\\\curl.exe\\\" https://example.test')",
        ),
        ("import subprocess", "subprocess.run(['/bin/bash', '-c', 'curl https://example.test'])"),
        ("import subprocess", "subprocess.run(['/usr/bin/env', 'curl', 'https://example.test'])"),
        ("import subprocess", "subprocess.run([b'curl', b'https://example.test'])"),
        ("import subprocess", "subprocess.run(['/bin/bash', '-lc', 'curl https://example.test'])"),
        (
            "import subprocess",
            "subprocess.run(['/bin/bash', '--noprofile', '-c', 'wget https://example.test'])",
        ),
        (
            "import subprocess",
            "subprocess.run(['/usr/bin/env', '-u', 'HTTP_PROXY', 'curl', 'https://example.test'])",
        ),
        (
            "import subprocess",
            "subprocess.run(['/usr/bin/env', '-C', '/tmp', 'wget', 'https://example.test'])",
        ),
        (
            "import subprocess",
            "subprocess.run(['/bin/sh', '-c', 'HTTP_PROXY=local exec curl https://example.test'])",
        ),
        (
            "import subprocess",
            "subprocess.run('HTTP_PROXY=local exec wget https://example.test', shell=True)",
        ),
        ("import os", "os.system('HTTP_PROXY=local exec curl https://example.test')"),
        ("import subprocess", "subprocess.run('git status;curl https://example.test', shell=True)"),
        ("import subprocess", "subprocess.run('git status&&curl https://example.test', shell=True)"),
        ("import subprocess", "subprocess.run('git status||wget https://example.test', shell=True)"),
        ("import subprocess", "subprocess.run('git status|/usr/bin/curl https://example.test', shell=True)"),
        ("import subprocess", "subprocess.run('git status&wget https://example.test', shell=True)"),
        ("import subprocess", "subprocess.run('git status\\ncurl https://example.test', shell=True)"),
        ("import subprocess", "subprocess.run('echo ok>/tmp/result;curl https://example.test', shell=True)"),
        ("import subprocess", "subprocess.run('echo $(curl https://example.test)', shell=True)"),
        ("import subprocess", "subprocess.run('echo `wget https://example.test`', shell=True)"),
        ("import subprocess", "subprocess.run(['/bin/bash', '-c', 'git status;curl https://example.test'])"),
        ("import subprocess", "subprocess.run(['/bin/sh', '-c', 'git&&/usr/bin/wget https://example.test'])"),
        ("import subprocess", "subprocess.run(['/bin/sh', '-c', 'command curl https://example.test'])"),
        ("import subprocess", "subprocess.run(['/bin/sh', '-c', 'command -- /usr/bin/wget https://example.test'])"),
        ("import subprocess", "subprocess.run(['/bin/sh', '-c', 'exec env -u HTTP_PROXY command -p curl'])"),
        ("import subprocess", "subprocess.run(['placeholder', '-c', 'curl https://example.test'], executable='/bin/bash')"),
        ("import subprocess", "subprocess.run(args=['placeholder', '-lc', 'wget https://example.test'], executable='BASH.EXE')"),
        ("import subprocess", "subprocess.run(['placeholder', '--noprofile', '-c', 'env -u HTTP_PROXY command -- /usr/bin/curl'], executable='/bin/sh')"),
        ("import subprocess", "subprocess.run(['placeholder', '-c', 'HTTP_PROXY=local exec env -C /tmp command -p wget'], executable=r'C:\\tools\\bash.exe')"),
        ("import subprocess", "subprocess.run(['placeholder', '-u', 'HTTP_PROXY', 'curl'], executable='/usr/bin/env')"),
        ("import subprocess", "subprocess.run(args=['placeholder', '-C', '/tmp', 'wget'], executable='ENV.EXE')"),
        ("import subprocess", "subprocess.run(['placeholder', 'bash', '-c', 'exec command -- /usr/bin/curl'], executable='/usr/bin/env')"),
        ("import subprocess", "subprocess.run(['placeholder', 'env', '-u', 'HTTP_PROXY', 'sh', '-c', 'command -p wget'], executable=r'C:\\tools\\env.exe')"),
    ],
)
def test_equivalent_literal_egress_spellings_fail_until_owned(
    tmp_path: Path, import_line: str, call: str
) -> None:
    contract_path, schema_path = _fixture(
        tmp_path, _contract(), {"runtime/process_client.py": f"{import_line}\n{call}\n"}
    )

    assert "unapproved network-capable module: runtime/process_client.py" in validate(
        tmp_path, contract_path, schema_path
    )


@pytest.mark.parametrize(
    "source",
    [
        "import importlib\nimportlib.import_module('integrations.google.client')\n",
        "import importlib as loader\nloader.import_module('integrations.google.client')\n",
        "from importlib import import_module\nimport_module(name='integrations.google.client')\n",
    ],
)
def test_literal_dynamic_internal_import_obeys_dependency_direction(
    tmp_path: Path, source: str
) -> None:
    contract_path, schema_path = _fixture(
        tmp_path,
        _contract(),
        {
            "runtime/dynamic_dependency.py": source,
            "integrations/google/client.py": "VALUE = 1\n",
        },
    )

    assert (
        "forbidden dependency edge: runtime.dynamic_dependency -> integrations.google.client"
        in validate(tmp_path, contract_path, schema_path)
    )


def test_literal_dynamic_import_participates_in_cycles(tmp_path: Path) -> None:
    contract_path, schema_path = _fixture(
        tmp_path,
        _contract(),
        {
            "runtime/a.py": "import importlib\nimportlib.import_module('runtime.b')\n",
            "runtime/b.py": "import runtime.a\n",
        },
    )
    assert any(
        error.startswith("internal import cycle: runtime.a -> runtime.b")
        for error in validate(tmp_path, contract_path, schema_path)
    )


def test_relative_literal_dynamic_import_obeys_edges_and_cycles(tmp_path: Path) -> None:
    contract_path, schema_path = _fixture(
        tmp_path,
        _contract(),
        {
            "runtime/a.py": (
                "import importlib\n"
                "importlib.import_module('.google.client', package='integrations')\n"
                "importlib.import_module('.b', package='runtime')\n"
            ),
            "runtime/b.py": "import runtime.a\n",
            "integrations/google/client.py": "VALUE = 1\n",
        },
    )
    errors = validate(tmp_path, contract_path, schema_path)
    assert "forbidden dependency edge: runtime.a -> integrations.google.client" in errors
    assert any(error.startswith("internal import cycle: runtime.a -> runtime.b") for error in errors)


@pytest.mark.parametrize(
    "call",
    [
        "importlib.import_module('.b')",
        "importlib.import_module('.b', package=PACKAGE)",
        "importlib.import_module('..b', package='runtime')",
    ],
)
def test_unresolved_literal_relative_import_fails_closed(tmp_path: Path, call: str) -> None:
    contract_path, schema_path = _fixture(
        tmp_path,
        _contract(),
        {"runtime/a.py": f"import importlib\nPACKAGE = 'runtime'\n{call}\n"},
    )
    assert any(
        error.startswith("unresolved literal relative import: runtime.a")
        for error in validate(tmp_path, contract_path, schema_path)
    )


@pytest.mark.parametrize(
    "source",
    [
        "from builtins import __import__ as load\nload('integrations.google.client')\n",
        "import builtins as bi\nbi.__import__('integrations.google.client')\n",
    ],
)
def test_builtin_literal_import_obeys_dependency_direction(tmp_path: Path, source: str) -> None:
    contract_path, schema_path = _fixture(
        tmp_path,
        _contract(),
        {
            "runtime/dynamic_dependency.py": source,
            "integrations/google/client.py": "VALUE = 1\n",
        },
    )
    assert (
        "forbidden dependency edge: runtime.dynamic_dependency -> integrations.google.client"
        in validate(tmp_path, contract_path, schema_path)
    )


def test_approved_literal_dynamic_import_remains_valid(tmp_path: Path) -> None:
    contract_path, schema_path = _fixture(
        tmp_path,
        _contract(),
        {
            "seoctl/composition.py": "import importlib\nimportlib.import_module('runtime.contract')\n",
            "runtime/contract.py": "VALUE = 1\n",
        },
    )
    assert validate(tmp_path, contract_path, schema_path) == []


@pytest.mark.parametrize(
    "call",
    [
        "subprocess.run(['git', 'status'])",
        "subprocess.run(['curl-helper', 'value'])",
        "subprocess.run(['scurl', 'value'])",
        "subprocess.run(['tool', 'https://example.test/curl'])",
    ],
)
def test_non_network_process_names_do_not_create_false_egress(
    tmp_path: Path, call: str
) -> None:
    contract_path, schema_path = _fixture(
        tmp_path,
        _contract(),
        {"runtime/process_client.py": f"import subprocess\n{call}\n"},
    )
    assert validate(tmp_path, contract_path, schema_path) == []


@pytest.mark.parametrize(
    "call",
    [
        "subprocess.run(['/bin/bash', '-c', 'git status'])",
        "subprocess.run(['/bin/bash', '-c', 'echo curl'])",
        "subprocess.run(['/usr/bin/env', 'git', 'status'])",
        "subprocess.run(['/usr/bin/env', 'NAME=curl', 'git', 'status'])",
        "subprocess.run([r'\"C:\\Program Files\\curl-helper.exe\"', 'value'])",
        "subprocess.run(['/bin/bash', '-lc', 'echo curl'])",
        "subprocess.run(['/bin/bash', '--noprofile', '-c', 'printf curl'])",
        "subprocess.run(['/usr/bin/env', '-u', 'HTTP_PROXY', 'git', 'status'])",
        "subprocess.run(['/usr/bin/env', '-C', '/tmp', 'git', 'status'])",
        "subprocess.run(['/usr/bin/env', '--unset=HTTP_PROXY', '--chdir=/tmp', 'git'])",
        "subprocess.run('HTTP_PROXY=local exec echo curl', shell=True)",
        "subprocess.run('command git status', shell=True)",
        "subprocess.run('command -- git status', shell=True)",
        "subprocess.run('command -p echo curl', shell=True)",
        "subprocess.run('command -v curl', shell=True)",
        "subprocess.run('command -V -- wget', shell=True)",
        "subprocess.run(\"echo 'literal;curl|wget&&x>y$(curl)`wget`'\", shell=True)",
        "subprocess.run('echo \"literal;curl|wget&&x>y\"', shell=True)",
        "subprocess.run(['/bin/bash', '-c', \"echo 'literal;curl|wget&&x>y'\"])",
        "subprocess.run(['/bin/bash', '-c', 'command git status'])",
        "subprocess.run(['git', 'status;curl&&wget|ftp>/tmp/value'])",
        "subprocess.run(['echo', 'https://example.test/?a=1&b=2;curl'])",
        "subprocess.run(['placeholder', '-c', \"echo 'curl;wget|ftp'\"], executable='/bin/bash')",
        "subprocess.run(['placeholder', '-c', 'command -v curl'], executable='/bin/sh')",
        "subprocess.run(['placeholder', '-c', 'curl https://example.test'], executable='/usr/bin/git')",
        "subprocess.run(['placeholder', 'curl;wget&&ftp'], executable='/bin/echo')",
        "subprocess.run(['placeholder', '-u', 'HTTP_PROXY', 'git', 'status'], executable='/usr/bin/env')",
        "subprocess.run(['placeholder', 'bash', '-c', \"echo 'curl;wget|ftp'\"], executable='env.exe')",
        "subprocess.run(['placeholder', 'sh', '-c', 'command -v curl'], executable='/usr/bin/env')",
        "subprocess.run(['placeholder', 'echo', 'https://example.test/?a=1&b=2;curl'], executable='env.exe')",
    ],
)
def test_literal_wrapper_negative_controls_remain_safe(tmp_path: Path, call: str) -> None:
    contract_path, schema_path = _fixture(
        tmp_path,
        _contract(),
        {"runtime/process_client.py": f"import subprocess\n{call}\n"},
    )
    assert validate(tmp_path, contract_path, schema_path) == []


@pytest.mark.parametrize(
    "call",
    [
        "subprocess.run(['/bin/bash', '--unknown', '-c', 'git status'])",
        "subprocess.run(['/usr/bin/env', '--unknown', 'git', 'status'])",
        "subprocess.run(['/bin/sh', OPTION, 'git status'])",
        "subprocess.run(['/usr/bin/env', OPTION, 'git', 'status'])",
        "subprocess.run(['command', OPTION, 'git'])",
        "subprocess.run(COMMAND, shell=True)",
        "subprocess.run(ARGS, executable='/bin/bash')",
        "subprocess.run(['placeholder', '-c', COMMAND], executable='/bin/sh')",
        "subprocess.run(['placeholder', '--unknown', 'git'], executable='bash.exe')",
        "subprocess.run(ARGS, executable='/usr/bin/env')",
        "subprocess.run(['placeholder', '-u', NAME, 'git'], executable='env.exe')",
        "subprocess.run(['placeholder', '--unknown', 'git'], executable='/usr/bin/env')",
    ],
)
def test_unrecognized_or_dynamic_wrapper_grammar_fails_closed(
    tmp_path: Path, call: str
) -> None:
    contract_path, schema_path = _fixture(
        tmp_path,
        _contract(),
        {"runtime/process_client.py": f"import subprocess\nOPTION = '-c'\n{call}\n"},
    )
    assert "unapproved network-capable module: runtime/process_client.py" in validate(
        tmp_path, contract_path, schema_path
    )


@pytest.mark.parametrize(
    ("import_line", "call"),
    [
        ("from subprocess import run", "run(['curl', 'https://example.test'])"),
        (
            "from subprocess import run as execute",
            "execute(['curl', 'https://example.test'])",
        ),
        ("from subprocess import Popen", "Popen(['curl', 'https://example.test'])"),
        (
            "from subprocess import Popen as launch",
            "launch(['curl', 'https://example.test'])",
        ),
        (
            "from subprocess import check_output",
            "check_output(['curl', 'https://example.test'])",
        ),
        (
            "from subprocess import check_output as capture",
            "capture(['curl', 'https://example.test'])",
        ),
    ],
)
def test_imported_subprocess_egress_fails_until_owned(
    tmp_path: Path, import_line: str, call: str
) -> None:
    contract_path, schema_path = _fixture(
        tmp_path,
        _contract(),
        {"runtime/process_client.py": f"{import_line}\n{call}\n"},
    )

    assert "unapproved network-capable module: runtime/process_client.py" in validate(
        tmp_path, contract_path, schema_path
    )


@pytest.mark.parametrize(
    ("import_line", "call"),
    [
        ("from importlib import import_module", "import_module('httpx')"),
        ("from importlib import import_module as load", "load('httpx')"),
    ],
)
def test_imported_dynamic_egress_fails_until_owned(
    tmp_path: Path, import_line: str, call: str
) -> None:
    contract_path, schema_path = _fixture(
        tmp_path,
        _contract(),
        {"runtime/dynamic_client.py": f"{import_line}\nclient = {call}\n"},
    )

    assert "unapproved network-capable module: runtime/dynamic_client.py" in validate(
        tmp_path, contract_path, schema_path
    )


@pytest.mark.parametrize(
    "source",
    [
        "import importlib\nload = importlib.import_module\nload('httpx')\n",
        "import importlib\nholder.load = importlib.import_module\nholder.load('requests')\n",
        "import importlib\napi = importlib\nload = api.import_module\nload('urllib.request')\n",
        "import importlib\nload: object = importlib.import_module\nload('httpx')\n",
        "load = __import__\nload('httpx')\n",
        "import builtins\nholder.load = builtins.__import__\nholder.load('requests')\n",
        "import importlib\nload = importlib.import_module\nload = choose_at_runtime\nload('httpx')\n",
    ],
)
def test_bounded_assignment_aliases_cannot_hide_literal_network_imports(
    tmp_path: Path, source: str
) -> None:
    contract_path, schema_path = _fixture(
        tmp_path, _contract(), {"runtime/dynamic_client.py": source}
    )
    assert "unapproved network-capable module: runtime/dynamic_client.py" in validate(
        tmp_path, contract_path, schema_path
    )


@pytest.mark.parametrize(
    "source",
    [
        "load = helper\nload('httpx')\n",
        "import importlib\nload = importlib.import_module\nload('runtime.optional')\n",
        "import importlib\nholder.load = helper\nholder.load('httpx')\n",
    ],
)
def test_non_reflective_assignments_and_safe_targets_remain_negative_controls(
    tmp_path: Path, source: str
) -> None:
    contract_path, schema_path = _fixture(
        tmp_path, _contract(), {"runtime/dynamic_client.py": source}
    )
    assert validate(tmp_path, contract_path, schema_path) == []


def test_network_allowlist_cannot_hide_missing_module(tmp_path: Path) -> None:
    contract = _contract()
    contract["network_modules"] = ["runtime/missing.py"]
    contract_path, schema_path = _fixture(tmp_path, contract, {})
    assert "stale or missing network-module entry: runtime/missing.py" in validate(
        tmp_path, contract_path, schema_path
    )
