/** Mirrors xumret.executor.models.StreamConfig */
export interface StreamConfig {
  mode: 'lines' | 'binary';
  back_pressure: boolean;
}

/** Mirrors xumret.executor.models.ProcessStep */
export interface ProcessStep {
  argv: string[];
  stdout_stream?: StreamConfig;
  stderr_stream?: StreamConfig;
}

/** Mirrors xumret.executor.models.Connection */
export type Connection = { type: 'pipe' } | { type: 'temp_file' };

/** Mirrors xumret.executor.models.RunOption */
export interface RunOption {
  slug?: string | null;
  mutex_by_slug?: boolean;
}

/** Mirrors xumret.executor.models.PhoneCommand */
export interface PhoneCommand {
  name: string;
  steps: ProcessStep[];
  connections: Connection[];
  daemon: boolean;
  run_option?: RunOption;
}
