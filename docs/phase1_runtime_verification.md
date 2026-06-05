# Phase 1 Runtime Verification

Date: 2026-06-05

Branch: main  
Tag: v0.1.0-phase1-bootstrap

## Result

Phase 1 data/control pipeline verified on `http://slither.com/io`.

## Evidence

- Extension content script connected.
- Page-context injector loaded.
- Native messaging host connected.
- `discoveredSelf`, `discoveredSnakes`, and `discoveredFood` became true after spawn.
- Python received live state frames.
- Python emitted `PHASE1_DUMMY` steering commands.
- Browser acknowledged commands with `command_ack`.
- Boost remained false.

## Latency Summary

```json
{
  "count": 1190,
  "max_ms": 11.400000005960464,
  "mean_ms": 2.5343697477539044,
  "median_ms": 2.0,
  "min_ms": 1.2999999970197678,
  "p90_ms": 4.0999999940395355,
  "p95_ms": 5.0,
  "p99_ms": 7.200000002980232
}
```

## Notes

Current `slither.com/io` runtime reports coordinates outside the older `0..21000` assumption. Phase 1 records those as warnings instead of blocking commands.

Some runtime packets report very low or zero `fam`; this is treated as telemetry for Phase 1.
