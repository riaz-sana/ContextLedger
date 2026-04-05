# ContextLedger VS Code Extension

Integrates ContextLedger skill versioning and context synthesis into VS Code.

## Prerequisites

- Python 3.11+ with the `contextledger` package installed (`pip install contextledger`)
- The `python -m contextledger` CLI must be available on your PATH

## Commands

Open the command palette (`Ctrl+Shift+P`) and type "ContextLedger":

| Command | Description |
|---------|-------------|
| **ContextLedger: Query Context** | Search your context memory and display results |
| **ContextLedger: Switch Profile** | Pick a skill profile from the registry |
| **ContextLedger: Status** | Show current ContextLedger status |
| **ContextLedger: Ingest Session** | (Placeholder) Ingest the current session |

## Status Bar

The status bar shows the active skill profile for the current file. Click it to switch profiles.

## Development

```bash
cd vscode-contextledger
npm install
npm run compile
```

Press `F5` in VS Code to launch an Extension Development Host for testing.
