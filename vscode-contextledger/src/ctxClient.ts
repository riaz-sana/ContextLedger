import { exec } from "child_process";

const CLI_MODULE = "python -m contextledger";

function run(command: string): Promise<string> {
  return new Promise((resolve, reject) => {
    exec(command, { timeout: 30_000 }, (error, stdout, stderr) => {
      if (error) {
        reject(new Error(stderr || error.message));
        return;
      }
      resolve(stdout.trim());
    });
  });
}

export function query(text: string, profile?: string): Promise<string> {
  const profileFlag = profile ? ` --profile ${profile}` : "";
  return run(`${CLI_MODULE} query "${text}"${profileFlag}`);
}

export function status(): Promise<string> {
  return run(`${CLI_MODULE} status`);
}

export function listProfiles(): Promise<string> {
  return run(`${CLI_MODULE} list`);
}

export function switchProfile(name: string): Promise<string> {
  return run(`${CLI_MODULE} checkout ${name}`);
}

export function projectRoute(filePath: string): Promise<string> {
  return run(`${CLI_MODULE} project route --file "${filePath}"`);
}
