# Backend Tests

Install the CIR and backend packages in editable mode, then run the backend suite from the
repository root:

```powershell
python -m pip install -e ".\cir[dev]" -e ".\backend[dev]"
python -m pytest backend\tests -q
```
