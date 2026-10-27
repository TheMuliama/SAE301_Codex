## Evidence-Based Development and Code Quality

You must follow an evidence-based development process.

The objective is to produce reliable, understandable, maintainable, and verifiable code.

### 1. Before modifying code

- Identify the problem or feature being addressed.
- Explain why the change is necessary.
- Identify affected modules and dependencies.
- Assess potential regressions.
- Define measurable acceptance criteria.

### 2. During implementation

- Prefer small, focused changes.
- Keep architecture simple and modular.
- Add or update automated tests for modified functionality.
- Avoid unrelated refactoring.
- Do not silently change the communication protocol, QPSK mapping, or radio parameters.
- Preserve Linux and Windows compatibility.

### 3. After implementation

Execute all relevant automated tests.

When appropriate, also execute:
- Static analysis and linting.
- Type checking.
- Integration tests.
- Simulation tests.
- Regression tests.

Investigate failures and correct them when possible.

Never claim tests passed unless they were actually executed.

### 4. Mandatory development journal

Update `docs/JOURNAL.md` after every significant change.

Each entry must include:

**Objective**
What was the intended result?

**Changes**
Which files, functions, dependencies, configurations, or interfaces changed?

**Justification**
Why was this solution selected? What alternatives were considered?

**Regression risks**
What existing behavior could break because of this change?

**Impact**
How could the change affect functionality, performance, reliability, hardware compatibility, or deployment?

**Verification**
Which exact commands were executed? What were the actual results?

**Evidence**
Include relevant commit hashes, test outputs, logs, measurements, or links to evidence files.

**Acceptance criteria**
For each criterion, indicate PASS, FAIL, or NOT TESTED.

**Conclusion**
State whether the objective was ACHIEVED, PARTIALLY ACHIEVED, or NOT ACHIEVED, based on the evidence.

**Limitations**
Identify anything that remains unverified, including hardware-specific behavior.

### 5. Evidence preservation

Create `docs/evidence/` for useful and reproducible supporting evidence.

Store concise test reports, simulation measurements, and relevant diagnostic outputs.

Do not commit large generated datasets, sensitive system information, or machine-specific secrets.

When tests fail, preserve useful failure information instead of documenting only the final success.

### 6. Quality gate

A development milestone can be marked complete only when:

1. Its acceptance criteria are satisfied.
2. Required automated tests pass.
3. Relevant regression tests pass.
4. The development journal is updated.
5. Evidence supports the conclusions.
6. Remaining risks and untested conditions are explicitly documented.

If a milestone cannot be fully verified, mark it PARTIALLY ACHIEVED or NOT ACHIEVED.

Do not confuse successful simulation with successful ADALM-Pluto hardware validation.

### 7. Final report

After each milestone, summarize:

- What changed.
- Why it changed.
- What was tested.
- What passed or failed.
- What could still break.
- Whether the objective was achieved.

Prioritize accuracy and reproducibility over optimistic conclusions.