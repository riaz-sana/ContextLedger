import * as vscode from "vscode";
import * as client from "./ctxClient";

let outputChannel: vscode.OutputChannel;
let statusBarItem: vscode.StatusBarItem;

export function activate(context: vscode.ExtensionContext): void {
  outputChannel = vscode.window.createOutputChannel("ContextLedger");

  // Status bar item showing the active skill profile
  statusBarItem = vscode.window.createStatusBarItem(
    vscode.StatusBarAlignment.Left,
    50
  );
  statusBarItem.command = "ContextLedger.switchProfile";
  statusBarItem.tooltip = "ContextLedger: click to switch profile";
  statusBarItem.text = "$(book) ctx";
  statusBarItem.show();
  context.subscriptions.push(statusBarItem);

  // --- Commands ---

  context.subscriptions.push(
    vscode.commands.registerCommand("ContextLedger.query", async () => {
      const text = await vscode.window.showInputBox({
        prompt: "Enter your context query",
        placeHolder: "e.g. how does the merge resolver work?",
      });
      if (!text) {
        return;
      }
      try {
        outputChannel.clear();
        outputChannel.appendLine(`> query: ${text}`);
        outputChannel.show(true);
        const result = await client.query(text);
        outputChannel.appendLine(result);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        vscode.window.showErrorMessage(`ContextLedger query failed: ${msg}`);
      }
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand(
      "ContextLedger.switchProfile",
      async () => {
        try {
          const raw = await client.listProfiles();
          const profiles = raw
            .split("\n")
            .map((l) => l.trim())
            .filter((l) => l.length > 0);

          if (profiles.length === 0) {
            vscode.window.showInformationMessage(
              "No ContextLedger profiles found."
            );
            return;
          }

          const picked = await vscode.window.showQuickPick(profiles, {
            placeHolder: "Select a skill profile",
          });
          if (!picked) {
            return;
          }

          const result = await client.switchProfile(picked);
          statusBarItem.text = `$(book) ${picked}`;
          vscode.window.showInformationMessage(result || `Switched to ${picked}`);
        } catch (err: unknown) {
          const msg = err instanceof Error ? err.message : String(err);
          vscode.window.showErrorMessage(
            `ContextLedger switchProfile failed: ${msg}`
          );
        }
      }
    )
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("ContextLedger.status", async () => {
      try {
        outputChannel.clear();
        outputChannel.appendLine("> status");
        outputChannel.show(true);
        const result = await client.status();
        outputChannel.appendLine(result);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        vscode.window.showErrorMessage(`ContextLedger status failed: ${msg}`);
      }
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("ContextLedger.ingestSession", async () => {
      vscode.window.showInformationMessage(
        "ContextLedger: session ingestion is not yet implemented."
      );
    })
  );

  // --- Update status bar on active editor change ---

  const updateStatusBar = async (editor: vscode.TextEditor | undefined) => {
    if (!editor) {
      return;
    }
    try {
      const filePath = editor.document.uri.fsPath;
      const profile = await client.projectRoute(filePath);
      if (profile) {
        statusBarItem.text = `$(book) ${profile}`;
      }
    } catch {
      // projectRoute may fail if CLI is not installed; silently ignore
    }
  };

  context.subscriptions.push(
    vscode.window.onDidChangeActiveTextEditor(updateStatusBar)
  );

  // Run once for the currently active editor
  updateStatusBar(vscode.window.activeTextEditor);
}

export function deactivate(): void {
  if (outputChannel) {
    outputChannel.dispose();
  }
  if (statusBarItem) {
    statusBarItem.dispose();
  }
}
