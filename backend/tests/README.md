# Backend Tests

Install the local packages in editable mode, then run the backend suite from the repository root:

```powershell
python -m pip install -e ".\cir[dev]" -e ".\preview[dev]" -e ".\adapters\unreal[dev]" -e ".\backend[dev]"
python -m pytest backend\tests -q
```
