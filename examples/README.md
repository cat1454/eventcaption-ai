# Synthetic example

Generate a new software fixture with:

```sh
python -m eventcaption_ai demo --output runs/synthetic-example
python -m eventcaption_ai replay runs/synthetic-example/records.jsonl
```

The fixture uses synthetic pixels and scripted WAIT/create/revise/withdraw decisions. It loads no model, consumes no GPU budget, and demonstrates no caption quality. The generated receipt labels it `synthetic_software_fixture`. Each run path must be new.
