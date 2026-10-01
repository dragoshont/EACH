# hello-repair fixture

A deliberately trivial, deterministic repair fixture used to exercise the
full EACH M1 pipeline end to end:

local fixture issue → approved immutable spec → sanitized declared
materials → `FixtureModel` (canned, non-inferential) → scoped unified
diff → real no-network container executor → deterministic failing/passing
tests → audit stub → private JSON/Markdown receipt.

`src/greet.py` contains a known, intentional one-line bug (`"Hell, "`
instead of `"Hello, "`). `tests/test_greet.py` fails against the buggy
source and passes once `each.demo.run_hello_repair` applies the fixture
model's patch. This fixture is never used to claim anything about a real
model's repair capability — see `each/models/fixture.py`.
