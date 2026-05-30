import { useState, type ReactNode } from 'react';
import { useAsyncEffect } from '@jokester/ts-commonutil/lib/react/hook/use-async-effect';
import { Message } from 'primereact/message';
import { ProgressSpinner } from 'primereact/progressspinner';

export type Slice<T> = { data: T | null; err: string | null };

export function useSlice<T>(fetcher: (signal?: AbortSignal) => Promise<T>): Slice<T> {
  const [state, setState] = useState<Slice<T>>({ data: null, err: null });
  useAsyncEffect(async (running, released) => {
    const ac = new AbortController();
    void released.then(() => ac.abort());
    try {
      const d = await fetcher(ac.signal);
      if (running.current) setState({ data: d, err: null });
    } catch (e) {
      if (ac.signal.aborted) return;
      if (running.current) setState({ data: null, err: String(e) });
    }
  }, []);
  return state;
}

export function SliceBody<T>({
  slice,
  render,
}: {
  slice: Slice<T>;
  render: (d: T) => ReactNode;
}) {
  if (slice.err) return <Message severity="error" text={slice.err} />;
  if (slice.data === null) return <ProgressSpinner style={{ width: '1.5rem', height: '1.5rem' }} />;
  return <>{render(slice.data)}</>;
}
