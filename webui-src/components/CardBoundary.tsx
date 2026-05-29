import { Component, type ErrorInfo, type ReactNode } from 'react';
import { Card, type CardProps } from 'primereact/card';
import { Message } from 'primereact/message';

import { createDebugLogger } from '~/util/log';

const log = createDebugLogger(import.meta.url);

interface State {
  error: Error | null;
}

export class CardBoundary extends Component<CardProps, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    log('caught %o %o', error, info);
  }

  render(): ReactNode {
    const { children, ...cardProps } = this.props;
    if (this.state.error) {
      return (
        <Card {...cardProps}>
          <Message severity="error" text={this.state.error.message || String(this.state.error)} />
        </Card>
      );
    }
    return <Card {...cardProps}>{children}</Card>;
  }
}
