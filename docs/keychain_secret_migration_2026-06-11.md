# Keychain Secret Migration - 2026-06-11

## What Changed

- Migrated these live secrets into macOS Keychain under the `Kampung AI` service:
  - `OPENAI_API_KEY`
  - `GOOGLE_API_KEY`
  - `XAI_API_KEY`
  - `ANTHROPIC_API_KEY`
  - `TELEGRAM_BOT_TOKEN`
- Set local `.env` to `MAYA_SECRET_PROVIDER=auto`.
- In `auto` mode, Maya tries Keychain first and falls back to `.env` if the Keychain item is missing.

## What Did Not Move

- LiveKit or other provider secrets
- Non-secret hotkey/runtime settings

## Verification

- Keychain reads succeeded for every migrated secret name above.
- Auto provider reads succeeded for the provider secrets.
- Log/doc leak scan for migrated names returned zero raw secret leaks.
- Verification output showed presence only, not values or lengths.

## Rollback

Set this in `.env`:

```bash
MAYA_SECRET_PROVIDER=env
```

That returns Maya to `.env`-only behavior without deleting the Keychain item.
