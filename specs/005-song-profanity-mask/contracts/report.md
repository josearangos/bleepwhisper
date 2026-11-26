# Contract: JSON report

The report stays a JSON array, one object per masked span, sorted by `start`.

## Preset / custom mask runs — unchanged

```json
[
  { "word": "damn", "start": 12.34, "end": 12.79 }
]
```

## Song style runs

```json
[
  { "word": "damn", "start": 12.34, "end": 12.79, "style": "vocal-dropout" }
]
```

## Song style run with fallback (mono input)

```json
[
  { "word": "damn", "start": 12.34, "end": 12.79, "style": "dip", "requested_style": "vocal-dropout" }
]
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `word` | string | yes | matched words of the span, space-joined |
| `start` | number (s, 3 decimals) | yes | |
| `end` | number (s, 3 decimals) | yes | |
| `style` | `"vocal-dropout" \| "reverse" \| "dip"` | song styles only | style actually applied |
| `requested_style` | string | only on fallback | style the user asked for |

An empty array still means no forbidden words were found.
