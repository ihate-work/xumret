/** Mirrors xumret.executor.models.ProcessStep */
export interface ProcessStep {
  argv: string[];
}

/** Mirrors xumret.executor.models.Connection */
export type Connection = { type: 'pipe' } | { type: 'temp_file' };

/** Mirrors xumret.executor.models.PhoneCommand */
export interface PhoneCommand {
  name: string;
  steps: ProcessStep[];
  connections: Connection[];
  daemon: boolean;
}
