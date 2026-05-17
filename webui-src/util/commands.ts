/** Mirrors xumret.executor.models.StreamConfig */
export interface StreamConfig {
  mode?: 'lines' | 'binary';
  capture?: boolean;
  forward_dest_process_idx?: number | null;
  /** @deprecated legacy field, ignored by backend */
  back_pressure?: boolean;
}

/** Mirrors xumret.executor.models.CommandStep */
export interface ProcessStep {
  argv: string[];
  stdout_stream?: StreamConfig;
  stderr_stream?: StreamConfig;
}

/** @deprecated legacy field, ignored by backend */
export type Connection = { type: 'pipe' } | { type: 'temp_file' };

/** Mirrors xumret.executor.models.RunOption */
export interface RunOption {
  timeout?: number | null;
  slug?: string | null;
  mutex_by_slug?: boolean;
}

/** Mirrors xumret.executor.models.PhoneCommand */
export interface PhoneCommand {
  name: string;
  desc?: string | null;
  steps: ProcessStep[];
  run_option?: RunOption;
  /** @deprecated legacy field, ignored by backend */
  connections?: Connection[];
  /** @deprecated legacy field, ignored by backend */
  daemon?: boolean;
}
