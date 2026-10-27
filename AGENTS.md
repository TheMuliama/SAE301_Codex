# SAÉ 3.01 — permanent development rules

This repository implements a bidirectional QPSK DATA/ACK link for two
ADALM-Pluto SDRs.  Python/PyADI-IIO and the protocol documented in
`docs/PROTOCOL.md` are authoritative; the historical GNU Radio notes in
`references/` are background material only.

## Safety

- Never transmit RF unless the user has explicitly confirmed suitable coaxial
  attenuation, power levels, Pluto limits, and laboratory/regulatory approval.
- Hardware diagnostics must be receive-only/non-transmitting by default.
- Never present simulation evidence as physical-radio evidence.

## Engineering and evidence

- Keep framing, QPSK/DSP, application state, and I/Q transports separated.
- Preserve Linux and Windows support and Python 3.10+ compatibility.
- Do not silently change the frame layout, bit order, QPSK mapping, or default
  radio parameters; update tests and `docs/PROTOCOL.md` with any such change.
- Add or update automated tests for each behavior change. Run relevant tests,
  inspect failures, fix them, and run regression tests.
- Record exact commands and actual outcomes in `docs/JOURNAL.md`. Never invent
  test results, measurements, hardware observations, or commit hashes.
- Store concise reproducible outputs in `docs/evidence/`; exclude secrets,
  local device addresses, virtual environments, and bulky captures.
- A hardware-dependent criterion remains `NOT TESTED` until exercised on the
  physical devices.

## Required journal entry fields

Every significant entry records: objective, changes made, technical decisions,
architecture impact, regression risks, expected impact, exact tests and actual
results, evidence, PASS/FAIL/NOT TESTED criteria, result, known limitations,
and next action.

